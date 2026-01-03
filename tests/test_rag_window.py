import pytest
from unittest.mock import MagicMock, patch
from contextlib import ExitStack
from concurrent.futures import Future

# テスト対象のインポート
from src.ui.rag_window import RAGManagementWindow

# --- Fixtures ---

@pytest.fixture
def mock_tk_root():
    """ルートウィンドウのモック"""
    return MagicMock()

@pytest.fixture
def mock_services():
    """RAGServiceとFileServiceのモック"""
    rag_service = MagicMock()
    file_service = MagicMock()
    return rag_service, file_service

@pytest.fixture
def rag_window_context(mock_tk_root, mock_services):
    """
    RAGManagementWindowのインスタンス化に必要なパッチを適用し、
    初期化済みのウィンドウとモックコンポーネントを返します。
    """
    rag_service, file_service = mock_services
    # 初期ロードでのエラー回避用に空リストを返すよう設定
    rag_service.list_vector_stores.return_value = []

    ui_mocks = {}

    with ExitStack() as stack:
        # 1. Toplevel（親クラス）の無効化
        stack.enter_context(patch("tkinter.Toplevel.__init__", return_value=None))
        for method in ["geometry", "title", "transient", "grab_set", "config", "wait_window", "update_idletasks"]:
            stack.enter_context(patch(f"tkinter.Toplevel.{method}"))
        
        # afterメソッドの同期実行化 (コールバックを即時実行する)
        stack.enter_context(patch("tkinter.Toplevel.after", side_effect=lambda ms, f=None, *a: f(*a) if f else "timer_id"))

        # 2. Tkinterウィジェットのモック
        ui_mocks["paned"] = stack.enter_context(patch("src.ui.rag_window.tk.PanedWindow"))
        stack.enter_context(patch("src.ui.rag_window.tk.Frame"))
        stack.enter_context(patch("src.ui.rag_window.tk.Menu"))
        stack.enter_context(patch("src.ui.rag_window.tk.Label"))
        stack.enter_context(patch("src.ui.rag_window.tk.Button"))
        stack.enter_context(patch("src.ui.rag_window.tk.StringVar"))
        stack.enter_context(patch("src.ui.rag_window.tk.BooleanVar"))

        # 3. TTKウィジェットのモック
        ui_mocks["tree"] = stack.enter_context(patch("src.ui.rag_window.ttk.Treeview"))
        ui_mocks["btn"] = stack.enter_context(patch("src.ui.rag_window.ttk.Button"))
        ui_mocks["label"] = stack.enter_context(patch("src.ui.rag_window.ttk.Label"))
        ui_mocks["labelframe"] = stack.enter_context(patch("src.ui.rag_window.ttk.LabelFrame"))
        ui_mocks["scrollbar"] = stack.enter_context(patch("src.ui.rag_window.ttk.Scrollbar"))
        ui_mocks["combobox"] = stack.enter_context(patch("src.ui.rag_window.ttk.Combobox"))
        ui_mocks["entry"] = stack.enter_context(patch("src.ui.rag_window.ttk.Entry"))
        ui_mocks["frame"] = stack.enter_context(patch("src.ui.rag_window.ttk.Frame"))

        # 4. ダイアログのモック
        ui_mocks["simpledialog"] = stack.enter_context(patch("src.ui.rag_window.simpledialog"))
        ui_mocks["messagebox"] = stack.enter_context(patch("src.ui.rag_window.messagebox"))
        ui_mocks["filedialog"] = stack.enter_context(patch("src.ui.rag_window.filedialog"))

        # 5. スレッドの同期実行化
        mock_thread = stack.enter_context(patch("src.ui.rag_window.threading.Thread"))
        mock_thread.side_effect = lambda target=None, daemon=None, args=(), **kw: MagicMock(start=lambda: target(*args) if target else None)

        # 6. ThreadPoolExecutor のモック
        mock_executor_cls = stack.enter_context(patch("src.ui.rag_window.ThreadPoolExecutor"))
        ui_mocks["executor"] = mock_executor_cls.return_value.__enter__.return_value

        # --- インスタンス化 ---
        window = RAGManagementWindow(mock_tk_root, rag_service, file_service)
        yield window, ui_mocks

