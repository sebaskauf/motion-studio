# Motion-Studio: Architektur (Vertrag für alle Teile)

Motion-Studio ist ein Agenten-Team für Claude Code. Es schaut sich einen Motion-Design-Kanal an, zerlegt ihn,
baut ein Video daraus fast 1:1 nach (gemessen), macht daraus einen Baukasten und produziert dann laufend eigene
Folgen in diesem Stil. Alles läuft lokal. Installation mit einem Prompt (SETUP-PROMPT.md).

## 1. Ablauf für den Nutzer

| Phase | Wie oft | Wer | Ergebnis |
|---|---|---|---|
| A Einrichten | einmal | motion-regie + Skill motion-setup | Programme installiert und geprüft, PROFIL.md, Sound-Bibliothek |
| B Kanal lernen | einmal pro Vorbild | motion-regie → motion-analyse → motion-bauer → motion-pruefer | BIBEL.md, Pilot-Nachbau mit Messwerten, Kit + REGELN.md + SKRIPT-BAUKASTEN.md |
| C Produzieren | laufend | motion-regie → motion-bauer (parallel) → motion-pruefer | Folgen im gelernten Stil, geprüft, Upload-Paket |

## 2. Agenten (vier)

| Agent | Rolle | Baut? |
|---|---|---|
| `motion-regie` | Einstieg und Hauptsitzung (`claude --agent motion-regie`), führt durch A/B/C, schreibt Skript/Storyboard/Ton, startet die anderen, pflegt STATUS. Nach 3 Fehlversuchen an derselben Szene: Mensch fragen | ja |
| `motion-analyse` | zerlegt Vorbild-Videos, bestimmt Typ, sagt Machbarkeit an, schreibt BIBEL.md. Viel Bildmaterial, deshalb eigener Kontext | nein |
| `motion-bauer` | baut die Szenen aus einem Brief: lädt je nach Szene motion-szene-2d, motion-szene-3d-web oder motion-szene-blender. Die Regie startet mehrere parallel in einer Nachricht (name `bauer-1`, `bauer-2` …, eine Szenengruppe pro Bauer). Nach 3 Fehlversuchen an einer Szene: aufhören und mit Bildern melden | ja |
| `motion-pruefer` | prüft und misst unabhängig, ohne Bau-Kontext. Befunde mit Zeitstempel, Schwere, Vorschlag | nein |

Nur die Hauptsitzung kann Agenten starten, deshalb startet der Nutzer Claude Code immer mit `claude --agent motion-regie` (die Dashboard-Knöpfe auch).
Rückkanal: Bauer laufen im Hintergrund und warten nie auf Antworten. Unklares lösen sie mit einer Annahme und melden sie in
`build/fertig_<name>.json` unter `"offen"`. Die Regie liest beim Warten `ms log --zeige` und die `fertig_*.json` und korrigiert per SendMessage an den Namen.

Warum nicht je ein Agent für 2D und 3D: Agenten trennen Kontext und laufen parallel, das Fachwissen steckt in Skills.
Ein Bauer, der den passenden Skill lädt, deckt beides ab und kann für 2D und 3D gleichzeitig mehrfach laufen.

## 3. Skills (alle mit Präfix `motion-`, damit nichts beim Nutzer kollidiert)

