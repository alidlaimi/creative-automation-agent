"""Eval-Bericht als Markdown (eval/reports/, versioniert) plus Kennzahlen als JSON für den
Vergleich mit dem vorherigen Bericht (Regressionsprinzip)."""

import json
from datetime import datetime
from pathlib import Path

from ..config import ROOT
from ..pipeline import RUNS
from .calibration import CalibrationResult
from .datasets import load_briefings
from .metrics import RunMetrics, Summary, run_metrics, summarize
from .negatives import NegativeResult
from .runner import EvalIndex

REPORTS = ROOT / "eval" / "reports"
COMPARE = [
    ("fact_error_variants", "Varianten mit Faktenfehler (generiert)", "weniger"),
    ("fact_errors_not_red", "Faktenfehler, die eine Sichtung erreichen", "weniger"),
    ("format_ok_share", "Formatkonform wie generiert", "mehr"),
    ("judge_mean", "Markenstimme Mittel (Modell)", "mehr"),
    ("copied_example_variants", "Varianten mit kopiertem Beispiel", "weniger"),
    ("cost_per_variant_usd", "Kosten pro Variante (USD)", "weniger"),
    ("duration_median_s", "Laufzeit Median (s)", "weniger"),
    ("approval_rate", "Freigabequote Review", "mehr"),
]


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{x:.0%}"


def _num(x) -> str:
    return "–" if x is None else str(x)


def previous_summary(current_id: str) -> tuple[str, dict] | None:
    files = sorted(p for p in REPORTS.glob("*.json") if p.stem != current_id)
    if not files:
        return None
    data = json.loads(files[-1].read_text("utf-8"))
    return files[-1].stem, data["summary"]


