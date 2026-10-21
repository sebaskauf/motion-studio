---
name: motion-video-zerlegen
description: Ein Vorbild-Video laden und messbar zerlegen (Schnitte und Szenen, Kontaktbögen, Palette, Bewegung und Kamera, Text per OCR, Captions, Rhythmus, Typ und Machbarkeit). Laden bei "Video zerlegen", "analysiere das Video", "Schnitte finden", "Kontaktbogen", "welcher Stil ist das", "ist das nachbaubar", "Machbarkeit", "Typ bestimmen".
---

# Video zerlegen

Ziel: Für jedes Vorbild-Video ein Ordner `__ARBEIT__/kanaele/<slug>/analyse/<id>/` mit `analyse.json`, `ANALYSE.md` und `boegen/`, alle Bögen angesehen, Fehler der Automatik korrigiert.

## Befehle

1. Laden: `__HEIM__/ms laden <id> --kanal <slug>` (YouTube, TikTok, Instagram per yt-dlp ohne Login oder Apify-Link). Eigene Datei: `__HEIM__/ms laden datei <pfad> --url <quelle> --views N --kanal <slug>`. Das Transkript entsteht dabei mit.
2. Zerlegen: `__HEIM__/ms zerlegen <id> --kanal <slug>`. Dauer: rund 40 s für 30 s in 720p, rund 2 min für 70 s in 1080p60.
3. Ton: `__HEIM__/ms ton-zerlegen <id> --kanal <slug>` (Skill motion-ton-zerlegen). Hängt seinen Abschnitt an ANALYSE.md.

Optionen von `ms zerlegen`: `--schwelle 3.0` (kleiner = mehr Schnitte), `--abstand 0.2` (s), `--ocr-fps 2`, `--sprachen de-DE,en-US`, `--ohne-ocr`, `--ohne-boegen`, `--out <ordner>` für Dateien außerhalb eines Kanals.

## Was drinsteht

| Teil | Wo | Wie gemessen |
|---|---|---|
| Szenen mit Start/Dauer | `analyse.json` → `szenen[]` (`id`, `start`, `ende`, `dauer`, `uebergang`) | Grundlage für den Vergleich Original gegen Nachbau |
| Übergänge | `schnitte[]`: `hart`, `hart+weissblitz`, `wisch`, `ueberblendung` | Bilddifferenz gegen die Umgebung, Farbverteilung, Kanten-Korrelation |
| Wechsel ohne Schnitt | `ereignisse.wechsel_im_bild` | Lichtwechsel, Pops, Textwechsel: Bildaufbau bleibt gleich |
| Kamera je Szene | `szenen[].kamera` (Schwenk %/s, Zoom %) | Phasenkorrelation auf vier Bildvierteln, grob |
| Bewegung | `bewegung` (Energiekurve 10 Hz, ruhige Phasen > 1,5 s, Doppelbilder) | Doppelbilder ab 35 % = auf Zweien animiert |
| Palette | `szenen[].palette`, `hintergrund`, `palette` gesamt | k-Means in Lab auf Schlüsselbildern (2 pro s) |
| Text | `text.einblendungen` (Box, Schrift ca. px), `text.captions` | Apple Vision (pyobjc oder Swift), sonst tesseract |
| Captions | Zone (px und %), Zeilenhöhe, Wörter pro Gruppe, Großbuchstaben, Füllung, Kontur, Grund, Hervorhebung | wechselnder Text in einem Höhenband, Abgleich mit dem Transkript |
| Typ | `typ` (Vorschlag, Anteile, Machbarkeit, Richtwert) und je Szene mit Sicherheit | Flächen, Kanten-Schärfe, Farbtöne, Paletten-Abdeckung, Text |
| Bögen | `boegen/uebersicht_NN.jpg` (1/s), `szene_NN.jpg` (4/s), `schnitte_NN.jpg`, `energie.png` | Szenennummer in jeder Kachel, roter Balken = neue Szene |

## Prüfen (Pflicht, mit dem Read-Werkzeug ansehen)

1. `schnitte_NN.jpg`: Jede Grenze zeigt zwei Bilder davor und zwei danach (bei Wisch und Überblendung Anfang und Ende). Für jede Grenze: echter Schnitt, Übergang oder Fehlalarm?
2. `uebersicht_NN.jpg`: Fehlt ein Schnitt (Bildwechsel ohne roten Balken)? Ist eine Szene in Wahrheit zwei?
3. Jeden `szene_NN.jpg` ansehen: Bildwelt, Figuren, Kamera, Effekte. Stimmt der Typ der Szene?
4. `energie.png`: Wo ist Ruhe, wo Tempo? Passt das zum Schnittbild?
5. Korrekturen unten in ANALYSE.md unter `## Korrekturen (Auge)` eintragen: falsche Grenzen, fehlende Grenzen, falscher Typ, mit Zeit und Grund. analyse.json nicht von Hand ändern.

## Typ und erreichbare Ähnlichkeit (Richtwerte aus gemessenen Nachbauten)

