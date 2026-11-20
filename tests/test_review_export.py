"""Review-Regeln, Korrekturen und Export – mit einem gescripteten Lauf, ohne Netz."""

import asyncio
import csv
import hashlib
import json
from pathlib import Path

import pytest
from fakes import ScriptedLLM, tool_use

from creative_agent.export import ExportError, clean_url, export_run
from creative_agent.gate import run_gate
from creative_agent.mcp_client import FixtureToolCaller, GalaxusProductSearch
from creative_agent.review import (
    ReviewError,
    current_gate,
    current_variant,
    decide,
    load_review,
    save_review,
)
from creative_agent.review.service import parse_edit, revise_variant
from creative_agent.skills import load_skills
from creative_agent.workflow import run_workflow, save_run

ROOT = Path(__file__).resolve().parents[1]
SKILLS = load_skills(ROOT / "skills")
BRIEFING = {
    "product_query": "Kopfhörer",
    "min_price_chf": None,
    "max_price_chf": 200,
    "channels": ["meta_feed", "google_ads_rsa"],
    "target_groups": ["Studierende"],
    "campaign_goal": "Pendler-Kopfhörer",
    "language": "de",
}
FEED = {
    "varianten": [
        {
            "product_id": "61276930",
            "idee": "a",
            "primaertext": "Lange Zugfahrt? 60 h Akku und ANC halten dich ruhig.",
            "ueberschrift": "Ruhe im Zug",
            "cta": "Ansehen",
        },
        {
            "product_id": "61276930",
            "idee": "b",
            "primaertext": "Jetzt mit Rabatt: 60 h Akku und ANC für jede Zugfahrt.",
            "ueberschrift": "Ruhe im Zug",
            "cta": "Ansehen",
        },
    ]
}
RSA = {
    "varianten": [
        {
            "product_id": "61276930",
            "idee": "c",
            "titel": ["Ruhe im Zug", "60 h Akku für Pendler", "Momentum 4 Wireless"],
            "beschreibung": ["ANC und 60 h Akku für lange Zugfahrten.", "Für Pendler mit Ohren."],
            "pfad": "kopfhoerer",
        },
        {
            "product_id": "61276930",
            "idee": "d",
            "titel": ["Ruhe im Zug", "60 h Akku", "Momentum 4"],
            "beschreibung": ["ANC für den Zug.", "Für Pendler."],
            "pfad": "anc",
        },
    ]
}


@pytest.fixture
def run(tmp_path):
    llm = ScriptedLLM(
        structured=[BRIEFING, FEED, RSA],
        tools=[
            [
                tool_use(
                    "search_products", {"query": "Kopfhörer", "min_price": None, "max_price": 200}
                )
            ],
            [
                tool_use(
                    "select_products",
                    {"choices": [{"product_id": "61276930", "reason": "60 h"}]},
                    "t2",
                )
            ],
        ],
    )
    search = GalaxusProductSearch(
        FixtureToolCaller(ROOT / "tests/fixtures/mcp"),
        server_url="https://mcp.galaxus.ch",
        agent_info="t",
        min_interval_seconds=0,
    )
    record = asyncio.run(
        run_workflow(
            "x",
            llm=llm,
            search=search,
            skills=SKILLS,
            model="claude-sonnet-5-5",
            model_fast="claude-haiku-5-5",
            budget_usd=1,
            timeout_seconds=30,
        )
    )
    assert record.status == "ok", record.error
    save_run(record, tmp_path)
    run_dir = tmp_path / record.run_id
    gates = {}
    for v in record.variants:
        gates[v.variant_id] = asyncio.run(run_gate(v, record.products[v.product_id], SKILLS))
    (run_dir / "gate.json").write_text(
        json.dumps([json.loads(g.model_dump_json()) for g in gates.values()]), "utf-8"
    )
    (run_dir / "assets").mkdir()
    from PIL import Image

    Image.new("RGB", (36, 45), "white").save(run_dir / "assets" / "meta_feed-z1-1.png")
    return record, gates, run_dir


# ---------- Freigaberegeln ----------


def test_red_variant_cannot_be_approved(run):
    record, gates, run_dir = run
    state = load_review(run_dir)
    assert gates["meta_feed-z1-2"].status == "rot"  # Rabatt-Aussage
    with pytest.raises(ReviewError, match="Rote"):
        decide(state, "meta_feed-z1-2", "freigegeben", "passt schon", gates["meta_feed-z1-2"])


def test_yellow_needs_reason_reject_needs_reason(run):
    record, gates, run_dir = run
    state = load_review(run_dir)
    yellow = gates["meta_feed-z1-1"]
    assert yellow.status == "gelb"  # kein Messbericht im Test
    with pytest.raises(ReviewError, match="Begründung"):
        decide(state, "meta_feed-z1-1", "freigegeben", "  ", yellow)
    decide(state, "meta_feed-z1-1", "freigegeben", "Layout visuell geprüft", yellow)
    with pytest.raises(ReviewError, match="Grund"):
        decide(state, "meta_feed-z1-2", "abgelehnt", "", gates["meta_feed-z1-2"])


