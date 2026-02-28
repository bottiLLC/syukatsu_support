"""
データモデルとスキーマの定義。

このモジュールはアプリケーション全体で使用されるPydantic V2モデルを集約します。
設定（UserConfig）、OpenAI APIリクエスト（ResponseRequestPayload）、
およびストリームイベント（StreamResult等）を含みます。
"""

from typing import List, Literal, Optional, Union, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


# --- Constants / App Config Defaults ---
class AppConfigDefaults:
    APP_VERSION: str = "v1.0.0"
    DEFAULT_MODEL: str = "gpt-5.2"
    DEFAULT_REASONING: Literal["none", "minimal", "low", "medium", "high", "xhigh"] = "high"


# --- Application Configuration Models ---

class UserConfig(BaseModel):
    """
    実行時のユーザー設定を表すPydanticモデル。
    """
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    api_key: Optional[str] = Field(
        default=None, description="復号化されたOpenAI APIキー。"
    )
    model: str = Field(
        default=AppConfigDefaults.DEFAULT_MODEL, description="選択されたOpenAIモデルのID。"
    )
    reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh"] = Field(
        default=AppConfigDefaults.DEFAULT_REASONING,
        description="モデルの推論強度（reasoning effort）。",
    )
    system_prompt_mode: str = Field(
        default="有価証券報告書 -財務分析-",
        description="現在選択されている分析戦略モード。",
    )
    last_response_id: Optional[str] = Field(
        default=None,
        description="コンテキストの継続性を保つための最後のレスポンスID。",
    )

    # RAG Configuration
    current_vector_store_id: Optional[str] = Field(
        default=None, description="現在選択されているVector StoreのID。"
    )
    use_file_search: bool = Field(
        default=False, description="File Search (RAG) ツールを有効にするかどうか。"
    )


# --- OpenAI API Request Models (Responses API) ---

class InputTextContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal["input_text"] = "input_text"
    text: str


class InputMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal["user", "assistant"]
    content: List[InputTextContent]


class FileSearchTool(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal["file_search"] = "file_search"
    vector_store_ids: List[str] = Field(default_factory=list)


class WebSearchTool(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal["web_search_preview"] = "web_search_preview"
    search_context_size: Optional[Literal["low", "medium", "high"]] = "medium"


class ReasoningOptions(BaseModel):
    model_config = ConfigDict(extra='forbid')
    effort: Literal["none", "minimal", "low", "medium", "high", "xhigh"] = "medium"


class ResponseRequestPayload(BaseModel):
    """
    client.responses.create 用メインリクエストペイロード。
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
    model_config = ConfigDict(extra='forbid')
    delta: str


class StreamResponseCreated(BaseModel):
    model_config = ConfigDict(extra='forbid')
    response_id: str


class StreamUsage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0


class StreamError(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message: str


StreamResult = Union[StreamTextDelta, StreamResponseCreated, StreamUsage, StreamError]

