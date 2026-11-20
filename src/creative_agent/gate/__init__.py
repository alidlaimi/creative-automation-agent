"""Quality Gate: Regeln, Faktencheck und Markenstimme – Ampel je Variante mit Begründung."""

from .findings import Finding, GateResult, JudgeResult
from .gate import run_gate
from .judge import BrandVoiceJudge

__all__ = ["BrandVoiceJudge", "Finding", "GateResult", "JudgeResult", "run_gate"]
