# 0002 – Datei-Cache für Antworten der Galaxus-Schnittstelle

- Status: vorgeschlagen
- Datum: 2026-11-17

## Kontext
Die Nutzungsbedingungen der Galaxus-MCP-Schnittstelle regeln weder Ratenlimits noch Caching.
Wir wollen den Anbieter schonen, Läufe reproduzierbar machen und Kosten/Laufzeit senken.
Die Datenmenge ist klein (wenige hundert Suchen, je ca. 10–40 KB).

## Optionen
1. **JSON-Datei pro Anfrage** (Schlüssel = SHA-256 der ergebnisrelevanten Argumente)
   - \+ keine Abhängigkeit, Einträge lesbar und einzeln löschbar, einfach zu erklären
   - − keine Abfragen über alle Einträge, viele kleine Dateien
2. **SQLite**
   - \+ eine Datei, Transaktionen, Abfragen möglich (z.B. «alle Suchen von gestern»)
   - − mehr Code, Inhalte für Nicht-Entwickler schwerer einsehbar
3. **Kein Cache**
   - − jede Demo und jeder Eval-Lauf belastet die Schnittstelle, Ergebnisse schwanken

## Entscheid
Option 1. Bei der erwarteten Menge bringt SQLite keinen Nutzen, der den Mehraufwand rechtfertigt.

Details:
- Gespeichert wird der **Rohtext**, nicht das normalisierte Ergebnis: Änderungen an der
  Normalisierung gelten sofort auch für gecachte Antworten.
- Schlüssel nur aus ergebnisrelevanten Argumenten (`query`, `language`, `first`, Preisfilter).
  `agentInfo` und `userIntent` beeinflussen laut Tool-Beschreibung die Ergebnisse nicht.
- Gültigkeit standardmässig 24 h (`MCP_CACHE_TTL_SECONDS`): Preise ändern sich, ein Werbemittel
  mit Preis aus einem veralteten Cache wäre ein Faktenfehler.
- Schreiben atomar (temporäre Datei, dann umbenennen); defekte Einträge zählen als Fehltreffer.
- Zusätzlich mindestens 1 s Abstand zwischen Live-Aufrufen.

## Konsequenzen
- Cache liegt in `data/cache/` und ist nicht im Repository.
- Wächst das System (mehrere Nutzer, Server-Betrieb), auf SQLite oder Redis wechseln;
  die Schnittstelle `get/set` bleibt gleich.
