"""
Syukatsu Support アプリのエントリーポイント。

依存関係の確認、初期状態の構築、およびTkinterメインループの起動を行います。
"""

import sys
from pathlib import Path

# uv run src/app.py 等で直接起動した場合でも 'src' モジュールが解決できるように
# sys.path にプロジェクトのルートディレクトリを動的に追加します。
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import tkinter as tk
from tkinter import messagebox
import structlog

# Initialize logger
from src.core.logger import setup_logging
# Using fallback since it might not exist yet, ignoring for now
try:
    setup_logging()
except Exception:
    pass

log = structlog.get_logger()


def main() -> None:
    """
    アプリケーションの起動ルーチン。
    1. ロギングの設定
    2. ステート（App State）の初期化
    3. UI（SyukatsuSupportApp）の生成
    4. Tkinterメインループ開始
    """
    log.info("Application starting (Refactored State-Driven Architecture)...")

    try:
        from src.state import AppState
        from src.ui import SyukatsuSupportApp

        log.info("Initializing AppState...")
        state = AppState()
        
        log.info("Initializing UI...")
        app = SyukatsuSupportApp(state)
        
        # Start event loop
        app.mainloop()

    except Exception as e:
        log.critical(f"Application failed to start: {e}", exc_info=True)
        
        try:
            if not tk._default_root:
                tk.Tk().withdraw()
        except Exception:
            pass

        messagebox.showerror(
            "重大なエラー",
            f"アプリケーションの起動中に予期せぬエラーが発生しました。\n\n{e}",
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
