"""
Shared type definitions module.

This module contains type aliases and enums used across multiple modules
to prevent circular imports and ensure type consistency throughout the application.
"""

from typing import Literal

# Constrains effort on reasoning. Valid values matching OpenAI API spec.
# Reference: components/schemas/ReasoningEffort in openapi.documented.yml
# Note: 'none' is supported by gpt-5.1, 'xhigh' by gpt-5.1-codex-max onwards.
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]

# Output formats for analysis logs used in the UI.
# Used to determine the color and formatting of log entries.
LogTag = Literal["user", "ai", "error", "info"]