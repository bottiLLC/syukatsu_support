"""
Pricing model definitions.

This module contains the pricing structures and tables for OpenAI models,
used for cost estimation based on token usage.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ModelPricing:
    """
    Pricing structure for target models (per 1 Million tokens).

    This class is immutable to prevent accidental modification of pricing constants.

    Attributes:
        input_price (float): Cost per 1M input tokens in USD.
        output_price (float): Cost per 1M output tokens in USD.
        cached_input_price (float): Cost per 1M cached input tokens in USD.
        input_price_over_200k (float): Cost per 1M input tokens in USD if prompt > 200k.
        output_price_over_200k (float): Cost per 1M output tokens in USD if prompt > 200k.
    """

    input_price: float
    output_price: float
    cached_input_price: float = 0.0
    input_price_over_200k: float = 0.0
    output_price_over_200k: float = 0.0
    cached_input_price_over_200k: float = 0.0


# Pricing Table based on 'Standard' Tier
# Prices are in USD per 1 Million Tokens.
PRICING_TABLE: Dict[str, ModelPricing] = {
    # Gemini Series
    "gemini-3.1-pro-preview": ModelPricing(
        input_price=2.00,
        output_price=12.00,
        input_price_over_200k=4.00,
        output_price_over_200k=18.00,
        cached_input_price=0.20,
        cached_input_price_over_200k=0.40,
    ),
    "gemini-3-flash-preview": ModelPricing(
        input_price=0.50,
        output_price=3.00,
        cached_input_price=0.05,
    ),
}