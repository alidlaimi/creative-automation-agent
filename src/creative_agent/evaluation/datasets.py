"""Datensätze der Evaluation (YAML in eval/), mit Schema-Validierung beim Laden."""

import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..config import ROOT
from ..mcp_client import Product
from ..mcp_client.normalize import parse_search_payload

EVAL_DIR = ROOT / "eval"
FIXTURES = ROOT / "tests" / "fixtures" / "mcp"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Briefing(_Strict):
    id: str
    kategorie: str
    text: str


class BriefingSet(_Strict):
    version: str
    briefings: list[Briefing] = Field(min_length=1)

    @field_validator("briefings")
    @classmethod
    def _unique(cls, v: list[Briefing]) -> list[Briefing]:
        ids = [b.id for b in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Briefing-IDs müssen eindeutig sein")
        return v


class Expectation(_Strict):
    status: list[Literal["gruen", "gelb", "rot"]]
    regeln: list[str] = []


class NegativeCase(_Strict):
    id: str
    beschreibung: str
    kanal: str
    produkt: str
    produkt_beschreibung: str | None = None
    produkt_name: str | None = None
    felder: dict[str, str | list[str]]
    erwartet: Expectation


class NegativeSet(_Strict):
    version: str
    faelle: list[NegativeCase] = Field(min_length=1)


class CalibrationText(_Strict):
    id: str
    kanal: str
    produkt: str
    zielgruppe: str
    felder: dict[str, str]


class CalibrationSet(_Strict):
    version: str
    texte: list[CalibrationText] = Field(min_length=1)


def _load(path: Path, model: type[BaseModel]):
    return model.model_validate(yaml.safe_load(path.read_text("utf-8")))


def load_briefings(path: Path = EVAL_DIR / "briefings" / "briefings.yaml") -> BriefingSet:
    return _load(path, BriefingSet)


def load_negatives(path: Path = EVAL_DIR / "negativtests.yaml") -> NegativeSet:
    return _load(path, NegativeSet)


def load_calibration(path: Path = EVAL_DIR / "kalibrierung" / "texte.yaml") -> CalibrationSet:
    return _load(path, CalibrationSet)


def fixture_products(fixture_dir: Path = FIXTURES) -> dict[str, Product]:
    """Alle Produkte aus den aufgezeichneten MCP-Antworten (echte Galaxus-Daten)."""
    products: dict[str, Product] = {}
    for path in sorted(fixture_dir.glob("search_products_*.json")):
        data = json.loads(path.read_text("utf-8"))
        result = parse_search_payload(data["result"]["content"][0]["text"], query=path.stem)
        products.update({p.id: p for p in result.products})
    return products
