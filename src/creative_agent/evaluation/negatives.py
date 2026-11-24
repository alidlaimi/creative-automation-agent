"""Negativtests: Stoppt das Gate jeden absichtlich eingebauten Fehler – und nur diese?"""

from pydantic import BaseModel

from ..gate import run_gate
from ..layouts import LayoutReport
from ..mcp_client import Product
from ..skills import Skill
from ..workflow.models import Variant
from .datasets import NegativeCase


class NegativeResult(BaseModel):
    id: str
    beschreibung: str
    expected_status: list[str]
    expected_rules: list[str]
    status: str
    rules: list[str]
    missing_rules: list[str]
    passed: bool
    is_control: bool


def _ok_report(width: int, height: int) -> LayoutReport:
    return LayoutReport(
        width=width,
        height=height,
        image_loaded=True,
        blocks=[],
        text_area_percent=10.0,
        max_text_area_percent=None,
        safe_zone_violations=[],
        overflowing=[],
        missing_elements=[],
    )


async def run_case(
    case: NegativeCase, products: dict[str, Product], skills: dict[str, Skill]
) -> NegativeResult:
    product = products[case.produkt]
    if case.produkt_beschreibung is not None:
        product = product.model_copy(update={"description": case.produkt_beschreibung})
    variant = Variant(
        variant_id=case.id,
        channel=case.kanal,
        target_group="Testfall",
        product_id=product.id,
        idea=case.beschreibung,
        fields=case.felder,
    )
    channel = skills["kanalformate"].rules.channels[case.kanal]
    report = (
        _ok_report(int(channel.image.width.value), int(channel.image.height.value))
        if channel.layout
        else None
    )
    gate = await run_gate(variant, product, skills, layout_report=report)
    rules = sorted({f.rule for f in gate.findings})
    missing = [r for r in case.erwartet.regeln if r not in rules]
    return NegativeResult(
        id=case.id,
        beschreibung=case.beschreibung,
        expected_status=list(case.erwartet.status),
        expected_rules=list(case.erwartet.regeln),
        status=gate.status,
        rules=rules,
        missing_rules=missing,
        passed=gate.status in case.erwartet.status and not missing,
        is_control="rot" not in case.erwartet.status,
    )


async def run_negatives(
    cases: list[NegativeCase], products: dict[str, Product], skills: dict[str, Skill]
) -> list[NegativeResult]:
    return [await run_case(c, products, skills) for c in cases]
