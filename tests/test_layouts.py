import asyncio
from decimal import Decimal
from pathlib import Path

import pytest

from creative_agent.layouts import analyse, compose_html, format_chf, layout_spec
from creative_agent.mcp_client import Image, Price, Product
from creative_agent.skills import load_skills
from creative_agent.workflow.models import Variant

ROOT = Path(__file__).resolve().parents[1]
CHANNELS = load_skills(ROOT / "skills")["kanalformate"].rules.channels
PRODUCT = Product(
    id="67496978",
    name="Headphone (a)",
    brand="Nothing",
    properties=("ANC", "75\xa0h"),
    price=Price(amount=Decimal("79"), currency="CHF"),
    image=Image(url="https://www.galaxus.ch/productimages/test", width=800, height=1000),
)


def variant(channel="meta_story", headline="Ruhe im Zug", cta="Ansehen"):
    return Variant(
        variant_id="v1",
        channel=channel,
        target_group="Studierende",
        product_id=PRODUCT.id,
        idea="",
        fields={"ueberschrift": headline, "cta": cta},
    )


# ---------- Spezifikation aus dem Skill ----------


def test_layout_spec_takes_safe_zones_from_skill():
    story = layout_spec(CHANNELS["meta_story"])
    assert (story.width, story.height) == (1440, 2560)
    assert (story.safe.top, story.safe.bottom, story.safe.left, story.safe.right) == (14, 35, 6, 6)
    banner = layout_spec(CHANNELS["google_display_banner"])
    assert banner.max_text_area_percent == 20 and banner.safe.left == 5


def test_text_only_channel_has_no_layout():
    with pytest.raises(ValueError):
        layout_spec(CHANNELS["google_ads_rsa"])


@pytest.mark.parametrize(
    ("amount", "text"), [("79", "CHF 79.–"), ("96.8", "CHF 96.80"), ("1299.00", "CHF 1299.–")]
)
def test_swiss_price_format(amount, text):
    assert format_chf(Decimal(amount)) == text


# ---------- HTML ----------


def test_price_and_name_come_from_product_data_not_from_model():
    v = variant(headline="Nur CHF 49 statt 79!")  # Modelltext mit falschem Preis
    html = compose_html(layout_spec(CHANNELS["meta_feed"]), v, PRODUCT)
    assert '<div data-block="preis">CHF 79.–</div>' in html
    assert '<div data-block="produktname">Nothing Headphone (a)</div>' in html


def test_text_is_html_escaped():
    v = variant(headline='<script>alert("x")</script>', cta="<b>Los</b>")
    html = compose_html(layout_spec(CHANNELS["meta_story"]), v, PRODUCT)
    assert "<script>alert" not in html and "&lt;script&gt;" in html
    assert "<b>Los</b>" not in html


def test_placeholder_used_without_remote_image():
    html = compose_html(
        layout_spec(CHANNELS["meta_feed"]), variant(), PRODUCT, use_remote_image=False
    )
    assert "galaxus.ch/productimages" not in html and "Platzhalter" in html


def test_guides_only_on_request():
    spec = layout_spec(CHANNELS["meta_story"])
    assert 'class="guide"' not in compose_html(spec, variant(), PRODUCT)
    assert 'class="guide"' in compose_html(spec, variant(), PRODUCT, show_guides=True)


def test_safe_zone_values_are_in_css_variables():
    html = compose_html(layout_spec(CHANNELS["meta_story"]), variant(), PRODUCT)
    assert "--safe-top: 14.0; --safe-bottom: 35.0" in html


# ---------- Messbericht (ohne Browser, mit erfundenen Messwerten) ----------


def _box(block, x, y, w, h, text="x", overflow=False):
    return {"block": block, "x": x, "y": y, "w": w, "h": h, "text": text, "overflow": overflow}


def test_analyse_detects_block_in_unsafe_zone():
    spec = layout_spec(CHANNELS["meta_story"])  # unten 35 % von 2560 = ab y 1664 unsicher
    measured = {
        "imageLoaded": True,
        "blocks": [
            _box("produktbild", 100, 400, 1200, 600, text=""),
            _box("produktname", 100, 1100, 800, 60),
            _box("preis", 100, 1300, 500, 120),
            _box("cta", 900, 1700, 400, 120),  # ragt in die untere Zone
        ],
    }
    report = analyse(spec, measured)
    assert report.safe_zone_violations == ["cta ausserhalb der sicheren Zone"]


