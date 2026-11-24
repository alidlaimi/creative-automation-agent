# 0007 – Review mit Freigaberegeln, Export nur von Freigegebenem

- Status: vorgeschlagen
- Datum: 2026-11-20

## Kontext
Nichts verlässt das System ohne menschliche Freigabe. Die Review muss schnell sein (Kreativ-Team),
nachvollziehbar (Governance) und Fehler des Gates auffangen, statt sie zu verdecken.

## Optionen für die Oberfläche
1. **Streamlit** – in Python, schnell gebaut, für einen internen Prototyp ausreichend; Grenzen bei
   Mehrbenutzerbetrieb und Rechten.
2. **Eigenes Web-Frontend (z.B. React + FastAPI)** – produktionsnäher, aber für ein Proof of Concept
   unverhältnismässig.
3. **Bestehendes Tool (z.B. Review in einem DAM/Asana)** – realistisch für den Betrieb, aber ohne Zugang
   nicht zeigbar.

Gewählt: Streamlit. Die Logik liegt in getesteten Modulen (`review.store`, `review.service`, `export`);
die Oberfläche zeigt nur an und ruft auf – ein späterer Wechsel betrifft nur die Darstellung.

## Entscheid: Regeln
- **Rot ist nicht freigebbar** (Knopf gesperrt, zusätzlich in der Logik und beim Export geprüft).
- **Gelb nur mit Begründung**, **Ablehnung immer mit Grund** – die Gründe sind Rohstoff für bessere Skills.
- **Korrekturen sind Revisionen:** neu gerendert, erneut durchs Gate; ein bestehender Entscheid verfällt.
  `run.json` bleibt unverändert – Modellausgabe und menschliche Änderung bleiben unterscheidbar.
- Entscheide speichern Fassung, Gate-Status, Zeit und eine Rolle («review»), keine Person.

## Entscheid: Export
- **Google Ads (Responsive Search Ads):** CSV mit den Spalten der offiziellen CSV-Spaltenreferenz des
  Google Ads Editors (Campaign, Ad group, Headline 1–15, Description 1–4, Path 1–2, Final URL, Status,
  Labels). `Status = Paused`: Auch nach dem Import geht nichts ohne aktives Einschalten live.
  `Labels` enthält die Varianten-ID (Rückverfolgung). Eine Spalte «Ad type» ist dort nicht dokumentiert –
  der Import muss einmal im Ads Editor verifiziert werden.
- **Meta:** generische CSV (Texte, Produkt, Preis aus den Daten, Bilddatei, URL, Gate, Freigabe).
- **Asset-Paket:** PNG je Bildvariante + `manifest.json` (Skills mit Hash, Modelle, Gate, Freigabe-
  begründung, SHA-256 je Bild) als ZIP.
- **Tracking-Parameter entfernt:** Die MCP-Links tragen `utm_source=shop-mcp`; in Anzeigen würde das
  Werbe-Traffic falsch als KI-Assistenten-Traffic ausweisen.
- Gegenprüfung beim Export: freigegeben, aber Gate rot oder Freigabe einer älteren Fassung → Abbruch.

## Konsequenzen
- Kennzahlen in der Oberfläche: Freigabequote, Kosten pro Variante (inkl. Markenstimme-Bewertung),
  Laufzeit des Agenten, Zeit Briefing → letzte Freigabe.
- Für echten Betrieb fehlen Anmeldung, Rollen und Mehrbenutzer-Sperren – bewusst ausserhalb des Umfangs.

## Nachtrag (2026-11-24): Test der Oberfläche
Der Ablauf «Freigabe → Export enthält nur Freigegebenes, Rot gesperrt» wird mit Streamlits
`AppTest` geprüft statt mit Playwright im Browser: gleiche Abdeckung der Logik, kein Browser und
kein laufender Server nötig, stabil in der CI. Playwright bleibt für das Rendering der Layouts.
