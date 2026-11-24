# Changelog faktencheck

## 1.0.1 – 2026-11-24
- «nur noch» ersetzt durch konkrete Knappheitsformen (nur noch wenige/heute/kurz/bis, letzte Exemplare):
  «Du musst nur noch das Regal aussuchen» wurde fälschlich als Lageraussage gestoppt.
- Code: Produktname und Marke zählen nicht als Verbotsbegriff («Barista Express»); Zahlwörter in den
  Produktdaten belegen Ziffern («drei Brenner» → «3 Brenner»).
- Anlass: Eval-Bericht 20261124-0849, alle 3 roten Varianten waren Fehlalarme.

## 1.0.0 – 2026-11-17
- Erste Version: Preise exakt, Zahlen mit Einheit, Superlative und Bewertungen nur mit Beleg.
- Verboten: Rabatt-/Aktionsaussagen, Verfügbarkeit, Lieferzeit/Versand – die Galaxus-Schnittstelle
  liefert diese Daten nicht (siehe docs/quellen/galaxus-mcp.md).