| Typ | Weg | Richtwert |
|---|---|---|
| 2D-Collage/Typo | HyperFrames + GSAP (motion-szene-2d) | ΔE ≈ 5, SSIM ≈ 0,84 erreicht (30-s-Papiercollage) |
| UI/Screen | HTML/CSS in HyperFrames | wie 2D, wenn die Schriften gefunden werden |
| 3D, Web-tauglich | Three.js in HyperFrames (motion-szene-3d-web) | ΔE ≈ 16 erreicht, Ziel < 15 knapp verfehlt. Hauptfehler: Figuren-Proportionen |
| 3D, Blender-Niveau | Blender-Spur (motion-szene-blender, Beta) | Szene, Licht, Kamera klappen. Figuren, Rig, Acting offen: erst 5 bis 8 s Probe messen |
| Realfilm/KI-Video | nicht nachbaubar | nur Schnitt, Captions, Ton, Skript übernehmen |

Die Automatik schlägt vor, das Auge entscheidet. Figuren mit Gesicht und Rig, weiches Licht wie im Film, echte Kamera oder KI-Video erkennst nur du sicher.

## Gate (fertig, wenn)

- `analyse.json` und `ANALYSE.md` existieren, `typ` und `szenen` sind gefüllt.
- Alle Bögen angesehen. Jede Grenze im Schnitte-Bogen beurteilt, Korrekturen in ANALYSE.md.
- Typ bestätigt oder begründet korrigiert, Machbarkeit in einem Satz.
- Captions beschrieben (Zone, Größe, Farben, Wörter pro Gruppe) oder "keine Captions" bestätigt.
- Register-Status `zerlegt` (setzt das Werkzeug).

## Fallen

- Gemessene Trefferquote: an drei Testvideos alle echten harten Schnitte gefunden. Fehlalarme gibt es bei Bildwechseln in einem Bildschirm (Display im Bild), Blitz-Effekten und schnellen 3D-Kamerafahrten. Deshalb immer den Schnitte-Bogen prüfen.
- Lichtwechsel, Pops und reine Titelwechsel ohne Schnitt landen unter "Wechsel im Bild". Ein Titelwechsel kann trotzdem eine inhaltliche Szene beginnen: im Bogen entscheiden.
- Eine 3D-Kamerafahrt über mehrere Sets hat keinen Schnitt. Szenen nach Inhalt teilst du von Hand (Korrekturen).
- Überblendungen über 0,9 s werden ignoriert (sonst zählt ein zoomender Tunnel als Blende).
- Kamera-Werte sind grob. Viel Eigenbewegung im Bild (Partikel, Figuren) verfälscht sie, dann steht "unklar".
- Captions ohne Transkript sind ungenauer: zuerst `ms laden` (macht das Transkript), dann `ms zerlegen`.
- Schriftgröße ist eine Schätzung aus der Zeilenbox von Vision (Großbuchstaben: Box ≈ 0,87 em, an einem Banner geeicht; gemischt ≈ 1,05 em, nicht geeicht). Für den Nachbau die Schrift am Bild nachmessen und mit dem Nachbau-Snapshot vergleichen.
- OCR liefert bei Collagen viele Schnipsel. Einblendungen mit einem Bild und unter 4 Zeichen fallen weg.
- Videos ohne Tonspur (oft bei Apify-Reels) bekommen den Ton über `ms laden` aus dem Tonlink. Liegt der Ton als eigene Datei daneben: `ms ton-zerlegen … --ton <datei>`.
- Texterkennung auf dem Mac: Apples Vision über die Pakete `pyobjc-framework-Vision` und `pyobjc-framework-Quartz`. Die installiert `__HEIM__/ms setup venv` mit (Studio-Umgebung, nie `pip install` ins System); `__HEIM__/ms check` zeigt, ob sie da sind. Fehlen sie, baut das Werkzeug `ocr_vision.swift` (braucht passende Command Line Tools), sonst tesseract, sonst ohne Text.
- Nie ein ganzes Video roh in den Speicher laden. Normalweg sind die `ms`-Werkzeuge. Reicht das nicht (eigene Zusatzmessung), ein kleines eigenes Skript mit der Studio-Python und der Bibliothek `_ms` (Bilder nur über `_ms.frames()`, streamt, oder `_ms.frame_bei()`). Erlaubt ist das eigene Hilfsskript, nicht der Aufruf der Werkzeug-Skripte unter `tools/` an `ms` vorbei. Claude Code fragt beim ersten Start einmal nach Erlaubnis.
  ```python
  # Datei z. B. __ARBEIT__/kanaele/<k>/analyse/<id>/messung.py, Start: __HEIM__/.venv/bin/python <datei>  (Windows: __HEIM__/.venv/Scripts/python.exe)
  import sys
  sys.path.insert(0, "__HEIM__/tools")
  import _ms
  video = "__ARBEIT__/kanaele/<k>/vorbild/<id>.mp4"
  for t, bild in _ms.frames(video, fps=10, groesse=(108, 192), start=3.5, ende=4.6):   # streamt Bild für Bild
      print(f"{t:.2f}", round(float(bild.mean()), 1))
  _ms.kontaktbogen(video, [3.8, 4.0, 4.2, 4.4], "__ARBEIT__/kanaele/<k>/analyse/<id>/boegen/punch.jpg", spalten=4)
  ```
- Schnelle Zooms und Kamera-Punches innerhalb einer Szene meldet `ms zerlegen` unter „Kamera-Ereignisse in einer Szene“ (Bewegungs-Spitze plus Skalenänderung, auch in der Kamera-Spalte der Szenen-Tabelle). Ein großes Objekt, das mittig wächst, misst sich ähnlich wie ein Zoom: im Szenenbogen entscheiden und in ANALYSE.md korrigieren. Spitzen ohne Kamera-Änderung stehen unter „Bewegungs-Spitzen“.
