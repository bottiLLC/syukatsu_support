"""RAG ナレッジベース管理ダイアログ UI モジュール。

Vector Store の一覧表示、新規作成、名前変更、削除、およびファイルアップロード/削除ダイアログを提供します。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import flet as ft
import structlog
from openai.types.vector_store import VectorStore

from src.application.usecases.rag_usecase import RAGUseCase

log = structlog.get_logger()


async def show_rag_manager(
    page: ft.Page,
    rag_usecase: RAGUseCase,
    on_close_refresh: Callable[[], Awaitable[None]] | None = None,
) -> None:
    """RAG管理ダイアログを表示し、Vector Storeおよびファイルの操作を提供します。"""
    current_store_id: str | None = None
    current_store_file_count: int = 0
    selected_file_id: str | None = None

    status_text = ft.Text("Ready", size=12)

    # --- UI Components ---

    store_table = ft.DataTable(
        columns=[
            ft.DataColumn(label=ft.Text("Name")),
            ft.DataColumn(label=ft.Text("ID")),
            ft.DataColumn(label=ft.Text("Status")),
            ft.DataColumn(label=ft.Text("Files")),
            ft.DataColumn(label=ft.Text("Bytes")),
        ],
        rows=[],
        show_checkbox_column=True,
    )

    file_table = ft.DataTable(
        columns=[
            ft.DataColumn(label=ft.Text("Filename")),
            ft.DataColumn(label=ft.Text("ID")),
            ft.DataColumn(label=ft.Text("Created")),
        ],
        rows=[],
        show_checkbox_column=True,
    )

    rename_store_btn = ft.ElevatedButton("✏️ 名前変更", disabled=True)
    del_store_btn = ft.ElevatedButton("🗑️ 削除", disabled=True)
    upload_file_btn = ft.ElevatedButton("📂 アップロード", disabled=True)
    del_file_btn = ft.ElevatedButton("🗑️ ファイル削除", disabled=True)
    create_store_btn = ft.ElevatedButton("➕ 新規作成", expand=True)

    def set_status(msg: str) -> None:
        """ステータスメッセージを更新して画面再描画します。"""
        status_text.value = msg
        page.update()

    async def _on_store_select(e: ft.ControlEvent) -> None:
        """Vector Store テーブルの行選択イベントを処理します。"""
        nonlocal current_store_id, current_store_file_count

        selected_row: ft.DataRow = e.control
        is_selected = str(e.data).lower() == "true"

        for row in store_table.rows:
            if row == selected_row:
                row.selected = is_selected
            else:
                row.selected = False

        if is_selected and isinstance(selected_row.cells[1].content, ft.Text):
            current_store_id = selected_row.cells[1].content.value
            count_val = (
                selected_row.cells[3].content.value if isinstance(selected_row.cells[3].content, ft.Text) else "0"
            )
            current_store_file_count = int(count_val or 0)
        else:
            current_store_id = None
            current_store_file_count = 0

        _update_store_buttons()
        if current_store_id:
            await _refresh_files(current_store_id)
        else:
            file_table.rows.clear()
        page.update()

    async def _on_file_select(e: ft.ControlEvent) -> None:
        """ファイル一覧テーブルの選択イベントを処理します。"""
        nonlocal selected_file_id
        selected_row: ft.DataRow = e.control
        is_selected = str(e.data).lower() == "true"

        for row in file_table.rows:
            if row == selected_row:
                row.selected = is_selected
            else:
                row.selected = False

        if is_selected and isinstance(selected_row.cells[1].content, ft.Text):
            selected_file_id = selected_row.cells[1].content.value
        else:
            selected_file_id = None

        del_file_btn.disabled = selected_file_id is None
        page.update()

    def _update_store_buttons() -> None:
        """選択状態に応じて操作ボタンの活性/非活性を切り替えます。"""
        has_sel = current_store_id is not None
        rename_store_btn.disabled = not has_sel
        del_store_btn.disabled = not has_sel
        upload_file_btn.disabled = not has_sel
        if not has_sel:
            del_file_btn.disabled = True

    async def _refresh_stores(e: ft.ControlEvent | None = None) -> None:
        """最新の Vector Store 一覧を取得してテーブルを再描画します。"""
        nonlocal current_store_id, current_store_file_count
        set_status("Loading Vector Stores...")
        try:
            stores: list[VectorStore] = await rag_usecase.list_vector_stores()
            rows: list[ft.DataRow] = []
            found_current = False
            for s in stores:
                name = getattr(s, "name", "(No Name)")
                usage = f"{getattr(s, 'usage_bytes', 0):,}"
                files_count = getattr(getattr(s, "file_counts", None), "total", 0)
                is_sel = str(s.id) == current_store_id
                if is_sel:
                    found_current = True

                rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(name)),
                            ft.DataCell(ft.Text(s.id)),
                            ft.DataCell(ft.Text(getattr(s, "status", ""))),
                            ft.DataCell(ft.Text(str(files_count))),
                            ft.DataCell(ft.Text(usage)),
                        ],
                        selected=is_sel,
                        on_select_change=_on_store_select,
                    )
                )
            store_table.rows = rows
            if not found_current:
                current_store_id = None
                current_store_file_count = 0
                file_table.rows.clear()
            else:
                if current_store_id:
                    await _refresh_files(current_store_id)
            _update_store_buttons()
            set_status(f"Loaded {len(stores)} Vector Stores.")
        except Exception as err:
            set_status(f"Error: {err}")
        page.update()

    async def _refresh_files(store_id: str) -> None:
        """選択された Vector Store 内のファイル一覧を取得してテーブルを再描画します。"""
        nonlocal selected_file_id
        set_status(f"Loading files for {store_id}...")
        try:
            files: list[dict[str, Any]] = await rag_usecase.list_files_in_store(store_id)
            if not files:
                set_status("No files found.")
                file_table.rows.clear()
            else:
                files.sort(key=lambda x: int(x.get("created_at", 0)), reverse=True)
                rows: list[ft.DataRow] = []
                for f in files:
                    created_timestamp = int(f.get("created_at", 0))
                    dt_str = datetime.fromtimestamp(created_timestamp, tz=UTC).astimezone().strftime("%Y-%m-%d %H:%M")
                    rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(ft.Text(str(f.get("filename", "")))),
                                ft.DataCell(ft.Text(str(f.get("id", "")))),
                                ft.DataCell(ft.Text(dt_str)),
                            ],
                            on_select_change=_on_file_select,
                        )
                    )
                file_table.rows = rows
                set_status(f"Loaded {len(files)} files.")
        except Exception as err:
            set_status(f"Error loading files: {err}")

        selected_file_id = None
        del_file_btn.disabled = True
        page.update()

    async def _on_delete_store(e: ft.ControlEvent) -> None:
        """選択された Vector Store の削除確認モーダルを表示します。"""
        if not current_store_id:
            return
        if current_store_file_count > 0:
            set_status("ファイルが登録されているVector Storeは削除できません。")
            return

        def confirm_del(ev: ft.ControlEvent) -> None:
            page.run_task(_do_delete, dlg_modal)

        async def _do_delete(modal: ft.AlertDialog) -> None:
            modal.open = False
            page.update()
            set_status("Deleting Vector Store...")
            try:
                if current_store_id:
                    await rag_usecase.delete_vector_store(current_store_id)
                await _refresh_stores()
                set_status("Deleted Vector Store.")
            except Exception as err:
                set_status(f"Error: {err}")

        def cancel_del(ev: ft.ControlEvent) -> None:
            dlg_modal.open = False
            page.update()

        actions_list: list[ft.Control] = [
            ft.TextButton("はい", on_click=confirm_del),
            ft.TextButton("いいえ", on_click=cancel_del),
        ]
        dlg_modal = ft.AlertDialog(
            title=ft.Text("確認"),
            content=ft.Text("本当にこのVector Storeを削除しますか？"),
            actions=actions_list,
        )
        page.overlay.append(dlg_modal)
        dlg_modal.open = True
        page.update()

    async def _on_rename_store(e: ft.ControlEvent) -> None:
        """Vector Store 名称変更モーダルを表示します。"""
        if not current_store_id:
            return

        name_field = ft.TextField(label="新しい名前", autofocus=True)

        def save_name(ev: ft.ControlEvent) -> None:
            page.run_task(_do_rename, dlg_modal, name_field.value or "")

        async def _do_rename(modal: ft.AlertDialog, new_name: str) -> None:
            modal.open = False
            page.update()
            if not new_name.strip():
                return
            set_status("Renaming Vector Store...")
            try:
                if current_store_id:
                    await rag_usecase.update_vector_store_name(current_store_id, new_name.strip())
                await _refresh_stores()
                set_status("Renamed Vector Store.")
            except Exception as err:
                set_status(f"Error: {err}")

        def cancel_dlg(ev: ft.ControlEvent) -> None:
            dlg_modal.open = False
            page.update()

        actions_list: list[ft.Control] = [
            ft.TextButton("保存", on_click=save_name),
            ft.TextButton("キャンセル", on_click=cancel_dlg),
        ]
        dlg_modal = ft.AlertDialog(
            title=ft.Text("名前変更"),
            content=name_field,
            actions=actions_list,
        )
        page.overlay.append(dlg_modal)
        dlg_modal.open = True
        page.update()

    async def _on_create_store(e: ft.ControlEvent) -> None:
        """新規 Vector Store 作成モーダルを表示します。"""
        name_field = ft.TextField(label="Vector Store名", autofocus=True)

        def save_name(ev: ft.ControlEvent) -> None:
            page.run_task(_do_create, dlg_modal, name_field.value or "")

        async def _do_create(modal: ft.AlertDialog, new_name: str) -> None:
            modal.open = False
            page.update()
            if not new_name.strip():
                return
            set_status("Creating Vector Store...")
            try:
                await rag_usecase.create_vector_store(new_name.strip())
                await _refresh_stores()
                set_status("Created Vector Store.")
            except Exception as err:
                set_status(f"Error: {err}")

        def cancel_dlg(ev: ft.ControlEvent) -> None:
            dlg_modal.open = False
            page.update()

        actions_list: list[ft.Control] = [
            ft.TextButton("作成", on_click=save_name),
            ft.TextButton("キャンセル", on_click=cancel_dlg),
        ]
        dlg_modal = ft.AlertDialog(
            title=ft.Text("新規作成"),
            content=name_field,
            actions=actions_list,
        )
        page.overlay.append(dlg_modal)
        dlg_modal.open = True
        page.update()

    async def _on_upload_file(e: ft.ControlEvent) -> None:
        """ファイル選択ダイアログを開き、Vector Store へのアップロードを実行します。"""
        if not current_store_id:
            return

        async def _do_upload(file_path: str) -> None:
            set_status("Uploading file...")
            try:
                if current_store_id:
                    await rag_usecase.upload_and_index_file(file_path, current_store_id)
                await _refresh_stores()
                set_status("File uploaded.")
            except Exception as err:
                set_status(f"Error: {err}")

        file_picker = ft.FilePicker()
        files = await file_picker.pick_files(allow_multiple=False)

        if files:
            for f in files:
                if f.path:
                    page.run_task(_do_upload, f.path)

    async def _on_delete_file(e: ft.ControlEvent) -> None:
        """選択ファイル削除確認モーダルを表示します。"""
        if not current_store_id or not selected_file_id:
            return

        def confirm_del(ev: ft.ControlEvent) -> None:
            page.run_task(_do_delete, dlg_modal)

        async def _do_delete(modal: ft.AlertDialog) -> None:
            modal.open = False
            page.update()
            set_status("Deleting file...")
            try:
                if current_store_id and selected_file_id:
                    await rag_usecase.delete_file_from_store_and_storage(current_store_id, selected_file_id)
                await _refresh_stores()
                set_status("Deleted file.")
            except Exception as err:
                set_status(f"Error: {err}")

        def cancel_del(ev: ft.ControlEvent) -> None:
            dlg_modal.open = False
            page.update()

        actions_list: list[ft.Control] = [
            ft.TextButton("はい", on_click=confirm_del),
            ft.TextButton("いいえ", on_click=cancel_del),
        ]
        dlg_modal = ft.AlertDialog(
            title=ft.Text("確認"),
            content=ft.Text("本当にこのファイルを削除しますか？"),
            actions=actions_list,
        )
        page.overlay.append(dlg_modal)
        dlg_modal.open = True
        page.update()

    rename_store_btn.on_click = _on_rename_store
    del_store_btn.on_click = _on_delete_store
    upload_file_btn.on_click = _on_upload_file
    del_file_btn.on_click = _on_delete_file
    create_store_btn.on_click = _on_create_store

    # Layout Construction
    left_panel = ft.Column(
        [
            ft.Row(
                [
                    ft.Text("Vector Stores", size=16, weight=ft.FontWeight.BOLD),
                    ft.IconButton(icon=ft.Icons.REFRESH, on_click=_refresh_stores),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Container(
                content=ft.Column([ft.Row([store_table], scroll=ft.ScrollMode.ALWAYS)], scroll=ft.ScrollMode.ALWAYS),
                expand=True,
                border=ft.border.all(1, ft.Colors.GREY_300),
            ),
            ft.Row([create_store_btn, rename_store_btn, del_store_btn]),
        ],
        expand=True,
    )

    right_panel = ft.Column(
        [
            ft.Text("Files in Selected Store", size=16, weight=ft.FontWeight.BOLD),
            ft.Container(
                content=ft.Column([ft.Row([file_table], scroll=ft.ScrollMode.ALWAYS)], scroll=ft.ScrollMode.ALWAYS),
                expand=True,
                border=ft.border.all(1, ft.Colors.GREY_300),
            ),
            ft.Row([upload_file_btn, del_file_btn]),
        ],
        expand=True,
    )

    content = ft.Container(
        width=1000,
        height=600,
        content=ft.Column(
            [
                ft.Row([left_panel, ft.VerticalDivider(), right_panel], expand=True),
                ft.Divider(),
                status_text,
            ]
        ),
    )

    def close_dlg(e: ft.ControlEvent) -> None:
        dlg.open = False
        page.update()
        if on_close_refresh:
            page.run_task(on_close_refresh)

    dlg = ft.AlertDialog(
        title=ft.Row(
            [
                ft.Text("ナレッジベース管理 (RAG Management)"),
                ft.IconButton(icon=ft.Icons.CLOSE, on_click=close_dlg),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        content=content,
    )

    page.overlay.append(dlg)
    dlg.open = True
    page.update()

    # Initial load
    await _refresh_stores()
