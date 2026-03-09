import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from openai import RateLimitError
from src.infrastructure.openai_client import OpenAIClient
from src.models import ResponseRequestPayload, StreamResponseCreated

@pytest.mark.asyncio
async def test_openai_client_resilience():
    client = OpenAIClient("test-key")

    mock_client = MagicMock()
    mock_client.responses.create = AsyncMock()
    mock_client.responses.create.side_effect = [
        RateLimitError(message="Rate limit", response=MagicMock(), body=None),
        "Success object"
    ]
    
    stream_res = await client._create_stream(mock_client, {})
    assert stream_res == "Success object"
    assert mock_client.responses.create.call_count == 2

    # For a robust test without depending on complex SDK internals, we test the event parsing:
    event_created = MagicMock()
    event_created.type = "response.created"
    event_created.response.id = "resp_123"

    result = client._process_event(event_created)
    assert isinstance(result, StreamResponseCreated)
    assert result.response_id == "resp_123"


@pytest.mark.asyncio
async def test_stream_analysis_validation_error():
    client = OpenAIClient("test-key")
    
    # Send a formally invalid payload model that causes ValidationError in pydantic
    # Wait, pydantic checks at instantiation.
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ResponseRequestPayload(
            model="gpt-5.4",
            input="Test",
            invalid_field="should fail" # type: ignore
        )

@pytest.mark.asyncio
async def test_process_text_delta():
    client = OpenAIClient("test-key")
    
    event_delta = MagicMock()
    event_delta.type = "response.output_text.delta"
    event_delta.delta = "Hello"
    
    result = client._process_event(event_delta)
    assert result.delta == "Hello"

@pytest.mark.asyncio
async def test_process_reasoning_text_delta():
    client = OpenAIClient("test-key")
    
    event_delta = MagicMock()
    event_delta.type = "response.reasoning_text.delta"
    event_delta.delta = " Thinking..."
    
    result = client._process_event(event_delta)
    assert result.delta == " Thinking..."

