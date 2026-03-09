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

import tkinter as tk  # noqa: E402
from tkinter import messagebox  # noqa: E402
import structlog  # noqa: E402

# Initialize logger
from src.core.logger import setup_logging  # noqa: E402
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

    # [NEW] スプラッシュスクリーンの表示
    splash = tk.Tk()
    splash.overrideredirect(True)
    splash.title("起動中")
    
    # 画面中央に配置
    width, height = 300, 100
    splash.update_idletasks()
    x = (splash.winfo_screenwidth() // 2) - (width // 2)
    y = (splash.winfo_screenheight() // 2) - (height // 2)
    splash.geometry(f"{width}x{height}+{x}+{y}")
    
    splash.configure(bg="#ffffff", relief=tk.RAISED, borderwidth=2)
    tk.Label(
        splash,
        text="就活サポートアプリ起動中...",
        font=("Helvetica", 14),
        bg="#ffffff",
        fg="#333333"
    ).pack(expand=True, fill="both")
    
    splash.update()

    try:
        from src.state import AppState
        from src.ui import SyukatsuSupportApp

        log.info("Initializing AppState...")
        state = AppState()
        
        # スプラッシュスクリーンを破棄
        splash.destroy()
        
        log.info("Initializing UI...")
        app = SyukatsuSupportApp(state)
        
        # Start event loop
        app.mainloop()

    except Exception as e:
        splash.destroy() # エラー時も破棄
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
