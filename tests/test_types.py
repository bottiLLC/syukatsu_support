import pytest
from typing import get_args
from src.types import ReasoningEffort, LogTag

class TestSharedTypes:

    def test_reasoning_effort_values(self):
        """
        [Integrity] Verify ReasoningEffort Literal contains all API-supported levels.
        """
        # Get the tuple of allowed values from the Literal
        allowed_values = get_args(ReasoningEffort)
        
        expected_values = {
            "none", "minimal", "low", "medium", "high", "xhigh"
        }
        
        # Check that all expected values are present
        assert set(allowed_values) == expected_values
        
        # Check ordering or type if strictness is needed (optional)
        assert isinstance(allowed_values, tuple)
        assert all(isinstance(v, str) for v in allowed_values)

    def test_log_tag_values(self):
        """
        [Integrity] Verify LogTag Literal contains the UI logging keys.
        """
        allowed_tags = get_args(LogTag)
        
        expected_tags = {"user", "ai", "error", "info"}
        
        assert set(allowed_tags) == expected_tags
        assert "error" in allowed_tags
        assert "ai" in allowed_tags