"""Review-Zustand je Lauf (review.json): Korrekturen als Revisionen, Entscheide mit Begründung.

run.json bleibt unverändert – so ist jederzeit nachvollziehbar, was das Modell geliefert und was
ein Mensch geändert hat. Gespeichert wird eine Rolle («review»), keine Person.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ..gate import GateResult
from ..layouts import LayoutReport
from ..workflow.models import RunRecord, Variant

DecisionValue = Literal["freigegeben", "abgelehnt"]


class ReviewError(ValueError):
    """Entscheid verstösst gegen die Freigaberegeln."""


class Decision(BaseModel):
    decision: DecisionValue
    reason: str
    gate_status: Literal["gruen", "gelb", "rot"]
    revision: int  # 0 = Originalvariante
    decided_at: datetime
    reviewer: str = "review"


class Revision(BaseModel):
    fields: dict[str, str | list[str]]
    edited_at: datetime
    gate: GateResult
    layout_report: LayoutReport | None = None
    png_path: str | None = None


class VariantReview(BaseModel):
    revisions: list[Revision] = Field(default_factory=list)
    decision: Decision | None = None


class ReviewState(BaseModel):
    run_id: str
    variants: dict[str, VariantReview] = Field(default_factory=dict)

    def entry(self, variant_id: str) -> VariantReview:
        return self.variants.setdefault(variant_id, VariantReview())


def review_path(run_dir: Path) -> Path:
    return run_dir / "review.json"


def load_review(run_dir: Path) -> ReviewState:
    path = review_path(run_dir)
    if path.exists():
        return ReviewState.model_validate_json(path.read_text("utf-8"))
    return ReviewState(run_id=run_dir.name)


def save_review(state: ReviewState, run_dir: Path) -> None:
    review_path(run_dir).write_text(state.model_dump_json(indent=2), encoding="utf-8")


def current_variant(record: RunRecord, state: ReviewState, variant_id: str) -> Variant:
    original = next(v for v in record.variants if v.variant_id == variant_id)
    entry = state.variants.get(variant_id)
    if entry and entry.revisions:
        return original.model_copy(update={"fields": entry.revisions[-1].fields})
    return original


def current_gate(
    gates: dict[str, GateResult], state: ReviewState, variant_id: str
) -> GateResult | None:
    entry = state.variants.get(variant_id)
    if entry and entry.revisions:
        return entry.revisions[-1].gate
    return gates.get(variant_id)


def decide(
    state: ReviewState,
    variant_id: str,
    decision: DecisionValue,
    reason: str,
    gate: GateResult | None,
) -> Decision:
    """Freigaberegeln: rot nie freigeben; gelb nur mit Begründung; Ablehnen immer mit Grund."""
    reason = reason.strip()
    if gate is None:
        raise ReviewError("Ohne Gate-Ergebnis keine Entscheidung – zuerst das Gate laufen lassen")
    if decision == "freigegeben" and gate.status == "rot":
        raise ReviewError(
            "Rote Varianten können nicht freigegeben werden – korrigieren oder ablehnen"
        )
    if decision == "freigegeben" and gate.status == "gelb" and not reason:
        raise ReviewError("Gelbe Variante: Freigabe nur mit Begründung")
    if decision == "abgelehnt" and not reason:
        raise ReviewError("Ablehnung braucht einen Grund (fliesst in die Verbesserung der Skills)")
    entry = state.entry(variant_id)
    result = Decision(
        decision=decision,
        reason=reason,
        gate_status=gate.status,
        revision=len(entry.revisions),
        decided_at=datetime.now(UTC),
    )
    entry.decision = result
    return result


def add_revision(state: ReviewState, variant_id: str, revision: Revision) -> None:
    """Neue Fassung: ein bestehender Entscheid gilt nicht mehr (Inhalt hat sich geändert)."""
    entry = state.entry(variant_id)
    entry.revisions.append(revision)
    entry.decision = None
