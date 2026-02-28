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