"""
Unit tests for type definitions in src/types.py.
Although these are mostly type aliases, we verify that the runtime introspection
of these types matches our expectations for valid values.
"""

from typing import get_args
from src.types import ReasoningEffort, LogTag

def test_reasoning_effort_values():
    """
    Verify that ReasoningEffort literal contains all values defined in the OpenAPI spec.
    Schema: none, minimal, low, medium, high, xhigh
    """
    valid_values = get_args(ReasoningEffort)
    
    expected = {"none", "minimal", "low", "medium", "high", "xhigh"}
    
    # Check that all expected values are present in the type definition
    for val in expected:
        assert val in valid_values, f"Missing expected reasoning effort: {val}"

def test_log_tag_values():
    """
    Verify that LogTag literal contains the tags used by the GUI for coloring.
    """
    valid_tags = get_args(LogTag)
    
    expected_tags = {"user", "ai", "error", "info"}
    
    for tag in expected_tags:
        assert tag in valid_tags, f"Missing expected log tag: {tag}"