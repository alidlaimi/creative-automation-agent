"""Review-Oberfläche. Start:  uv run streamlit run src/creative_agent/review/app.py"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import streamlit as st

from creative_agent.config import ROOT, Settings
from creative_agent.export import ExportError, export_run
from creative_agent.gate import BrandVoiceJudge, GateResult
from creative_agent.layouts import format_chf
from creative_agent.review import (
    ReviewError,
    current_gate,
    current_variant,
    decide,
    load_review,
    save_review,
)
from creative_agent.review.service import layout_renderer_for, parse_edit, revise_variant
from creative_agent.skills import load_skills
from creative_agent.workflow.budget import CostTracker
from creative_agent.workflow.models import RunRecord

RUNS = Path(os.environ.get("CAA_RUNS_DIR", ROOT / "output" / "runs"))
ICON = {"gruen": "🟢", "gelb": "🟡", "rot": "🔴", None: "⚪"}
SEVERITY = {"rot": "🔴", "gelb": "🟡", "info": "ℹ️"}
DEFAULT_BRIEFING = "Pendler-Kopfhörer bis CHF 200, Story und Feed, Zielgruppe Studierende"

st.set_page_config(page_title="Creative Automation – Review", layout="wide")


def flash(msg: str, kind: str = "success") -> None:
    st.session_state["flash"] = (msg, kind)


def show_flash() -> None:
    if "flash" in st.session_state:
        msg, kind = st.session_state.pop("flash")
        getattr(st, kind)(msg)


def list_runs() -> list[str]:
    if not RUNS.exists():
        return []
    return sorted((p.name for p in RUNS.iterdir() if (p / "run.json").exists()), reverse=True)


def load_gates(run_dir: Path) -> dict[str, GateResult]:
    path = run_dir / "gate.json"
    if not path.exists():
        return {}
    return {d["variant_id"]: GateResult.model_validate(d) for d in json.loads(path.read_text())}


# ---------- Seitenleiste: Lauf wählen oder neu starten ----------

st.sidebar.title("Creative Automation")
st.sidebar.caption(
    "Private Arbeitsprobe auf Basis der öffentlichen Galaxus-MCP-Schnittstelle – "
    "nicht offiziell von Galaxus."
)
with st.sidebar.expander("Neuer Lauf", expanded=not list_runs()):
    briefing = st.text_area("Briefing", DEFAULT_BRIEFING, height=90)
    variants_per_cell = st.number_input("Varianten je Kanal und Zielgruppe", 1, 4, 2)
    if st.button("Lauf starten", type="primary", width="stretch"):
        from creative_agent.pipeline import run_pipeline

        with st.status("Lauf läuft …", expanded=True) as status:
            try:
                run_id = asyncio.run(
                    run_pipeline(briefing, variants_per_cell=variants_per_cell, progress=st.write)
                )
                st.session_state["run_id"] = run_id
                status.update(label="Lauf abgeschlossen", state="complete")
                flash(f"Lauf {run_id} erstellt")
            except Exception as exc:  # Fehler sichtbar machen statt App-Absturz
                status.update(label="Lauf fehlgeschlagen", state="error")
                st.error(f"{type(exc).__name__}: {exc}")
                st.stop()
        st.rerun()

runs = list_runs()
if not runs:
    st.info("Noch kein Lauf vorhanden. Links ein Briefing eingeben und starten.")
    st.stop()
default = runs.index(st.session_state["run_id"]) if st.session_state.get("run_id") in runs else 0
run_id = st.sidebar.selectbox("Lauf", runs, index=default)
run_dir = RUNS / run_id
record = RunRecord.model_validate_json((run_dir / "run.json").read_text("utf-8"))
gates = load_gates(run_dir)
state = load_review(run_dir)
skills = load_skills(ROOT / "skills")
show_guides = st.sidebar.toggle("Sichere Zonen einblenden", value=False)

if record.briefing:
    b = record.briefing
    st.sidebar.markdown(f"**Briefing:** {record.briefing_text}")
    st.sidebar.caption(
        f"Suche «{b.product_query}», CHF {b.min_price_chf or '–'}–"
        f"{b.max_price_chf or '–'} · Kanäle {', '.join(b.channels)}"
    )
st.sidebar.caption("Skills: " + ", ".join(f"{s.name} {s.version}" for s in record.skills))
st.sidebar.caption(f"Modelle: {', '.join(sorted(set(record.models.values())))}")

# ---------- Kopf: Kennzahlen ----------

st.title("Review")
show_flash()
if record.status != "ok":
    st.error(f"Lauf-Status {record.status}: {record.error}")
if not gates:
    st.warning(
        "Für diesen Lauf gibt es noch kein Gate-Ergebnis: "
        "`uv run python -m creative_agent.gate " + run_id + "`"
    )

statuses = [(current_gate(gates, state, v.variant_id) or None) for v in record.variants]
decisions = [state.variants.get(v.variant_id) for v in record.variants]
approved = [d for d in decisions if d and d.decision and d.decision.decision == "freigegeben"]
decided = [d for d in decisions if d and d.decision]
judge_cost = sum(g.judge.cost_usd for g in statuses if g and g.judge)
n = max(len(record.variants), 1)
last_approval = max((d.decision.decided_at for d in approved), default=None)

c = st.columns(6)
c[0].metric("Varianten", len(record.variants))
c[1].metric(
    "🟢 / 🟡 / 🔴",
    " / ".join(
        str(sum(1 for g in statuses if g and g.status == s)) for s in ("gruen", "gelb", "rot")
    ),
)
c[2].metric("Freigabequote", f"{len(approved) / len(decided):.0%}" if decided else "–")
c[3].metric("Kosten pro Variante", f"USD {(record.cost_total_usd + judge_cost) / n:.3f}")
c[4].metric("Laufzeit Agent", f"{record.duration_seconds or 0:.0f} s")
c[5].metric(
    "Briefing → letzte Freigabe",
    f"{(last_approval - record.started_at).total_seconds() / 60:.0f} min" if last_approval else "–",
)

channels = sorted({v.channel for v in record.variants})
selected = st.multiselect("Kanäle", channels, default=channels)

# ---------- Varianten ----------

for original in record.variants:
    if original.channel not in selected:
        continue
    vid = original.variant_id
    variant = current_variant(record, state, vid)
    gate = current_gate(gates, state, vid)
    entry = state.variants.get(vid)
    product = record.products.get(variant.product_id)
    revisions = len(entry.revisions) if entry else 0

    with st.container(border=True):
        head = (
            f"{ICON[gate.status if gate else None]} **{vid}** · {variant.channel} · "
            f"Zielgruppe {variant.target_group}"
        )
        if revisions:
            head += f" · korrigiert (Fassung {revisions})"
        if entry and entry.decision:
            mark = "✅ freigegeben" if entry.decision.decision == "freigegeben" else "⛔ abgelehnt"
            head += f" · {mark}"
        st.markdown(head)
        col_img, col_text, col_act = st.columns([1, 1.4, 1])

        with col_img:
            suffix = f"-r{revisions}" if revisions else ""
            png = run_dir / "assets" / f"{vid}{suffix}{'-hilfslinien' if show_guides else ''}.png"
            if png.exists():
                st.image(str(png), width="stretch")
            elif skills["kanalformate"].rules.channels[variant.channel].layout:
                st.caption("Noch nicht gerendert")
            else:
                st.caption("Textanzeige – kein Bild")

        with col_text:
            if product:
                price = format_chf(product.price.amount) if product.price else "kein Preis"
                st.caption(f"Produkt {product.id}: {product.brand or ''} {product.name} · {price}")
                st.caption(f"Idee: {variant.idea}")
            for key, value in variant.fields.items():
                if isinstance(value, list):
                    st.markdown(f"**{key}**")
                    for item in value:
                        st.markdown(f"- {item}  `{len(item)}`")
                else:
                    st.markdown(f"**{key}**: {value}  `{len(value)}`")
            if gate:
                st.markdown("**Quality Gate**")
                if not gate.findings:
                    st.caption("Keine Beanstandung.")
                for f in gate.findings:
                    where = f" · {f.field}" if f.field else ""
                    st.markdown(f"{SEVERITY[f.severity]} `{f.rule}`{where}: {f.message}")
                    if f.source:
                        st.caption(f"Quelle: {f.source}")
                if gate.judge:
                    with st.expander(
                        f"Markenstimme {gate.judge.mean} "
                        f"(Schwelle {gate.judge.threshold}, {gate.judge.model})"
                    ):
                        for k, score in gate.judge.scores.items():
                            st.markdown(f"**{k}: {score}** – {gate.judge.reasons[k]}")
                        st.caption(gate.judge.overall)

        with col_act:
            with st.form(f"edit-{vid}"):
                st.markdown("**Korrigieren**")
                raw = {}
                for key, value in variant.fields.items():
                    if isinstance(value, list):
                        raw[key] = st.text_area(
                            f"{key} (eine Zeile pro Eintrag)", "\n".join(value), key=f"{vid}-{key}"
                        )
                    else:
                        raw[key] = st.text_input(key, value, key=f"{vid}-{key}")
                if st.form_submit_button("Korrigieren & neu prüfen"):
                    settings = Settings()
                    judge, tracker = None, CostTracker(settings.run_budget_usd)
                    if settings.anthropic_api_key is not None:
                        from creative_agent.workflow.llm import AnthropicLLM

                        judge = BrandVoiceJudge(
                            AnthropicLLM(settings.require_api_key()),
                            settings.anthropic_model_judge,
                            threshold=settings.judge_threshold,
                            min_criterion=settings.judge_min_criterion,
                        )
                    with st.spinner("Rendern und prüfen …"):
                        rev = asyncio.run(
                            revise_variant(
                                record,
                                state,
                                vid,
                                parse_edit(variant, raw),
                                skills,
                                render=layout_renderer_for(record, run_dir, skills),
                                judge=judge,
                                tracker=tracker,
                            )
                        )
                    save_review(state, run_dir)
                    flash(
                        f"{vid}: neue Fassung geprüft – {ICON[rev.gate.status]} {rev.gate.status}"
                    )
                    st.rerun()

            reason = st.text_input(
                "Begründung", key=f"{vid}-reason", placeholder="Pflicht bei gelb und bei Ablehnung"
            )
            b1, b2 = st.columns(2)
            if b1.button(
                "Freigeben",
                key=f"{vid}-ok",
                type="primary",
                disabled=gate is None or gate.status == "rot",
                width="stretch",
            ):
                try:
                    decide(state, vid, "freigegeben", reason, gate)
                    save_review(state, run_dir)
                    flash(f"{vid} freigegeben")
                    st.rerun()
                except ReviewError as exc:
                    st.error(str(exc))
            if b2.button("Ablehnen", key=f"{vid}-no", width="stretch"):
                try:
                    decide(state, vid, "abgelehnt", reason, gate)
                    save_review(state, run_dir)
                    flash(f"{vid} abgelehnt", "info")
                    st.rerun()
                except ReviewError as exc:
                    st.error(str(exc))
            if gate and gate.status == "rot":
                st.caption("Rot: nicht freigebbar – korrigieren oder ablehnen.")
            if entry and entry.decision:
                d = entry.decision
                st.caption(
                    f"Entscheid {d.decided_at:%d.%m.%Y %H:%M} (UTC), Fassung {d.revision}, "
                    f"Gate {d.gate_status}: {d.reason or '–'}"
                )

# ---------- Export ----------

st.divider()
st.subheader("Export")
st.caption(
    "Nur freigegebene Varianten. Google-Anzeigen starten pausiert. Produkt-Links ohne "
    "MCP-Tracking-Parameter."
)
if st.button("Export erstellen", disabled=not approved):
    try:
        result = export_run(record, state, gates, run_dir)
        st.session_state["export"] = result.model_dump()
        flash(f"Export mit {len(result.variant_ids)} Variante(n) erstellt")
        st.rerun()
    except ExportError as exc:
        st.error(str(exc))
exp = st.session_state.get("export")
if exp and Path(exp["directory"]).parent.parent == run_dir:
    st.write("Enthalten: " + ", ".join(exp["variant_ids"]))
    with open(exp["zip_path"], "rb") as fh:
        st.download_button("ZIP herunterladen", fh, file_name=Path(exp["zip_path"]).name)
    for f in exp["files"]:
        if f.endswith(".csv"):
            with open(f, "rb") as fh:
                st.download_button(
                    f"{Path(f).name} herunterladen", fh, file_name=Path(f).name, key=f
                )
st.caption(
    f"Stand {datetime.now():%d.%m.%Y %H:%M} · Protokoll: {run_dir.relative_to(ROOT)}"
    if run_dir.is_relative_to(ROOT)
    else ""
)
