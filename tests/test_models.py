"""
Unit tests for data models defined in src.core.models.
Focuses on validation and normalization logic for API payloads.
"""

from typing import List
import pytest
from pydantic import ValidationError

from src.core.models import (
    ResponseRequestPayload,
    FileSearchTool,
    InputMessage,
    InputTextContent,
    ReasoningOptions,
)


class TestResponseRequestPayload:
    """Tests for the main request payload model."""

    def test_normalize_string_input(self):
        """
        Verifies that a simple string input is automatically converted
        to the required list of InputMessage objects with 'user' role.
        """
        payload = ResponseRequestPayload(
            model="gpt-5.2",
            input="Simple user query",
            instructions="System prompt",
        )

        # Check normalization
        assert isinstance(payload.input, list)
        assert len(payload.input) == 1

        message = payload.input[0]
        assert isinstance(message, InputMessage)
        assert message.role == "user"

        assert len(message.content) == 1
        content_item = message.content[0]
        assert isinstance(content_item, InputTextContent)
        assert content_item.type == "input_text"
        assert content_item.text == "Simple user query"

    def test_pass_structured_input_directly(self):
        """
        Verifies that passing a pre-structured list of dicts works correctly.
        """
        structured_input = [
            {"role": "user", "content": [{"type": "input_text", "text": "Hello"}]},
            {"role": "assistant", "content": [{"type": "input_text", "text": "Hi"}]},
            {"role": "user", "content": [{"type": "input_text", "text": "Next"}]},
        ]

        payload = ResponseRequestPayload(
            model="gpt-5.2",
            input=structured_input,
            instructions="System prompt",
        )

        assert len(payload.input) == 3
        assert payload.input[1].role == "assistant"
        assert payload.input[1].content[0].text == "Hi"

    def test_validation_error_missing_fields(self):
        """Verifies that missing required fields raise ValidationError."""
        # 'instructions' is Optional, so omitting it should NOT raise an error.
        # We test omitting 'model' instead, which IS required.
        with pytest.raises(ValidationError) as excinfo:
            ResponseRequestPayload(
                # model="gpt-5.2",  # Missing required field
                input="test",
            )
        assert "model" in str(excinfo.value)

    def test_reasoning_options_serialization(self):
        """Verifies correct handling of nested reasoning options."""
        payload = ResponseRequestPayload(
            model="gpt-5.2",
            input="test",
            instructions="sys",
            reasoning={"effort": "high"},  # Pass as dict
        )

        assert isinstance(payload.reasoning, ReasoningOptions)
        assert payload.reasoning.effort == "high"


class TestFileSearchTool:
    """Tests for the FileSearchTool model configuration."""

    def test_flat_structure_initialization(self):
        """
        Verifies that passing 'vector_store_ids' works with the flat model structure defined in models.py.
        The actual Pydantic model defines vector_store_ids at the top level.
        """
        tool_data = {
            "type": "file_search",
            "vector_store_ids": ["vs_123", "vs_456"],
        }

        tool = FileSearchTool(**tool_data)

        assert tool.type == "file_search"
        # The model is flat, so we access vector_store_ids directly
        assert tool.vector_store_ids == ["vs_123", "vs_456"]

    def test_default_values(self):
        """Verifies defaults for optional fields."""
        tool = FileSearchTool()
        assert tool.type == "file_search"
        assert tool.vector_store_ids == []