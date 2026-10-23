---
name: motion-setup
description: "Großes Setup von Motion-Studio in Stufen (Basis, Analyse, 3D-Web, Blender, Sound, KI) für Mac, Windows und Linux: prüfen, nach Ja installieren, erneut prüfen. Danach Interview, eine Frage nach der anderen, das PROFIL.md füllt. Laden, wenn ms check bei basis FEHLT meldet, beim ersten Start, oder bei \"richte Motion-Studio ein\", \"Setup\", \"installier\", \"Programme fehlen\", \"Profil anpassen\", \"Schlüssel eintragen\", \"Blender einrichten\", \"Whisper-Modell\"."
---

# motion-setup

Ziel: Am Ende zeigt `__HEIM__/ms check --stufe alle` bei `basis` „ok“, PROFIL.md steht auf `setup: fertig`, und der Nutzer weiß,
welche optionalen Stufen er hat und welche nicht. Systemdetails (Homebrew, winget, Pfade, Fallen): `OS-DETAILS.md` in diesem Ordner.

## Grundsätze
- **Prüfen, dann nach Ja installieren, dann wieder prüfen.** Nichts installieren ohne Ja. Nichts als erledigt melden, was `ms check` nicht bestätigt.
- Eine Frage nach der anderen. Was du selbst prüfen kannst, prüfst du, statt zu fragen.
- Schlägt etwas fehl: genaue Fehlermeldung zeigen, Ursache nennen, nächsten Versuch vorschlagen. Nicht überspringen.
- Befehle, die ein Passwort brauchen (Homebrew-Installer, `sudo`), kann Claude Code nicht eintippen. Gib dem Nutzer die Zeile für sein eigenes Terminal und warte, bis er „fertig“ sagt.
- Kosten: Das Setup selbst ist gratis. Bezahlte Dienste (Apify, ElevenLabs, Tripo, Higgsfield) nur erklären und nach Wunsch des Nutzers verbinden.
- Live-Log: `__HEIM__/ms log "Setup: <Stufe> <Ergebnis>" --wer motion-regie`.

## 0. Stand zeigen
`__HEIM__/ms check --stufe alle` ausführen und dem Nutzer als kurze Tabelle zeigen: Stufe, ok/fehlt, was fehlt. Dann die Reihenfolge vorschlagen: Basis, Profil, Sound, danach nur, was er braucht.

## Stufe 1: Basis (Pflicht)
ffmpeg, Python 3.9+, Node.js 22+, HyperFrames + HyperFrames-Skills + Chrome für HyperFrames, yt-dlp, Transkription (whisper-cli mit Modell oder faster-whisper), git.
1. `__HEIM__/ms setup programme --stufe basis` zeigt, was fehlt und welche Befehle laufen würden. Dem Nutzer zeigen, Ja holen.
2. `__HEIM__/ms setup programme --stufe basis --ja`. Mac ohne Homebrew: das Werkzeug zeigt die Installer-Zeile, der Nutzer führt sie selbst im Programm Terminal aus. Windows: nach winget Claude Code neu starten (PATH).
3. `__HEIM__/ms setup venv` (Python-Umgebung des Studios mit numpy, pillow und scipy, auf dem Mac dazu pyobjc-framework-Vision und -Quartz für die Texterkennung; Liste in `__HEIM__/requirements.txt`; gratis, 1 bis 3 Minuten).
4. Transkription: Mac `brew install whisper-cpp` (falls nicht schon in Schritt 2) und `__HEIM__/ms setup whisper-modell turbo` (zeigt Größe: 1,62 GB; schwächerer Rechner: `small` 0,49 GB; Mittelweg `turbo-q5` 0,57 GB), nach Ja mit `--ja`. Windows und Linux: `__HEIM__/ms setup venv --whisper` (faster-whisper, lädt sein Modell beim ersten Lauf).
5. `__HEIM__/ms setup hyperframes-skills` zeigt den Stand, nach Ja `--ja`. Installiert die öffentlichen HyperFrames- und GSAP-Skills von HeyGen.
6. **Gate:** `__HEIM__/ms check --stufe basis` zeigt nur noch PROFIL.md als offen (oder gar nichts).

