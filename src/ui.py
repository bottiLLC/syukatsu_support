import flet as ft
import datetime
from typing import List
from src.state import AppState
from src.styles import UI_COLORS

class SyukatsuSupportApp:
    def __init__(self, page: ft.Page, state: AppState):
        self.page = page
        self.state = state
        self.page.title = "SYUKATSU Support - 合同会社ぼっち (v2.1.0)"
        self.page.padding = 20
        self.page.theme_mode = ft.ThemeMode.LIGHT
        
        # Set default window size to fit layout without scrolling
        self.page.window.width = 1250
        self.page.window.height = 850

        # State Binding Setup
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
        # Initialize UI with current state values
        self.page.run_task(self._sync_from_state)

    def _build_ui(self):
        # --- Left Panel ---
        self.api_key_field = ft.TextField(
            label="OpenAI APIキー", password=True, can_reveal_password=True, 
            value=self.state.config.api_key, expand=True, dense=True
        )
        self.api_key_btn = ft.ElevatedButton("登録", on_click=self._on_register_key)
        
        self.model_combo = ft.Dropdown(
            label="モデル", options=[ft.dropdown.Option("gpt-5.4-pro"), ft.dropdown.Option("gpt-5.4")],
            value=self.state.config.model, expand=True, dense=True
        )
        self.reasoning_combo = ft.Dropdown(
            label="推論強度", options=[ft.dropdown.Option(o) for o in ["none", "minimal", "low", "medium", "high", "xhigh"]],
            value=self.state.config.reasoning_effort, expand=True, dense=True
        )
        
        self.vs_combo = ft.Dropdown(
            label="Vector Store", options=[], value=self.state.config.current_vector_store_id, dense=True, width=330
        )
        self.use_file_search_cb = ft.Checkbox(label="ファイル検索(RAG)を使用", value=self.state.config.use_file_search)
        self.rag_btn = ft.ElevatedButton("🛠️ ナレッジベース管理", on_click=self._on_open_rag_manager)

        # --- Prompt Mode Selection (Dynamically loaded from JSON) ---
        prompt_options = [ft.dropdown.Option(m) for m in self.state.available_prompt_modes]
        valid_val = self.state.config.system_prompt_mode if self.state.config.system_prompt_mode in self.state.available_prompt_modes else None
        
        self.mode_combo = ft.Dropdown(
            label="分析モード選択", options=prompt_options,
            value=valid_val, dense=True, on_select=self._on_prompt_mode_select, width=330
        )
        
        self.sys_prompt_field = ft.TextField(
            label="システムプロンプト", multiline=True, width=330, height=200,
            value=self.state.get_system_prompt(self.state.config.system_prompt_mode), text_size=12
        )
        self.clear_btn = ft.ElevatedButton("🧹 コンテキスト消去", on_click=self._on_clear_context)

        left_column = ft.Column([
            ft.Text("企業分析設定", size=18, weight="bold"),
            ft.Divider(),
            ft.Row([self.api_key_field, self.api_key_btn]),
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
        ], width=350, scroll=ft.ScrollMode.ADAPTIVE)

        # --- Right Panel ---
        self.response_id_text = ft.Text(f"前回レスポンスID: {self.state.config.last_response_id or 'None'}", size=12, color=ft.Colors.GREY_600)
        
        # Log view container
        log_container = ft.Container(
            content=self.chat_list,
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=5,
            padding=10,
            expand=True,
            bgcolor=ft.Colors.WHITE
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

        # Main Layout
        main_row = ft.Row([left_column, ft.VerticalDivider(), right_column], expand=True)

        # Status Bar
        self.status_text = ft.Text(self.state.status_message, size=12)
        self.cost_text = ft.Text(self.state.cost_info, size=12)
        bottom_bar = ft.Container(
            content=ft.Row([self.status_text, self.cost_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=5,
            bgcolor=ft.Colors.GREY_200,
            border_radius=5
        )

        self.page.add(
            ft.Column([
                main_row,
                bottom_bar
            ], expand=True)
        )

    # --- Callbacks from State ---
    async def _sync_from_state(self):
        self.status_text.value = self.state.status_message
        self.cost_text.value = self.state.cost_info
        self.response_id_text.value = f"前回レスポンスID: {self.state.config.last_response_id or 'None'}"
        
        is_proc = self.state.is_processing
        self.send_btn.disabled = is_proc
        self.stop_btn.disabled = not is_proc
        self.input_field.disabled = is_proc
        
        self.page.update()

    async def _append_log(self, text: str, tag: str):
        if tag == "user":
            self.chat_list.controls.append(
                ft.Container(
                    content=ft.Text(text, color=ft.Colors.WHITE, selectable=True),
                    bgcolor=UI_COLORS["USER_BG"],
                    border_radius=5,
                    padding=10,
                    margin=ft.margin.symmetric(vertical=5)
                )
            )
            self.current_ai_message = None
        elif tag == "ai":
            if not self.current_ai_message:
                self.current_ai_text = text
                self.current_ai_message = ft.Text(self.current_ai_text, color=UI_COLORS["AI_FG"], selectable=True)
                self.chat_list.controls.append(self.current_ai_message)
            else:
                self.current_ai_text += text
                self.current_ai_message.value = self.current_ai_text
        elif tag == "error":
            self.chat_list.controls.append(ft.Text(text, color=ft.Colors.RED, selectable=True))
            self.current_ai_message = None
        elif tag == "info":
            self.chat_list.controls.append(ft.Text(text, size=11, color=ft.Colors.GREY_600, selectable=True))
            self.current_ai_message = None
            
        self.page.update()

    async def _clear_log(self):
        self.chat_list.controls.clear()
        self.current_ai_message = None
        self.page.update()

    async def _show_error(self, title: str, msg: str):
        self._show_dialog(title, msg, is_error=True)

    async def _show_info(self, title: str, msg: str):
        self._show_dialog(title, msg, is_error=False)

    def _show_dialog(self, title: str, msg: str, is_error: bool = False):
        def close_dlg(e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(title, color=ft.Colors.RED if is_error else ft.Colors.BLUE),
            content=ft.Text(msg),
            actions=[ft.TextButton("OK", on_click=close_dlg)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    async def _update_vs_combo(self, values: List[str]):
        self.vs_combo.options = [ft.dropdown.Option(val) for val in values]
        current = self.state.config.current_vector_store_id
        
        # Preserve selection if it still exists
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

    # --- User Interactions ---
    async def _sync_to_state(self):
        self.state.config.model = self.model_combo.value or "gpt-5.4"
        self.state.config.reasoning_effort = self.reasoning_combo.value or "medium"
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
        def confirm_clear(e):
            self.page.run_task(self.state.clear_context)
            dlg.open = False
            self.page.update()
            
        def cancel_clear(e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("確認"),
            content=ft.Text("セッションをリセットしますか？"),
            actions=[
                ft.TextButton("はい", on_click=confirm_clear),
                ft.TextButton("いいえ", on_click=cancel_clear),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    async def _on_save_log(self, e):
        """「保存 💾」ボタンが押されたときにダイアログを開く処理"""
        # Instantiate FilePicker dynamically (do NOT append to overlay)
        file_picker = ft.FilePicker()
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        path = await file_picker.save_file(
            file_name=f"{timestamp}_分析レポート.txt", 
            allowed_extensions=["txt"]
        )
        
        if path:
            text_content = ""
            for control in self.chat_list.controls:
                if hasattr(control, "content") and hasattr(control.content, "value"):
                    text_content += control.content.value + "\n\n"
                elif hasattr(control, "value"):
                    text_content += control.value + "\n\n"
                    
            with open(path, "w", encoding="utf-8") as f:
                f.write(text_content.strip())
            self.page.run_task(self._show_info, "保存", f"保存しました: {path}")

    async def _start_generation(self):
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

    async def _on_submit_text(self, e):
        await self._start_generation()

    async def _on_submit_button(self, e):
        await self._start_generation()

    async def _on_stop_generation(self, e):
        await self.state.cancel_generation()

    async def _on_open_rag_manager(self, e):
        from src.rag_ui import show_rag_manager
        
        await self.state.update_api_key(self.api_key_field.value.strip(), silent=True)
        if not self.state.config.api_key or not getattr(self.state, "client", None) or not getattr(self.state, "rag_usecase", None):
            await self._show_error("エラー", "API Keyを登録してください。")
            return
            
        # Call RAG Manager
        await show_rag_manager(self.page, self.state.rag_usecase, self.state.refresh_vector_stores)
