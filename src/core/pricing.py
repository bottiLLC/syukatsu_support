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
    Pricing structure for OpenAI models (per 1 Million tokens).

    This class is immutable to prevent accidental modification of pricing constants.

    Attributes:
        input_price (float): Cost per 1M input tokens in USD.
        output_price (float): Cost per 1M output tokens in USD.
        cached_input_price (float): Cost per 1M cached input tokens in USD.
                                    Defaults to 0.0 if not defined.
    """

    input_price: float
    output_price: float
    cached_input_price: float = 0.0


# Pricing Table based on 'Standard' Tier
# Prices are in USD per 1 Million Tokens.
# Note: These values should be updated to match the latest OpenAI pricing page.
PRICING_TABLE: Dict[str, ModelPricing] = {
    # GPT-5 Series
    "gpt-5.2-pro": ModelPricing(
        input_price=21.00,
        output_price=168.00,
        cached_input_price=0.0
    ),
    "gpt-5.2": ModelPricing(
        input_price=1.75,
        output_price=14.00,
        cached_input_price=0.175
    ),
    "gpt-5-mini": ModelPricing(
        input_price=0.25,
        output_price=2.00,
        cached_input_price=0.025
    ),
}