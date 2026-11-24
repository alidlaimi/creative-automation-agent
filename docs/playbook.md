# Playbook für das Kreationsteam

Für alle, die mit dem Creative-Automation-Agent arbeiten – ohne Programmierkenntnisse.

## 1. Der Ablauf in einem Satz
Du schreibst ein kurzes Briefing, der Agent sucht passende Produkte bei Galaxus, schreibt Varianten
je Kanal und Zielgruppe, setzt sie in Layouts – und ein **Quality Gate** prüft jede Variante, bevor du
sie siehst. **Du entscheidest**, was freigegeben und exportiert wird.

Briefing-Beispiel: *«Pendler-Kopfhörer bis CHF 200, Story und Feed, Zielgruppe Studierende»*
Nenne Produkt, Preisrahmen, Kanäle (Feed, Story, Banner, Suchanzeige) und Zielgruppe.

## 2. Die Ampel lesen
| Farbe | Bedeutung | Was du tust |
|---|---|---|
| 🟢 grün | Keine Beanstandung | Inhaltlich prüfen, freigeben oder ablehnen |
| 🟡 gelb | Eine Empfehlung ist verletzt oder die Markenstimme ist schwach | Meldung lesen; Freigabe nur **mit Begründung** |
| 🔴 rot | Offizielles Plattform-Limit verletzt, Fakt nicht belegt oder verbotene Aussage | **Nicht freigebbar.** Korrigieren oder ablehnen |

Jede Meldung nennt die Regel, das Feld, den Grund und die Quelle (z.B. die Google-Hilfeseite). Typische
rote Meldungen: falscher Preis, Zahl nicht in den Produktdaten, «Rabatt», «sofort lieferbar», Titel zu lang.

**Korrigieren:** Text im Feld rechts anpassen, «Korrigieren & neu prüfen». Die neue Fassung wird neu
gerendert und läuft erneut durchs Gate. Ein früherer Entscheid verfällt.

## 3. Wann ein Mensch eingreifen muss – immer bei diesen Punkten
- **Qualitative Behauptungen** («läuft auch ohne Akku», «ideal für Allergiker»): Das Gate prüft Zahlen,
  Preise und Begriffe – nicht, ob eine Aussage inhaltlich stimmt.
- **Gelbe Varianten:** Die Markenstimme-Bewertung ist ein Hinweis, kein Urteil.
- **Bilder:** Passt das Produktbild zum Text? Liegt nichts Wichtiges in den rot markierten Zonen
  (Schalter «Sichere Zonen einblenden»)?
- **Ton gegenüber Menschen:** Witze auf Kosten anderer erkennt kein Regelwerk zuverlässig.

Ablehnungsgründe aufschreiben: Sie sind der Rohstoff, um die Skills zu verbessern.

## 4. Einen Skill anpassen (ohne Code)
Die Regeln liegen in drei Ordnern unter `skills/`:

| Skill | Was du dort änderst |
|---|---|
| `markenstimme` | Haltung, Beispiele, No-Gos, verbotene Floskeln, Bewertungsrubrik |
| `kanalformate` | Masse, Zeichenlimits, sichere Zonen – jeder Wert mit Quelle und Prüfdatum |
| `faktencheck` | Welche Begriffe verboten sind, welche Superlative einen Beleg brauchen |

So gehst du vor:
1. In `SKILL.md` (Text) oder `rules.yaml` (Listen und Werte) ändern. Beispiel: in
   `skills/faktencheck/rules.yaml` unter `verboten:rabatt_aktion` den Begriff `Knaller` ergänzen.
2. Oben in `SKILL.md` die **Version erhöhen** (z.B. 1.0.1 → 1.0.2).
3. In `CHANGELOG.md` einen Abschnitt `## 1.0.2 – Datum` mit dem Grund ergänzen.
4. Prüfen: `uv run python -m creative_agent.skills` – zeigt OK oder genau, was falsch ist.
5. Änderung als Pull Request einreichen; nach Freigabe gilt die neue Version.
   Jede Änderung wird im nächsten Eval-Lauf neu gemessen.

## 5. Einen neuen Kanal hinzufügen
In `skills/kanalformate/rules.yaml` einen bestehenden Kanal-Block kopieren, umbenennen (z.B.
`linkedin_feed`), Werte von der **offiziellen** Seite der Plattform übernehmen und je Wert `quelle`,
`status` (`offizielles Limit` oder `Empfehlung`) und `geprueft` eintragen. Hat der Kanal ein Bild, unter
`layout:` ein vorhandenes Layout wählen (`feed`, `story`, `banner`). Version erhöhen, prüfen – fertig.
Es braucht keine Programmierung: Der Agent liest Felder und Limits direkt aus dem Skill.

## 6. Export
«Export erstellen» liefert ein ZIP mit: Google-Ads-CSV (Suchanzeigen, Status «Pausiert»), Meta-CSV,
PNG je Bildvariante und `manifest.json` (wer hat wann warum freigegeben, mit welchen Skill-Versionen).
Nur freigegebene Varianten sind enthalten. Vor dem Hochladen in die Plattform: Stichprobe ansehen.
