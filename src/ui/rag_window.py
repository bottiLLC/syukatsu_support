"""
RAG Management Window module for the Job Hunting Support Application.

This module provides a dedicated interface for managing Vector Stores and
their associated files. It serves as a central hub for:
- Creating, renaming, and deleting Vector Stores.
- Uploading and indexing files (e.g. Annual Reports, Corporate Guides) into specific stores.
- Viewing and deleting files within stores.
"""

import datetime
import logging
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Dict, List, Optional

from src.core.rag_services import FileService, VectorStoreService
from src.ui.styles import UI_FONTS

logger = logging.getLogger(__name__)


class RAGManagementWindow(tk.Toplevel):
    """
    A modal window for managing RAG Vector Stores and Files.
    Uses a Master-Detail layout.
    """

    def __init__(
        self,
        parent: tk.Tk,
        rag_service: VectorStoreService,
        file_service: FileService,
    ) -> None:
        """
        Initialize the management window.

        Args:
            parent: The parent Tk window.
            rag_service: Instance of VectorStoreService.
            file_service: Instance of FileService.
        """
        super().__init__(parent)
        self.rag_service = rag_service
        self.file_service = file_service

        self.title("ナレッジベース管理 (RAG Management)")
        self.geometry("1100x750")
        self.transient(parent)  # Set as transient window to parent
        self.grab_set()  # Make modal

        # State
        self._current_store_id: Optional[str] = None
        self._current_store_file_count: int = 0

        # UI Components (Initialized in _setup_ui)
        self._store_tree: ttk.Treeview
        self._file_tree: ttk.Treeview
        self._rename_btn: ttk.Button
        self._del_store_btn: ttk.Button
        self._upload_btn: ttk.Button
        self._delete_file_btn: ttk.Button
        self._status_var: tk.StringVar

        self._setup_ui()

        # Initial load
        self.after(100, self._refresh_stores_async)

    def _setup_ui(self) -> None:
        """Setup the UI components."""
        # Main Layout: PanedWindow (Left: Stores, Right: Files)
        paned = tk.PanedWindow(
            self, orient=tk.HORIZONTAL, sashwidth=4, sashrelief=tk.RAISED
        )
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- Left Panel: Vector Stores ---
        left_frame = ttk.LabelFrame(paned, text=" Vector Stores ", padding=5)
        paned.add(left_frame, width=450, stretch="never")

        # Treeview for Stores
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
        self._store_tree.bind("<<TreeviewSelect>>", self._on_store_select)

        # Scrollbar for Stores
        store_scroll = ttk.Scrollbar(
            left_frame, orient="vertical", command=self._store_tree.yview
        )
        store_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._store_tree.configure(yscrollcommand=store_scroll.set)

        # Left Panel Buttons (Store Management)
        btn_frame_left = ttk.Frame(left_frame)
        btn_frame_left.pack(fill=tk.X, pady=(5, 0))

        # Row 1: Actions
        row1 = ttk.Frame(btn_frame_left)
        row1.pack(fill=tk.X, pady=(0, 2))
        ttk.Button(row1, text="➕ 新規作成", command=self._create_store).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2)
        )
        self._rename_btn = ttk.Button(
            row1, text="✏️ 名前変更", command=self._rename_store, state="disabled"
        )
        self._rename_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # Row 2: Delete & Refresh
        row2 = ttk.Frame(btn_frame_left)
        row2.pack(fill=tk.X)
        self._del_store_btn = ttk.Button(
            row2, text="🗑️ 削除", command=self._delete_store, state="disabled"
        )
        self._del_store_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(
            row2, text="🔄 更新", command=self._refresh_stores_async
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # --- Right Panel: Files ---
        right_frame = ttk.LabelFrame(paned, text=" Files in Selected Store ", padding=5)
        paned.add(right_frame, stretch="always")

        # Treeview for Files
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
        self._file_tree.bind("<<TreeviewSelect>>", self._on_file_select)

        # Scrollbar for Files
        file_scroll = ttk.Scrollbar(
            right_frame, orient="vertical", command=self._file_tree.yview
        )
        file_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._file_tree.configure(yscrollcommand=file_scroll.set)

        # Right Panel Buttons (File Operations)
        btn_frame_right = ttk.Frame(right_frame)
        btn_frame_right.pack(fill=tk.X, pady=(5, 0))

        self._upload_btn = ttk.Button(
            btn_frame_right,
            text="📂 ファイルアップロード",
            command=self._handle_upload,
            state="disabled",
        )
        self._upload_btn.pack(side=tk.LEFT, padx=(0, 5))

        self._delete_file_btn = ttk.Button(
            btn_frame_right,
            text="🗑️ ファイル削除",
            command=self._delete_selected_file_async,
            state="disabled",
        )
        self._delete_file_btn.pack(side=tk.RIGHT)

        ttk.Label(
            btn_frame_right,
            text="⚠️ StoreとStorageの両方から削除されます",
            font=UI_FONTS["SMALL_MONO"],
            foreground="gray",
        ).pack(side=tk.RIGHT, padx=5)

        # --- Status Bar ---
        self._status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            self,
            textvariable=self._status_var,
            relief=tk.SUNKEN,
            font=UI_FONTS["STATUS"],
            padding=(5, 2),
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # --- Async Logic & UI Updates ---

    def _set_status(self, msg: str, busy: bool = False) -> None:
        """Update status bar and cursor."""
        self._status_var.set(msg)
        self.config(cursor="watch" if busy else "")
        self.update_idletasks()

    def _refresh_stores_async(self) -> None:
        """Fetch vector stores in background."""
        self._set_status("Loading Vector Stores...", busy=True)
        # Clear existing
        self._store_tree.delete(*self._store_tree.get_children())
        self._file_tree.delete(*self._file_tree.get_children())

        # Reset selection state
        self._current_store_id = None
        self._current_store_file_count = 0
        self._update_button_states()

        def _task() -> None:
            try:
                stores = self.rag_service.list_vector_stores()
                self.after(0, lambda: self._update_store_list(stores))
            except Exception as e:
                logger.error(f"Failed to load stores: {e}")
                self.after(0, lambda: self._set_status(f"Error: {e}"))

        threading.Thread(target=_task, daemon=True).start()

    def _update_store_list(self, stores: List[Any]) -> None:
        """Update the store treeview on main thread."""
        for s in stores:
            # Handle Pydantic model attributes
            name = s.name if s.name else "(No Name)"
            usage = f"{s.usage_bytes:,}" if hasattr(s, "usage_bytes") else "0"

            # Extract file count safely
            files_count = 0
            if hasattr(s, "file_counts"):
                # Handle Pydantic model object
                if hasattr(s.file_counts, "total"):
                    files_count = s.file_counts.total
                elif isinstance(s.file_counts, dict):
                    files_count = s.file_counts.get("total", 0)

            self._store_tree.insert(
                "", "end", values=(name, s.id, s.status, files_count, usage)
            )

        self._set_status(f"Loaded {len(stores)} Vector Stores.")
        self.config(cursor="")

    def _on_store_select(self, event: Any) -> None:
        """Handle store selection."""
        selection = self._store_tree.selection()
        if not selection:
            self._current_store_id = None
            self._current_store_file_count = 0
            self._update_button_states()
            return

        item = self._store_tree.item(selection[0])
        store_id = item["values"][1]
        file_count = item["values"][3]

        self._current_store_id = store_id
        self._current_store_file_count = int(file_count) if file_count else 0

        self._update_button_states()
        self._refresh_files_async(store_id)

    def _update_button_states(self) -> None:
        """Enable/Disable buttons based on selection."""
        has_selection = self._current_store_id is not None

        state = "normal" if has_selection else "disabled"
        if self._rename_btn:
            self._rename_btn.config(state=state)
        if self._del_store_btn:
            self._del_store_btn.config(state=state)
        if self._upload_btn:
            self._upload_btn.config(state=state)

        # File delete button depends on file selection, not store selection
        if not has_selection:
            self._file_tree.delete(*self._file_tree.get_children())
            if self._delete_file_btn:
                self._delete_file_btn.config(state="disabled")

    # --- Store Operations ---

    def _create_store(self) -> None:
        """Create a new vector store."""
        name = simpledialog.askstring("新規作成", "Vector Storeの名前を入力してください:")
        if not name:
            return

        self._set_status("Creating store...", busy=True)

        def _task() -> None:
            try:
                self.rag_service.create_vector_store(name=name)
                self.after(0, lambda: self._set_status(f"Created store '{name}'."))
                self.after(0, self._refresh_stores_async)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
                self.after(0, lambda: self._set_status("Create failed."))

        threading.Thread(target=_task, daemon=True).start()

    def _rename_store(self) -> None:
        """Rename the selected store."""
        if not self._current_store_id:
            return

        selection = self._store_tree.selection()
        current_name = self._store_tree.item(selection[0])["values"][0]

        new_name = simpledialog.askstring(
            "名前変更", "新しい名前を入力してください:", initialvalue=current_name
        )
        if not new_name or new_name == current_name:
            return

        self._set_status("Renaming...", busy=True)

        def _task() -> None:
            try:
                self.rag_service.update_vector_store(self._current_store_id, new_name)
                self.after(0, lambda: self._set_status("Rename successful."))
                self.after(0, self._refresh_stores_async)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
                self.after(0, lambda: self._set_status("Rename failed."))

        threading.Thread(target=_task, daemon=True).start()

    def _delete_store(self) -> None:
        """Delete the selected store (Safe)."""
        if not self._current_store_id:
            return

        # Safety Check: Prevent deletion if files exist
        if self._current_store_file_count > 0:
            messagebox.showwarning(
                "削除できません",
                f"このStoreには {self._current_store_file_count} 個のファイルが含まれています。\n"
                "削除する前に、Store内のすべてのファイルを削除してください。",
            )
            return

        confirm = messagebox.askyesno(
            "削除確認",
            f"Vector Store '{self._current_store_id}' を削除してもよろしいですか？",
        )
        if not confirm:
            return

        self._set_status("Deleting store...", busy=True)

        def _task() -> None:
            try:
                self.rag_service.delete_vector_store(self._current_store_id)
                self.after(0, lambda: self._set_status("Store deleted."))
                self.after(0, self._refresh_stores_async)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
                self.after(0, lambda: self._set_status("Delete failed."))

        threading.Thread(target=_task, daemon=True).start()

    # --- File Operations ---

    def _handle_upload(self) -> None:
        """Upload a file to the selected store."""
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
        if not file_path:
            return

        self._set_status(f"Uploading {file_path}...", busy=True)
        if self._upload_btn:
            self._upload_btn.config(state="disabled")

        def _task() -> None:
            try:
                # 1. Upload File
                self._set_status_threadsafe("Uploading file to OpenAI...")
                file_obj = self.file_service.upload_file(file_path)

                # 2. Add to Store (Batch)
                self._set_status_threadsafe("Indexing file in Vector Store...")
                batch = self.rag_service.create_file_batch(
                    self._current_store_id, [file_obj.id]
                )

                # 3. Poll for completion
                self.rag_service.poll_batch_status(self._current_store_id, batch.id)

                # Success
                self.after(
                    0,
                    lambda: self._set_status(
                        f"Successfully uploaded {file_obj.filename}."
                    ),
                )
                # Refresh both files and store list (to update file counts)
                self.after(0, lambda: self._refresh_files_async(self._current_store_id))
                self.after(0, self._refresh_stores_async)

            except Exception as e:
                logger.error(f"Upload failed: {e}")
                self.after(0, lambda: messagebox.showerror("Upload Failed", str(e)))
                self.after(0, lambda: self._set_status("Upload failed."))
            finally:
                if self._upload_btn:
                    self.after(0, lambda: self._upload_btn.config(state="normal"))

        threading.Thread(target=_task, daemon=True).start()

    def _set_status_threadsafe(self, msg: str) -> None:
        self.after(0, lambda: self._set_status(msg, busy=True))

    def _refresh_files_async(self, store_id: Optional[str]) -> None:
        """Fetch files for the selected store in background."""
        if not store_id:
            return

        self._file_tree.delete(*self._file_tree.get_children())
        if self._delete_file_btn:
            self._delete_file_btn.config(state="disabled")
        self._set_status(f"Loading files for {store_id}...", busy=True)

        def _task() -> None:
            try:
                # 1. Get file objects from Vector Store (list of VectorStoreFile)
                vs_files = self.rag_service.list_files_in_store(store_id)
                if not vs_files:
                    self.after(
                        0,
                        lambda: self._update_file_ui(
                            [], f"No files found in {store_id}."
                        ),
                    )
                    return

                # 2. Fetch filenames concurrently using the FileService helper
                file_details: List[Dict[str, Any]] = []

                with ThreadPoolExecutor(max_workers=5) as executor:
                    # Map future to VectorStoreFile object for error context
                    future_to_vs_file = {
                        executor.submit(
                            self.file_service.get_file_details, f.id
                        ): f
                        for f in vs_files
                    }

                    for future in as_completed(future_to_vs_file):
                        vs_file = future_to_vs_file[future]
                        try:
                            f_obj = future.result()
                            if f_obj:
                                file_details.append(
                                    {
                                        "id": f_obj.id,
                                        "filename": f_obj.filename,
                                        "created_at": f_obj.created_at,
                                    }
                                )
                            else:
                                logger.warning(f"File details not found for {vs_file.id}")
                                file_details.append(
                                    {
                                        "id": vs_file.id,
                                        "filename": "<Unknown>",
                                        "created_at": vs_file.created_at,
                                    }
                                )
                        except Exception as e:
                            logger.warning(
                                f"Failed to fetch metadata for file {vs_file.id}: {e}"
                            )
                            file_details.append(
                                {
                                    "id": vs_file.id,
                                    "filename": "<Error>",
                                    "created_at": vs_file.created_at,
                                }
                            )

                self.after(0, lambda: self._update_file_list(file_details))

            except Exception as e:
                logger.error(f"Failed to load files: {e}")
                self.after(0, lambda: self._set_status(f"Error loading files: {e}"))

        threading.Thread(target=_task, daemon=True).start()

    def _update_file_ui(self, files: List[dict], msg: str) -> None:
        """Helper to update UI with empty list or error."""
        self._set_status(msg)
        self.config(cursor="")

    def _update_file_list(self, files: List[dict]) -> None:
        """Update file treeview."""
        # Sort by creation time desc
        files.sort(key=lambda x: x["created_at"], reverse=True)

        for f in files:
            dt_str = datetime.datetime.fromtimestamp(f["created_at"]).strftime(
                "%Y-%m-%d %H:%M"
            )
            self._file_tree.insert(
                "", "end", values=(f["filename"], f["id"], dt_str)
            )

        self._set_status(f"Loaded {len(files)} files.")
        self.config(cursor="")

    def _on_file_select(self, event: Any) -> None:
        """Enable delete button when file selected."""
        if self._file_tree.selection():
            if self._delete_file_btn:
                self._delete_file_btn.config(state="normal")
        else:
            if self._delete_file_btn:
                self._delete_file_btn.config(state="disabled")

    def _delete_selected_file_async(self) -> None:
        """Execute deletion workflow."""
        selection = self._file_tree.selection()
        if not selection or not self._current_store_id:
            return

        item = self._file_tree.item(selection[0])
        filename, file_id, _ = item["values"]

        confirm = messagebox.askyesno(
            "削除確認",
            f"以下のファイルを削除してもよろしいですか？\n\n{filename}\n({file_id})\n\n"
            "警告: この操作は Vector Store からの削除だけでなく、ファイル実体も完全に削除します。",
        )
        if not confirm:
            return

        self._set_status(f"Deleting {filename}...", busy=True)
        if self._delete_file_btn:
            self._delete_file_btn.config(state="disabled")

        def _task() -> None:
            try:
                # 1. Remove from Vector Store Index
                self.rag_service.delete_file_from_store(self._current_store_id, file_id)
                logger.info(f"Removed {file_id} from store {self._current_store_id}")

                # 2. Delete actual file entity
                self.file_service.delete_file(file_id)
                logger.info(f"Deleted file entity {file_id}")

                self.after(
                    0, lambda: self._on_delete_success(store_id=self._current_store_id)
                )
            except Exception as e:
                logger.error(f"Deletion failed: {e}")
                self.after(0, lambda: messagebox.showerror("Deletion Failed", str(e)))
                self.after(0, lambda: self._set_status("Deletion failed."))
                if self._delete_file_btn:
                    self.after(0, lambda: self._delete_file_btn.config(state="normal"))

        threading.Thread(target=_task, daemon=True).start()

    def _on_delete_success(self, store_id: Optional[str]) -> None:
        """Post-deletion refresh."""
        self._set_status("File deleted successfully.")
        self._refresh_files_async(store_id)
        # Also refresh store list to update counts
        self._refresh_stores_async()