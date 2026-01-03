import pytest
from dataclasses import FrozenInstanceError
from src.core.pricing import ModelPricing, PRICING_TABLE

# --- Test Cases: ModelPricing Dataclass ---

class TestModelPricing:

    def test_model_pricing_structure(self):
        """[Structure] Verify ModelPricing attributes."""
        pricing = ModelPricing(input_price=1.0, output_price=2.0, cached_input_price=0.5)
        
        assert pricing.input_price == 1.0
        assert pricing.output_price == 2.0
        assert pricing.cached_input_price == 0.5

    def test_model_pricing_immutability(self):
        """[Structure] Verify that ModelPricing is immutable (frozen)."""
        pricing = ModelPricing(input_price=1.0, output_price=2.0)
        
        # Should raise FrozenInstanceError when trying to modify
        with pytest.raises(FrozenInstanceError):
            pricing.input_price = 5.0 # type: ignore

    def test_default_cached_price(self):
        """[Defaults] Verify cached_input_price defaults to 0.0 if not provided."""
        pricing = ModelPricing(input_price=10.0, output_price=20.0)
        assert pricing.cached_input_price == 0.0

# --- Test Cases: PRICING_TABLE ---

class TestPricingTable:

    def test_table_integrity(self):
        """[Structure] Verify PRICING_TABLE is a dict of strings to ModelPricing."""
        assert isinstance(PRICING_TABLE, dict)
        assert len(PRICING_TABLE) > 0
        
        for model_name, pricing in PRICING_TABLE.items():
            assert isinstance(model_name, str)
            assert isinstance(pricing, ModelPricing)

    @pytest.mark.parametrize("model_key", [
        "gpt-5.2",
        "gpt-5.2-pro",
        "gpt-5-mini",
        "o3-pro"
    ])
    def test_essential_models_exist(self, model_key):
        """[Content] Ensure critical models defined in specs exist in the table."""
        assert model_key in PRICING_TABLE

    @pytest.mark.parametrize("model, expected_input, expected_output, expected_cached", [
        # Based on Pricing.txt (Source of Truth)
        # gpt-5.2: In $1.75, Out $14.00, Cached $0.175
        ("gpt-5.2", 1.75, 14.00, 0.175),
        
        # gpt-5-mini: In $0.25, Out $2.00, Cached $0.025
        ("gpt-5-mini", 0.25, 2.00, 0.025),
        
        # gpt-5.2-pro: In $21.00, Out $168.00, Cached 0.0 (implied)
        ("gpt-5.2-pro", 21.00, 168.00, 0.0),
        
        # o3-pro: In $20.00, Out $80.00, Cached 0.0
        ("o3-pro", 20.00, 80.00, 0.0),
    ])
    def test_price_accuracy(self, model, expected_input, expected_output, expected_cached):
        """
        [Accuracy] Verify prices match the Pricing.txt source of truth exactly.
        This is critical for cost estimation accuracy.
        """
        pricing = PRICING_TABLE[model]
        
        assert pricing.input_price == expected_input, f"{model} input price mismatch"
        assert pricing.output_price == expected_output, f"{model} output price mismatch"
        assert pricing.cached_input_price == expected_cached, f"{model} cached price mismatch"

    def test_pricing_sanity(self):
        """[Sanity] Ensure no negative prices and logical consistency."""
        for name, p in PRICING_TABLE.items():
            assert p.input_price >= 0, f"{name}: Negative input price"
            assert p.output_price >= 0, f"{name}: Negative output price"
            assert p.cached_input_price >= 0, f"{name}: Negative cached price"
            
            # General rule: Output is usually more expensive than Input
            # (Not strict for all future models, but true for current ones)
            if "pro" not in name: # o3-pro output(80) > input(20), so this holds.
                 assert p.output_price >= p.input_price