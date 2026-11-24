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

## Ergebnis der ersten Kalibrierung (2026-11-24)
20 Texte, 17 von Hand «passt», 3 «passt nicht». Modell: Sonnet 5.5, markenstimme 1.0.1. Kosten USD 0.23.

| Regel | beste Schwelle | Übereinstimmung | Kappa | LOO |
|---|---|---|---|---|
| Sperre, wenn ein Kriterium ≤ 2 (ursprünglich) | 3.25 | 50 % | 0.17 | 45 % |
| Sperre, wenn ein Kriterium ≤ 1 | 3.25 | 60 % | 0.25 | 60 % |
| keine Kriterium-Sperre | **2.25** | **85 %** | **0.48** | **85 %** |

**Befund:** Mit der ursprünglichen Regel urteilt das Modell viel strenger als der Mensch: Es sperrt
10 Texte, die der Mensch freigeben würde – fast immer, weil «unkonventionell» mit 1 bewertet wurde.
Der Mensch beurteilt «Würde ich das freigeben?», die Rubrik misst «Wie stark ist der eigene Dreh?».
Das Modell hat dabei nie einen Text durchgelassen, den der Mensch ablehnt.

**Entscheid:** keine Kriterium-Sperre, Schwelle 2.25 (`JUDGE_MIN_CRITERION=0`, `JUDGE_THRESHOLD=2.25`).
Die Bewertung wirkt damit als Erkennung klar schwacher Texte; sie bleibt höchstens gelb.

**Vorbehalt:** Die Regel wurde nach Ansicht der Daten gewählt. Leave-one-out deckt nur die Wahl der
Schwelle ab, nicht die Wahl der Regel – die 85 % sind daher eher optimistisch. Mit nur 3 Ablehnungen ist
Kappa instabil. Nächster Schritt: neue, nicht verwendete Texte beschriften und die Regel daran prüfen,
idealerweise mit einer zweiten Person aus dem Kreativ-Team.
