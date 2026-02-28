"""
料金モデルの定義とコスト計算ロジック。

このモジュールには、OpenAIモデルの料金構造とテーブルが含まれており、
トークン使用量に基づくコスト見積もりに使用されます。
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class ModelPricing:
    """
    OpenAIモデルの料金構造（100万トークンあたり）。

    料金定数の誤った変更を防ぐため、このクラスはイミュータブル（不変）です。

    Attributes:
        input_price (float): 100万入力トークンあたりのコスト（USD）。
        output_price (float): 100万出力トークンあたりのコスト（USD）。
        cached_input_price (float): 100万キャッシュ済み入力トークンあたりのコスト（USD）。
                                    未定義の場合はデフォルトで0.0になります。
    """

    input_price: float
    output_price: float
    cached_input_price: float = 0.0


# 'Standard' ティアに基づく料金テーブル
# 価格は100万トークンあたりのUSDです。
# Note: これらの値は、最新のOpenAIの料金ページに合わせて更新する必要があります。
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
    # Legacy Fallbacks
    "gpt-4o": ModelPricing(
        input_price=2.50,
        output_price=10.00,
        cached_input_price=1.25
    ),
    "gpt-4o-mini": ModelPricing(
        input_price=0.150,
        output_price=0.600,
        cached_input_price=0.075
    )
}

class CostCalculator:
    """Provides methods for calculating API usage costs."""
    
    @staticmethod
    def calculate(model_name: str, usage_event: Any) -> str:
        """
        Calculates the estimated cost in USD based on a StreamUsage event or object
        that holds usage statistics.
        """
        # Fallback handling strings just in case
        if isinstance(usage_event, str):
            return f"Cost: $0.00000 | {usage_event}"

        try:
            prompt_tokens = getattr(usage_event, "prompt_tokens", getattr(getattr(usage_event, "usage", None), "prompt_tokens", 0))
            completion_tokens = getattr(usage_event, "completion_tokens", getattr(getattr(usage_event, "usage", None), "completion_tokens", 0))
            
            # Additional cached tokens parsing
            cached_tokens = 0
            if hasattr(usage_event, "prompt_tokens_details"):
                cached_tokens = getattr(usage_event.prompt_tokens_details, "cached_tokens", 0)
            elif hasattr(getattr(usage_event, "usage", None), "prompt_tokens_details"):
                cached_tokens = getattr(usage_event.usage.prompt_tokens_details, "cached_tokens", 0)

            pricing = PRICING_TABLE.get(model_name)
            if not pricing:
                return f"Cost: Unknown Model ({model_name})"

            # Prevent double charging for cached tokens
            uncached_prompt_tokens = max(0, prompt_tokens - cached_tokens)

            cost = (
                (uncached_prompt_tokens / 1_000_000) * pricing.input_price +
                (cached_tokens / 1_000_000) * pricing.cached_input_price +
                (completion_tokens / 1_000_000) * pricing.output_price
            )

            return f"Cost: ${cost:.5f} | In: {prompt_tokens} (Cache: {cached_tokens}) | Out: {completion_tokens}"
            
        except AttributeError:
             return "Cost: Data Unreadable"
        except Exception as e:
            return f"Cost Error: {str(e)}"