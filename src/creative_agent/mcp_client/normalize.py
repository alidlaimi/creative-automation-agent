"""Übersetzt die Rohantwort von `search_products` in das eigene Produktschema.

Grundsätze:
- Fehlende optionale Felder -> None, kein Absturz.
- Unbekannte neue Felder -> ignoriert (Schemaänderung bricht nichts).
- Einträge ohne ID oder Name -> verworfen und gezählt; ohne ID ist kein Faktencheck möglich.
- Preise als Decimal aus dem Originaltext, damit 96.8 exakt 96.8 bleibt.
"""

import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from .schema import Image, Price, Product, Rating, ReviewSummary, SearchResult

log = logging.getLogger(__name__)


class MCPDataError(ValueError):
    """Antwort der Schnittstelle ist nicht verwertbar."""


def _str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _price(raw: Any) -> Price | None:
    if not isinstance(raw, dict):
        return None
    amount, currency = raw.get("amountInclusive"), _str(raw.get("currency"))
    if amount is None or currency is None or isinstance(amount, bool):
        return None
    try:
        return Price(amount=Decimal(str(amount)), currency=currency)
    except InvalidOperation:
        log.warning("Ungültiger Preis ignoriert: %r", raw)
        return None


def _image(raw: Any) -> Image | None:
    if not isinstance(raw, dict) or not _str(raw.get("url")):
        return None
    width, height = raw.get("width"), raw.get("height")
    return Image(
        url=_str(raw["url"]),
        width=width if isinstance(width, int) else None,
        height=height if isinstance(height, int) else None,
    )


def _rating(raw: Any) -> Rating | None:
    if not isinstance(raw, dict):
        return None
    try:
        return Rating(average=float(raw["averageRating"]), count=int(raw["ratingCount"]))
    except (KeyError, TypeError, ValueError):
        return None


def _reviews(raw: Any) -> ReviewSummary | None:
    if not isinstance(raw, dict):
        return None

    def clean(items: Any) -> tuple[str, ...]:
        if not isinstance(items, list):
            return ()
        return tuple(s for s in (_str(i) for i in items) if s)

    summary = ReviewSummary(pros=clean(raw.get("pros")), cons=clean(raw.get("cons")))
    return summary if summary.pros or summary.cons else None


def _properties(raw: Any) -> tuple[str, ...]:
    if isinstance(raw, list):
        parts = raw
    elif isinstance(raw, str):
        parts = raw.split(",")
    else:
        return ()
    return tuple(s for s in (_str(p) for p in parts) if s)


def normalize_product(raw: dict[str, Any]) -> Product | None:
    product_id, name = _str(raw.get("id")), _str(raw.get("name"))
    if product_id is None or name is None:
        return None
    return Product(
        id=product_id,
        name=name,
        brand=_str(raw.get("brand")),
        product_type=_str(raw.get("productType")),
        properties=_properties(raw.get("properties")),
        description=_str(raw.get("description")),
        price=_price(raw.get("priceIfAvailable")),
        page_url=_str(raw.get("pageUrl")),
        image=_image(raw.get("previewImage")),
        rating=_rating(raw.get("ratingSummaryIfAvailable")),
        reviews=_reviews(raw.get("productReviewsSummaryIfAvailable")),
    )


def parse_search_payload(text: str, query: str) -> SearchResult:
    """`text` ist der Inhalt von content[0].text der Tool-Antwort (JSON als String)."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MCPDataError(f"Antwort ist kein gültiges JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise MCPDataError("Antwort ist kein JSON-Objekt")

    raw_products = payload.get("products") or []
    if not isinstance(raw_products, list):
        raise MCPDataError("Feld 'products' ist keine Liste")

    products, skipped = [], 0
    for raw in raw_products:
        product = normalize_product(raw) if isinstance(raw, dict) else None
        if product is None:
            skipped += 1
        else:
            products.append(product)
    if skipped:
        log.warning("%d Produkt(e) ohne ID oder Name verworfen", skipped)

    total = payload.get("totalCount")
    return SearchResult(
        query=query,
        corrected_search_term=_str(payload.get("correctedSearchTerm")),
        total_count=total if isinstance(total, int) else None,
        products=tuple(products),
        error_message=_str(payload.get("errorMessage")),
        skipped_products=skipped,
    )
