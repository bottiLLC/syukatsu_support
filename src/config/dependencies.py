"""
依存関係の検証モジュール。

このモジュールは、アプリケーションがそれらをインポートしようとする前に、
必要なすべてのサードパーティライブラリがインストールされていることを保証するためのチェックを実行します。
"""

import structlog
import sys
import tkinter as tk
from tkinter import messagebox
from typing import List

# ロガーのセットアップ
log = structlog.get_logger()

# 実行時に検証する必須パッケージのリスト
REQUIRED_PACKAGES = [
    "openai",
    "pydantic",
    "httpx",
    "cryptography",
    "dotenv",
    "tenacity",  # リトライロジック（リジリエンス）のために追加
]


def check_dependencies() -> None:
    """
    必要なすべてのサードパーティパッケージがインストールされていることを検証します。
    """
    # 【追加】PyInstallerでビルド済み(Frozen)の場合はチェックをスキップする
    if getattr(sys, 'frozen', False):
        log.info("Running in frozen mode (PyInstaller). Skipping dependency check.")
        return

    missing_packages: List[str] = []

    for package in REQUIRED_PACKAGES:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        _handle_missing_dependencies(missing_packages)


def _handle_missing_dependencies(missing_packages: List[str]) -> None:
    """
    依存関係が不足しているシナリオを処理します。

    エラーをログに記録し、アプリケーションを終了する前にグラフィカルなアラートを表示します。

    Args:
        missing_packages (List[str]): インポートに失敗したパッケージ名のリスト。
    """
    log.critical(
        "必要な依存関係が不足しています",
        missing_packages=missing_packages,
        suggested_command=f"pip install --upgrade {' '.join(missing_packages)}",
    )

    # ユーザー向けメッセージ（日本語）
    display_msg = (
        "必要なライブラリが見つかりません。\n\n"
        "以下のコマンドを実行してインストールしてください:\n"
        f"pip install --upgrade {' '.join(missing_packages)}"
    )

    _show_error_dialog("Dependency Error", display_msg)
    sys.exit(1)


def _show_error_dialog(title: str, message: str) -> None:
    """
    Tkinterのエラーメッセージボックスを安全に表示します。

    メインウィンドウがまだ作成されていない場合、メッセージボックスが
    確実に表示されるように一時的なルートウィンドウを作成します。

    Args:
        title (str): エラーウィンドウのタイトル。
        message (str): エラーメッセージの内容。
    """
    # メインアプリケーションウィンドウがまだ作成されていないため、
    # メッセージボックスを表示するための一時的なルートウィンドウを初期化します。
    try:
        # TclErrorを避けるため、すでにrootが存在するかチェックします。
        if not tk._default_root:
            root = tk.Tk()
            root.withdraw()  # メインウィンドウを非表示にする
            should_destroy = True
        else:
            root = tk._default_root
            should_destroy = False
    except Exception:
        # フォールバック
        root = tk.Tk()
        root.withdraw()
        should_destroy = True

    messagebox.showerror(title, message)

    # メッセージボックスが閉じられた後、確実にルートウィンドウを破棄します。
    if should_destroy:
        root.destroy()