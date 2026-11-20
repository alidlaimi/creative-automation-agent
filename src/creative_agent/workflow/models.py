"""Datenmodelle des Workflows: Briefing, Auswahl, Varianten, Lauf-Protokoll."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from ..mcp_client import Product


class BriefingSpec(BaseModel):
    """Vom Modell aus dem Freitext-Briefing gelesen – wird in der Review angezeigt."""

    product_query: str = Field(
        description="Kurzer Suchbegriff für die Produktsuche, z.B. 'Kopfhörer Noise Cancelling'"
    )
    min_price_chf: int | None = Field(description="Untere Preisgrenze in CHF oder null")
    max_price_chf: int | None = Field(description="Obere Preisgrenze in CHF oder null")
    channels: list[str] = Field(description="Kanal-IDs, nur aus der erlaubten Liste")
    target_groups: list[str] = Field(description="Zielgruppen, z.B. 'Studierende'")
    campaign_goal: str = Field(description="Ziel der Kampagne in einem Satz")
    language: Literal["de", "fr", "it", "en"] = Field(description="Sprache der Werbetexte")


class ProductChoice(BaseModel):
    product_id: str
    reason: str


class SearchLog(BaseModel):
    query: str
    min_price: int | None = None
    max_price: int | None = None
    total_count: int | None = None
    product_ids: list[str]


class Variant(BaseModel):
    variant_id: str
    channel: str
    target_group: str
    product_id: str
    idea: str
    fields: dict[str, str | list[str]]


class CostLine(BaseModel):
    step: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class SkillRef(BaseModel):
    name: str
    version: str
    content_hash: str


class RunRecord(BaseModel):
    """Alles, was nötig ist, um ein Werbemittel nachzuvollziehen – ohne Personendaten."""

    run_id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: Literal["ok", "budget_exceeded", "timeout", "error"] = "ok"
    error: str | None = None
    briefing_text: str
    briefing: BriefingSpec | None = None
    models: dict[str, str]
    skills: list[SkillRef]
    searches: list[SearchLog] = []
    products: dict[str, Product] = Field(default_factory=dict, description="Datenbasis Faktencheck")
    selection: list[ProductChoice] = []
    research_completed_by: str | None = None
    variants: list[Variant] = []
    costs: list[CostLine] = []
    cost_total_usd: float = 0.0
    budget_usd: float
    duration_seconds: float | None = None
