"""
Unit tests for type definitions in src/types.py.
Although these are mostly type aliases, we verify that the runtime introspection
of these types matches our expectations for valid values.
"""

from typing import get_args
from src.types import ThinkingLevel, LogTag

def test_thinking_level_values():
    """
    Verify that ThinkingLevel literal contains all values defined in the Gemini API spec.
    Schema: minimal, low, medium, high
    """
    valid_values = get_args(ThinkingLevel)
    
    expected = {"minimal", "low", "medium", "high"}
    
    # Check that all expected values are present in the type definition
    for val in expected:
        assert val in valid_values, f"Missing expected thinking level: {val}"

def test_log_tag_values():
    """
    Verify that LogTag literal contains the tags used by the GUI for coloring.
    """
    valid_tags = get_args(LogTag)
    
    expected_tags = {"user", "ai", "error", "info"}
    
    for tag in expected_tags:
        assert tag in valid_tags, f"Missing expected log tag: {tag}"