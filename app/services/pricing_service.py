from dataclasses import dataclass


@dataclass(frozen=True)
class PricingConfig:
    """Pricing rates configured in micro-cents per unit.
    
    1 USD = 100 Cents = 1,000,000 Micro-cents.
    1 Cent = 10,000 Micro-cents.
    
    Default Gemini/Standard baseline:
    - Normal Input: $1.50 per 1M tokens -> 150 cents / 1M = 150 micro-cents / token.
    - Cached Input: $0.375 per 1M tokens -> 37.5 ~ 38 micro-cents / token.
    - Output: $6.00 per 1M tokens -> 600 micro-cents / token.
    - Reasoning: Counted as output -> 600 micro-cents / token.
    - API Call: 0 micro-cents by default (or configured per-call flat cost).
    """
    input_token_microcents: int = 150
    cached_input_token_microcents: int = 38
    output_token_microcents: int = 600
    api_call_microcents: int = 0


@dataclass(frozen=True)
class TokenUsageBreakdown:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.cached_input_tokens
            + self.output_tokens
            + self.reasoning_tokens
        )


@dataclass(frozen=True)
class PricingResult:
    input_cost_microcents: int
    cached_input_cost_microcents: int
    output_cost_microcents: int
    reasoning_cost_microcents: int
    api_call_cost_microcents: int
    total_cost_microcents: int
    total_cost_cents: int
    total_tokens: int


class PricingService:
    def __init__(self, config: PricingConfig | None = None) -> None:
        self.config = config or PricingConfig()

    def calculate_cost(
        self,
        tokens: TokenUsageBreakdown | None = None,
        api_calls: int = 0,
    ) -> PricingResult:
        """Calculates precise monetary cost using integer-only arithmetic.
        
        Rules:
        1. input_cost = input_tokens * input_token_microcents
        2. cached_input_cost = cached_input_tokens * cached_input_token_microcents
        3. output_cost = output_tokens * output_token_microcents
        4. reasoning_cost = reasoning_tokens * output_token_microcents (priced as output)
        5. api_call_cost = api_calls * api_call_microcents
        6. total_cost_cents = integer ceiling to whole cents: (total_microcents + 9999) // 10000
        """
        t = tokens or TokenUsageBreakdown()

        input_cost = t.input_tokens * self.config.input_token_microcents
        cached_input_cost = (
            t.cached_input_tokens * self.config.cached_input_token_microcents
        )
        output_cost = t.output_tokens * self.config.output_token_microcents
        # Reasoning tokens are priced as output tokens
        reasoning_cost = t.reasoning_tokens * self.config.output_token_microcents
        api_call_cost = api_calls * self.config.api_call_microcents

        total_microcents = (
            input_cost
            + cached_input_cost
            + output_cost
            + reasoning_cost
            + api_call_cost
        )

        # Integer ceiling conversion from micro-cents to cents (no floats)
        total_cents = (
            (total_microcents + 9999) // 10000 if total_microcents > 0 else 0
        )

        return PricingResult(
            input_cost_microcents=input_cost,
            cached_input_cost_microcents=cached_input_cost,
            output_cost_microcents=output_cost,
            reasoning_cost_microcents=reasoning_cost,
            api_call_cost_microcents=api_call_cost,
            total_cost_microcents=total_microcents,
            total_cost_cents=total_cents,
            total_tokens=t.total_tokens,
        )
