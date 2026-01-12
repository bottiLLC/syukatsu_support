"""
Logging configuration module for the Job Hunting Support Application.

This module handles the setup of the application-wide logging configuration.
Separating this allows for easier modifications to log formats or handlers
(e.g., adding file logging) without modifying the main entry point.
"""

import logging

# Logging configuration constants
LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """
    Configures the root logger for the application.

    This function initializes the logging system with the standard format,
    date format, and log level defined in the module constants.
    It uses `logging.basicConfig` to ensure a default StreamHandler is attached.
    """
    logging.basicConfig(
        level=LOG_LEVEL,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
    )