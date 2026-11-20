"""Rendert alle Bild-Varianten eines Laufs.

uv run python -m creative_agent.layouts            # neuester Lauf
uv run python -m creative_agent.layouts <run_id> --guides --placeholder
"""

import argparse
import asyncio
import json
import sys

from ..config import ROOT
from ..skills import load_skills
from ..workflow.models import RunRecord
from .compose import compose_html, layout_spec
from .images import ImageFetcher
from .render import LayoutRenderer

RUNS = ROOT / "output" / "runs"


async def render_run(record: RunRecord, guides: bool, placeholder: bool) -> list[dict]:
    channels = load_skills(ROOT / "skills")["kanalformate"].rules.channels
    out_dir = RUNS / record.run_id / "assets"
    reports = []
    fetcher = ImageFetcher(ROOT / "data" / "cache" / "images")
    async with LayoutRenderer() as renderer:
        for v in record.variants:
            channel = channels[v.channel]
            if not channel.layout:
                continue  # z.B. Suchanzeige: reiner Text
            spec = layout_spec(channel)
            product = record.products[v.product_id]
            image_src = None
            if not placeholder and product.image:
                image_src = fetcher.data_uri(product.image.url)
                if image_src is None:
                    print(f"Bild {product.id} nicht geladen: {fetcher.errors[product.image.url]}")
            html = compose_html(
                spec,
                v,
                product,
                use_remote_image=not placeholder,
                show_guides=guides,
                image_src=image_src,
            )
            suffix = "-hilfslinien" if guides else ""
            report = await renderer.render(html, spec, out_dir / f"{v.variant_id}{suffix}.png")
            reports.append({"variant_id": v.variant_id, **report.model_dump()})
    (out_dir / f"layout_report{'-hilfslinien' if guides else ''}.json").write_text(
        json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return reports


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id", nargs="?")
    parser.add_argument("--guides", action="store_true", help="sichere Zonen rot einzeichnen")
    parser.add_argument("--placeholder", action="store_true", help="Platzhalter statt Produktbild")
    args = parser.parse_args()
    run_id = args.run_id or max(p.name for p in RUNS.iterdir() if (p / "run.json").exists())
    record = RunRecord.model_validate_json((RUNS / run_id / "run.json").read_text("utf-8"))
    for r in asyncio.run(render_run(record, args.guides, args.placeholder)):
        flags = r["safe_zone_violations"] + [f"Überlauf: {b}" for b in r["overflowing"]]
        flags += [f"fehlt: {m}" for m in r["missing_elements"]]
        if not r["image_loaded"]:
            flags.append("Bild nicht geladen")
        print(
            f"{r['variant_id']}: {r['png_path']} | Text {r['text_area_percent']} % | "
            f"{'OK' if not flags else '; '.join(flags)}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
