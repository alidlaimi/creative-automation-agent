# Quellen: Galaxus-MCP-Schnittstelle

Geprüft am **2026-11-17**. Nur offizielle Quellen, kein Scraping.

| Angabe | Wert | Quelle |
|---|---|---|
| Server-Adresse | `https://mcp.galaxus.ch` | Claude-Verzeichnis (Konnektor-URL), Galaxus-README |
| Transport | Streamable HTTP | Galaxus-README (`claude mcp add … --transport http`) |
| Anmeldung | nicht erforderlich | Claude-Verzeichnis, Galaxus-README |
| Betreiber | Digitec Galaxus AG | Claude-Verzeichnis («Entwickelt von Galaxus»), Nutzungsbedingungen |
| Region | Schweiz und Liechtenstein | Claude-Verzeichnis, Galaxus-README |
| Tools | nur `search_products` | Claude-Verzeichnis, Galaxus-README |
| Support | mcp.support@digitecgalaxus.ch | Claude-Verzeichnis |

## `search_products` laut Doku
Parameter: `query` (Pflicht), `agentInfo` (Pflicht, Name/Anbieter/Modell des Agenten),
`first` (1–50, Standard 10), `minPrice`, `maxPrice`, `userIntent` (ohne Personendaten).

Felder je Produkt: `id`, `name`, `properties`, `description`, `productType`, `brand`,
`priceIfAvailable`, `pageUrl` (mit UTM-Parametern), `ratingSummaryIfAvailable`,
`productReviewsSummaryIfAvailable`.

## Tatsächliches Schema (Server selbst, `initialize` + `tools/list`, 2026-11-17)
Massgebend ist die Antwort des Servers, nicht die README. Abfrage aus dem Browser auf `mcp.galaxus.ch`.

- Protokollversion: `2025-06-18` (klassischer `initialize`-Handshake), Antworten als `text/event-stream`
- Server-Instruktionen: Sprachen en, de, fr, it, nl; Sprache als `language` an jedes Tool übergeben
- `search_products` – Pflichtfelder: `query`, `agentInfo`, **`language`** (fehlt in der README)
- `first`: Ganzzahl 1–50, Standard 10; `minPrice`/`maxPrice`: **Ganzzahlen** 1–1 000 000 (Shop-Währung)
- Antwort: `{correctedSearchTerm, totalCount, products[]}`, bei leerem Ergebnis `errorMessage`;
  ungültige Eingaben (z.B. min > max) und Transportfehler als MCP-Fehlerergebnis
- Produktfelder zusätzlich zur README: **`previewImage`**
- `priceIfAvailable` inkl. MWST, `null` wenn kein Preis geliefert wird
- **Nicht geliefert:** Lagerbestand, Lieferzeiten, vollständige Bewertungen
- Annotationen: `readOnlyHint: true`, `destructiveHint: false`

## Abweichungen zur Medienmitteilung
Die Mitteilung nennt **Verfügbarkeit**. Die Schnittstelle liefert laut Tool-Beschreibung weder Lagerbestand
noch Lieferzeiten. → Faktencheck: Verfügbarkeits- und Lieferaussagen («sofort lieferbar») sind nicht
belegbar und werden gestoppt.

## Was die Nutzungsbedingungen nicht regeln
Automatisierte Nutzung, Ratenlimits, Caching, Nutzung von Bildern/Inhalten, kommerzielle Nutzung.
Unser Umgang: wenige Anfragen, Cache, keine Bilder im Repository, keine Veröffentlichung.
Personendaten nie in `agentInfo` oder `userIntent`.

## Links
- Claude-Verzeichnis: https://claude.ai/directory/galaxus-search-mcp
- Technische Doku: https://mcp.galaxus.ch/static/README.md
- Nutzungsbedingungen (gültig ab 2026-09-01): https://mcp.galaxus.ch/static/TERMS_OF_USE.md
- Medienmitteilung (11.11.2026): https://www.galaxus.ch/de/page/galaxus-startet-mcp-schnittstelle-fuer-ki-assistenten-44216
