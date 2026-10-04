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

"""データモデルおよびPydanticスキーマ定義モジュール。

アプリケーション全体で使用される設定 (UserConfig)、OpenAI Responses API リクエストモデル、
およびストリーミングイベントの型定義を集約します。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh", "max"]
AvailableModel = Literal["gpt-6-astra", "gpt-6.1-sol", "gpt-6-luna"]


class ViewMode(StrEnum):
    """UI表示モード定義。"""

    SIMPLE = "simple"
    ADVANCED = "advanced"


class AnalysisMethod(StrEnum):
    """分析実行方式の定義。"""

    DIRECT = "direct"  # 単一有報PDFの直接全文分析（No-RAG）
    RAG = "rag"  # Vector Storeを用いた横断検索分析


# --- Constants / App Config Defaults ---


class AppConfigDefaults:
    """アプリケーション設定のデフォルト値を定義する定数クラス。"""

    DEFAULT_MODEL: str = "gpt-6.1-sol"
    DEFAULT_REASONING: ReasoningEffort = "high"
    DEFAULT_VIEW_MODE: ViewMode = ViewMode.SIMPLE
    DEFAULT_MAX_OUTPUT_TOKENS: int = 200_000


# --- Application Configuration Models ---


class UserConfig(BaseModel):
    """実行時のユーザー設定を表すPydanticモデル。"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    api_key: str | None = Field(default=None, description="復号化されたOpenAI APIキー。")
    view_mode: ViewMode = Field(
        default=AppConfigDefaults.DEFAULT_VIEW_MODE,
        description="UI表示モード（シンプル/詳細）。",
    )
    model: str = Field(default=AppConfigDefaults.DEFAULT_MODEL, description="選択されたOpenAIモデルのID。")
    reasoning_effort: ReasoningEffort = Field(
        default=AppConfigDefaults.DEFAULT_REASONING,
        description="モデルの推論強度（reasoning effort）。",
    )
    system_prompt_mode: str = Field(
        default="財務分析",
        description="現在選択されている分析戦略モード。",
    )
    last_response_id: str | None = Field(
        default=None,
        description="コンテキストの継続性を保つための最後のレスポンスID。",
    )

    # Input File & Analysis Method Configuration
    active_pdf_path: str | None = Field(
        default=None,
        description="選択中の有価証券報告書 (PDF) のローカル絶対パス。",
    )
    analysis_method: AnalysisMethod = Field(
        default=AnalysisMethod.DIRECT,
        description="分析実行方式（直接分析またはRAG）。",
    )

    # RAG Configuration
    current_vector_store_id: str | None = Field(default=None, description="現在選択されているVector StoreのID。")
    use_file_search: bool = Field(default=False, description="File Search (RAG) ツールを有効にするかどうか。")


# --- OpenAI API Request Models (Responses API) ---


class InputTextContent(BaseModel):
    """テキスト入力コンテンツを表すスキーマ。"""

    model_config = ConfigDict(extra="forbid")
    type: Literal["input_text"] = "input_text"
    text: str


class InputFileContent(BaseModel):
    """ファイル入力コンテンツを表すスキーマ（Responses API）。"""

    model_config = ConfigDict(extra="forbid")
    type: Literal["input_file"] = "input_file"
    file_id: str


class InputMessage(BaseModel):
    """会話メッセージ入力（ロールとコンテンツ）を表すスキーマ。"""

    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: list[InputTextContent | InputFileContent]


class FileSearchTool(BaseModel):
    """OpenAI File Search ツール設定スキーマ。"""

    model_config = ConfigDict(extra="forbid")
    type: Literal["file_search"] = "file_search"
    vector_store_ids: list[str] = Field(default_factory=list)


class WebSearchTool(BaseModel):
    """Web Search プレビューツール設定スキーマ。"""

    model_config = ConfigDict(extra="forbid")
    type: Literal["web_search_preview"] = "web_search_preview"
    search_context_size: Literal["low", "medium", "high"] | None = "medium"


class ReasoningOptions(BaseModel):
    """推論強度オプションスキーマ。"""

    model_config = ConfigDict(extra="forbid")
    effort: ReasoningEffort = "medium"


# --- Structured Outputs Schema ---

MARKDOWN_OUTPUT_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "markdown_content": {
            "type": "string",
            "description": "マークダウン形式で記述された本文",
        }
    },
    "required": ["markdown_content"],
    "additionalProperties": False,
}


class ResponseFormatJsonSchema(BaseModel):
    """Responses API の JSON Schema 設定。"""

    model_config = ConfigDict(extra="forbid")
    type: Literal["json_schema"] = "json_schema"
    name: str = "markdown_response"
    strict: bool = True
    schema_: dict[str, Any] = Field(default_factory=lambda: dict(MARKDOWN_OUTPUT_SCHEMA), alias="schema")


class ResponseTextConfig(BaseModel):
    """Responses API の text 設定。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    format: ResponseFormatJsonSchema = Field(default_factory=ResponseFormatJsonSchema)


class ResponseRequestPayload(BaseModel):
    """client.responses.create 用メインリクエストペイロード。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    model: str
    input: list[InputMessage] | str
    instructions: str | None = None
    reasoning: ReasoningOptions | None = None
    tools: list[FileSearchTool | WebSearchTool] | None = None
    previous_response_id: str | None = None
    stream: bool = True
    text: ResponseTextConfig | None = Field(default_factory=ResponseTextConfig)
    max_output_tokens: int | None = Field(
        default=AppConfigDefaults.DEFAULT_MAX_OUTPUT_TOKENS,
        description="最大出力トークン数（1回あたり約300円＝$2.00換算: 200,000トークン上限）。",
    )

    @field_validator("input", mode="before")
    @classmethod
    def normalize_input(cls, v: Any) -> list[dict[str, Any]] | Any:
        """文字列入力を正規化されたメッセージ構造に変換します。"""
        if isinstance(v, str):
            return [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": v}],
                }
            ]
        return v

    @model_validator(mode="after")
    def validate_model_and_reasoning(self) -> Self:
        """モデルと推論強度の整合性を検証します。'none' は gpt-6-luna のみ利用可能です。"""
        if self.reasoning and self.reasoning.effort == "none" and self.model != "gpt-6-luna":
            raise ValueError(
                f"モデル '{self.model}' では推論強度 'none' は利用できません。'none' は gpt-6-luna のみ対応しています。"
            )
        return self


# --- Stream Response Event Models ---


class StreamTextDelta(BaseModel):
    """テキスト差分ストリーミングイベントスキーマ。"""

    model_config = ConfigDict(extra="forbid")
    delta: str


class StreamResponseCreated(BaseModel):
    """レスポンス生成開始イベントスキーマ。"""

    model_config = ConfigDict(extra="forbid")
    response_id: str


class StreamUsage(BaseModel):
    """トークン使用量イベントスキーマ。"""

    model_config = ConfigDict(extra="forbid")
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0


class StreamError(BaseModel):
    """エラーイベントスキーマ。"""

    model_config = ConfigDict(extra="forbid")
    message: str


StreamResult = StreamTextDelta | StreamResponseCreated | StreamUsage | StreamError
