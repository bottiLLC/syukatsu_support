"""
依存関係の検証モジュール（src/config/dependencies.py）のユニットテスト。
"""

from unittest.mock import patch
from src.config.dependencies import check_dependencies, REQUIRED_PACKAGES

class TestDependencyCheck:
    """
    実行時の依存関係チェックロジックをテストします。
    """

    def test_all_packages_present(self):
        """
        すべてのパッケージがインポート可能であれば、エラーが発生せずアプリケーションが続行されることを検証します。
        """
        # テスト環境自体にパッケージがあることを前提とするか、
        # 常に成功するように __import__ をモックします。
        with patch("builtins.__import__") as mock_import:
            check_dependencies()
            
            # 必要なすべてのパッケージをインポートしようとしたことを検証します。
            for pkg in REQUIRED_PACKAGES:
                mock_import.assert_any_call(pkg)

    def test_missing_package_exits_app(self):
        """
        不足しているパッケージがエラーダイアログをトリガーし、sys.exit(1) を実行することを検証します。
        """
        # 'tenacity' が不足している状況をシミュレート
        original_import = __import__
        
        def mock_import_side_effect(name, *args, **kwargs):
            if name == "tenacity":
                raise ImportError("No module named 'tenacity'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import_side_effect):
            with patch("tkinter.messagebox.showerror") as mock_showerror:
                with patch("tkinter.Tk") as mock_tk:
                    with patch("sys.exit") as mock_exit:
                        with patch("src.config.dependencies.log") as mock_logger:
                            
                            check_dependencies()
                            
                            # 1. 致命的なエラーの記録
                            mock_logger.critical.assert_called()
                        
                        # 2. GUIアラートの表示
                        mock_showerror.assert_called_once()
                        title, msg = mock_showerror.call_args[0]
                        assert "Dependency Error" in title
                        assert "pip install" in msg
                        assert "tenacity" in msg
                        
                        # 3. 終了
                        mock_exit.assert_called_once_with(1)

    def test_required_packages_list_integrity(self):
        """
        リファクタリングされたアプリの主要なライブラリが必須要件リストに含まれていることを確認します。
        """
        assert "tenacity" in REQUIRED_PACKAGES
        assert "openai" in REQUIRED_PACKAGES
        assert "pydantic" in REQUIRED_PACKAGES