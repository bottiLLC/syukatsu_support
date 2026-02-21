"""
Unit tests for the base service module (src/core/base.py).
"""

import pytest
from src.core.base import BaseGeminiService

class TestBaseGeminiService:
    """Tests for the abstract base class initialization."""

    def test_init_success(self):
        """Verify that the service initializes with correct key."""
        service = BaseGeminiService(api_key="test-key")
        assert service._api_key == "test-key"

    def test_init_missing_key(self):
        """Verify that missing API key raises ValueError."""
        with pytest.raises(ValueError):
            BaseGeminiService(api_key="")

        with pytest.raises(ValueError):
            BaseGeminiService(api_key=None)  # type: ignore