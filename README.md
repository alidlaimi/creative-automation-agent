# Creative Automation Agent

> **Private Arbeitsprobe** von Ali Dlaimi auf Basis der öffentlichen Galaxus-MCP-Schnittstelle.
> Nicht offiziell von Digitec Galaxus, nicht mit Galaxus abgestimmt. Kein Galaxus-Logo, keine
> veröffentlichten Werbemittel; Produktbilder und gerenderte Werbemittel sind nicht im Repository.

## Zweck
Aus einem kurzen Kampagnen-Briefing entstehen Werbemittel-Varianten für verschiedene Kanäle und
Zielgruppen – mit echten Produktdaten, modularen Layouts (Feed, Story, Banner) und einem Quality Gate,
das jede Variante prüft, bevor ein Mensch sie sieht. Freigabe und Export bleiben beim Menschen.

## Architektur
_Diagramm folgt (Meilenstein 9)._

## Ablauf
Briefing → Produktsuche (MCP) → Auswahl mit Begründung → Textvarianten → Layouts → Quality Gate → Review → Export

## Skills
| Skill | Inhalt | Status |
|---|---|---|
| markenstimme | Tonalität, Beispiele, No-Gos, Rubrik | offen |
| kanalformate | Masse, Zeichenlimits, sichere Zonen – je Wert mit Quelle | offen |
| faktencheck | Belegpflicht für Preise, Zahlen, Superlative | offen |

## Eval-Ergebnisse
_Folgt (Meilenstein 8)._

## Architecture Decision Records
Siehe [docs/adr](docs/adr/README.md).

## Setup
```bash
uv sync
cp .env.example .env   # lokal ausfüllen, nie committen
uv run pytest
```

## Grenzen
_Folgt._

## Nächste Schritte
Bildgenerierung, Anbindung an ein DAM, Rückfluss von Performance-Daten aus den Ad-Plattformen.
