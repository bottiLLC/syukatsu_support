"""
Base service module for OpenAI API interactions.

This module provides the abstract base class for all services that require
access to the OpenAI API, ensuring consistent configuration management.
"""

import logging

from openai import AsyncOpenAI
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from src.config.app_config import AppConfig

# Setup logger
logger = logging.getLogger(__name__)


class BaseOpenAIService:
    """
    Base class for services interacting with the OpenAI API.

    Enforces the use of AsyncOpenAI within an async context manager
    to prevent resource leaks, per the application's global rules.

    Attributes:
        _api_key (str): The decrypted OpenAI API key.
    """

    def __init__(self, api_key: str) -> None:
        """
        Initializes the OpenAI service with the provided API key.

        Args:
            api_key (str): The decrypted OpenAI API key.

        Raises:
            ValueError: If the provided API key is empty or None.
        """
        if not api_key:
            logger.error("Attempted to initialize BaseOpenAIService without an API key.")
            raise ValueError("API Key is required to initialize the OpenAI service.")

        self._api_key = api_key

    @asynccontextmanager
    async def get_async_client(self) -> AsyncGenerator[AsyncOpenAI, None]:
        """
        Context manager that yields an AsyncOpenAI client.
        Ensures proper creation and cleanup of the async HTTP session.

        Yields:
            AsyncOpenAI: A configured asynchronous OpenAI client.
        """
        client = AsyncOpenAI(
            api_key=self._api_key,
            timeout=AppConfig.API_TIMEOUT,
            max_retries=AppConfig.API_MAX_RETRIES,
        )
        try:
            yield client
        finally:
            await client.close()