"""Markenstimme: Bewertung durch ein Modell anhand der Rubrik im Skill.

Vorläufig (bis zur Kalibrierung in Meilenstein 8): Ein Ergebnis unter dem Schwellwert führt
höchstens zu GELB – ein Mensch entscheidet. Erst eine gemessene Übereinstimmung mit
menschlichen Urteilen rechtfertigt mehr Gewicht.
"""

from pydantic import BaseModel, Field

from ..mcp_client import Product
from ..skills import Skill
from ..skills.models import BrandVoiceRules
from ..workflow.budget import CostTracker
from ..workflow.llm import LLM
from ..workflow.models import Variant
from ..workflow.prompts import DATA_NOTICE, wrap_products
from ..workflow.steps import StepContext, structured_with_retry
from .findings import JudgeResult
from .rules import texts_of


class CriterionScore(BaseModel):
    id: str = Field(description="ID des Kriteriums aus der Rubrik")
    score: int = Field(description="Punktzahl gemäss Skala")
    begruendung: str = Field(description="Ein Satz, mit Bezug auf den Text")


class JudgeOutput(BaseModel):
    bewertungen: list[CriterionScore]
    gesamteindruck: str = Field(description="Ein Satz")


def judge_system(skill: Skill) -> str:
    rules: BrandVoiceRules = skill.rules
    r = rules.rubric
    criteria = "\n".join(
        f"- {c.id} ({c.name}): {c.question}\n  {r.scale_max} = {c.score_high}\n"
        f"  {r.scale_min} = {c.score_low}"
        for c in r.criteria
    )
    return (
        "Du bewertest Werbetexte streng und unabhängig gegen eine Markenstimme. "
        "Du schreibst nichts um.\n\n"
        f"## Markenstimme\n{skill.instructions}\n\n"
        f"## Rubrik (Skala {r.scale_min} bis {r.scale_max}, ganze Zahlen)\n{criteria}\n\n"
        "Bewerte jedes Kriterium genau einmal. Sei kritisch: Eine 5 nur, wenn nichts zu verbessern "
        f"ist.\n{DATA_NOTICE}"
    )


class BrandVoiceJudge:
    def __init__(self, llm: LLM, model: str, threshold: float = 2.25, min_criterion: int = 0):
        self.llm = llm
        self.model = model
        self.threshold = threshold
        self.min_criterion = min_criterion

    async def judge(
        self, variant: Variant, product: Product, skill: Skill, tracker: CostTracker
    ) -> JudgeResult:
        rubric = skill.rules.rubric
        ids = [c.id for c in rubric.criteria]

        def validate(out: JudgeOutput) -> list[str]:
            got = [b.id for b in out.bewertungen]
            errors = [f"Kriterium {i!r} fehlt" for i in ids if i not in got]
            errors += [f"Unbekanntes Kriterium {g!r}" for g in got if g not in ids]
            errors += [
                f"{b.id}: {b.score} ausserhalb {rubric.scale_min}–{rubric.scale_max}"
                for b in out.bewertungen
                if not rubric.scale_min <= b.score <= rubric.scale_max
            ]
            return errors

        text = "\n".join(f"{field}: {value}" for field, value in texts_of(variant))
        prompt = (
            f"Kanal: {variant.channel}\nZielgruppe: {variant.target_group}\n\n"
            f"Zu bewertender Text:\n{text}\n\n"
            f"Produktdaten (nur zur Einordnung von Übertreibungen):\n{wrap_products([product])}"
        )
        before = len(tracker.calls)
        ctx = StepContext(llm=self.llm, tracker=tracker, model=self.model, model_fast=self.model)
        out: JudgeOutput = await structured_with_retry(
            ctx,
            step=f"markenstimme:{variant.variant_id}",
            model=self.model,
            system=judge_system(skill),
            prompt=prompt,
            output_model=JudgeOutput,
            validate=validate,
            max_tokens=1200,
        )
        scores = {b.id: b.score for b in out.bewertungen}
        mean = round(sum(scores.values()) / len(scores), 2)
        passed = mean >= self.threshold and min(scores.values()) > self.min_criterion
        return JudgeResult(
            model=self.model,
            scores=scores,
            reasons={b.id: b.begruendung for b in out.bewertungen},
            overall=out.gesamteindruck,
            mean=mean,
            threshold=self.threshold,
            passed=passed,
            cost_usd=round(sum(c.cost_usd for c in tracker.calls[before:]), 6),
        )
