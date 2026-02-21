"""
Service layer for OpenAI API interactions and cost calculation.

This module provides the `LLMService` for communicating with the OpenAI Responses API
and the `CostCalculator` for estimating usage costs. It handles asynchronous streaming responses,
event processing, and error management for the Job Hunting Support application.
"""

import logging
from typing import Any, AsyncGenerator, Optional

from openai import (
    OpenAIError,
    AsyncOpenAI
)
from pydantic import ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
    before_sleep_log,
)

from src.core.base import BaseOpenAIService
from src.core.models import (
    ResponseRequestPayload,
    StreamError,
    StreamResponseCreated,
    StreamResult,
    StreamTextDelta,
    StreamUsage,
)
from src.core.pricing import PRICING_TABLE, ModelPricing

logger = logging.getLogger(__name__)


class CostCalculator:
    """
    Provides utilities to calculate the estimated cost of API usage.
    """

    _TOKEN_UNIT = 1_000_000

    @classmethod
    def calculate(cls, model_name: str, usage: StreamUsage) -> str:
        """
        Calculates the estimated cost for a given model and token usage.

        Args:
            model_name: The identifier of the model used (e.g., "gpt-5.2").
            usage: The token usage statistics (input, output, cached).

        Returns:
            A formatted string displaying token counts and estimated cost in USD.
        """
        pricing = cls._get_pricing(model_name)
        is_estimate = False

        # Fallback to default pricing if model not found
        if not pricing:
            pricing = PRICING_TABLE.get("gpt-5.2")
            is_estimate = True

        if not pricing:
            return "Cost info unavailable"

        # Calculate input cost: (Total Input - Cached) * Input Price
        non_cached_input = max(0, usage.input_tokens - usage.cached_tokens)
        input_cost = (non_cached_input / cls._TOKEN_UNIT) * pricing.input_price

        # Calculate cached input cost
        cached_cost = (
            usage.cached_tokens / cls._TOKEN_UNIT
        ) * pricing.cached_input_price

        # Calculate output cost
        output_cost = (usage.output_tokens / cls._TOKEN_UNIT) * pricing.output_price

        total_cost = input_cost + cached_cost + output_cost
        estimate_label = "(Est.)" if is_estimate else ""

        return (
            f"Tokens: {usage.total_tokens} "
            f"(In:{usage.input_tokens}/Cache:{usage.cached_tokens}/Out:{usage.output_tokens}) | "
            f"Cost: ${total_cost:.5f} {estimate_label}"
        )

    @staticmethod
    def _get_pricing(model_name: str) -> Optional[ModelPricing]:
        """
        Retrieves the pricing configuration for the specified model.

        Matches the model name against the pricing table keys, prioritizing
        longer (more specific) matches first.

        Args:
            model_name: The model identifier.

        Returns:
            The ModelPricing object if found, otherwise None.
        """
        # Sort keys by length in descending order to match specific models first
        sorted_keys = sorted(PRICING_TABLE.keys(), key=len, reverse=True)

        for key in sorted_keys:
            if key in model_name:
                return PRICING_TABLE[key]
        return None


