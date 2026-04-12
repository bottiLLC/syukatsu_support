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
就活サポートアプリのロギング設定モジュール。

このモジュールはアプリケーション全体のロギング設定を処理します。
これを分離することで、メインのエントリポイントを変更することなく、
ログの形式やハンドラー（例：ファイルロギングの追加）の変更を容易にします。
"""

import logging
import structlog
import sys

def setup_logging() -> None:
    """
    structlogを使用してアプリケーションのルートロガーを設定します。
    
    これにより、観測性（Observability）向上のための構造化ロギングが初期化されます。
    """
    # WindowsコンソールでのUnicodeEncodeErrorを防ぐため、標準出力をUTF-8に強制
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False
    )