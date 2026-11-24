"""Beschriften für die Kalibrierung – blind, ohne Modellbewertung.

Start:  uv run streamlit run src/creative_agent/evaluation/label_app.py
"""

import hashlib

import streamlit as st

from creative_agent.config import ROOT
from creative_agent.evaluation.calibration import load_labels, save_label
from creative_agent.evaluation.datasets import fixture_products, load_calibration
from creative_agent.layouts import format_chf
from creative_agent.skills import load_skill

st.set_page_config(page_title="Kalibrierung Markenstimme", layout="centered")

texts = load_calibration().texte
# Feste, gemischte Reihenfolge: nicht nach Qualität sortiert, aber für alle gleich
texts = sorted(texts, key=lambda t: hashlib.sha256(t.id.encode()).hexdigest())
products = fixture_products()
labels = load_labels()
skill = load_skill(ROOT / "skills" / "markenstimme")

with st.sidebar:
    st.subheader("Markenstimme (Kurzfassung)")
    haltung = skill.instructions.split("## Haltung in drei Sätzen")[1].split("## ")[0]
    st.markdown(haltung)
    st.caption(
        f"Skill markenstimme {skill.version}. Urteile nach deinem Gefühl als Kreativ-Lead: "
        "Würdest du diesen Text so freigeben?"
    )

done = sum(t.id in labels for t in texts)
st.title("Kalibrierung: Passt der Text zur Markenstimme?")
st.progress(done / len(texts), text=f"{done} von {len(texts)} beurteilt")

if "pos" not in st.session_state:
    st.session_state.pos = next((i for i, t in enumerate(texts) if t.id not in labels), 0)
pos = st.session_state.pos
text = texts[pos]
product = products[text.produkt]

with st.container(border=True):
    price = format_chf(product.price.amount) if product.price else ""
    st.caption(f"{product.brand} {product.name} · {price} · Zielgruppe {text.zielgruppe}")
    st.markdown(f"### {text.felder['ueberschrift']}")
    st.markdown(text.felder["primaertext"])
    st.button(text.felder["cta"], disabled=True, key="cta-preview")
    st.caption(f"Text {pos + 1} von {len(texts)} · ID {text.id}")

previous = labels.get(text.id)
if previous:
    st.info(f"Bisheriges Urteil: **{previous['urteil']}** {previous.get('notiz') or ''}")
note = st.text_input("Notiz (optional): Was stört oder gefällt?", key=f"note-{text.id}")


def go(step: int) -> None:
    st.session_state.pos = min(max(st.session_state.pos + step, 0), len(texts) - 1)


c1, c2 = st.columns(2)
if c1.button("✅ Passt", type="primary", width="stretch"):
    save_label(text.id, "passt", note)
    go(1)
    st.rerun()
if c2.button("❌ Passt nicht", width="stretch"):
    save_label(text.id, "passt_nicht", note)
    go(1)
    st.rerun()
b1, b2 = st.columns(2)
b1.button("← Zurück", on_click=go, args=(-1,), width="stretch")
b2.button("Überspringen →", on_click=go, args=(1,), width="stretch")
if done == len(texts):
    st.success("Fertig. Nächster Schritt: uv run python -m creative_agent.evaluation kalibrieren")
