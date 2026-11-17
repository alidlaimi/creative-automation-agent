import json
from decimal import Decimal
from pathlib import Path

import pytest

from creative_agent.mcp_client import MCPDataError
from creative_agent.mcp_client.normalize import parse_search_payload

FIXTURE = Path(__file__).parent / "fixtures" / "mcp" / "search_products_kopfhoerer.json"


@pytest.fixture
def recorded_text() -> str:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["result"]["content"][0]["text"]


def test_recorded_response_is_normalized(recorded_text):
    result = parse_search_payload(recorded_text, query="Kopfhörer")
    assert result.total_count == 905
    assert len(result.products) == 5
    assert result.skipped_products == 0
    momentum = next(p for p in result.products if p.id == "61276930")
    assert momentum.brand == "Sennheiser"
    assert momentum.price.amount == Decimal("139")
    assert momentum.price.currency == "CHF"
    assert momentum.image.url.startswith("https://www.galaxus.ch/productimages/")
    assert momentum.rating.count == 843


def test_prices_are_exact_decimals(recorded_text):
    result = parse_search_payload(recorded_text, query="Kopfhörer")
    prices = {p.id: p.price.amount for p in result.products}
    assert prices["76213675"] == Decimal("96.8")  # kein float-Rundungsfehler


def test_variants_with_same_name_stay_separate(recorded_text):
    """Gleicher Name, unterschiedliche IDs und Preise: Faktencheck muss per ID prüfen."""
    result = parse_search_payload(recorded_text, query="Kopfhörer")
    variants = [p for p in result.products if p.name == "Noise Cancelling Wired"]
    assert len({p.id for p in variants}) == 3
    assert len({p.price.amount for p in variants}) == 2


def test_properties_are_split(recorded_text):
    result = parse_search_payload(recorded_text, query="Kopfhörer")
    qc = next(p for p in result.products if p.id == "38631244")
    assert qc.properties == ("ANC", "24\xa0h", "Kabelgebunden", "Kabellos")


def test_missing_optional_fields_become_none():
    text = json.dumps({"products": [{"id": 1, "name": "Minimal"}]})
    product = parse_search_payload(text, query="x").products[0]
    assert product.price is None and product.image is None and product.rating is None
    assert product.reviews is None and product.properties == ()


def test_null_price_and_broken_fields_are_tolerated():
    raw = {
        "id": 2,
        "name": "Ohne Preis",
        "priceIfAvailable": None,
        "previewImage": {"width": 10},
        "ratingSummaryIfAvailable": {"averageRating": "kaputt"},
        "productReviewsSummaryIfAvailable": {"pros": [], "cons": []},
    }
    product = parse_search_payload(json.dumps({"products": [raw]}), query="x").products[0]
    assert (product.price, product.image, product.rating, product.reviews) == (None,) * 4


def test_unknown_fields_are_ignored():
    raw = {
        "id": 3,
        "name": "Neu",
        "stockLevel": 7,
        "priceIfAvailable": {"amountInclusive": 5, "currency": "CHF", "discount": 1},
    }
    product = parse_search_payload(json.dumps({"products": [raw]}), query="x").products[0]
    assert product.price.amount == Decimal("5")


def test_products_without_id_or_name_are_skipped():
    text = json.dumps(
        {"products": [{"name": "ohne ID"}, {"id": 4}, "kein Objekt", {"id": 5, "name": "ok"}]}
    )
    result = parse_search_payload(text, query="x")
    assert [p.id for p in result.products] == ["5"]
    assert result.skipped_products == 3


def test_error_message_without_products():
    result = parse_search_payload(json.dumps({"errorMessage": "Keine Treffer"}), query="x")
    assert result.products == () and result.error_message == "Keine Treffer"


@pytest.mark.parametrize("text", ["kein json", "[1, 2]", json.dumps({"products": "x"})])
def test_unusable_responses_raise(text):
    with pytest.raises(MCPDataError):
        parse_search_payload(text, query="x")
