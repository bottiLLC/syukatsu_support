import asyncio
import datetime
import structlog
import threading
from typing import Any, Dict, List, Optional

from src.ui.rag_model import RagModel
from src.ui.rag_view import RagView

log = structlog.get_logger()

class RagPresenter:
    """
    RAG管理MVPパターンのためのPresenterコンポーネント。
    async/awaitを使用して、Vector Storeとファイル管理のビジネスロジックを処理します。
    """

    def __init__(self, view: RagView, model: RagModel) -> None:
        self.view = view
        self.model = model

        self._bind_callbacks()

        # Initial data load
        self.view.after(100, self.refresh_stores_async)

    def _bind_callbacks(self) -> None:
        self.view.on_refresh_stores_callback = self.refresh_stores_async
        self.view.on_store_select_callback = self.handle_store_select
        self.view.on_create_store_callback = self.create_store
        self.view.on_rename_store_callback = self.rename_store
        self.view.on_delete_store_callback = self.delete_store
        self.view.on_upload_file_callback = self.upload_file
        self.view.on_delete_file_callback = self.delete_file_async
        self.view.on_file_select_callback = self.handle_file_select

    def refresh_stores_async(self) -> None:
        self.view.set_status("Loading Vector Stores...", busy=True)
        self.view.clear_stores()

        self.model.current_store_id = None
        self.model.current_store_file_count = 0
        self.view.update_button_states(False)

        async def _async_task() -> None:
            try:
                stores = await self.model.rag_service.list_vector_stores()
                self.view.after(0, lambda: self._update_store_list(stores))
            except Exception as e:
                log.error("Failed to load stores", error=str(e))
                self.view.after(0, lambda err=e: self.view.set_status(f"Error: {err}"))

        def _thread_target() -> None:
            asyncio.run(_async_task())

        threading.Thread(target=_thread_target, daemon=True).start()

    def _update_store_list(self, stores: List[Any]) -> None:
        for s in stores:
            name = s.name if s.name else "(No Name)"
            usage = f"{s.usage_bytes:,}" if hasattr(s, "usage_bytes") else "0"

            files_count = 0
            if hasattr(s, "file_counts"):
                if hasattr(s.file_counts, "total"):
                    files_count = s.file_counts.total
                elif isinstance(s.file_counts, dict):
                    files_count = s.file_counts.get("total", 0)

            self.view.add_store(name, s.id, s.status, files_count, usage)

        self.view.set_status(f"Loaded {len(stores)} Vector Stores.")

    def handle_store_select(self, store_id: Optional[str], file_count: int) -> None:
        self.model.current_store_id = store_id
        self.model.current_store_file_count = file_count

        self.view.update_button_states(store_id is not None)
        if store_id:
            self.refresh_files_async(store_id)

    def handle_file_select(self, has_selection: bool) -> None:
        state = "normal" if has_selection else "disabled"
        self.view.set_delete_file_btn_state(state)

    def create_store(self, name: str) -> None:
        self.view.set_status("Creating store...", busy=True)

        async def _async_task() -> None:
            try:
                await self.model.rag_service.create_vector_store(name=name)
                self.view.after(0, lambda: self.view.set_status(f"Created store '{name}'."))
                self.view.after(0, self.refresh_stores_async)
            except Exception as e:
                self.view.after(0, lambda err=e: self.view.show_error("Error", str(err)))
                self.view.after(0, lambda: self.view.set_status("Create failed."))

        def _thread_target() -> None:
            asyncio.run(_async_task())

        threading.Thread(target=_thread_target, daemon=True).start()

    def rename_store(self, store_id: str, new_name: str) -> None:
        self.view.set_status("Renaming...", busy=True)

        async def _async_task() -> None:
            try:
                await self.model.rag_service.update_vector_store(store_id, new_name)
                self.view.after(0, lambda: self.view.set_status("Rename successful."))
                self.view.after(0, self.refresh_stores_async)
            except Exception as e:
                self.view.after(0, lambda err=e: self.view.show_error("Error", str(err)))
                self.view.after(0, lambda: self.view.set_status("Rename failed."))

        def _thread_target() -> None:
            asyncio.run(_async_task())

        threading.Thread(target=_thread_target, daemon=True).start()

    def delete_store(self, store_id: str) -> None:
        if self.model.current_store_file_count > 0:
            self.view.show_warning(
                "削除できません",
                f"このStoreには {self.model.current_store_file_count} 個のファイルが含まれています。\n"
                "削除する前に、Store内のすべてのファイルを削除してください。",
            )
            return

        confirm = self.view.ask_yes_no(
            "削除確認",
            f"Vector Store '{store_id}' を削除してもよろしいですか？",
        )
        if not confirm:
            return

        self.view.set_status("Deleting store...", busy=True)

        async def _async_task() -> None:
            try:
                await self.model.rag_service.delete_vector_store(store_id)
                self.view.after(0, lambda: self.view.set_status("Store deleted."))
                self.view.after(0, self.refresh_stores_async)
            except Exception as e:
                self.view.after(0, lambda err=e: self.view.show_error("Error", str(err)))
                self.view.after(0, lambda: self.view.set_status("Delete failed."))

        def _thread_target() -> None:
            asyncio.run(_async_task())

        threading.Thread(target=_thread_target, daemon=True).start()

    def upload_file(self, file_path: str, store_id: str) -> None:
        self.view.set_status(f"Uploading {file_path}...", busy=True)
        self.view.set_upload_btn_state("disabled")

        async def _async_task() -> None:
            try:
                self._set_status_threadsafe("Uploading file to OpenAI...")
                file_obj = await self.model.file_service.upload_file(file_path)

                self._set_status_threadsafe("Indexing file in Vector Store...")
                batch = await self.model.rag_service.create_file_batch(store_id, [file_obj.id])

                await self.model.rag_service.poll_batch_status(store_id, batch.id)

                self.view.after(0, lambda: self.view.set_status(f"Successfully uploaded {file_obj.filename}."))
                self.view.after(0, lambda: self.refresh_files_async(store_id))
                self.view.after(0, self.refresh_stores_async)

            except Exception as e:
                log.error("Upload failed", error=str(e), file_path=file_path)
                self.view.after(0, lambda err=e: self.view.show_error("Upload Failed", str(err)))
                self.view.after(0, lambda: self.view.set_status("Upload failed."))
            finally:
                self.view.after(0, lambda: self.view.set_upload_btn_state("normal"))

        def _thread_target() -> None:
            asyncio.run(_async_task())

        threading.Thread(target=_thread_target, daemon=True).start()

    def _set_status_threadsafe(self, msg: str) -> None:
        self.view.after(0, lambda: self.view.set_status(msg, busy=True))

    def refresh_files_async(self, store_id: str) -> None:
        self.view.clear_files()
        self.view.set_status(f"Loading files for {store_id}...", busy=True)

        async def _async_task() -> None:
            try:
                vs_files = await self.model.rag_service.list_files_in_store(store_id)
                if not vs_files:
                    self.view.after(0, lambda: self.view.set_status(f"No files found in {store_id}."))
                    return

                # Limit concurrency to 10 to prevent memory/connection exhaustion
                sem = asyncio.Semaphore(10)
                
                async def fetch_detail_with_sem(f_id: str) -> Any:
                    async with sem:
                        return await self.model.file_service.get_file_details(f_id)

                tasks = [fetch_detail_with_sem(f.id) for f in vs_files]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                file_details: List[Dict[str, Any]] = []

                for vs_file, result in zip(vs_files, results):
                    if isinstance(result, Exception):
                        log.warning("Failed to fetch metadata for file, possibly deleted", file_id=vs_file.id, error=str(result))
                        continue
                    elif result:
                        file_details.append({
                            "id": result.id,
                            "filename": result.filename,
                            "created_at": result.created_at,
                        })
                    else:
                        log.warning("File details not found, skipping as it might be deleted.", file_id=vs_file.id)
                        continue

                self.view.after(0, lambda: self._update_file_list(file_details))

            except Exception as e:
                log.error("Failed to load files", error=str(e), store_id=store_id)
                self.view.after(0, lambda err=e: self.view.set_status(f"Error loading files: {err}"))

        def _thread_target() -> None:
            asyncio.run(_async_task())

        threading.Thread(target=_thread_target, daemon=True).start()

    def _update_file_list(self, files: List[dict]) -> None:
        files.sort(key=lambda x: x["created_at"], reverse=True)

        for f in files:
            dt_str = datetime.datetime.fromtimestamp(f["created_at"]).strftime("%Y-%m-%d %H:%M")
            self.view.add_file(f["filename"], f["id"], dt_str)

        self.view.set_status(f"Loaded {len(files)} files.")

    def delete_file_async(self, filename: str, file_id: str, store_id: str) -> None:
        confirm = self.view.ask_yes_no(
            "削除確認",
            f"以下のファイルを削除してもよろしいですか？\n\n{filename}\n({file_id})\n\n"
            "警告: この操作は Vector Store からの削除だけでなく、ファイル実体も完全に削除します。",
        )
        if not confirm:
            return

        self.view.set_status(f"Deleting {filename}...", busy=True)
        self.view.set_delete_file_btn_state("disabled")

        async def _async_task() -> None:
            try:
                await self.model.rag_service.delete_file_from_store(store_id, file_id)
                log.info("Removed file from store", file_id=file_id, store_id=store_id)

                await self.model.file_service.delete_file(file_id)
                log.info("Deleted file entity", file_id=file_id)

                self.view.after(0, lambda: self.on_delete_success(store_id))
            except Exception as e:
                log.error("Deletion failed", error=str(e), file_id=file_id)
                self.view.after(0, lambda err=e: self.view.show_error("Deletion Failed", str(err)))
                self.view.after(0, lambda: self.view.set_status("Deletion failed."))
                self.view.after(0, lambda: self.view.set_delete_file_btn_state("normal"))

        def _thread_target() -> None:
            asyncio.run(_async_task())

        threading.Thread(target=_thread_target, daemon=True).start()

    def on_delete_success(self, store_id: str) -> None:
        self.view.set_status("File deleted successfully.")
        self.refresh_files_async(store_id)
        self.refresh_stores_async()
