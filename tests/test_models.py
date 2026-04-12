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
from pydantic import ValidationError
from src.models import (
    UserConfig,
    ResponseRequestPayload,
    FileSearchTool,
    StreamTextDelta,
)

def test_user_config_defaults():
    config = UserConfig()
    assert config.model == "gpt-5.4"
    assert config.reasoning_effort == "high"
    assert config.use_file_search is False
    assert config.api_key is None

def test_response_request_payload_normalization():
    # String input should be normalized to InputMessage
    payload = ResponseRequestPayload(
        model="gpt-5.4",
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
            model="gpt-5.4",
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