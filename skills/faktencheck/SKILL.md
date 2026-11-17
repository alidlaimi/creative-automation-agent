---
name: faktencheck
description: Welche Angaben in Werbetexten belegt sein müssen und welche Aussagen verboten sind. Grundlage für den deterministischen Faktencheck im Quality Gate.
version: 1.0.0
owner: Kreationsteam (Platzhalter)
---

# Faktencheck

**Grundsatz:** Jede Zahl und jeder Preis in einem Werbetext muss im Produktdatensatz stehen, den die
Galaxus-Schnittstelle für **genau dieses Produkt (Produkt-ID)** geliefert hat. Was nicht belegt ist, stoppt
das Gate (rot). Das Modell darf formulieren, aber keine Fakten erfinden.

## Was geprüft wird
1. **Preise** – exakt wie in den Produktdaten (`preis_exakt: true`). CHF 96.80 ist nicht CHF 97.–.
   Varianten mit gleichem Namen haben teils andere Preise: Es zählt immer die Produkt-ID.
2. **Zahlen mit Einheit** (z.B. «60 h», «30 mm») – müssen in einem der `belegfelder` vorkommen.
   Schreibweisen wie «60 h», «60h» oder «60 Stunden» gelten als gleich.
3. **Superlative** («die beste», «leiseste») – nur erlaubt, wenn der Begriff in den Produktdaten steht.
4. **Bewertungen** («4.5 Sterne», «über 800 Bewertungen») – nur mit den Bewertungsdaten des Produkts.
5. **Verbotene Aussagen** – siehe `verbotene_aussagen`. Die Schnittstelle liefert keine Rabatte,
   keinen Lagerbestand und keine Lieferzeiten. Solche Aussagen sind deshalb nie belegbar.

## Anpassen ohne Code
Begriffe in `rules.yaml` ergänzen oder entfernen (Gross-/Kleinschreibung spielt keine Rolle),
Version erhöhen, Changelog nachführen, prüfen mit `uv run python -m creative_agent.skills`.
Jede Änderung wird danach im Eval-Lauf neu gemessen.
