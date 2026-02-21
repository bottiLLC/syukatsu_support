"""
Shared type definitions module.

This module contains type aliases and enums used across multiple modules
to prevent circular imports and ensure type consistency throughout the application.
"""

from typing import Literal

# Constrains effort on thinking. Valid values matching Gemini API spec.
ThinkingLevel = Literal["minimal", "low", "medium", "high"]

# Output formats for analysis logs used in the UI.
# Used to determine the color and formatting of log entries.
LogTag = Literal["user", "ai", "error", "info"]