"""
リトライおよびエラー処理のデコレータを提供するリジリエンス（回復性）モジュール。
"""

import logging
import structlog
from typing import Any, Callable, TypeVar, Coroutine
from functools import wraps

import openai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
    before_sleep_log,
)

log = structlog.get_logger(__name__)

T = TypeVar("T")

def resilient_api_call() -> Callable[[Callable[..., Coroutine[Any, Any, T]]], Callable[..., Coroutine[Any, Any, T]]]:
    """
    OpenAI API の非同期呼び出しに対して、tenacity を使用してリトライロジックを追加し、
    structlog と統合するデコレータ。
    """
    
    # We want to catch specific transient errors from OpenAI
    retry_exceptions = (
        openai.RateLimitError,
        openai.APIConnectionError,
        openai.InternalServerError,
        openai.APITimeoutError
    )

    tenacity_retry = retry(
        retry=retry_if_exception_type(retry_exceptions),
        wait=wait_random_exponential(multiplier=1, max=60),
        stop=stop_after_attempt(5),
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True,
    )

    def decorator(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            retrying_func = tenacity_retry(func)
            return await retrying_func(*args, **kwargs)
        return wrapper

    return decorator
