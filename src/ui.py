"""
Tkinter UI コンポーネント。

ビジネスロジックを持たず、レイアウトの定義と AppState とのバインド（同期）のみを行います。
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk, filedialog
from typing import Optional, List

from src.state import AppState
from src.core.prompts import SYSTEM_PROMPTS
from src.styles import UI_COLORS, UI_FONTS, WINDOW_SIZE


class SyukatsuSupportApp(tk.Tk):
    """
    Tkinterのメインウィンドウ。AppStateを監視し、イベントをルーティングします。
    """
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.title("SYUKATSU Support - 合同会社ぼっち (v1.10)")
        self.geometry(WINDOW_SIZE)

        # UI State Variables
        self.api_key_var = tk.StringVar(value=self.state.config.api_key or "")
        self.model_var = tk.StringVar(value=self.state.config.model)
        self.reasoning_var = tk.StringVar(value=self.state.config.reasoning_effort)
        self.prompt_mode_var = tk.StringVar(value=self.state.config.system_prompt_mode)
        self.status_var = tk.StringVar(value=self.state.status_message)
        self.cost_info_var = tk.StringVar(value=self.state.cost_info)
        self.response_id_var = tk.StringVar(value=self.state.config.last_response_id or "None")

        self.vs_id_var = tk.StringVar(value=self.state.config.current_vector_store_id or "")
        self.use_file_search_var = tk.BooleanVar(value=self.state.config.use_file_search)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._setup_ui()
        self._bind_state_callbacks()

        # Update loop
        self.after(100, self._process_events)

    def _setup_ui(self):
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        self._setup_styles()

        paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=6, sashrelief=tk.RAISED)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        paned_window.add(self._create_left_panel(paned_window), width=380, stretch="never")
        paned_window.add(self._create_right_panel(paned_window), stretch="always")

        self._create_status_bar()

        # 初期モードの適用
        mode = self.prompt_mode_var.get()
        self._sys_prompt_view.insert("1.0", self.state.get_system_prompt(mode))

    def _setup_styles(self):
        style = ttk.Style()
        style.configure("Bold.TLabel", font=UI_FONTS["BOLD"])
        style.configure("Title.TLabel", font=UI_FONTS["TITLE"], foreground=UI_COLORS["TITLE"])

    def _create_left_panel(self, parent) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text=" 企業分析設定", padding=10)

        # API Key
        ttk.Label(frame, text="OpenAI APIキー:", style="Bold.TLabel").pack(anchor="w")
        key_frame = ttk.Frame(frame)
        key_frame.pack(fill="x")
        self._entry_key = ttk.Entry(key_frame, textvariable=self.api_key_var, show="*")
        self._entry_key.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(key_frame, text="登録", command=self._on_register_key).pack(side="right")
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

        # Model Config
        ttk.Label(frame, text="モデル設定:", style="Bold.TLabel").pack(anchor="w")
        grid = ttk.Frame(frame)
        grid.pack(fill="x", pady=5)
        
        ttk.Label(grid, text="モデル:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            grid, textvariable=self.model_var, values=["gpt-5.2-pro", "gpt-5.2", "gpt-5-mini"], state="readonly"
        ).grid(row=0, column=1, sticky="ew", padx=5)

        ttk.Label(grid, text="推論強度:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Combobox(
            grid, textvariable=self.reasoning_var, values=["none", "minimal", "low", "medium", "high", "xhigh"], state="readonly"
        ).grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

        # RAG Section
        ttk.Label(frame, text="ナレッジベース (RAG):", style="Bold.TLabel").pack(anchor="w")
        rag_frame = ttk.Frame(frame)
        rag_frame.pack(fill="x", pady=5)

        self._vs_combo = ttk.Combobox(rag_frame, textvariable=self.vs_id_var, state="readonly")
        self._vs_combo.pack(fill="x", pady=(0, 5))
        ttk.Button(rag_frame, text="🛠️ ナレッジベース管理", command=self._on_open_rag_manager).pack(fill="x")
        ttk.Checkbutton(rag_frame, text="ファイル検索(RAG)を使用", variable=self.use_file_search_var).pack(anchor="w", pady=(5, 0))

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

        # Prompt Mode
        ttk.Label(frame, text="モード選択:", style="Bold.TLabel").pack(anchor="w")
        cb_prompt = ttk.Combobox(frame, textvariable=self.prompt_mode_var, values=list(SYSTEM_PROMPTS.keys()), state="readonly")
        cb_prompt.pack(fill="x", pady=(2, 5))
        cb_prompt.bind("<<ComboboxSelected>>", self._on_prompt_mode_select)

        ttk.Label(frame, text="システムプロンプト:", style="Bold.TLabel").pack(anchor="w", pady=(5, 0))
        self._sys_prompt_view = scrolledtext.ScrolledText(frame, height=10, width=30, font=UI_FONTS["MONO"], wrap=tk.WORD)
        self._sys_prompt_view.pack(fill="both", expand=True, pady=5)

        ttk.Button(frame, text="🧹 コンテキスト消去 (新規セッション)", command=self._on_clear_context).pack(fill="x", pady=10)

        return frame

    def _create_right_panel(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent)

        # Info Header
        info_frame = ttk.Frame(frame)
        info_frame.pack(fill="x", pady=5, padx=5)
        ttk.Label(info_frame, text="レポート (応答履歴)", style="Title.TLabel").pack(side="left")

        id_display = ttk.Frame(info_frame)
        id_display.pack(side="right")
        ttk.Label(id_display, textvariable=self.response_id_var, font=UI_FONTS["SMALL_BOLD"], foreground=UI_COLORS["ID_FG"]).pack(side="right")
        ttk.Label(id_display, text="前回レスポンスID: ", font=UI_FONTS["SMALL_MONO"], foreground=UI_COLORS["LABEL_FG"]).pack(side="right")

        # Log
        self._log_view = scrolledtext.ScrolledText(frame, state="disabled", font=UI_FONTS["NORMAL"], wrap=tk.WORD)
        self._log_view.pack(fill="both", expand=True, padx=5)
        self._configure_log_tags()

        # Input
        input_frame = ttk.LabelFrame(frame, text=" リクエスト入力 (Ctrl+Enterで送信) ", padding=5)
        input_frame.pack(fill="x", padx=5, pady=5)

        self._input_view = scrolledtext.ScrolledText(input_frame, height=4, font=UI_FONTS["NORMAL"], undo=True)
        self._input_view.pack(fill="x", side="left", expand=True)
        self._input_view.bind("<Control-Return>", lambda e: self._on_start_generation())
        self._input_view.bind("<Command-Return>", lambda e: self._on_start_generation())

        # Buttons
        btn_frame = ttk.Frame(input_frame)
        btn_frame.pack(side="right", fill="y", padx=(5, 0))

        self._send_btn = ttk.Button(btn_frame, text="分析開始 🚀", command=self._on_start_generation)
        self._send_btn.pack(fill="x", pady=(0, 2))
        
        self._stop_btn = ttk.Button(btn_frame, text="停止 ⏹️", command=self._on_stop_generation, state="disabled")
        self._stop_btn.pack(fill="x", pady=(2, 2))
        
        ttk.Button(btn_frame, text="保存 💾", command=self._on_save_log).pack(fill="x", pady=(2, 0))

        return frame

    def _create_status_bar(self):
        bar = ttk.Frame(self, relief=tk.SUNKEN)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(bar, textvariable=self.status_var, font=UI_FONTS["STATUS"]).pack(side=tk.LEFT, padx=5)
        ttk.Label(bar, textvariable=self.cost_info_var, font=UI_FONTS["STATUS_MONO"]).pack(side=tk.RIGHT, padx=5)

    def _configure_log_tags(self):
        self._log_view.tag_config("user", foreground=UI_COLORS["USER_FG"], background=UI_COLORS["USER_BG"], font=UI_FONTS["NORMAL_BOLD"], lmargin1=10, lmargin2=10, rmargin=10)
        self._log_view.tag_config("ai", foreground=UI_COLORS["AI_FG"], lmargin1=10, lmargin2=10, rmargin=10)
        self._log_view.tag_config("error", foreground=UI_COLORS["ERROR_FG"])

    # --- Bindings to AppState ---
    def _bind_state_callbacks(self):
        self.state.on_state_change = self._sync_from_state
        self.state.on_text_delta = self._append_log
        self.state.on_error = lambda title, msg: messagebox.showerror(title, msg)
        self.state.on_info = lambda title, msg: messagebox.showinfo(title, msg)
        self.state.on_clear_text = self._clear_log
        self.state.on_vs_updated = self._update_vs_combo

    def _sync_from_state(self):
        # Sync simple scalar variables
        self.status_var.set(self.state.status_message)
        self.cost_info_var.set(self.state.cost_info)
        self.response_id_var.set(self.state.config.last_response_id or "None")
        
        # UI controls
        if self.state.is_processing:
            self._send_btn.config(state="disabled")
            self._stop_btn.config(state="normal")
        else:
            self._send_btn.config(state="normal")
            self._stop_btn.config(state="disabled")

    def _sync_to_state(self):
        # UI -> AppState config write-back
        self.state.config.model = self.model_var.get()
        self.state.config.reasoning_effort = self.reasoning_var.get()
        self.state.config.system_prompt_mode = self.prompt_mode_var.get()
        self.state.config.use_file_search = self.use_file_search_var.get()
        self.state.config.current_vector_store_id = self.vs_id_var.get()

    def _append_log(self, text: str, tag: str):
        self._log_view.config(state="normal")
        self._log_view.insert(tk.END, text, tag)
        self._log_view.see(tk.END)
        self._log_view.config(state="disabled")

    def _clear_log(self):
        self._log_view.config(state="normal")
        self._log_view.delete("1.0", tk.END)
        self._log_view.config(state="disabled")

    def _update_vs_combo(self, values: List[str]):
        self._vs_combo["values"] = values
        current = self.vs_id_var.get()
        for i, val in enumerate(values):
            if current in val:
                self._vs_combo.current(i)
                return

    def _process_events(self):
        self.state.process_queue_events()
        self.after(50, self._process_events)

    # --- User Interactions ---
    def _on_register_key(self):
        self.state.update_api_key(self.api_key_var.get().strip())

    def _on_prompt_mode_select(self, event=None):
        mode = self.prompt_mode_var.get()
        self._sys_prompt_view.delete("1.0", tk.END)
        self._sys_prompt_view.insert("1.0", self.state.get_system_prompt(mode))
        self._sync_to_state()

    def _on_clear_context(self):
        if messagebox.askyesno("確認", "セッションをリセットしますか？"):
            self.state.clear_context()

    def _on_save_log(self):
        text = self._log_view.get("1.0", tk.END).strip()
        if not text:
            return
        path_str = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt")],
            initialfile="分析レポート.txt"
        )
        if path_str:
            with open(path_str, "w", encoding="utf-8") as f:
                f.write(text)
            messagebox.showinfo("保存", "保存しました。")

    def _on_start_generation(self) -> str:
        if self.state.is_processing:
            return "break"
        
        self._sync_to_state()
        
        user_input = self._input_view.get("1.0", tk.END).strip()
        system_prompt = self._sys_prompt_view.get("1.0", tk.END).strip()
        
        if user_input:
            self._input_view.delete("1.0", tk.END)
            self.state.handle_submit(user_input, system_prompt)
            
        return "break"

    def _on_stop_generation(self):
        self.state.cancel_generation()

    def _on_open_rag_manager(self):
        from src.rag_ui import RAGManagementWindow
        
        self.state.update_api_key(self.api_key_var.get().strip())
        if not self.state.config.api_key or not self.state.client:
            messagebox.showwarning("エラー", "API Keyを登録してください。")
            return
            
        window = RAGManagementWindow(self, self.state.client)
        self.wait_window(window)
        self.state.refresh_vector_stores()

    def _on_close(self):
        self._sync_to_state()
        self.state.save_config()
        if self.state.is_processing:
            self.state.cancel_generation()
        self.destroy()
