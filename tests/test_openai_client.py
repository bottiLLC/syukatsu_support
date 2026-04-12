# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import pytest
from unittest.mock import AsyncMock, MagicMock
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

