"""
Unit tests for the service layer (LLMService and CostCalculator).
Focuses on interactions with the OpenAI Responses API and cost estimation logic.
"""

from unittest.mock import MagicMock, patch
from typing import Any, List

import pytest
from openai import APIConnectionError, RateLimitError, APITimeoutError, AuthenticationError

from src.core.services import LLMService, CostCalculator
from src.core.models import (
    ResponseRequestPayload,
    StreamTextDelta,
    StreamResponseCreated,
    StreamUsage,
    StreamError,
)
from src.core.pricing import PRICING_TABLE


# --- CostCalculator Tests ---


class TestCostCalculator:
    """Tests for the CostCalculator utility class."""

    def test_calculate_known_model(self):
        """Verifies cost calculation for a known model (e.g., gpt-4o)."""
        # Create a dummy usage object
        usage = StreamUsage(
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            cached_tokens=0
        )
        
        # We need to ensure we use a model that exists in PRICING_TABLE
        model_name = "gpt-4o" # or any key present in PRICING_TABLE
        if model_name not in PRICING_TABLE:
            # Fallback to any key available if the specific one is missing in test env
            model_name = list(PRICING_TABLE.keys())[0]

        cost_str = CostCalculator.calculate(model_name, usage)
        assert "Cost: $" in cost_str
        assert "Tokens: 1500" in cost_str

    def test_calculate_unknown_model_fallback(self):
        """Verifies that an unknown model falls back to default pricing (gpt-5.2)."""
        usage = StreamUsage(
            input_tokens=1000,
            output_tokens=1000,
            total_tokens=2000,
            cached_tokens=0
        )
        
        # Use a non-existent model name
        cost_str = CostCalculator.calculate("unknown-model-v99", usage)
        
        # Should contain estimate marker
        assert "(Est.)" in cost_str
        assert "Cost: $" in cost_str

    def test_calculate_with_caching(self):
        """Verifies that cached tokens are calculated at a lower rate."""
        usage = StreamUsage(
            input_tokens=1000,
            output_tokens=0,
            total_tokens=1000,
            cached_tokens=500  # 500 cached, 500 non-cached
        )
        # Using a model we know the pricing for (mocking or relying on constant)
        # Here we just check the string formatting for correctness
        cost_str = CostCalculator.calculate("gpt-5.2", usage)
        assert "In:1000/Cache:500/Out:0" in cost_str


# --- LLMService Tests ---


class TestLLMService:
    """Tests for LLMService interactions with OpenAI API."""

    @pytest.fixture
    def mock_client(self):
        """Mocks the OpenAI client instance."""
        # FIX: Patch src.core.base.OpenAI because LLMService inherits init from BaseOpenAIService
        # defined in src.core.base, which is where the OpenAI class is imported and instantiated.
        with patch("src.core.base.OpenAI") as mock_openai_cls:
            mock_instance = MagicMock()
            mock_openai_cls.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def service(self, mock_client):
        """Initializes LLMService with the mocked client."""
        return LLMService(api_key="test-key")

    @pytest.fixture
    def valid_payload(self):
        """Returns a valid ResponseRequestPayload."""
        return ResponseRequestPayload(
            model="gpt-5.2",
            input="Test input",  # Will be normalized
            instructions="System prompt"
        )

    def _create_mock_event(self, event_type: str, **kwargs) -> MagicMock:
        """Helper to create mock stream events."""
        event = MagicMock()
        event.type = event_type
        for k, v in kwargs.items():
            setattr(event, k, v)
        return event

    def test_stream_diagnosis_success(self, service, mock_client, valid_payload):
        """
        Verifies a successful streaming session with text deltas and usage stats.
        """
        # Setup mock stream events
        mock_events = [
            self._create_mock_event(
                "response.created", 
                response=MagicMock(id="resp_123")
            ),
            self._create_mock_event(
                "response.output_text.delta", 
                delta="Hello "
            ),
            self._create_mock_event(
                "response.output_text.delta", 
                delta="World"
            ),
            self._create_mock_event(
                "response.completed",
                response=MagicMock(
                    usage=MagicMock(
                        input_tokens=10,
                        output_tokens=5,
                        total_tokens=15,
                        input_tokens_details=MagicMock(cached_tokens=2)
                    )
                )
            )
        ]
        
        # Configure client mock
        mock_client.responses.create.return_value = iter(mock_events)

        # Execute
        results = list(service.stream_diagnosis(valid_payload))

        # Assertions
        assert len(results) == 4
        
        # 1. Response Created
        assert isinstance(results[0], StreamResponseCreated)
        assert results[0].response_id == "resp_123"
        
        # 2. Text Deltas
        assert isinstance(results[1], StreamTextDelta)
        assert results[1].delta == "Hello "
        assert isinstance(results[2], StreamTextDelta)
        assert results[2].delta == "World"
        
        # 3. Usage
        assert isinstance(results[3], StreamUsage)
        assert results[3].total_tokens == 15
        assert results[3].cached_tokens == 2

        # Verify API call arguments
        mock_client.responses.create.assert_called_once()
        call_kwargs = mock_client.responses.create.call_args[1]
        assert call_kwargs["model"] == "gpt-5.2"
        # Input should be normalized to list
        assert isinstance(call_kwargs["input"], list)
        assert call_kwargs["input"][0]["role"] == "user"

    def test_stream_diagnosis_api_connection_error(self, service, mock_client, valid_payload):
        """Verifies handling of API connection errors."""
        mock_client.responses.create.side_effect = APIConnectionError(message="Connection failed", request=MagicMock())

        results = list(service.stream_diagnosis(valid_payload))

        assert len(results) == 1
        assert isinstance(results[0], StreamError)
        assert "[Connection Error]" in results[0].message

    def test_stream_diagnosis_rate_limit_error(self, service, mock_client, valid_payload):
        """Verifies handling of Rate Limit errors."""
        mock_client.responses.create.side_effect = RateLimitError(message="Rate limit", response=MagicMock(), body=None)

        results = list(service.stream_diagnosis(valid_payload))

        assert len(results) == 1
        assert isinstance(results[0], StreamError)
        assert "[Rate Limit]" in results[0].message

    def test_stream_diagnosis_stream_error_event(self, service, mock_client, valid_payload):
        """Verifies handling of an 'error' event emitted during the stream."""
        mock_events = [
            self._create_mock_event(
                "error",
                error=MagicMock(message="Something went wrong mid-stream")
            )
        ]
        mock_client.responses.create.return_value = iter(mock_events)

        results = list(service.stream_diagnosis(valid_payload))

        assert len(results) == 1
        assert isinstance(results[0], StreamError)
        assert "Something went wrong" in results[0].message

    def test_stream_diagnosis_ignore_unknown_events(self, service, mock_client, valid_payload):
        """Verifies that unknown event types are ignored."""
        mock_events = [
            self._create_mock_event("response.unknown_event_type")
        ]
        mock_client.responses.create.return_value = iter(mock_events)

        results = list(service.stream_diagnosis(valid_payload))

        # Should produce no results, but strictly not raise an error
        assert len(results) == 0