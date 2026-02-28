"""
src/core/models.py で定義されたデータモデルのユニットテスト。
Pydanticモデルが OpenAI Responses API スキーマに従ってデータを正しく検証およびシリアライズすることを保証します。
"""

import pytest
from pydantic import ValidationError

from src.core.models import (
    ResponseRequestPayload,
    InputMessage,
    InputTextContent,
    FileSearchTool,
    StreamTextDelta,
    StreamUsage,
    StreamError,
)

class TestResponseRequestPayload:
    """メインAPIリクエストペイロードモデルのテスト。"""

    def test_payload_normalization_string_input(self):
        """
        単純な文字列入力が、APIで必要とされる複雑な List[InputMessage] 構造へと
        正しく正規化されることを検証します。
        """
        payload = ResponseRequestPayload(
            model="gpt-5.2",
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
        構築済みの InputMessage オブジェクトのリストを渡した場合、そのまま機能することを検証します。
        """
        raw_input = [
            InputMessage(
                role="user", 
                content=[InputTextContent(text="Explicit input")]
            )
        ]
        payload = ResponseRequestPayload(
            model="gpt-5.2",
            input=raw_input
        )
        
        assert payload.input == raw_input
        assert payload.input[0].content[0].text == "Explicit input"

    def test_payload_with_tools(self):
        """ツール群（RAG/File Search等）の正しいシリアライズを検証します。"""
        tools = [
            FileSearchTool(vector_store_ids=["vs_123"])
        ]
        payload = ResponseRequestPayload(
            model="gpt-5.2",
            input="Check this file",
            tools=tools
        )
        
        dump = payload.model_dump(exclude_none=True)
        assert "tools" in dump
        assert dump["tools"][0]["type"] == "file_search"
        assert dump["tools"][0]["vector_store_ids"] == ["vs_123"]

    def test_payload_validation_failure(self):
        """必須フィールドが欠如している場合に ValidationError が発生することを検証します。"""
        with pytest.raises(ValidationError):
            ResponseRequestPayload(
                # Missing 'model' and 'input'
                instructions="System prompt only" 
            )

class TestStreamEvents:
    """ストリームレスポンスイベントモデルのテスト。"""

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