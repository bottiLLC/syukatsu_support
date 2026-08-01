# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# 
# Safe Resource Path Resolver for PyInstaller (_MEIPASS) and Local Execution.

import sys
from pathlib import Path
from typing import Union


def get_resource_path(relative_path: Union[str, Path]) -> Path:
    """
    PyInstaller実行時 (sys._MEIPASS) と通常開発時 (ローカルパス) の
    両方で正しくリソース絶対パスを取得する共通ヘルパー関数。

    Args:
        relative_path: プロジェクトルートからの相対パス (例: "system_prompts.json")

    Returns:
        Path: 解決された絶対パス
    """
    if hasattr(sys, '_MEIPASS'):
        base_path = Path(sys._MEIPASS)
    else:
        # src/core/utils.py から見てプロジェクトルートは親の親の親ディレクトリ
        base_path = Path(__file__).resolve().parent.parent.parent

    return (base_path / relative_path).resolve()