def test_correction_reruns_gate_and_resets_decision(run):
    record, gates, run_dir = run
    state = load_review(run_dir)
    vid = "meta_feed-z1-2"
    decide(state, vid, "abgelehnt", "Rabatt-Aussage", gates[vid])
    raw = {
        "primaertext": "Lange Zugfahrt? 60 h Akku und ANC halten dich unterwegs ruhig.",
        "ueberschrift": "Ruhe im Zug",
        "cta": "Ansehen",
    }
    rev = asyncio.run(
        revise_variant(
            record, state, vid, parse_edit(current_variant(record, state, vid), raw), SKILLS
        )
    )
    assert rev.gate.status != "rot"
    assert state.variants[vid].decision is None  # neuer Inhalt -> neuer Entscheid nötig
    assert current_gate(gates, state, vid).status == rev.gate.status
    save_review(state, run_dir)
    reloaded = load_review(run_dir)
    assert current_variant(record, reloaded, vid).fields["primaertext"].startswith("Lange")
    original = json.loads((run_dir / "run.json").read_text("utf-8"))
    assert "Rabatt" in original["variants"][1]["fields"]["primaertext"]  # Original bleibt


def test_list_fields_are_edited_line_by_line(run):
    record, _, _ = run
    rsa = next(v for v in record.variants if v.channel == "google_ads_rsa")
    fields = parse_edit(rsa, {"titel": "A\n\nB\n C ", "beschreibung": "x\ny", "pfad": " p "})
    assert fields == {"titel": ["A", "B", "C"], "beschreibung": ["x", "y"], "pfad": "p"}


# ---------- Export ----------


def _approve_all_possible(record, gates, run_dir):
    state = load_review(run_dir)
    for v in record.variants:
        g = gates[v.variant_id]
        if g.status != "rot":
            decide(state, v.variant_id, "freigegeben", "geprüft", g)
    return state


def test_export_contains_only_approved(run):
    record, gates, run_dir = run
    state = _approve_all_possible(record, gates, run_dir)
    result = export_run(record, state, gates, run_dir)
    assert "meta_feed-z1-2" not in result.variant_ids  # rot, nicht freigegeben
    assert set(result.variant_ids) == {
        "meta_feed-z1-1",
        "google_ads_rsa-z1-1",
        "google_ads_rsa-z1-2",
    }


def test_google_csv_uses_official_columns_and_is_paused(run):
    record, gates, run_dir = run
    result = export_run(record, _approve_all_possible(record, gates, run_dir), gates, run_dir)
    path = Path(result.directory) / "google_ads_rsa.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    header = path.read_text("utf-8").splitlines()[0].split(",")
    assert header[:3] == ["Campaign", "Ad group", "Headline 1"]
    assert "Headline 15" in header and "Description 4" in header and "Final URL" in header
    assert all(r["Status"] == "Paused" for r in rows)
    assert rows[0]["Headline 3"] == "Momentum 4 Wireless" and rows[0]["Path 1"] == "kopfhoerer"
    assert "utm_" not in rows[0]["Final URL"] and rows[0]["Final URL"].startswith("https://")
    assert rows[0]["Labels"].endswith("google_ads_rsa-z1-1")


def test_manifest_and_assets(run):
    record, gates, run_dir = run
    result = export_run(record, _approve_all_possible(record, gates, run_dir), gates, run_dir)
    out = Path(result.directory)
    manifest = json.loads((out / "manifest.json").read_text("utf-8"))
    item = next(i for i in manifest["items"] if i["variant_id"] == "meta_feed-z1-1")
    assert (
        item["image_sha256"] == hashlib.sha256((out / item["image_file"]).read_bytes()).hexdigest()
    )
    assert item["decision_reason"] == "geprüft" and manifest["skills"]["faktencheck"].startswith(
        "1."
    )
    assert Path(result.zip_path).exists()
    meta = list(csv.DictReader((out / "meta_ads.csv").open(encoding="utf-8")))
    assert [r["variant_id"] for r in meta] == ["meta_feed-z1-1"] and meta[0]["price"] == "CHF 139.–"


def test_export_refuses_tampered_or_stale_approvals(run):
    record, gates, run_dir = run
    state = load_review(run_dir)
    with pytest.raises(ExportError, match="Keine"):
        export_run(record, state, gates, run_dir)
    # manipuliert: rote Variante als freigegeben eingetragen
    state = _approve_all_possible(record, gates, run_dir)
    red = gates["meta_feed-z1-2"].model_copy(update={"status": "gruen"})
    decide(state, "meta_feed-z1-2", "freigegeben", "x", red)
    with pytest.raises(ExportError, match="Gate rot"):
        export_run(record, state, gates, run_dir)


def test_clean_url_removes_only_tracking():
    url = "https://www.galaxus.ch/de/s1/product/x-123?utm_source=shop-mcp&utm_medium=tool&v=2"
    assert clean_url(url) == "https://www.galaxus.ch/de/s1/product/x-123?v=2"


# ---------- Oberfläche (Streamlit AppTest, ohne Browser) ----------


def test_review_app_renders_run(run, monkeypatch):
    from streamlit.testing.v1 import AppTest

    record, _, run_dir = run
    monkeypatch.setenv("CAA_RUNS_DIR", str(run_dir.parent))
    at = AppTest.from_file(str(ROOT / "src/creative_agent/review/app.py"), default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    assert at.title[0].value == "Review"
    assert at.metric[0].value == str(len(record.variants))
    labels = [b.label for b in at.button]
    assert labels.count("Freigeben") == len(record.variants)
