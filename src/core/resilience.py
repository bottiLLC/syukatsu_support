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
