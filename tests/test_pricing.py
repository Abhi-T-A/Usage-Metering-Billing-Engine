import pytest
from app.services.pricing_service import (
    PricingConfig,
    PricingService,
    TokenUsageBreakdown,
)


@pytest.fixture
def custom_pricing_service() -> PricingService:
    """Fixture providing pinned, easy-to-verify pricing constants:
    - Input: 100 micro-cents/token ($1.00 / 1M)
    - Cached Input: 25 micro-cents/token ($0.25 / 1M) -> 75% discount
    - Output: 400 micro-cents/token ($4.00 / 1M)
    - Reasoning: priced as output (400 micro-cents/token)
    - API Call: 10,000 micro-cents (1 cent flat per call)
    """
    config = PricingConfig(
        input_token_microcents=100,
        cached_input_token_microcents=25,
        output_token_microcents=400,
        api_call_microcents=10000,
    )
    return PricingService(config=config)


def test_pricing_normal_input_tokens(custom_pricing_service: PricingService):
    """1,000 normal input tokens @ 100 microcents = 100,000 microcents = 10 cents."""
    tokens = TokenUsageBreakdown(input_tokens=1000)
    result = custom_pricing_service.calculate_cost(tokens=tokens)

    assert result.input_cost_microcents == 100_000
    assert result.cached_input_cost_microcents == 0
    assert result.output_cost_microcents == 0
    assert result.reasoning_cost_microcents == 0
    assert result.total_cost_microcents == 100_000
    assert result.total_cost_cents == 10
    assert result.total_tokens == 1000


def test_pricing_cached_input_discount(custom_pricing_service: PricingService):
    """1,000 cached input tokens @ 25 microcents = 25,000 microcents = 3 cents (ceil)."""
    tokens = TokenUsageBreakdown(cached_input_tokens=1000)
    result = custom_pricing_service.calculate_cost(tokens=tokens)

    assert result.cached_input_cost_microcents == 25_000
    # 25,000 microcents = 2.5 cents -> integer ceiling gives 3 cents
    assert result.total_cost_cents == 3
    assert result.total_tokens == 1000


def test_pricing_output_tokens(custom_pricing_service: PricingService):
    """500 output tokens @ 400 microcents = 200,000 microcents = 20 cents."""
    tokens = TokenUsageBreakdown(output_tokens=500)
    result = custom_pricing_service.calculate_cost(tokens=tokens)

    assert result.output_cost_microcents == 200_000
    assert result.total_cost_cents == 20
    assert result.total_tokens == 500


def test_pricing_reasoning_tokens_priced_as_output(
    custom_pricing_service: PricingService,
):
    """Reasoning tokens must be priced at output token rate (400 microcents)."""
    tokens = TokenUsageBreakdown(reasoning_tokens=500)
    result = custom_pricing_service.calculate_cost(tokens=tokens)

    # 500 * 400 = 200,000 microcents
    assert result.reasoning_cost_microcents == 200_000
    assert result.total_cost_cents == 20
    assert result.total_tokens == 500


def test_pricing_combined_calculation(custom_pricing_service: PricingService):
    """Combined usage calculation:
    - 1,200 input tokens: 1,200 * 100 = 120,000 microcents
    - 200 cached input tokens: 200 * 25 = 5,000 microcents
    - 800 output tokens: 800 * 400 = 320,000 microcents
    - 100 reasoning tokens: 100 * 400 = 40,000 microcents
    - 2 API calls: 2 * 10,000 = 20,000 microcents
    Total microcents = 120,000 + 5,000 + 320,000 + 40,000 + 20,000 = 505,000 microcents
    Total cents = 51 cents (505,000 / 10,000 = 50.5 -> ceil = 51)
    """
    tokens = TokenUsageBreakdown(
        input_tokens=1200,
        cached_input_tokens=200,
        output_tokens=800,
        reasoning_tokens=100,
    )
    result = custom_pricing_service.calculate_cost(tokens=tokens, api_calls=2)

    assert result.input_cost_microcents == 120_000
    assert result.cached_input_cost_microcents == 5_000
    assert result.output_cost_microcents == 320_000
    assert result.reasoning_cost_microcents == 40_000
    assert result.api_call_cost_microcents == 20_000
    assert result.total_cost_microcents == 505_000
    assert result.total_cost_cents == 51
    assert result.total_tokens == 2300


def test_pricing_zero_usage_returns_zero_cost(
    custom_pricing_service: PricingService,
):
    """Zero usage returns exactly 0 cents."""
    result = custom_pricing_service.calculate_cost()
    assert result.total_cost_microcents == 0
    assert result.total_cost_cents == 0
    assert result.total_tokens == 0


def test_pricing_types_are_strictly_integers(
    custom_pricing_service: PricingService,
):
    """Ensures all cost fields are strictly python `int` without float contamination."""
    tokens = TokenUsageBreakdown(
        input_tokens=333,
        cached_input_tokens=111,
        output_tokens=222,
        reasoning_tokens=77,
    )
    result = custom_pricing_service.calculate_cost(tokens=tokens, api_calls=3)

    assert isinstance(result.input_cost_microcents, int)
    assert isinstance(result.cached_input_cost_microcents, int)
    assert isinstance(result.output_cost_microcents, int)
    assert isinstance(result.reasoning_cost_microcents, int)
    assert isinstance(result.api_call_cost_microcents, int)
    assert isinstance(result.total_cost_microcents, int)
    assert isinstance(result.total_cost_cents, int)
    assert isinstance(result.total_tokens, int)
