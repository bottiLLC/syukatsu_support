"""
RAG管理MVPパターンのためのモデル。
"""

import structlog
from typing import Optional

from src.core.rag_services import FileService, VectorStoreService

log = structlog.get_logger()

class RagModel:
    """
    RAG管理MVPパターンのためのモデル。
    ベクトルストアとファイルのための状態とサービスインスタンスを管理します。
    """

    def __init__(self, rag_service: VectorStoreService, file_service: FileService) -> None:
        self.rag_service = rag_service
        self.file_service = file_service

        self.current_store_id: Optional[str] = None
        self.current_store_file_count: int = 0
