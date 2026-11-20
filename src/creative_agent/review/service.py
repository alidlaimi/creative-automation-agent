"""Korrektur einer Variante: neu rendern (falls Bildkanal) und erneut durchs Gate."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from ..gate import BrandVoiceJudge, run_gate
from ..layouts import LayoutReport
from ..skills import Skill
from ..workflow.budget import CostTracker
from ..workflow.models import RunRecord, Variant
from .store import ReviewState, Revision, add_revision, current_variant

# Rendert eine Variante und liefert (Messbericht, PNG-Pfad); None, wenn kein Bildkanal.
Renderer = Callable[[Variant, int], Awaitable[tuple[LayoutReport, str] | None]]


def parse_edit(variant: Variant, raw: dict[str, str]) -> dict[str, str | list[str]]:
    """Formularwerte -> Felder. Listenfelder: ein Eintrag pro Zeile."""
    fields: dict[str, str | list[str]] = {}
    for key, old in variant.fields.items():
        value = raw.get(key, "")
        if isinstance(old, list):
            fields[key] = [line.strip() for line in value.splitlines() if line.strip()]
        else:
            fields[key] = value.strip()
    return fields


async def revise_variant(
    record: RunRecord,
    state: ReviewState,
    variant_id: str,
    new_fields: dict[str, str | list[str]],
    skills: dict[str, Skill],
    *,
    render: Renderer | None = None,
    judge: BrandVoiceJudge | None = None,
    tracker: CostTracker | None = None,
) -> Revision:
    base = current_variant(record, state, variant_id)
    edited = base.model_copy(update={"fields": new_fields})
    revision_no = len(state.entry(variant_id).revisions) + 1
    report, png = None, None
    if render is not None:
        rendered = await render(edited, revision_no)
        if rendered is not None:
            report, png = rendered
    gate = await run_gate(
        edited,
        record.products.get(edited.product_id),
        skills,
        layout_report=report,
        judge=judge,
        tracker=tracker,
    )
    revision = Revision(
        fields=new_fields,
        edited_at=datetime.now(UTC),
        gate=gate,
        layout_report=report,
        png_path=png,
    )
    add_revision(state, variant_id, revision)
    return revision


def layout_renderer_for(record: RunRecord, run_dir, skills: dict[str, Skill]) -> Renderer:
    """Renderer für korrigierte Varianten: PNG + Hilfslinien-PNG je Revision."""
    from ..config import ROOT
    from ..layouts import LayoutRenderer, compose_html, layout_spec
    from ..layouts.images import ImageFetcher

    async def render(variant: Variant, revision_no: int):
        channel = skills["kanalformate"].rules.channels[variant.channel]
        if not channel.layout:
            return None
        spec = layout_spec(channel)
        product = record.products[variant.product_id]
        image = None
        if product.image:
            image = ImageFetcher(ROOT / "data" / "cache" / "images").data_uri(product.image.url)
        out = run_dir / "assets" / f"{variant.variant_id}-r{revision_no}.png"
        async with LayoutRenderer() as renderer:
            report = await renderer.render(
                compose_html(spec, variant, product, image_src=image), spec, out
            )
            await renderer.render(
                compose_html(spec, variant, product, image_src=image, show_guides=True),
                spec,
                out.with_name(f"{variant.variant_id}-r{revision_no}-hilfslinien.png"),
            )
        return report, str(out)

    return render
