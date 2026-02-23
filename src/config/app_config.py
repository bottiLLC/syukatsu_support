"""
Configuration module for the Job Hunting Support Application.

This module handles:
1. Secure management of API keys using local encryption (Fernet).
2. Loading and saving user configuration via JSON and Environment Variables.
3. Defining application constants and default settings.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

from src.types import ThinkingLevel

# Load environment variables from .env file (if present)
load_dotenv()

# Setup Logger
logger = logging.getLogger(__name__)

# Constants
# Paths are relative to the Current Working Directory
CONFIG_FILE = Path("config.json")
KEY_FILE = Path(".secret.key")


class AppConfig:
    """
    Defines global application configuration constants.

    Attributes:
        APP_VERSION (str): The current version of the application.
        DEFAULT_MODEL (str): The default Gemini model (targeting gemini-3.1-pro).
        DEFAULT_REASONING (ReasoningEffort): Default reasoning effort level.
        API_TIMEOUT (float): Global timeout for API calls in seconds.
        API_MAX_RETRIES (int): Number of retries for failed API calls.
    """

    APP_VERSION: str = "v1.0.0"

    # Default settings to enforce on startup (Safety & Cost management)
    DEFAULT_MODEL: str = "gemini-3.1-pro-preview"
    DEFAULT_THINKING_LEVEL: ThinkingLevel = "high"

    API_TIMEOUT: float = 1200.0
    API_MAX_RETRIES: int = 2


class UserConfig(BaseModel):
    """
    Pydantic model representing the runtime user configuration.

    This model holds the *decrypted* API key in memory.
    It is NOT dumped directly to disk to prevent plain-text leakage.
    """

    model_config = {"populate_by_name": True}

    api_key: Optional[str] = Field(
        default=None, description="The decrypted Gemini API Key."
    )
    model: str = Field(
        default=AppConfig.DEFAULT_MODEL, description="The selected Gemini model ID."
    )
    thinking_level: ThinkingLevel = Field(
        default=AppConfig.DEFAULT_THINKING_LEVEL,
        description="The thinking level for the model.",
    )
    # FIX: Corrected string to match src/core/prompts.py (Added space)
    system_prompt_mode: str = Field(
        default="有価証券報告書 -財務分析-",
        description="The currently selected analysis strategy mode.",
    )
    last_response_id: Optional[str] = Field(
        default=None,
        description="The ID of the last response for context continuity.",
    )

    # --- RAG Configuration ---
    current_vector_store_id: Optional[str] = Field(
        default=None, description="The ID of the currently selected Vector Store."
    )
    use_file_search: bool = Field(
        default=False, description="Whether to enable File Search (RAG) tool."
    )


class SecurityManager:
    """
    Handles local encryption and decryption of sensitive data using Fernet.
    """

    @staticmethod
    def _get_or_create_key() -> bytes:
        """
        Retrieves the encryption key from disk or generates a new one.

        Returns:
            bytes: The Fernet encryption key.

        Raises:
            IOError: If reading or writing the key file fails.
        """
        if KEY_FILE.exists():
            try:
                return KEY_FILE.read_bytes()
            except IOError as e:
                logger.error(f"Failed to read key file: {e}")
                raise

        # Generate new key if it doesn't exist
        logger.info("Generating new encryption key.")
        key = Fernet.generate_key()
        try:
            KEY_FILE.write_bytes(key)
            # Set restrictive permissions on POSIX systems (Read/Write by owner only)
            if os.name == "posix":
                KEY_FILE.chmod(0o600)
        except IOError as e:
            logger.critical(f"Failed to save encryption key: {e}")
            raise
        return key

    @classmethod
    def encrypt(cls, plain_text: str) -> str:
        """
        Encrypts a string.

        Args:
            plain_text: The text to encrypt.

        Returns:
            The encrypted text string, or empty string if input is empty/error.
        """
        if not plain_text:
            return ""
        try:
            fernet = Fernet(cls._get_or_create_key())
            return fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return ""

    @classmethod
    def decrypt(cls, cipher_text: str) -> Optional[str]:
        """
        Decrypts a string.

        Args:
            cipher_text: The encrypted text string.

        Returns:
            The decrypted text, or None if decryption fails.
        """
        if not cipher_text:
            return None
        try:
            fernet = Fernet(cls._get_or_create_key())
            return fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
        except (InvalidToken, Exception) as e:
            logger.warning(
                f"Decryption failed. The secret key might have been regenerated "
                f"or the data is corrupted. Details: {e}"
            )
            return None


class ConfigManager:
    """
    Service for loading and saving application configuration.

    Ensures API keys are encrypted on disk and decrypted in memory.
    Enforces default settings on load to prevent expensive model usage across sessions.
    """

    @staticmethod
    def load() -> UserConfig:
        """
        Loads configuration from disk and environment variables.

        Priority:
        1. Environment Variable (GEMINI_API_KEY) - Highest security priority.
        2. Config File (Encrypted API Key) - Persistence for GUI users.

        Safety:
            Model and Reasoning Effort are ALWAYS reset to defaults on load
            to prevent expensive model usage across sessions.

        Returns:
            UserConfig: The loaded configuration object.
        """
        config_data: Dict[str, Any] = {}

        # 1. Load from JSON file (mainly for API Key persistence)
        if CONFIG_FILE.exists():
            try:
                with CONFIG_FILE.open("r", encoding="utf-8") as f:
                    file_data = json.load(f)

                # Decrypt API Key if 'encrypted_api_key' is present
                encrypted_key = file_data.get("encrypted_api_key")
                if encrypted_key:
                    decrypted_key = SecurityManager.decrypt(encrypted_key)
                    if decrypted_key:
                        file_data["api_key"] = decrypted_key
                    else:
                        # Decryption failed; ensure we don't pass garbage
                        logger.warning("Resetting API key due to decryption failure.")
                        file_data["api_key"] = None

                # Remove encrypted field from the dict used for Pydantic init
                file_data.pop("encrypted_api_key", None)
                config_data = file_data

            except (json.JSONDecodeError, IOError, Exception) as e:
                logger.error(f"Failed to load config file: {e}")

        # 2. Environment override (overwrites file-based key if present)
        env_key = os.getenv("GEMINI_API_KEY")
        if env_key:
            config_data["api_key"] = env_key

        # 3. Enforce Safety Defaults (Ignore saved model/thinking settings)
        config_data["model"] = AppConfig.DEFAULT_MODEL
        config_data["thinking_level"] = AppConfig.DEFAULT_THINKING_LEVEL

        # Reset prompt mode and context for a fresh start
        # FIX: Ensure consistency with prompts.py
        config_data["system_prompt_mode"] = "有価証券報告書 -財務分析-"
        config_data["last_response_id"] = None

        # RAG settings (use_file_search, current_vector_store_id) are preserved if loaded

        # Validate and return
        try:
            return UserConfig(**config_data)
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            # Fallback to default configuration
            return UserConfig()

    @staticmethod
    def save(config: UserConfig) -> None:
        """
        Saves the configuration to disk.

        The 'api_key' field is explicitly excluded from the plain text dump
        and stored securely in 'encrypted_api_key'.

        Args:
            config: The current configuration state to save.
        """
        try:
            # 1. Convert to dict, explicitly excluding sensitive fields
            data = config.model_dump(exclude={"api_key"})

            # 2. Encrypt and add the API key manually
            if config.api_key:
                encrypted = SecurityManager.encrypt(config.api_key)
                if encrypted:
                    data["encrypted_api_key"] = encrypted

            # 3. Write to disk
            with CONFIG_FILE.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

            logger.info("Configuration saved successfully.")
        except IOError as e:
            logger.error(f"Failed to save configuration: {e}")