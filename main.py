"""
就活サポートアプリケーションのエントリーポイント。

このモジュールはSyukatsuSupportAppのブートストラップスクリプトとして機能します。
ロギングの設定、依存関係の検証、GUIの初期化をオーケストレーションします。
"""

import sys
import tkinter as tk
from tkinter import messagebox

import structlog

# Local imports
from src.config.dependencies import check_dependencies
from src.config.logging_config import setup_logging

# Initialize logger
log = structlog.get_logger()


def main() -> None:
    """
    メイン実行ルーチン。

    アプリケーションの起動シーケンスをオーケストレーションします：
    1. ロギングを設定します。
    2. 必要な依存関係をチェックします。
    3. メインGUIアプリケーションを起動します。
    """
    # 1. Setup Logging
    setup_logging()
    log.info("Application starting...")

    # 2. Check Dependencies
    # Must be done before importing modules that use these dependencies
    check_dependencies()

    try:
        # 3. Launch GUI
        # Import inside main/try block to capture import errors if dependencies fail
        # pylint: disable=import-outside-toplevel
        from src.ui.gui import SyukatsuSupportApp

        log.info("Initializing GUI...")
        app = SyukatsuSupportApp()
        app.mainloop()

    except Exception as e:
        log.critical(f"Application failed to start: {e}", exc_info=True)

        # Fallback error reporting using a temporary Tk instance if the app crashed
        # before the main window could handle the error.
        try:
            # If Tkinter hasn't been initialized or was destroyed, ensure we have a root.
            # Accessing protected member _default_root to check state.
            # pylint: disable=protected-access
            if not tk._default_root:  # type: ignore
                tk.Tk().withdraw()
        except Exception:
            # Ignore errors during fallback mechanism to ensure the message box attempt proceeds
            pass

        messagebox.showerror(
            "重大なエラー",
            f"アプリケーションの起動中に予期せぬエラーが発生しました。\n\n{e}",
        )
        sys.exit(1)


if __name__ == "__main__":
    main()