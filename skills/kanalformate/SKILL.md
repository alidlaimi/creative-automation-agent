---
name: kanalformate
description: Formate, Masse, Zeichenlimits und sichere Zonen je Werbekanal. Grundlage für Layouts und Quality Gate.
version: 1.0.0
owner: Kreationsteam (Platzhalter)
---

# Kanalformate

Dieser Skill beschreibt **pro Kanal**, wie gross ein Werbemittel ist, wie viele Zeichen ein Text haben darf
und welche Bildbereiche frei bleiben müssen. Die Werte stehen in `rules.yaml`.

## Regeln für jeden Wert
Jeder Wert hat vier Angaben – ohne sie lässt sich der Skill nicht laden:

| Angabe | Bedeutung |
|---|---|
| `wert` | die Zahl oder der Text |
| `status` | `offizielles Limit` (Plattform lehnt ab) · `Empfehlung` (Plattform kürzt oder rät ab) · `interne Vorgabe` (unsere Regel) |
| `quelle` | Link auf die offizielle Seite der Plattform oder auf unsere Doku |
| `geprueft` | Datum der letzten Prüfung (JJJJ-MM-TT) |

**Wie das Quality Gate den Status nutzt:** Verstoss gegen ein `offizielles Limit` → **rot** (Stopp).
Verstoss gegen eine `Empfehlung` → **gelb** (Mensch entscheidet). Ist ein Prüfdatum älter als 90 Tage,
erscheint ein Hinweis – der Wert gilt weiter, soll aber neu geprüft werden.

## Neuen Kanal hinzufügen (ohne Code)
1. In `rules.yaml` unter `kanaele:` einen Block kopieren und umbenennen (z.B. `linkedin_feed`).
2. Werte von der offiziellen Seite übernehmen, Quelle und Prüfdatum eintragen.
3. Gibt es ein Bild, unter `layout:` ein bestehendes Template wählen (`feed`, `story`, `banner`).
4. Version im Kopf dieser Datei erhöhen und in `CHANGELOG.md` notieren.
5. Prüfen: `uv run python -m creative_agent.skills`

## Bekannte Abweichungen zu verbreiteten Angaben (Stand 2026-11-17)
- Meta Feed: Der offizielle Guide empfiehlt 4:5 mit 1440×1800 px (nicht 1:1 / 1080×1080).
- Meta Stories: unten 35 % frei lassen (viele Ratgeber nennen noch 20 %).
- Google Display (responsiv): Text im Bild höchstens 20 % der Fläche – sonst Ablehnung.
