import queue
import threading
from typing import Any, Optional

from src.config.app_config import ConfigManager, UserConfig
from src.core.rag_services import FileService, VectorStoreService


class MainModel:
    """
    状態とビジネスデータを保持するメインアプリケーションモデル。
    """

    def __init__(self) -> None:
        try:
            self.user_config: UserConfig = ConfigManager.load()
        except Exception:
            self.user_config = UserConfig()

        self.is_generating: bool = False
        self.message_queue: queue.Queue[Any] = queue.Queue()
        self.cancel_event: threading.Event = threading.Event()
        self.active_thread: Optional[threading.Thread] = None

        self.rag_service: Optional[VectorStoreService] = None
        self.file_service: Optional[FileService] = None

    def save_config(self) -> None:
        """現在の設定を永続ストレージに保存します。"""
        ConfigManager.save(self.user_config)
