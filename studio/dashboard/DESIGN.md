# DESIGN.md STUDIO (Dashboard von Motion-Studio)

Gilt für `index.html` in beiden Modi: eingebaut (Motion-Studio-Arbeitsordner) und mit `--adapter` (z. B. reel-studio im Agentic OS).
Einmal entschieden, danach Gesetz. Wer davon abweicht, ändert zuerst diese Datei.

## Gefühl
Mood-Wörter: ruhig, präzise, werkstattartig, warm-dunkel, ehrlich.
Referenz: Agentic OS (Tab [07] AGENTIC: Fast-Schwarz, ein Orange, Mono-Labels in Versalien, grüne Statuslinien, 1px-Linien). STUDIO ist ein Geschwister davon, kein fremdes SaaS.
Richtung: C Technisch-Mono, gebunden an die Agentic-OS-Tokens.

## Kern-Loop (UX regiert)
Tab öffnen → in 3 Sekunden wissen: Braucht etwas mich? Wann geht der nächste Post raus, reicht der Vorrat? Was tun die Agenten gerade? → höchstens 1 Klick zur Aktion (Weiter, Folge bauen, ansehen).
Reihenfolge auf dem Bildschirm folgt genau diesen drei Fragen.

## Farben (CSS-Variablen, Pflicht)
Dunkel (Standard, `?thema=dunkel`, Agentic OS):
--bg #0b0a09 · --panel #121110 · --panel-2 #181614 · --line #24211e · --line-2 #302c28
--text #ece9e3 · --muted #8b877f · --dim #5b5852
--accent #ff6b1a (NUR Hauptaktion, ausgewählt/aktiv, aktueller Schritt) · --accent-weak #2a1a10
--ok #4ade80 · --warn #e3b46b · --bad #f0857c
Hell (`?thema=hell`, eigenständig im Browser):
--bg #f4f1ec · --panel #fbfaf7 · --panel-2 #f0ece5 · --line #e3ded6 · --line-2 #d6d0c6
--text #1b1917 · --muted #6d675e · --dim #9a948a · --accent #b8460a (Text auf Akzent weiß) · --accent-weak #fbe6d9
--ok #1a7f5a · --warn #8f5c0e · --bad #c2402f   (20.10.: Akzent und warn dunkler, damit beide WCAG AA auf dem Panel erreichen)
Regeln: Akzent nie als Fläche großer Blöcke, nie im Fließtext, eine Akzent-Stelle pro Blickfeld. Status über Farbe UND Text (nie nur Farbe).

## Schrift (self-hosted woff2 unter dashboard/fonts/, OFL)
Labels, Zahlen, Zeiten, Abschnittstitel: JetBrains Mono 500/700, Labels in Versalien mit letter-spacing .12em.
Fließtext, Titel von Folgen, Sätze: IBM Plex Sans 400/600, Zeilenhöhe 1.5.
Skala: 10 (Mono-Label, Zeilenhöhe ≥ 1.4, sonst verschwinden Umlaut-Punkte bei Versalien) · 11 · 13 (Text) · 15 (Folgentitel) · 20 (Abschnitts-Kopfzahl) · 28 (Kennzahl).
Verboten: Inter, Roboto, Arial, System-Font als Identität.

## Fläche und Tiefe
8er-Raster. Radius 6px für Panels, 4px für Knöpfe und Tags. Flach: 1px-Linien, keine Schatten (Ausnahme: Detail-Schublade).
Maximal 2 Ebenen: Panel → Zeile. Keine Karten in Karten, keine Pillen in Pillen.
Kein Akzentbalken links an Karten oder Bannern. Hinweise sind Zeilen mit Mono-Tag (WARTET, FEHLER, HÄNGT).

