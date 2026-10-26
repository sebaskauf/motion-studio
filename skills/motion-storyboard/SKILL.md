---
name: motion-storyboard
description: "Storyboard und Szenenplan einer Motion-Studio-Folge: Bildwelt und Motiv, Szenen auf den Wortzeiten schneiden, eine Aktion pro Aussage genau auf dem Wort, Wow-Moment pro Szene, Art je Szene (2d, 3d-web, blender), STORYBOARD.md und build/scenes.json, plus die Brief-Vorlage, mit der die Regie mehrere motion-bauer parallel beauftragt. Laden bei \"Storyboard\", \"Szenen planen\", \"scenes.json\", \"Szenen aufteilen\", \"Brief an den Bauer\", \"Bauer starten\"."
---

# motion-storyboard

Eingang: `SKRIPT.md`, `voice/woerter.json` und `voice/timing.txt` (aus `ms woerter`), Kanal-Dateien `kanaele/<k>/BIBEL.md`, `REGELN.md`, falls vorhanden (beim Pilot: die [R]-Regeln aus BIBEL.md), `kit/KATALOG.md`.
Ausgang: `STORYBOARD.md`, `build/scenes.json`, je Bauer ein Brief. Danach `__HEIM__/ms status <folge> storyboard --notiz "<n> Szenen, <x> % 3D"`.

## 1. Bildwelt (eine Idee, die sich durchzieht)
- Eine Welt (Werkstatt, Bühne, Schreibtisch, Stadt …) und ein wiederkehrendes **Motiv**, das das Thema greifbar macht (ein Stempel, farbige Karten, ein Zähler). Das Motiv taucht in Hook, Mitte und Schluss auf.
- Look, Farben, Schrift, Kamera-Stil kommen aus der BIBEL ([R]-Regeln zuerst). Farben pro Element festlegen und in jedem Brief identisch übergeben.
- Formatwechsel: nicht zweimal hintereinander dieselbe Bildidee wie die letzte Folge.

## 2. Szenen schneiden
- Normale Folge: Grenze = Wortzeit des ersten Worts der neuen Aussage − 0,06 s. Die nächste Szene startet dort, die vorige endet 0,06 s später (Überlappung). Rechnen: `start_neu = wort_s − 0.06`, `dur_alt = start_neu + 0.06 − start_alt`.
- Pilot (Nachbau): Grenzen = Schnitte des Originals aus der Analyse, eine Szene pro Shot, gleiche Zeiten. Läuft der Pilot über einen Ausschnitt (`ms stimme --original --von <s>`): Start im Pilot = Start im Original − von.
- Erste Szene startet bei 0. Letzte endet genau bei der Gesamtdauer = Länge von `voice/stimme.wav` + Auslauf (Standard 0,47 s, anders mit `ms szenen --auslauf <s>`; `ms szenen --check --plan` rechnet und meldet, `ms render` übernimmt den Auslauf aus index.html).
- Länge 1,5 bis 8 s, Schnittrhythmus aus der BIBEL hat Vorrang. Lange Aufzählungen: Art abwechseln.
- **Art je Szene** nach BIBEL: `2d` (Typo, Collage, UI, Diagramm), `3d-web` (Three.js, Toon oder PBR), `blender` (nur wenn die BIBEL Blender-Niveau verlangt und `ms blender check` ok ist; Render kostet Minuten pro Sekunde).
- **Tracks:** höhere Zahl liegt oben. Üblich: 3D abwechselnd 1 und 2, 2D 3 (liegt beim Überlapp über 3D). Captions 10 und Ton 20 setzt `ms szenen` selbst.

