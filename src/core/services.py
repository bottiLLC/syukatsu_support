"""
Service layer for Gemini API interactions and cost calculation.

This module provides the `LLMService` for communicating with the Gemini API
and the `CostCalculator` for estimating usage costs. It handles asynchronous streaming responses,
event processing, and error management for the Job Hunting Support application.
"""

import logging
from typing import Any, AsyncGenerator, Optional

from google.genai import errors as genai_errors
from google.genai import types as genai_types
from google import genai
from pydantic import ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
    before_sleep_log,
)

from src.core.base import BaseGeminiService
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
        """
        pricing = cls._get_pricing(model_name)
        is_estimate = False

        if not pricing:
            pricing = PRICING_TABLE.get("gemini-3.1-pro")
            is_estimate = True

        if not pricing:
            return "Cost info unavailable"

        non_cached_input = max(0, usage.input_tokens - usage.cached_tokens)
        input_cost = (non_cached_input / cls._TOKEN_UNIT) * pricing.input_price

        cached_cost = (
            usage.cached_tokens / cls._TOKEN_UNIT
        ) * pricing.cached_input_price

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
        sorted_keys = sorted(PRICING_TABLE.keys(), key=len, reverse=True)

        for key in sorted_keys:
            if key in model_name:
                return PRICING_TABLE[key]
        return None


class LLMService(BaseGeminiService):
    """
    Service for interacting with the Gemini API.

    Handles the streaming of analysis responses using the Google GenAI SDK
    and converts API events into application-specific domain objects.
    """

    async def stream_analysis(
        self, payload: ResponseRequestPayload
    ) -> AsyncGenerator[StreamResult, None]:
        """
        Executes an asynchronous streaming request to the Gemini API.
        """
        try:
            logger.info(f"Starting async stream analysis with model: {payload.model}")

            async for result in self._execute_api_call(payload):
                yield result

        except Exception as e:
            logger.exception("Unexpected error in stream_analysis")
            yield StreamError(
                message=f"\n[Unexpected Error] 予期せぬエラーが発生しました: {e}"
            )

    @retry(
        retry=retry_if_exception_type(genai_errors.APIError),
        wait=wait_random_exponential(multiplier=1, max=60),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _create_stream(self, client: genai.Client, payload: ResponseRequestPayload) -> Any:
        """
        Helper method to initiate the API stream with retry logic.
        """
        contents = []
        for msg in payload.input:
            role = "model" if msg.role == "assistant" else "user"
            parts = []
            for c in msg.content:
                if c.type == "input_text":
                    parts.append(genai_types.Part.from_text(text=c.text))
            contents.append(genai_types.Content(role=role, parts=parts))

        config_args = {"temperature": 0.7}
        
        if payload.thinking:
            config_args["thinking_config"] = {"thinking_level": payload.thinking.level}
        
        # Add RAG files directly to context here
        file_parts = []
        if payload.tools:
            from src.core.rag_services import db
            import asyncio
            for tool in payload.tools:
                t_type = getattr(tool, "type", None)
                if t_type == "file_search":
                    for vid in getattr(tool, "vector_store_ids", []):
                        for fid in db.get_files(vid):
                            try:
                                try:
                                    f_obj = await client.aio.files.get(name=fid)
                                except AttributeError:
                                    # Fallback for older SDK versions or sync client if aio is not available
                                    f_obj = await asyncio.to_thread(client.files.get, name=fid)
                                file_parts.append(genai_types.Part.from_uri(file_uri=f_obj.uri, mime_type=f_obj.mime_type))
                            except Exception as e:
                                logger.error(f"Failed to load RAG file {fid}: {e}")

        if file_parts:
            logger.info(f"Injecting {len(file_parts)} files into Gemini context.")
            if contents and contents[0].role == "user":
                contents[0].parts = file_parts + contents[0].parts
            else:
                contents.insert(0, genai_types.Content(role="user", parts=file_parts))

        if payload.instructions:
            config_args["system_instruction"] = payload.instructions
            
        config = genai_types.GenerateContentConfig(**config_args)

        return await client.aio.models.generate_content_stream(
            model=payload.model,
            contents=contents,
            config=config,
        )

    async def _execute_api_call(
        self, payload: ResponseRequestPayload
    ) -> AsyncGenerator[StreamResult, None]:
        """
        Executes the API call within an async context manager and yields results.
        Handles specific API exceptions and converts them to StreamError events.
        """
        try:
            async with self.get_async_client() as client:
                stream = await self._create_stream(client, payload)

                yield StreamResponseCreated(response_id="gemini-stream")

                async for chunk in stream:
                    if chunk.text:
                        yield StreamTextDelta(delta=chunk.text)
                        
                    if getattr(chunk, "usage_metadata", None):
                        usage = chunk.usage_metadata
                        in_tokens = getattr(usage, "prompt_token_count", 0)
                        out_tokens = getattr(usage, "candidates_token_count", 0)
                        tot_tokens = getattr(usage, "total_token_count", 0)
                        cached = getattr(usage, "cached_content_token_count", 0)
                        
                        yield StreamUsage(
                            input_tokens=in_tokens,
                            output_tokens=out_tokens,
                            total_tokens=tot_tokens,
                            cached_tokens=cached,
                        )

        except genai_errors.APIError as e:
             logger.error(f"Gemini API error: {e}")
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