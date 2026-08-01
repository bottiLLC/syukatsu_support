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

"""
就職活動サポートアプリ (SYUKATSU Support) - オールインワン単一ファイル版

本スクリプトは、データモデル、セキュリティ暗号化、料金計算、OpenAI API非同期通信、
RAG(Vector Store)管理、プロンプト定義、GUI画面をすべて単一ファイルに集約した完全自己完結型アプリケーションです。
"""

import sys
import os
import json
import asyncio
import datetime
import traceback
import structlog
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Literal, Union, AsyncGenerator, Callable, Awaitable

import flet as ft
try:
    import flet_desktop
except ImportError:
    pass
from pydantic import BaseModel, ConfigDict, Field, field_validator, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from tenacity import retry, wait_exponential, stop_after_attempt
from cryptography.fernet import Fernet, InvalidToken
import openai
from openai import AsyncOpenAI, OpenAIError, NotFoundError, APIError

# --- PyInstaller Resource Path Resolver ---
def get_resource_path(relative_path: str) -> Path:
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).resolve().parent / relative_path

# --- Crash & Error Logger ---
_app_data_dir = os.path.expandvars(r'%LOCALAPPDATA%\SYUKATSU_Support')
os.makedirs(_app_data_dir, exist_ok=True)
CRASH_LOG_FILE = Path(_app_data_dir) / "crash_log.txt"

def log_crash_and_exit(e: Exception):
    error_msg = f"[{datetime.datetime.now()}]\n" + "".join(traceback.format_exception(type(e), e, e.__traceback__))
    try:
        CRASH_LOG_FILE.write_text(error_msg, encoding="utf-8")
    except Exception:
        pass

    # Windows MessageBox Alert for easy debugging
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                f"アプリケーションの起動中にエラーが発生しました。\n\nログ保存先: {CRASH_LOG_FILE}\n\nエラー概要:\n{str(e)[:300]}",
                "SYUKATSU Support エラー",
                0x10 | 0x0
            )
        except Exception:
            pass

# --- Event Loop & Logger Setup ---
log = structlog.get_logger()

# --- App System Data & Internal Prompts ---
EMBEDDED_SYSTEM_PROMPTS: Dict[str, str] = {
    "有価証券報告書 -財務分析-": """### ROLE
You are a "Critical Financial Analyst" and "Strategic Business Mentor" for university students.
Your mission is to deeply analyze the "Annual Securities Report" (有価証券報告書) to expose the reality behind the business models, financial numbers, and corporate strategies with evidence and clarity.

### OBJECTIVE
Deeply analyze the report focusing strictly on Business Segments, Financial Condition (PL/BS/CF), Future Strategies, and Business Risks.

### OUTPUT CONSTRAINTS
1. Language: Japanese (Professional yet accessible, sharp, highly analytical).
2. Format: Use Markdown. Use "💡 表の顔 (The Good)" and "⚠️ 裏の顔 (The Risk/Reality)" to contrast views.
""",
    "有価証券報告書 -人的資本分析-": """### ROLE
You are an expert "Critical HR Consultant" and "Corporate Culture Detective" for university students.
Your mission is to analyze the "Annual Securities Report" (有価証券報告書) — specifically focusing on Human Capital and Sustainability data — to expose the true working conditions and corporate culture.

### OUTPUT CONSTRAINTS
1. Language: Japanese.
2. Format: Use Markdown with "💡 表の顔" and "⚠️ 裏の顔".
""",
    "ガクチカ添削": """# 命令
あなたは数万人の学生の就職活動を支援してきた親身で優秀なキャリアアドバイザー（ES添削メンター）です。
学生時代に力を入れたこと（ガクチカ）を読み、論理の飛躍や誇張を優しく指摘し、等身大の魅力を引き出す深掘り質問を作成してください。

# 出力形式
1. 面接官から見て「少し無理がある」と感じられる部分とその理由
2. 隠れている「等身大の魅力」の推測
3. 経験の解像度を上げる深掘り質問（3問）
""",
    "志望動機検討": """### ROLE
You are an elite "Strategic Career Coach" and "ES Architect" for university students.
Transform the student's motive into an "Indispensable Problem Solver" perspective using the Annual Securities Report.

### OUTPUT CONSTRAINTS
1. Language: Japanese (Persuasive, actionable).
2. Format: Markdown.
""",
    "システムプロンプトなし": ""
}


class PromptManager:
    """プロンプト管理（外部JSONがあれば読み込み、無ければ埋め込みプロンプトを利用）"""
    def __init__(self):
        self.prompts: Dict[str, str] = EMBEDDED_SYSTEM_PROMPTS.copy()
        json_path = get_resource_path("system_prompts.json")
        if json_path.exists():
            try:
                with json_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.prompts.update(data)
            except Exception as e:
                log.warning("system_prompts.jsonの読み込みに失敗しました。内蔵プロンプトを使用します。", error=str(e))

    def get_all_modes(self) -> List[str]:
        return list(self.prompts.keys())

    def get_prompt(self, mode_name: str) -> str:
        return self.prompts.get(mode_name, "")


# --- Data Models (Pydantic V2) ---
class AppConfigDefaults:
    DEFAULT_MODEL: str = "gpt-5.6-terra"
    DEFAULT_REASONING: Literal["none", "minimal", "low", "medium", "high", "xhigh"] = "high"


class UserConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    api_key: Optional[str] = Field(default=None, description="復号化されたOpenAI APIキー。")
    model: str = Field(default=AppConfigDefaults.DEFAULT_MODEL, description="選択されたOpenAIモデルのID。")
    reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh"] = Field(
        default=AppConfigDefaults.DEFAULT_REASONING, description="モデルの推論強度。"
    )
    system_prompt_mode: str = Field(default="有価証券報告書 -財務分析-", description="現在選択されている分析戦略モード。")
    last_response_id: Optional[str] = Field(default=None, description="前回のレスポンスID。")
    current_vector_store_id: Optional[str] = Field(default=None, description="選択中のVector Store ID。")
    use_file_search: bool = Field(default=False, description="File Search (RAG) ツール有効フラグ。")


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
    effort: Literal["none", "minimal", "low", "medium", "high", "xhigh"] = "high"