## 3. Was in jeder Szene passiert
- **Eine Aktion pro Aussage, genau auf dem Wort.** Zeit aus `voice/timing.txt`. Jede Aktion 0,3 bis 0,4 s lesbar, die nächste erst danach.
- **Lokale Zeit** = global − Szenenstart. Im Storyboard immer beides: „Stempel auf ‚Rekord‘ 12,42 global = 1,10 lokal“.
- **Ein Wow-Moment pro Szene** (KATALOG-Rezepte: Kamera-Punch, Treffer-Blitz mit Bloom, Licht-Dramatik, Konfetti, Glanz-Wisch, Zählwerk, Portal). Er stützt die Aussage, er ersetzt sie nicht.
- **Kein Stillstand über 1,5 s:** dann Kamerafahrt, neuer Effekt oder lebendiges Detail einplanen.
- **Hook (erste Szene):** ab Bild 1 Bewegung und das Hauptmotiv groß im Bild, eine klare Idee, nicht vier Dinge in zwei Sekunden.
- Übergänge: Standard Schnitt oder Wisch. Mindestens zwei echte Übergänge pro Folge (Portal in eine Fläche, Objekt fliegt in die Kamera, Herauszoomen aus einem Bildschirm). Beide Seiten im Brief vermerken.
- Alles Wichtige oberhalb der Caption-Zone (Caption-Stil `y` minus 125 px, Standard y 1345).

## 4. STORYBOARD.md
Eine Zeile pro Szene:

| Szene | Start bis Ende | Art | Gesagt (Wortlaut) | Kernaktion @ Wort (global / lokal) | Wow | Sound pro Aktion | Übergang raus | Bauer |
|---|---|---|---|---|---|---|---|---|