| Gruppe | Skill | Inhalt |
|---|---|---|
| Einrichten | `motion-setup` | großes Setup: Programme je Betriebssystem in Stufen (Basis, Analyse, 3D-Web, Blender, Sound, optional KI), Prüfung `ms check`, Interview → PROFIL.md, Schlüssel in `.env` |
| | `motion-sound-bibliothek` | Anleitung mit Links (referenz/SOUND-QUELLEN.md), Laden, Einlesen, Katalog, Abhörseite, Familien, Sperrliste |
| Ablauf | `motion-kanal-lernen` | Phase B Schritt für Schritt mit Gates |
| | `motion-folge` | Phase C Schritt für Schritt mit Gates, Upload-Paket |
| Finden | `motion-vorlagen-finden` | Register, YouTube/TikTok gratis per yt-dlp, Apify nur mit Kostenansage und Ja, Ausreißer-Filter |
| Zerlegen | `motion-video-zerlegen` | Schnitte, Kontaktbögen, Palette, Bewegung/Kamera, Text (OCR), Typ-Bestimmung |
| | `motion-ton-zerlegen` | Transkript, Sprechtempo, Lautheit, Effekt-Momente, Musik ja/nein |
| | `motion-skript-zerlegen` | Baukasten (Hook, Re-Hook, Beleg, Nutzen, CTA), Hook-Formeln, Länge, Themen |
| | `motion-bibel` | Format BIBEL.md mit [B] beobachtet / [P] vermutet / [R] Regel |
| Bauen | `motion-skript` | Vorlage → eigenes Skript in Kanalsprache, Sprechtext/Anzeigetext, Aussprache |
| | `motion-stimme` | TTS (ElevenLabs, Higgsfield, eigene Aufnahme), Tempo-Fit, Wortzeiten, Caption-Gruppen |
| | `motion-storyboard` | Szenen auf Wortzeiten, eine Aktion pro Aussage, Wow-Moment, Sound pro Szene, scenes.json |
| | `motion-szene-2d` | HyperFrames + GSAP (Collage, Typo, UI, Diagramme, Lottie), seek-sicher, Snapshots |
| | `motion-szene-3d-web` | Three.js in HyperFrames, Kamera-Mathe, Toon/PBR, seek-sicher, Snapshots |
| | `motion-szene-blender` | Blender headless (bpy), EEVEE, Assets (Poly Haven …), Figuren (Bibliothek, Tripo, Mixamo), Clip in HyperFrames einbetten |
| | `motion-ton-mix` | Ereignisse aus der Bibliothek, Familien reihum, Pegel unter der Stimme, −14 LUFS |
| | `motion-qa` | Vollrender, Schwarzbild-Scan, Kontaktbögen ansehen, Lautheit, Ausschlussfehler |
| Prüfen | `motion-vergleich` | Original gegen Nachbau: ΔE/SSIM pro Szene, Paarbögen, Nebeneinander-Video |
| Lernen | `motion-kanal-kit` | aus dem Pilot wiederverwendbare Bausteine, KATALOG.md, REGELN.md, Ton-Rezept |

Mitinstalliert (öffentlich, von HeyGen): HyperFrames-Skills über `npx hyperframes skills`.

## 4. Dateien beim Nutzer

```
~/.claude/agents/motion-*.md                 4 Agenten
~/.claude/skills/motion-*/SKILL.md           Skills (+ eigene Unterordner)
~/.claude/motion-studio/   = HEIM            aus studio/ dieses Repos
  ms                       Einstieg für alle Werkzeuge: ms <werkzeug> [args], ms hilfe
  tools/                   Python-Werkzeuge (tools/_ms.py = gemeinsame Bibliothek)
  dashboard/               server.py + index.html (127.0.0.1)
  blender/                 msblend.py (Hilfen in Blender), Beispielszene
  vorlagen/                Startdateien (PROFIL-START.md, LERNLOG-START.md, BIBEL-VORLAGE.md …)
  referenz/                Wissen (SOUND-QUELLEN.md, BLENDER.md, …)
  config.json              {"arbeitsordner": "~/MotionStudio", …}  (vom Setup geschrieben)
  .venv/                   Python-Umgebung des Studios
~/MotionStudio/  = ARBEIT  gehört dem Nutzer, wird bei Updates nie überschrieben
  PROFIL.md  LERNLOG.md  .env (Schlüssel, nie ausgeben)  .claude/settings.json (erlaubte Befehle, Read auf CFG/skills/**)
  kanaele/<slug>/          STATUS.json BIBEL.md REGELN.md SKRIPT-BAUKASTEN.md AUSSPRACHE.json vorbild/ analyse/<video-id>/
                           kit/{lib,fonts,tex,beispiele} kit/KATALOG.md kit/ton-rezept.json kit/captions.json (Caption-Stil)
  folgen/<JJJJ-MM-TT>-<slug>/  STATUS.json SKRIPT.md STORYBOARD.md voice/ build/ (HyperFrames-Projekt) out/ snapshots/
                           blender/<sid>/ (Blender-Szenen: szene.py, Bilder, render.log) PRUEFBERICHT.md HANDOFF.md CAPTION.md upload/
                           Pilot zusätzlich: vorbild/ausschnitt.mp4 (Original im Pilot-Fenster) VERSUCHE.md (Messversuche, motion-vergleich)
  vorlagen/register.json  vorlagen/videos/<id>.mp4  vorlagen/transkripte/<id>.json
  sounds/files/<quelle>/…  sounds/katalog.json
  assets/<quelle>/<typ>/<id>/  3D-Assets mit lizenz.json (ms assets, Blender-Spur)
  live/events.jsonl        Live-Log fürs Dashboard
```

