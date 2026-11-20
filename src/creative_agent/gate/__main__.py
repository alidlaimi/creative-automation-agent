"""Quality Gate für einen Lauf.

uv run python -m creative_agent.gate                 # neuester Lauf, mit Markenstimme-Bewertung
uv run python -m creative_agent.gate <run_id> --no-judge
"""

import argparse
import asyncio
import json
import sys

from ..config import ROOT, Settings
from ..layouts import LayoutReport
from ..skills import load_skills
from ..workflow.budget import PRICES, CostTracker
from ..workflow.models import RunRecord
from .gate import run_gate
from .judge import BrandVoiceJudge

RUNS = ROOT / "output" / "runs"
ICON = {"gruen": "🟢", "gelb": "🟡", "rot": "🔴"}


def load_layout_reports(run_dir) -> dict[str, LayoutReport]:
    path = run_dir / "assets" / "layout_report.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text("utf-8"))
    return {d.pop("variant_id"): LayoutReport.model_validate(d) for d in data}


async def gate_run(record: RunRecord, use_judge: bool) -> list[dict]:
    settings = Settings()
    skills = load_skills(ROOT / "skills")
    judge = None
    tracker = CostTracker(settings.run_budget_usd)
    if use_judge:
        from ..workflow.llm import AnthropicLLM

        if settings.anthropic_model_judge not in PRICES:
            raise SystemExit(f"Kein geprüfter Preis für {settings.anthropic_model_judge!r}")
        judge = BrandVoiceJudge(
            AnthropicLLM(settings.require_api_key()),
            settings.anthropic_model_judge,
            threshold=settings.judge_threshold,
        )
    reports = load_layout_reports(RUNS / record.run_id)
    results = []
    for v in record.variants:
        result = await run_gate(
            v,
            record.products.get(v.product_id),
            skills,
            layout_report=reports.get(v.variant_id),
            judge=judge,
            tracker=tracker,
        )
        results.append(json.loads(result.model_dump_json()))
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id", nargs="?")
    parser.add_argument("--no-judge", action="store_true", help="ohne Modellbewertung (gratis)")
    args = parser.parse_args()
    run_id = args.run_id or max(p.name for p in RUNS.iterdir() if (p / "run.json").exists())
    record = RunRecord.model_validate_json((RUNS / run_id / "run.json").read_text("utf-8"))
    results = asyncio.run(gate_run(record, not args.no_judge))
    (RUNS / run_id / "gate.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for r in results:
        print(f"{ICON[r['status']]} {r['variant_id']}")
        for f in r["findings"]:
            print(
                f"     [{f['severity']}] {f['rule']}{' · ' + f['field'] if f['field'] else ''}: "
                f"{f['message']}"
            )
        if r["judge"]:
            j = r["judge"]
            print(f"     Markenstimme {j['mean']} (Schwelle {j['threshold']}): {j['scores']}")
    counts = {s: sum(r["status"] == s for r in results) for s in ICON}
    print(
        f"\n{counts['gruen']} grün · {counts['gelb']} gelb · {counts['rot']} rot "
        f"– Bericht: {(RUNS / run_id / 'gate.json').relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
