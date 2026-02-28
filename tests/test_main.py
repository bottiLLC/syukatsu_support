import pytest
from unittest.mock import patch, MagicMock

# Import the target module
# Note: We assume the project root is in PYTHONPATH
import main

class TestMainApplication:
    """
    アプリケーションのエントリーポイント（main.py）のテスト。
    """

    @pytest.fixture(autouse=True)
    def mock_dependencies(self):
        """
        ログ出力や実際のパッケージチェックなどの副作用を防ぐために、
        すべてのテストで外部依存関係をモックします。
        """
        with patch("main.setup_logging") as mock_log_setup, \
             patch("main.check_dependencies") as mock_check_deps, \
             patch("main.log") as mock_logger:
            
            self.mock_log_setup = mock_log_setup
            self.mock_check_deps = mock_check_deps
            self.mock_logger = mock_logger
            yield

    def test_main_success_path(self):
        """
        [正常系] 起動シーケンスが正しいことを検証します:
        Logging -> Dependencies -> GUI -> Mainloop
        """
        # main() 内部でインポートされたGUIクラスをモックします
        # main.pyはsrc.ui.guiからSyukatsuSupportAppをインポートするため、これをパッチします
        with patch("src.ui.gui.SyukatsuSupportApp") as MockApp:
            mock_app_instance = MockApp.return_value
            
            main.main()
            
            # 1. ロギング設定
            self.mock_log_setup.assert_called_once()
            
            # 2. 依存関係チェック
            self.mock_check_deps.assert_called_once()
            
            # 3. GUI初期化
            MockApp.assert_called_once()
            
            # 4. メインループ開始
            mock_app_instance.mainloop.assert_called_once()
            
            # 重大なエラーがないこと
            self.mock_logger.critical.assert_not_called()

    def test_main_startup_crash_handling(self):
        """
        [異常系] 起動中の例外処理を検証します。
        重大なエラーをログに記録し、メッセージボックスを表示して終了(exit(1))する必要があります。
        """
        # GUI初期化中のエラーをシミュレート
        error_msg = "Simulated Startup Crash"
        with patch("src.ui.gui.SyukatsuSupportApp", side_effect=RuntimeError(error_msg)):
            
            # 例外ブロックで使用されるTkinterコンポーネントをモック
            with patch("tkinter.Tk") as MockTk, \
                 patch("tkinter.messagebox.showerror") as mock_showerror, \
                 patch("tkinter._default_root", None, create=True): # rootが存在しないことをシミュレート
                
                # sys.exit(1) を期待
                with pytest.raises(SystemExit) as excinfo:
                    main.main()
                
                assert excinfo.value.code == 1
                
                # 1. ロギングの検証
                self.mock_logger.critical.assert_called_once()
                args, kwargs = self.mock_logger.critical.call_args
                
                # 標準のロギングkwargsをチェック
                assert kwargs.get("exc_info") is True
                
                # 2. フォールバック用のRoot作成の検証 (_default_rootがNoneだったため)
                # Tkインスタンスを作成し、withdraw (非表示) すること
                MockTk.assert_called_once()
                MockTk.return_value.withdraw.assert_called_once()
                
                # 3. ユーザーへの警告の検証
                mock_showerror.assert_called_once()
                call_args = mock_showerror.call_args[0]
                assert "重大なエラー" in call_args[0]
                assert error_msg in call_args[1]

    def test_main_crash_with_existing_root(self):
        """
        [異常系] Tk rootが既に存在する場合の例外処理を検証します。
        新しいTkインスタンスを作成せず、エラーを表示するはずです。
        """
        # エラーをシミュレート
        with patch("src.ui.gui.SyukatsuSupportApp", side_effect=ValueError("Config Error")):
             
             # 既存のrootをシミュレート
             mock_existing_root = MagicMock()
             
             with patch("tkinter.Tk") as MockTk, \
                  patch("tkinter.messagebox.showerror") as mock_showerror, \
                  patch("tkinter._default_root", mock_existing_root, create=True):
                 
                 with pytest.raises(SystemExit):
                     main.main()
                 
                 # rootが存在するため新しいrootを作成しないはずです
                 MockTk.assert_not_called()
                 
                 # 引き続きエラーは表示されるはずです
                 mock_showerror.assert_called()