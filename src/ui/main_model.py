import queue
import threading
from typing import Any, Optional

from src.config.app_config import ConfigManager, UserConfig
from src.core.rag_services import FileService, VectorStoreService


class MainModel:
    """
    Main application model holding state and business data.
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
        """Saves current configuration to persistent storage."""
        ConfigManager.save(self.user_config)