Platzhalter in Agent- und Skill-Dateien, ersetzt von install.sh: `__HEIM__` (absoluter Pfad HEIM), `__ARBEIT__` (absoluter Pfad ARBEIT).
In Skills und Agenten immer `__HEIM__/ms <werkzeug>` schreiben, nie `python3 …/tools/x.py`.

## 5. Status-Vertrag (Dashboard liest nur diese Dateien)

`folgen/<id>/STATUS.json`:
```json
{"id": "2026-10-20-slug", "art": "folge|pilot", "titel": "…", "kanal": "slug",
 "vorlage": {"id": "…", "url": "…", "creator": "…", "views": 0},
 "phase": "szenen", "phasen": {"skript": {"zeit": "ISO", "notiz": "…"}},
 "kosten": [{"zeit": "ISO", "betrag": 0.42, "einheit": "USD|EUR|Credits", "was": "…"}],
 "video": "out/x.mp4", "vorschau": "out/x.jpg", "wartet_auf": "Frage an den Nutzer", "fehler": "…",
 "geplant": "ISO", "gepostet": {"zeit": "ISO", "link": "…", "plattform": "instagram"},
 "messwerte": {"delta_e": 5.2, "ssim": 0.84}, "erstellt": "ISO", "aktualisiert": "ISO"}
```
Folgen-Phasen (Reihenfolge): `vorlage skript stimme storyboard szenen ton render vergleich pruefung fertig geplant gepostet`
(`vergleich` nur beim Pilot). Dashboard-Spalten: Vorlage | Skript | Stimme | Szenen (storyboard, szenen, ton) | Render (render, vergleich) | Prüfung | Fertig | Geplant | Gepostet.
`kanaele/<slug>/STATUS.json`: `art: "kanal"`, Phasen `vorbild zerlegt bibel pilot gemessen kit bereit`, Felder `vorbild`, `pilot` (Ordner der Pilot-Folge), `messwerte`.

Setzen nur über `ms status <ziel> <phase> --notiz "…"` (plus Felder, siehe `ms status --help`) bzw. `_ms.status_setzen()`.
Live-Log: `ms log "<was gerade passiert>" --ziel <ziel> [--art info|warnung|fehler|frage|kosten]` bzw. `_ms.log()`.
Eine Zeile in `live/events.jsonl`: `{"zeit", "wer", "ziel", "art", "text"}`. Agenten setzen `MS_AGENT` nicht selbst, sie geben `--wer` an.
Wartet ein Agent auf eine Antwort des Nutzers: `ms status <ziel> --wartet "<Frage>"`, nach der Antwort `--wartet-weg`.

