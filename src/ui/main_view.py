import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any, Callable, List, Optional

from src.config.app_config import AppConfig, UserConfig
from src.core.pricing import PRICING_TABLE
from src.core.prompts import SYSTEM_PROMPTS
from src.ui.styles import UI_COLORS, UI_FONTS, WINDOW_SIZE


class MainView(tk.Tk):
    """
    Main GUI view component.
    """

    def __init__(self, initial_config: UserConfig) -> None:
        super().__init__()
        self.title(f"SYUKATSU Support ({AppConfig.APP_VERSION}) - 合同会社ぼっち")
        self.geometry(WINDOW_SIZE)

        # Callbacks (assigned by Presenter)
        self.on_close_callback: Optional[Callable[[], None]] = None
        self.on_key_update_callback: Optional[Callable[[str], None]] = None
        self.on_register_key_callback: Optional[Callable[[str], None]] = None
        self.on_apply_prompt_mode_callback: Optional[Callable[[str], None]] = None
        self.on_open_rag_manager_callback: Optional[Callable[[], None]] = None
        self.on_start_generation_callback: Optional[Callable[[], None]] = None
        self.on_stop_generation_callback: Optional[Callable[[], None]] = None
        self.on_clear_context_callback: Optional[Callable[[], None]] = None
        self.on_save_log_callback: Optional[Callable[[str], None]] = None

        self.protocol("WM_DELETE_WINDOW", self._handle_close)

        # UI State Variables
        self.api_key_var = tk.StringVar(value=initial_config.api_key or "")
        self.model_var = tk.StringVar(value=initial_config.model)
        self.reasoning_var = tk.StringVar(value=initial_config.thinking_level)
        self.prompt_mode_var = tk.StringVar(value=initial_config.system_prompt_mode)
        self.status_var = tk.StringVar(value="待機中")
        self.cost_info_var = tk.StringVar(value="Cost: $0.00000")

        last_id = initial_config.last_response_id
        self.response_id_var = tk.StringVar(value=last_id if last_id else "None")

        self.vs_id_var = tk.StringVar(value=initial_config.current_vector_store_id or "")
        self.use_file_search_var = tk.BooleanVar(value=initial_config.use_file_search)

        # UI Components
        self._sys_prompt_view: scrolledtext.ScrolledText = None  # type: ignore
        self._log_view: scrolledtext.ScrolledText = None  # type: ignore
        self._input_view: scrolledtext.ScrolledText = None  # type: ignore
        self._send_btn: ttk.Button = None  # type: ignore
        self._stop_btn: ttk.Button = None  # type: ignore
        self._entry_key: ttk.Entry = None  # type: ignore
        self._vs_combo: ttk.Combobox = None  # type: ignore

        self._setup_ui()

    def _setup_ui(self) -> None:
        self._enable_high_dpi()
        self._setup_styles()

        paned_window = tk.PanedWindow(
            self, orient=tk.HORIZONTAL, sashwidth=6, sashrelief=tk.RAISED
        )
        paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_panel = self._create_left_panel(paned_window)
        paned_window.add(left_panel, width=380, stretch="never")

        right_panel = self._create_right_panel(paned_window)
        paned_window.add(right_panel, stretch="always")

        self._create_status_bar()

    def _enable_high_dpi(self) -> None:
        try:
            from ctypes import windll

            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    def _setup_styles(self) -> None:
        style = ttk.Style()
        style.configure("Bold.TLabel", font=UI_FONTS["BOLD"])
        style.configure(
            "Title.TLabel", font=UI_FONTS["TITLE"], foreground=UI_COLORS["TITLE"]
        )

    def _create_left_panel(self, parent: tk.PanedWindow) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text=" 企業分析設定", padding=10)

        # API Key Section
        ttk.Label(frame, text="Gemini APIキー:", style="Bold.TLabel").pack(anchor="w")
        
        key_frame = ttk.Frame(frame)
        key_frame.pack(fill="x", pady=(2, 0))
        
        self._entry_key = tk.Entry(key_frame, show="*", relief="solid", bd=1)
        if self.api_key_var.get():
            self._entry_key.insert(0, self.api_key_var.get())
        self._entry_key.pack(side="left", fill="x", expand=True, ipady=2)
        self._entry_key.bind("<FocusOut>", self._handle_key_update)

        ttk.Button(
            key_frame,
            text="登録",
            command=self._handle_register_key,
            width=6,
        ).pack(side="right", padx=(5, 0))

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

        # Model Configuration Section
        ttk.Label(frame, text="モデル設定:", style="Bold.TLabel").pack(anchor="w")
        grid_frame = ttk.Frame(frame)
        grid_frame.pack(fill="x", pady=5)

        ttk.Label(grid_frame, text="モデル:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            grid_frame,
            textvariable=self.model_var,
            values=list(PRICING_TABLE.keys()),
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", padx=5)

        ttk.Label(grid_frame, text="思考レベル:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Combobox(
            grid_frame,
            textvariable=self.reasoning_var,
            values=["minimal", "low", "medium", "high"],
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        grid_frame.columnconfigure(1, weight=1)
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

        # RAG Section
        ttk.Label(frame, text="ナレッジベース (RAG):", style="Bold.TLabel").pack(anchor="w")
        rag_frame = ttk.Frame(frame)
        rag_frame.pack(fill="x", pady=5)

        ttk.Label(rag_frame, text="FileSearch Stores:").pack(anchor="w")
        self._vs_combo = ttk.Combobox(
            rag_frame, textvariable=self.vs_id_var, state="readonly"
        )
        self._vs_combo.pack(fill="x", pady=(0, 5))

        ttk.Button(
            rag_frame, text="🛠️ ナレッジベース管理", command=self._handle_open_rag_manager
        ).pack(fill="x")

        ttk.Checkbutton(
            rag_frame,
            text="ファイル検索(RAG)を使用",
            variable=self.use_file_search_var,
        ).pack(anchor="w", pady=(5, 0))

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

        # Prompt Mode Section
        ttk.Label(frame, text="モード選択:", style="Bold.TLabel").pack(anchor="w")

        cb_prompt = ttk.Combobox(
            frame,
            textvariable=self.prompt_mode_var,
            values=list(SYSTEM_PROMPTS.keys()),
            state="readonly",
        )
        cb_prompt.pack(fill="x", pady=(2, 5))
        cb_prompt.bind("<<ComboboxSelected>>", self._handle_apply_prompt_mode)

        ttk.Label(frame, text="システムプロンプト:", style="Bold.TLabel").pack(anchor="w", pady=(5, 0))

        self._sys_prompt_view = scrolledtext.ScrolledText(
            frame, height=10, width=30, font=UI_FONTS["MONO"], wrap=tk.WORD
        )
        self._sys_prompt_view.pack(fill="both", expand=True, pady=5)

        # Context Control
        ttk.Button(
            frame, text="🧹 コンテキスト消去 (新規セッション)", command=self._handle_clear_context
        ).pack(fill="x", pady=10)

        return frame

    def _create_right_panel(self, parent: tk.PanedWindow) -> ttk.Frame:
        frame = ttk.Frame(parent)

        info_frame = ttk.Frame(frame)
        info_frame.pack(fill="x", pady=5, padx=5)
        ttk.Label(info_frame, text="レポート (応答履歴)", style="Title.TLabel").pack(
            side="left"
        )

        id_display = ttk.Frame(info_frame)
        id_display.pack(side="right")
        
        # Format the label directly to "前回レスポンスID: <ID>"
        # Using a single label for cleaner display since we just want to show the ID next to the text
        ttk.Label(
            id_display,
            text="前回レスポンスID:",
            font=UI_FONTS["SMALL_MONO"],
            foreground=UI_COLORS["LABEL_FG"],
        ).pack(side="left", padx=(0, 5))
        
        ttk.Label(
            id_display,
            textvariable=self.response_id_var,
            font=UI_FONTS["SMALL_BOLD"],
            foreground=UI_COLORS["ID_FG"],
        ).pack(side="left")

        self._log_view = scrolledtext.ScrolledText(
            frame, state="disabled", font=UI_FONTS["NORMAL"], wrap=tk.WORD
        )
        self._log_view.pack(fill="both", expand=True, padx=5)
        self._configure_log_tags()

        input_frame = ttk.LabelFrame(
            frame, text=" リクエスト入力 (Ctrl+Enterで送信) ", padding=5
        )
        input_frame.pack(fill="x", padx=5, pady=5)

        self._input_view = scrolledtext.ScrolledText(
            input_frame, height=4, font=UI_FONTS["NORMAL"], undo=True
        )
        self._input_view.pack(fill="x", side="left", expand=True)
        self._input_view.bind(
            "<Control-Return>", lambda e: self._handle_start_generation()
        )
        self._input_view.bind(
            "<Command-Return>", lambda e: self._handle_start_generation()
        )

        btn_frame = ttk.Frame(input_frame)
        btn_frame.pack(side="right", fill="y", padx=(5, 0))

        self._send_btn = ttk.Button(
            btn_frame, text="分析開始 🚀", command=self._handle_start_generation
        )
        self._send_btn.pack(fill="x", pady=(0, 2))

        self._stop_btn = ttk.Button(
            btn_frame, text="停止 ⏹️", command=self._handle_stop_generation, state="disabled"
        )
        self._stop_btn.pack(fill="x", pady=(2, 2))

        ttk.Button(btn_frame, text="保存 💾", command=self._handle_save_log).pack(
            fill="x", pady=(2, 0)
        )

        return frame

    def _create_status_bar(self) -> None:
        bar = ttk.Frame(self, relief=tk.SUNKEN)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(bar, textvariable=self.status_var, font=UI_FONTS["STATUS"]).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Label(
            bar, textvariable=self.cost_info_var, font=UI_FONTS["STATUS_MONO"]
        ).pack(side=tk.RIGHT, padx=5)

    def _configure_log_tags(self) -> None:
        self._log_view.tag_config(
            "user",
            foreground=UI_COLORS["USER_FG"],
            background=UI_COLORS["USER_BG"],
            font=UI_FONTS["NORMAL_BOLD"],
            lmargin1=10,
            lmargin2=10,
            rmargin=10,
        )
        self._log_view.tag_config(
            "ai",
            foreground=UI_COLORS["AI_FG"],
            lmargin1=10,
            lmargin2=10,
            rmargin=10,
        )
        self._log_view.tag_config("error", foreground=UI_COLORS["ERROR_FG"])
        self._log_view.tag_config(
            "info", foreground="blue", font=UI_FONTS["SMALL_MONO"]
        )

    # --- View Actions (Called by Presenter) ---
    def set_system_prompt(self, prompt: str) -> None:
        self._sys_prompt_view.delete("1.0", tk.END)
        self._sys_prompt_view.insert("1.0", prompt)

    def get_system_prompt(self) -> str:
        return self._sys_prompt_view.get("1.0", tk.END).strip()

    def get_api_key(self) -> str:
        return self._entry_key.get().strip()

    def get_user_input(self) -> str:
        return self._input_view.get("1.0", tk.END).strip()

    def clear_user_input(self) -> None:
        self._input_view.delete("1.0", tk.END)

    def append_log(self, text: str, tag: Optional[str] = None) -> None:
        self._log_view.config(state="normal")
        self._log_view.insert(tk.END, text, tag)
        self._log_view.see(tk.END)
        self._log_view.config(state="disabled")

    def clear_log(self) -> None:
        self._log_view.config(state="normal")
        self._log_view.delete("1.0", tk.END)
        self._log_view.config(state="disabled")

    def get_log_content(self) -> str:
        return self._log_view.get("1.0", tk.END).strip()

    def update_vs_combo(self, values: List[str]) -> None:
        self._vs_combo["values"] = values

    def set_vs_combo_index(self, index: int) -> None:
        if 0 <= index < len(self._vs_combo["values"]):
            self._vs_combo.current(index)

    def get_vs_combo_values(self) -> List[str]:
        return list(self._vs_combo["values"])

    def set_generation_state(self, is_generating: bool) -> None:
        if is_generating:
            self._send_btn.config(state="disabled")
            self._stop_btn.config(state="normal")
        else:
            self._send_btn.config(state="normal")
            self._stop_btn.config(state="disabled")

    def focus_api_key(self) -> None:
        self._entry_key.focus_set()

    def show_warning(self, title: str, message: str) -> None:
        messagebox.showwarning(title, message)

    def show_error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message)

    def ask_yes_no(self, title: str, message: str) -> bool:
        return messagebox.askyesno(title, message)

    def show_info(self, title: str, message: str) -> None:
        messagebox.showinfo(title, message)

    def ask_save_file_name(self, default_filename: str) -> str:
        path_str = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt")],
            initialfile=default_filename,
        )
        return path_str

    # --- Event Handlers (Routing to Presenter) ---
    def _handle_close(self) -> None:
        if self.on_close_callback:
            self.on_close_callback()
        self.destroy()

    def _handle_register_key(self) -> None:
        if self.on_register_key_callback:
            self.on_register_key_callback(self.get_api_key())

    def _handle_key_update(self, event: Any) -> None:
        if self.on_key_update_callback:
            self.on_key_update_callback(self.get_api_key())

    def _handle_apply_prompt_mode(self, event: Optional[tk.Event] = None) -> None:
        if self.on_apply_prompt_mode_callback:
            self.on_apply_prompt_mode_callback(self.prompt_mode_var.get())

    def _handle_open_rag_manager(self) -> None:
        if self.on_open_rag_manager_callback:
            self.on_open_rag_manager_callback()

    def _handle_start_generation(self) -> str:
        if self.on_start_generation_callback:
            self.on_start_generation_callback()
        return "break"

    def _handle_stop_generation(self) -> None:
        if self.on_stop_generation_callback:
            self.on_stop_generation_callback()

    def _handle_clear_context(self) -> None:
        if self.on_clear_context_callback:
            self.on_clear_context_callback()

    def _handle_save_log(self) -> None:
        if self.on_save_log_callback:
            text = self.get_log_content()
            if text:
                self.on_save_log_callback(text)
