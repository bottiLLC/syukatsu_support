"""
Service Robot Diagnosis Support GUI Application.

This module provides the main graphical user interface for the application,
orchestrating user inputs, LLM interactions via the Responses API, and
RAG (Retrieval-Augmented Generation) management.
"""

import datetime
import logging
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any, List, Optional

# Local imports
from src.config.app_config import AppConfig, ConfigManager, UserConfig
from src.core.models import (
    FileSearchTool,
    ReasoningOptions,
    ResponseRequestPayload,
    StreamError,
    StreamResponseCreated,
    StreamTextDelta,
    StreamUsage,
)
from src.core.pricing import PRICING_TABLE
from src.core.prompts import SYSTEM_PROMPTS
from src.core.rag_services import FileService, VectorStoreService
from src.core.services import CostCalculator, LLMService
from src.ui.styles import UI_COLORS, UI_FONTS, WINDOW_SIZE

logger = logging.getLogger(__name__)


class QMTroubleshootingApp(tk.Tk):
    """
    Main GUI application class for Service Robot Investigation Support.

    Inherits from tk.Tk and manages the main application window lifecycle.
    """

    def __init__(self) -> None:
        """
        Initializes the application, loads configuration, and sets up the UI.
        """
        super().__init__()
        self.title(f"Service Robot Investigation Support ({AppConfig.APP_VERSION}) - QM")
        self.geometry(WINDOW_SIZE)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # --- Configuration Load ---
        try:
            self._user_config: UserConfig = ConfigManager.load()
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            messagebox.showwarning(
                "設定エラー", "設定の読み込みに失敗しました。デフォルト設定で開始します。"
            )
            self._user_config = UserConfig()

        # --- UI State Variables ---
        self._api_key_var = tk.StringVar(value=self._user_config.api_key or "")
        self._show_key_var = tk.BooleanVar(value=False)
        self._model_var = tk.StringVar(value=self._user_config.model)
        self._reasoning_var = tk.StringVar(value=self._user_config.reasoning_effort)
        self._prompt_mode_var = tk.StringVar(
            value=self._user_config.system_prompt_mode
        )
        self._status_var = tk.StringVar(value="待機中")
        self._cost_info_var = tk.StringVar(value="Cost: $0.00000")

        last_id = self._user_config.last_response_id
        self._response_id_var = tk.StringVar(value=last_id if last_id else "None")

        # RAG State Variables
        self._vs_id_var = tk.StringVar(
            value=self._user_config.current_vector_store_id or ""
        )
        self._use_file_search_var = tk.BooleanVar(
            value=self._user_config.use_file_search
        )

        # --- Concurrency Management ---
        self._message_queue: queue.Queue[Any] = queue.Queue()
        self._is_generating: bool = False
        self._cancel_event = threading.Event()
        self._active_thread: Optional[threading.Thread] = None

        # --- Service Instances ---
        self._rag_service: Optional[VectorStoreService] = None
        self._file_service: Optional[FileService] = None

        # --- UI Components (Initialized in _setup_ui) ---
        # Type hints for widgets initialized later
        self._sys_prompt_view: scrolledtext.ScrolledText
        self._log_view: scrolledtext.ScrolledText
        self._input_view: scrolledtext.ScrolledText
        self._send_btn: ttk.Button
        self._stop_btn: ttk.Button
        self._entry_key: ttk.Entry
        self._vs_combo: ttk.Combobox

        # --- Initialization ---
        self._setup_ui()
        self._apply_prompt_mode()

        # Initialize services if API key is present
        if self._user_config.api_key:
            self._init_services(self._user_config.api_key)
            self._refresh_vector_stores()

        # Start message loop
        self.after(100, self._process_queue)

    def _init_services(self, api_key: str) -> None:
        """
        Initializes the backend service layers with the provided API key.

        Args:
            api_key: The OpenAI API Key.
        """
        try:
            self._rag_service = VectorStoreService(api_key)
            self._file_service = FileService(api_key)
            logger.info("Services initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            messagebox.showerror("サービスエラー", f"サービスの初期化に失敗しました: {e}")

    def _setup_ui(self) -> None:
        """
        Constructs the main user interface layout and widgets.
        """
        self._enable_high_dpi()
        self._setup_styles()

        # Main Layout: Paned Window
        paned_window = tk.PanedWindow(
            self, orient=tk.HORIZONTAL, sashwidth=6, sashrelief=tk.RAISED
        )
        paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left Panel (Configuration)
        left_panel = self._create_left_panel(paned_window)
        paned_window.add(left_panel, width=380, stretch="never")

        # Right Panel (Chat/Log)
        right_panel = self._create_right_panel(paned_window)
        paned_window.add(right_panel, stretch="always")

        # Status Bar
        self._create_status_bar()

    def _enable_high_dpi(self) -> None:
        """Enables High DPI awareness on Windows systems."""
        try:
            from ctypes import windll

            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    def _setup_styles(self) -> None:
        """Configures custom ttk styles using constants from ui_styles."""
        style = ttk.Style()
        style.configure("Bold.TLabel", font=UI_FONTS["BOLD"])
        style.configure(
            "Title.TLabel", font=UI_FONTS["TITLE"], foreground=UI_COLORS["TITLE"]
        )

    def _create_left_panel(self, parent: tk.PanedWindow) -> ttk.LabelFrame:
        """
        Creates the left configuration panel.

        Args:
            parent: The parent widget.

        Returns:
            The configured left panel frame.
        """
        frame = ttk.LabelFrame(parent, text=" 診断設定 (Diagnostic Strategy) ", padding=10)

        # --- API Key Section ---
        ttk.Label(frame, text="OpenAI APIキー:", style="Bold.TLabel").pack(anchor="w")
        self._entry_key = ttk.Entry(frame, textvariable=self._api_key_var, show="*")
        self._entry_key.pack(fill="x", pady=(2, 0))
        self._entry_key.bind("<FocusOut>", self._on_key_update)

        ttk.Checkbutton(
            frame,
            text="キーを表示",
            variable=self._show_key_var,
            command=self._toggle_key_visibility,
        ).pack(anchor="w")

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

        # --- Model Configuration Section ---
        ttk.Label(frame, text="モデル設定:", style="Bold.TLabel").pack(anchor="w")
        grid_frame = ttk.Frame(frame)
        grid_frame.pack(fill="x", pady=5)

        # Model Selector
        ttk.Label(grid_frame, text="モデル:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            grid_frame,
            textvariable=self._model_var,
            values=list(PRICING_TABLE.keys()),
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", padx=5)

        # Reasoning Effort Selector
        ttk.Label(grid_frame, text="推論強度:").grid(
            row=1, column=0, sticky="w", pady=5
        )
        ttk.Combobox(
            grid_frame,
            textvariable=self._reasoning_var,
            # Updated to match OpenAPI spec (components/schemas/ReasoningEffort)
            values=["none", "minimal", "low", "medium", "high", "xhigh"],
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        grid_frame.columnconfigure(1, weight=1)

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

        # --- RAG Section ---
        ttk.Label(frame, text="ナレッジベース (RAG):", style="Bold.TLabel").pack(anchor="w")

        rag_frame = ttk.Frame(frame)
        rag_frame.pack(fill="x", pady=5)

        ttk.Label(rag_frame, text="Vector Stores:").pack(anchor="w")
        self._vs_combo = ttk.Combobox(
            rag_frame, textvariable=self._vs_id_var, state="readonly"
        )
        self._vs_combo.pack(fill="x", pady=(0, 5))

        # Manage Button
        ttk.Button(
            rag_frame, text="🛠️ ナレッジベース管理", command=self._open_rag_manager
        ).pack(fill="x")

        ttk.Checkbutton(
            rag_frame,
            text="ファイル検索(RAG)を使用",
            variable=self._use_file_search_var,
        ).pack(anchor="w", pady=(5, 0))

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

        # --- Prompt Mode Section ---
        ttk.Label(frame, text="診断モード (指示書):", style="Bold.TLabel").pack(anchor="w")

        cb_prompt = ttk.Combobox(
            frame,
            textvariable=self._prompt_mode_var,
            values=list(SYSTEM_PROMPTS.keys()),
            state="readonly",
        )
        cb_prompt.pack(fill="x", pady=(2, 5))
        cb_prompt.bind("<<ComboboxSelected>>", self._apply_prompt_mode)

        self._sys_prompt_view = scrolledtext.ScrolledText(
            frame, height=10, width=30, font=UI_FONTS["MONO"], wrap=tk.WORD
        )
        self._sys_prompt_view.pack(fill="both", expand=True, pady=5)

        # --- Context Control ---
        ttk.Button(
            frame, text="🧹 コンテキスト消去 (新規セッション)", command=self._clear_context
        ).pack(fill="x", pady=10)

        return frame

    def _create_right_panel(self, parent: tk.PanedWindow) -> ttk.Frame:
        """
        Creates the right panel for logs and interaction.

        Args:
            parent: The parent widget.

        Returns:
            The configured right panel frame.
        """
        frame = ttk.Frame(parent)

        # Header Info
        info_frame = ttk.Frame(frame)
        info_frame.pack(fill="x", pady=5, padx=5)
        ttk.Label(info_frame, text="調査ログ (応答履歴)", style="Title.TLabel").pack(
            side="left"
        )

        id_display = ttk.Frame(info_frame)
        id_display.pack(side="right")
        ttk.Label(
            id_display,
            textvariable=self._response_id_var,
            font=UI_FONTS["SMALL_BOLD"],
            foreground=UI_COLORS["ID_FG"],
        ).pack(side="right")
        ttk.Label(
            id_display,
            text="前回レスポンスID: ",
            font=UI_FONTS["SMALL_MONO"],
            foreground=UI_COLORS["LABEL_FG"],
        ).pack(side="right")

        # Log View
        self._log_view = scrolledtext.ScrolledText(
            frame, state="disabled", font=UI_FONTS["NORMAL"], wrap=tk.WORD
        )
        self._log_view.pack(fill="both", expand=True, padx=5)
        self._configure_log_tags()

        # Input Area
        input_frame = ttk.LabelFrame(
            frame, text=" 症状 / エンジニア入力 (Ctrl+Enterで送信) ", padding=5
        )
        input_frame.pack(fill="x", padx=5, pady=5)

        self._input_view = scrolledtext.ScrolledText(
            input_frame, height=4, font=UI_FONTS["NORMAL"], undo=True
        )
        self._input_view.pack(fill="x", side="left", expand=True)
        # Bind shortcuts
        self._input_view.bind("<Control-Return>", lambda e: self._start_generation())
        self._input_view.bind("<Command-Return>", lambda e: self._start_generation())

        # Buttons
        btn_frame = ttk.Frame(input_frame)
        btn_frame.pack(side="right", fill="y", padx=(5, 0))

        self._send_btn = ttk.Button(
            btn_frame, text="分析開始 🚀", command=self._start_generation
        )
        self._send_btn.pack(fill="x", pady=(0, 2))

        self._stop_btn = ttk.Button(
            btn_frame, text="停止 ⏹️", command=self._stop_generation, state="disabled"
        )
        self._stop_btn.pack(fill="x", pady=(2, 2))

        ttk.Button(btn_frame, text="保存 💾", command=self._save_log).pack(
            fill="x", pady=(2, 0)
        )

        return frame

    def _create_status_bar(self) -> None:
        """Creates the bottom status bar."""
        bar = ttk.Frame(self, relief=tk.SUNKEN)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(bar, textvariable=self._status_var, font=UI_FONTS["STATUS"]).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Label(
            bar, textvariable=self._cost_info_var, font=UI_FONTS["STATUS_MONO"]
        ).pack(side=tk.RIGHT, padx=5)

    def _configure_log_tags(self) -> None:
        """Configures text tags for the log view styling."""
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

    # --- Event Handlers ---

    def _toggle_key_visibility(self) -> None:
        """Toggles the masking of the API key entry."""
        if self._show_key_var.get():
            self._entry_key.config(show="")
        else:
            self._entry_key.config(show="*")

    def _on_key_update(self, event: Any) -> None:
        """Handle API Key updates to re-initialize services."""
        api_key = self._api_key_var.get().strip()
        if api_key:
            self._init_services(api_key)
            self._refresh_vector_stores()

    def _apply_prompt_mode(self, event: Optional[tk.Event] = None) -> None:
        """Updates the system prompt based on the selected mode."""
        mode = self._prompt_mode_var.get()
        prompt = SYSTEM_PROMPTS.get(mode, "")
        self._sys_prompt_view.delete("1.0", tk.END)
        self._sys_prompt_view.insert("1.0", prompt)

    # --- RAG Management Logic ---

    def _refresh_vector_stores(self) -> None:
        """
        Fetches available vector stores in a background thread and updates the UI.
        """
        if not self._rag_service:
            return

        def _fetch() -> None:
            try:
                stores = self._rag_service.list_vector_stores()
                # Format: "Name (ID)" or "ID" if no name
                values: List[str] = []
                for s in stores:
                    label = f"{s.name} ({s.id})" if s.name else s.id
                    values.append(label)

                # Schedule UI update on main thread
                self.after(0, lambda: self._update_vs_combo(values))
            except Exception as e:
                logger.error(f"Failed to fetch vector stores: {e}")

        threading.Thread(target=_fetch, daemon=True).start()

    def _update_vs_combo(self, values: List[str]) -> None:
        """
        Updates the Vector Store combobox values and maintains selection.

        Args:
            values: List of formatted vector store labels.
        """
        self._vs_combo["values"] = values

        # Try to maintain selection
        current_id = self._vs_id_var.get()
        if current_id:
            found = False
            for i, val in enumerate(values):
                # Check if the stored ID is part of the label
                if current_id in val:
                    self._vs_combo.current(i)
                    found = True
                    break
            if not found:
                # If the ID no longer exists, clear the selection
                self._vs_id_var.set("")

    def _open_rag_manager(self) -> None:
        """
        Opens the RAG Management Window (modal).
        Refreshes stores after the window closes.
        """
        # Local import to avoid circular dependency and handle potential import errors
        try:
            from src.ui.rag_window import RAGManagementWindow
        except ImportError as e:
            logger.error(f"Failed to import RAGManagementWindow: {e}")
            messagebox.showerror(
                "エラー",
                "RAG管理モジュールを読み込めませんでした。\n"
                "依存関係が正しくインストールされているか確認してください。",
            )
            return

        api_key = self._api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("設定エラー", "API Keyを設定してください。")
            return

        if not self._rag_service or not self._file_service:
            self._init_services(api_key)

        # Open the modal window
        # Ensure services are initialized before passing
        if self._rag_service and self._file_service:
            window = RAGManagementWindow(self, self._rag_service, self._file_service)
            # Wait for the window to close
            self.wait_window(window)

            # Refresh the combo box to reflect any changes
            self._refresh_vector_stores()

    # --- LLM Generation Logic ---

    def _start_generation(self) -> Optional[str]:
        """
        Initiates the LLM generation process.
        Validates input, constructs payload, and starts the background thread.

        Returns:
            'break' to stop event propagation if triggered by key binding, else None.
        """
        if self._is_generating:
            return None

        api_key = self._api_key_var.get().strip()
        user_input_text = self._input_view.get("1.0", tk.END).strip()
        sys_instructions = self._sys_prompt_view.get("1.0", tk.END).strip()

        if not api_key:
            messagebox.showwarning("APIキー未設定", "API Keyを入力してください。")
            self._entry_key.focus_set()
            return None
        if not user_input_text:
            return None

        # Prepare RAG tools configuration
        tools = None
        if self._use_file_search_var.get():
            vs_val = self._vs_combo.get()
            if not vs_val:
                messagebox.showwarning(
                    "RAGエラー", "ファイル検索が有効ですが、Vector Storeが選択されていません。"
                )
                return None

            # Extract ID from "Name (ID)" format
            # Example: "My Store (vs_123abc)" -> "vs_123abc"
            vs_id = vs_val.split("(")[-1].strip(")") if "(" in vs_val else vs_val

            # Create FileSearchTool instance per Pydantic model
            # Adhering to openapi.documented.yml schema for file_search tool
            tools = [FileSearchTool(type="file_search", vector_store_ids=[vs_id])]

        # Update UI state
        self._is_generating = True
        self._send_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        model = self._model_var.get()
        effort = self._reasoning_var.get()
        self._status_var.set(f"{model} ({effort}) で推論中...")
        self._cancel_event.clear()

        # Log User Input
        timestamp = datetime.datetime.now().strftime("%H:%M")
        self._append_log(f"\n[USER] {timestamp}\n{user_input_text}\n", "user")
        self._input_view.delete("1.0", tk.END)

        # Prepare Payload
        prev_id = self._user_config.last_response_id
        if not prev_id or prev_id == "None":
            prev_id = None

        try:
            # Type casting for reasoning effort (validation handled by Pydantic)
            payload = ResponseRequestPayload(
                model=model,
                input=user_input_text,
                instructions=sys_instructions,
                reasoning=ReasoningOptions(effort=effort),  # type: ignore
                previous_response_id=prev_id,
                tools=tools,  # Pass the tool list (can be None)
                stream=True,
            )
        except Exception as e:
            messagebox.showerror("設定エラー", f"不正な設定値です: {e}")
            self._is_generating = False
            self._send_btn.config(state="normal")
            return None

        # Start Thread
        self._active_thread = threading.Thread(
            target=self._run_llm_thread,
            args=(api_key, payload),
            daemon=True,
        )
        self._active_thread.start()
        return "break"  # Stop event propagation (e.g. newline in text widget)

    def _stop_generation(self) -> None:
        """Signals the generation thread to stop."""
        if self._is_generating:
            self._cancel_event.set()
            self._append_log("\n[SYSTEM] ユーザーによって中断されました。\n", "error")

    def _run_llm_thread(self, api_key: str, payload: ResponseRequestPayload) -> None:
        """
        Runs the LLM streaming request in a background thread.

        Args:
            api_key: OpenAI API Key.
            payload: Request parameters.
        """
        try:
            if self._cancel_event.is_set():
                return

            service = LLMService(api_key)
            start_msg = f"\n[AI ({payload.model})] thinking...\n"
            self._message_queue.put(StreamTextDelta(delta=start_msg))

            stream = service.stream_diagnosis(payload)
            for event in stream:
                if self._cancel_event.is_set():
                    break
                self._message_queue.put(event)

        except Exception as e:
            logger.exception("LLM thread failed")
            self._message_queue.put(StreamError(message=str(e)))
        finally:
            self._message_queue.put(None)  # Signal completion

    def _process_queue(self) -> None:
        """
        Polls the message queue and updates the UI in the main thread.
        This ensures thread safety for Tkinter updates.
        """
        try:
            while True:
                event = self._message_queue.get_nowait()

                if event is None:  # Done signal
                    self._is_generating = False
                    self._send_btn.config(state="normal")
                    self._stop_btn.config(state="disabled")
                    self._status_var.set("待機中")

                elif isinstance(event, StreamTextDelta):
                    self._append_log(event.delta, "ai")

                elif isinstance(event, StreamResponseCreated):
                    self._user_config.last_response_id = event.response_id
                    self._response_id_var.set(event.response_id)

                elif isinstance(event, StreamUsage):
                    cost_str = CostCalculator.calculate(self._model_var.get(), event)
                    self._cost_info_var.set(cost_str)

                elif isinstance(event, StreamError):
                    self._append_log(event.message, "error")

                self._message_queue.task_done()
        except queue.Empty:
            pass

        # Reschedule check if window exists
        if self.winfo_exists():
            self.after(50, self._process_queue)

    def _clear_context(self) -> None:
        """Resets the conversation context after user confirmation."""
        confirm = messagebox.askyesno(
            "コンテキストの消去",
            "会話の文脈（Previous Response ID）を破棄して新しいセッションを開始しますか？",
        )
        if confirm:
            self._user_config.last_response_id = None
            self._response_id_var.set("None")

            self._log_view.config(state="normal")
            self._log_view.delete("1.0", tk.END)
            self._log_view.config(state="disabled")

            self._cost_info_var.set("Cost: $0.00000")
            self._status_var.set("コンテキストを消去しました。")

    def _save_log(self) -> None:
        """Saves the current log content to a text file."""
        text = self._log_view.get("1.0", tk.END).strip()
        if not text:
            return

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        default_filename = f"QM_Log_{timestamp}.txt"

        path_str = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt")],
            initialfile=default_filename,
        )

        if path_str:
            try:
                path = Path(path_str)
                with path.open("w", encoding="utf-8") as f:
                    header = (
                        f"Model: {self._model_var.get()}\n"
                        f"Prompt Mode: {self._prompt_mode_var.get()}\n"
                        f"Tools: {'File Search' if self._use_file_search_var.get() else 'None'}\n"
                    )
                    f.write(header + "-" * 40 + "\n" + text)
                messagebox.showinfo("保存完了", "ログを保存しました。")
            except Exception as e:
                messagebox.showerror("保存エラー", f"保存に失敗しました: {str(e)}")

    def _append_log(self, text: str, tag: Optional[str] = None) -> None:
        """
        Appends text to the log view with optional styling.

        Args:
            text: The text to append.
            tag: The style tag to apply (e.g., 'user', 'ai', 'error').
        """
        self._log_view.config(state="normal")
        self._log_view.insert(tk.END, text, tag)
        self._log_view.see(tk.END)
        self._log_view.config(state="disabled")

    def _on_close(self) -> None:
        """
        Handles application closure.
        Saves configuration and ensures threads are terminated cleanly.
        """
        # Update config object from UI variables
        self._user_config.api_key = self._api_key_var.get()
        self._user_config.model = self._model_var.get()
        # Explicit cast for type checker (Pydantic validates actual value)
        self._user_config.reasoning_effort = self._reasoning_var.get()  # type: ignore
        self._user_config.system_prompt_mode = self._prompt_mode_var.get()

        # Save RAG settings
        raw_vs = self._vs_id_var.get()
        if "(" in raw_vs:
            # Extract ID if format is "Name (ID)"
            self._user_config.current_vector_store_id = raw_vs.split("(")[-1].strip(
                ")"
            )
        else:
            self._user_config.current_vector_store_id = raw_vs

        self._user_config.use_file_search = self._use_file_search_var.get()

        try:
            ConfigManager.save(self._user_config)
        except Exception as e:
            logger.error(f"Failed to save configuration on close: {e}")
            messagebox.showwarning("保存エラー", f"設定の保存に失敗しました: {e}")

        # Stop active generation if any
        if self._is_generating:
            self._cancel_event.set()
            if self._active_thread and self._active_thread.is_alive():
                self._active_thread.join(timeout=1.0)

        self.destroy()
        try:
            self.quit()
        except Exception:
            pass