# --- Test Cases ---

def test_initialization_loads_stores(mock_tk_root, mock_services):
    """[Init] 起動時にVector Storesのリストを取得し、Treeviewに反映することを確認。"""
    # このテストは setup 時の挙動を確認するため、fixtureを使わず手動でコンテキストを作成
    rag_service, file_service = mock_services
    
    # 修正: MagicMockのコンストラクタで name 引数を使うと、モックの属性ではなくデバッグ用の名前が設定されてしまうため、
    # インスタンス生成後に属性として設定するか、configure_mockを使用する。
    store1 = MagicMock(id="vs_1", status="completed", usage_bytes=1024)
    store1.name = "Manuals"
    store1.file_counts.total = 5
    rag_service.list_vector_stores.return_value = [store1]

    with ExitStack() as stack:
        # 1. Toplevelのパッチ
        stack.enter_context(patch("tkinter.Toplevel.__init__", return_value=None))
        # [修正点] after は別途コールバック実行ロジックを入れるため、ここから除外
        for method in ["geometry", "title", "transient", "grab_set", "config", "wait_window", "update_idletasks"]:
            stack.enter_context(patch(f"tkinter.Toplevel.{method}"))
        
        # [修正点] after が呼ばれたら引数の関数を実行するように side_effect を設定
        stack.enter_context(patch("tkinter.Toplevel.after", side_effect=lambda ms, f=None, *a: f(*a) if f else "timer_id"))

        # 2. tk.* のパッチ
        stack.enter_context(patch("src.ui.rag_window.tk.PanedWindow"))
        stack.enter_context(patch("src.ui.rag_window.tk.Frame"))
        stack.enter_context(patch("src.ui.rag_window.tk.Menu"))
        stack.enter_context(patch("src.ui.rag_window.tk.Label"))
        stack.enter_context(patch("src.ui.rag_window.tk.Button"))
        stack.enter_context(patch("src.ui.rag_window.tk.StringVar"))
        stack.enter_context(patch("src.ui.rag_window.tk.BooleanVar"))

        # 3. ttk.* のパッチ
        mock_tree_cls = stack.enter_context(patch("src.ui.rag_window.ttk.Treeview"))
        for widget in ["Button", "Label", "LabelFrame", "Scrollbar", "Combobox", "Entry", "Frame"]:
            stack.enter_context(patch(f"src.ui.rag_window.ttk.{widget}"))

        # 4. Thread同期化
        mock_thread = stack.enter_context(patch("src.ui.rag_window.threading.Thread"))
        mock_thread.side_effect = lambda target=None, **kw: MagicMock(start=lambda: target())
        
        # 5. Executorモック (念のため追加)
        stack.enter_context(patch("src.ui.rag_window.ThreadPoolExecutor"))

        # インスタンス化
        window = RAGManagementWindow(mock_tk_root, rag_service, file_service)

        # 検証
        rag_service.list_vector_stores.assert_called()
        window._store_tree.insert.assert_called()
        args, kwargs = window._store_tree.insert.call_args
        # kwargs.get('values') が None の場合、args[2] (第3引数) を取得する
        values = kwargs.get('values') or args[2]
        assert "Manuals" in values

def test_create_store_success(rag_window_context):
    """[Store Ops] 新規Store作成の正常系フロー。"""
    window, mocks = rag_window_context
    rag_service = window.rag_service

    mocks["simpledialog"].askstring.return_value = "New Store"

    window._create_store()

    rag_service.create_vector_store.assert_called_with(name="New Store")
    assert rag_service.list_vector_stores.call_count >= 2

def test_create_store_cancel(rag_window_context):
    """[Store Ops] キャンセル時はAPIを呼ばない。"""
    window, mocks = rag_window_context
    rag_service = window.rag_service
    
    mocks["simpledialog"].askstring.return_value = None

    window._create_store()

    rag_service.create_vector_store.assert_not_called()

