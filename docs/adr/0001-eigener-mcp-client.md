# 0001 – Eigener MCP-Client statt MCP-Connector der Claude API

- Status: vorgeschlagen
- Datum: 2026-11-17

## Kontext
Produktdaten kommen ausschliesslich aus der Galaxus-MCP-Schnittstelle. Es gibt zwei Wege, sie anzubinden:
Die Claude API kann einen entfernten MCP-Server direkt als Tool-Quelle einbinden (MCP-Connector), oder
unsere Anwendung spricht selbst mit dem Server (eigener Client mit dem offiziellen MCP-SDK für Python)
und reicht dem Modell nur aufbereitete Daten weiter.

Anforderungen: Faktencheck gegen exakt die Daten, die das Modell gesehen hat; Tests und CI ohne
Live-Aufrufe; sparsame Anfragen; Schutz vor Prompt-Injection aus Produkttexten; Nachvollziehbarkeit je Lauf.

## Optionen
1. **MCP-Connector der Claude API**
   - \+ wenig Code, das Modell ruft die Tools selbst auf
   - − Rohdaten gehen ungefiltert ans Modell, keine Normalisierung dazwischen
   - − kein eigener Cache, schwer reproduzierbar; Fixtures für CI kaum möglich
   - − Faktencheck müsste die Tool-Ergebnisse nachträglich aus der Antwort rekonstruieren
2. **Eigener MCP-Client**
   - \+ Normalisierung in ein eigenes Produktschema (pydantic), robust gegen fehlende Felder
   - \+ Cache und Ratenbegrenzung in unserer Hand
   - \+ Antworten aufzeichnen → Fixtures → CI ohne Live-Aufrufe
   - \+ Produktdatensatz ist die einzige Wahrheit für den Faktencheck und wird pro Lauf protokolliert
   - \+ Produkttexte werden klar als Daten markiert ans Modell übergeben
   - − mehr Code und eine zusätzliche Abhängigkeit (MCP-SDK)

## Entscheid
Option 2: eigener MCP-Client. Das Quality Gate braucht einen festen, protokollierten Produktdatensatz als
Referenz; das ist mit dem Connector nur auf Umwegen zu haben.

## Konsequenzen
- Der Agent bekommt ein eigenes Tool `search_products`, das intern den MCP-Client nutzt.
- Bei Schemaänderungen des Servers muss nur die Normalisierung angepasst werden.
- Der Connector bleibt eine Option für schnelle Prototypen; ein Wechsel würde den Faktencheck betreffen.
