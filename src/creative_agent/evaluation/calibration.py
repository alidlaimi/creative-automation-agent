"""Kalibrierung der Markenstimme-Bewertung an menschlichen Urteilen.

Mensch: «passt» / «passt_nicht» je Text (blind, ohne Modellbewertung).
Modell: Rubrik-Punkte je Kriterium. Vorhersage «passt» = Mittelwert ≥ Schwelle und kein Kriterium
≤ min_criterion. Gemessen werden Übereinstimmung, Cohens Kappa (zufallsbereinigt) und die beiden
Fehlerarten. Gewählt wird die Schwelle mit dem höchsten Kappa; bei Gleichstand die mit weniger
«falschen Freigaben» (Modell sagt passt, Mensch nicht), dann die strengere.
Zusätzlich Leave-one-out: Schwelle ohne den jeweiligen Text gewählt, dann an ihm geprüft – eine
ehrlichere Schätzung bei nur 20 Beispielen.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

from ..gate import BrandVoiceJudge, run_gate
from ..gate.judge import judge_system
from ..mcp_client import Product
from ..skills import Skill
from ..workflow.budget import CostTracker
from ..workflow.models import Variant
from .datasets import EVAL_DIR, CalibrationText
from .negatives import _ok_report

CAL_DIR = EVAL_DIR / "kalibrierung"
LABELS = CAL_DIR / "urteile.yaml"
MODEL_SCORES = CAL_DIR / "modell_urteile.json"
THRESHOLDS = [x / 4 for x in range(8, 19)]  # 2.0 … 4.5 in Viertelschritten
Label = Literal["passt", "passt_nicht"]


def as_variant(text: CalibrationText) -> Variant:
    return Variant(
        variant_id=text.id,
        channel=text.kanal,
        target_group=text.zielgruppe,
        product_id=text.produkt,
        idea="",
        fields=dict(text.felder),
    )


def deterministic_status(
    text: CalibrationText, products: dict[str, Product], skills: dict[str, Skill]
) -> str:
    import asyncio

    channel = skills["kanalformate"].rules.channels[text.kanal]
    report = _ok_report(int(channel.image.width.value), int(channel.image.height.value))
    gate = asyncio.run(
        run_gate(as_variant(text), products[text.produkt], skills, layout_report=report)
    )
    return gate.status


# ---------- Menschliche Urteile ----------


def load_labels(path: Path = LABELS) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text("utf-8")) or {}
    return data.get("urteile", {})


def save_label(text_id: str, label: Label, note: str = "", path: Path = LABELS) -> None:
    labels = load_labels(path)
    labels[text_id] = {"urteil": label, "notiz": note.strip()}
    header = (
        "# Menschliche Urteile zur Markenstimme (blind, ohne Modellbewertung).\n"
        "# Erfasst mit: uv run streamlit run src/creative_agent/evaluation/label_app.py\n"
    )
    path.write_text(
        header
        + yaml.safe_dump(
            {"urteile": dict(sorted(labels.items()))}, allow_unicode=True, sort_keys=False
        ),
        "utf-8",
    )


# ---------- Modellurteile (mit Cache: kein zweites Bezahlen für dasselbe Urteil) ----------


class ModelScore(BaseModel):
    fingerprint: str
    scores: dict[str, int]
    mean: float
    reasons: dict[str, str]
    model: str
    cost_usd: float
    judged_at: datetime


def fingerprint(text: CalibrationText, product: Product, skill: Skill, model: str) -> str:
    raw = json.dumps(
        {
            "felder": text.felder,
            "produkt": product.model_dump(mode="json"),
            "skill": skill.content_hash,
            "prompt": judge_system(skill),
            "model": model,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def load_model_scores(path: Path = MODEL_SCORES) -> dict[str, ModelScore]:
    if not path.exists():
        return {}
    return {k: ModelScore.model_validate(v) for k, v in json.loads(path.read_text("utf-8")).items()}


async def judge_texts(
    texts: list[CalibrationText],
    products: dict[str, Product],
    skills: dict[str, Skill],
    judge: BrandVoiceJudge,
    budget_usd: float,
    path: Path = MODEL_SCORES,
    progress=print,
) -> dict[str, ModelScore]:
    cache = load_model_scores(path)
    tracker = CostTracker(budget_usd)
    for t in texts:
        product = products[t.produkt]
        fp = fingerprint(t, product, skills["markenstimme"], judge.model)
        if t.id in cache and cache[t.id].fingerprint == fp:
            continue
        result = await judge.judge(as_variant(t), product, skills["markenstimme"], tracker)
        cache[t.id] = ModelScore(
            fingerprint=fp,
            scores=result.scores,
            mean=result.mean,
            reasons=result.reasons,
            model=result.model,
            cost_usd=result.cost_usd,
            judged_at=datetime.now(UTC),
        )
        path.write_text(
            json.dumps(
                {k: json.loads(v.model_dump_json()) for k, v in sorted(cache.items())},
                ensure_ascii=False,
                indent=1,
            ),
            "utf-8",
        )
        progress(f"{t.id}: Mittel {result.mean} {result.scores}")
    return cache


# ---------- Auswertung ----------


class ThresholdRow(BaseModel):
    threshold: float
    agreement: float
    kappa: float
    false_pass: int  # Modell «passt», Mensch «passt nicht»
    false_block: int  # Modell «passt nicht», Mensch «passt»


class RuleVariant(BaseModel):
    min_criterion: int
    chosen: ThresholdRow
    loo_agreement: float


class CalibrationResult(BaseModel):
    n: int
    human_pass: int
    min_criterion: int
    rows: list[ThresholdRow]
    chosen: ThresholdRow
    loo_agreement: float
    items: list[dict]
    rule_variants: list[RuleVariant] = []


def predict(score: ModelScore, threshold: float, min_criterion: int) -> bool:
    return score.mean >= threshold and min(score.scores.values()) > min_criterion


def kappa(pairs: list[tuple[bool, bool]]) -> float:
    n = len(pairs)
    if n == 0:
        return 0.0
    po = sum(a == b for a, b in pairs) / n
    pa = sum(a for a, _ in pairs) / n
    pb = sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if pe == 1 else round((po - pe) / (1 - pe), 3)


def _row(data: list[tuple[ModelScore, bool]], t: float, min_criterion: int) -> ThresholdRow:
    pairs = [(predict(s, t, min_criterion), human) for s, human in data]
    return ThresholdRow(
        threshold=t,
        agreement=round(sum(p == h for p, h in pairs) / len(pairs), 3),
        kappa=kappa(pairs),
        false_pass=sum(p and not h for p, h in pairs),
        false_block=sum(h and not p for p, h in pairs),
    )


def _choose(rows: list[ThresholdRow]) -> ThresholdRow:
    return max(rows, key=lambda r: (r.kappa, -r.false_pass, r.threshold))


def evaluate(
    scores: dict[str, ModelScore], labels: dict[str, dict], min_criterion: int = 0
) -> CalibrationResult:
    ids = sorted(set(scores) & set(labels))
    if len(ids) < 5:
        raise ValueError(f"Zu wenige beschriftete und bewertete Texte ({len(ids)})")
    data = [(scores[i], labels[i]["urteil"] == "passt") for i in ids]
    rows = [_row(data, t, min_criterion) for t in THRESHOLDS]
    chosen = _choose(rows)
    loo_hits = 0
    for k in range(len(data)):
        rest = data[:k] + data[k + 1 :]
        t = _choose([_row(rest, th, min_criterion) for th in THRESHOLDS]).threshold
        loo_hits += predict(data[k][0], t, min_criterion) == data[k][1]
    items = [
        {
            "id": i,
            "mensch": labels[i]["urteil"],
            "notiz": labels[i].get("notiz", ""),
            "modell_mittel": scores[i].mean,
            "modell_punkte": scores[i].scores,
            "modell_passt": predict(scores[i], chosen.threshold, min_criterion),
        }
        for i in ids
    ]
    return CalibrationResult(
        n=len(ids),
        human_pass=sum(h for _, h in data),
        min_criterion=min_criterion,
        rows=rows,
        chosen=chosen,
        loo_agreement=round(loo_hits / len(data), 3),
        items=items,
    )


def evaluate_with_variants(
    scores: dict[str, ModelScore], labels: dict[str, dict], min_criterion: int
) -> CalibrationResult:
    """Ergebnis für die konfigurierte Regel, plus Vergleich der Regelvarianten (Transparenz)."""
    result = evaluate(scores, labels, min_criterion)
    variants = []
    for mc in (2, 1, 0):
        r = evaluate(scores, labels, mc)
        variants.append(
            RuleVariant(min_criterion=mc, chosen=r.chosen, loo_agreement=r.loo_agreement)
        )
    return result.model_copy(update={"rule_variants": variants})
