---
name: markenstimme
description: Tonalität für Werbetexte – Regeln, Beispiele, No-Gos und Bewertungsrubrik. Eigene Ableitung aus öffentlicher Galaxus-Kommunikation, ersetzbar durch echte Vorgaben.
version: 1.0.1
owner: Kreationsteam (Platzhalter)
herkunft: Ableitung (nicht offiziell)
---

# Markenstimme

> **Hinweis:** Dies ist **meine Ableitung** aus öffentlicher Kommunikation von Galaxus – keine offizielle
> Markenrichtlinie. Grundlage sind öffentlich publizierte Werte und Selbstbeschreibungen, u.a. der
> Leitsatz «Mutig sein, echt bleiben» und die Werte kooperativ, innovativ, piratisch, eigenverantwortlich,
> ambitioniert ([Stelleninserat Galaxus, jobs.ch](https://jobs.ch/de/stellenangebote/detail/889c344d-a3cf-4db9-818f-5fbfdf284bde)),
> sowie «Bestehendes immer wieder neu denken» ([Galaxus Jobs](https://www.galaxus.at/en/joboffer/4324)).
> Mit echten Vorgaben des Kreationsteams wird dieser Skill ersetzt: neue Version, gleiche Struktur.

## Haltung in drei Sätzen
1. **Ehrlich statt laut.** Wir sagen, was ein Produkt kann – und was nicht. Keine leeren Versprechen.
2. **Unkonventionell mit Substanz.** Ein überraschender Blickwinkel oder eine Prise Selbstironie, aber
   immer mit einem echten Produktnutzen dahinter.
3. **Nah an der Zielgruppe.** Wir duzen, sprechen konkret und in ihrer Situation (z.B. Pendeln, Lernen).

## Schreibregeln
- Du-Form. Schweizer Rechtschreibung: «ss», nie «ß». Preise als «CHF 139.–» oder «CHF 96.80».
- Ein Gedanke pro Satz. Verben statt Substantivketten.
- Höchstens ein Ausrufezeichen pro Text.
- Zahlen nur, wenn sie in den Produktdaten stehen (siehe Skill `faktencheck`).
- Kein Druck («Jetzt zuschlagen!»), keine künstliche Knappheit.

## Beispiele (eigene Formulierungen)
Die Beispiele zeigen die **Haltung**, nicht den Wortlaut. **Nie wörtlich oder fast wörtlich übernehmen** –
jede Variante braucht eine eigene Formulierung. Das Quality Gate prüft auf Übernahmen.

**Gut**
- «60 Stunden Akku. Das sind ziemlich viele Zugfahrten.» (konkret, belegbar, leicht selbstironisch)
- «Der Zug ist laut. Dein Kopf muss es nicht sein.» (Blickwinkel der Zielgruppe, klarer Nutzen)
- «Kabel statt Bluetooth: einstecken, fertig.» (unkonventionell, Nachteil wird zum Argument)

**Schlecht**
- «Revolutionärer Sound, der dein Leben verändert!!!» (Floskel, Übertreibung, drei Ausrufezeichen)
- «Die besten Kopfhörer der Welt – nur heute im Angebot!» (unbelegter Superlativ, Aktionsaussage)
- «Sehr geehrte Kundinnen und Kunden, entdecken Sie unser Sortiment.» (Sie-Form, austauschbar)

## No-Gos
Floskeln aus `verbotene_floskeln`, das Zeichen «ß», mehr als ein Ausrufezeichen, Sie-Form,
Aussagen über andere Marken, Witze auf Kosten von Personengruppen.

## Bewertung
Die Rubrik in `rules.yaml` wird vom Modell angewendet (1 = trifft nicht zu, 5 = trifft voll zu).
Die Bewertung ist **kalibriert** an von Menschen beschrifteten Beispielen (Meilenstein 8); der Schwellwert
wird dort begründet festgelegt. Deterministische Regeln (Anrede, «ß», Ausrufezeichen, Floskeln) prüft der
Code – dafür braucht es kein Modell.