def test_rename_store_success(rag_window_context):
    """[Store Ops] Store名変更。"""
    window, mocks = rag_window_context
    rag_service = window.rag_service

    window._current_store_id = "vs_123"
    window._store_tree.selection.return_value = ["item1"]
    window._store_tree.item.return_value = {"values": ["Old Name", "vs_123", "active", 0, "0"]}

    mocks["simpledialog"].askstring.return_value = "Renamed Store"

    window._rename_store()

    rag_service.update_vector_store.assert_called_with("vs_123", "Renamed Store")

def test_delete_store_safety_check(rag_window_context):
    """[Store Ops] ファイルがあるStoreは削除不可。"""
    window, mocks = rag_window_context
    rag_service = window.rag_service

    window._current_store_id = "vs_populated"
    window._current_store_file_count = 5 

    window._delete_store()

    mocks["messagebox"].showwarning.assert_called_once()
    rag_service.delete_vector_store.assert_not_called()

def test_delete_store_success(rag_window_context):
    """[Store Ops] 空のStore削除。"""
    window, mocks = rag_window_context
    rag_service = window.rag_service

    window._current_store_id = "vs_empty"
    window._current_store_file_count = 0
    mocks["messagebox"].askyesno.return_value = True

    window._delete_store()

    rag_service.delete_vector_store.assert_called_with("vs_empty")

def test_handle_upload_success(rag_window_context):
    """[File Ops] アップロード成功フロー。"""
    window, mocks = rag_window_context
    rag_service = window.rag_service
    file_service = window.file_service

    window._current_store_id = "vs_target"
    mocks["filedialog"].askopenfilename.return_value = "/doc.pdf"

    file_service.upload_file.return_value = MagicMock(id="f1", filename="doc.pdf")
    rag_service.create_file_batch.return_value = MagicMock(id="b1")

    window._handle_upload()

    file_service.upload_file.assert_called_with("/doc.pdf")
    rag_service.create_file_batch.assert_called_with("vs_target", ["f1"])
    rag_service.poll_batch_status.assert_called_with("vs_target", "b1")

def test_refresh_files_async_logic(rag_window_context):
    """[File Ops] ファイル一覧の並列取得ロジック。"""
    window, mocks = rag_window_context
    rag_service = window.rag_service
    mock_executor = mocks["executor"]

    rag_service.list_files_in_store.return_value = [
        MagicMock(id="fA"), MagicMock(id="fB")
    ]

    # Executorが返すFutureの設定
    f1 = Future(); f1.set_result(MagicMock(id="fA", filename="A.txt", created_at=100))
    f2 = Future(); f2.set_result(MagicMock(id="fB", filename="B.txt", created_at=200))
    mock_executor.submit.side_effect = [f1, f2]

    window._refresh_files_async("vs_target")

    rag_service.list_files_in_store.assert_called_with("vs_target")
    assert window._file_tree.insert.call_count == 2

def test_delete_selected_file_success(rag_window_context):
    """[File Ops] ファイル削除。"""
    window, mocks = rag_window_context
    rag_service = window.rag_service
    file_service = window.file_service

    window._current_store_id = "vs_target"
    window._file_tree.selection.return_value = ["item_f"]
    window._file_tree.item.return_value = {"values": ["t.pdf", "f99", "date"]}
    mocks["messagebox"].askyesno.return_value = True

    window._delete_selected_file_async()

    rag_service.delete_file_from_store.assert_called_with("vs_target", "f99")
    file_service.delete_file.assert_called_with("f99")

def test_on_store_select_updates_state(rag_window_context):
    """[Events] Store選択イベント。"""
    window, _ = rag_window_context
    window._refresh_files_async = MagicMock()

    window._store_tree.selection.return_value = ["i1"]
    window._store_tree.item.return_value = {"values": ["N", "vs_sel", "act", "10", "1KB"]}

    window._on_store_select(None)

    assert window._current_store_id == "vs_sel"
    window._refresh_files_async.assert_called_with("vs_sel")

def test_upload_error_handling(rag_window_context):
    """[Error] アップロードエラー時のダイアログ。"""
    window, mocks = rag_window_context
    window.file_service.upload_file.side_effect = Exception("Fail")
    
    window._current_store_id = "vs_t"
    mocks["filedialog"].askopenfilename.return_value = "bad.pdf"

    window._handle_upload()

    mocks["messagebox"].showerror.assert_called()