**Eigene Pipelines per `--adapter`:** `ms dashboard --adapter <datei.py>` zeigt statt des Arbeitsordners eine fremde Pipeline
(Beispiel: `reel-studio/tools/studio_adapter.py`). Die Datei wird als Modul geladen (ohne `__pycache__` im fremden Repo) und darf liefern:
`TITEL` (Kopfzeile), `stand() -> dict` (Schema wie `/api/stand`: `folgen` mit Phasen wie oben, `sitzungen`, `log`; Pfade `ordner`,
`video`, `vorschau` absolut, der Server rechnet sie in `/datei`-Pfade um; dazu `aktionen` = feste Knöpfe
`[{art, label, hinweis, bestaetigen?, primaer?, gefahr?}]`, `kennzahlen` = `[{label, wert, hinweis, art?}]`, je Folge optional
`trial`, `zwilling_von`, `hinweis`, `geplant` (ISO mit Uhrzeit), `infos` (Detail-Tabelle), oben `bild_format: "hoch"`),
`datei_wurzeln() -> list[Path]` (nur darin liefert `/datei`, Pfad `<n>/<relativ>`), `auftrag(art, params)` (nur Arten aus `aktionen`),
`sitzung(name, was)` für weiter/oeffnen/stopp (eigener Präfix, `starten.liste(muster)` hilft), optional `folge_gepostet`,
`folge_geplant`, `ordner_oeffnen` (fehlen sie, blendet die Seite die Knöpfe aus). Host-, Origin- und Token-Prüfung gelten unverändert
für alle Adapter-Aktionen. Ohne `--adapter` bleibt alles wie oben.
Optional für die Seite (DESIGN.md, Kern-Loop): `sendeplan` = `{heute: [...], morgen: [...]}`, je Slot `{slot, zeit, art: post|trial,
zustand: gepostet|geplant|faellt_aus|vorbei, folge_id, titel, vorschau (absolut, der Server macht daraus _vorschau), link, trial, grund, zu}`
(`zu` = Slot des Originals bei Trial-Zwillingen); `autopilot` = `{aktiv, bauen, puffer, vorrat, naechster: {zeit, titel, folge_id}}` für die
Kopfzeile; `hinweise` = JETZT-Zeilen `[{art, tag, text, knopf: {label, aktion: auftrag|detail|dialog|los, art?, folge?}}]` in Klartext.
Hängende oder wartende Sitzungen ergänzt die Seite selbst. Ohne Adapter leitet der Server `sendeplan` aus `geplant`/`gepostet` der Folgen ab.
Server-Routen zusätzlich: `/fonts/<datei>.woff2` (nur aus `dashboard/fonts/`), `POST /api/neustart` (Token; der Prozess ersetzt sich per
`os.execv` mit denselben Argumenten, die Seite lädt danach neu). `/api/stand` liefert `server_id` (neu je Start).

## 6. Werkzeuge (`ms <name>` = `studio/tools/<name>.py`)

Regeln für jedes Werkzeug:
- Kopf-Docstring: erste Zeile = Kurzbeschreibung (erscheint in `ms hilfe`), danach alle Aufrufe mit Beispielen. `--help` funktioniert.
- `import _ms` für Pfade, Status, Log, probe/frames/frame_bei/kontaktbogen/wav_aus/lufs/transkribiere, json_lesen/json_schreiben, env, befehl.
  `_ms.py` NICHT ändern. Fehlt etwas Allgemeines, eigenes Modul `_<bereich>.py` anlegen und im Abschlussbericht nennen.
- Python 3.9-kompatibel (`from __future__ import annotations`), Mac/Windows/Linux. Pfade mit pathlib. Keine Pfade eines bestimmten Rechners.
- **Nie ein ganzes Video roh in den RAM laden.** Frames nur über `_ms.frames()` (streamt) oder `_ms.frame_bei()`.
- Schwere Pakete (torch, transformers, librosa, scikit-image …) nur lazy importieren und mit verständlicher Meldung ausfallen, wenn sie fehlen.
- Fehler als `raise SystemExit("FEHLER: … was tun")`, keine Tracebacks für erwartbare Fehler.
- Ausgabe knapp und deutsch, Ergebnisse als Dateien (JSON + lesbares .md/.jpg), Pfade am Ende ausgeben.
- Kosten verursachende Aufrufe (Apify, ElevenLabs, Tripo …): erst Schätzung ausgeben, ausführen nur mit `--ja`. Schlüssel nur über `_ms.env()`, nie ausgeben.