class LLMService(BaseOpenAIService):
    """
    Service for interacting with the OpenAI Responses API.

    Handles the streaming of analysis responses using AsyncOpenAI context managers
    and converts API events into application-specific domain objects.
    """

    async def stream_analysis(
        self, payload: ResponseRequestPayload
    ) -> AsyncGenerator[StreamResult, None]:
        """
        Executes an asynchronous streaming request to the Responses API.

        Args:
            payload: The request payload containing model, input, and other parameters.

        Yields:
            StreamResult objects representing text deltas, response metadata,
            usage statistics, or errors.
        """
        try:
            # Convert Pydantic model to dict, excluding None to respect API defaults
            request_params = payload.model_dump(exclude_none=True)

            logger.info(f"Starting async stream analysis with model: {payload.model}")

            # Yield from async generator
            async for result in self._execute_api_call(request_params):
                yield result

        except Exception as e:
            # Catch-all for any unhandled exceptions during the generator setup
            logger.exception("Unexpected error in stream_analysis")
            yield StreamError(
                message=f"\n[Unexpected Error] 予期せぬエラーが発生しました: {e}"
            )

    @retry(
        retry=retry_if_exception_type(OpenAIError),
        wait=wait_random_exponential(multiplier=1, max=60),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _create_stream(self, client: AsyncOpenAI, request_params: dict) -> Any:
        """
        Helper method to initiate the API stream with retry logic.
        This only retries the *connection* establishment, not the stream iteration.
        """
        # STRICTLY using client.responses.create per requirements
        return await client.responses.create(**request_params)

    async def _execute_api_call(
        self, request_params: dict
    ) -> AsyncGenerator[StreamResult, None]:
        """
        Executes the API call within an async context manager and yields results.
        Handles specific API exceptions and converts them to StreamError events.
        """
        try:
            async with self.get_async_client() as client:
                stream = await self._create_stream(client, request_params)

                async for event in stream:
                    result = self._process_event(event)
                    if result:
                        yield result

        except OpenAIError as e:
            logger.error(f"OpenAI API error: {e}")
            from src.core.errors import translate_api_error
            msg = translate_api_error(e)
            yield StreamError(message=f"\n[API Error] {msg}")
        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            yield StreamError(
                message=f"\n[Validation Error] リクエストデータの形式が不正です: {e}"
            )
        except Exception as e:
            logger.exception("Error during stream iteration")
            yield StreamError(
                message=f"\n[Stream Error] ストリーム処理中にエラーが発生しました: {e}"
            )

    def _process_event(self, event: Any) -> Optional[StreamResult]:
        """
        Parses a raw API event into a domain object.

        Args:
            event: The event object returned by the OpenAI SDK stream.

        Returns:
            A StreamResult object if the event is relevant, otherwise None.
        """
        # Event type checking based on OpenAPI 'ResponseStreamEvent' schema
        event_type = getattr(event, "type", None)

        if not event_type:
            return None

        if event_type == "response.output_text.delta":
            return self._handle_text_delta(event)

        if event_type == "response.created":
            return self._handle_response_created(event)

        if event_type == "response.completed":
            return self._handle_response_completed(event)

        if event_type == "error":
            return self._handle_error_event(event)

        return None

    def _handle_text_delta(self, event: Any) -> Optional[StreamTextDelta]:
        """Handles 'response.output_text.delta' events."""
        delta_content = getattr(event, "delta", None)
        if delta_content:
            return StreamTextDelta(delta=delta_content)
        return None

    def _handle_response_created(
        self, event: Any
    ) -> Optional[StreamResponseCreated]:
        """Handles 'response.created' events."""
        response_obj = getattr(event, "response", None)
        if response_obj and hasattr(response_obj, "id"):
            return StreamResponseCreated(response_id=response_obj.id)
        return None

    def _handle_response_completed(self, event: Any) -> Optional[StreamUsage]:
        """
        Handles 'response.completed' events to extract usage statistics.
        """
        response_obj = getattr(event, "response", None)
        if not response_obj:
            return None

        usage_obj = getattr(response_obj, "usage", None)
        if not usage_obj:
            return None

        # Extract usage fields safely with defaults
        input_tokens = getattr(usage_obj, "input_tokens", 0)
        output_tokens = getattr(usage_obj, "output_tokens", 0)
        total_tokens = getattr(usage_obj, "total_tokens", 0)

        # Extract cached tokens from input_tokens_details
        cached_tokens = 0
        input_details = getattr(usage_obj, "input_tokens_details", None)
        if input_details:
            cached_tokens = getattr(input_details, "cached_tokens", 0)

        return StreamUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cached_tokens=cached_tokens,
        )

    def _handle_error_event(self, event: Any) -> StreamError:
        """
        Handles 'error' events from the stream.
        """
        error_obj = getattr(event, "error", None)
        message = "Unknown stream error"

        if error_obj:
            if hasattr(error_obj, "message"):
                message = error_obj.message
            elif isinstance(error_obj, dict):
                message = error_obj.get("message", message)
            else:
                message = str(error_obj)

        return StreamError(message=f"\n[Stream Error] {message}")