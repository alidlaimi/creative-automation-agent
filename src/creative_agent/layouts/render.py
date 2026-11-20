"""Rendert HTML mit Playwright zu PNG und misst das Ergebnis.

Der Messbericht ist die Grundlage für die Bildregeln im Quality Gate:
sichere Zone, Textanteil, Textüberlauf, Pflichtelemente, Bild geladen.
"""

import os
from pathlib import Path

from pydantic import BaseModel

from .compose import LayoutSpec

TEXT_BLOCKS = {"produktname", "headline", "preis", "cta"}
ELEMENT_TO_BLOCK = {
    "produktname": "produktname",
    "preis": "preis",
    "cta": "cta",
    "produktbild": "produktbild",
}

MEASURE_JS = """
() => {
  const lineHeight = (el) => {
    const cs = getComputedStyle(el);
    const lh = parseFloat(cs.lineHeight);
    return Number.isNaN(lh) ? 1.2 * parseFloat(cs.fontSize) : lh;
  };
  const canvas = document.querySelector('.canvas').getBoundingClientRect();
  const blocks = [...document.querySelectorAll('[data-block]')]
    .filter(el => el.dataset.block !== 'hintergrund')
    .map(el => {
      const r = el.getBoundingClientRect();
      return {
        block: el.dataset.block,
        x: r.left - canvas.left, y: r.top - canvas.top, w: r.width, h: r.height,
        text: el.innerText.trim(),
        // Überlauf = mindestens eine halbe Zeile verborgen (Unterlängen der Schrift zählen nicht)
        overflow: (el.scrollHeight - el.clientHeight) > 0.5 * lineHeight(el)
          || el.scrollWidth > el.clientWidth + 2,
      };
    });
  const img = document.querySelector('[data-block="produktbild"] img');
  return {blocks, imageLoaded: !!img && img.complete && img.naturalWidth > 0};
}
"""


class BlockBox(BaseModel):
    block: str
    x: float
    y: float
    w: float
    h: float
    text: str
    overflow: bool


class LayoutReport(BaseModel):
    width: int
    height: int
    png_path: str | None = None
    image_loaded: bool
    blocks: list[BlockBox]
    text_area_percent: float
    max_text_area_percent: float | None
    safe_zone_violations: list[str]
    overflowing: list[str]
    missing_elements: list[str]


def analyse(spec: LayoutSpec, measured: dict, png_path: str | None = None) -> LayoutReport:
    blocks = [BlockBox(**b) for b in measured["blocks"]]
    w, h = spec.width, spec.height
    left, right = w * spec.safe.left / 100, w - w * spec.safe.right / 100
    top, bottom = h * spec.safe.top / 100, h - h * spec.safe.bottom / 100
    tol = 1.0

    violations = [
        f"{b.block} ausserhalb der sicheren Zone"
        for b in blocks
        if b.block in TEXT_BLOCKS | {"produktbild"}
        and (
            b.x < left - tol
            or b.y < top - tol
            or b.x + b.w > right + tol
            or b.y + b.h > bottom + tol
        )
    ]
    text_area = sum(b.w * b.h for b in blocks if b.block in TEXT_BLOCKS and b.text)
    present = {b.block for b in blocks if b.block == "produktbild" or b.text}
    missing = [e for e in spec.required_elements if ELEMENT_TO_BLOCK.get(e, e) not in present]
    return LayoutReport(
        width=w,
        height=h,
        png_path=png_path,
        image_loaded=bool(measured["imageLoaded"]),
        blocks=blocks,
        text_area_percent=round(100 * text_area / (w * h), 2),
        max_text_area_percent=spec.max_text_area_percent,
        safe_zone_violations=violations,
        overflowing=[b.block for b in blocks if b.overflow and b.block in TEXT_BLOCKS],
        missing_elements=missing,
    )


class LayoutRenderer:
    """Ein Browser für viele Renderings. Nutzung: `async with LayoutRenderer() as r: ...`"""

    def __init__(self, executable_path: str | None = None) -> None:
        # Optional eigener Chrome (z.B. CI-Image); sonst Playwrights Chromium.
        self.executable_path = executable_path or os.environ.get("CHROMIUM_EXECUTABLE") or None

    async def __aenter__(self) -> "LayoutRenderer":
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(executable_path=self.executable_path)
        return self

    async def __aexit__(self, *exc) -> None:
        await self._browser.close()
        await self._pw.stop()

    async def render(self, html: str, spec: LayoutSpec, out_path: Path) -> LayoutReport:
        page = await self._browser.new_page(
            viewport={"width": spec.width, "height": spec.height}, device_scale_factor=1
        )
        try:
            await page.set_content(html, wait_until="networkidle", timeout=20_000)
            measured = await page.evaluate(MEASURE_JS)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            await page.locator(".canvas").screenshot(path=str(out_path))
        finally:
            await page.close()
        return analyse(spec, measured, str(out_path))