Belegte Namen (Besitzer in Klammern): `status log neu` (Kern) · `check setup` (Setup) · `vorlagen laden transkript zerlegen ton_zerlegen` (Analyse) ·
`szenen snap render vergleich kit` (Bau/Prüfung) · `blender assets` (Blender) · `stimme woerter sound mix` (Ton) · `dashboard` = `dashboard/server.py`, `starten` (Dashboard).

## 7. HyperFrames-Projekt einer Folge (`folgen/<id>/build/`)

- `scenes.json`: `[{"id": "s1", "start": 0.0, "dur": 4.2, "track": 1, "art": "2d|3d-web|blender", "inhalt": "…"}]`, Szenen überlappen 0,06 s.
  Optional je Szene `"captions": false` (keine Untertitel in dieser Szene).
- `compositions/<id>.html`: eine Komposition pro Szene (Format nach den HyperFrames-Skills, `data-composition-id`, `data-duration`).
  Blender-Szenen: Komposition mit `<video src="assets/video/<id>.mp4">`, darüber optional 2D-Ebenen.
- `ms szenen <folge>` schreibt `index.html` (alle Szenen, Captions im Kanal-Stil, Stimme + Mix), legt für fehlende Kompositionen
  neutrale Platzhalter an (`data-platzhalter="1"`, richtige Dauer, nie über eine vorhandene Datei) und prüft Lücken/Dauern.
  Die Regie ruft es vor dem Start der Bauer mit `--plan` auf. `--check` meldet Platzhalter als „noch nicht gebaut“, `--check --plan` nicht.
  Gesamtdauer = Länge `voice/stimme.wav` + Auslauf (Standard 0,47 s, `--auslauf`). Der Auslauf steht als `<!-- ms-auslauf X -->` in
  index.html, `ms szenen --check` und `ms render` übernehmen ihn. Captions werden am Ende gekappt.
  `build/captions.json` (Gruppen, schreibt `ms woerter`): Gruppen mit `"hand": true` überschreibt `ms woerter` nicht.
- Pilot: `ms stimme <pilot> --original [--von --bis]` nimmt den Originalton (Zeitachse unverändert) und schreibt `vorbild/ausschnitt.mp4`.
- `ms render <folge> <name>` → `out/<name>.mp4` + `out/qa_<name>/*.jpg` + Schwarzbild-Scan + LUFS.
- Ton: `voice/` (Stimme, Wortzeiten `voice/woerter.json`, `voice/timing.txt`), `build/assets/audio/` (Mix, Ereignisse).

## 8. Sicherheit und Kosten (gilt für Agenten und Werkzeuge)

- Nie posten ohne ausdrücklichen Auftrag des Nutzers. Posten ist Stufe 2 (noch nicht im Paket): das Upload-Paket liegt in `folgen/<id>/upload/`.
- Apify und alle bezahlten APIs: vorher Kosten schätzen, Nutzer fragen, erst nach Ja ausführen.
- Nie löschen ohne Ja. Ersetztes nach `_ueberholt/` verschieben.
- Keine Zugangsdaten in Dateien außer `ARBEIT/.env`. Werte nie ausgeben.
- Keine Cookies aus dem Browser des Nutzers lesen (kein `--cookies-from-browser`).
- Fremde Videos nur zur Analyse; veröffentlicht wird nur eigener Inhalt.
- Dashboard: nur 127.0.0.1, Knöpfe starten nur feste Aufträge, POST nur mit Sitzungs-Token.
