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

"""就職活動サポートアプリ メイン UI モジュール。

Flet を使用したデスクトップ GUI の構築、リアクティブなステート連携、
シンプルモード・詳細モードの切り替え、PDF直接投入・RAG分析、
および各種分析・ナレッジベース操作のユーザーイベントハンドラを提供します。
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import flet as ft

from src.core.docx_exporter import export_markdown_to_docx
from src.core.prompts import (
    MODE_ENTRY_SHEET,
    MODE_FINANCIAL,
    MODE_HUMAN_CAPITAL,
)
from src.core.utils import clean_citation_markers, extract_markdown_content
from src.models import AnalysisMethod, AppConfigDefaults, ReasoningEffort, ViewMode
from src.state import AppState
from src.styles import UI_COLORS


class SyukatsuSupportApp:
    """就活サポートアプリのメインビューおよびイベント配線を統括するクラス。"""

    def __init__(self, page: ft.Page, state: AppState) -> None:
        """SyukatsuSupportApp を初期化し、UIを構築します。

        Args:
            page: Flet Page オブジェクト
            state: アプリケーション状態管理オブジェクト
        """
        self.page = page
        self.state = state
        self.page.title = "SYUKATSU Support - 合同会社ぼっち (v2.3.0)"
        self.page.padding = ft.Padding(12, 8, 12, 8)
        self.page.theme_mode = ft.ThemeMode.LIGHT

        # Set default window size to fit layout without scrolling
        self.page.window.width = 1380
        self.page.window.height = 980

        # State Binding Setup
        self.state.on_state_change = self._sync_from_state
        self.state.on_text_delta = self._append_log
        self.state.on_clear_text = self._clear_log
        self.state.on_error = self._show_error
        self.state.on_info = self._show_info
        self.state.on_vs_updated = self._update_vs_combo

        self.chat_list = ft.ListView(expand=True, spacing=10, auto_scroll=True)
        self.current_ai_message: ft.Markdown | None = None
        self.current_ai_text: str = ""

        self._build_ui()
        # Initialize UI with current state values
        self.page.run_task(self._sync_from_state)

    def _build_ui(self) -> None:
        """メイン画面の各コンポーネントをレイアウトに配置します。"""
        # --- Top AppBar: 常駐型モード切り替えヘッダー ---
        self._build_appbar()

        # --- Left Panels: シンプルモード & 詳細モード ---
        self._build_simple_panel()
        self._build_advanced_panel()

        # 左パネルの動的コンテナ（現在選択されているモードのパネルを格納）
        self.left_panel_container = ft.Container(
            content=self.simple_panel if self.state.config.view_mode == ViewMode.SIMPLE else self.advanced_panel,
            width=430,
        )

        # --- Right Panel: レポート出力・ストリーミング・操作エリア ---
        self._build_right_panel()

        # Main Layout (左右分割)
        main_row = ft.Row(
            [self.left_panel_container, ft.VerticalDivider(width=1), self.right_column],
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

        # Status Bar
        self.status_text = ft.Text(self.state.status_message, size=12)
        self.cost_text = ft.Text(self.state.cost_info, size=12)
        bottom_bar = ft.Container(
            content=ft.Row([self.status_text, self.cost_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.Padding(10, 5, 10, 5),
            bgcolor=ft.Colors.GREY_200,
            border_radius=5,
        )

        self.page.add(
            ft.Column(
                [
                    main_row,
                    bottom_bar,
                ],
                expand=True,
            )
        )

    def _build_appbar(self) -> None:
        """AppBar 常駐型セグメントボタンによるモード切替ヘッダーを構築します。"""
        self.mode_segment = ft.SegmentedButton(
            segments=[
                ft.Segment(
                    value=ViewMode.SIMPLE.value,
                    label=ft.Text("🔰 かんたん (シンプル)"),
                    icon=ft.Icon(ft.Icons.LIGHTBULB_OUTLINE),
                ),
                ft.Segment(
                    value=ViewMode.ADVANCED.value,
                    label=ft.Text("⚙️ 詳細 (カスタム)"),
                    icon=ft.Icon(ft.Icons.TUNE),
                ),
            ],
            selected=[self.state.config.view_mode.value],
            allow_multiple_selection=False,
            on_change=self._on_mode_change,
        )

        self.page.appbar = ft.AppBar(
            leading=ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.BLUE_600, size=26),
            title=ft.Text(
                f"就職活動サポートAI（Powerd by {AppConfigDefaults.DEFAULT_MODEL}）",
                weight=ft.FontWeight.BOLD,
                size=18,
            ),
            center_title=False,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            actions=[
                ft.Container(
                    content=self.mode_segment,
                    margin=ft.margin.only(right=16),
                )
            ],
        )

    def _build_simple_panel(self) -> None:
        """シンプルモード: 直感的な3ステップ動線パネルを構築します。"""
        # [STEP 1] APIキー状態コンポーネント
        has_key = bool(self.state.config.api_key)
        self.simple_api_icon = ft.Icon(
            ft.Icons.CHECK_CIRCLE if has_key else ft.Icons.WARNING,
            color=ft.Colors.GREEN_600 if has_key else ft.Colors.ORANGE_800,
            size=20,
        )
        self.simple_api_label = ft.Text(
            "登録完了" if has_key else "APIキー: 未設定 (要登録)",
            size=13,
            weight=ft.FontWeight.W_500,
            color=ft.Colors.GREEN_700 if has_key else ft.Colors.RED_800,
        )
        self.simple_api_btn = ft.OutlinedButton(
            "設定 / 変更",
            icon=ft.Icons.KEY,
            on_click=self._on_open_api_key_dialog,
            style=ft.ButtonStyle(
                padding=ft.Padding(12, 6, 12, 6),
            ),
        )

        step1_card = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text("STEP 1", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900),
                                self.simple_api_icon,
                                self.simple_api_label,
                            ],
                            alignment=ft.MainAxisAlignment.START,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=8,
                        ),
                        ft.Row(
                            [self.simple_api_btn],
                            alignment=ft.MainAxisAlignment.END,
                        ),
                    ],
                    spacing=4,
                ),
                padding=ft.Padding(12, 8, 12, 8),
            ),
            elevation=1,
        )

        # [STEP 2] 有価証券報告書 (PDF) ドロップ＆選択コンポーネント
        self.simple_file_name = ft.Text(
            "有価証券報告書 (PDF) が未選択です",
            size=13,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.GREY_800,
            text_align=ft.TextAlign.CENTER,
        )
        self.simple_file_meta = ft.Text("", size=11, color=ft.Colors.GREY_600)
        self.simple_clear_pdf_btn = ft.TextButton(
            "✕ 解除",
            icon=ft.Icons.CLOSE,
            visible=False,
            on_click=self._on_clear_pdf,
        )

        self.simple_pick_pdf_btn = ft.ElevatedButton(
            "有報PDFを選択する",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=self._on_pick_pdf,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(14, 8, 14, 8),
            ),
        )

        step2_drop_zone = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.PICTURE_AS_PDF, size=32, color=ft.Colors.BLUE_600),
                    ft.Text(
                        "EDINETからダウンロードした\n有価証券報告書 (PDF) を指定",
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    self.simple_pick_pdf_btn,
                    self.simple_file_name,
                    self.simple_file_meta,
                    self.simple_clear_pdf_btn,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=4,
            ),
            border=ft.border.all(1.5, ft.Colors.BLUE_300),
            border_radius=10,
            padding=ft.Padding(12, 8, 12, 8),
            bgcolor=ft.Colors.BLUE_50,
        )

        step2_card = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "STEP 2: 有価証券報告書 (PDF) を指定", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900
                        ),
                        step2_drop_zone,
                    ],
                    spacing=6,
                ),
                padding=ft.Padding(12, 8, 12, 8),
            ),
            elevation=1,
        )

        # [STEP 3] 3大プリセット分析ボタン群
        self.btn_preset_finance = ft.FilledButton(
            "１．財務分析",
            icon=ft.Icons.ANALYTICS,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(14, 9, 14, 9),
            ),
            on_click=lambda _: self.page.run_task(self._on_preset_click, MODE_FINANCIAL),
            expand=True,
        )
        self.btn_preset_human_capital = ft.FilledButton(
            "２．人的資本分析",
            icon=ft.Icons.PEOPLE_ALT,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(14, 9, 14, 9),
                bgcolor=ft.Colors.TEAL_700,
            ),
            on_click=lambda _: self.page.run_task(self._on_preset_click, MODE_HUMAN_CAPITAL),
            expand=True,
        )
        self.btn_preset_entry_sheet = ft.FilledButton(
            "３．志望動機検討",
            icon=ft.Icons.LIGHTBULB,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(14, 9, 14, 9),
                bgcolor=ft.Colors.AMBER_800,
            ),
            on_click=lambda _: self.page.run_task(self._on_preset_click, MODE_ENTRY_SHEET),
            expand=True,
        )

        step3_card = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "STEP 3: 分析する観点を選択（ワンクリックで実行）",
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.BLUE_900,
                        ),
                        ft.Text(
                            "ボタンを押すと、AIが有報を精読し自動でレポートを生成します。",
                            size=11,
                            color=ft.Colors.GREY_600,
                        ),
                        self.btn_preset_finance,
                        self.btn_preset_human_capital,
                        self.btn_preset_entry_sheet,
                    ],
                    spacing=6,
                ),
                padding=ft.Padding(12, 8, 12, 8),
            ),
            elevation=1,
        )

        self.simple_panel = ft.Column(
            [
                step1_card,
                step2_card,
                step3_card,
            ],
            spacing=8,
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
        )

    def _build_advanced_panel(self) -> None:
        """詳細モード: 自由プロンプト入力、モデル・推論強度・RAG/直接分析を包含したパネルを構築します。"""
        # APIキー
        self.api_key_field = ft.TextField(
            label="OpenAI APIキー",
            password=True,
            can_reveal_password=True,
            value=self.state.config.api_key or "",
            expand=True,
            dense=True,
        )
        self.api_key_btn = ft.ElevatedButton("登録", on_click=self._on_register_key)
        self.api_key_disclaimer = ft.Text(
            "※APIキーは本PC内（./data）に暗号化保存され、外部送信されません。",
            color=ft.Colors.GREY_600,
            size=10.5,
        )

        # PDF直接指定
        self.adv_file_name = ft.Text("有報PDF: 未選択", size=12, color=ft.Colors.GREY_700, weight=ft.FontWeight.BOLD)
        self.adv_pick_pdf_btn = ft.OutlinedButton("PDF選択", icon=ft.Icons.UPLOAD_FILE, on_click=self._on_pick_pdf)
        self.adv_clear_pdf_btn = ft.TextButton("解除", icon=ft.Icons.CLOSE, visible=False, on_click=self._on_clear_pdf)

        pdf_select_row = ft.Row(
            [
                self.adv_pick_pdf_btn,
                ft.Container(content=self.adv_file_name, expand=True),
                self.adv_clear_pdf_btn,
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # 分析方式の切り替え
        self.method_radio = ft.RadioGroup(
            content=ft.Row(
                [
                    ft.Radio(value=AnalysisMethod.DIRECT, label="⚡ 直接分析 (PDF全文・高速)"),
                    ft.Radio(value=AnalysisMethod.RAG, label="📚 RAG分析 (Vector Store)"),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            value=self.state.config.analysis_method,
            on_change=self._on_analysis_method_change,
        )

        # モデル & 推論強度
        current_model = self.state.config.model
        if current_model not in ["gpt-6-astra", "gpt-6.1-sol", "gpt-6-luna"]:
            current_model = AppConfigDefaults.DEFAULT_MODEL
            self.state.config.model = current_model

        reasoning_opts = (
            ["max", "xhigh", "high", "medium", "low", "none"]
            if current_model == "gpt-6-luna"
            else ["max", "xhigh", "high", "medium", "low"]
        )
        if self.state.config.reasoning_effort not in reasoning_opts:
            self.state.config.reasoning_effort = AppConfigDefaults.DEFAULT_REASONING

        self.model_combo = ft.Dropdown(
            label="モデル",
            options=[
                ft.dropdown.Option("gpt-6-astra"),
                ft.dropdown.Option("gpt-6.1-sol"),
                ft.dropdown.Option("gpt-6-luna"),
            ],
            value=self.state.config.model,
            expand=True,
            dense=True,
            on_select=self._on_model_change,
        )
        self.reasoning_combo = ft.Dropdown(
            label="推論強度",
            options=[ft.dropdown.Option(o) for o in reasoning_opts],
            value=self.state.config.reasoning_effort,
            expand=True,
            dense=True,
        )

        # RAGナレッジベース設定
        self.vs_combo = ft.Dropdown(
            label="Vector Store",
            options=[],
            value=self.state.config.current_vector_store_id,
            dense=True,
            width=390,
        )
        self.use_file_search_cb = ft.Checkbox(
            label="File Search (RAG) ツールを使用",
            value=self.state.config.use_file_search,
            on_change=self._on_toggle_file_search,
        )
        self.rag_btn = ft.ElevatedButton("🛠️ ナレッジベース管理", on_click=self._on_open_rag_manager)

        # プロンプト設定
        prompt_options = [ft.dropdown.Option(m) for m in self.state.available_prompt_modes]
        valid_val = (
            self.state.config.system_prompt_mode
            if self.state.config.system_prompt_mode in self.state.available_prompt_modes
            else (self.state.available_prompt_modes[0] if self.state.available_prompt_modes else None)
        )

        self.mode_combo = ft.Dropdown(
            label="分析モード選択",
            options=prompt_options,
            value=valid_val,
            dense=True,
            on_select=self._on_prompt_mode_select,
            width=390,
        )

        self.sys_prompt_field = ft.TextField(
            label="システムプロンプト",
            multiline=True,
            width=390,
            min_lines=8,
            max_lines=12,
            value=self.state.get_system_prompt(self.state.config.system_prompt_mode),
            text_size=12,
        )
        self.clear_btn = ft.ElevatedButton("🧹 コンテキスト消去", on_click=self._on_clear_context)

        self.advanced_panel = ft.Column(
            [
                ft.Text("カスタム分析設定", size=16, weight=ft.FontWeight.BOLD),
                ft.Divider(height=1),
                ft.Row([self.api_key_field, self.api_key_btn]),
                self.api_key_disclaimer,
                ft.Divider(height=1),
                ft.Text("有価証券報告書 (PDF)", weight=ft.FontWeight.BOLD, size=13),
                pdf_select_row,
                ft.Text("分析方式", weight=ft.FontWeight.BOLD, size=13),
                self.method_radio,
                ft.Row([self.model_combo, self.reasoning_combo]),
                ft.Divider(height=1),
                ft.Text("ナレッジベース (RAG)", weight=ft.FontWeight.BOLD, size=13),
                self.vs_combo,
                ft.Row([self.rag_btn, self.use_file_search_cb], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(height=1),
                self.mode_combo,
                self.sys_prompt_field,
                self.clear_btn,
            ],
            width=410,
            spacing=6,
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
        )

    def _build_right_panel(self) -> None:
        """右パネル: レポート出力、ストリーミング、自由入力（詳細時）および保存・停止ボタン群を構築します。"""
        self.response_id_text = ft.Text(
            f"前回レスポンスID: {self.state.config.last_response_id or 'None'}",
            size=12,
            color=ft.Colors.GREY_600,
        )
        self.pdf_badge_text = ft.Text("", size=12, color=ft.Colors.BLUE_800, weight=ft.FontWeight.BOLD)

        # Log view container
        log_container = ft.Container(
            content=self.chat_list,
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=6,
            padding=12,
            expand=True,
            bgcolor=ft.Colors.WHITE,
        )

        self.input_field = ft.TextField(
            label="リクエスト入力 (Shift+Enterで改行)",
            multiline=True,
            min_lines=3,
            max_lines=5,
            expand=True,
            on_submit=self._on_submit_text,
            shift_enter=True,
        )
        self.send_btn = ft.ElevatedButton("送信 🚀", on_click=self._on_submit_button)
        self.stop_btn = ft.ElevatedButton("停止 ⏹️", on_click=self._on_stop_generation, disabled=True)
        self.save_btn = ft.ElevatedButton("レポート保存 💾", on_click=self._on_save_log)

        # 詳細モード用リクエスト行
        self.advanced_input_row = ft.Row(
            [
                self.input_field,
                ft.Column([self.send_btn, self.stop_btn, self.save_btn], alignment=ft.MainAxisAlignment.START),
            ],
            visible=self.state.config.view_mode == ViewMode.ADVANCED,
        )

        # シンプルモード用アクション行（入力不要、停止と保存のみ）
        self.simple_actions_row = ft.Row(
            [
                ft.Text(
                    "※分析結果は下記ボタンから Word / テキストとして保存できます。", size=12, color=ft.Colors.GREY_700
                ),
                ft.Container(expand=True),
                self.stop_btn,
                self.save_btn,
            ],
            visible=self.state.config.view_mode == ViewMode.SIMPLE,
            alignment=ft.MainAxisAlignment.END,
        )

        self.right_column = ft.Column(
            [
                ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Text("レポート (応答履歴)", size=18, weight=ft.FontWeight.BOLD),
                                self.pdf_badge_text,
                            ],
                            spacing=10,
                        ),
                        self.response_id_text,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                log_container,
                self.simple_actions_row,
                self.advanced_input_row,
            ],
            expand=True,
        )

    # --- Mode & PDF Switching Handlers ---

    async def _on_mode_change(self, e: ft.ControlEvent) -> None:
        """AppBarのセグメントボタンによるモード切り替えを処理します。"""
        if not self.mode_segment.selected:
            return
        new_mode = next(iter(self.mode_segment.selected))
        await self.state.set_view_mode(ViewMode(new_mode))

    async def _on_pick_pdf(self, e: ft.ControlEvent) -> None:
        """ファイルピッカーを起動し、有価証券報告書 (PDF) を指定します。"""
        file_picker = ft.FilePicker()
        files = await file_picker.pick_files(
            dialog_title="有価証券報告書 (PDF) を選択",
            allowed_extensions=["pdf"],
            allow_multiple=False,
        )
        if files and files[0].path:
            await self.state.set_active_pdf(files[0].path)

    async def _on_clear_pdf(self, e: ft.ControlEvent) -> None:
        """選択中の有価証券報告書 (PDF) を解除します。"""
        await self.state.set_active_pdf(None)

    async def _on_open_api_key_dialog(self, e: ft.ControlEvent) -> None:
        """シンプルモード向けのAPIキー入力・設定ダイアログを表示します。"""
        key_input = ft.TextField(
            label="OpenAI APIキー",
            password=True,
            can_reveal_password=True,
            value=self.state.config.api_key or "",
            autofocus=True,
            text_size=13,
            width=680,
            on_submit=lambda _: self.page.run_task(save_key),
        )

        def close_dialog(ev: ft.ControlEvent) -> None:
            dlg.open = False
            self.page.update()

        async def save_key() -> None:
            val = key_input.value.strip() if key_input.value else ""
            if not val:
                await self._show_error("入力エラー", "APIキーを入力してください。")
                return
            dlg.open = False
            self.page.update()
            await self.state.update_api_key(val)
            await self._sync_from_state()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("OpenAI APIキーの設定", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text("お持ちの OpenAI APIキー (sk-...) を入力してください。"),
                        key_input,
                        ft.Text(
                            "※APIキーは本PC内（./data）に暗号化保存され、外部送信されません。",
                            size=11,
                            color=ft.Colors.GREY_600,
                        ),
                    ],
                    tight=True,
                    spacing=12,
                ),
                width=720,
            ),
            actions=[
                ft.ElevatedButton("保存", on_click=lambda _: self.page.run_task(save_key)),
                ft.TextButton("キャンセル", on_click=close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    async def _on_preset_click(self, mode_name: str) -> None:
        """シンプルモードのプリセットボタン押下イベントを処理します。"""
        if self.state.is_processing:
            return
        await self.state.handle_preset_submit(mode_name)

    async def _on_analysis_method_change(self, e: ft.ControlEvent) -> None:
        """詳細モードにおける分析方式（直接分析 / RAG）の切り替えを処理します。"""
        selected_method = cast(AnalysisMethod, self.method_radio.value)
        await self.state.set_analysis_method(selected_method)

    async def _on_toggle_file_search(self, e: ft.ControlEvent) -> None:
        """詳細モードにおけるRAGチェックボックス変更を処理します。"""
        is_rag = bool(self.use_file_search_cb.value)
        method = AnalysisMethod.RAG if is_rag else AnalysisMethod.DIRECT
        self.method_radio.value = method
        await self.state.set_analysis_method(method)

    # --- Callbacks from State ---

    async def _sync_from_state(self) -> None:
        """State の最新値を UI ウィジェットに反映します。"""
        is_proc = self.state.is_processing
        current_mode = self.state.config.view_mode

        # 1. AppBar & パネル表示の同期
        self.mode_segment.selected = [current_mode.value]
        if current_mode == ViewMode.SIMPLE:
            self.left_panel_container.content = self.simple_panel
            self.simple_actions_row.visible = True
            self.advanced_input_row.visible = False
        else:
            self.left_panel_container.content = self.advanced_panel
            self.simple_actions_row.visible = False
            self.advanced_input_row.visible = True

        # 2. APIキー状態の同期
        key_val = self.state.config.api_key
        if key_val:
            self.simple_api_icon.icon = ft.Icons.CHECK_CIRCLE
            self.simple_api_icon.color = ft.Colors.GREEN_600
            self.simple_api_label.value = "登録完了"
            self.simple_api_label.color = ft.Colors.GREEN_700
        else:
            self.simple_api_icon.icon = ft.Icons.WARNING
            self.simple_api_icon.color = ft.Colors.ORANGE_800
            self.simple_api_label.value = "APIキー: 未設定 (要登録)"
            self.simple_api_label.color = ft.Colors.RED_800

        self.api_key_field.value = self.state.config.api_key or ""

        # 3. 有価証券報告書 (PDF) 状態の同期
        pdf_path = self.state.config.active_pdf_path
        if pdf_path and Path(pdf_path).exists():
            p = Path(pdf_path)
            size_mb = p.stat().st_size / (1024 * 1024)
            size_str = f"{size_mb:.2f} MB" if size_mb >= 1.0 else f"{p.stat().st_size / 1024:.1f} KB"
            self.simple_file_name.value = f"📄 {p.name}"
            self.simple_file_name.color = ft.Colors.BLUE_900
            self.simple_file_meta.value = f"サイズ: {size_str} | パス: {p.parent.name}/{p.name}"
            self.simple_clear_pdf_btn.visible = True

            self.adv_file_name.value = f"📄 {p.name} ({size_str})"
            self.adv_file_name.color = ft.Colors.BLUE_900
            self.adv_clear_pdf_btn.visible = True

            self.pdf_badge_text.value = f"[対象PDF: {p.name}]"
        else:
            self.simple_file_name.value = "有価証券報告書 (PDF) が未選択です"
            self.simple_file_name.color = ft.Colors.GREY_800
            self.simple_file_meta.value = "※下のボタンを押してPDFファイルを選択してください"
            self.simple_clear_pdf_btn.visible = False

            self.adv_file_name.value = "有報PDF: 未選択"
            self.adv_file_name.color = ft.Colors.GREY_700
            self.adv_clear_pdf_btn.visible = False
            self.pdf_badge_text.value = ""

        # 4. ボタン状態と進行状況
        self.btn_preset_finance.disabled = is_proc
        self.btn_preset_human_capital.disabled = is_proc
        self.btn_preset_entry_sheet.disabled = is_proc

        self.send_btn.disabled = is_proc
        self.stop_btn.disabled = not is_proc
        self.input_field.disabled = is_proc

        self.method_radio.value = self.state.config.analysis_method
        self.use_file_search_cb.value = self.state.config.use_file_search

        self.status_text.value = self.state.status_message
        self.cost_text.value = self.state.cost_info
        self.response_id_text.value = f"前回レスポンスID: {self.state.config.last_response_id or 'None'}"

        self.page.update()

    @staticmethod
    def _create_ai_markdown_style() -> ft.MarkdownStyleSheet:
        """AI返答用のマークダウン文字色・書式スタイルシートを生成します。"""
        fg_color = UI_COLORS["AI_FG"]
        return ft.MarkdownStyleSheet(
            p_text_style=ft.TextStyle(color=fg_color),
            h1_text_style=ft.TextStyle(color=fg_color, weight=ft.FontWeight.BOLD),
            h2_text_style=ft.TextStyle(color=fg_color, weight=ft.FontWeight.BOLD),
            h3_text_style=ft.TextStyle(color=fg_color, weight=ft.FontWeight.BOLD),
            h4_text_style=ft.TextStyle(color=fg_color, weight=ft.FontWeight.BOLD),
            h5_text_style=ft.TextStyle(color=fg_color, weight=ft.FontWeight.BOLD),
            h6_text_style=ft.TextStyle(color=fg_color, weight=ft.FontWeight.BOLD),
            strong_text_style=ft.TextStyle(color=fg_color, weight=ft.FontWeight.BOLD),
            em_text_style=ft.TextStyle(color=fg_color, italic=True),
            list_bullet_text_style=ft.TextStyle(color=fg_color),
            table_body_text_style=ft.TextStyle(color=fg_color),
            table_head_text_style=ft.TextStyle(color=fg_color, weight=ft.FontWeight.BOLD),
            blockquote_text_style=ft.TextStyle(color=fg_color),
        )

    async def _append_log(self, text: str, tag: str) -> None:
        """ログビューにメッセージまたはストリーミングテキストを追加します。"""
        if tag == "user":
            self.chat_list.controls.append(
                ft.Container(
                    content=ft.Text(text, color=UI_COLORS["USER_FG"], selectable=True),
                    bgcolor=UI_COLORS["USER_BG"],
                    border_radius=5,
                    padding=10,
                    margin=ft.margin.symmetric(vertical=5),
                )
            )
            self.current_ai_message = None
        elif tag == "ai":
            if not self.current_ai_message:
                self.current_ai_text = text
                ai_msg = ft.Markdown(
                    value="",
                    selectable=True,
                    extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                    md_style_sheet=self._create_ai_markdown_style(),
                )
                self.current_ai_message = ai_msg
                self.chat_list.controls.append(ai_msg)
            else:
                self.current_ai_text += text

            # 構造化出力 (JSON) から markdown_content を抽出
            raw_content = extract_markdown_content(self.current_ai_text)
            # LLMの出力結果(response_text)から <thought>～</thought> ブロックを削除
            final_report = re.sub(r"<thought>.*?</thought>", "", raw_content, flags=re.DOTALL)
            # ストリーミング中でまだ閉じていない <thought> ブロックも非表示化
            final_report = re.sub(r"<thought>.*", "", final_report, flags=re.DOTALL).strip()
            # 内部引用タグ (fileciteturn...) をクリーンアップ
            final_report = clean_citation_markers(final_report) or ""
            self.current_ai_message.value = final_report

        elif tag == "error":
            self.chat_list.controls.append(ft.Text(text, color=ft.Colors.RED, selectable=True))
            self.current_ai_message = None
        elif tag == "info":
            self.chat_list.controls.append(ft.Text(text, size=11, color=ft.Colors.GREY_600, selectable=True))
            self.current_ai_message = None

        self.page.update()

    async def _clear_log(self) -> None:
        """チャットログの表示をクリアします。"""
        self.chat_list.controls.clear()
        self.current_ai_message = None
        self.page.update()

    async def _show_error(self, title: str, msg: str) -> None:
        """エラーダイアログを表示します。"""
        self._show_dialog(title, msg, is_error=True)

    async def _show_info(self, title: str, msg: str) -> None:
        """情報ダイアログを表示します。"""
        self._show_dialog(title, msg, is_error=False)

    def _show_dialog(self, title: str, msg: str, is_error: bool = False) -> None:
        """ダイアログを表示する共通ルーチン。"""

        def close_dlg(e: ft.ControlEvent) -> None:
            dlg.open = False
            self.page.update()

        async def save_error(e: ft.ControlEvent) -> None:
            file_picker = ft.FilePicker()
            timestamp = datetime.now(UTC).astimezone().strftime("%Y%m%d_%H%M")
            path = await file_picker.save_file(file_name=f"{timestamp}_error_log.txt", allowed_extensions=["txt"])
            if path:
                now_str = datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S")
                Path(path).write_text(f"[{now_str}] {title}\n{msg}", encoding="utf-8")
                self.page.run_task(self._show_info, "保存完了", f"エラーログを保存しました:\n{path}")

        actions: list[ft.Control] = [ft.TextButton("OK", on_click=close_dlg)]

        if is_error:
            actions.insert(
                0,
                ft.TextButton(
                    "開発者にメールで連絡",
                    url="mailto:info@botti.yokohama?subject=SYUKATSU Support エラー報告&body=※先ほど保存したエラーログを添付してください / アプリVer: 最新 / OS: Windows",
                ),
            )
            actions.insert(0, ft.TextButton("エラーログをローカルに保存", on_click=save_error))

        dlg = ft.AlertDialog(
            title=ft.Text(title, color=ft.Colors.RED if is_error else ft.Colors.BLUE),
            content=ft.Text(msg),
            actions=actions,
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    async def _update_vs_combo(self, values: list[str]) -> None:
        """Vector Store のドロップダウン選択肢を更新します。"""
        self.vs_combo.options = [ft.dropdown.Option(val) for val in values]
        current = self.state.config.current_vector_store_id

        found = False
        if current:
            for val in values:
                if current in val:
                    self.vs_combo.value = val
                    found = True
                    break
        if not found and values:
            self.vs_combo.value = None

        self.page.update()

    async def _on_model_change(self, e: ft.ControlEvent) -> None:
        """モデル変更イベントを処理し、推論強度選択肢の動的切替および高額モデル選択時の警告を行います。"""
        selected_model = self.model_combo.value or AppConfigDefaults.DEFAULT_MODEL

        # 推論強度オプションの動的更新（none は luna のみ許可）
        if selected_model == "gpt-6-luna":
            opts = ["max", "xhigh", "high", "medium", "low", "none"]
        else:
            opts = ["max", "xhigh", "high", "medium", "low"]
            if self.reasoning_combo.value == "none":
                self.reasoning_combo.value = "medium"
                self.state.config.reasoning_effort = "medium"

        self.reasoning_combo.options = [ft.dropdown.Option(o) for o in opts]
        if self.reasoning_combo.value not in opts:
            self.reasoning_combo.value = opts[0]
            self.state.config.reasoning_effort = cast(ReasoningEffort, opts[0])

        if selected_model == "gpt-6-astra":

            def confirm_change(_e: ft.ControlEvent) -> None:
                dlg.open = False
                self.page.update()

            def cancel_change(_e: ft.ControlEvent) -> None:
                self.model_combo.value = "gpt-6.1-sol"
                self.reasoning_combo.options = [
                    ft.dropdown.Option(o) for o in ["max", "xhigh", "high", "medium", "low"]
                ]
                if self.reasoning_combo.value == "none":
                    self.reasoning_combo.value = "medium"
                    self.state.config.reasoning_effort = "medium"
                self.state.config.model = "gpt-6.1-sol"
                dlg.open = False
                self.page.update()

            msg = f"{selected_model} は最上位の高度推論モデルであり、gpt-6.1-sol や gpt-6-luna と比較して高額なコストが発生する可能性があります。モデルを変更しますか？"
            actions_list: list[ft.Control] = [
                ft.TextButton("はい", on_click=confirm_change),
                ft.TextButton("いいえ", on_click=cancel_change),
            ]
            dlg = ft.AlertDialog(
                title=ft.Text("確認"),
                content=ft.Text(msg),
                actions=actions_list,
                actions_alignment=ft.MainAxisAlignment.END,
            )
            self.page.overlay.append(dlg)
            dlg.open = True

        await self._sync_to_state()
        self.page.update()

    async def _sync_to_state(self) -> None:
        """UIコンポーネントの入力値を State へ同期します。"""
        self.state.config.model = self.model_combo.value or AppConfigDefaults.DEFAULT_MODEL
        raw_effort = self.reasoning_combo.value or AppConfigDefaults.DEFAULT_REASONING
        valid_efforts = (
            ["max", "xhigh", "high", "medium", "low", "none"]
            if self.state.config.model == "gpt-6-luna"
            else ["max", "xhigh", "high", "medium", "low"]
        )
        if raw_effort in valid_efforts:
            self.state.config.reasoning_effort = cast(ReasoningEffort, raw_effort)
        else:
            self.state.config.reasoning_effort = (
                "medium" if raw_effort == "none" else AppConfigDefaults.DEFAULT_REASONING
            )
        self.state.config.system_prompt_mode = self.mode_combo.value or MODE_FINANCIAL
        self.state.config.use_file_search = self.use_file_search_cb.value or False
        self.state.config.current_vector_store_id = self.vs_combo.value
        self.state.save_config()

    async def _on_register_key(self, e: ft.ControlEvent) -> None:
        """APIキー登録ボタンイベントを処理します。"""
        await self.state.update_api_key(self.api_key_field.value.strip())

    async def _on_prompt_mode_select(self, e: ft.ControlEvent) -> None:
        """プロンプトモード選択イベントを処理します。"""
        mode = self.mode_combo.value or ""
        self.sys_prompt_field.value = self.state.get_system_prompt(mode)
        await self._sync_to_state()
        self.page.update()

    async def _on_clear_context(self, e: ft.ControlEvent) -> None:
        """コンテキスト消去確認モーダルを表示します。"""

        def confirm_clear(ev: ft.ControlEvent) -> None:
            self.page.run_task(self.state.clear_context)
            dlg.open = False
            self.page.update()

        def cancel_clear(ev: ft.ControlEvent) -> None:
            dlg.open = False
            self.page.update()

        actions_list: list[ft.Control] = [
            ft.TextButton("はい", on_click=confirm_clear),
            ft.TextButton("いいえ", on_click=cancel_clear),
        ]
        dlg = ft.AlertDialog(
            title=ft.Text("確認"),
            content=ft.Text("セッションをリセットしますか？"),
            actions=actions_list,
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    async def _on_save_log(self, e: ft.ControlEvent) -> None:
        """レポートログ保存ダイアログを開き、Word (.docx) またはテキスト (.txt) として出力します。"""
        text_content = ""
        for control in self.chat_list.controls:
            if hasattr(control, "content") and hasattr(control.content, "value"):
                text_content += str(control.content.value) + "\n\n"
            elif hasattr(control, "value"):
                text_content += str(control.value) + "\n\n"

        if not text_content.strip():
            await self._show_info("通知", "保存するレポート内容がありません。")
            return

        def close_format_dlg(ev: ft.ControlEvent) -> None:
            format_dlg.open = False
            self.page.update()

        async def save_as_format(file_type: str) -> None:
            format_dlg.open = False
            self.page.update()

            timestamp = datetime.now(UTC).astimezone().strftime("%Y%m%d_%H%M%S")
            file_picker = ft.FilePicker()
            ext = "docx" if file_type == "docx" else "txt"
            path = await file_picker.save_file(
                dialog_title=f"レポートの保存先を選択 ({ext.upper()})",
                file_name=f"report_log_{timestamp}.{ext}",
                allowed_extensions=[ext],
            )
            if not path:
                return

            try:
                cleaned_export = clean_citation_markers(text_content.strip()) or ""
                if file_type == "docx":
                    export_markdown_to_docx(cleaned_export, path)
                    await self._show_info("保存完了", f"Wordレポートを保存しました:\n{path}")
                else:
                    Path(path).write_text(cleaned_export, encoding="utf-8")
                    await self._show_info("保存完了", f"テキストレポートを保存しました:\n{path}")
            except Exception as ex:
                await self._show_error("保存エラー", f"ファイルの保存に失敗しました:\n{ex}")

        format_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("保存形式の選択", weight=ft.FontWeight.BOLD),
            content=ft.Text(
                "レポートの出力形式を選択してください。\nWord形式（.docx）またはテキスト形式（.txt）で保存できます。"
            ),
            actions=[
                ft.ElevatedButton(
                    "📄 Word (.docx)",
                    on_click=lambda _: self.page.run_task(save_as_format, "docx"),
                ),
                ft.ElevatedButton(
                    "📝 テキスト (.txt)",
                    on_click=lambda _: self.page.run_task(save_as_format, "txt"),
                ),
                ft.TextButton("キャンセル", on_click=close_format_dlg),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.overlay.append(format_dlg)
        format_dlg.open = True
        self.page.update()

    async def _start_generation(self) -> None:
        """分析リクエストを開始し、非同期タスクとして実行します。"""
        if self.state.is_processing:
            return

        await self._sync_to_state()

        user_input = self.input_field.value.strip()
        system_prompt = self.sys_prompt_field.value.strip()

        if user_input:
            self.input_field.value = ""
            self.page.update()
            # Flet run_task is used to not block the current UI event
            self.page.run_task(self.state.handle_submit, user_input, system_prompt)

    async def _on_submit_text(self, e: ft.ControlEvent) -> None:
        """入力欄での Shift+Enter / Enter 送信イベントを処理します。"""
        await self._start_generation()

    async def _on_submit_button(self, e: ft.ControlEvent) -> None:
        """送信ボタン押下イベントを処理します。"""
        await self._start_generation()

    async def _on_stop_generation(self, e: ft.ControlEvent) -> None:
        """停止ボタン押下イベントを処理します。"""
        await self.state.cancel_generation()

    async def _on_open_rag_manager(self, e: ft.ControlEvent) -> None:
        """ナレッジベース管理画面ダイアログを開きます。"""
        from src.rag_ui import show_rag_manager

        await self.state.update_api_key(self.api_key_field.value.strip(), silent=True)
        if not self.state.config.api_key or not self.state.client or not self.state.rag_usecase:
            await self._show_error("エラー", "API Keyを登録してください。")
            return

        await show_rag_manager(self.page, self.state.rag_usecase, self.state.refresh_vector_stores)