class ResponseRequestPayload(BaseModel):
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
            return [{"role": "user", "content": [{"type": "input_text", "text": v}]}]
        return v


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


# --- Security & Config Storage ---
CONFIG_FILE = Path(_app_data_dir) / "config.json"
KEY_FILE = Path(_app_data_dir) / ".secret.key"


class SecurityManager:
    @staticmethod
    def _get_or_create_key() -> bytes:
        if KEY_FILE.exists():
            try:
                return KEY_FILE.read_bytes()
            except IOError as e:
                log.error("キーファイルの読み込み失敗", error=str(e))
                raise

        key = Fernet.generate_key()
        try:
            KEY_FILE.write_bytes(key)
            if os.name == "posix":
                KEY_FILE.chmod(0o600)
        except IOError as e:
            log.critical("キー保存失敗", error=str(e))
            raise
        return key

    @classmethod
    def encrypt(cls, plain_text: str) -> str:
        if not plain_text:
            return ""
        try:
            fernet = Fernet(cls._get_or_create_key())
            return fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")
        except Exception as e:
            log.error("暗号化失敗", error=str(e))
            return ""

    @classmethod
    def decrypt(cls, cipher_text: str) -> Optional[str]:
        if not cipher_text:
            return None
        try:
            fernet = Fernet(cls._get_or_create_key())
            return fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
        except (InvalidToken, Exception) as e:
            log.warning("復号化失敗", error=str(e))
            return None


class ConfigManager:
    @staticmethod
    def load() -> UserConfig:
        config_data: Dict[str, Any] = {}

        if CONFIG_FILE.exists():
            try:
                with CONFIG_FILE.open("r", encoding="utf-8") as f:
                    file_data = json.load(f)

                encrypted_key = file_data.get("encrypted_api_key")
                if encrypted_key:
                    decrypted_key = SecurityManager.decrypt(encrypted_key)
                    file_data["api_key"] = decrypted_key

                file_data.pop("encrypted_api_key", None)
                config_data = file_data
            except Exception as e:
                log.error("設定ファイルの読み込み失敗", error=str(e))

        env_key = os.getenv("OPENAI_API_KEY")
        if env_key:
            config_data["api_key"] = env_key

        config_data["model"] = AppConfigDefaults.DEFAULT_MODEL
        config_data["reasoning_effort"] = AppConfigDefaults.DEFAULT_REASONING

        try:
            return UserConfig(**config_data)
        except ValidationError:
            return UserConfig()

    @staticmethod
    def save(config: UserConfig) -> None:
        try:
            data = config.model_dump(exclude={"api_key"})
            if config.api_key:
                encrypted = SecurityManager.encrypt(config.api_key)
                if encrypted:
                    data["encrypted_api_key"] = encrypted

            with CONFIG_FILE.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except IOError as e:
            log.error("設定の保存失敗", error=str(e))


# --- Pricing & Cost Calculation ---
@dataclass(frozen=True)
class ModelPricing:
    input_price: float
    output_price: float
    cached_input_price: float = 0.0


PRICING_TABLE: Dict[str, ModelPricing] = {
    "gpt-5.6-sol": ModelPricing(input_price=5.00, output_price=30.00, cached_input_price=0.50),
    "gpt-5.6-terra": ModelPricing(input_price=2.00, output_price=12.00, cached_input_price=0.20),
    "gpt-5.6-luna": ModelPricing(input_price=0.20, output_price=1.20, cached_input_price=0.02),
    "gpt-5.4-pro": ModelPricing(input_price=30.00, output_price=180.00, cached_input_price=0.0),
    "gpt-5.4": ModelPricing(input_price=2.50, output_price=15.00, cached_input_price=0.25),
    "gpt-4o": ModelPricing(input_price=2.50, output_price=10.00, cached_input_price=1.25),
    "gpt-4o-mini": ModelPricing(input_price=0.150, output_price=0.600, cached_input_price=0.075),
}


class CostCalculator:
    @staticmethod
    def calculate(model_name: str, usage_event: Any) -> str:
        if isinstance(usage_event, str):
            return f"Cost: $0.00000 | {usage_event}"

        try:
            prompt_tokens = getattr(usage_event, "input_tokens", 0)
            completion_tokens = getattr(usage_event, "output_tokens", 0)
            cached_tokens = getattr(usage_event, "cached_tokens", 0)

            pricing = PRICING_TABLE.get(model_name)
            if not pricing:
                return f"Cost: Unknown Model ({model_name})"

            uncached_prompt_tokens = max(0, prompt_tokens - cached_tokens)
            cost = (
                (uncached_prompt_tokens / 1_000_000) * pricing.input_price +
                (cached_tokens / 1_000_000) * pricing.cached_input_price +
                (completion_tokens / 1_000_000) * pricing.output_price
            )
            return f"Cost: ${cost:.5f} | In: {prompt_tokens} (Cache: {cached_tokens}) | Out: {completion_tokens}"
        except Exception as e:
            return f"Cost Error: {str(e)}"


