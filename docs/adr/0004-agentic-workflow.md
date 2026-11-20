# 0004 – Workflow: agentische Recherche, strukturiertes Texten

- Status: vorgeschlagen
- Datum: 2026-11-20

## Kontext
Aus einem kurzen Briefing sollen Varianten je Kanal und Zielgruppe entstehen – mit echten Produktdaten,
begrenzten Kosten und nachvollziehbar. Das Modell soll formulieren, aber keine Fakten liefern.

## Optionen
1. **Vollständig agentisch:** Ein Modell mit allen Tools entscheidet Ablauf, Suche und Texte selbst.
   Flexibel, aber Kosten, Dauer und Ergebnisform schwer zu begrenzen und zu testen.
2. **Fester Ablauf:** Code sucht, Modell schreibt nur. Berechenbar, aber das Modell kann Suchbegriffe
   nicht nachschärfen («Kopfhörer» liefert z.B. kabelgebundene Modelle für Pendler).
3. **Mischform:** Recherche agentisch (Tool `search_products`, max. 3 Suchen, Abschluss über Tool
   `select_products` mit Begründung), danach fester Ablauf pro Kanal × Zielgruppe mit strukturierter Ausgabe.

## Entscheid
Option 3.

- **Fakten kommen vom Code:** Das Modell wählt nur IDs, die in einem Suchergebnis vorkamen; erfundene IDs
  werden mit Fehlermeldung zurückgegeben. Alle gesehenen Produkte landen im Lauf-Protokoll als Datenbasis
  für den Faktencheck.
- **Keine erzwungene Tool-Wahl:** Neuere Modelle (u.a. Sonnet 5.5) lehnen `tool_choice` `any`/`tool`
  mit HTTP 400 ab (https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use,
  geprüft 2026-11-20). Die Recherche läuft daher mit `auto` + `strict: true`. Wählt das Modell nach den
  erlaubten Runden nicht selbst aus, schliesst ein strukturierter Aufruf die Auswahl garantiert ab.
  Im Protokoll steht, welcher Weg genommen wurde (`research_completed_by`). Erkannt im ersten Live-Lauf;
  das Test-LLM lehnt erzwungene Tool-Wahl seither ebenfalls ab.
- **Strukturierte Ausgabe** (`output_config.format`, JSON-Schema). Das Schema pro Kanal entsteht
  dynamisch aus dem Skill `kanalformate` – ein neuer Kanal braucht keinen neuen Code.
- Bewusst `messages.create` statt `messages.parse`: `parse` wirft bei ungültiger Antwort eine Ausnahme,
  die Token-Zahlen gingen verloren und das Budget würde Kosten übersehen.
- **Wiederholung** bei ungültiger Antwort (max. 3 Versuche) mit konkretem Fehlerhinweis an das Modell.
- **Budget und Zeitlimit pro Lauf** (`RUN_BUDGET_USD`, `RUN_TIMEOUT_SECONDS`). Vor jedem Aufruf wird
  geprüft; `max_tokens` begrenzt das Überschiessen. Preise nur für Modelle mit geprüftem Preis.
- **Zeichenlimits werden nicht im Schema erzwungen**, sondern stehen im Prompt. Strukturierte Ausgaben
  unterstützen `maxLength` nicht; geprüft wird deterministisch im Quality Gate (Meilenstein 6).
- **Modelle:** Sonnet 5.5 für Recherche und Texte, Haiku 5.5 für das Briefing (einfache Extraktion).
- Produktdaten gehen als markierte Daten (`<produktdaten>`) ans Modell, mit dem Hinweis, darin enthaltene
  Anweisungen nicht zu befolgen.

## Konsequenzen
- Pro Lauf: 1 Briefing-Aufruf, 2–4 Recherche-Aufrufe, 1 Aufruf je Kanal × Zielgruppe (+ Wiederholungen).
- Das gescriptete Test-LLM deckt alle Pfade ab (Wiederholung, erfundene ID, Budget, Zeitlimit) ohne Netz.
- Nächste Optimierung: Prompt-Caching für den gleichbleibenden System-Prompt beim Texten.
