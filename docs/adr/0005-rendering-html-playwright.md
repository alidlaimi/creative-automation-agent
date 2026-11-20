# 0005 – Layouts als HTML/CSS, gerendert mit Playwright

- Status: vorgeschlagen
- Datum: 2026-11-20

## Kontext
Varianten sollen in modulare Layouts für Feed (4:5), Story (9:16) und Banner (1.91:1) gesetzt werden.
Die Bildregeln der Plattformen (sichere Zonen, max. 20 % Text bei Google Display) sollen
**deterministisch geprüft** werden, nicht per Augenmass.

## Optionen
1. **Pillow (Python-Bildbibliothek)** – keine Browser-Abhängigkeit, aber Zeilenumbruch, Typografie und
   Messung selbst bauen; Designer können Layouts nicht anpassen.
2. **Design-Tool-API (z.B. Figma, Canva)** – professionelle Vorlagen, aber Konto/Lizenz, Netzabhängigkeit,
   Messung der Ergebnisse schwierig.
3. **HTML/CSS-Templates + Playwright** – Layouts lesbar und von Designern anpassbar, der Browser rendert
   Typografie korrekt und kann nach dem Rendern **messen**, wo jeder Baustein liegt.

## Entscheid
Option 3.

- Bausteine (`produktbild`, `produktname`, `headline`, `preis`, `cta`, `hintergrund`) als Jinja2-Makros,
  jedes mit `data-block` markiert. Formate setzen die Bausteine nur unterschiedlich zusammen.
- Masse und sichere Zonen kommen aus dem Skill `kanalformate` (CSS-Variablen) – keine Zahl im Template.
- **Preis und Produktname im Bild stammen aus den Produktdaten**, nicht vom Modell: Ein falscher Preis
  im Bild ist dadurch ausgeschlossen. Das Modell liefert nur Headline und CTA.
- Autoescape an: Text aus Schnittstelle oder Modell kann kein HTML/JavaScript einschleusen.
- **Messbericht** je Rendering: Bausteine ausserhalb der sicheren Zone, Textanteil in %, Textüberlauf
  (mindestens eine halbe Zeile verborgen), fehlende Pflichtelemente, Bild geladen. Grundlage fürs Gate.
- Texte schrumpfen nie; zu langer Text erscheint als Überlauf statt still verkleinert zu werden.
- Optionale Hilfslinien (rot markierte unsichere Zonen) für die Review.
- Eigenes neutrales Design über CSS-Variablen; kein Galaxus-Logo.

## Konsequenzen
- Playwright braucht ein Chromium (`uv run playwright install --with-deps chromium`); in CI im Docker-Image.
- Browser-Tests sind markiert (`browser`) und werden übersprungen, wenn kein Chromium vorhanden ist.
- Produktbilder werden zur Laufzeit von Galaxus geladen und nur lokal gespeichert (`output/`).
- Nächster Schritt wäre ein echtes Design System (Farben, Schriften, Abstände) als eigener Skill.