# --- Error Translation ---
def translate_api_error(e: Exception) -> str:
    """
    OpenAI APIエラーおよびシステム例外を初心者に分かりやすい丁寧な日本語メッセージに変換します。
    """
    # Tenacity の RetryError の場合は内部で発生した元の例外を取り出す
    if hasattr(e, "last_attempt") and getattr(e, "last_attempt", None):
        try:
            exc = e.last_attempt.exception()
            if exc:
                e = exc
        except Exception:
            pass

    err_str = str(e)

    # 1. アプリの多重起動によるロック / ファイル権限エラー
    if isinstance(e, PermissionError) or "WinError 32" in err_str or "Permission denied" in err_str or "locked" in err_str.lower():
        return (
            "【アプリの多重起動エラー】 (App Lock Error)\n"
            "SYUKATSU Supportがすでに別のウィンドウまたはバックグラウンドで起動しているため、設定ファイルやデータがロックされています。\n"
            "他のSYUKATSU Supportの画面を閉じてから、再度起動・操作をお試しください。"
        )

    # 2. タイムアウト
    if isinstance(e, (openai.APITimeoutError, TimeoutError)) or "APITimeoutError" in err_str or "timed out" in err_str.lower():
        return (
            "【通信タイムアウト】 (APITimeoutError)\n"
            "OpenAIサーバーからの応答が制限時間を超えました。\n"
            "サーバーが一時的に混雑している可能性があります。数十秒ほど待ってから再度お試しください。"
        )

    # 3. APIキー形式エラー (UnicodeEncodeError / 全角文字混入など)
    if isinstance(e, (UnicodeEncodeError, UnicodeError)) or "ascii" in err_str.lower() or "ordinal not in range" in err_str.lower() or "codec" in err_str.lower():
        return (
            "【APIキー文字エラー】 (Invalid Key Format)\n"
            "入力されたOpenAI APIキーに全角文字や全角スペースなど、使用できない文字が含まれています。\n"
            "APIキーはすべて半角英数字・半角記号（sk-proj-...等）である必要があります。\n"
            "入力欄に半角の正しいAPIキーを貼り付け直し、「登録」ボタンを押してください。"
        )

    # 4. APIキーが誤っている (AuthenticationError)
    if isinstance(e, openai.AuthenticationError) or "AuthenticationError" in err_str or "invalid_api_key" in err_str.lower() or "401" in err_str:
        return (
            "【APIキーエラー】 (AuthenticationError)\n"
            "入力されたOpenAI APIキーが正しくないか、無効化されています。\n"
            "正しいAPIキー（sk-proj-...など）を入力欄に貼り付け直し、「登録」ボタンを押してください。"
        )

    # 4. API利用上限 / 残高不足 (RateLimitError)
    if isinstance(e, openai.RateLimitError) or "RateLimitError" in err_str:
        # クレジットの残高が不足している場合
        if "insufficient_quota" in err_str or "quota" in err_str.lower() or "billing" in err_str.lower() or "credit" in err_str.lower():
            return (
                "【クレジット残高不足】 (Insufficient Quota)\n"
                "OpenAIアカウントの無料利用分が終了したか、チャージ残高が不足しています。\n"
                "OpenAIの管理画面（https://platform.openai.com/settings/organization/billing）でクレジット残高や支払い情報をご確認ください。"
            )
        # 短期的なAPI利用上限（レート制限）に達している場合
        return (
            "【一時的な利用制限】 (RateLimitError)\n"
            "短時間での利用回数または利用量の上限（レートリミット）に達しました。\n"
            "数十秒〜数分ほど時間を置いてから再度お試しください。"
        )
        # 短期的なAPI利用上限（レート制限）に達している場合
        return (
            "【一時的な利用制限】 (RateLimitError)\n"
            "短時間での利用回数または利用量の上限（レートリミット）に達しました。\n"
            "数十秒〜数分ほど時間を置いてから再度お試しください。"
        )

    # 5. リクエストエラー (BadRequestError) - 入力トークン上限オーバー / 推論レベルミスマッチ等
    if isinstance(e, openai.BadRequestError) or "BadRequestError" in err_str:
        # 入力トークン上限オーバー
        if any(k in err_str.lower() for k in ["context_length_exceeded", "maximum context length", "exceeds the context window", "string_above_max_length", "too long", "token limit"]):
            return (
                "【入力文字数制限オーバー】 (Context Window Exceeded)\n"
                "送信した文章または過去の会話履歴が、AIが一度に処理できる制限（トークン上限）を超えています。\n"
                "「🧹 コンテキスト消去」ボタンを押して会話履歴をリセットするか、質問文を短くして再度お試しください。"
            )
        # 推論レベルミスマッチ
        if "reasoning_effort" in err_str or "reasoning.effort" in err_str:
            return (
                "【モデル設定エラー】 (Reasoning Effort Error)\n"
                "選択した推論強度が、現在のモデルでサポートされていません。\n"
                "推論強度を変更するか、対応するモデル（gpt-5.6-terra等）を選択してください。"
            )
        return (
            f"【リクエストエラー】 (BadRequestError)\n"
            f"送信したデータ形式または設定内容に問題があります。\n"
            f"詳細: {err_str}"
        )

    # 6. その他の標準的なOpenAI例外
    if isinstance(e, openai.APIConnectionError) or "APIConnectionError" in err_str:
        return (
            "【ネットワーク接続エラー】 (APIConnectionError)\n"
            "OpenAIのサーバーに接続できませんでした。\n"
            "インターネットの接続状態を確認し、再度お試しください。"
        )

    if isinstance(e, openai.NotFoundError) or "NotFoundError" in err_str:
        return (
            "【リソースが見つかりません】 (NotFoundError)\n"
            "指定されたモデルやVector Store（ナレッジベース）が存在しないか、アクセス権がありません。\n"
            "設定画面でモデルやVector Storeが正しいか確認してください。"
        )

    if isinstance(e, openai.InternalServerError) or "InternalServerError" in err_str:
        return (
            "【OpenAIサーバーエラー】 (InternalServerError)\n"
            "OpenAIのサーバー側で一時的な障害が発生しています。\n"
            "しばらく待ってから再度お試しください。"
        )

    if isinstance(e, openai.ConflictError) or "ConflictError" in err_str:
        return (
            "【データ競合エラー】 (ConflictError)\n"
            "リソースが別の処理で更新中であるため、競合が発生しました。\n"
            "しばらく待ってから再度お試しください。"
        )

    if isinstance(e, openai.OpenAIError):
        return (
            f"【OpenAI APIエラー】 ({type(e).__name__})\n"
            f"AI通信中にエラーが発生しました。\n"
            f"詳細: {err_str}"
        )

    # 7. その他の予期せぬエラー
    return f"【システムエラー】 予期せぬエラーが発生しました:\n{err_str}"


