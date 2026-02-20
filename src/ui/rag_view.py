"""
View component for RAG Management MVP pattern.
"""

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, List, Optional

from src.ui.styles import UI_FONTS


class RagView(tk.Toplevel):
    """
    View component for RAG Management MVP pattern.
    Responsible for rendering the UI and forwarding user events.
    """

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("ナレッジベース管理 (RAG Management)")
        self.geometry("1100x750")
        self.transient(parent)
        self.grab_set()

        # Callbacks (assigned by Presenter)
        self.on_refresh_stores_callback: Optional[Callable[[], None]] = None
        self.on_store_select_callback: Optional[Callable[[Optional[str], int], None]] = None
        self.on_create_store_callback: Optional[Callable[[str], None]] = None
        self.on_rename_store_callback: Optional[Callable[[str, str], None]] = None
        self.on_delete_store_callback: Optional[Callable[[str], None]] = None
        self.on_upload_file_callback: Optional[Callable[[str, str], None]] = None
        self.on_delete_file_callback: Optional[Callable[[str, str, str], None]] = None
        self.on_file_select_callback: Optional[Callable[[bool], None]] = None

        # UI State
        self.status_var = tk.StringVar(value="Ready")

        # Widget references
        self._store_tree: ttk.Treeview = None  # type: ignore
        self._file_tree: ttk.Treeview = None  # type: ignore
        self._rename_btn: ttk.Button = None  # type: ignore
        self._del_store_btn: ttk.Button = None  # type: ignore
        self._upload_btn: ttk.Button = None  # type: ignore
        self._delete_file_btn: ttk.Button = None  # type: ignore

        self._current_store_id: Optional[str] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        paned = tk.PanedWindow(
            self, orient=tk.HORIZONTAL, sashwidth=4, sashrelief=tk.RAISED
        )
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left Panel: Vector Stores
        left_frame = ttk.LabelFrame(paned, text=" Vector Stores ", padding=5)
        paned.add(left_frame, width=450, stretch="never")

        self._store_tree = ttk.Treeview(
            left_frame,
            columns=("name", "id", "status", "files", "usage"),
            show="headings",
            selectmode="browse",
        )
        self._store_tree.heading("name", text="Name")
        self._store_tree.heading("id", text="ID")
        self._store_tree.heading("status", text="Status")
        self._store_tree.heading("files", text="Files")
        self._store_tree.heading("usage", text="Bytes")

        self._store_tree.column("name", width=140)
        self._store_tree.column("id", width=90)
        self._store_tree.column("status", width=70)
        self._store_tree.column("files", width=50, anchor="center")
        self._store_tree.column("usage", width=70, anchor="e")

        self._store_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self._store_tree.bind("<<TreeviewSelect>>", self._handle_store_select)

        store_scroll = ttk.Scrollbar(
            left_frame, orient="vertical", command=self._store_tree.yview
        )
        store_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._store_tree.configure(yscrollcommand=store_scroll.set)

        btn_frame_left = ttk.Frame(left_frame)
        btn_frame_left.pack(fill=tk.X, pady=(5, 0))

        row1 = ttk.Frame(btn_frame_left)
        row1.pack(fill=tk.X, pady=(0, 2))
        ttk.Button(row1, text="➕ 新規作成", command=self._handle_create_store).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2)
        )
        self._rename_btn = ttk.Button(
            row1, text="✏️ 名前変更", command=self._handle_rename_store, state="disabled"
        )
        self._rename_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        row2 = ttk.Frame(btn_frame_left)
        row2.pack(fill=tk.X)
        self._del_store_btn = ttk.Button(
            row2, text="🗑️ 削除", command=self._handle_delete_store, state="disabled"
        )
        self._del_store_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(
            row2, text="🔄 更新", command=self._handle_refresh_stores
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # Right Panel: Files
        right_frame = ttk.LabelFrame(paned, text=" Files in Selected Store ", padding=5)
        paned.add(right_frame, stretch="always")

        self._file_tree = ttk.Treeview(
            right_frame,
            columns=("filename", "id", "created"),
            show="headings",
            selectmode="browse",
        )
        self._file_tree.heading("filename", text="Filename")
        self._file_tree.heading("id", text="File ID")
        self._file_tree.heading("created", text="Created")

        self._file_tree.column("filename", width=250)
        self._file_tree.column("id", width=120)
        self._file_tree.column("created", width=120)

        self._file_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self._file_tree.bind("<<TreeviewSelect>>", self._handle_file_select)

        file_scroll = ttk.Scrollbar(
            right_frame, orient="vertical", command=self._file_tree.yview
        )
        file_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._file_tree.configure(yscrollcommand=file_scroll.set)

        btn_frame_right = ttk.Frame(right_frame)
        btn_frame_right.pack(fill=tk.X, pady=(5, 0))

        self._upload_btn = ttk.Button(
            btn_frame_right,
            text="📂 ファイルアップロード",
            command=self._handle_upload_file,
            state="disabled",
        )
        self._upload_btn.pack(side=tk.LEFT, padx=(0, 5))

        self._delete_file_btn = ttk.Button(
            btn_frame_right,
            text="🗑️ ファイル削除",
            command=self._handle_delete_file,
            state="disabled",
        )
        self._delete_file_btn.pack(side=tk.RIGHT)

        ttk.Label(
            btn_frame_right,
            text="⚠️ StoreとStorageの両方から削除されます",
            font=UI_FONTS["SMALL_MONO"],
            foreground="gray",
        ).pack(side=tk.RIGHT, padx=5)

        status_bar = ttk.Label(
            self,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            font=UI_FONTS["STATUS"],
            padding=(5, 2),
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # --- UI Updaters ---

    def set_status(self, msg: str, busy: bool = False) -> None:
        self.status_var.set(msg)
        self.config(cursor="watch" if busy else "")
        self.update_idletasks()

    def clear_stores(self) -> None:
        self._store_tree.delete(*self._store_tree.get_children())
        self.clear_files()

    def add_store(self, name: str, s_id: str, status: str, files_count: int, usage: str) -> None:
        self._store_tree.insert("", "end", values=(name, s_id, status, files_count, usage))

    def clear_files(self) -> None:
        self._file_tree.delete(*self._file_tree.get_children())
        self._delete_file_btn.config(state="disabled")

    def add_file(self, filename: str, f_id: str, dt_str: str) -> None:
        self._file_tree.insert("", "end", values=(filename, f_id, dt_str))

    def update_button_states(self, has_selection: bool) -> None:
        state = "normal" if has_selection else "disabled"
        self._rename_btn.config(state=state)
        self._del_store_btn.config(state=state)
        self._upload_btn.config(state=state)
        if not has_selection:
            self.clear_files()

    def get_selected_store(self) -> Optional[tuple]:
        selection = self._store_tree.selection()
        if not selection:
            return None
        return self._store_tree.item(selection[0])["values"]

    def get_selected_file(self) -> Optional[tuple]:
        selection = self._file_tree.selection()
        if not selection:
            return None
        return self._file_tree.item(selection[0])["values"]

    def show_warning(self, title: str, message: str) -> None:
        messagebox.showwarning(title, message)

    def show_error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message)

    def ask_yes_no(self, title: str, message: str) -> bool:
        return messagebox.askyesno(title, message)

    def set_upload_btn_state(self, state: str) -> None:
        self._upload_btn.config(state=state)

    def set_delete_file_btn_state(self, state: str) -> None:
        self._delete_file_btn.config(state=state)

    # --- Event Handlers (Routing to Presenter) ---

    def _handle_refresh_stores(self) -> None:
        if self.on_refresh_stores_callback:
            self.on_refresh_stores_callback()

    def _handle_store_select(self, event: Any) -> None:
        selection = self._store_tree.selection()
        if not selection:
            self._current_store_id = None
            if self.on_store_select_callback:
                self.on_store_select_callback(None, 0)
            return

        item = self._store_tree.item(selection[0])
        store_id = str(item["values"][1])
        file_count = int(item["values"][3]) if item["values"][3] else 0
        
        self._current_store_id = store_id
        if self.on_store_select_callback:
            self.on_store_select_callback(store_id, file_count)

    def _handle_create_store(self) -> None:
        name = simpledialog.askstring("新規作成", "Vector Storeの名前を入力してください:")
        if name and self.on_create_store_callback:
            self.on_create_store_callback(name)

    def _handle_rename_store(self) -> None:
        values = self.get_selected_store()
        if not values or not self._current_store_id:
            return

        current_name = values[0]
        new_name = simpledialog.askstring(
            "名前変更", "新しい名前を入力してください:", initialvalue=current_name
        )
        if new_name and new_name != current_name and self.on_rename_store_callback:
            self.on_rename_store_callback(self._current_store_id, new_name)

    def _handle_delete_store(self) -> None:
        if self._current_store_id and self.on_delete_store_callback:
            self.on_delete_store_callback(self._current_store_id)

    def _handle_file_select(self, event: Any) -> None:
        has_selection = bool(self._file_tree.selection())
        if self.on_file_select_callback:
            self.on_file_select_callback(has_selection)

    def _handle_upload_file(self) -> None:
        if not self._current_store_id:
            return

        file_path = filedialog.askopenfilename(
            title="アップロードするファイルを選択",
            filetypes=[
                ("All Files", "*.*"),
                ("PDF", "*.pdf"),
                ("Text", "*.txt"),
                ("JSON", "*.json"),
            ],
        )
        if file_path and self.on_upload_file_callback:
            self.on_upload_file_callback(file_path, self._current_store_id)

    def _handle_delete_file(self) -> None:
        f_values = self.get_selected_file()
        if not f_values or not self._current_store_id:
            return

        filename, file_id, _ = f_values
        if self.on_delete_file_callback:
            self.on_delete_file_callback(str(filename), str(file_id), self._current_store_id)
