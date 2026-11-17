# 0003 – Skill-Format: SKILL.md + rules.yaml + CHANGELOG.md

- Status: vorgeschlagen
- Datum: 2026-11-17

## Kontext
Markenstimme, Kanalformate und Faktencheck sollen versioniert, austauschbar und **von einem
Kreativ-Team ohne Code** anpassbar sein. Gleichzeitig braucht das Quality Gate exakte, prüfbare Werte.

## Optionen
1. **Nur Markdown** – sehr lesbar, aber Limits und Listen müsste der Code aus Fliesstext lesen (fehleranfällig).
2. **Nur YAML** – maschinenlesbar, aber Haltung, Beispiele und Begründungen passen schlecht in YAML.
3. **Ordner pro Skill mit `SKILL.md` + `rules.yaml` + `CHANGELOG.md`**
   - `SKILL.md`: Kopf (name, description, version) und Anleitung in Prosa – lehnt sich an das Format
     der Agent Skills von Anthropic an und dient direkt als Modell-Anweisung.
   - `rules.yaml`: alles, was der Code prüft, mit Schema-Validierung.
   - `CHANGELOG.md`: nachvollziehbar, wer was warum geändert hat.
4. **Datenbank mit Admin-Oberfläche** – komfortabel, aber für ein Proof of Concept zu viel; Versionierung
   müsste nachgebaut werden, die Git bereits liefert.

## Entscheid
Option 3.

- Strikte Validierung beim Laden (`extra="forbid"`): Tippfehler in Schlüsseln fallen sofort auf.
- **Quellenpflicht:** Jeder Kanalwert hat `wert`, `status`, `quelle`, `geprueft`. Ohne Quelle oder
  Datum lädt der Skill nicht. Prüfdatum älter als 90 Tage → Hinweis, kein Fehler.
- **Status steuert das Gate:** `offizielles Limit` → rot, `Empfehlung` → gelb, `interne Vorgabe` → je nach Regel.
- Version im Semver-Format; ohne passenden Changelog-Eintrag lädt der Skill nicht.
- Jeder Skill hat einen Inhalts-Hash; Version + Hash werden pro Lauf protokolliert (Nachvollziehbarkeit).
- YAML-Schlüssel deutsch (Kreativ-Team), Python-Attribute englisch (Code-Konvention).

## Konsequenzen
- Kreativ-Team arbeitet in zwei Textdateien und prüft mit `uv run python -m creative_agent.skills`.
- Änderungen laufen über Git (Pull Request = Freigabe einer neuen Skill-Version).
- Für Teams ohne Git wäre eine einfache Oberfläche der nächste Schritt; das Dateiformat bleibt gleich.
