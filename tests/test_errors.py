from unittest.mock import MagicMock
import openai
import pytest

from app import translate_api_error as app_translate
from src.core.errors import translate_api_error as src_translate


def test_permission_error_translation():
    err = PermissionError("Permission denied: config.json")
    for translate_fn in [src_translate, app_translate]:
        msg = translate_fn(err)
        assert "多重起動" in msg
        assert "ロック" in msg


def test_timeout_error_translation():
    err = openai.APITimeoutError(request=None)
    for translate_fn in [src_translate, app_translate]:
        msg = translate_fn(err)
        assert "タイムアウト" in msg


def test_authentication_error_translation():
    err = openai.AuthenticationError(
        message="Invalid API key",
        response=MagicMock(status_code=401, headers={}),
        body=None
    )
    for translate_fn in [src_translate, app_translate]:
        msg = translate_fn(err)
        assert "APIキーエラー" in msg
        assert "無効" in msg


def test_rate_limit_insufficient_quota():
    err = openai.RateLimitError(
        message="You exceeded your current quota, please check your plan and billing details.",
        response=MagicMock(status_code=429, headers={}),
        body={"error": {"code": "insufficient_quota"}}
    )
    for translate_fn in [src_translate, app_translate]:
        msg = translate_fn(err)
        assert "残高不足" in msg or "Quota" in msg


def test_rate_limit_exceeded():
    err = openai.RateLimitError(
        message="Rate limit reached for requests",
        response=MagicMock(status_code=429, headers={}),
        body={"error": {"code": "rate_limit_exceeded"}}
    )
    for translate_fn in [src_translate, app_translate]:
        msg = translate_fn(err)
        assert "一時的な利用制限" in msg


def test_context_window_exceeded():
    err = openai.BadRequestError(
        message="This model's maximum context length is 128000 tokens. However, your messages resulted in 130000 tokens.",
        response=MagicMock(status_code=400, headers={}),
        body=None
    )
    for translate_fn in [src_translate, app_translate]:
        msg = translate_fn(err)
        assert "入力文字数制限オーバー" in msg
        assert "コンテキスト消去" in msg


def test_retry_error_wrapped_connection_error():
    from tenacity import RetryError
    last_attempt = MagicMock()
    last_attempt.exception.return_value = openai.APIConnectionError(request=MagicMock())
    err = RetryError(last_attempt)
    for translate_fn in [src_translate, app_translate]:
        msg = translate_fn(err)
        assert "ネットワーク接続エラー" in msg

def test_retry_error_string_fallback():
    err = Exception("RetryError[<Future at 0x21796b1e850 state=finished raised APIConnectionError>]")
    for translate_fn in [src_translate, app_translate]:
        msg = translate_fn(err)
        assert "ネットワーク接続エラー" in msg


def test_unicode_encode_error_translation():
    err = UnicodeEncodeError("ascii", "全角文字", 0, 4, "ordinal not in range(128)")
    for translate_fn in [src_translate, app_translate]:
        msg = translate_fn(err)
        assert "APIキー文字エラー" in msg
        assert "全角文字" in msg
