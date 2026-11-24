import asyncio

from creative_agent.config import ROOT
from creative_agent.evaluation.datasets import (
    fixture_products,
    load_briefings,
    load_calibration,
    load_negatives,
)
from creative_agent.evaluation.negatives import run_negatives
from creative_agent.skills import load_skills

SKILLS = load_skills(ROOT / "skills")


def test_briefing_set_has_15_varied_briefings():
    s = load_briefings()
    assert len(s.briefings) == 15
    assert len({b.kategorie for b in s.briefings}) >= 12
    text = " ".join(b.text for b in s.briefings).lower()
    for channel_word in ("story", "feed", "suchanzeige", "banner"):
        assert channel_word in text


def test_every_negative_case_is_stopped_and_controls_pass():
    cases = load_negatives().faelle
    results = asyncio.run(run_negatives(cases, fixture_products(), SKILLS))
    failed = [(r.id, r.status, r.missing_rules, r.rules) for r in results if not r.passed]
    assert not failed, failed
    assert sum(r.is_control for r in results) >= 3
    assert sum(not r.is_control for r in results) >= 15


def test_negative_cases_reference_known_products_and_channels():
    products = fixture_products()
    channels = SKILLS["kanalformate"].rules.channels
    for case in load_negatives().faelle:
        assert case.produkt in products and case.kanal in channels, case.id


def test_calibration_texts_pass_deterministic_rules():
    """Kalibriert wird nur, was die Regeln nicht entscheiden: Texte dürfen nicht rot sein."""
    from creative_agent.evaluation.calibration import deterministic_status

    products = fixture_products()
    bad = {
        t.id: s
        for t in load_calibration().texte
        if (s := deterministic_status(t, products, SKILLS)) == "rot"
    }
    assert not bad, bad
