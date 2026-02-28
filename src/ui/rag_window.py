"""
就活サポートアプリケーション（MVPファクトリー）のためのRAG管理ウィンドウモジュール。

このモジュールは、Vector Storeおよびそれらに関連付けられたファイルを管理するための
専用インターフェースを提供します。MVPアーキテクチャに変換されています。
"""

import structlog
import tkinter as tk

from src.core.rag_services import FileService, VectorStoreService
from src.ui.rag_model import RagModel
from src.ui.rag_view import RagView
from src.ui.rag_presenter import RagPresenter

log = structlog.get_logger()

class RAGManagementWindow(RagView):
    """
    RAG管理MVPパターンのためのファクトリー。
    GUIモジュールの呼び出しフローとの後方互換性のためにRagViewを継承していますが、
    内部的にはMVPインスタンスをオーケストレーションします。
    """

    def __init__(
        self,
        parent: tk.Tk,
        rag_service: VectorStoreService,
        file_service: FileService,
    ) -> None:
        # ビューを初期化
        super().__init__(parent)
        
        # モデルとプレゼンターを初期化
        self.model = RagModel(rag_service, file_service)
        self.presenter = RagPresenter(self, self.model)