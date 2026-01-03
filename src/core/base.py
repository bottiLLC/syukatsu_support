"""
Base service module for OpenAI API interactions.

This module provides the abstract base class for all services that require
access to the OpenAI API, ensuring consistent client initialization,
configuration, and error handling patterns.
"""

import logging

from openai import OpenAI

from src.config.app_config import AppConfig

# Setup logger
logger = logging.getLogger(__name__)


class BaseOpenAIService:
    """
    Base class for services interacting with the OpenAI API.

    This class encapsulates the initialization of the synchronous OpenAI client,
    enforcing global configuration settings such as timeouts and retry limits.

    Attributes:
        _client (OpenAI): The configured OpenAI client instance.
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

        self._client: OpenAI = OpenAI(
            api_key=api_key,
            timeout=AppConfig.API_TIMEOUT,
            max_retries=AppConfig.API_MAX_RETRIES,
        )