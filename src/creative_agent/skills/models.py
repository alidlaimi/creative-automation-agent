"""Schemas der Skill-Regeln (rules.yaml).

Die YAML-Schlüssel sind deutsch (für das Kreativ-Team), die Python-Attribute englisch.
`extra="forbid"`: Ein Tippfehler im Schlüssel (z.B. `max_zeichn`) fällt beim Laden auf,
statt dass die Regel still ignoriert wird.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Status = Literal["offizielles Limit", "Empfehlung", "interne Vorgabe"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class Sourced(Strict):
    """Ein Wert mit Herkunft. Ohne Quelle und Prüfdatum lässt sich kein Wert laden."""

    value: int | float | str | list[str] = Field(alias="wert")
    status: Status
    source: str = Field(alias="quelle")
    checked: date = Field(alias="geprueft")
    note: str | None = Field(default=None, alias="hinweis")

    @field_validator("source")
    @classmethod
    def _source_is_url_or_repo_path(cls, v: str) -> str:
        v = v.strip()
        if v.startswith("https://") or v.startswith(("docs/", "skills/")):
            return v
        raise ValueError("Quelle muss eine https-URL oder ein Pfad unter docs/ bzw. skills/ sein")


# ---------- kanalformate ----------


class TextFieldSpec(Strict):
    label: str = Field(alias="bezeichnung")
    max_chars: Sourced | None = Field(default=None, alias="max_zeichen")
    min_chars: Sourced | None = Field(default=None, alias="min_zeichen")
    min_count: Sourced | None = Field(default=None, alias="min_anzahl")
    max_count: Sourced | None = Field(default=None, alias="max_anzahl")


class SafeZone(Strict):
    top: Sourced | None = Field(default=None, alias="oben_prozent")
    bottom: Sourced | None = Field(default=None, alias="unten_prozent")
    left: Sourced | None = Field(default=None, alias="links_prozent")
    right: Sourced | None = Field(default=None, alias="rechts_prozent")


class ImageSpec(Strict):
    width: Sourced = Field(alias="breite_px")
    height: Sourced = Field(alias="hoehe_px")
    aspect_ratio: Sourced = Field(alias="seitenverhaeltnis")
    max_text_area_percent: Sourced | None = Field(default=None, alias="max_textanteil_prozent")
    safe_zone: SafeZone | None = Field(default=None, alias="sichere_zone")


class Channel(Strict):
    label: str = Field(alias="name")
    platform: str = Field(alias="plattform")
    layout: str | None = Field(default=None, description="Name des HTML-Templates")
    image: ImageSpec | None = Field(default=None, alias="bild")
    text_fields: dict[str, TextFieldSpec] = Field(alias="textfelder")
    required_elements: Sourced | None = Field(default=None, alias="pflichtangaben")

    @model_validator(mode="after")
    def _layout_needs_image(self) -> "Channel":
        if self.layout and self.image is None:
            raise ValueError("Kanal mit Layout braucht eine Bildangabe ('bild')")
        if not self.text_fields:
            raise ValueError("Kanal braucht mindestens ein Textfeld")
        return self


class ChannelFormatsRules(Strict):
    channels: dict[str, Channel] = Field(alias="kanaele")


# ---------- faktencheck ----------


class ForbiddenClaim(Strict):
    category: str = Field(alias="kategorie")
    reason: str = Field(alias="begruendung")
    terms: list[str] = Field(alias="begriffe", min_length=1)


class FactCheckRules(Strict):
    currency: str = Field(alias="waehrung")
    price_must_match_exactly: bool = Field(alias="preis_exakt")
    units: list[str] = Field(alias="einheiten", min_length=1)
    evidence_fields: list[Literal["name", "properties", "description", "brand", "product_type"]] = (
        Field(alias="belegfelder", min_length=1)
    )
    superlatives: list[str] = Field(alias="superlative_nur_mit_beleg")
    forbidden_claims: list[ForbiddenClaim] = Field(alias="verbotene_aussagen", min_length=1)
    rating_claims_need_evidence: bool = Field(alias="bewertungen_nur_mit_beleg")


# ---------- markenstimme ----------


class RubricCriterion(Strict):
    id: str
    name: str
    question: str = Field(alias="frage")
    score_high: str = Field(alias="hoch")
    score_low: str = Field(alias="tief")


class Rubric(Strict):
    scale_min: int = Field(alias="skala_min")
    scale_max: int = Field(alias="skala_max")
    criteria: list[RubricCriterion] = Field(alias="kriterien", min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> "Rubric":
        ids = [c.id for c in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("Kriterien-IDs müssen eindeutig sein")
        if self.scale_min >= self.scale_max:
            raise ValueError("skala_min muss kleiner als skala_max sein")
        return self


class BrandVoiceRules(Strict):
    address_form: Literal["du", "sie"] = Field(alias="anrede")
    forbidden_characters: list[str] = Field(alias="verbotene_zeichen")
    max_exclamation_marks: int = Field(alias="max_ausrufezeichen", ge=0)
    forbidden_phrases: list[str] = Field(alias="verbotene_floskeln")
    rubric: Rubric = Field(alias="rubrik")


RULE_MODELS: dict[str, type[Strict]] = {
    "kanalformate": ChannelFormatsRules,
    "faktencheck": FactCheckRules,
    "markenstimme": BrandVoiceRules,
}
