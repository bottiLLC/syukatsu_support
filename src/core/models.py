"""
OpenAI Responses API 用のデータモデル。

このモジュールは `/v1/responses` エンドポイントの `openapi.documented.yml` 仕様に
厳密に従うPydanticモデルを定義します。リクエストペイロードやレスポンスのストリームイベントの
バリデーション、シリアライズ、正規化を処理します。
"""

from typing import List, Literal, Optional, Union, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict

# --- Input Message Models (Strict Schema) ---


class InputTextContent(BaseModel):
    """
    入力メッセージのテキストコンテンツを表します。
    Schema: {"type": "input_text", "text": "..."}
    """
    model_config = ConfigDict(extra='forbid')

    type: Literal["input_text"] = "input_text"
    text: str


class InputMessage(BaseModel):
    """
    会話履歴内のメッセージを表します。
    Schema: {"role": "user" | "assistant", "content": [...]}
    """
    model_config = ConfigDict(extra='forbid')

    role: Literal["user", "assistant"]
    content: List[InputTextContent]


# --- Tool Models ---


class FileSearchTool(BaseModel):
    """
    File Search ツールの定義。
    アプリのテストで想定されるフラットな構造に一致させます。
    """
    model_config = ConfigDict(extra='forbid')

    type: Literal["file_search"] = "file_search"
    vector_store_ids: List[str] = Field(default_factory=list)


class WebSearchTool(BaseModel):
    """
    Web Search ツールの定義 (プレビュー)。
    """
    model_config = ConfigDict(extra='forbid')

    type: Literal["web_search_preview"] = "web_search_preview"
    search_context_size: Optional[Literal["low", "medium", "high"]] = "medium"


# --- Configuration Models ---


class ReasoningOptions(BaseModel):
    """
    モデルの推論強度 (reasoning effort) の設定。
    """
    model_config = ConfigDict(extra='forbid')

    # Updated to match 'ReasoningEffort' in openapi.documented.yml
    effort: Literal["none", "minimal", "low", "medium", "high", "xhigh"] = "medium"


# --- Request Payload ---


class ResponseRequestPayload(BaseModel):
    """
    `client.responses.create` 用のメインペイロード。
    InputParam スキーマに厳密に従います。
    """
    model_config = ConfigDict(extra='forbid')

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
        入力フィールドを正規化します。
        単純な文字列が提供された場合（GUIから）、'user' ロールを持つ
        必要な List[InputMessage] 構造へと変換します。
        """
        if isinstance(v, str):
            return [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": v}],
                }
            ]
        return v


# --- Stream Response Event Models ---


class StreamTextDelta(BaseModel):
    """ストリームからのテキストチャンク (response.output_text.delta) を表します。"""
    model_config = ConfigDict(extra='forbid')
    delta: str


class StreamResponseCreated(BaseModel):
    """レスポンスの生成 (response.created) を表します。"""
    model_config = ConfigDict(extra='forbid')
    response_id: str


class StreamUsage(BaseModel):
    """トークン使用量の統計情報 (response.completed) を表します。"""
    model_config = ConfigDict(extra='forbid')

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0


class StreamError(BaseModel):
    """ストリーム中に発生したエラーを表します。"""
    model_config = ConfigDict(extra='forbid')
    message: str


# LLMService が生成する可能性があるすべてのストリーム結果の Union 型
StreamResult = Union[StreamTextDelta, StreamResponseCreated, StreamUsage, StreamError]