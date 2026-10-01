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
    FileSearchTool,
    InputMessage,
    ResponseRequestPayload,
    StreamTextDelta,
    UserConfig,
)


def test_user_config_defaults() -> None:
    """UserConfig の初期化時デフォルト値が仕様通りであることを検証します。"""
    config = UserConfig()
    assert config.model == "gpt-6.1-sol"
    assert config.reasoning_effort == "high"
    assert config.use_file_search is False
    assert config.api_key is None


def test_response_request_payload_normalization() -> None:
    """文字列入力が自動的に InputMessage 構造へ正規化されることを検証します。"""
    # String input should be normalized to InputMessage
    payload = ResponseRequestPayload(
        model="gpt-6.1-sol",
        input="Hello World",
    )
    assert isinstance(payload.input, list)
    assert len(payload.input) == 1
    msg = payload.input[0]
    assert isinstance(msg, InputMessage)
    assert msg.role == "user"
    assert msg.content[0].type == "input_text"
    assert msg.content[0].text == "Hello World"


def test_reasoning_effort_luna_none_allowed() -> None:
    """gpt-6-luna では推論強度 none が許可されることを検証します。"""
    from src.models import ReasoningOptions

    payload = ResponseRequestPayload(
        model="gpt-6-luna",
        input="Test Luna",
        reasoning=ReasoningOptions(effort="none"),
    )
    assert payload.reasoning is not None
    assert payload.reasoning.effort == "none"


@pytest.mark.parametrize("disallowed_model", ["gpt-6-astra", "gpt-6.1-sol"])
def test_reasoning_effort_none_disallowed_for_astra_and_sol(disallowed_model: str) -> None:
    """gpt-6-astra および gpt-6.1-sol では推論強度 none が禁止されることを検証します。"""
    from src.models import ReasoningOptions

    with pytest.raises(ValidationError, match="gpt-6-luna のみ対応しています"):
        ResponseRequestPayload(
            model=disallowed_model,
            input="Test Disallowed",
            reasoning=ReasoningOptions(effort="none"),
        )


@pytest.mark.parametrize("effort", ["max", "xhigh", "high", "medium", "low"])
def test_reasoning_effort_standard_levels_allowed(effort: str) -> None:
    """max, xhigh, high, medium, low は全モデルで許可されることを検証します。"""
    from src.models import ReasoningOptions

    for model in ["gpt-6-astra", "gpt-6.1-sol", "gpt-6-luna"]:
        payload = ResponseRequestPayload(
            model=model,
            input="Test Standard",
            reasoning=ReasoningOptions(effort=effort),  # type: ignore[arg-type]
        )
        assert payload.reasoning is not None
        assert payload.reasoning.effort == effort


def test_forbid_extra_fields() -> None:
    """ResponseRequestPayload に未定義フィールドを渡した際にバリデーションエラーとなることを検証します。"""
    # extra fields should be forbidden in request payload
    with pytest.raises(ValidationError):
        ResponseRequestPayload(
            model="gpt-5.4",
            input="Test",
            invalid_field="should fail",  # type: ignore[call-arg]
        )


def test_stream_text_delta_forbid_extra() -> None:
    """StreamTextDelta に余分なフィールドが指定された場合にバリデーションエラーとなることを検証します。"""
    with pytest.raises(ValidationError):
        StreamTextDelta(delta="test", extra_field="fail")  # type: ignore[call-arg]


def test_tools_serialization() -> None:
    """FileSearchTool を含むリクエストペイロードが正しくシリアライズされることを検証します。"""
    tool = FileSearchTool(vector_store_ids=["vs_123"])
    payload = ResponseRequestPayload(
        model="gpt-4o",
        input="Query",
        tools=[tool],
    )
    dumped = payload.model_dump(exclude_none=True)
    assert "tools" in dumped
    assert dumped["tools"][0]["type"] == "file_search"
    assert dumped["tools"][0]["vector_store_ids"] == ["vs_123"]
