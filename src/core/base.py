"""
Base service module for Gemini API interactions.

This module provides the abstract base class for all services that require
access to the Gemini API, ensuring consistent configuration management.
"""

import logging

from google import genai
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from src.config.app_config import AppConfig

# Setup logger
logger = logging.getLogger(__name__)


class BaseGeminiService:
    """
    Base class for services interacting with the Gemini API.

    Enforces the use of genai.Client within an async context manager
    to prevent resource leaks, per the application's global rules.

    Attributes:
        _api_key (str): The decrypted Gemini API key.
    """

    def __init__(self, api_key: str) -> None:
        """
        Initializes the Gemini service with the provided API key.

        Args:
            api_key (str): The decrypted Gemini API key.

        Raises:
            ValueError: If the provided API key is empty or None.
        """
        if not api_key:
            logger.error("Attempted to initialize BaseGeminiService without an API key.")
            raise ValueError("API Key is required to initialize the Gemini service.")

        self._api_key = api_key

    @asynccontextmanager
    async def get_async_client(self) -> AsyncGenerator[genai.Client, None]:
        """
        Context manager that yields a genai.Client.
        Ensures proper creation and cleanup of the async HTTP session.

        Yields:
            genai.Client: A configured asynchronous Gemini client.
        """
        client = genai.Client(api_key=self._api_key)
        try:
            yield client
        finally:
            if client and hasattr(client, "aio") and hasattr(client.aio, "aclose"):
                await client.aio.aclose()