def test_analyse_computes_text_area_and_missing_elements():
    spec = layout_spec(CHANNELS["google_display_banner"])  # 1200 x 628, Pflicht: Bild + Preis
    measured = {
        "imageLoaded": False,
        "blocks": [
            _box("produktbild", 200, 40, 700, 540, text=""),
            _box("preis", 600, 100, 600, 314, text="CHF 79.–"),  # 25 % der Fläche
        ],
    }
    report = analyse(spec, measured)
    assert report.text_area_percent == pytest.approx(25.0)
    assert not report.image_loaded and report.missing_elements == []
    report2 = analyse(
        spec, {"imageLoaded": True, "blocks": [_box("produktbild", 200, 40, 700, 540, text="")]}
    )
    assert report2.missing_elements == ["preis"]


def test_analyse_lists_overflowing_text():
    spec = layout_spec(CHANNELS["meta_feed"])
    measured = {
        "imageLoaded": True,
        "blocks": [_box("headline", 90, 1100, 1260, 300, overflow=True)],
    }
    assert analyse(spec, measured).overflowing == ["headline"]


# ---------- Echtes Rendering (nur wenn ein Chromium verfügbar ist) ----------


def _renderer_or_skip():
    from creative_agent.layouts import LayoutRenderer

    async def probe():
        async with LayoutRenderer():
            return True

    try:
        asyncio.run(probe())
    except Exception as exc:  # kein Browser installiert
        pytest.skip(f"Kein Chromium für Playwright: {type(exc).__name__}")
    return LayoutRenderer


@pytest.mark.browser
def test_render_story_inside_safe_zone(tmp_path):
    renderer_cls = _renderer_or_skip()
    spec = layout_spec(CHANNELS["meta_story"])
    html = compose_html(spec, variant(), PRODUCT, use_remote_image=False)

    async def run():
        async with renderer_cls() as r:
            return await r.render(html, spec, tmp_path / "story.png")

    report = asyncio.run(run())
    assert (tmp_path / "story.png").exists()
    assert report.safe_zone_violations == [] and report.overflowing == []
    assert report.missing_elements == [] and report.image_loaded


@pytest.mark.browser
def test_render_detects_too_long_headline(tmp_path):
    renderer_cls = _renderer_or_skip()
    spec = layout_spec(CHANNELS["meta_feed"])
    long_text = "Dieser Titel ist viel zu lang für das Layout und läuft ganz sicher über " * 3
    html = compose_html(
        spec, variant("meta_feed", headline=long_text), PRODUCT, use_remote_image=False
    )

    async def run():
        async with renderer_cls() as r:
            return await r.render(html, spec, tmp_path / "feed.png")

    assert "headline" in asyncio.run(run()).overflowing


def test_preloaded_image_is_embedded():
    """Vom ImageFetcher geladenes Bild (data-URI) ersetzt die Galaxus-URL."""
    data_uri = "data:image/jpeg;base64,AAAA"
    html = compose_html(layout_spec(CHANNELS["meta_feed"]), variant(), PRODUCT, image_src=data_uri)
    assert data_uri in html and "galaxus.ch/productimages" not in html


def test_render_run_without_image_channel_does_not_crash(tmp_path, monkeypatch):
    """Eval 20261124-0849: Briefing nur mit Suchanzeige brach beim Schreiben des Berichts ab."""
    from creative_agent.layouts import __main__ as cli

    class NoBrowser:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

    monkeypatch.setattr(cli, "RUNS", tmp_path)
    monkeypatch.setattr(cli, "LayoutRenderer", NoBrowser)
    rsa = Variant(
        variant_id="r1",
        channel="google_ads_rsa",
        target_group="x",
        product_id=PRODUCT.id,
        idea="",
        fields={"titel": ["a", "b", "c"]},
    )

    class Rec:
        run_id = "lauf"
        variants = [rsa]
        products = {PRODUCT.id: PRODUCT}

    assert asyncio.run(cli.render_run(Rec(), guides=False, placeholder=True)) == []
    assert (tmp_path / "lauf" / "assets" / "layout_report.json").exists()