## Komponenten
- Kopfzeile (eine Zeile): STUDIO + Kanal · Status-Chips (Autopilot, nächster Post, Vorrat) · rechts Hauptaktion + Menü „⋯“ (selten Genutztes, Gefährliches mit Bestätigung).
- Panel: Mono-Kopf (TITEL · Zähler rechts), 1px-Linie, Zeilen.
- Schrittleiste (Pipeline je Folge): Punkte + Linie wie im Agentic OS, erledigt grün, aktueller Schritt orange, offen dim.
- Sendeplan: Zeitleiste des Tages, ein Slot pro Sendezeit, Zwilling als kleiner Nachläufer.
- Tags: Mono, 10px, Rahmen 1px, Text in Statusfarbe. TRIAL und ZWILLING neutral (muted).
- Icons: ein Satz, inline SVG, 16px, Strich 1.5, runde Enden (play, extern, terminal, pfeil, mehr, neu laden). Keine Emojis.
- Knöpfe: primär (orange Fläche, dunkler Text) genau einer pro Blickfeld; sekundär (Rahmen); Gefahr (Rahmen + rote Schrift, immer mit Bestätigung).

## STUDIO v3 (22.10.2026)
- Pixel-Crew (`pixel.js`):
  - Jeder Agent ist ein kleiner Clawd (32 × 28 Pixel, pixelig skaliert) mit Rollen-Zubehör.
  - Die Tätigkeit bestimmt die Requisite: rendert = Filmrolle, Stimme = Mikro, fragt = Hand hoch und orangenes Fragezeichen, Fehler = Rauch, schläft = zZ.
  - Das ist die einzige Dauer-Animation der Seite: ein gemeinsamer Takt mit 8 Bildern/s, ruhige Schritt-Loops, pausiert im Hintergrund.
  - Bei „weniger Bewegung“ zeigt jede Figur ein Standbild.
- Crew-Leiste über den Agenten. Beim Drüberfahren, Fokus oder Klick öffnet sich eine Info-Karte mit ruhiger Szene: Die Figur schwebt auf einem Kissen, Staubkörnchen steigen auf.
- Frage-Block:
  - Steht in JETZT, nicht doppelt. Die Agentenkarte zeigt nur eine Kurzzeile mit „Antworten“.
  - Optionen sind ganze Zeilen mit Ziffer, darunter steht das Feld für eine eigene Antwort.
  - Die Freigabe zeigt den Befehl als Mono-Kasten.
- Chat-Schublade: Verlauf als Gespräch (Agent links, du rechts in Akzent-schwach, Werkzeuge als eingeklappte Mono-Zeilen), unten Antwort.
- Steuerung: Schalter (Autopilot, Tagesbau) statt Menüpunkten. Dazu Fortschrittsbalken (heute) und Wochenbudget mit Marke an der Bremse.
- Zahlen im Stil der Plattform:
  - Instagram, TikTok und YouTube haben je eigenen Profilkopf und eigenes Raster.
  - Bewusste Ausnahme von der Farbregel nur in dieser Karte: der Instagram-Ring in Markenfarben bzw. TikTok schwarz.

## Motion
Ein gestaffelter Aufbau beim ersten Laden (300 bis 450 ms gesamt). Feedback 150 bis 200 ms. Polling ändert nur Inhalte, nie das Layout (kein Flackern, kein Springen). Keine blinkenden Punkte, keine Scale-Hover. prefers-reduced-motion respektieren.

## Zustände (jeder Bereich)
laden (Skeleton-Zeilen) · leer (1 Satz, warum es nützt, 1 Knopf) · Fehler (freundlich, nächster Schritt, Details ins Log) · gefüllt · übervoll (Liste begrenzt + „alle anzeigen“, lange Titel 2 Zeilen mit Auslassung).

## Sprache
Deutsch, kurz, konkret, keine internen Kürzel („8-fertig“ → „fertig“). Zeiten 12:35, Daten „Mo 19.10.“. Keine Floskeln.

## Verboten
Lila/Teal-Verläufe · Drei-Spalten-Deko · Emoji-Icons · blinkende Live-Punkte · Akzentbalken als Deko · gemischte Icon-Sets · Floskeltexte · Inter/System-Font.
