"""OpenAI API エラー翻訳モジュールのユニットテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock

import openai

from src.core.errors import translate_api_error as src_translate


def test_permission_error_translation() -> None:
    """設定ファイルのパーミッションエラー翻訳を検証します。"""
    err = PermissionError("Permission denied: config.json")
    msg = src_translate(err)
    assert "多重起動" in msg
    assert "ロック" in msg


def test_timeout_error_translation() -> None:
    """API タイムアウトエラーの翻訳を検証します。"""
    err = openai.APITimeoutError(request=None)
    msg = src_translate(err)
    assert "タイムアウト" in msg


def test_authentication_error_translation() -> None:
    """認証エラー（無効なAPIキー）の翻訳を検証します。"""
    err = openai.AuthenticationError(
        message="Invalid API key",
        response=MagicMock(status_code=401, headers={}),
        body=None,
    )
    msg = src_translate(err)
    assert "APIキーエラー" in msg
    assert "無効" in msg


def test_rate_limit_insufficient_quota() -> None:
    """残高不足（クォータ制限）エラーの翻訳を検証します。"""
    err = openai.RateLimitError(
        message="You exceeded your current quota, please check your plan and billing details.",
        response=MagicMock(status_code=429, headers={}),
        body={"error": {"code": "insufficient_quota"}},
    )
    msg = src_translate(err)
    assert "残高不足" in msg or "Quota" in msg


def test_rate_limit_exceeded() -> None:
    """リクエストレート制限エラーの翻訳を検証します。"""
    err = openai.RateLimitError(
        message="Rate limit reached for requests",
        response=MagicMock(status_code=429, headers={}),
        body={"error": {"code": "rate_limit_exceeded"}},
    )
    msg = src_translate(err)
    assert "一時的な利用制限" in msg


def test_context_window_exceeded() -> None:
    """トークン超過（コンテキスト長上限）エラーの翻訳を検証します。"""
    err = openai.BadRequestError(
        message="This model's maximum context length is 128000 tokens. However, your messages resulted in 130000 tokens.",
        response=MagicMock(status_code=400, headers={}),
        body=None,
    )
    msg = src_translate(err)
    assert "入力文字数制限オーバー" in msg
    assert "コンテキスト消去" in msg


def test_retry_error_wrapped_connection_error() -> None:
    """Tenacity RetryError にラップされた接続エラーの翻訳を検証します。"""
    from tenacity import RetryError

    last_attempt = MagicMock()
    last_attempt.exception.return_value = openai.APIConnectionError(request=MagicMock())
    err = RetryError(last_attempt)
    msg = src_translate(err)
    assert "ネットワーク接続エラー" in msg


def test_retry_error_string_fallback() -> None:
    """Tenacity RetryError 文字列フォールバックの翻訳を検証します。"""
    err = Exception("RetryError[<Future at 0x21796b1e850 state=finished raised APIConnectionError>]")
    msg = src_translate(err)
    assert "ネットワーク接続エラー" in msg


def test_unicode_encode_error_translation() -> None:
    """APIキー全角文字混入エラーの翻訳を検証します。"""
    err = UnicodeEncodeError("ascii", "全角文字", 0, 4, "ordinal not in range(128)")
    msg = src_translate(err)
    assert "APIキー文字エラー" in msg
    assert "全角文字" in msg