## Stufe 2: Profil (Pflicht, Interview)
Fragen einzeln stellen, Antwort sofort in `__ARBEIT__/PROFIL.md` eintragen (Kopf bleibt `setup: unvollständig`, bis alles steht). Vorschläge machen, wo der Nutzer unsicher ist.
**Hier nur das Technische und das Geld.** Nicht nach Kanal, Nische oder Vorbild fragen (Sebastian 23.10.: „Was macht dein Kanal?“ ist die falsche erste Frage). Das kommt erst nach dem Setup, als Start der Produktion mit drei Kernfragen: Short-Form oder lange YouTube-Videos, welcher Stil von welchem Account, welche Arten von Videos (Skill motion-format-finden). Die Felder Nische, Vorbild-Kanäle und Eigener Twist bleiben bis dahin leer.
1. System: selbst aus `ms check` übernehmen (Mac mit Apple Silicon/Intel, Windows, Linux). Nur bestätigen lassen.
2. Sprache der Videos.
3. Plattformen und Format (Standard 9:16, 20 bis 60 Sekunden).
4. Eigener Kanal: Handle(s), auf denen er postet oder posten will (leer lassen, wenn es noch keinen gibt).
5. Stimme: Anbieter ElevenLabs (kostet, beste Qualität), Higgsfield (wenn er es schon hat) oder eigene Aufnahme (gratis, oft am glaubwürdigsten, auch für Dateien aus anderen Programmen). Bei ElevenLabs: Stimm-ID (voice_id), Modell, Einstellungen, falls schon bekannt. Felder wie in PROFIL.md, Abschnitt Stimme (Skill motion-stimme liest sie).
6. Budget pro Monat und pro Folge, welche bezahlten Dienste erlaubt sind. Standard „Ohne Nachfrage frei bis: 0“, also jede Ausgabe vorher fragen.
7. Skript vor dem Bau zeigen: ja/nein (Standard ja).
8. Rhythmus: Folgen pro Woche, Posting-Tage.
Am Ende `setup: fertig`, `erstellt` und `aktualisiert` mit Datum, Werkzeug-Zeile aus `ms check --kurz`. Das Profil einmal ganz zeigen und fragen, ob etwas fehlt.

## Stufe 3: Sound (für Phase C nötig)
Skill **motion-sound-bibliothek** laden und durchgehen. **Gate:** `__HEIM__/ms check --stufe sound` meldet „ok“.

## Stufe 4: Analyse (für Phase B)
Programme kommen aus der Basis. Optional: tesseract für Texterkennung im Bild (`__HEIM__/ms setup programme --stufe analyse`).
Apify nur, wenn der Nutzer Instagram-Vorbilder hat: YouTube und TikTok gehen gratis über yt-dlp, Instagram meist nur über Apify (ein paar Cent pro Lauf, immer erst nach Kostenansage und Ja) oder indem er Videos selbst speichert. Konto auf apify.com, Token unter Settings, API & Integrations.

## Stufe 5: 3D-Web
Braucht nur die Basis (Three.js kommt mit dem Kit). **Gate:** `__HEIM__/ms check --stufe 3d-web` „ok“.

## Stufe 6: Blender (optional, Beta)
Ehrlich vorher sagen: Szene, Licht und Kamera klappen headless gut. Figuren mit Rig und Schauspiel auf dem Niveau großer Kanäle sind nicht belegt.
Rechenzeit (gemessen, Apple M3 Pro, Beispielszene 1080×1920): EEVEE 1,5 bis 1,9 s pro Bild, ein 20-s-Reel also 15 bis 19 Minuten. Cycles rund 2 h pro Reel, nur für Einzelshots. `__HEIM__/ms blender check` misst es auf deinem Rechner.
1. `__HEIM__/ms setup programme --stufe blender` (Mac: `brew install --cask blender`, Windows: winget `BlenderFoundation.Blender`, rund 0,9 GB), nach Ja `--ja`. Empfohlen ab 4.2.
2. `__HEIM__/ms blender check` misst Sekunden pro Bild auf diesem Rechner und rechnet ein 20-s-Reel hoch. Die Zahl dem Nutzer nennen und ins Profil (Zeile Blender) schreiben.
3. Optional Tripo für Figuren aus Text oder Bild (kostet pro Figur, Preis vor jeder Nutzung prüfen und nennen, `__HEIM__/ms assets kosten tripo`).
4. **Gate:** `__HEIM__/ms check --stufe blender` „ok“ und eine gemessene Zeit pro Bild.