# --- OpenAI Client Infrastructure ---
class OpenAIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def _get_client(self) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=self.api_key)

    async def stream_analysis(self, payload: ResponseRequestPayload) -> AsyncGenerator[StreamResult, None]:
        try:
            request_params = payload.model_dump(exclude_none=True)
            async for result in self._execute_stream(request_params):
                yield result
        except Exception as e:
            log.exception("stream_analysisエラー", error=str(e))
            yield StreamError(message=f"\n[Unexpected Error] {e}")

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    async def _create_stream(self, client: AsyncOpenAI, request_params: dict) -> Any:
        return await client.responses.create(**request_params)

    async def _execute_stream(self, request_params: dict) -> AsyncGenerator[StreamResult, None]:
        try:
            async with self._get_client() as client:
                stream = await self._create_stream(client, request_params)
                async for event in stream:
                    result = self._process_event(event)
                    if result:
                        yield result
        except OpenAIError as e:
            yield StreamError(message=f"\n{translate_api_error(e)}")
        except Exception as e:
            yield StreamError(message=f"\n{translate_api_error(e)}")

    def _process_event(self, event: Any) -> Optional[StreamResult]:
        event_type = getattr(event, "type", None)
        if not event_type:
            return None

        if event_type in ["response.output_text.delta", "response.reasoning_text.delta"]:
            delta_content = getattr(event, "delta", None)
            return StreamTextDelta(delta=delta_content) if delta_content else None
        elif event_type == "response.created":
            response_obj = getattr(event, "response", None)
            if response_obj and hasattr(response_obj, "id"):
                return StreamResponseCreated(response_id=response_obj.id)
        elif event_type == "response.completed":
            response_obj = getattr(event, "response", None)
            if not response_obj:
                return None
            usage_obj = getattr(response_obj, "usage", None)
            if not usage_obj:
                return None
            cached_tokens = 0
            input_details = getattr(usage_obj, "input_tokens_details", None)
            if input_details:
                cached_tokens = getattr(input_details, "cached_tokens", 0)
            return StreamUsage(
                input_tokens=getattr(usage_obj, "input_tokens", 0),
                output_tokens=getattr(usage_obj, "output_tokens", 0),
                total_tokens=getattr(usage_obj, "total_tokens", 0),
                cached_tokens=cached_tokens,
            )
        elif event_type == "error":
            error_obj = getattr(event, "error", None)
            msg = getattr(error_obj, "message", str(error_obj)) if error_obj else "Unknown error"
            translated = translate_api_error(Exception(msg))
            return StreamError(message=f"\n{translated}")

        return None

    # --- Vector Store & File Operations ---
    async def list_vector_stores(self, limit: int = 20) -> List[Any]:
        try:
            async with self._get_client() as client:
                res = await client.vector_stores.list(limit=limit)
                return list(res.data)
        except Exception as e:
            log.error("Vector Store取得失敗", error=str(e))
            return []

    async def create_vector_store(self, name: str) -> Any:
        async with self._get_client() as client:
            return await client.vector_stores.create(name=name)

    async def update_vector_store(self, vector_store_id: str, name: str) -> Any:
        async with self._get_client() as client:
            return await client.vector_stores.update(vector_store_id=vector_store_id, name=name)

    async def delete_vector_store(self, vector_store_id: str) -> bool:
        async with self._get_client() as client:
            res = await client.vector_stores.delete(vector_store_id=vector_store_id)
            return res.deleted

    async def list_files_in_store(self, vector_store_id: str) -> List[Any]:
        try:
            async with self._get_client() as client:
                res = await client.vector_stores.files.list(vector_store_id=vector_store_id)
                return list(res.data)
        except NotFoundError:
            return []

    async def delete_file_from_store(self, vector_store_id: str, file_id: str) -> bool:
        async with self._get_client() as client:
            res = await client.vector_stores.files.delete(vector_store_id=vector_store_id, file_id=file_id)
            return res.deleted

    async def upload_file(self, file_path: str, purpose: str = "assistants") -> Any:
        path_obj = Path(file_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        async with self._get_client() as client:
            with path_obj.open("rb") as f:
                return await client.files.create(file=f, purpose=purpose)

    async def delete_file(self, file_id: str) -> bool:
        async with self._get_client() as client:
            res = await client.files.delete(file_id=file_id)
            return res.deleted

    async def create_file_batch(self, vector_store_id: str, file_ids: List[str]) -> Any:
        async with self._get_client() as client:
            return await client.vector_stores.file_batches.create(vector_store_id=vector_store_id, file_ids=file_ids)

    async def poll_batch_status(self, vector_store_id: str, batch_id: str, interval: float = 2.0, max_retries: int = 60) -> str:
        for _ in range(max_retries):
            try:
                async with self._get_client() as client:
                    batch = await client.vector_stores.file_batches.retrieve(vector_store_id=vector_store_id, batch_id=batch_id)
                    if batch.status in ["completed", "failed", "cancelled"]:
                        return batch.status
                await asyncio.sleep(interval)
            except Exception:
                await asyncio.sleep(interval)
        return "timed_out"


# --- Application Use Cases ---
class LLMUseCase:
    def __init__(self, client: OpenAIClient):
        self.client = client

    async def execute_analysis_stream(self, payload: ResponseRequestPayload, cancel_event: Optional[asyncio.Event] = None) -> AsyncGenerator[StreamResult, None]:
        try:
            yield StreamTextDelta(delta=f"\n[AI ({payload.model})] 分析中...\n\n")
            stream = self.client.stream_analysis(payload)
            async for event in stream:
                if cancel_event and cancel_event.is_set():
                    break
                yield event
        except Exception as e:
            yield StreamError(message=str(e))


class RAGUseCase:
    def __init__(self, client: OpenAIClient):
        self.client = client

    async def list_vector_stores(self) -> List[Any]:
        return await self.client.list_vector_stores()

    async def create_vector_store(self, name: str) -> Any:
        return await self.client.create_vector_store(name=name)

    async def update_vector_store_name(self, store_id: str, new_name: str) -> None:
        await self.client.update_vector_store(store_id, new_name)

    async def delete_vector_store(self, store_id: str) -> bool:
        return await self.client.delete_vector_store(vector_store_id=store_id)

    async def list_files_in_store(self, store_id: str) -> List[dict]:
        vs_files = await self.client.list_files_in_store(vector_store_id=store_id)
        file_details = []
        if vs_files:
            async with self.client._get_client() as ac:
                for vf in vs_files:
                    try:
                        f = await ac.files.retrieve(vf.id)
                        file_details.append({"id": f.id, "filename": f.filename, "created_at": f.created_at})
                    except Exception:
                        continue
        return file_details

    async def upload_and_index_file(self, file_path: str, store_id: str) -> None:
        f_obj = await self.client.upload_file(file_path=file_path)
        batch = await self.client.create_file_batch(vector_store_id=store_id, file_ids=[f_obj.id])
        await self.client.poll_batch_status(vector_store_id=store_id, batch_id=batch.id)

    async def delete_file_from_store_and_storage(self, store_id: str, file_id: str) -> None:
        await self.client.delete_file_from_store(vector_store_id=store_id, file_id=file_id)
        await self.client.delete_file(file_id=file_id)


# --- Global Application State (ViewModel) ---
class AppState:
    def __init__(self):
        self.config: UserConfig = ConfigManager.load()
        self.is_processing: bool = False
        self.status_message: str = "起動中..."
        self.cost_info: str = "Cost: $0.00000"

        self.prompt_manager = PromptManager()
        self.available_prompt_modes = self.prompt_manager.get_all_modes()

        self.on_state_change: Optional[Callable[[], Union[None, Awaitable[None]]]] = None
        self.on_text_delta: Optional[Callable[[str, str], Union[None, Awaitable[None]]]] = None
        self.on_clear_text: Optional[Callable[[], Union[None, Awaitable[None]]]] = None
        self.on_error: Optional[Callable[[str, str], Union[None, Awaitable[None]]]] = None
        self.on_info: Optional[Callable[[str, str], Union[None, Awaitable[None]]]] = None
        self.on_vs_updated: Optional[Callable[[List[str]], Union[None, Awaitable[None]]]] = None

        self.client: Optional[OpenAIClient] = None
        self.llm_usecase: Optional[LLMUseCase] = None
        self.rag_usecase: Optional[RAGUseCase] = None
        self.cancel_event: asyncio.Event = asyncio.Event()

        if self.config.api_key:
            self.init_client()
        else:
            self.status_message = "待機中"

    async def _notify(self):
        if self.on_state_change:
            res = self.on_state_change()
            if asyncio.iscoroutine(res):
                await res

    async def _notify_text(self, text: str, tag: str):
        if self.on_text_delta:
            res = self.on_text_delta(text, tag)
            if asyncio.iscoroutine(res):
                await res

    async def _notify_error(self, title: str, msg: str):
        if self.on_error:
            res = self.on_error(title, msg)
            if asyncio.iscoroutine(res):
                await res

    async def _notify_info(self, title: str, msg: str):
        if self.on_info:
            res = self.on_info(title, msg)
            if asyncio.iscoroutine(res):
                await res

    def init_client(self):
        if self.config.api_key:
            self.client = OpenAIClient(self.config.api_key)
            self.llm_usecase = LLMUseCase(self.client)
            self.rag_usecase = RAGUseCase(self.client)
            asyncio.create_task(self.refresh_vector_stores())

    def save_config(self):
        ConfigManager.save(self.config)

    async def update_api_key(self, api_key: str, silent: bool = False):
        if api_key:
            cleaned_key = api_key.strip().replace("　", "")
            try:
                cleaned_key.encode("ascii")
            except UnicodeEncodeError:
                await self._notify_error(
                    "APIキー入力エラー",
                    "入力されたAPIキーに全角文字が含まれています。\nAPIキーはすべて半角英数字・記号で入力してください。"
                )
                return

            self.config.api_key = cleaned_key
            self.save_config()
            self.init_client()
            if not silent:
                await self._notify_info("設定完了", "APIキーを保存しました。")

    def get_system_prompt(self, mode_name: str) -> str:
        return self.prompt_manager.get_prompt(mode_name)

    async def refresh_vector_stores(self):
        if not self.rag_usecase:
            self.status_message = "待機中"
            await self._notify()
            return
        try:
            stores = await self.rag_usecase.list_vector_stores()
            values = [f"{s.name} ({s.id})" if getattr(s, "name", None) else getattr(s, "id", "") for s in stores]
            if self.on_vs_updated:
                res = self.on_vs_updated(values)
                if asyncio.iscoroutine(res):
                    await res
        except Exception as e:
            log.error("Vector Store一覧の取得失敗", error=str(e))
        finally:
            self.status_message = "待機中"
            await self._notify()

    async def clear_context(self):
        self.config.last_response_id = None
        self.cost_info = "Cost: $0.00000"
        self.status_message = "コンテキストを消去しました。"
        if self.on_clear_text:
            res = self.on_clear_text()
            if asyncio.iscoroutine(res):
                await res
        await self._notify()

    async def cancel_generation(self):
        if self.is_processing:
            self.cancel_event.set()
            await self._notify_text("\n[SYSTEM] 中断されました。\n", "error")

    async def handle_submit(self, user_input: str, system_prompt: str):
        if self.is_processing or not user_input.strip():
            return
        if not self.config.api_key or not self.client:
            await self._notify_error(
                "APIキーが未登録です",
                "OpenAI APIキーが設定されていません。\n画面左側の「OpenAI APIキー」入力欄にAPIキーを入力し、「登録」ボタンを押してください。"
            )
            return

        tools = None
        if self.config.use_file_search:
            vs_val = self.config.current_vector_store_id
            if not vs_val:
                await self._notify_error("RAGエラー", "Vector Storeが選択されていません。")
                return
            vs_id = vs_val.split("(")[-1].strip(")") if "(" in vs_val else vs_val
            tools = [FileSearchTool(type="file_search", vector_store_ids=[vs_id])]

        self.is_processing = True
        self.status_message = f"{self.config.model} ({self.config.reasoning_effort}) で分析中..."
        self.cancel_event.clear()
        await self._notify()

        timestamp = datetime.datetime.now().strftime("%H:%M")
        await self._notify_text(f"\n[USER] {timestamp}\n{user_input}\n", "user")

        prev_id = self.config.last_response_id if self.config.last_response_id != "None" else None

        try:
            payload = ResponseRequestPayload(
                model=self.config.model,
                input=user_input,
                instructions=system_prompt,
                reasoning=ReasoningOptions(effort=self.config.reasoning_effort),
                previous_response_id=prev_id,
                tools=tools,
                stream=True,
            )
        except Exception as e:
            await self._notify_error("設定エラー", f"不正な設定値です: {e}")
            self.is_processing = False
            await self._notify()
            return

        if self.llm_usecase:
            stream = self.llm_usecase.execute_analysis_stream(payload, self.cancel_event)
            async for event in stream:
                if isinstance(event, StreamTextDelta):
                    await self._notify_text(event.delta, "ai")
                elif isinstance(event, StreamResponseCreated):
                    self.config.last_response_id = event.response_id
                    await self._notify()
                elif isinstance(event, StreamUsage):
                    self.cost_info = CostCalculator.calculate(self.config.model, event)
                    await self._notify_text(f"\n\n[{self.cost_info}]\n", "info")
                    await self._notify()
                elif isinstance(event, StreamError):
                    await self._notify_text(event.message, "error")

            self.is_processing = False
            self.status_message = "待機中"
            await self._notify()


# --- Flet Presentation Layer (UI View) ---
class SyukatsuSupportApp:
    def __init__(self, page: ft.Page, state: AppState):
        self.page = page
        self.state = state
        self.page.title = "SYUKATSU Support - 合同会社ぼっち (v2.3.0)"
        self.page.padding = 20
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.window.width = 1350
        self.page.window.height = 980

        self.state.on_state_change = self._sync_from_state
        self.state.on_text_delta = self._append_log
        self.state.on_clear_text = self._clear_log
        self.state.on_error = self._show_error
        self.state.on_info = self._show_info
        self.state.on_vs_updated = self._update_vs_combo

        self.chat_list = ft.ListView(expand=True, spacing=10, auto_scroll=True)
        self.current_ai_message = None
        self.current_ai_text = ""

        self._build_ui()
        self.page.run_task(self._sync_from_state)

    def _build_ui(self):
        self.api_key_field = ft.TextField(
            label="OpenAI APIキー", password=True, can_reveal_password=True,
            value=self.state.config.api_key, expand=True, dense=True
        )
        self.api_key_btn = ft.ElevatedButton("登録", on_click=self._on_register_key)
        self.api_key_disclaimer = ft.Text(
            "※入力されたAPIキーは本PC内（AppData）にのみ暗号化保存され、\n 外部へ送信・保持されることはありません。",
            color=ft.Colors.RED_700, size=10.5, weight="bold", no_wrap=False
        )

        self.model_combo = ft.Dropdown(
            label="モデル", options=[
                ft.dropdown.Option("gpt-5.6-terra"),
                ft.dropdown.Option("gpt-5.6-sol"),
                ft.dropdown.Option("gpt-5.6-luna"),
            ],
            value=self.state.config.model, expand=True, dense=True, on_select=self._on_model_change
        )
        self.reasoning_combo = ft.Dropdown(
            label="推論強度", options=[ft.dropdown.Option(o) for o in ["none", "minimal", "low", "medium", "high", "xhigh"]],
            value=self.state.config.reasoning_effort, expand=True, dense=True
        )

        self.vs_combo = ft.Dropdown(
            label="Vector Store", options=[], value=self.state.config.current_vector_store_id, dense=True, width=390
        )
        self.use_file_search_cb = ft.Checkbox(label="ファイル検索(RAG)を使用", value=self.state.config.use_file_search)
        self.rag_btn = ft.ElevatedButton("🛠️ ナレッジベース管理", on_click=self._on_open_rag_manager)

        prompt_options = [ft.dropdown.Option(m) for m in self.state.available_prompt_modes]
        valid_val = self.state.config.system_prompt_mode if self.state.config.system_prompt_mode in self.state.available_prompt_modes else None

        self.mode_combo = ft.Dropdown(
            label="分析モード選択", options=prompt_options,
            value=valid_val, dense=True, on_select=self._on_prompt_mode_select, width=390
        )
        self.sys_prompt_field = ft.TextField(
            label="システムプロンプト", multiline=True, width=390, min_lines=12, max_lines=16,
            value=self.state.get_system_prompt(self.state.config.system_prompt_mode), text_size=12
        )
        self.clear_btn = ft.ElevatedButton("🧹 コンテキスト消去", on_click=self._on_clear_context)

        left_column = ft.Column([
            ft.Text("企業分析設定", size=18, weight="bold"),
            ft.Divider(),
            ft.Row([self.api_key_field, self.api_key_btn]),
            self.api_key_disclaimer,
            ft.Row([self.model_combo, self.reasoning_combo]),
            ft.Divider(),
            ft.Text("ナレッジベース (RAG)", weight="bold"),
            self.vs_combo,
            self.rag_btn,
            self.use_file_search_cb,
            ft.Divider(),
            self.mode_combo,
            self.sys_prompt_field,
            self.clear_btn
        ], width=410, spacing=6, scroll=ft.ScrollMode.ADAPTIVE)

        self.response_id_text = ft.Text(f"前回レスポンスID: {self.state.config.last_response_id or 'None'}", size=12, color=ft.Colors.GREY_600)

        log_container = ft.Container(
            content=self.chat_list, border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=5, padding=10, expand=True, bgcolor=ft.Colors.WHITE
        )

        self.input_field = ft.TextField(
            label="リクエスト入力 (Shift+Enterで改行)", multiline=True, min_lines=3, max_lines=5,
            expand=True, on_submit=self._on_submit_text, shift_enter=True
        )
        self.send_btn = ft.ElevatedButton("送信 🚀", on_click=self._on_submit_button)
        self.stop_btn = ft.ElevatedButton("停止 ⏹️", on_click=self._on_stop_generation, disabled=True)
        self.save_btn = ft.ElevatedButton("保存 💾", on_click=self._on_save_log)

        input_row = ft.Row([
            self.input_field,
            ft.Column([self.send_btn, self.stop_btn, self.save_btn], alignment=ft.MainAxisAlignment.START)
        ])

        right_column = ft.Column([
            ft.Row([ft.Text("レポート (応答履歴)", size=18, weight="bold"), self.response_id_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            log_container,
            input_row
        ], expand=True)

        main_row = ft.Row([left_column, ft.VerticalDivider(), right_column], expand=True, vertical_alignment=ft.CrossAxisAlignment.START)

        self.status_text = ft.Text(self.state.status_message, size=12)
        self.cost_text = ft.Text(self.state.cost_info, size=12)
        bottom_bar = ft.Container(
            content=ft.Row([self.status_text, self.cost_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=5, bgcolor=ft.Colors.GREY_200, border_radius=3
        )

        self.page.add(ft.Column([main_row, bottom_bar], expand=True))

    async def _sync_from_state(self):
        self.api_key_field.value = self.state.config.api_key or ""
        self.model_combo.value = self.state.config.model
        self.reasoning_combo.value = self.state.config.reasoning_effort
        self.use_file_search_cb.value = self.state.config.use_file_search
        self.response_id_text.value = f"前回レスポンスID: {self.state.config.last_response_id or 'None'}"
        self.status_text.value = self.state.status_message
        self.cost_text.value = self.state.cost_info
        self.send_btn.disabled = self.state.is_processing
        self.stop_btn.disabled = not self.state.is_processing
        self.page.update()

    async def _append_log(self, text: str, tag: str):
        if tag == "user":
            self.chat_list.controls.append(
                ft.Container(content=ft.Text(text, color=ft.Colors.BLUE_800, weight="bold"), bgcolor=ft.Colors.BLUE_50, padding=10, border_radius=5)
            )
            self.current_ai_message = None
            self.current_ai_text = ""
        elif tag == "ai":
            self.current_ai_text += text
            if not self.current_ai_message:
                txt_control = ft.Markdown(self.current_ai_text, selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_WEB)
                self.current_ai_message = ft.Container(content=txt_control, bgcolor=ft.Colors.GREY_50, padding=10, border_radius=5)
                self.chat_list.controls.append(self.current_ai_message)
            else:
                self.current_ai_message.content.value = self.current_ai_text
        elif tag == "info":
            self.chat_list.controls.append(ft.Text(text, color=ft.Colors.GREEN_700, size=12))
        elif tag == "error":
            self.chat_list.controls.append(ft.Text(text, color=ft.Colors.RED_700, size=12, weight="bold"))

        self.page.update()

    async def _clear_log(self):
        self.chat_list.controls.clear()
        self.current_ai_message = None
        self.current_ai_text = ""
        self.page.update()

    async def _show_error(self, title: str, msg: str):
        def close_dlg(_e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(title, color=ft.Colors.RED),
            content=ft.Text(msg),
            actions=[ft.TextButton("OK", on_click=close_dlg)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    async def _show_info(self, title: str, msg: str):
        def close_dlg(_e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(msg),
            actions=[ft.TextButton("OK", on_click=close_dlg)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    async def _update_vs_combo(self, values: List[str]):
        self.vs_combo.options = [ft.dropdown.Option(v) for v in values]
        current = self.state.config.current_vector_store_id
        if current and any(current in val for val in values):
            self.vs_combo.value = next(val for val in values if current in val)
        elif values:
            self.vs_combo.value = values[0]
        else:
            self.vs_combo.value = None
        self.page.update()

    async def _on_model_change(self, e):
        selected_model = self.model_combo.value
        if selected_model == "gpt-5.6-sol":
            def confirm_change(_e):
                dlg.open = False
                self.page.update()

            def cancel_change(_e):
                self.model_combo.value = "gpt-5.6-terra"
                dlg.open = False
                self.page.update()

            msg = f"{selected_model} は高度な推論を行うモデルですが、gpt-5.6-terraと比較して高額なコストが発生する可能性があります。変更しますか？"
            dlg = ft.AlertDialog(
                title=ft.Text("確認"), content=ft.Text(msg),
                actions=[ft.TextButton("はい", on_click=confirm_change), ft.TextButton("いいえ", on_click=cancel_change)],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            self.page.overlay.append(dlg)
            dlg.open = True
            self.page.update()

    async def _sync_to_state(self):
        self.state.config.model = self.model_combo.value or "gpt-5.6-terra"
        self.state.config.reasoning_effort = self.reasoning_combo.value or "high"
        self.state.config.system_prompt_mode = self.mode_combo.value or "standard"
        self.state.config.use_file_search = self.use_file_search_cb.value or False
        self.state.config.current_vector_store_id = self.vs_combo.value

    async def _on_register_key(self, e):
        await self.state.update_api_key(self.api_key_field.value.strip())

    async def _on_prompt_mode_select(self, e):
        mode = self.mode_combo.value
        self.sys_prompt_field.value = self.state.get_system_prompt(mode)
        await self._sync_to_state()
        self.page.update()

    async def _on_clear_context(self, e):
        def confirm_clear(_e):
            self.page.run_task(self.state.clear_context)
            dlg.open = False
            self.page.update()

        def cancel_clear(_e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("確認"), content=ft.Text("会話コンテキストおよび表示ログを消去しますか？"),
            actions=[ft.TextButton("はい", on_click=confirm_clear), ft.TextButton("いいえ", on_click=cancel_clear)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    async def _on_submit_text(self, e):
        await self._on_submit_button(e)

    async def _on_submit_button(self, e):
        await self._sync_to_state()
        text = self.input_field.value
        self.input_field.value = ""
        self.page.update()
        self.page.run_task(self.state.handle_submit, text, self.sys_prompt_field.value)

    async def _on_stop_generation(self, e):
        await self.state.cancel_generation()

    async def _on_save_log(self, e):
        full_text = ""
        for ctrl in self.chat_list.controls:
            if hasattr(ctrl, "content") and hasattr(ctrl.content, "value"):
                full_text += ctrl.content.value + "\n\n"
            elif hasattr(ctrl, "value"):
                full_text += ctrl.value + "\n\n"

        if not full_text.strip():
            await self._show_info("通知", "保存するレポート内容がありません。")
            return

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_picker = ft.FilePicker()
        path = await file_picker.save_file(
            dialog_title="レポートの保存先を選択",
            file_name=f"report_log_{timestamp}.txt",
            allowed_extensions=["txt"]
        )

        if path:
            try:
                Path(path).write_text(full_text.strip(), encoding="utf-8")
                await self._show_info("保存完了", f"レポートを保存しました:\n{path}")
            except Exception as ex:
                await self._show_error("保存エラー", f"ファイルの保存に失敗しました:\n{ex}")

    async def _on_open_rag_manager(self, e):
        if not self.state.rag_usecase:
            await self._show_error("エラー", "API Keyが設定されていません。")
            return

        new_store_field = ft.TextField(label="新規Vector Store名", expand=True, dense=True)
        store_list = ft.ListView(expand=True, spacing=5)
        file_list = ft.ListView(expand=True, spacing=5)
        status_txt = ft.Text("", size=12, color=ft.Colors.GREY_700)
        selected_store_id = [None]

        async def refresh_stores():
            status_txt.value = "Vector Store一覧を取得中..."
            self.page.update()
            stores = await self.state.rag_usecase.list_vector_stores()
            store_list.controls.clear()
            for s in stores:
                s_name = getattr(s, "name", "No Name")
                s_id = s.id
                store_list.controls.append(
                    ft.ListTile(
                        title=ft.Text(f"{s_name} ({s_id})"),
                        on_click=lambda _e, sid=s_id: self.page.run_task(select_store, sid)
                    )
                )
            status_txt.value = "取得完了"
            self.page.update()

        async def select_store(sid: str):
            selected_store_id[0] = sid
            status_txt.value = f"Store: {sid} のファイル一覧を取得中..."
            self.page.update()
            files = await self.state.rag_usecase.list_files_in_store(sid)
            file_list.controls.clear()
            for f in files:
                file_list.controls.append(
                    ft.ListTile(
                        title=ft.Text(f.get("filename", "Unknown")),
                        subtitle=ft.Text(f"ID: {f.get('id')}"),
                        trailing=ft.IconButton(
                            ft.Icons.DELETE,
                            on_click=lambda _e, fid=f.get("id"): self.page.run_task(delete_file, sid, fid)
                        )
                    )
                )
            status_txt.value = f"選択中: {sid}"
            self.page.update()

        async def create_store(_e):
            if new_store_field.value.strip():
                status_txt.value = "作成中..."
                self.page.update()
                await self.state.rag_usecase.create_vector_store(new_store_field.value.strip())
                new_store_field.value = ""
                await refresh_stores()

        async def delete_file(sid: str, fid: str):
            status_txt.value = "ファイル削除中..."
            self.page.update()
            await self.state.rag_usecase.delete_file_from_store_and_storage(sid, fid)
            await select_store(sid)

        async def pick_and_upload(_e):
            if not selected_store_id[0]:
                status_txt.value = "Vector Storeが選択されていません。"
                self.page.update()
                return
            file_picker = ft.FilePicker()
            files = await file_picker.pick_files(allow_multiple=True)
            if files:
                for f in files:
                    status_txt.value = f"アップロード・インデックス中: {f.name}..."
                    self.page.update()
                    await self.state.rag_usecase.upload_and_index_file(f.path, selected_store_id[0])
                await select_store(selected_store_id[0])

        upload_btn = ft.ElevatedButton(
            "ファイル追加 📄",
            on_click=lambda e: self.page.run_task(pick_and_upload, e)
        )

        dlg = ft.AlertDialog(
            title=ft.Text("ナレッジベース (Vector Store) 管理"),
            content=ft.Container(
                content=ft.Column([
                    ft.Row([new_store_field, ft.ElevatedButton("作成", on_click=create_store)]),
                    ft.Divider(),
                    ft.Row([
                        ft.Column([ft.Text("Vector Stores", weight="bold"), store_list], expand=True),
                        ft.VerticalDivider(),
                        ft.Column([ft.Row([ft.Text("ファイル一覧", weight="bold"), upload_btn]), file_list], expand=True)
                    ], expand=True),
                    status_txt
                ]),
                width=800, height=500
            ),
            actions=[ft.TextButton("閉じる", on_click=lambda _e: (setattr(dlg, "open", False), self.page.update(), self.page.run_task(self.state.refresh_vector_stores)))]
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()
        self.page.run_task(refresh_stores)


# --- Application Main Entry Point ---
def main(page: ft.Page) -> None:
    log.info("SYUKATSU Support App starting (Single-File Architecture)...")
    try:
        state = AppState()
        SyukatsuSupportApp(page, state)
    except Exception as e:
        log_crash_and_exit(e)
        log.critical(f"Application failed to start: {e}", exc_info=True)
        err_msg = translate_api_error(e)
        dlg = ft.AlertDialog(
            title=ft.Text("起動エラー", color=ft.Colors.RED),
            content=ft.Text(f"起動中にエラーが発生しました:\n\n{err_msg}"),
            open=True,
            actions=[ft.TextButton("OK", on_click=lambda _e: page.window.close())],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(dlg)
        page.update()


if __name__ == "__main__":
    # Clean up broken temp cache folders in .flet/client if any
    flet_cache_dir = Path.home() / ".flet" / "client"
    if flet_cache_dir.exists():
        try:
            for tmp_path in flet_cache_dir.glob("*"):
                if tmp_path.is_dir() and len(tmp_path.name.split(".")) > 3:
                    try:
                        import shutil
                        shutil.rmtree(tmp_path, ignore_errors=True)
                    except Exception:
                        pass
        except Exception:
            pass

    max_retries = 5
    for attempt in range(max_retries):
        try:
            ft.run(main)
            break
        except PermissionError as pe:
            if attempt == max_retries - 1:
                log_crash_and_exit(pe)
                raise
            import time
            time.sleep(1.5)
        except Exception as e:
            log_crash_and_exit(e)
            raise