Darunter: Bildwelt, Motiv, Farbtabelle (Element: #hex), Schrift, Kamera-Stil.

## 5. build/scenes.json
```json
[{"id": "s1", "start": 0.0, "dur": 4.2, "track": 1, "art": "3d-web", "inhalt": "Würfel landet auf dem Sockel"},
 {"id": "s2", "start": 4.14, "dur": 3.1, "track": 3, "art": "2d", "inhalt": "Zähler bis 1.000, Stempel REKORD"}]
```
ids: Buchstabe zuerst, dann a-z 0-9 _ - (werden zu Dateinamen und CSS-ids). `inhalt` kurz, erscheint auf den Kontaktbögen.
Optional `"captions": false`: in dieser Szene keine Untertitel (Titelkarte, großer Text im Bild). Wörter, die dort beginnen, fallen weg, eine laufende Gruppe endet am Szenenstart. Captions ganz aus: `kit/captions.json` `"an": false`.
**Gate:** `__HEIM__/ms szenen <folge> --check --plan` zeigt „Prüfung: OK“ (keine Lücke, Ende = Gesamtdauer). Fehlende Kompositionen sind hier noch erlaubt.

## 6. Bauer-Gruppen und Briefe
- 2 bis 4 Szenen pro Bauer, möglichst gleiche Art (ein 3D-Bauer, ein bis zwei 2D-Bauer). Szenen mit gemeinsamem Übergang in dieselbe Gruppe.
- Jeder Bauer bekommt einen Namen: `bauer-1`, `bauer-2` … Der Name steht im Brief, in `fertig_<name>.json` und ist die Adresse für SendMessage.
- **Vor dem Start:** `__HEIM__/ms szenen <folge> --plan`. Das schreibt `build/index.html` und legt für jede Szene ohne Komposition einen neutralen Platzhalter an (richtige Dauer, `data-platzhalter="1"`). So laufen lint und `ms snap` der Bauer von Anfang an. „noch nicht gebaut“ ist hier nur ein Hinweis.
- **Start:** Starte alle Bauer in EINER Nachricht parallel über das Agent-Tool (subagent_type "motion-bauer", name "bauer-1", "bauer-2" …), je Bauer ein Brief.
- Brief-Vorlage (ausfüllen, nichts weglassen):

```
Du bist motion-bauer "<name>" für die Folge <folge-id>. Projekt: __ARBEIT__/folgen/<folge-id>/build/  Kanal: <k>
Szenen: <s2 (2d), s4 (3d-web)>
Grenzen: Du fasst NUR build/compositions/<s2,s4>.html an, dazu neu: build/fertig_<name>.json, build/sfx_<name>.json,
  snapshots/<name>_*/, bei Blender build/assets/video/<id>.mp4 und blender/<id>/. Nie index.html, scenes.json, captions,
  andere Szenen, build/assets/lib oder das Kit des Kanals. Nichts löschen. Fehlt ein Baustein: in der Szene selbst bauen.
  Deine Kompositionen liegen als Platzhalter da: mit Read öffnen, mit Write komplett ersetzen.
  Keine bezahlten Dienste, keine Downloads mit Konto, .env nie lesen. Bedarf in fertig_<name>.json unter "offen" anfordern.
Lies zuerst: kanaele/<k>/BIBEL.md, REGELN.md, falls vorhanden (beim Pilot: die [R]-Regeln aus BIBEL.md), kit/KATALOG.md,
  STORYBOARD.md (deine Zeilen), Skill je Art.
Bildwelt/Motiv: <…>   Farben: <Element: #hex, …>   Schrift: <…>   Kamera-Stil: <…>
Pro Szene:
  <id> · Start global <x> · Dauer <d> · Art <…> · Track <n>
  Gesagt: "<Wortlaut>"
  Wortzeiten LOKAL: <Wort 0,12 · Wort 0,48 · …>
  Bildidee: <…>
  Aktionen: <lokal 0,48 „Wort“: was passiert> · <…>
  Wow: <…>   Übergang rein: <…>   raus: <…>
[Pilot] Referenz: analyse/<video>/… Bilder je Szene. Ziel so nah wie möglich. Paarbilder mit
  __HEIM__/ms snap <folge-id> <zeiten> --gegen __ARBEIT__/folgen/<folge-id>/vorbild/ausschnitt.mp4 (gleiche Zeitachse).
[Pilot] Bewegungsliste deiner Szenen (aus NACHBAU.md bzw. der Analyse): <Zeit · Element · wie es auftaucht · Dauerbewegung · Details>
  Bewegung prüfst du mit Streifen: __HEIM__/ms snap <folge-id> <t> --streifen --gegen …/vorbild/ausschnitt.mp4
Fertig, wenn: __HEIM__/ms szenen <folge-id> --check --lint --nur <s2,s4> ohne Fehler, jede Szene im Raster angesehen und
  korrigiert, Kernaktionen auf dem Wort sichtbar. [Pilot] Jeder Eintrag der Bewegungsliste einmal als Streifen gegen das
  Original angesehen und angeglichen (wie es auftaucht, Dauerbewegung, Details).
Dann build/fertig_<name>.json und build/sfx_<name>.json schreiben (Format im Agent motion-bauer) und kurz berichten.
Live-Log: __HEIM__/ms log "<was gerade passiert>" --ziel <folge-id> --wer motion-bauer
Du arbeitest im Hintergrund, niemand beantwortet Fragen. Unklar: sinnvolle Annahme treffen, weiterbauen, die Annahme
  in fertig_<name>.json unter "offen" und im Bericht nennen.
Nach 3 Fehlversuchen an einer Szene: aufhören, mit Pfaden der Kontaktbögen, Versuchen und vermuteter Ursache melden.
```

## 7. Nach den Bauern
Bauer warten nie auf Antworten. Während sie arbeiten: `__HEIM__/ms log --zeige` und die schon vorhandenen `build/fertig_*.json` lesen, jede Annahme unter `"offen"` entscheiden, Korrekturen per SendMessage an den Namen (`bauer-1` …).
Warten, bis jede `build/fertig_<name>.json` da ist. Dann `__HEIM__/ms szenen <folge>` (Gate „Prüfung: OK“, also auch kein „noch nicht gebaut“ mehr), `__HEIM__/ms mix <folge> --vorschlaege` für den Ton (Skill motion-ton-mix), danach Skill motion-qa.

## Fallen
- Szenen ohne Überlappung (Start = Ende) ergeben ein Schwarzbild. Immer 0,06 s.
- Wortzeiten zur falschen Stimme (Stimme neu erzeugt, woerter.json alt): `ms woerter` nach jeder Stimm-Änderung neu.
- Zu viele Ideen im Hook. Eine Idee pro Moment.
