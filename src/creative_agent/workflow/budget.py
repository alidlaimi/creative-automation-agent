"""Kosten pro Aufruf und Budgetgrenze pro Lauf."""

from dataclasses import dataclass, field

from .llm import TokenUsage

# USD pro Million Tokens. Quelle: https://platform.claude.com/docs/en/about-claude/pricing
# geprüft 2026-11-20. Haiku 5.5 hat zwei Stufen (Prompts bis / über 100 000 Tokens).
# Weitere Modelle erst mit geprüften Preisen eintragen – sonst bricht der Lauf bewusst ab.
PRICING_SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing (geprüft 2026-11-20)"


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cache_write_5m: float
    cache_read: float


PRICES: dict[str, Price] = {
    "claude-sonnet-5-5": Price(2.0, 10.0, 2.50, 0.10),
    "claude-haiku-5-5": Price(0.10, 0.50, 0.125, 0.01),
}
HAIKU_LONG_PROMPT = Price(0.50, 2.50, 0.625, 0.05)
HAIKU_THRESHOLD = 100_000


class BudgetExceeded(RuntimeError):
    pass


def price_for(model: str, usage: TokenUsage) -> Price:
    if model not in PRICES:
        raise ValueError(f"Kein Preis für Modell {model!r} hinterlegt – Budget wäre nicht prüfbar")
    if model == "claude-haiku-5-5" and usage.total_input > HAIKU_THRESHOLD:
        return HAIKU_LONG_PROMPT
    return PRICES[model]


def cost_usd(model: str, usage: TokenUsage) -> float:
    p = price_for(model, usage)
    return (
        usage.input_tokens * p.input
        + usage.output_tokens * p.output
        + usage.cache_creation_input_tokens * p.cache_write_5m
        + usage.cache_read_input_tokens * p.cache_read
    ) / 1_000_000


@dataclass
class CallCost:
    step: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass
class CostTracker:
    budget_usd: float
    calls: list[CallCost] = field(default_factory=list)

    @property
    def spent_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    def check(self) -> None:
        """Vor jedem Aufruf: Ist noch Budget übrig? (max_tokens begrenzt das Überschiessen.)"""
        if self.spent_usd >= self.budget_usd:
            raise BudgetExceeded(
                f"Budget von USD {self.budget_usd:.2f} erreicht (USD {self.spent_usd:.4f})"
            )

    def add(self, step: str, model: str, usage: TokenUsage) -> None:
        self.calls.append(
            CallCost(step, model, usage.total_input, usage.output_tokens, cost_usd(model, usage))
        )
