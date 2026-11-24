"""Eval-Lauf: alle Briefings des Testsets durch die ganze Pipeline, mit Gesamtbudget.

Der Index (welcher Lauf gehört zu welchem Briefing) liegt in output/evals/<eval_id>.json.
Abgebrochene Läufe lassen sich mit --resume fortsetzen.
"""

import hashlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from ..config import ROOT, Settings
from ..pipeline import RUNS, run_pipeline
from ..skills import load_skills
from .datasets import load_briefings
from .metrics import run_metrics

EVALS = ROOT / "output" / "evals"
PROMPT_FILES = ["src/creative_agent/workflow/prompts.py", "src/creative_agent/gate/judge.py"]


class EvalIndex(BaseModel):
    eval_id: str
    started_at: datetime
    briefing_set_version: str
    git_commit: str
    git_dirty: bool
    prompt_hash: str
    skills: dict[str, str]
    models: dict[str, str]
    judge_threshold: float
    budget_usd: float
    runs: dict[str, str] = {}  # briefing_id -> run_id
    stopped_reason: str | None = None


def git_info() -> tuple[str, bool]:
    env = {"GIT_OPTIONAL_LOCKS": "0", "PATH": "/usr/bin:/bin:/usr/local/bin"}
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain", "--", "src", "skills", "eval"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return commit, dirty
    except (OSError, subprocess.CalledProcessError):
        return "unbekannt", True


def prompt_hash() -> str:
    digest = hashlib.sha256()
    for f in PROMPT_FILES:
        digest.update((ROOT / f).read_bytes())
    return digest.hexdigest()[:12]


def save_index(index: EvalIndex) -> Path:
    EVALS.mkdir(parents=True, exist_ok=True)
    path = EVALS / f"{index.eval_id}.json"
    path.write_text(index.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_index(eval_id: str) -> EvalIndex:
    return EvalIndex.model_validate_json((EVALS / f"{eval_id}.json").read_text("utf-8"))


async def run_eval(
    budget_usd: float,
    resume: str | None = None,
    only: list[str] | None = None,
    variants_per_cell: int = 2,
    progress=print,
) -> EvalIndex:
    settings = Settings()
    briefing_set = load_briefings()
    if resume:
        index = load_index(resume)
    else:
        commit, dirty = git_info()
        now = datetime.now(UTC)
        index = EvalIndex(
            eval_id=f"{now:%Y%m%d-%H%M}",
            started_at=now,
            briefing_set_version=briefing_set.version,
            git_commit=commit,
            git_dirty=dirty,
            prompt_hash=prompt_hash(),
            skills={
                s.name: f"{s.version} ({s.content_hash})"
                for s in load_skills(ROOT / "skills").values()
            },
            models={
                "texte_recherche": settings.anthropic_model,
                "briefing": settings.anthropic_model_fast,
                "markenstimme": settings.anthropic_model_judge,
            },
            judge_threshold=settings.judge_threshold,
            budget_usd=budget_usd,
        )
    save_index(index)
    for b in briefing_set.briefings:
        if only and b.id not in only:
            continue
        if b.id in index.runs:
            continue
        spent = sum(run_metrics(bid, RUNS / rid).cost_usd for bid, rid in index.runs.items())
        if spent >= budget_usd:
            index.stopped_reason = f"Gesamtbudget USD {budget_usd:.2f} erreicht (USD {spent:.2f})"
            progress(index.stopped_reason)
            break
        progress(f"[{b.id}] {b.text}  (bisher USD {spent:.2f})")
        try:
            run_id = await run_pipeline(
                b.text,
                variants_per_cell=variants_per_cell,
                progress=lambda msg: progress(f"    {msg}"),
            )
        except Exception as exc:  # ein fehlerhaftes Briefing stoppt nicht das ganze Testset
            progress(f"    Fehler: {type(exc).__name__}: {exc}")
            continue
        index.runs[b.id] = run_id
        save_index(index)
    save_index(index)
    return index
