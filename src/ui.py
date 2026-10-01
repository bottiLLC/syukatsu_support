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
およびバックアップ操作を含むユーザー操作ハンドラを提供します。
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import flet as ft

from backup_manager import get_backup_dir, run_backup, set_backup_dir
from src.core.utils import clean_citation_markers
from src.models import ReasoningEffort
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
        self.page.padding = 20
        self.page.theme_mode = ft.ThemeMode.LIGHT

        # Set default window size to fit layout without scrolling
        self.page.window.width = 1350
        self.page.window.height = 980

        # State Binding Setup
        self.state.on_state_change = self._sync_from_state
        self.state.on_text_delta = self._append_log
        self.state.on_clear_text = self._clear_log
        self.state.on_error = self._show_error
        self.state.on_info = self._show_info
        self.state.on_vs_updated = self._update_vs_combo

        self.chat_list = ft.ListView(expand=True, spacing=10, auto_scroll=True)
        self.current_ai_message: ft.Text | None = None
        self.current_ai_text: str = ""

        self._build_ui()
        # Initialize UI with current state values
        self.page.run_task(self._sync_from_state)

    def _build_ui(self) -> None:
        """メイン画面の各コンポーネントをレイアウトに配置します。"""
        # --- Left Panel ---
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
            "※入力されたAPIキーは本PC内（./data）にのみ暗号化保存され、\n 外部へ送信・保持されることはありません。",
            color=ft.Colors.RED_700,
            size=10.5,
            weight=ft.FontWeight.BOLD,
            no_wrap=False,
        )

        self.model_combo = ft.Dropdown(
            label="モデル",
            options=[
                ft.dropdown.Option("gpt-5.6-terra"),
                ft.dropdown.Option("gpt-5.6-sol"),
                ft.dropdown.Option("gpt-5.6-luna"),
            ],
            value=self.state.config.model,
            expand=True,
            dense=True,
            on_select=self._on_model_change,
        )
        self.reasoning_combo = ft.Dropdown(
            label="推論強度",
            options=[ft.dropdown.Option(o) for o in ["none", "minimal", "low", "medium", "high", "xhigh"]],
            value=self.state.config.reasoning_effort,
            expand=True,
            dense=True,
        )

        self.vs_combo = ft.Dropdown(
            label="Vector Store",
            options=[],
            value=self.state.config.current_vector_store_id,
            dense=True,
            width=390,
        )
        self.use_file_search_cb = ft.Checkbox(label="ファイル検索(RAG)を使用", value=self.state.config.use_file_search)
        self.rag_btn = ft.ElevatedButton("🛠️ ナレッジベース管理", on_click=self._on_open_rag_manager)

        # --- Backup & Data Protection (Python-backup-script compliant) ---
        self.backup_dir_field = ft.TextField(
            label="保存先フォルダ",
            value=str(get_backup_dir()),
            dense=True,
            width=390,
        )
        self.update_backup_dir_btn = ft.ElevatedButton(
            "保存先パスを更新",
            on_click=self._on_update_backup_dir,
            width=390,
        )
        self.run_backup_btn = ft.ElevatedButton(
            "今すぐバックアップを実行",
            on_click=self._on_run_backup,
            width=390,
        )
        self.backup_status_caption = ft.Text("", size=11, color=ft.Colors.GREY_700)

        # --- Prompt Mode Selection (Dynamically loaded from JSON) ---
        prompt_options = [ft.dropdown.Option(m) for m in self.state.available_prompt_modes]
        valid_val = (
            self.state.config.system_prompt_mode
            if self.state.config.system_prompt_mode in self.state.available_prompt_modes
            else None
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
            min_lines=10,
            max_lines=14,
            value=self.state.get_system_prompt(self.state.config.system_prompt_mode),
            text_size=12,
        )
        self.clear_btn = ft.ElevatedButton("🧹 コンテキスト消去", on_click=self._on_clear_context)

        left_column = ft.Column(
            [
                ft.Text("企業分析設定", size=18, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Row([self.api_key_field, self.api_key_btn]),
                self.api_key_disclaimer,
                ft.Row([self.model_combo, self.reasoning_combo]),
                ft.Divider(),
                ft.Text("ナレッジベース (RAG)", weight=ft.FontWeight.BOLD),
                self.vs_combo,
                self.rag_btn,
                self.use_file_search_cb,
                ft.Divider(),
                ft.Text("データ保護・バックアップ", weight=ft.FontWeight.BOLD),
                self.backup_dir_field,
                self.update_backup_dir_btn,
                self.run_backup_btn,
                self.backup_status_caption,
                ft.Divider(),
                self.mode_combo,
                self.sys_prompt_field,
                self.clear_btn,
            ],
            width=410,
            spacing=6,
            scroll=ft.ScrollMode.ADAPTIVE,
        )

        # --- Right Panel ---
        self.response_id_text = ft.Text(
            f"前回レスポンスID: {self.state.config.last_response_id or 'None'}",
            size=12,
            color=ft.Colors.GREY_600,
        )

        # Log view container
        log_container = ft.Container(
            content=self.chat_list,
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=5,
            padding=10,
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
        self.save_btn = ft.ElevatedButton("保存 💾", on_click=self._on_save_log)

        input_row = ft.Row(
            [
                self.input_field,
                ft.Column([self.send_btn, self.stop_btn, self.save_btn], alignment=ft.MainAxisAlignment.START),
            ]
        )

        right_column = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("レポート (応答履歴)", size=18, weight=ft.FontWeight.BOLD),
                        self.response_id_text,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                log_container,
                input_row,
            ],
            expand=True,
        )

        # Main Layout
        main_row = ft.Row(
            [left_column, ft.VerticalDivider(), right_column],
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

        # Status Bar
        self.status_text = ft.Text(self.state.status_message, size=12)
        self.cost_text = ft.Text(self.state.cost_info, size=12)
        bottom_bar = ft.Container(
            content=ft.Row([self.status_text, self.cost_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=5,
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

    # --- Callbacks from State ---

    async def _sync_from_state(self) -> None:
        """State の最新値を UI ウィジェットに反映します。"""
        self.status_text.value = self.state.status_message
        self.cost_text.value = self.state.cost_info
        self.response_id_text.value = f"前回レスポンスID: {self.state.config.last_response_id or 'None'}"

        is_proc = self.state.is_processing
        self.send_btn.disabled = is_proc
        self.stop_btn.disabled = not is_proc
        self.input_field.disabled = is_proc

        self.page.update()

    async def _append_log(self, text: str, tag: str) -> None:
        """ログビューにメッセージまたはストリーミングテキストを追加します。"""
        if tag == "user":
            self.chat_list.controls.append(
                ft.Container(
                    content=ft.Text(text, color=ft.Colors.WHITE, selectable=True),
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
                ai_msg = ft.Text("", color=UI_COLORS["AI_FG"], selectable=True)
                self.current_ai_message = ai_msg
                self.chat_list.controls.append(ai_msg)
            else:
                self.current_ai_text += text

            # LLMの出力結果(response_text)から <thought>～</thought> ブロックを削除
            final_report = re.sub(r"<thought>.*?</thought>", "", self.current_ai_text, flags=re.DOTALL)
            # ストリーミング中でまだ閉じていない <thought> ブロックも非表示化
            final_report = re.sub(r"<thought>.*", "", final_report, flags=re.DOTALL).strip()
            # 内部引用タグ (fileciteturn...) をクリーンアップ
            final_report = clean_citation_markers(final_report)
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

    # --- Backup UI Event Handlers ---

    async def _on_update_backup_dir(self, e: ft.ControlEvent) -> None:
        """バックアップ保存先フォルダの更新イベントを処理します。"""
        target = self.backup_dir_field.value or ""
        res = set_backup_dir(target)
        if res["success"]:
            await self._show_info("バックアップ設定", str(res["message"]))
        else:
            await self._show_error("バックアップ設定エラー", str(res["message"]))

    async def _on_run_backup(self, e: ft.ControlEvent) -> None:
        """今すぐバックアップ実行イベントを処理します。"""
        self.backup_status_caption.value = "圧縮・整合性検証中..."
        self.page.update()

        res = run_backup(app_name="syukatsu_support")
        if res["success"]:
            self.backup_status_caption.value = f"完了日時: {res['timestamp']}\n保存先: {res['destination']}"
            await self._show_info("バックアップ完了", str(res["message"]))
        else:
            self.backup_status_caption.value = ""
            await self._show_error("バックアップエラー", str(res["message"]))
        self.page.update()

    # --- User Interactions ---

    async def _on_model_change(self, e: ft.ControlEvent) -> None:
        """モデル変更イベントを処理し、高推論モデル選択時は警告モーダルを表示します。"""
        selected_model = self.model_combo.value
        if selected_model == "gpt-5.6-sol":

            def confirm_change(_e: ft.ControlEvent) -> None:
                dlg.open = False
                self.page.update()

            def cancel_change(_e: ft.ControlEvent) -> None:
                self.model_combo.value = "gpt-5.6-terra"
                dlg.open = False
                self.page.update()

            msg = f"{selected_model} は高度な推論を行うモデルですが、gpt-5.6-terraと比較して高額なコストが発生する可能性があります。モデルを変更しますか？"
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
            self.page.update()

    async def _sync_to_state(self) -> None:
        """UIコンポーネントの入力値を State へ同期します。"""
        self.state.config.model = self.model_combo.value or "gpt-5.6-terra"
        raw_effort = self.reasoning_combo.value or "high"
        if raw_effort in ["none", "minimal", "low", "medium", "high", "xhigh"]:
            self.state.config.reasoning_effort = cast(ReasoningEffort, raw_effort)
        else:
            self.state.config.reasoning_effort = "high"
        self.state.config.system_prompt_mode = self.mode_combo.value or "有価証券報告書 -財務分析-"
        self.state.config.use_file_search = self.use_file_search_cb.value or False
        self.state.config.current_vector_store_id = self.vs_combo.value

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
        """レポートログ保存ダイアログを開き、テキストファイルとして出力します。"""
        text_content = ""
        for control in self.chat_list.controls:
            if hasattr(control, "content") and hasattr(control.content, "value"):
                text_content += str(control.content.value) + "\n\n"
            elif hasattr(control, "value"):
                text_content += str(control.value) + "\n\n"

        if not text_content.strip():
            await self._show_info("通知", "保存するレポート内容がありません。")
            return

        timestamp = datetime.now(UTC).astimezone().strftime("%Y%m%d_%H%M%S")
        file_picker = ft.FilePicker()
        path = await file_picker.save_file(
            dialog_title="レポートの保存先を選択",
            file_name=f"report_log_{timestamp}.txt",
            allowed_extensions=["txt"],
        )

        if path:
            try:
                cleaned_export = clean_citation_markers(text_content.strip())
                Path(path).write_text(cleaned_export, encoding="utf-8")
                await self._show_info("保存完了", f"レポートを保存しました:\n{path}")
            except OSError as ex:
                await self._show_error("保存エラー", f"ファイルの保存に失敗しました:\n{ex}")

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
