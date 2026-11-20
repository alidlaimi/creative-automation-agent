"""Ergebnisse des Quality Gates: Meldungen und Ampel je Variante."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from ..skills.models import Sourced

Severity = Literal["rot", "gelb", "info"]
Status = Literal["gruen", "gelb", "rot"]


class Finding(BaseModel):
    rule: str
    severity: Severity
    message: str
    field: str | None = None
    source: str | None = None  # Skill-Version oder offizielle Quelle


class JudgeResult(BaseModel):
    model: str
    scores: dict[str, int]
    reasons: dict[str, str]
    overall: str
    mean: float
    threshold: float
    passed: bool
    cost_usd: float


class GateResult(BaseModel):
    variant_id: str
    status: Status
    findings: list[Finding]
    judge: JudgeResult | None = None
    skills: dict[str, str]
    checked_at: datetime


def severity_for(value: Sourced | None) -> Severity:
    """Offizielles Limit / interne Vorgabe -> rot (Stopp); Empfehlung -> gelb (Mensch)."""
    if value is None or value.status == "Empfehlung":
        return "gelb"
    return "rot"


def source_of(value: Sourced | None) -> str | None:
    return f"{value.source} (geprüft {value.checked})" if value else None


def overall_status(findings: list[Finding]) -> Status:
    severities = {f.severity for f in findings}
    if "rot" in severities:
        return "rot"
    if "gelb" in severities:
        return "gelb"
    return "gruen"
