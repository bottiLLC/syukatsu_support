"""OpenAI API エラー翻訳モジュールのユニットテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
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
    req = httpx.Request("GET", "https://api.openai.com/v1")
    err = openai.APITimeoutError(request=req)
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
    assert "■ 原因:" in msg
    assert "■ 対応方法:" in msg


def test_authentication_ip_not_authorized() -> None:
    """IPホワイトリスト制限エラーの翻訳を検証します。"""
    err = openai.AuthenticationError(
        message="Your IP address is not authorized",
        response=MagicMock(status_code=401, headers={}),
        body={"error": {"code": "ip_not_authorized"}},
    )
    msg = src_translate(err)
    assert "アクセス拒否（IP制限）" in msg
    assert "IPホワイトリスト" in msg
    assert "■ 対応方法:" in msg


def test_authentication_account_deactivated() -> None:
    """アカウント無効化エラーの翻訳を検証します。"""
    err = openai.AuthenticationError(
        message="Account has been deactivated",
        response=MagicMock(status_code=401, headers={}),
        body={"error": {"code": "account_deactivated"}},
    )
    msg = src_translate(err)
    assert "アカウント無効化エラー" in msg
    assert "■ 対応方法:" in msg


def test_permission_denied_error_translation() -> None:
    """403 権限エラーの翻訳を検証します。"""
    err = openai.PermissionDeniedError(
        message="You do not have access to this resource",
        response=MagicMock(status_code=403, headers={}),
        body=None,
    )
    msg = src_translate(err)
    assert "アクセス権限エラー" in msg
    assert "■ 原因:" in msg
    assert "■ 対応方法:" in msg


def test_not_found_error_translation() -> None:
    """404 Not Found エラーの翻訳を検証します。"""
    err = openai.NotFoundError(
        message="Model or vector store not found",
        response=MagicMock(status_code=404, headers={}),
        body=None,
    )
    msg = src_translate(err)
    assert "リソースが見つかりません" in msg
    assert "■ 対応方法:" in msg


def test_conflict_error_translation() -> None:
    """409 データ競合エラーの翻訳を検証します。"""
    err = openai.ConflictError(
        message="Resource is being modified",
        response=MagicMock(status_code=409, headers={}),
        body=None,
    )
    msg = src_translate(err)
    assert "リソース競合エラー" in msg
    assert "■ 対応方法:" in msg


def test_unprocessable_entity_error_translation() -> None:
    """422 処理不能エンティティエラーの翻訳を検証します。"""
    err = openai.UnprocessableEntityError(
        message="Failed to parse file",
        response=MagicMock(status_code=422, headers={}),
        body=None,
    )
    msg = src_translate(err)
    assert "データ処理不可エラー" in msg
    assert "■ 対応方法:" in msg


def test_rate_limit_usage_limit_exceeded() -> None:
    """429 月間利用上限超過エラーの翻訳を検証します。"""
    err = openai.RateLimitError(
        message="You have exceeded your monthly usage limit",
        response=MagicMock(status_code=429, headers={}),
        body={"error": {"code": "organization_usage_limit_exceeded"}},
    )
    msg = src_translate(err)
    assert "月間利用上限到達" in msg
    assert "■ 対応方法:" in msg


def test_internal_server_error_translation() -> None:
    """500 サーバー内部エラーの翻訳を検証します。"""
    err = openai.InternalServerError(
        message="An internal server error occurred",
        response=MagicMock(status_code=500, headers={}),
        body=None,
    )
    msg = src_translate(err)
    assert "OpenAIサーバーエラー" in msg
    assert "status.openai.com" in msg
    assert "■ 対応方法:" in msg


def test_gateway_and_service_unavailable_errors() -> None:
    """502/503/504 ゲートウェイおよびサーバー過負荷エラーの翻訳を検証します。"""
    err_502 = openai.APIStatusError(
        message="Bad Gateway",
        response=MagicMock(status_code=502, headers={}),
        body=None,
    )
    msg_502 = src_translate(err_502)
    assert "ゲートウェイ通信エラー" in msg_502

    err_503 = openai.APIStatusError(
        message="Service Unavailable / Overloaded",
        response=MagicMock(status_code=503, headers={}),
        body=None,
    )
    msg_503 = src_translate(err_503)
    assert "サーバー過負荷・一時停止" in msg_503


def test_bad_request_reasoning_effort() -> None:
    """400 reasoning_effort ミスマッチエラーの翻訳を検証します。"""
    err = openai.BadRequestError(
        message="Invalid reasoning_effort value for model",
        response=MagicMock(status_code=400, headers={}),
        body=None,
    )
    msg = src_translate(err)
    assert "モデル設定エラー" in msg
    assert "推論強度" in msg
    assert "■ 対応方法:" in msg


def test_generic_openai_and_system_error_translation() -> None:
    """汎用OpenAIErrorおよび未知のシステム例外の翻訳を検証します。"""
    gen_oai = openai.OpenAIError("Some custom openai error")
    msg_oai = src_translate(gen_oai)
    assert "OpenAI APIエラー" in msg_oai
    assert "■ 対応方法:" in msg_oai

    gen_sys = RuntimeError("Unexpected system fault")
    msg_sys = src_translate(gen_sys)
    assert "システムエラー" in msg_sys
    assert "■ 対応方法:" in msg_sys
