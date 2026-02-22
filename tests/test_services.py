"""
Unit tests for the service layer (LLMService and CostCalculator).
Focuses on interactions with the Gemini API and cost estimation logic.
"""

import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Any, List

import pytest
from google.genai import errors as genai_errors
from google.genai import types as genai_types

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

    def test_calculate_cost_with_valid_model(self):
        """Verifies cost calculation for a known model (e.g., gemini-3.1-pro)."""
        usage = StreamUsage(
            input_tokens=100_000,
            output_tokens=50_000,
            total_tokens=150_000,
            cached_tokens=0,
        )
        
        model_name = "gemini-3.1-pro-preview"
        if model_name not in PRICING_TABLE:
            model_name = list(PRICING_TABLE.keys())[0]

        cost_str = CostCalculator.calculate(model_name, usage)
        assert "Cost: $" in cost_str

    def test_calculate_unknown_model_fallback(self):
        """Verifies that an unknown model falls back to default pricing (gemini-3.1-pro-preview)."""
        usage = StreamUsage(
            input_tokens=1000,
            output_tokens=1000,
            total_tokens=2000,
            cached_tokens=0
        )
        
        cost_str = CostCalculator.calculate("unknown-model-v99", usage)
        assert "(Est.)" in cost_str
        assert "Cost: $" in cost_str

    def test_calculate_with_caching(self):
        """Verifies that cached tokens are calculated at a lower rate."""
        usage = StreamUsage(
            input_tokens=1000,
            output_tokens=0,
            total_tokens=1000,
            cached_tokens=500
        )
        cost_str = CostCalculator.calculate("gemini-3.1-pro-preview", usage)
        assert "In:1000/Cache:500/Out:0" in cost_str


# --- LLMService Tests ---

class TestLLMService:
    """Tests for LLMService interactions with Gemini API."""

    @pytest.fixture
    def mock_client(self):
        """Mocks the genai.Client instance."""
        with patch("src.core.base.genai.Client") as mock_client_cls:
            mock_instance = MagicMock()
            # client.aio must be a MagicMock where .close() is an AsyncMock
            mock_aio = MagicMock()
            mock_aio.close = AsyncMock()
            mock_aio.aclose = AsyncMock()
            mock_instance.aio = mock_aio
            mock_client_cls.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def service(self, mock_client):
        """Initializes LLMService with the mocked client."""
        return LLMService(api_key="test-key")

    @pytest.fixture
    def valid_payload(self):
        """Returns a valid ResponseRequestPayload."""
        return ResponseRequestPayload(
            model="gemini-3.1-pro-preview",
            input="Test input",
            instructions="System prompt"
        )

    def _create_mock_chunk(self, text: str = "", usage=None, response_id: str = None) -> MagicMock:
        """Helper to create mock stream chunks."""
        chunk = MagicMock()
        chunk.text = text
        chunk.usage_metadata = usage
        if response_id:
            chunk.response_id = response_id
        return chunk

    async def _mock_async_generator(self, items):
        for item in items:
            yield item

    @pytest.mark.asyncio
    async def test_stream_analysis_success(self, service, mock_client, valid_payload):
        """
        Verifies a successful streaming session with text deltas and usage stats.
        """
        usage_mock = MagicMock()
        usage_mock.prompt_token_count = 10
        usage_mock.candidates_token_count = 5
        usage_mock.total_token_count = 15
        usage_mock.cached_content_token_count = 2

        mock_events = [
            self._create_mock_chunk(text="Hello ", response_id="mock-id-123"),
            self._create_mock_chunk(text="World", usage=usage_mock)
        ]
        
        mock_client.aio.models.generate_content_stream = AsyncMock(
            return_value=self._mock_async_generator(mock_events)
        )

        results = [res async for res in service.stream_analysis(valid_payload)]

        # 1 ResponseCreated, 2 TextDelta, 1 StreamUsage = 4 total events
        assert len(results) == 4
        
        assert isinstance(results[0], StreamResponseCreated)
        assert results[0].response_id == "mock-id-123"
        
        assert isinstance(results[1], StreamTextDelta)
        assert results[1].delta == "Hello "
        assert isinstance(results[2], StreamTextDelta)
        assert results[2].delta == "World"
        
        assert isinstance(results[3], StreamUsage)
        assert results[3].total_tokens == 15
        assert results[3].cached_tokens == 2

        mock_client.aio.models.generate_content_stream.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_analysis_api_connection_error(self, service, mock_client, valid_payload):
        """Verifies handling of API errors."""
        mock_client.aio.models.generate_content_stream.side_effect = genai_errors.APIError(500, {"message": "Connection failed"})

        results = [res async for res in service.stream_analysis(valid_payload)]

        assert len(results) == 1
        assert isinstance(results[0], StreamError)
        assert "Connection failed" in results[0].message

    @pytest.mark.asyncio
    async def test_stream_analysis_rate_limit_error(self, service, mock_client, valid_payload):
        """Verifies handling of Rate Limit errors."""
        mock_client.aio.models.generate_content_stream.side_effect = genai_errors.APIError(429, {"message": "Rate limit"})

        results = [res async for res in service.stream_analysis(valid_payload)]

        assert len(results) == 1
        assert isinstance(results[0], StreamError)
        assert "利用制限エラー" in results[0].message

    @pytest.mark.asyncio
    async def test_stream_analysis_stream_error_event(self, service, mock_client, valid_payload):
        """Verifies handling of an unexpected exception during the stream."""
        mock_client.aio.models.generate_content_stream.side_effect = Exception("Something went wrong mid-stream")

        results = [res async for res in service.stream_analysis(valid_payload)]

        assert len(results) == 1
        assert isinstance(results[0], StreamError)
        assert "Something went wrong" in results[0].message