def build_report(
    index: EvalIndex, negatives: list[NegativeResult], calibration: CalibrationResult | None
) -> tuple[str, Summary, list[RunMetrics]]:
    briefings = {b.id: b for b in load_briefings().briefings}
    items = [run_metrics(bid, RUNS / rid) for bid, rid in index.runs.items()]
    s = summarize(items)
    errors = [n for n in negatives if not n.is_control]
    controls = [n for n in negatives if n.is_control]
    lines = [
        f"# Eval-Bericht {index.eval_id}",
        "",
        "> Private Arbeitsprobe auf Basis der öffentlichen Galaxus-MCP-Schnittstelle, "
        "nicht offiziell von Galaxus.",
        "",
        "## Versionen",
        "",
        f"- Datum: {index.started_at:%d.%m.%Y %H:%M} UTC · Commit `{index.git_commit}`"
        + (" (mit lokalen Änderungen)" if index.git_dirty else ""),
        f"- Testset: briefings {index.briefing_set_version} ({len(briefings)} Briefings)",
        "- Skills: " + ", ".join(f"{k} {v}" for k, v in index.skills.items()),
        f"- Prompts: `{index.prompt_hash}` · Modelle: "
        + ", ".join(f"{k} = {v}" for k, v in index.models.items()),
        f"- Schwellwert Markenstimme: {index.judge_threshold}",
        "",
        "## Ergebnis",
        "",
        "| Messgrösse | Wert | Ziel |",
        "|---|---|---|",
        f"| Faktenfehler, die eine menschliche Sichtung erreichen | "
        f"**{s.fact_errors_not_red}** | 0 |",
        f"| Varianten mit Faktenfehler, wie generiert (vom Gate gestoppt) | "
        f"{s.fact_error_variants} von {s.variants} | möglichst 0 |",
        f"| Negativtests vom Gate gestoppt | **{sum(n.passed for n in errors)} / {len(errors)}** | "
        "alle |",
        f"| Saubere Kontrollfälle nicht blockiert | {sum(n.passed for n in controls)} / "
        f"{len(controls)} | alle |",
        f"| Formatkonform wie generiert | {_pct(s.format_ok_share)} | – |",
        "| Formatkonform im Export | 100 % (rote Varianten sind nicht freigebbar) | 100 % |",
        f"| Ampel 🟢 / 🟡 / 🔴 | {s.green} / {s.yellow} / {s.red} | – |",
        f"| Markenstimme (Modell, Mittel 1–5) | {_num(s.judge_mean)}, über Schwelle "
        f"{_pct(s.judge_pass_share)} | – |",
        f"| Kopierte Skill-Beispiele | {s.copied_example_variants} | 0 |",
        f"| Kosten | USD {s.cost_total_usd:.2f} gesamt, USD {_num(s.cost_per_variant_usd)} pro "
        "Variante | – |",
        f"| Laufzeit Briefing → geprüfte Varianten | Median {_num(s.duration_median_s)} s, "
        f"max. {_num(s.duration_max_s)} s | – |",
        f"| Freigabequote Review | {_pct(s.approval_rate)} ({s.reviewed_variants} beurteilt) | – |",
        f"| Zeit Briefing → Freigabe | Median {_num(s.minutes_to_approval_median)} min | – |",
        "",
        f"Läufe: {s.runs_ok} von {s.runs} ohne Abbruch"
        + (f" · Abbruch: {index.stopped_reason}" if index.stopped_reason else "")
        + ".",
        "",
    ]
    prev = previous_summary(index.eval_id)
    if prev:
        prev_id, p = prev
        cur = s.model_dump()
        lines += [
            "## Vergleich zum letzten Bericht",
            "",
            f"Vorher: `{prev_id}`",
            "",
            "| Messgrösse | vorher | jetzt | |",
            "|---|---|---|---|",
        ]
        for key, label, better in COMPARE:
            a, b = p.get(key), cur.get(key)
            mark = ""
            if isinstance(a, int | float) and isinstance(b, int | float) and a != b:
                mark = "✅" if (b > a) == (better == "mehr") else "⚠️"
            lines.append(f"| {label} | {_num(a)} | {_num(b)} | {mark} |")
        lines.append("")
    lines += [
        "## Je Briefing",
        "",
        "| ID | Briefing | Varianten | 🟢/🟡/🔴 | Faktenfehler | Markenstimme | Kosten USD | "
        "Dauer s | Lauf |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for m in items:
        b = briefings.get(m.briefing_id)
        mean = round(sum(m.judge_means) / len(m.judge_means), 2) if m.judge_means else "–"
        status = m.run_status if m.run_status == "ok" else f"**{m.run_status}**"
        lines.append(
            f"| {m.briefing_id} | {b.text if b else ''} | {m.variants} | {m.green}/{m.yellow}/"
            f"{m.red} | {m.fact_error_variants} | {mean} | {m.cost_usd:.3f} | "
            f"{_num(m.duration_seconds)} | {status} `{m.run_id}` |"
        )
    rule_totals: dict[str, int] = {}
    for m in items:
        for r, c in m.rule_counts.items():
            rule_totals[r] = rule_totals.get(r, 0) + c
    if rule_totals:
        lines += ["", "## Häufigste Gate-Meldungen", "", "| Regel | Anzahl |", "|---|---|"]
        lines += [f"| `{r}` | {c} |" for r, c in sorted(rule_totals.items(), key=lambda x: -x[1])]
    lines += [
        "",
        "## Negativtests",
        "",
        "| Fall | Erwartet | Ergebnis | Regeln | |",
        "|---|---|---|---|---|",
    ]
    for n in negatives:
        exp = "/".join(n.expected_status) + (
            f": {', '.join(n.expected_rules)}" if n.expected_rules else ""
        )
        lines.append(
            f"| {n.id} – {n.beschreibung} | {exp} | {n.status} | "
            f"{', '.join(n.rules) or '–'} | {'✅' if n.passed else '❌'} |"
        )
    lines += ["", "## Kalibrierung Markenstimme", ""]
    if calibration is None:
        lines.append("Noch nicht durchgeführt (es fehlen menschliche Urteile).")
    else:
        c = calibration
        lines += [
            f"{c.n} Texte, davon {c.human_pass} von Hand als «passt» beurteilt (blind). "
            f"Modellurteil «passt» = Mittel ≥ Schwelle und kein Kriterium ≤ {c.min_criterion}.",
            "",
            f"**Gewählte Schwelle {c.chosen.threshold}:** "
            f"Übereinstimmung {_pct(c.chosen.agreement)}, "
            f"Cohens Kappa {c.chosen.kappa}, falsche Freigaben {c.chosen.false_pass}, "
            f"falsche Sperren {c.chosen.false_block}. Leave-one-out-Übereinstimmung "
            f"{_pct(c.loo_agreement)}.",
            "",
            "| Schwelle | Übereinstimmung | Kappa | falsche Freigaben | falsche Sperren |",
            "|---|---|---|---|---|",
        ]
        lines += [
            f"| {r.threshold} | {_pct(r.agreement)} | {r.kappa} | {r.false_pass} | "
            f"{r.false_block} |"
            for r in c.rows
        ]
        if c.rule_variants:
            lines += [
                "",
                "Vergleich der Entscheidungsregel (Sperre, wenn ein Kriterium ≤ Wert):",
                "",
                "| Regel | beste Schwelle | Übereinstimmung | Kappa | LOO |",
                "|---|---|---|---|---|",
            ]
            lines += [
                f"| ≤ {v.min_criterion}{' (aus)' if v.min_criterion == 0 else ''} | "
                f"{v.chosen.threshold} | {_pct(v.chosen.agreement)} | {v.chosen.kappa} | "
                f"{_pct(v.loo_agreement)} |"
                for v in c.rule_variants
            ]
        disagree = [i for i in c.items if (i["mensch"] == "passt") != i["modell_passt"]]
        if disagree:
            lines += ["", "Abweichungen (Mensch ≠ Modell bei gewählter Schwelle):", ""]
            lines += [
                f"- `{i['id']}` Mensch {i['mensch']}, Modell {i['modell_mittel']}"
                + (f" – Notiz: {i['notiz']}" if i["notiz"] else "")
                for i in disagree
            ]
    lines += [
        "",
        "## Grenzen",
        "",
        "- Der Faktencheck prüft Zahlen, Preise, Superlative und Verbotsbegriffe – keine "
        "qualitativen Behauptungen (z.B. «läuft auch ohne Akku»). "
        "Diese fängt nur die menschliche Review.",
        "- Testset und Kalibrierung sind klein (15 Briefings, 20 Texte); Kennzahlen sind Hinweise, "
        "keine statistisch belastbaren Werte.",
        "- Die Markenstimme ist eine eigene Ableitung, kalibriert an den Urteilen einer Person.",
        "- Produktdaten ändern sich (Preise, Sortiment): Läufe an verschiedenen Tagen sind nur "
        "eingeschränkt vergleichbar.",
        "",
        f"_Erstellt {datetime.now():%d.%m.%Y %H:%M} mit "
        f"`uv run python -m creative_agent.evaluation bericht {index.eval_id}`._",
    ]
    return "\n".join(lines) + "\n", s, items


def write_report(
    index: EvalIndex, negatives: list[NegativeResult], calibration: CalibrationResult | None
) -> Path:
    text, summary, items = build_report(index, negatives, calibration)
    REPORTS.mkdir(parents=True, exist_ok=True)
    md = REPORTS / f"{index.eval_id}.md"
    md.write_text(text, encoding="utf-8")
    (REPORTS / f"{index.eval_id}.json").write_text(
        json.dumps(
            {
                "eval_id": index.eval_id,
                "index": json.loads(index.model_dump_json()),
                "summary": summary.model_dump(),
                "calibration": calibration.chosen.model_dump() if calibration else None,
                "negatives_passed": f"{sum(n.passed for n in negatives)}/{len(negatives)}",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return md
