"""Workflow-Lauf von der Kommandozeile.

  uv run python -m creative_agent.workflow \
    "Pendler-Kopfhörer bis CHF 200, Story und Feed, Zielgruppe Studierende"
... --offline-mcp   Produktdaten aus Fixtures (Modell läuft trotzdem live)
"""

import argparse
import asyncio
import sys

from ..config import ROOT, Settings
from ..mcp_client import FileCache, FixtureToolCaller, GalaxusProductSearch, LiveToolCaller
from ..skills import load_skills
from .budget import PRICES
from .llm import AnthropicLLM
from .run import run_workflow, save_run


def main() -> int:
    parser = argparse.ArgumentParser(description="Creative-Automation-Workflow")
    parser.add_argument("briefing")
    parser.add_argument("--variants", type=int, default=2, help="Varianten je Kanal und Zielgruppe")
    parser.add_argument("--offline-mcp", action="store_true")
    args = parser.parse_args()

    settings = Settings()
    for m in (settings.anthropic_model, settings.anthropic_model_fast):
        if m not in PRICES:
            print(f"Kein geprüfter Preis für {m!r} – Budget nicht prüfbar. Erlaubt: {list(PRICES)}")
            return 2
    llm = AnthropicLLM(settings.require_api_key())
    model_tag = f"model: {settings.anthropic_model}"
    agent_info = (
        f"creative-automation-agent/0.1 (private portfolio project, Claude API); {model_tag}"
    )
    caller = (
        FixtureToolCaller(ROOT / "tests" / "fixtures" / "mcp")
        if args.offline_mcp
        else LiveToolCaller(settings.galaxus_mcp_url)
    )
    search = GalaxusProductSearch(
        caller,
        server_url=settings.galaxus_mcp_url,
        agent_info=agent_info,
        cache=FileCache(ROOT / "data" / "cache" / "mcp", settings.mcp_cache_ttl_seconds),
    )
    record = asyncio.run(
        run_workflow(
            args.briefing,
            llm=llm,
            search=search,
            skills=load_skills(ROOT / "skills"),
            model=settings.anthropic_model,
            model_fast=settings.anthropic_model_fast,
            budget_usd=settings.run_budget_usd,
            timeout_seconds=settings.run_timeout_seconds,
            variants_per_cell=args.variants,
        )
    )
    path = save_run(record, ROOT / "output" / "runs")

    print(f"Lauf {record.run_id}: {record.status}" + (f" – {record.error}" if record.error else ""))
    if record.briefing:
        b = record.briefing
        print(
            f"Briefing: '{b.product_query}', CHF {b.min_price_chf}–{b.max_price_chf}, "
            f"Kanäle {b.channels}, Zielgruppen {b.target_groups}"
        )
    for s in record.searches:
        print(f"Suche: '{s.query}' -> {s.total_count} Treffer")
    for c in record.selection:
        p = record.products[c.product_id]
        print(f"Auswahl [{p.id}] {p.brand} {p.name}: {c.reason}")
    for v in record.variants:
        print(f"\n[{v.variant_id}] Produkt {v.product_id} – {v.idea}")
        for k, val in v.fields.items():
            print(f"  {k}: {val}")
    print(
        f"\nKosten USD {record.cost_total_usd:.4f} / Budget {record.budget_usd:.2f}, "
        f"{record.duration_seconds} s, Protokoll: {path.relative_to(ROOT)}"
    )
    return 0 if record.status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
