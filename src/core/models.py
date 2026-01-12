"""
Data models for the OpenAI Responses API.

This module defines Pydantic models that strictly adhere to the `openapi.documented.yml`
specifications for the `/v1/responses` endpoint. It handles validation, serialization,
and normalization of request payloads and response stream events.
"""

from typing import List, Literal, Optional, Union, Any
from pydantic import BaseModel, Field, field_validator

# --- Input Message Models (Strict Schema) ---


class InputTextContent(BaseModel):
    """
    Represents the text content of an input message.
    Schema: {"type": "input_text", "text": "..."}
    """

    type: Literal["input_text"] = "input_text"
    text: str


class InputMessage(BaseModel):
    """
    Represents a message in the conversation history.
    Schema: {"type": "message", "role": "user" | "assistant", "content": [...]}
    """

    type: Literal["message"] = "message"
    role: Literal["user", "assistant"]
    content: List[InputTextContent]


# --- Tool Models ---


class FileSearchTool(BaseModel):
    """
    Definition of the File Search tool.
    Matches the flat structure expected by the application tests.
    """

    type: Literal["file_search"] = "file_search"
    vector_store_ids: List[str] = Field(default_factory=list)


class WebSearchTool(BaseModel):
    """
    Definition of the Web Search tool (Preview).
    """

    type: Literal["web_search_preview"] = "web_search_preview"
    search_context_size: Optional[Literal["low", "medium", "high"]] = "medium"


# --- Configuration Models ---


class ReasoningOptions(BaseModel):
    """
    Configuration for the model's reasoning effort.
    """

    # Updated to match 'ReasoningEffort' in openapi.documented.yml
    effort: Literal["none", "minimal", "low", "medium", "high", "xhigh"] = "medium"


# --- Request Payload ---


class ResponseRequestPayload(BaseModel):
    """
    The main payload for `client.responses.create`.
    Strictly follows the InputParam schema.
    """

    model: str
    input: List[InputMessage]
    instructions: Optional[str] = None
    reasoning: Optional[ReasoningOptions] = None
    tools: Optional[List[Union[FileSearchTool, WebSearchTool]]] = None
    previous_response_id: Optional[str] = None
    stream: bool = True

    @field_validator("input", mode="before")
    @classmethod
    def normalize_input(cls, v: Any) -> List[Any]:
        """
        Normalizes the input field.
        If a simple string is provided (from GUI), converts it to the
        required List[InputMessage] structure with 'user' role.
        """
        if isinstance(v, str):
            return [
                {
                    "type": "message",  # Explicitly set type
                    "role": "user",
                    "content": [{"type": "input_text", "text": v}],
                }
            ]
        return v


# --- Stream Response Event Models ---


class StreamTextDelta(BaseModel):
    """Represents a text chunk from the stream (response.output_text.delta)."""

    delta: str


class StreamResponseCreated(BaseModel):
    """Represents the creation of a response (response.created)."""

    response_id: str


class StreamUsage(BaseModel):
    """Represents token usage statistics (response.completed)."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0


class StreamError(BaseModel):
    """Represents an error occurring during the stream."""

    message: str


# Union type for all possible stream results yielded by LLMService
StreamResult = Union[StreamTextDelta, StreamResponseCreated, StreamUsage, StreamError]