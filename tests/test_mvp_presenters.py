"""
MVP Presenters（MainPresenterとRagPresenter）のユニットテスト。
"""

import pytest
import queue
import threading
from unittest.mock import MagicMock, patch

from src.ui.main_model import MainModel
from src.ui.main_presenter import MainPresenter
from src.ui.rag_model import RagModel
from src.ui.rag_presenter import RagPresenter


@pytest.fixture
def mock_main_view():
    view = MagicMock()
    view.prompt_mode_var.get.return_value = "default"
    view.api_key_var.get.return_value = "test_key"
    view.model_var.get.return_value = "gpt-5.2"
    view.reasoning_var.get.return_value = "medium"
    view.use_file_search_var.get.return_value = False
    return view


@pytest.fixture
def mock_main_model():
    model = MagicMock(spec=MainModel)
    model.user_config = MagicMock()
    model.user_config.api_key = "test_key"
    model.user_config.last_response_id = None
    model.is_generating = False
    model.message_queue = queue.Queue()
    model.cancel_event = threading.Event()
    return model


@pytest.mark.asyncio
async def test_main_presenter_initialization(mock_main_view, mock_main_model):
    """MainPresenterがUIの依存関係なしに初期化され、正しくバインドされることをテストします。"""
    with patch("src.ui.main_presenter.VectorStoreService") as MockVS, \
         patch("src.ui.main_presenter.FileService") as MockFS:
        
        presenter = MainPresenter(mock_main_view, mock_main_model)
        
        # コールバックがバインドされていることを検証
        assert mock_main_view.on_start_generation_callback == presenter.handle_start_generation
        assert mock_main_view.on_close_callback == presenter.handle_close
        
        # 初期状態が適用されていることを検証
        mock_main_view.set_system_prompt.assert_called_once()
        
        # サービスが初期化されていることを検証
        MockVS.assert_called_once_with("test_key")
        MockFS.assert_called_once_with("test_key")


@pytest.mark.asyncio
async def test_main_presenter_start_generation(mock_main_view, mock_main_model):
    """生成を開始するとモデルの状態とビューが適切に更新されることをテストします。"""
    with patch("src.ui.main_presenter.VectorStoreService"), \
         patch("src.ui.main_presenter.FileService"):
        
        presenter = MainPresenter(mock_main_view, mock_main_model)
        
        mock_main_view.get_user_input.return_value = "Hello"
        mock_main_view.get_system_prompt.return_value = "System Prompt"
        
        presenter.handle_start_generation()
        
        # 生成状態がビューとモデルで更新されていることを検証
        assert mock_main_model.is_generating is True
        mock_main_view.set_generation_state.assert_called_with(True)
        mock_main_view.append_log.assert_called()
        mock_main_view.clear_user_input.assert_called_once()
        assert mock_main_model.active_thread is not None
        assert mock_main_model.active_thread.is_alive()


@pytest.fixture
def mock_rag_view():
    view = MagicMock()
    return view


@pytest.fixture
def mock_rag_model():
    model = MagicMock(spec=RagModel)
    model.rag_service = MagicMock()
    model.file_service = MagicMock()
    model.current_store_id = None
    model.current_store_file_count = 0
    return model


@pytest.mark.asyncio
async def test_rag_presenter_refresh(mock_rag_view, mock_rag_model):
    """RagPresenterがVector Storeのバックグラウンドフェッチをトリガーすることをテストします。"""
    presenter = RagPresenter(mock_rag_view, mock_rag_model)
    
    # コールバックバインディングのチェック
    assert mock_rag_view.on_refresh_stores_callback == presenter.refresh_stores_async
    assert mock_rag_view.on_create_store_callback == presenter.create_store
    
    presenter.refresh_stores_async()
    
    mock_rag_view.set_status.assert_called_with("Loading Vector Stores...", busy=True)
    mock_rag_view.clear_stores.assert_called()
    assert mock_rag_model.current_store_id is None
