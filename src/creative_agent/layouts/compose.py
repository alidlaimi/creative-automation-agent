"""Füllt die HTML-Templates. Ohne Browser – dadurch schnell testbar.

Preis und Produktname kommen aus den Produktdaten, nie vom Modell.
Autoescape ist an: Text aus Schnittstelle oder Modell kann kein HTML/JS einschleusen.
"""

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from ..mcp_client import Product
from ..skills.models import Channel
from ..workflow.models import Variant

TEMPLATES = Path(__file__).resolve().parents[3] / "templates"

PLACEHOLDER_IMAGE = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 400'>"
    "<rect width='400' height='400' fill='%23ece8df'/>"
    "<circle cx='200' cy='170' r='90' fill='none' stroke='%23b9b2a4' stroke-width='18'/>"
    "<rect x='95' y='170' width='40' height='90' rx='16' fill='%23b9b2a4'/>"
    "<rect x='265' y='170' width='40' height='90' rx='16' fill='%23b9b2a4'/>"
    "<text x='200' y='340' font-family='sans-serif' font-size='26' fill='%238a8476' "
    "text-anchor='middle'>Platzhalter</text></svg>"
)


def format_chf(amount: Decimal) -> str:
    """Schweizer Schreibweise: CHF 79.– bzw. CHF 96.80"""
    if amount == amount.to_integral_value():
        return f"CHF {int(amount)}.–"
    return f"CHF {amount.quantize(Decimal('0.01'))}"


@dataclass(frozen=True)
class SafeZone:
    top: float = 0
    bottom: float = 0
    left: float = 0
    right: float = 0


@dataclass(frozen=True)
class LayoutSpec:
    layout: str
    width: int
    height: int
    safe: SafeZone
    max_text_area_percent: float | None
    required_elements: tuple[str, ...]


def layout_spec(channel: Channel) -> LayoutSpec:
    if not channel.layout or channel.image is None:
        raise ValueError(f"Kanal {channel.label!r} hat kein Layout")
    img = channel.image
    sz = img.safe_zone

    def pct(value) -> float:
        return float(value.value) if value else 0.0

    return LayoutSpec(
        layout=channel.layout,
        width=int(img.width.value),
        height=int(img.height.value),
        safe=SafeZone(
            top=pct(sz.top) if sz else 0,
            bottom=pct(sz.bottom) if sz else 0,
            left=pct(sz.left) if sz else 0,
            right=pct(sz.right) if sz else 0,
        ),
        max_text_area_percent=(
            float(img.max_text_area_percent.value) if img.max_text_area_percent else None
        ),
        required_elements=tuple(
            channel.required_elements.value if channel.required_elements else ()
        ),
    )


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(enabled_extensions=("html", "j2"), default=True),
        undefined=StrictUndefined,  # fehlende Variable = Fehler statt leerer Fläche
    )


def compose_html(
    spec: LayoutSpec,
    variant: Variant,
    product: Product,
    *,
    use_remote_image: bool = True,
    show_guides: bool = False,
    image_src: str | None = None,
) -> str:
    """image_src: bereits geladenes Bild (data-URI); sonst URL bzw. Platzhalter."""
    if image_src is None:
        image_src = product.image.url if (use_remote_image and product.image) else PLACEHOLDER_IMAGE
    headline = variant.fields.get("ueberschrift") or variant.fields.get("titel") or ""
    if isinstance(headline, list):
        headline = headline[0] if headline else ""
    return (
        _env()
        .get_template(f"{spec.layout}.html.j2")
        .render(
            layout=spec.layout,
            w=spec.width,
            h=spec.height,
            safe=spec.safe,
            show_guides=show_guides,
            image_src=image_src,
            product_name=" ".join(x for x in (product.brand, product.name) if x),
            headline=headline,
            price=format_chf(product.price.amount) if product.price else "",
            cta=str(variant.fields.get("cta", "")),
        )
    )
