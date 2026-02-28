"""
RAG管理ウィンドウ（src/ui/rag_window.py）のユニットテスト。
MVPコンポーネントの初期化を検証します。
"""

import pytest
from unittest.mock import MagicMock, patch

def test_rag_management_window_init():
    """RAGManagementWindowがRagModelとRagPresenterを正しく初期化することを検証します。"""
    
    with patch("src.ui.rag_window.RagModel") as MockModel, \
         patch("src.ui.rag_window.RagPresenter") as MockPresenter:
         
        from src.ui.rag_window import RAGManagementWindow
        import tkinter as tk
        
        root = tk.Tk()
        root.withdraw()
        
        mock_rag_service = MagicMock()
        mock_file_service = MagicMock()
        
        # 実行
        window = RAGManagementWindow(root, mock_rag_service, mock_file_service)
        
        # 検証
        MockModel.assert_called_once_with(mock_rag_service, mock_file_service)
        MockPresenter.assert_called_once_with(window, MockModel.return_value)
        
        window.destroy()
        root.destroy()