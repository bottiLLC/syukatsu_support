"""
アプリケーション状態およびビジネスロジック管理モジュール。

UIフレームワークから独立して、アプリケーションの全ての「状態」と「振る舞い」を管轄します。
Fletの非同期環境に最適化されており、async/awaitを用いて直接ロジックを実行します。
"""

import asyncio
import datetime
import structlog
from typing import Callable, Optional, List, Awaitable, Union

from src.models import (
    UserConfig,
    ReasoningOptions,
    ResponseRequestPayload,
    StreamTextDelta,
    StreamResponseCreated,
    StreamUsage,
    StreamError,
    FileSearchTool,
)
from src.core.pricing import CostCalculator
from src.infrastructure.security import ConfigManager
from src.infrastructure.openai_client import OpenAIClient
from src.core.prompts import PromptManager
from src.application.usecases.llm_usecase import LLMUseCase
from src.application.usecases.rag_usecase import RAGUseCase

log = structlog.get_logger()


class AppState:
    """
    アプリケーションのグローバルな状態とすべてのユースケース（機能）を管理するクラス。
    UIコンポーネントはこのクラスのフィールドを読み取り、メソッドを呼び出して操作を行います。
    """
    def __init__(self):
        # --- State Variables ---
        self.config: UserConfig = ConfigManager.load()
        self.is_processing: bool = False
        self.result_text: str = ""
        self.status_message: str = "待機中"
        self.cost_info: str = "Cost: $0.00000"
        
        # --- Prompt Management ---
        self.prompt_manager = PromptManager()
        self.available_prompt_modes = self.prompt_manager.get_all_modes()
        
        # UI Callbacks for Reactive Updates
        self.on_state_change: Optional[Callable[[], Union[None, Awaitable[None]]]] = None
        self.on_text_delta: Optional[Callable[[str, str], Union[None, Awaitable[None]]]] = None # (text, tag)
        self.on_clear_text: Optional[Callable[[], Union[None, Awaitable[None]]]] = None
        self.on_error: Optional[Callable[[str, str], Union[None, Awaitable[None]]]] = None # (title, msg)
        self.on_info: Optional[Callable[[str, str], Union[None, Awaitable[None]]]] = None # (title, msg)
        self.on_vs_updated: Optional[Callable[[List[str]], Union[None, Awaitable[None]]]] = None
        
        # --- Internal ---
        self.client: Optional[OpenAIClient] = None
        self.llm_usecase: Optional[LLMUseCase] = None
        self.rag_usecase: Optional[RAGUseCase] = None
        self.cancel_event: asyncio.Event = asyncio.Event()

        if self.config.api_key:
            self.init_client()

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
            self.config.api_key = api_key
            self.save_config()
            self.init_client()
            if not silent:
                await self._notify_info("設定完了", "APIキーを登録し保存しました。")

    def get_system_prompt(self, mode_name: str) -> str:
        return self.prompt_manager.get_prompt(mode_name)

    async def refresh_vector_stores(self):
        if not self.rag_usecase:
            return
        try:
            stores = await self.rag_usecase.list_vector_stores()
            values = [f"{s.name} ({s.id})" if getattr(s, "name", None) else getattr(s, "id", "") for s in stores]
            if self.on_vs_updated:
                res = self.on_vs_updated(values)
                if asyncio.iscoroutine(res):
                    await res
        except Exception as e:
            log.error("Failed to fetch vector stores", error=str(e))

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
            await self._notify_text("\n[SYSTEM] ユーザーによって中断されました。\n", "error")

    async def handle_submit(self, user_input: str, system_prompt: str):
        if self.is_processing or not user_input.strip():
            return

        if not self.config.api_key or not self.client:
            await self._notify_error("APIキー未設定", "API Keyを入力してください。")
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
                    if "_REASONING_EFFORT_ERROR_" in event.message:
                        err_msg = f"{self.config.model} では推論強度「{self.config.reasoning_effort}」は使用できません。"
                        await self._notify_error("設定エラー", err_msg)
                        await self._notify_text(f"\n[エラー] {err_msg}\n", "error")
                    else:
                        await self._notify_text(event.message, "error")

            self.is_processing = False
            self.status_message = "待機中"
            await self._notify()


