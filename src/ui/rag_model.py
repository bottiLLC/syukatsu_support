"""
Model for the RAG Management MVP pattern.
"""

import logging
from typing import Optional

from src.core.rag_services import FileService, VectorStoreService

logger = logging.getLogger(__name__)

class RagModel:
    """
    Model for the RAG Management MVP pattern.
    Manages state and service instances for vector stores and files.
    """

    def __init__(self, rag_service: VectorStoreService, file_service: FileService) -> None:
        self.rag_service = rag_service
        self.file_service = file_service

        self.current_store_id: Optional[str] = None
        self.current_store_file_count: int = 0
