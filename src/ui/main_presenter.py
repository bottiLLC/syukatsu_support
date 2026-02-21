import asyncio
import datetime
import logging
import queue
import threading
from pathlib import Path
from typing import Any, List, Optional

from src.core.models import (
    FileSearchTool,
    ReasoningOptions,
    ResponseRequestPayload,
    StreamError,
    StreamResponseCreated,
    StreamTextDelta,
    StreamUsage,
)
from src.core.rag_services import FileService, VectorStoreService
from src.core.services import CostCalculator, LLMService
from src.core.prompts import SYSTEM_PROMPTS
from src.ui.main_model import MainModel
from src.ui.main_view import MainView

logger = logging.getLogger(__name__)

class MainPresenter:
    """
    MVP Presenter for the main application.
    Orchestrates communication between MainView and MainModel,
    as well as interacting with backend services.
    """

    def __init__(self, view: MainView, model: MainModel) -> None:
        self.view = view
        self.model = model

        self._bind_callbacks()
        self._apply_initial_state()

        if self.model.user_config.api_key:
            self._init_services(self.model.user_config.api_key)
            self._refresh_vector_stores()

        # Start the message loop
        self.view.after(100, self._process_queue)

    def _bind_callbacks(self) -> None:
        self.view.on_close_callback = self.handle_close
        self.view.on_key_update_callback = self.handle_key_update
        self.view.on_apply_prompt_mode_callback = self.handle_apply_prompt_mode
        self.view.on_open_rag_manager_callback = self.handle_open_rag_manager
        self.view.on_start_generation_callback = self.handle_start_generation
        self.view.on_stop_generation_callback = self.handle_stop_generation
        self.view.on_clear_context_callback = self.handle_clear_context
        self.view.on_save_log_callback = self.handle_save_log

    def _apply_initial_state(self) -> None:
        mode = self.view.prompt_mode_var.get()
        prompt = SYSTEM_PROMPTS.get(mode, "")
        self.view.set_system_prompt(prompt)

    def _init_services(self, api_key: str) -> None:
        try:
            self.model.rag_service = VectorStoreService(api_key)
            self.model.file_service = FileService(api_key)
            logger.info("Services initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            self.view.show_error("サービスエラー", f"サービスの初期化に失敗しました: {e}")

    def handle_key_update(self, api_key: str) -> None:
        if api_key:
            self._init_services(api_key)
            self._refresh_vector_stores()

    def handle_apply_prompt_mode(self, mode: str) -> None:
        prompt = SYSTEM_PROMPTS.get(mode, "")
        self.view.set_system_prompt(prompt)

    def _refresh_vector_stores(self) -> None:
        if not self.model.rag_service:
            return

        async def _fetch() -> None:
            try:
                if not self.model.rag_service:
                    return
                stores = await self.model.rag_service.list_vector_stores()
                values: List[str] = []
                for s in stores:
                    label = f"{s.name} ({s.id})" if s.name else s.id
                    values.append(label)

                self.view.after(0, lambda: self._update_vs_combo(values))
            except Exception as e:
                logger.error(f"Failed to fetch vector stores: {e}")

        def _thread_target() -> None:
            asyncio.run(_fetch())

        threading.Thread(target=_thread_target, daemon=True).start()

    def _update_vs_combo(self, values: List[str]) -> None:
        self.view.update_vs_combo(values)
        current_id = self.view.vs_id_var.get()
        if current_id:
            found = False
            for i, val in enumerate(values):
                if current_id in val:
                    self.view.set_vs_combo_index(i)
                    found = True
                    break
            if not found:
                self.view.vs_id_var.set("")

    def handle_open_rag_manager(self) -> None:
        try:
            from src.ui.rag_window import RAGManagementWindow
        except ImportError as e:
            logger.error(f"Failed to import RAGManagementWindow: {e}")
            self.view.show_error("エラー", "RAG管理モジュールを読み込めませんでした。")
            return

        api_key = self.view.api_key_var.get().strip()
        if not api_key:
            self.view.show_warning("設定エラー", "API Keyを設定してください。")
            return

        if not self.model.rag_service or not self.model.file_service:
            self._init_services(api_key)

        if self.model.rag_service and self.model.file_service:
            window = RAGManagementWindow(self.view, self.model.rag_service, self.model.file_service)
            self.view.wait_window(window)
            self._refresh_vector_stores()

    def handle_start_generation(self) -> None:
        if self.model.is_generating:
            return

        api_key = self.view.api_key_var.get().strip()
        user_input_text = self.view.get_user_input()
        sys_instructions = self.view.get_system_prompt()

        if not api_key:
            self.view.show_warning("APIキー未設定", "API Keyを入力してください。")
            self.view.focus_api_key()
            return
        if not user_input_text:
            return

        tools = None
        if self.view.use_file_search_var.get():
            vs_val = self.view.vs_id_var.get()
            if not vs_val:
                self.view.show_warning("RAGエラー", "ファイル検索が有効ですが、Vector Storeが選択されていません。")
                return
            vs_id = vs_val.split("(")[-1].strip(")") if "(" in vs_val else vs_val
            tools = [FileSearchTool(type="file_search", vector_store_ids=[vs_id])]

        self.model.is_generating = True
        self.view.set_generation_state(True)
        
        model_name = self.view.model_var.get()
        effort = self.view.reasoning_var.get()
        self.view.status_var.set(f"{model_name} ({effort}) で分析中...")
        self.model.cancel_event.clear()

        timestamp = datetime.datetime.now().strftime("%H:%M")
        self.view.append_log(f"\n[USER] {timestamp}\n{user_input_text}\n", "user")
        self.view.clear_user_input()

        prev_id = self.model.user_config.last_response_id
        if not prev_id or prev_id == "None":
            prev_id = None

        try:
            payload = ResponseRequestPayload(
                model=model_name,
                input=user_input_text,
                instructions=sys_instructions,
                reasoning=ReasoningOptions(effort=effort),  # type: ignore
                previous_response_id=prev_id,
                tools=tools,
                stream=True,
            )
        except Exception as e:
            self.view.show_error("設定エラー", f"不正な設定値です: {e}")
            self.model.is_generating = False
            self.view.set_generation_state(False)
            return

        self.model.active_thread = threading.Thread(
            target=self._run_llm_thread,
            args=(api_key, payload),
            daemon=True,
        )
        self.model.active_thread.start()

    def handle_stop_generation(self) -> None:
        if self.model.is_generating:
            self.model.cancel_event.set()
            self.view.append_log("\n[SYSTEM] ユーザーによって中断されました。\n", "error")

    def _run_llm_thread(self, api_key: str, payload: ResponseRequestPayload) -> None:
        async def _async_run() -> None:
            try:
                if self.model.cancel_event.is_set():
                    return

                service = LLMService(api_key)
                start_msg = f"\n[AI ({payload.model})] analyzing...\n"
                self.model.message_queue.put(StreamTextDelta(delta=start_msg))

                stream = service.stream_analysis(payload)
                async for event in stream:
                    if self.model.cancel_event.is_set():
                        break
                    self.model.message_queue.put(event)

            except Exception as e:
                logger.exception("LLM thread failed")
                self.model.message_queue.put(StreamError(message=str(e)))
            finally:
                self.model.message_queue.put(None)

        asyncio.run(_async_run())

    def _process_queue(self) -> None:
        try:
            while True:
                event = self.model.message_queue.get_nowait()

                if event is None:
                    self.model.is_generating = False
                    self.view.set_generation_state(False)
                    self.view.status_var.set("待機中")

                elif isinstance(event, StreamTextDelta):
                    self.view.append_log(event.delta, "ai")

                elif isinstance(event, StreamResponseCreated):
                    self.model.user_config.last_response_id = event.response_id
                    self.view.response_id_var.set(event.response_id)

                elif isinstance(event, StreamUsage):
                    cost_str = CostCalculator.calculate(self.view.model_var.get(), event)
                    self.view.cost_info_var.set(cost_str)

                elif isinstance(event, StreamError):
                    if "_REASONING_EFFORT_ERROR_" in event.message:
                        model_name = self.view.model_var.get()
                        effort = self.view.reasoning_var.get()
                        msg = f"{model_name} では推論強度「{effort}」は使用できません。"
                        self.view.show_error("設定エラー", msg)
                        self.view.append_log(f"\\n[エラー] {msg}\\n", "error")
                    else:
                        self.view.append_log(event.message, "error")

                self.model.message_queue.task_done()
        except queue.Empty:
            pass

        if self.view.winfo_exists():
            self.view.after(50, self._process_queue)

    def handle_clear_context(self) -> None:
        confirm = self.view.ask_yes_no(
            "コンテキストの消去",
            "会話の文脈（Previous Response ID）を破棄して新しいセッションを開始しますか？",
        )
        if confirm:
            self.model.user_config.last_response_id = None
            self.view.response_id_var.set("None")
            self.view.clear_log()
            self.view.cost_info_var.set("Cost: $0.00000")
            self.view.status_var.set("コンテキストを消去しました。")

    def handle_save_log(self, text: str) -> None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        default_filename = f"分析レポート_{timestamp}.txt"
        path_str = self.view.ask_save_file_name(default_filename)

        if path_str:
            try:
                path = Path(path_str)
                with path.open("w", encoding="utf-8") as f:
                    header = (
                        f"Model: {self.view.model_var.get()}\n"
                        f"Prompt Mode: {self.view.prompt_mode_var.get()}\n"
                        f"Tools: {'File Search' if self.view.use_file_search_var.get() else 'None'}\n"
                    )
                    f.write(header + "-" * 40 + "\n" + text)
                self.view.show_info("保存完了", "ログを保存しました。")
            except Exception as e:
                self.view.show_error("保存エラー", f"保存に失敗しました: {str(e)}")

    def handle_close(self) -> None:
        self.model.user_config.api_key = self.view.api_key_var.get()
        self.model.user_config.model = self.view.model_var.get()
        self.model.user_config.reasoning_effort = self.view.reasoning_var.get()  # type: ignore
        self.model.user_config.system_prompt_mode = self.view.prompt_mode_var.get()

        raw_vs = self.view.vs_id_var.get()
        if "(" in raw_vs:
            self.model.user_config.current_vector_store_id = raw_vs.split("(")[-1].strip(")")
        else:
            self.model.user_config.current_vector_store_id = raw_vs

        self.model.user_config.use_file_search = self.view.use_file_search_var.get()

        try:
            self.model.save_config()
        except Exception as e:
            logger.error(f"Failed to save configuration on close: {e}")
            self.view.show_warning("保存エラー", f"設定の保存に失敗しました: {e}")

        if self.model.is_generating:
            self.model.cancel_event.set()
            if self.model.active_thread and self.model.active_thread.is_alive():
                self.model.active_thread.join(timeout=1.0)
