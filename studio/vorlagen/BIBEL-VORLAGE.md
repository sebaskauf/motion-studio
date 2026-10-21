# Bibel: <Kanalname> (@<handle>)

Stand: <JJJJ-MM-TT>. Grundlage: <Anzahl> Videos, zerlegt mit `ms zerlegen` und `ms ton-zerlegen`.

Legende:
- **[B]** beobachtet: in den Videos gemessen oder in den Bögen gesehen, mit Quelle (Video-ID, Zeit, Datei).
- **[P]** vermutet: plausible Herkunft oder Wirkung, nicht belegt.
- **[R]** Regel: unsere Entscheidung für den Nachbau und die eigenen Folgen. Kein Befund über das Vorbild.

Quellen:

| ID | Views | Faktor | Dauer | Analyse |
|---|---|---|---|---|
| <id> | <views> | <faktor> | <s> | `analyse/<id>/ANALYSE.md` |

## 0. Zweck und Messlatte

- Ziel: <eigene Folgen in diesem Stil, Sprache, Plattform> [R]
- Pilot: <ID des Videos, das fast 1:1 nachgebaut wird> [R]
- Messlatte Pilot (siehe Abschnitt 14) [R]

## 1. Format und Maße

- Auflösung, Bildrate, Dauer (Spanne und Median) [B]
- Sicherer Bereich: wo nie Wichtiges steht (Captions, Profil, Buttons der Plattform) [B/R]

## 2. Typ und Machbarkeit

- Typ je Video und nach Bildschirmzeit, z. B. "2D-Collage 70 %, 3D 30 %" [B, aus `analyse.json` → `typ`, mit Blick bestätigt]
- Weg: motion-szene-2d / motion-szene-3d-web / motion-szene-blender [R]
- Erreichbare Ähnlichkeit (Richtwerte: 2D ΔE ≈ 5, SSIM ≈ 0,84; einfache 3D ΔE ≈ 16; Figuren-Animation offen) [R]
- Was NICHT geht und warum, ehrlich [R]

## 3. Bildwelt

- Welt, Materialien, Stil (Papier, Vektor, Toon, Glas, UI …) [B]
- Wiederkehrende Motive und Requisiten [B]
- Layouts (Vollfläche, Bühne, Karte, geteiltes Bild) mit Anteil [B]

## 4. Palette

- Hintergründe und Hauptfarben als Hex mit Anteil, je Video und gesamt [B, `szenen[].palette`, `palette`]
- Akzentfarben und wofür sie stehen (Warnung, Marke, Hervorhebung) [B/P]
- Regel für eigene Folgen [R]

## 5. Schriften

- Titel/Banner: Schrift (Kandidat), Größe in px bei 1080 Breite, Gewicht, Groß/klein [B: Größe, P: Schriftname]
- Labels und Zahlen [B/P]
- Unsere Wahl (frei lizenzierte Schrift, die nah dran ist) [R]

## 6. Captions

- Zone in px und % der Höhe, Ausrichtung [B, `text.captions`]
- Schriftgröße, Füllung, Kontur, Grund (Kasten/Etikett), Groß/klein [B]
- Wörter pro Gruppe, Zeilen, Wechsel-Takt [B]
- Hervorhebung des aktiven Worts (Farbe, Größe, Animation) [B/P]

## 7. Kamera

- Ruhig, Schwenk, Zoom, Push-in, Whip: je Szene [B, `szenen[].kamera` + Bögen]
- Typische Stärke (Zoom % pro Szene) und Kurven (gleichmäßig, Punch, Abklingen) [B/P]

## 8. Schnitt-Rhythmus

- Schnitte pro 10 s, Szenenlänge Mittel/Median/kürzeste/längste [B, `rhythmus`]
- Verlauf über das Video (schneller Hook, ruhige Mitte …) [B]
- Bewegung: ruhige Phasen, Animation auf Zweien ja/nein [B, `bewegung`]

## 9. Übergänge

- Arten und Häufigkeit: hart, Wisch, Überblendung, Weißblitz, Match-Cut [B, `schnitte[]`]
- Was davor und danach passiert (Bögen `schnitte_NN.jpg`) [B]

## 10. Effekte

- Pop-ins mit Überschwingen, Stempel, Partikel, Zähler, Glühen, Rauch … mit Häufigkeit [B]
- Timing zur Stimme (Effekt auf dem Wort?) [B/P]

## 11. Figuren

- Gibt es Figuren? Form, Proportionen, Gesicht, wie bewegt [B]
- Machbarkeit (Bibliothek, 3D-Generator, Blender) [R]

## 12. Ton

- Lautheit (LUFS), LRA [B, `ton.json`]
- Stimme: Tempo (Wörter/s), Pausen, Charakter [B]
- Musikbett: ja/nein, Abstand zur Stimme in dB [B oder P]
- Effekte: Arten, an Schnitten oder auf Aktionen [P, bis angehört]
- Unser Mix-Ziel [R]

## 13. Skript-Baukasten

- Kurzfassung, Details in `SKRIPT-BAUKASTEN.md`: Länge, Wortbudget, Bausteine, Hook-Formeln, CTA [B/R]

## 14. Messlatte für den Pilot

| Was | Ziel | Wie gemessen |
|---|---|---|
| Farbabstand je Szene | z. B. ΔE < 7 (2D) bzw. < 15 (3D) | `ms vergleich` |
| Strukturähnlichkeit | z. B. SSIM > 0,8 (2D) | `ms vergleich` |
| Schnitte | gleiche Zeiten ±1 Frame | Szenen aus `analyse.json` |
| Captions | Position ±2 % der Höhe, gleiche Gruppenlänge | Paarbögen |
| Lautheit | Original ±1 LU | `ms ton-zerlegen` am Pilot |

Ausschlussfehler (Pilot fällt durch, egal wie gut der Rest ist) [R]:
- Ergebnis einer Aussage im entscheidenden Moment verdeckt
- Text auf dem Handy nicht lesbar
- Stimme und Bild nicht synchron
- Stil-, Material- oder Lichtbruch zwischen Szenen

## 15. Offene Fragen an den Nutzer

- <Frage, warum sie wichtig ist, Vorschlag>