## Stufe 7: KI-Pakete (optional)
Wofür: Sounds maschinell anhören und per Text suchen, Tiefe schätzen. Mac rund 1 GB, mit NVIDIA-CUDA 3 GB und mehr, Modelle laden beim ersten Lauf dazu. `__HEIM__/ms setup venv --ki` zeigt das, nach Ja `--ki --ja`.
**Gate:** `__HEIM__/ms check --stufe ki` „ok“.

## Schlüssel (nur auf Wunsch)
- Schlüssel stehen nur in `__ARBEIT__/.env`. Du liest diese Datei nie und zeigst nie einen Wert. Die Datei ist für Claude gesperrt, die Werkzeuge lesen sie selbst.
- Weg 1 (am besten): Datei für den Nutzer öffnen (Mac `open -e "__ARBEIT__/.env"`, Windows `notepad "__ARBEIT__/.env"`), er trägt `NAME=wert` selbst ein und speichert.
- Weg 2: Hat er den Wert schon in eine Datei kopiert: `__HEIM__/ms setup schluessel <NAME> < <datei>`. Danach die Datei löschen lassen (er selbst).
- Bekannte Namen: `APIFY_TOKEN`, `ELEVENLABS_API_KEY`, `FREESOUND_API_KEY`, `TRIPO_API_KEY`. Prüfen mit `__HEIM__/ms check` (zeigt nur gesetzt/fehlt).
- Higgsfield läuft nicht über einen Schlüssel, sondern als Connector: auf claude.ai unter Einstellungen, Connectors Higgsfield verbinden. Mit demselben Konto in Claude Code angemeldet, erscheinen die Higgsfield-Werkzeuge dort (prüfen mit `/mcp`). Kostet Credits, jede Nutzung vorher nennen.

## Abschluss
1. `__HEIM__/ms check --stufe alle` ausführen und als Beleg zeigen.
2. Kurze Übersicht: Basis ok, Profil fertig, Sound ja/nein, Blender ja/nein, KI ja/nein, verbundene Dienste (nur Namen).
3. Eine Zeile ins Lernlog: Datum, „Setup fertig“, System, offene optionale Stufen.
4. Hinweis: Claude Code einmal neu starten, falls Skills neu installiert wurden, und künftig immer im Arbeitsordner mit der Regie als Hauptsitzung starten: `cd "__ARBEIT__" && claude --agent motion-regie`. Dort gelten die erlaubten Befehle, und nur die Hauptsitzung kann Analyse, Bauer und Prüfer starten. Die Knöpfe im Dashboard starten genauso.
5. Nächster Schritt vorschlagen: „Lern den Kanal <Vorbild aus dem Profil>“ (Skill motion-kanal-lernen).

## Bekannte Fallen
- Homebrew-Python verbietet `pip install` ins System. Immer `ms setup venv`, nie `pip install --user`.
- Windows: Nach winget sind Programme erst in einem neuen Terminal im PATH. Git for Windows ist Pflicht, sonst hat Claude Code kein Bash.
- `npx hyperframes skills` schreibt auch nach `~/.agents/skills` (für andere KI-Werkzeuge). Das ist von HyperFrames so gewollt.
- Ein schon vorhandenes Whisper-Modell in `~/.cache/whisper-cpp/` wird automatisch gefunden. Kein zweites laden.
- Läuft `ms check` sehr lange: `npx` lädt beim ersten Mal HyperFrames. Danach dauert der Check 3 bis 5 Sekunden.
