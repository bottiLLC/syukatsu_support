# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Syukatsu Support アプリのエントリーポイント。

依存関係の確認、初期状態の構築、およびFletメインループの起動を行います。
"""

import sys
from pathlib import Path

# uv run src/app.py 等で直接起動した場合でも 'src' モジュールが解決できるように
# sys.path にプロジェクトのルートディレクトリを動的に追加します。
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import flet as ft
import structlog

# Initialize logger
from src.core.logger import setup_logging
try:
    setup_logging()
except Exception:
    pass

log = structlog.get_logger()


def main(page: ft.Page) -> None:
    """
    Flet アプリケーションの起動ルーチン。
    1. ステート（AppState）の初期化
    2. UI（SyukatsuSupportApp）の生成
    """
    log.info("Application starting (Flet State-Driven Architecture)...")

    try:
        from src.state import AppState
        from src.ui import SyukatsuSupportApp

        log.info("Initializing AppState...")
        state = AppState()
        
        log.info("Initializing Flet UI...")
        SyukatsuSupportApp(page, state)

    except Exception as e:
        log.critical(f"Application failed to start: {e}", exc_info=True)
        # 起動エラー時のフォールバックUI
        page.add(
            ft.AlertDialog(
                title=ft.Text("重大なエラー", color=ft.Colors.RED),
                content=ft.Text(f"アプリケーションの起動中に予期せぬエラーが発生しました。\n\n{e}"),
                open=True
            )
        )
        page.update()

if __name__ == "__main__":
    log.info("Starting Flet app...")
    # ユーザーが見るローカルのウィンドウアプリとして構築
    ft.run(main)
