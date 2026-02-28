"""
アプリケーション状態およびビジネスロジック管理モジュール。

UIフレームワークから独立して、アプリケーションの全ての「状態」と「振る舞い」を管轄します。
ReflexのStateパターンを模倣し、Tkinter UIからはこの層のメソッドのみを呼び出します。
"""

import asyncio
import datetime
import queue
import threading
import structlog
from typing import Callable, Optional, List

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
from src.core.prompts import SYSTEM_PROMPTS

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
        
        # UI Callbacks for Reactive Updates
        self.on_state_change: Optional[Callable[[], None]] = None
        self.on_text_delta: Optional[Callable[[str, str], None]] = None # (text, tag)
        self.on_clear_text: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[str, str], None]] = None # (title, msg)
        self.on_info: Optional[Callable[[str, str], None]] = None # (title, msg)
        self.on_vs_updated: Optional[Callable[[List[str]], None]] = None
        
        # --- Internal ---
        self.client: Optional[OpenAIClient] = None
        self.message_queue: queue.Queue = queue.Queue()
        self.cancel_event: threading.Event = threading.Event()
        self.active_thread: Optional[threading.Thread] = None

        if self.config.api_key:
            self.init_client()

    def _notify(self):
        if self.on_state_change:
            self.on_state_change()

    def init_client(self):
        if self.config.api_key:
            self.client = OpenAIClient(self.config.api_key)
            self.refresh_vector_stores()

    def save_config(self):
        ConfigManager.save(self.config)

    def update_api_key(self, api_key: str):
        if api_key:
            self.config.api_key = api_key
            self.save_config()
            self.init_client()
            if self.on_info:
                self.on_info("設定完了", "APIキーを登録し保存しました。")

    def get_system_prompt(self, mode_name: str) -> str:
        return SYSTEM_PROMPTS.get(mode_name, "")

    def refresh_vector_stores(self):
        if not self.client:
            return

        async def _fetch():
            try:
                stores = await self.client.list_vector_stores()
                values = [f"{s.name} ({s.id})" if getattr(s, "name", None) else getattr(s, "id", "") for s in stores]
                if self.on_vs_updated:
                    self.on_vs_updated(values)
            except Exception as e:
                log.error("Failed to fetch vector stores", error=str(e))

        threading.Thread(target=lambda: asyncio.run(_fetch()), daemon=True).start()

    def clear_context(self):
        self.config.last_response_id = None
        self.cost_info = "Cost: $0.00000"
        self.status_message = "コンテキストを消去しました。"
        if self.on_clear_text:
            self.on_clear_text()
        self._notify()

    def cancel_generation(self):
        if self.is_processing:
            self.cancel_event.set()
            if self.on_text_delta:
                self.on_text_delta("\n[SYSTEM] ユーザーによって中断されました。\n", "error")

    def handle_submit(self, user_input: str, system_prompt: str):
        if self.is_processing or not user_input.strip():
            return

        if not self.config.api_key or not self.client:
            if self.on_error:
                self.on_error("APIキー未設定", "API Keyを入力してください。")
            return

        tools = None
        if self.config.use_file_search:
            vs_val = self.config.current_vector_store_id
            if not vs_val:
                if self.on_error:
                    self.on_error("RAGエラー", "Vector Storeが選択されていません。")
                return
            
            vs_id = vs_val.split("(")[-1].strip(")") if "(" in vs_val else vs_val
            tools = [FileSearchTool(type="file_search", vector_store_ids=[vs_id])]

        self.is_processing = True
        self.status_message = f"{self.config.model} ({self.config.reasoning_effort}) で分析中..."
        self.cancel_event.clear()
        self._notify()

        timestamp = datetime.datetime.now().strftime("%H:%M")
        if self.on_text_delta:
            self.on_text_delta(f"\n[USER] {timestamp}\n{user_input}\n", "user")

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
            if self.on_error:
                self.on_error("設定エラー", f"不正な設定値です: {e}")
            self.is_processing = False
            self._notify()
            return

        self.active_thread = threading.Thread(
            target=self._run_llm_thread,
            args=(payload,),
            daemon=True,
        )
        self.active_thread.start()

    def _run_llm_thread(self, payload: ResponseRequestPayload):
        async def _async_run():
            try:
                start_msg = f"\n[AI ({payload.model})] analyzing...\n（数分から10分程度の時間を要する場合があります。）\n\n"
                self.message_queue.put(StreamTextDelta(delta=start_msg))

                stream = self.client.stream_analysis(payload)
                async for event in stream:
                    if self.cancel_event.is_set():
                        break
                    self.message_queue.put(event)

            except Exception as e:
                log.exception("LLM thread failed", error=str(e))
                self.message_queue.put(StreamError(message=str(e)))
            finally:
                self.message_queue.put(None)

        asyncio.run(_async_run())

    def process_queue_events(self):
        """
        メインスレッド（GUIのイベントループ）から周期的に呼ばれ、
        バックグラウンドスレッドで発生したイベントを処理してUIを更新します。
        """
        try:
            for _ in range(50):
                event = self.message_queue.get_nowait()
                if event is None:
                    self.is_processing = False
                    self.status_message = "待機中"
                    self._notify()
                    break

                elif isinstance(event, StreamTextDelta):
                    if self.on_text_delta:
                        self.on_text_delta(event.delta, "ai")

                elif isinstance(event, StreamResponseCreated):
                    self.config.last_response_id = event.response_id
                    self._notify()

                elif isinstance(event, StreamUsage):
                    self.cost_info = CostCalculator.calculate(self.config.model, event)
                    self._notify()

                elif isinstance(event, StreamError):
                    if "_REASONING_EFFORT_ERROR_" in event.message:
                        err_msg = f"{self.config.model} では推論強度「{self.config.reasoning_effort}」は使用できません。"
                        if self.on_error:
                            self.on_error("設定エラー", err_msg)
                        if self.on_text_delta:
                            self.on_text_delta(f"\n[エラー] {err_msg}\n", "error")
                    else:
                        if self.on_text_delta:
                            self.on_text_delta(event.message, "error")

        except queue.Empty:
            pass

