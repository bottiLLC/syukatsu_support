"""
Unit tests for data models defined in src/core/models.py.
Ensures Pydantic models correctly validate and serialize data according to the OpenAI Responses API schema.
"""

import pytest
from pydantic import ValidationError

from src.core.models import (
    ResponseRequestPayload,
    InputMessage,
    InputTextContent,
    FileSearchTool,
    ThinkingOptions,
    StreamTextDelta,
    StreamResponseCreated,
    StreamUsage,
    StreamError,
)

class TestResponseRequestPayload:
    """Tests for the main API request payload model."""

    def test_payload_normalization_string_input(self):
        """
        Verifies that a simple string input is correctly normalized into 
        the complex List[InputMessage] structure required by the API.
        """
        payload = ResponseRequestPayload(
            model="gemini-3.1-pro",
            input="Help me with financial analysis."
        )

        # 1. Check strict structure
        assert len(payload.input) == 1
        message = payload.input[0]
        assert isinstance(message, InputMessage)
        assert message.role == "user"
        
        # 2. Check content nesting
        assert len(message.content) == 1
        content = message.content[0]
        assert isinstance(content, InputTextContent)
        assert content.type == "input_text"
        assert content.text == "Help me with financial analysis."

    def test_payload_explicit_list_input(self):
        """
        Verifies that passing a pre-formatted list of InputMessage objects works as is.
        """
        raw_input = [
            InputMessage(
                role="user", 
                content=[InputTextContent(text="Explicit input")]
            )
        ]
        payload = ResponseRequestPayload(
            model="gemini-3.1-pro",
            input=raw_input
        )
        
        assert payload.input == raw_input
        assert payload.input[0].content[0].text == "Explicit input"

    def test_payload_with_tools(self):
        """Verifies correct serialization of tools (RAG/File Search)."""
        tools = [
            FileSearchTool(vector_store_ids=["vs_123"])
        ]
        payload = ResponseRequestPayload(
            model="gemini-3.1-pro",
            input="Check this file",
            tools=tools
        )
        
        dump = payload.model_dump(exclude_none=True)
        assert "tools" in dump
        assert dump["tools"][0]["type"] == "file_search"
        assert dump["tools"][0]["vector_store_ids"] == ["vs_123"]

    def test_payload_validation_failure(self):
        """Verifies that missing required fields raises ValidationError."""
        with pytest.raises(ValidationError):
            ResponseRequestPayload(
                # Missing 'model' and 'input'
                instructions="System prompt only" 
            )

class TestStreamEvents:
    """Tests for stream response event models."""

    def test_stream_text_delta(self):
        delta = StreamTextDelta(delta="Hello")
        assert delta.delta == "Hello"

    def test_stream_usage(self):
        usage = StreamUsage(
            input_tokens=10, 
            output_tokens=20, 
            total_tokens=30,
            cached_tokens=5
        )
        assert usage.total_tokens == 30
        assert usage.cached_tokens == 5

    def test_stream_error(self):
        error = StreamError(message="Something broke")
        assert "Something broke" in error.message