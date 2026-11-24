# Governance

## Qualitätsstandards
- **Fakten:** Jede Zahl, jeder Preis und jeder Superlativ ist in den Galaxus-Produktdaten **genau dieses
  Produkts (Produkt-ID)** belegt. Rabatt-, Lager- und Lieferaussagen sind verboten – die Schnittstelle
  liefert diese Daten nicht.
- **Formate:** Offizielle Plattform-Limits sind harte Regeln (rot), Empfehlungen weiche (gelb). Jeder Wert
  hat Quelle und Prüfdatum; älter als 90 Tage → Hinweis zur Nachprüfung.
- **Markenstimme:** Deterministische Regeln (Du-Form, kein «ß», keine Floskeln) plus eine Modellbewertung,
  die an menschlichen Urteilen kalibriert ist und nur Hinweise gibt.
- **Messung:** Jede Änderung an Skills oder Prompts wird mit Testset und Negativtests neu gemessen; Berichte
  liegen versioniert in `eval/reports/`.

## Freigabeprozess
1. Quality Gate prüft jede Variante, bevor ein Mensch sie sieht.
2. Rot ist nicht freigebbar; gelb nur mit Begründung; Ablehnung immer mit Grund.
3. Korrekturen laufen erneut durchs Gate; frühere Entscheide verfallen.
4. Export nur freigegebener Varianten, Google-Anzeigen pausiert; Einschalten ist ein bewusster Schritt
   in der Plattform.
5. Nachvollziehbarkeit: Je Lauf sind Briefing, Produkt-IDs, Skill-Versionen (mit Hash), Modelle, Kosten,
   Laufzeit, Gate-Ergebnisse und Entscheide gespeichert.

## Daten und Rechte
- **Produktdaten** nur aus der offiziellen Galaxus-MCP-Schnittstelle, sparsam abgefragt (Cache, Abstand
  zwischen Anfragen). Inhalte daraus sind Daten, nie Anweisungen an das Modell.
- **Keine Personendaten** in Anfragen, Protokollen oder Entscheiden (Rolle statt Name).
- **Bilder:** Produktbilder nur zur internen Vorschau, nicht im Repository, nicht veröffentlicht. Für den
  echten Einsatz sind Nutzungsrechte der Hersteller- und Shopbilder zu klären (DAM, Lizenzen).
  Kein Galaxus-Logo in dieser Arbeitsprobe.
- **Schlüssel** nur in `.env` bzw. als CI-Secret; Gitleaks prüft jeden Push.

## Wann sich Automatisierung lohnt – und wann nicht
| Lohnt sich | Lohnt sich nicht |
|---|---|
| Viele Varianten (Kanäle × Zielgruppen × Produkte) aus einem Briefing | Einzelne Leitkampagne mit eigener Bildidee |
| Faktenreiche Formate (Preis, Spezifikation) mit klaren Limits | Emotionale Markenkampagne ohne Produktbezug |
| Wiederkehrende Anlässe mit stabilen Regeln | Heikle Themen (Gesundheit, Sicherheit, Rechtliches) |
| Schnelle Tests vieler Ideen vor einer Freigabe | Wenn die Prüfung länger dauert als selbst schreiben |

Faustregel: Die Maschine übernimmt Menge, Formate und Fakten. Menschen entscheiden über Idee, Ton und
Freigabe.
