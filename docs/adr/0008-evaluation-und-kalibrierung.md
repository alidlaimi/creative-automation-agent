# 0008 – Evaluation: Testset, Negativtests, kalibrierte Markenstimme, versionierter Bericht

- Status: vorgeschlagen
- Datum: 2026-11-24

## Kontext
Angekündigt sind messbare Zusagen: 0 erfundene Preise/Spezifikationen, Formate 100 % konform,
Freigabequote, Kosten pro Variante, Zeit vom Briefing bis zur Freigabe. Jede Änderung an Skills oder
Prompts soll neu gemessen werden. Die Markenstimme-Bewertung durch ein Modell ist nur so viel wert,
wie sie mit menschlichem Urteil übereinstimmt.

## Entscheid
1. **Testset** (`eval/briefings/briefings.yaml`, versioniert): 15 Briefings über 15 Kategorien, alle vier
   Kanäle, verschiedene Preisspannen (nur Obergrenze, nur Untergrenze, sehr tief), eines mit zwei
   Zielgruppen.
2. **Negativtests** (`eval/negativtests.yaml`): 16 absichtlich fehlerhafte Varianten gegen echte,
   aufgezeichnete Produktdaten – jede mit erwarteter Regel – plus 3 saubere **Kontrollfälle**, die nicht
   rot werden dürfen (misst Fehlalarme). Läuft ohne Netz in jedem Testlauf (pytest) und im Bericht.
3. **Faktentreue ehrlich gemessen:** zwei Zahlen statt einer. (a) Wie oft erzeugt der Generator
   Faktenfehler? (b) Wie viele davon erreichen eine menschliche Sichtung (nicht rot)? Ziel für (b) ist 0;
   dass das Gate erkennt, belegen die Negativtests. Was der Faktencheck grundsätzlich nicht sieht
   (qualitative Behauptungen), steht als Grenze im Bericht.
4. **Kalibrierung der Markenstimme:** 20 eigene Feed-Texte unterschiedlicher Qualität zu echten Produkten,
   die alle die deterministischen Regeln bestehen (kalibriert wird nur, was die Regeln nicht entscheiden).
   - Menschliches Urteil **blind** (ohne Modellbewertung) in einer kleinen Beschriftungs-Oberfläche:
     «passt» / «passt nicht», binär, weil das der echten Freigabeentscheidung entspricht.
   - Modellurteil «passt» = Mittel ≥ Schwelle und kein Kriterium ≤ 2.
   - Gemessen für Schwellen 2.0–4.5: Übereinstimmung, **Cohens Kappa** (zufallsbereinigt – bei unausgewogenen
     Urteilen täuscht reine Übereinstimmung), falsche Freigaben, falsche Sperren.
   - Gewählt: höchstes Kappa; bei Gleichstand weniger falsche Freigaben (teurerer Fehler), dann strenger.
   - **Leave-one-out** als ehrlichere Schätzung, weil Schwelle und Messung sonst auf denselben 20 Texten
     beruhen.
   - Modellurteile werden mit Fingerabdruck (Text, Produkt, Skill-Hash, Prompt, Modell) zwischengespeichert:
     erneute Auswertung kostet nichts, eine Änderung an Skill oder Prompt erzwingt neue Urteile.
   - Die Bewertung bleibt **höchstens gelb**: Auch kalibriert ist sie ein Hinweis, die Freigabe bleibt beim
     Menschen.
5. **Eval-Lauf** über alle Briefings mit **Gesamtbudget** (Abbruch vor dem nächsten Briefing), fortsetzbar.
6. **Bericht** als Markdown in `eval/reports/` (versioniert im Repository) mit Commit, Prompt-Hash,
   Skill-Versionen, Modellen und Schwellwert, plus Kennzahlen als JSON. Liegt ein früherer Bericht vor,
   zeigt eine Vergleichstabelle Verbesserungen ✅ und Verschlechterungen ⚠️ (Regressionsprinzip).

## Konsequenzen
- Freigabequote und Zeit bis zur Freigabe entstehen erst durch eine echte Review; der Bericht lässt sich
  nach der Review neu erzeugen, ohne Kosten.
- 15 Briefings und 20 Texte sind wenig: Der Bericht nennt die Kennzahlen als Hinweise, nicht als
  statistisch belastbare Werte. Für den Betrieb würde man das Testset aus echten Kampagnen erweitern und
  mehrere Personen beschriften lassen (Übereinstimmung zwischen Menschen als Obergrenze).
- Kalibriert ist an einer Person (Ali) und an einer eigenen Ableitung der Markenstimme.
