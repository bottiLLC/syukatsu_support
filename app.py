"""就職活動サポートアプリ (SYUKATSU Support) エントリーポイント。

ルート直下のランチャーとして機能し、プロジェクトルートを sys.path に決定論的に追加した上で、
モジュラー設計された src.app:main を呼び出します。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 実行ディレクトリに依存しない決定論的モジュール解決
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import flet as ft

from src.app import main

if __name__ == "__main__":
    ft.app(target=main)
