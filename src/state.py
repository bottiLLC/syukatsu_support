"""アプリケーション状態およびビジネスロジック管理モジュール。

UIフレームワークから独立して、アプリケーションの全状態とユースケース連携を管理します。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from src.application.usecases.llm_usecase import LLMUseCase
from src.application.usecases.rag_usecase import RAGUseCase
from src.core.pricing import CostCalculator
from src.core.prompts import PromptManager
from src.infrastructure.openai_client import OpenAIClient
from src.infrastructure.security import ConfigManager
from src.models import (
    AnalysisMethod,
    AppConfigDefaults,
    FileSearchTool,
    InputFileContent,
    InputMessage,
    InputTextContent,
    ReasoningOptions,
    ResponseRequestPayload,
    StreamError,
    StreamResponseCreated,
    StreamTextDelta,
    StreamUsage,
    UserConfig,
    ViewMode,
)

log = structlog.get_logger()

# Reactive UI Callback Types
StateChangeCallback = Callable[[], Awaitable[None] | None]
TextDeltaCallback = Callable[[str, str], Awaitable[None] | None]
DialogCallback = Callable[[str, str], Awaitable[None] | None]
VectorStoresCallback = Callable[[list[str]], Awaitable[None] | None]


class AppState:
    """アプリケーションのグローバルな状態とすべてのユースケース（機能）を管理するクラス。"""

    def __init__(self) -> None:
        """AppState インスタンスを初期化し、設定とプロンプトをロードします。"""
        # --- State Variables ---
        self.config: UserConfig = ConfigManager.load()
        self.is_processing: bool = False
        self.status_message: str = "待機中"
        self.cost_info: str = "Cost: $0.00000"
        self._uploaded_file_cache: dict[str, str] = {}

        # --- Prompt Management ---
        self.prompt_manager: PromptManager = PromptManager()
        self.available_prompt_modes: list[str] = self.prompt_manager.get_all_modes()

        # UI Callbacks for Reactive Updates
        self.on_state_change: StateChangeCallback | None = None
        self.on_text_delta: TextDeltaCallback | None = None
        self.on_clear_text: StateChangeCallback | None = None
        self.on_error: DialogCallback | None = None
        self.on_info: DialogCallback | None = None
        self.on_vs_updated: VectorStoresCallback | None = None

        # --- Internal ---
        self.client: OpenAIClient | None = None
        self.llm_usecase: LLMUseCase | None = None
        self.rag_usecase: RAGUseCase | None = None
        self.cancel_event: asyncio.Event = asyncio.Event()
        self._background_tasks: set[asyncio.Task[Any]] = set()

        if self.config.api_key:
            self.init_client()

    async def _notify(self) -> None:
        """状態変更イベントをUIコールバックへ通知します。"""
        if self.on_state_change:
            res = self.on_state_change()
            if asyncio.iscoroutine(res):
                await res

    async def _notify_text(self, text: str, tag: str) -> None:
        """テキスト差分イベントをUIログへ通知します。"""
        if self.on_text_delta:
            res = self.on_text_delta(text, tag)
            if asyncio.iscoroutine(res):
                await res

    async def _notify_error(self, title: str, msg: str) -> None:
        """エラーダイアログ表示イベントをUIへ通知します。"""
        if self.on_error:
            res = self.on_error(title, msg)
            if asyncio.iscoroutine(res):
                await res

    async def _notify_info(self, title: str, msg: str) -> None:
        """情報ダイアログ表示イベントをUIへ通知します。"""
        if self.on_info:
            res = self.on_info(title, msg)
            if asyncio.iscoroutine(res):
                await res

    def init_client(self) -> None:
        """APIキーに基づいて OpenAIClient および各ユースケースを初期化します。"""
        if self.config.api_key:
            self.client = OpenAIClient(self.config.api_key)
            self.llm_usecase = LLMUseCase(self.client)
            self.rag_usecase = RAGUseCase(self.client)
            task = asyncio.create_task(self.refresh_vector_stores())
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    def save_config(self) -> None:
        """現在のユーザー設定を永続化ファイルに保存します。"""
        ConfigManager.save(self.config)

    async def update_api_key(self, api_key: str, silent: bool = False) -> None:
        """OpenAI APIキーを検証・保存し、クライアントを再初期化します。"""
        if api_key:
            cleaned_key = api_key.strip().replace("　", "")
            try:
                cleaned_key.encode("ascii")
            except UnicodeEncodeError:
                await self._notify_error(
                    "APIキー入力エラー",
                    "入力されたAPIキーに全角文字が含まれています。\nAPIキーはすべて半角英数字・記号で入力してください。",
                )
                return

            self.config.api_key = cleaned_key
            self.save_config()
            self.init_client()
            if not silent:
                await self._notify_info("設定完了", "APIキーを登録し保存しました。")

    def get_system_prompt(self, mode_name: str) -> str:
        """指定された分析モードのシステムプロンプトを取得します。"""
        return self.prompt_manager.get_prompt(mode_name)

    async def refresh_vector_stores(self) -> None:
        """接続された OpenAI アカウントから Vector Store 一覧を取得・更新します。"""
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

    async def set_view_mode(self, mode: ViewMode) -> None:
        """UI表示モードを切り替えて設定を保存します。"""
        self.config.view_mode = mode
        self.save_config()
        await self._notify()

    async def set_active_pdf(self, path: str | None) -> None:
        """分析対象の有価証券報告書 (PDF) のパスを設定・保存します。"""
        self.config.active_pdf_path = path
        self.save_config()
        await self._notify()

    async def set_analysis_method(self, method: AnalysisMethod) -> None:
        """分析方式（直接分析またはRAG）を切り替えて設定を保存します。"""
        self.config.analysis_method = method
        self.config.use_file_search = method == AnalysisMethod.RAG
        self.save_config()
        await self._notify()

    async def clear_context(self) -> None:
        """会話コンテキストIDおよびログ表示を消去して初期状態に復帰します。"""
        self.config.last_response_id = None
        self.cost_info = "Cost: $0.00000"
        self.status_message = "コンテキストを消去しました。"
        if self.on_clear_text:
            res = self.on_clear_text()
            if asyncio.iscoroutine(res):
                await res
        await self._notify()

    async def cancel_generation(self) -> None:
        """実行中の分析ストリーミング処理を中断します。"""
        if self.is_processing:
            self.cancel_event.set()
            await self._notify_text("\n[SYSTEM] ユーザーによって中断されました。\n", "error")

    async def handle_preset_submit(self, mode_name: str) -> None:
        """シンプルモードのプリセットボタンからワンクリックで定型分析を実行します。"""
        if not self.config.active_pdf_path:
            await self._notify_error(
                "PDFファイル未選択",
                "分析対象の有価証券報告書 (PDF) が選択されていません。\n先に「STEP 2」でPDFファイルを指定してください。",
            )
            return

        # シンプルモード初期値の適用
        if self.config.view_mode == ViewMode.SIMPLE:
            self.config.model = AppConfigDefaults.DEFAULT_MODEL
            self.config.reasoning_effort = AppConfigDefaults.DEFAULT_REASONING

        sys_prompt = self.get_system_prompt(mode_name)
        if not sys_prompt:
            await self._notify_error("モードエラー", f"分析モード「{mode_name}」のプロンプトが見つかりません。")
            return

        user_query = (
            f"添付された有価証券報告書 (PDF) を精読し、「{mode_name}」の分析観点に基づき、"
            "事実と数値の証拠を引用しながら詳細な分析レポートを作成してください。"
        )
        await self.handle_submit(user_query, sys_prompt)

    async def handle_submit(self, user_input: str, system_prompt: str) -> None:
        """ユーザーリクエストを検証し、LLM分析ストリーミングを実行・監視します。"""
        if self.is_processing or not user_input.strip():
            return

        if not self.config.api_key or not self.client:
            await self._notify_error(
                "APIキーが未登録です",
                "OpenAI APIキーが設定されていません。\n画面の「OpenAI APIキー」設定よりAPIキーを入力・登録してください。",
            )
            return

        # 1. ツール構成 (RAG または直接分析)
        tools: list[Any] | None = None
        use_rag = self.config.analysis_method == AnalysisMethod.RAG or self.config.use_file_search

        if use_rag:
            vs_val = self.config.current_vector_store_id
            if not vs_val:
                await self._notify_error("RAGエラー", "Vector Storeが選択されていません。")
                return

            vs_id = vs_val.split("(")[-1].strip(")") if "(" in vs_val else vs_val
            tools = [FileSearchTool(type="file_search", vector_store_ids=[vs_id])]

        # 2. リクエスト入力の構築 (PDF直接添付またはテキスト)
        req_input: list[InputMessage] | str = user_input

        if not use_rag and self.config.active_pdf_path:
            pdf_path = Path(self.config.active_pdf_path)
            if not pdf_path.exists():
                await self._notify_error(
                    "ファイルエラー",
                    f"指定された有価証券報告書PDFが存在しません:\n{self.config.active_pdf_path}",
                )
                return

            # ファイルアップロードまたはキャッシュから file_id を取得
            file_id = self._uploaded_file_cache.get(str(pdf_path))
            if not file_id:
                self.is_processing = True
                self.status_message = "有報PDFをアップロード中..."
                await self._notify()
                try:
                    file_obj = await self.client.upload_file(str(pdf_path), purpose="assistants")
                    file_id = file_obj.id
                    self._uploaded_file_cache[str(pdf_path)] = file_id
                except Exception as e:
                    await self._notify_error(
                        "PDFアップロード失敗", f"OpenAIへのファイルアップロードに失敗しました:\n{e}"
                    )
                    self.is_processing = False
                    self.status_message = "エラー発生"
                    await self._notify()
                    return

            req_input = [
                InputMessage(
                    role="user",
                    content=[
                        InputFileContent(type="input_file", file_id=file_id),
                        InputTextContent(type="input_text", text=user_input),
                    ],
                )
            ]

        self.is_processing = True
        self.status_message = f"{self.config.model} ({self.config.reasoning_effort}) で分析中..."
        self.cancel_event.clear()
        await self._notify()

        timestamp = datetime.now(UTC).astimezone().strftime("%H:%M")
        await self._notify_text(f"\n[USER] {timestamp}\n{user_input}\n", "user")

        prev_id = self.config.last_response_id if self.config.last_response_id != "None" else None

        try:
            payload = ResponseRequestPayload(
                model=self.config.model,
                input=req_input,
                instructions=system_prompt,
                reasoning=ReasoningOptions(effort=self.config.reasoning_effort),
                previous_response_id=prev_id,
                tools=tools,
                stream=True,
                max_output_tokens=AppConfigDefaults.DEFAULT_MAX_OUTPUT_TOKENS,
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
                        err_msg = (
                            f"{self.config.model} では推論強度「{self.config.reasoning_effort}」は使用できません。"
                        )
                        await self._notify_error("設定エラー", err_msg)
                        await self._notify_text(f"\n[エラー] {err_msg}\n", "error")
                    else:
                        await self._notify_text(event.message, "error")

            self.is_processing = False
            self.status_message = "待機中"
            await self._notify()
