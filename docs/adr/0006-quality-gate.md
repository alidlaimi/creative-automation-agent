# 0006 – Quality Gate: Regeln vor Modell, Ampel mit Begründung

- Status: vorgeschlagen
- Datum: 2026-11-20

## Kontext
Bevor ein Mensch eine Variante sieht, soll jede Variante geprüft sein: Formate, Fakten, Bildregeln,
Markenstimme. Ziele: 0 erfundene Preise/Spezifikationen, 100 % plattformkonforme Formate.

## Optionen
1. **Alles per Modell beurteilen** («Ist diese Anzeige korrekt?») – einfach, aber nicht reproduzierbar,
   nicht erklärbar und genau bei Zahlen unzuverlässig.
2. **Nur Regeln** – reproduzierbar, aber Tonalität lässt sich nicht als Regel fassen.
3. **Regeln zuerst, Modell nur für die Markenstimme** – deterministisch, wo möglich; das Modell bewertet
   nur, was sich nicht regeln lässt.

## Entscheid
Option 3.

**Ampel:** schwerste Meldung bestimmt die Farbe. Schweregrad aus dem Skill-Status:
`offizielles Limit`/`interne Vorgabe` → rot, `Empfehlung` → gelb. Jede Meldung nennt Regel, Feld,
Begründung und Quelle (Skill-Version bzw. offizielle URL mit Prüfdatum).

**Regeln (Code):**
- Formate: Zeichenlimits, Anzahl (z.B. RSA 3–15 Titel), leere Felder, CTA.
- Bildregeln aus dem Messbericht: sichere Zone, Textanteil (Google Display ≤ 20 %), Textüberlauf,
  Pflichtelemente, Bild geladen.
- Faktencheck **gegen die Produkt-ID** (Varianten mit gleichem Namen haben andere Preise):
  - Preise exakt (CHF 96.80 ≠ CHF 99.–), Schweizer Schreibweisen (79.–, 1'299.–).
  - Zahlen mit Einheit müssen in Name/Eigenschaften/Beschreibung stehen; Synonyme (h = Std. = Stunden),
    geschützte Leerzeichen der Schnittstelle werden normalisiert.
  - **Jede weitere Zahl muss erklärbar sein** (Produktname, Bewertung, Produktdaten) – fängt auch
    erfundene Angaben ohne Einheit («2 Jahre Garantie»).
  - Superlative nur mit Beleg; Rabatt-, Verfügbarkeits- und Lieferaussagen immer rot.
- Markenstimme deterministisch: «ß», Floskeln, Ausrufezeichen, Sie-Form, (fast) wörtliche Übernahme
  der Skill-Beispiele (≥ 5 gleiche Wörter rot, 3–4 gelb).
- **Prompt-Injection:** Wirkt ein Produkttext wie eine Anweisung, gibt es einen Hinweis, und die
  Beschreibung zählt **nicht mehr als Beleg** – sonst könnte ein manipulierter Text seine eigenen
  Behauptungen «belegen» (im Test gefunden).

**Modell (Markenstimme):** Bewertung je Kriterium der Rubrik (strukturierte Ausgabe), Mittelwert gegen
Schwellwert. Läuft nur, wenn die Regeln nicht schon rot sind (Kosten). **Vorläufig höchstens gelb**, bis
die Kalibrierung (Meilenstein 8) eine Übereinstimmung mit menschlichen Urteilen belegt.

## Konsequenzen
- Das Gate ist eine reine Funktion (Variante + Produktdaten + Skills → Ergebnis): korrigierte Varianten
  in der Review laufen einfach erneut durch.
- Grenzen des Faktenchecks: Er prüft Zahlen, Preise, Superlative und Verbotsbegriffe, nicht jede
  qualitative Aussage («auffälliges Design»). Dafür bleibt die menschliche Freigabe.
- Begriffslisten sind unvollständig; neue Fälle aus der Review werden als Begriff im Skill ergänzt und
  im Eval-Lauf gemessen.
