"""Ein ganzer Durchlauf: Briefing → Recherche → Texte → Layouts → Quality Gate.

Wird von der Review-Oberfläche («Neuer Lauf») und der Kommandozeile genutzt.
"""

import json
from collections.abc import Callable

from .config import ROOT, Settings
from .gate.__main__ import gate_run
from .layouts.__main__ import render_run
from .mcp_client import FileCache, FixtureToolCaller, GalaxusProductSearch, LiveToolCaller
from .skills import load_skills
from .workflow.budget import PRICES
from .workflow.llm import AnthropicLLM
from .workflow.run import run_workflow, save_run

RUNS = ROOT / "output" / "runs"


def check_models(settings: Settings) -> None:
    for m in (
        settings.anthropic_model,
        settings.anthropic_model_fast,
        settings.anthropic_model_judge,
    ):
        if m not in PRICES:
            raise RuntimeError(f"Kein geprüfter Preis für {m!r} – Budget nicht prüfbar")


def make_search(settings: Settings, offline: bool = False) -> GalaxusProductSearch:
    model_tag = f"model: {settings.anthropic_model}"
    caller = (
        FixtureToolCaller(ROOT / "tests" / "fixtures" / "mcp")
        if offline
        else LiveToolCaller(settings.galaxus_mcp_url)
    )
    return GalaxusProductSearch(
        caller,
        server_url=settings.galaxus_mcp_url,
        agent_info=f"creative-automation-agent/0.1 (private portfolio project, Claude API); "
        f"{model_tag}",
        cache=FileCache(ROOT / "data" / "cache" / "mcp", settings.mcp_cache_ttl_seconds),
    )


async def run_pipeline(
    briefing: str,
    *,
    variants_per_cell: int = 2,
    offline_mcp: bool = False,
    progress: Callable[[str], None] = print,
) -> str:
    settings = Settings()
    check_models(settings)
    progress("Briefing lesen, Produkte recherchieren, Texte schreiben …")
    record = await run_workflow(
        briefing,
        llm=AnthropicLLM(settings.require_api_key()),
        search=make_search(settings, offline_mcp),
        skills=load_skills(ROOT / "skills"),
        model=settings.anthropic_model,
        model_fast=settings.anthropic_model_fast,
        budget_usd=settings.run_budget_usd,
        timeout_seconds=settings.run_timeout_seconds,
        variants_per_cell=variants_per_cell,
    )
    save_run(record, RUNS)
    if record.status != "ok":
        progress(f"Lauf beendet mit Status {record.status}: {record.error}")
        return record.run_id
    progress("Layouts rendern …")
    await render_run(record, guides=False, placeholder=False)
    await render_run(record, guides=True, placeholder=False)
    progress("Quality Gate prüfen …")
    results = await gate_run(record, use_judge=True)
    (RUNS / record.run_id / "gate.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    progress("Fertig.")
    return record.run_id
