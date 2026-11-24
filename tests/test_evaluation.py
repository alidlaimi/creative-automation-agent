import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fakes import ScriptedLLM, tool_use

from creative_agent.evaluation import report as report_mod
from creative_agent.evaluation.calibration import ModelScore, evaluate, kappa, predict
from creative_agent.evaluation.datasets import fixture_products, load_negatives
from creative_agent.evaluation.metrics import run_metrics, summarize
from creative_agent.evaluation.negatives import run_negatives
from creative_agent.evaluation.runner import EvalIndex
from creative_agent.gate import run_gate
from creative_agent.mcp_client import FixtureToolCaller, GalaxusProductSearch
from creative_agent.skills import load_skills
from creative_agent.workflow import run_workflow, save_run

ROOT = Path(__file__).resolve().parents[1]
SKILLS = load_skills(ROOT / "skills")


def score(mean, low=None):
    s = {"ehrlich": 4, "unkonventionell": 4, "zielgruppennah": 4, "klar": 4}
    if low is not None:
        s["klar"] = low
    return ModelScore(
        fingerprint="x",
        scores=s,
        mean=mean,
        reasons={},
        model="m",
        cost_usd=0,
        judged_at=datetime.now(UTC),
    )


# ---------- Kalibrierung ----------


def test_kappa_values():
    assert kappa([(True, True), (False, False)] * 5) == 1.0
    assert kappa([(True, False), (False, True)] * 5) == -1.0
    assert kappa([(True, True), (True, False), (False, True), (False, False)]) == 0.0


def test_predict_respects_minimum_criterion():
    assert predict(score(3.75), 3.5, 2)
    assert not predict(score(3.75, low=2), 3.5, 2)  # ein Kriterium zu schwach
    assert not predict(score(3.25), 3.5, 2)


def test_evaluate_picks_threshold_that_separates_human_labels():
    means = {
        f"t{i:02}": m
        for i, m in enumerate([4.5, 4.25, 4.0, 4.0, 3.75, 3.25, 3.0, 2.75, 2.5, 3.5], 1)
    }
    human = {k: ("passt" if v >= 3.75 else "passt_nicht") for k, v in means.items()}
    human["t10"] = "passt_nicht"  # 3.5 ist für den Menschen knapp nicht genug
    result = evaluate(
        {k: score(v) for k, v in means.items()}, {k: {"urteil": v} for k, v in human.items()}
    )
    assert result.chosen.threshold == 3.75 and result.chosen.kappa == 1.0
    assert result.chosen.false_pass == 0 and result.loo_agreement >= 0.8
    assert result.human_pass == 5 and len(result.rows) == 11


def test_evaluate_needs_enough_labels():
    with pytest.raises(ValueError):
        evaluate({"a": score(4)}, {"a": {"urteil": "passt"}})


# ---------- Messgrössen und Bericht ----------


@pytest.fixture
def eval_run(tmp_path, monkeypatch):
    briefing = {
        "product_query": "Kopfhörer",
        "min_price_chf": None,
        "max_price_chf": 200,
        "channels": ["meta_feed"],
        "target_groups": ["Studierende"],
        "campaign_goal": "Pendler-Kopfhörer",
        "language": "de",
    }
    feed = {
        "varianten": [
            {
                "product_id": "61276930",
                "idee": "a",
                "primaertext": "Lange Zugfahrt? 60 h Akku und ANC halten dich ruhig.",
                "ueberschrift": "Ruhe im Zug",
                "cta": "Ansehen",
            },
            {
                "product_id": "61276930",
                "idee": "b",
                "primaertext": "Für CHF 89.– mit 80 h Akku und ANC für jede Zugfahrt.",
                "ueberschrift": "Ruhe im Zug",
                "cta": "Ansehen",
            },
        ]
    }
    llm = ScriptedLLM(
        structured=[briefing, feed],
        tools=[
            [tool_use("search_products", {"query": "K", "min_price": None, "max_price": 200})],
            [
                tool_use(
                    "select_products",
                    {"choices": [{"product_id": "61276930", "reason": "r"}]},
                    "t2",
                )
            ],
        ],
    )
    search = GalaxusProductSearch(
        FixtureToolCaller(ROOT / "tests/fixtures/mcp"),
        server_url="u",
        agent_info="t",
        min_interval_seconds=0,
    )
    record = asyncio.run(
        run_workflow(
            "b01",
            llm=llm,
            search=search,
            skills=SKILLS,
            model="claude-sonnet-5-5",
            model_fast="claude-haiku-5-5",
            budget_usd=1,
            timeout_seconds=30,
        )
    )
    save_run(record, tmp_path)
    gates = [
        asyncio.run(run_gate(v, record.products[v.product_id], SKILLS)) for v in record.variants
    ]
    (tmp_path / record.run_id / "gate.json").write_text(
        json.dumps([json.loads(g.model_dump_json()) for g in gates]), "utf-8"
    )
    monkeypatch.setattr(report_mod, "RUNS", tmp_path)
    monkeypatch.setattr(report_mod, "REPORTS", tmp_path / "reports")
    index = EvalIndex(
        eval_id="20261124-0900",
        started_at=datetime.now(UTC),
        briefing_set_version="1.0.0",
        git_commit="abc1234",
        git_dirty=False,
        prompt_hash="p",
        skills={"faktencheck": "1.0.0"},
        models={"t": "m"},
        judge_threshold=3.5,
        budget_usd=3,
        runs={"b01": record.run_id},
    )
    return index, tmp_path / record.run_id


def test_metrics_count_fact_errors_and_keep_them_red(eval_run):
    _, run_dir = eval_run
    m = run_metrics("b01", run_dir)
    assert m.variants == 2 and m.fact_error_variants == 1 and m.red == 1
    assert m.fact_errors_not_red == 0
    s = summarize([m])
    assert s.cost_per_variant_usd > 0 and s.approval_rate is None


def test_report_contains_versions_metrics_and_negatives(eval_run):
    index, _ = eval_run
    negatives = asyncio.run(run_negatives(load_negatives().faelle, fixture_products(), SKILLS))
    path = report_mod.write_report(index, negatives, None)
    text = path.read_text("utf-8")
    assert "Commit `abc1234`" in text and "Negativtests vom Gate gestoppt | **16 / 16**" in text
    assert "Faktenfehler, die eine menschliche Sichtung erreichen | **0**" in text
    assert "Noch nicht durchgeführt" in text and "## Grenzen" in text
    summary = json.loads(path.with_suffix(".json").read_text("utf-8"))
    assert summary["summary"]["fact_error_variants"] == 1


def test_report_compares_with_previous(eval_run):
    index, _ = eval_run
    negatives = []
    report_mod.write_report(index.model_copy(update={"eval_id": "20261101-0900"}), negatives, None)
    text = report_mod.write_report(index, negatives, None).read_text("utf-8")
    assert "## Vergleich zum letzten Bericht" in text and "20261101-0900" in text


def test_rule_variants_are_reported():
    from creative_agent.evaluation.calibration import evaluate_with_variants

    means = [4.5, 4.0, 3.75, 3.0, 2.5, 2.0]
    scores = {f"t{i}": score(m) for i, m in enumerate(means)}
    labels = {
        f"t{i}": {"urteil": "passt" if m >= 3.75 else "passt_nicht"} for i, m in enumerate(means)
    }
    r = evaluate_with_variants(scores, labels, 0)
    assert [v.min_criterion for v in r.rule_variants] == [2, 1, 0] and r.min_criterion == 0
