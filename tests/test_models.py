import pytest
from pydantic import ValidationError
from src.models import (
    UserConfig,
    ResponseRequestPayload,
    FileSearchTool,
    InputMessage,
    ReasoningOptions,
    StreamTextDelta,
)

def test_user_config_defaults():
    config = UserConfig()
    assert config.model == "gpt-5.2"
    assert config.reasoning_effort == "high"
    assert config.use_file_search is False
    assert config.api_key is None

def test_response_request_payload_normalization():
    # String input should be normalized to InputMessage
    payload = ResponseRequestPayload(
        model="gpt-5.2",
        input="Hello World" # type: ignore
    )
    assert len(payload.input) == 1
    assert payload.input[0].role == "user"
    assert payload.input[0].content[0].type == "input_text"
    assert payload.input[0].content[0].text == "Hello World"

def test_forbid_extra_fields():
    # extra fields should be forbidden in request payload
    with pytest.raises(ValidationError):
        ResponseRequestPayload(
            model="gpt-5.2",
            input="Test", # type: ignore
            invalid_field="should fail" # type: ignore
        )

def test_stream_text_delta_forbid_extra():
    with pytest.raises(ValidationError):
        StreamTextDelta(delta="test", extra_field="fail") # type: ignore

def test_tools_serialization():
    tool = FileSearchTool(vector_store_ids=["vs_123"])
    payload = ResponseRequestPayload(
        model="gpt-4o",
        input="Query", # type: ignore
        tools=[tool]
    )
    dumped = payload.model_dump(exclude_none=True)
    assert "tools" in dumped
    assert dumped["tools"][0]["type"] == "file_search"
    assert dumped["tools"][0]["vector_store_ids"] == ["vs_123"]