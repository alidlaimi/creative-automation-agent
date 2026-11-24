"""Quality Gate: alle Regeln je Variante, Ampel mit Begründung, vor jeder menschlichen Sichtung."""

from datetime import UTC, datetime

from ..layouts import LayoutReport
from ..mcp_client import Product
from ..skills import Skill
from ..workflow.budget import CostTracker
from ..workflow.models import Variant
from .findings import Finding, GateResult, overall_status
from .judge import BrandVoiceJudge
from .rules import (
    check_brand_rules,
    check_facts,
    check_format,
    check_layout,
    check_suspicious_product_text,
)


async def run_gate(
    variant: Variant,
    product: Product | None,
    skills: dict[str, Skill],
    *,
    layout_report: LayoutReport | None = None,
    judge: BrandVoiceJudge | None = None,
    tracker: CostTracker | None = None,
) -> GateResult:
    channel = skills["kanalformate"].rules.channels.get(variant.channel)
    findings: list[Finding] = []
    if channel is None:
        findings.append(
            Finding(
                rule="kanal_unbekannt",
                severity="rot",
                message=f"Kanal {variant.channel!r} nicht im Skill kanalformate",
            )
        )
    if product is None:
        findings.append(
            Finding(
                rule="produkt_unbekannt",
                severity="rot",
                message=f"Produkt {variant.product_id} nicht im Datensatz des Laufs",
            )
        )
    if channel is not None and product is not None:
        findings += check_format(variant, channel, skills["kanalformate"])
        findings += check_layout(layout_report, channel)
        findings += check_facts(variant, product, skills["faktencheck"])
        findings += check_suspicious_product_text(product)
        findings += check_brand_rules(variant, skills["markenstimme"])

    judge_result = None
    if judge is not None and product is not None:
        if overall_status(findings) == "rot":
            findings.append(
                Finding(
                    rule="markenstimme_bewertung",
                    severity="info",
                    message="Nicht bewertet – Variante ist bereits rot (spart Kosten)",
                )
            )
        else:
            judge_result = await judge.judge(
                variant, product, skills["markenstimme"], tracker or CostTracker(1.0)
            )
            if not judge_result.passed:
                weak = [f"{k}={v}" for k, v in judge_result.scores.items()]
                findings.append(
                    Finding(
                        rule="markenstimme_bewertung",
                        severity="gelb",
                        message=f"Markenstimme unter Schwellwert (Mittel {judge_result.mean} < "
                        f"{judge_result.threshold}"
                        + (
                            f" oder ein Kriterium ≤ {judge.min_criterion}"
                            if judge.min_criterion
                            else ""
                        )
                        + "): "
                        f"{', '.join(weak)} – {judge_result.overall}",
                        source=f"markenstimme {skills['markenstimme'].version} (kalibriert, "
                        "nur Hinweis – siehe eval/kalibrierung)",
                    )
                )

    return GateResult(
        variant_id=variant.variant_id,
        status=overall_status(findings),
        findings=findings,
        judge=judge_result,
        skills={s.name: s.version for s in skills.values()},
        checked_at=datetime.now(UTC),
    )
