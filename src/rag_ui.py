"""
RAG管理用Tkinterサブウィンドウ。

Vector Storeおよびファイルの管理UIを提供します。
UI内で直接 `OpenAIClient` を非同期実行タスクとして呼び出します。
"""

import asyncio
import datetime
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, List, Optional
import structlog

from src.infrastructure.openai_client import OpenAIClient
from src.styles import UI_FONTS

log = structlog.get_logger()


class RAGManagementWindow(tk.Toplevel):
    def __init__(self, parent: tk.Tk, client: OpenAIClient) -> None:
        super().__init__(parent)
        self.client = client
        self.title("ナレッジベース管理 (RAG Management)")
        self.geometry("1100x750")
        self.transient(parent)
        self.grab_set()

        self.status_var = tk.StringVar(value="Ready")
        self.current_store_id: Optional[str] = None
        self.current_store_file_count: int = 0

        self._setup_ui()
        
        # Initial Load
        self._refresh_stores_async()

    def _setup_ui(self) -> None:
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=4, sashrelief=tk.RAISED)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left Panel (Stores)
        left_frame = ttk.LabelFrame(paned, text=" Vector Stores ", padding=5)
        paned.add(left_frame, width=450, stretch="never")

        self.store_tree = ttk.Treeview(left_frame, columns=("name", "id", "status", "files", "usage"), show="headings", selectmode="browse")
        for col, text, width, anchor in [
            ("name", "Name", 140, "w"), ("id", "ID", 90, "w"), 
            ("status", "Status", 70, "w"), ("files", "Files", 50, "center"), 
            ("usage", "Bytes", 70, "e")
        ]:
            self.store_tree.heading(col, text=text)
            self.store_tree.column(col, width=width, anchor=anchor)

        self.store_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.store_tree.bind("<<TreeviewSelect>>", self._on_store_select)

        store_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=self.store_tree.yview)
        store_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.store_tree.configure(yscrollcommand=store_scroll.set)

        btn_left = ttk.Frame(left_frame)
        btn_left.pack(fill=tk.X, pady=(5, 0))
        
        row1 = ttk.Frame(btn_left)
        row1.pack(fill=tk.X, pady=(0, 2))
        ttk.Button(row1, text="➕ 新規作成", command=self._on_create_store).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.rename_btn = ttk.Button(row1, text="✏️ 名前変更", command=self._on_rename_store, state="disabled")
        self.rename_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        row2 = ttk.Frame(btn_left)
        row2.pack(fill=tk.X)
        self.del_store_btn = ttk.Button(row2, text="🗑️ 削除", command=self._on_delete_store, state="disabled")
        self.del_store_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row2, text="🔄 更新", command=self._refresh_stores_async).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # Right Panel (Files)
        right_frame = ttk.LabelFrame(paned, text=" Files in Selected Store ", padding=5)
        paned.add(right_frame, stretch="always")

        self.file_tree = ttk.Treeview(right_frame, columns=("filename", "id", "created"), show="headings", selectmode="browse")
        for col, text, width in [("filename", "Filename", 250), ("id", "File ID", 120), ("created", "Created", 120)]:
            self.file_tree.heading(col, text=text)
            self.file_tree.column(col, width=width)

        self.file_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.file_tree.bind("<<TreeviewSelect>>", self._on_file_select)
        
        file_scroll = ttk.Scrollbar(right_frame, orient="vertical", command=self.file_tree.yview)
        file_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_tree.configure(yscrollcommand=file_scroll.set)

        btn_right = ttk.Frame(right_frame)
        btn_right.pack(fill=tk.X, pady=(5, 0))

        self.upload_btn = ttk.Button(btn_right, text="📂 ファイルアップロード", command=self._on_upload_file, state="disabled")
        self.upload_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.del_file_btn = ttk.Button(btn_right, text="🗑️ ファイル削除", command=self._on_delete_file, state="disabled")
        self.del_file_btn.pack(side=tk.RIGHT)
        ttk.Label(btn_right, text="⚠️ StoreとStorageの両方から削除されます", font=UI_FONTS["SMALL_MONO"], foreground="gray").pack(side=tk.RIGHT, padx=5)

        ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, font=UI_FONTS["STATUS"], padding=(5, 2)).pack(side=tk.BOTTOM, fill=tk.X)

    # --- UI Helpers ---

    def set_status(self, msg: str, busy: bool = False):
        self.status_var.set(msg)
        self.config(cursor="watch" if busy else "")
        self.update_idletasks()

    def _run_thread(self, coro):
        threading.Thread(target=lambda: asyncio.run(coro), daemon=True).start()

    # --- Logic: Stores ---

    def _refresh_stores_async(self):
        self.set_status("Loading Vector Stores...", busy=True)
        self.store_tree.delete(*self.store_tree.get_children())
        self.file_tree.delete(*self.file_tree.get_children())
        self.current_store_id = None
        self.current_store_file_count = 0
        self._update_store_buttons()

        async def _fetch():
            try:
                stores = await self.client.list_vector_stores()
                self.after(0, lambda: self._render_stores(stores))
            except Exception as e:
                self.after(0, lambda err=e: self.set_status(f"Error: {err}"))

        self._run_thread(_fetch())

    def _render_stores(self, stores: List[Any]):
        for s in stores:
            name = getattr(s, "name", "(No Name)")
            usage = f"{getattr(s, 'usage_bytes', 0):,}"
            files_count = getattr(getattr(s, "file_counts", None), "total", 0)
            self.store_tree.insert("", "end", values=(name, s.id, getattr(s, "status", ""), files_count, usage))
        self.set_status(f"Loaded {len(stores)} Vector Stores.")

    def _on_store_select(self, event):
        sel = self.store_tree.selection()
        if not sel:
            self.current_store_id = None
            self._update_store_buttons()
            return
        
        vals = self.store_tree.item(sel[0])["values"]
        self.current_store_id = str(vals[1])
        self.current_store_file_count = int(vals[3]) if vals[3] else 0
        self._update_store_buttons()
        self._refresh_files_async(self.current_store_id)

    def _update_store_buttons(self):
        st = "normal" if self.current_store_id else "disabled"
        self.rename_btn.config(state=st)
        self.del_store_btn.config(state=st)
        self.upload_btn.config(state=st)
        if not self.current_store_id:
            self.file_tree.delete(*self.file_tree.get_children())
            self.del_file_btn.config(state="disabled")

    def _on_create_store(self):
        name = simpledialog.askstring("新規作成", "Vector Storeの名前を入力してください:")
        if not name: return
        self.set_status("Creating store...", busy=True)

        async def _create():
            try:
                await self.client.create_vector_store(name)
                self.after(0, lambda: self.set_status(f"Created store '{name}'."))
                self.after(0, self._refresh_stores_async)
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror("Error", str(err)))
                self.after(0, lambda: self.set_status("Create failed."))
                
        self._run_thread(_create())

    def _on_rename_store(self):
        sel = self.store_tree.selection()
        if not sel: return
        cur_name = self.store_tree.item(sel[0])["values"][0]
        new_name = simpledialog.askstring("名前変更", "新しい名前を入力してください:", initialvalue=cur_name)
        
        # Async client wrap doesnt have update_vector_store implemented correctly yet in my stub so I will use direct if possible:
        # Actually client.vector_stores.update is real API. Let's add it to wrapper or call direct
        if new_name and new_name != cur_name and self.current_store_id:
            self.set_status("Renaming...", busy=True)
            async def _rename():
                try:
                    # Calling internal directly for speed
                    async with self.client._get_client() as ac:
                        await ac.vector_stores.update(vector_store_id=self.current_store_id, name=new_name) # type: ignore
                    self.after(0, self._refresh_stores_async)
                except Exception as e:
                    self.after(0, lambda err=e: messagebox.showerror("Error", str(err)))
            self._run_thread(_rename())

    def _on_delete_store(self):
        if self.current_store_file_count > 0:
            messagebox.showwarning("削除できません", f"このStoreには {self.current_store_file_count} 個のファイルが含まれています。\n削除する前にファイルを削除してください。")
            return
        if not messagebox.askyesno("削除確認", f"Vector Store '{self.current_store_id}' を削除しますか？"):
            return
            
        self.set_status("Deleting store...", busy=True)
        async def _del():
            try:
                await self.client.delete_vector_store(self.current_store_id) # type: ignore
                self.after(0, self._refresh_stores_async)
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror("Error", str(err)))
        self._run_thread(_del())

    # --- Logic: Files ---

    def _refresh_files_async(self, store_id: str):
        self.file_tree.delete(*self.file_tree.get_children())
        self.set_status(f"Loading files for {store_id}...", busy=True)

        async def _fetch():
            try:
                vs_files = await self.client.list_files_in_store(store_id)
                if not vs_files:
                    self.after(0, lambda: self.set_status("No files found."))
                    return
                # Display files 
                file_details = []
                async with self.client._get_client() as ac:
                    for vf in vs_files:
                        try:
                            f = await ac.files.retrieve(vf.id)
                            file_details.append({"id": f.id, "filename": f.filename, "created_at": f.created_at})
                        except Exception:
                            continue

                self.after(0, lambda: self._render_files(file_details))
            except Exception as e:
                self.after(0, lambda err=e: self.set_status(f"Error loading files: {err}"))
        self._run_thread(_fetch())

    def _render_files(self, files: List[dict]):
        files.sort(key=lambda x: x["created_at"], reverse=True)
        for f in files:
            dt_str = datetime.datetime.fromtimestamp(f["created_at"]).strftime("%Y-%m-%d %H:%M")
            self.file_tree.insert("", "end", values=(f["filename"], f["id"], dt_str))
        self.set_status(f"Loaded {len(files)} files.")

    def _on_file_select(self, event):
        self.del_file_btn.config(state="normal" if self.file_tree.selection() else "disabled")

    def _on_upload_file(self):
        if not self.current_store_id: return
        file_path = filedialog.askopenfilename(filetypes=[("All Files", "*.*"), ("PDF", "*.pdf"), ("Text", "*.txt")])
        if not file_path: return

        self.set_status(f"Uploading...", busy=True)
        self.upload_btn.config(state="disabled")

        async def _up():
            try:
                f_obj = await self.client.upload_file(file_path)
                self.after(0, lambda: self.set_status("Indexing file..."))
                batch = await self.client.create_file_batch(self.current_store_id, [f_obj.id]) # type: ignore
                await self.client.poll_batch_status(self.current_store_id, batch.id) # type: ignore
                self.after(0, lambda: self._refresh_files_async(self.current_store_id)) # type: ignore
                self.after(0, self._refresh_stores_async)
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror("Error", str(err)))
            finally:
                self.after(0, lambda: self.upload_btn.config(state="normal"))
        self._run_thread(_up())

    def _on_delete_file(self):
        sel = self.file_tree.selection()
        if not sel or not self.current_store_id: return
        vals = self.file_tree.item(sel[0])["values"]
        f_name, f_id = vals[0], vals[1]

        if not messagebox.askyesno("削除確認", f"{f_name} を完全に削除しますか？"):
            return

        self.set_status("Deleting...", busy=True)
        self.del_file_btn.config(state="disabled")

        async def _delf():
            try:
                await self.client.delete_file_from_store(self.current_store_id, f_id) # type: ignore
                await self.client.delete_file(f_id)
                self.after(0, lambda s=self.current_store_id: self._refresh_files_async(s)) # type: ignore
                self.after(0, self._refresh_stores_async)
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror("Error", str(err)))
            finally:
                self.after(0, lambda: self.del_file_btn.config(state="normal"))
                
        self._run_thread(_delf())

