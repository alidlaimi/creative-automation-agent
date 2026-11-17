"""Eigenes Produktschema.

Bewusst unabhängig vom Antwortformat der Galaxus-Schnittstelle: Ändert Galaxus ein Feld,
wird nur die Normalisierung angepasst, nicht Workflow, Gate oder Export.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class Price(_Frozen):
    amount: Decimal = Field(description="Preis inkl. MWST, exakt (Decimal statt float)")
    currency: str


class Image(_Frozen):
    url: str
    width: int | None = None
    height: int | None = None


class Rating(_Frozen):
    average: float
    count: int


class ReviewSummary(_Frozen):
    pros: tuple[str, ...] = ()
    cons: tuple[str, ...] = ()


class Product(_Frozen):
    id: str = Field(description="Galaxus-Produkt-ID; Referenz für den Faktencheck")
    name: str
    brand: str | None = None
    product_type: str | None = None
    properties: tuple[str, ...] = Field(default=(), description="z.B. ('ANC', '60 h')")
    description: str | None = None
    price: Price | None = None
    page_url: str | None = None
    image: Image | None = None
    rating: Rating | None = None
    reviews: ReviewSummary | None = None


class SearchResult(_Frozen):
    query: str
    corrected_search_term: str | None = None
    total_count: int | None = None
    products: tuple[Product, ...] = ()
    error_message: str | None = None
    skipped_products: int = Field(default=0, description="Einträge ohne ID oder Name")
