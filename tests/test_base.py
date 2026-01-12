"""
Unit tests for the base service module (src/core/base.py).
"""

from unittest.mock import patch

import pytest

from src.config.app_config import AppConfig
from src.core.base import BaseOpenAIService


class TestBaseOpenAIService:
    """Tests for the abstract base class initialization."""

    def test_init_success(self):
        """Verify that the client initializes with correct config."""
        # Patch OpenAI to avoid actual network calls or key validation
        with patch("src.core.base.OpenAI") as MockOpenAI:
            service = BaseOpenAIService(api_key="test-key")

            # Check if OpenAI was called with expected params
            MockOpenAI.assert_called_once()
            _, kwargs = MockOpenAI.call_args

            assert kwargs["api_key"] == "test-key"
            assert kwargs["timeout"] == AppConfig.API_TIMEOUT
            assert kwargs["max_retries"] == AppConfig.API_MAX_RETRIES

            # Verify the _client attribute is set
            assert service._client == MockOpenAI.return_value

    def test_init_missing_key(self):
        """Verify that missing API key raises ValueError."""
        # Test empty string
        with pytest.raises(ValueError):
            BaseOpenAIService(api_key="")

        # Test None
        with pytest.raises(ValueError):
            BaseOpenAIService(api_key=None)  # type: ignore