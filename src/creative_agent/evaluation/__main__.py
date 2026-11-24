"""Evaluation von der Kommandozeile.

uv run python -m creative_agent.evaluation negativ                 # gratis, ohne Netz
uv run python -m creative_agent.evaluation kalibrieren             # Modellurteile + Auswertung
uv run python -m creative_agent.evaluation lauf --budget 3         # 15 Briefings live
uv run python -m creative_agent.evaluation lauf --resume <eval_id> # abgebrochenen Lauf fortsetzen
uv run python -m creative_agent.evaluation bericht <eval_id>       # Bericht (nach der Review neu)
"""

import argparse
import asyncio
import json
import sys

from ..config import ROOT, Settings
from ..skills import load_skills
from .calibration import (
    CAL_DIR,
    evaluate_with_variants,
    judge_texts,
    load_labels,
    load_model_scores,
)
from .datasets import fixture_products, load_calibration, load_negatives
from .negatives import run_negatives
from .runner import load_index, run_eval


def _negatives():
    return asyncio.run(
        run_negatives(load_negatives().faelle, fixture_products(), load_skills(ROOT / "skills"))
    )


def _calibration():
    labels, scores = load_labels(), load_model_scores()
    try:
        return evaluate_with_variants(scores, labels, Settings().judge_min_criterion)
    except ValueError:
        return None


def cmd_negativ(_args) -> int:
    results = _negatives()
    for r in results:
        print(f"{'✅' if r.passed else '❌'} {r.id:32} {r.status:5} {', '.join(r.rules)}")
    errors = [r for r in results if not r.is_control]
    print(
        f"\nFehlerfälle gestoppt: {sum(r.passed for r in errors)}/{len(errors)} · "
        f"Kontrollfälle frei: {sum(r.passed for r in results if r.is_control)}/"
        f"{sum(r.is_control for r in results)}"
    )
    return 0 if all(r.passed for r in results) else 1


def cmd_kalibrieren(args) -> int:
    texts = load_calibration().texte
    labels = load_labels()
    missing = [t.id for t in texts if t.id not in labels]
    if missing:
        print(
            f"Es fehlen noch {len(missing)} Urteile ({', '.join(missing)}).\n"
            "Erfassen mit: uv run streamlit run src/creative_agent/evaluation/label_app.py"
        )
        return 1
    settings = Settings()
    from ..gate import BrandVoiceJudge
    from ..workflow.llm import AnthropicLLM

    judge = BrandVoiceJudge(
        AnthropicLLM(settings.require_api_key()),
        settings.anthropic_model_judge,
        min_criterion=settings.judge_min_criterion,
    )
    asyncio.run(
        judge_texts(
            texts, fixture_products(), load_skills(ROOT / "skills"), judge, budget_usd=args.budget
        )
    )
    result = evaluate_with_variants(load_model_scores(), labels, settings.judge_min_criterion)
    (CAL_DIR / "ergebnis.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(
        f"\n{'Schwelle':>8} {'Überein.':>9} {'Kappa':>6} {'falsch frei':>12} "
        f"{'falsch gesperrt':>16}"
    )
    for r in result.rows:
        mark = "  ◀ gewählt" if r.threshold == result.chosen.threshold else ""
        print(
            f"{r.threshold:>8} {r.agreement:>9.0%} {r.kappa:>6} {r.false_pass:>12} "
            f"{r.false_block:>16}{mark}"
        )
    print(
        f"\nLeave-one-out-Übereinstimmung: {result.loo_agreement:.0%} · "
        f"Mensch «passt»: {result.human_pass}/{result.n}"
    )
    print("\nRegelvarianten (Sperre, wenn ein Kriterium ≤ Wert):")
    for v in result.rule_variants:
        c = v.chosen
        print(
            f"  ≤{v.min_criterion}: Schwelle {c.threshold}, Kappa {c.kappa}, "
            f"Überein. {c.agreement:.0%}, LOO {v.loo_agreement:.0%}"
        )
    print(
        f"Empfehlung für JUDGE_MIN_CRITERION={settings.judge_min_criterion}: "
        f"JUDGE_THRESHOLD={result.chosen.threshold}"
    )
    return 0


def cmd_lauf(args) -> int:
    index = asyncio.run(
        run_eval(args.budget, resume=args.resume, only=args.only, variants_per_cell=args.variants)
    )
    print(
        f"\nEval {index.eval_id}: {len(index.runs)} Läufe. Bericht: "
        f"uv run python -m creative_agent.evaluation bericht {index.eval_id}"
    )
    return 0


def cmd_bericht(args) -> int:
    from .report import write_report

    path = write_report(load_index(args.eval_id), _negatives(), _calibration())
    print(f"Bericht: {path.relative_to(ROOT)}")
    summary = json.loads(path.with_suffix(".json").read_text("utf-8"))["summary"]
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="creative_agent.evaluation")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("negativ").set_defaults(func=cmd_negativ)
    p = sub.add_parser("kalibrieren")
    p.add_argument("--budget", type=float, default=0.5)
    p.set_defaults(func=cmd_kalibrieren)
    p = sub.add_parser("lauf")
    p.add_argument("--budget", type=float, default=3.0, help="Gesamtbudget USD")
    p.add_argument("--resume")
    p.add_argument("--only", nargs="*", help="nur diese Briefing-IDs, z.B. b01 b02")
    p.add_argument("--variants", type=int, default=2)
    p.set_defaults(func=cmd_lauf)
    p = sub.add_parser("bericht")
    p.add_argument("eval_id")
    p.set_defaults(func=cmd_bericht)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
