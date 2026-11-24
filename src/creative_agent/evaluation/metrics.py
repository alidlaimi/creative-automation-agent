"""Messgrössen je Lauf und gesamt – aus run.json, gate.json und (falls vorhanden) review.json."""

import json
import statistics
from pathlib import Path

from pydantic import BaseModel

FACT_RULES = {
    "preis_falsch",
    "preis_unbelegt",
    "angabe_unbelegt",
    "zahl_unbelegt",
    "superlativ",
    "bewertung_unbelegt",
}
FORMAT_RULES = {
    "zeichenlimit",
    "anzahl",
    "feld_fehlt",
    "feld_leer",
    "pflichtangabe",
    "text_ueberlauf",
    "textanteil",
    "sichere_zone",
    "bild",
}


def is_fact_rule(rule: str) -> bool:
    return rule in FACT_RULES or rule.startswith("verboten:")


class RunMetrics(BaseModel):
    briefing_id: str
    run_id: str
    run_status: str
    error: str | None = None
    variants: int = 0
    green: int = 0
    yellow: int = 0
    red: int = 0
    fact_error_variants: int = 0
    fact_errors_not_red: int = 0  # müsste immer 0 sein: Faktenfehler, die eine Sichtung erreichen
    format_ok_variants: int = 0  # ohne rote Format-/Bildmeldung, wie generiert
    format_yellow_variants: int = 0  # nur Empfehlungen verletzt
    copied_example_variants: int = 0
    judge_means: list[float] = []
    judge_passed: int = 0
    judge_count: int = 0
    cost_usd: float = 0.0
    duration_seconds: float | None = None
    approved: int = 0
    decided: int = 0
    minutes_to_last_approval: float | None = None
    rule_counts: dict[str, int] = {}


def run_metrics(briefing_id: str, run_dir: Path) -> RunMetrics:
    run = json.loads((run_dir / "run.json").read_text("utf-8"))
    m = RunMetrics(
        briefing_id=briefing_id,
        run_id=run["run_id"],
        run_status=run["status"],
        error=run.get("error"),
        cost_usd=run["cost_total_usd"],
        duration_seconds=run.get("duration_seconds"),
        variants=len(run["variants"]),
    )
    gate_path = run_dir / "gate.json"
    gates = json.loads(gate_path.read_text("utf-8")) if gate_path.exists() else []
    counts: dict[str, int] = {}
    for g in gates:
        rules = [(f["rule"], f["severity"]) for f in g["findings"]]
        for r, _ in rules:
            counts[r] = counts.get(r, 0) + 1
        m.green += g["status"] == "gruen"
        m.yellow += g["status"] == "gelb"
        m.red += g["status"] == "rot"
        fact = [r for r, _ in rules if is_fact_rule(r)]
        m.fact_error_variants += bool(fact)
        m.fact_errors_not_red += bool(fact) and g["status"] != "rot"
        fmt_red = [r for r, s in rules if r in FORMAT_RULES and s == "rot"]
        fmt_yellow = [r for r, s in rules if r in FORMAT_RULES and s == "gelb"]
        m.format_ok_variants += not fmt_red
        m.format_yellow_variants += bool(fmt_yellow) and not fmt_red
        m.copied_example_variants += any(r == "beispiel_kopiert" for r, _ in rules)
        if g.get("judge"):
            m.judge_count += 1
            m.judge_means.append(g["judge"]["mean"])
            m.judge_passed += bool(g["judge"]["passed"])
            m.cost_usd += g["judge"]["cost_usd"]
    m.rule_counts = counts
    review_path = run_dir / "review.json"
    if review_path.exists():
        from datetime import datetime

        review = json.loads(review_path.read_text("utf-8"))
        decisions = [v["decision"] for v in review["variants"].values() if v.get("decision")]
        m.decided = len(decisions)
        approvals = [d for d in decisions if d["decision"] == "freigegeben"]
        m.approved = len(approvals)
        if approvals:
            last = max(datetime.fromisoformat(d["decided_at"]) for d in approvals)
            started = datetime.fromisoformat(run["started_at"])
            m.minutes_to_last_approval = round((last - started).total_seconds() / 60, 1)
    m.cost_usd = round(m.cost_usd, 4)
    return m


class Summary(BaseModel):
    runs: int
    runs_ok: int
    variants: int
    green: int
    yellow: int
    red: int
    fact_error_variants: int
    fact_errors_not_red: int
    format_ok_share: float
    judge_mean: float | None
    judge_pass_share: float | None
    copied_example_variants: int
    cost_total_usd: float
    cost_per_variant_usd: float | None
    duration_median_s: float | None
    duration_max_s: float | None
    approval_rate: float | None
    reviewed_variants: int
    minutes_to_approval_median: float | None


def summarize(items: list[RunMetrics]) -> Summary:
    variants = sum(m.variants for m in items)
    judged = sum(m.judge_count for m in items)
    means = [x for m in items for x in m.judge_means]
    durations = [m.duration_seconds for m in items if m.duration_seconds is not None]
    decided = sum(m.decided for m in items)
    to_approval = [
        m.minutes_to_last_approval for m in items if m.minutes_to_last_approval is not None
    ]
    cost = round(sum(m.cost_usd for m in items), 4)
    return Summary(
        runs=len(items),
        runs_ok=sum(m.run_status == "ok" for m in items),
        variants=variants,
        green=sum(m.green for m in items),
        yellow=sum(m.yellow for m in items),
        red=sum(m.red for m in items),
        fact_error_variants=sum(m.fact_error_variants for m in items),
        fact_errors_not_red=sum(m.fact_errors_not_red for m in items),
        format_ok_share=round(sum(m.format_ok_variants for m in items) / variants, 3)
        if variants
        else 0.0,
        judge_mean=round(statistics.mean(means), 2) if means else None,
        judge_pass_share=round(sum(m.judge_passed for m in items) / judged, 3) if judged else None,
        copied_example_variants=sum(m.copied_example_variants for m in items),
        cost_total_usd=cost,
        cost_per_variant_usd=round(cost / variants, 4) if variants else None,
        duration_median_s=round(statistics.median(durations), 1) if durations else None,
        duration_max_s=round(max(durations), 1) if durations else None,
        approval_rate=round(sum(m.approved for m in items) / decided, 3) if decided else None,
        reviewed_variants=decided,
        minutes_to_approval_median=round(statistics.median(to_approval), 1)
        if to_approval
        else None,
    )
