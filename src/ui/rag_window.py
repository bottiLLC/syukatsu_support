"""
RAG Management Window module for the Job Hunting Support Application (MVP Factory).

This module provides a dedicated interface for managing Vector Stores and
their associated files. Converted to MVP architecture.
"""

import logging
import tkinter as tk

from src.core.rag_services import FileService, VectorStoreService
from src.ui.rag_model import RagModel
from src.ui.rag_view import RagView
from src.ui.rag_presenter import RagPresenter

logger = logging.getLogger(__name__)

class RAGManagementWindow(RagView):
    """
    Factory for the RAG Management MVP pattern.
    Inherits from RagView for backwards compatibility with GUI module calling flow,
    but internally orchestrates the MVP instances.
    """

    def __init__(
        self,
        parent: tk.Tk,
        rag_service: VectorStoreService,
        file_service: FileService,
    ) -> None:
        # Initialize the view
        super().__init__(parent)
        
        # Initialize the model and presenter
        self.model = RagModel(rag_service, file_service)
        self.presenter = RagPresenter(self, self.model)