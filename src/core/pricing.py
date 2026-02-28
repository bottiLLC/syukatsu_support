"""
料金モデルの定義。

このモジュールには、OpenAIモデルの料金構造とテーブルが含まれており、
トークン使用量に基づくコスト見積もりに使用されます。
"""

from dataclasses import dataclass
from typing import Dict


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
}