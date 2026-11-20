"""Orchestrierung: Briefing → Recherche → Varianten, mit Budget, Zeitlimit und Protokoll."""

import asyncio
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..mcp_client import GalaxusProductSearch
from ..skills import Skill
from ..skills.models import ChannelFormatsRules
from .budget import BudgetExceeded, CostTracker
from .llm import LLM
from .models import CostLine, RunRecord, SkillRef
from .steps import (
    StepContext,
    WorkflowError,
    parse_briefing,
    research_products,
    selection_products,
    write_variants,
)


def new_run_id(now: datetime) -> str:
    return f"{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"


async def run_workflow(
    briefing_text: str,
    *,
    llm: LLM,
    search: GalaxusProductSearch,
    skills: dict[str, Skill],
    model: str,
    model_fast: str,
    budget_usd: float,
    timeout_seconds: float,
    variants_per_cell: int = 2,
) -> RunRecord:
    started = datetime.now(UTC)
    t0 = time.monotonic()
    tracker = CostTracker(budget_usd)
    record = RunRecord(
        run_id=new_run_id(started),
        started_at=started,
        briefing_text=briefing_text,
        models={"texte_recherche": model, "briefing": model_fast},
        skills=[
            SkillRef(name=s.name, version=s.version, content_hash=s.content_hash)
            for s in skills.values()
        ],
        budget_usd=budget_usd,
    )
    ctx = StepContext(llm=llm, tracker=tracker, model=model, model_fast=model_fast)
    channels: ChannelFormatsRules = skills["kanalformate"].rules

    async def steps() -> None:
        record.briefing = await parse_briefing(ctx, briefing_text, channels)
        research = await research_products(ctx, record.briefing, search)
        record.searches, record.products = research.searches, research.products
        record.selection = research.selection
        record.research_completed_by = research.completed_by
        chosen = selection_products(research.selection, research.products)
        for channel_id in record.briefing.channels:
            for g, group in enumerate(record.briefing.target_groups, 1):
                record.variants += await write_variants(
                    ctx,
                    spec=record.briefing,
                    channel_id=channel_id,
                    channel=channels.channels[channel_id],
                    target_group=group,
                    products=chosen,
                    brand_voice=skills["markenstimme"],
                    fact_check=skills["faktencheck"],
                    count=variants_per_cell,
                    id_prefix=f"{channel_id}-z{g}",
                )

    try:
        async with asyncio.timeout(timeout_seconds):
            await steps()
    except BudgetExceeded as exc:
        record.status, record.error = "budget_exceeded", str(exc)
    except TimeoutError:
        record.status, record.error = "timeout", f"Zeitlimit {timeout_seconds:.0f} s erreicht"
    except WorkflowError as exc:
        record.status, record.error = "error", str(exc)
    except (
        Exception
    ) as exc:  # z.B. API-Fehler (Schlüssel, Guthaben, Modell): protokollieren statt abstürzen
        record.status, record.error = "error", f"{type(exc).__name__}: {exc}"[:800]
    finally:
        record.finished_at = datetime.now(UTC)
        record.duration_seconds = round(time.monotonic() - t0, 2)
        record.costs = [CostLine(**c.__dict__) for c in tracker.calls]
        record.cost_total_usd = round(tracker.spent_usd, 6)
    return record


def save_run(record: RunRecord, runs_dir: Path) -> Path:
    path = runs_dir / record.run_id / "run.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return path
