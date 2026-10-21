---
name: motion-stimme
description: "Stimme einer Motion-Studio-Folge erzeugen und vorbereiten: Anbieter laut PROFIL.md (ElevenLabs, Higgsfield, eigene Aufnahme), billiger Aussprache-Test vorab, Kostenansage, Whisper-Gegenprobe ≥ 95 %, Tempo-Fit auf die Vorlage, −14 LUFS, Wortzeiten und Caption-Gruppen (ms stimme, ms woerter). Laden bei \"Stimme\", \"Voiceover\", \"vertonen\", \"TTS\", \"ElevenLabs\", \"Aussprache\", \"Tempo anpassen\", \"Wortzeiten\", \"timing.txt\", Phase stimme."
---

# motion-stimme

Eingang: `voice/script.json` (Skill motion-skript), `__ARBEIT__/PROFIL.md` (Abschnitt Stimme: Anbieter, Stimm-ID, Modell, Einstellungen), `kanaele/<k>/AUSSPRACHE.json`.
Ausgang: `voice/stimme.wav` (fertig, −14 LUFS), `voice/woerter.json`, `voice/timing.txt`, `build/captions.json`.
`<folge>` = Folgen-ID, z. B. `2026-10-20-thema`.

## 1. Anbieter wählen (aus PROFIL.md)
| Anbieter | Weg | Kosten |
|---|---|---|
| ElevenLabs | `ms stimme <folge> --elevenlabs --stimme <voice_id>` direkt über die API (Schlüssel `ELEVENLABS_API_KEY` in `__ARBEIT__/.env`) | 1 Credit pro Zeichen (Multilingual v2/v3), Flash/Turbo 0,5. Kommerziell ab Starter-Plan |
| Higgsfield | im Agenten über den Higgsfield-MCP (Audio-Erzeugung, TTS-Modelle wie ElevenLabs v4), Datei laden, dann `ms stimme <folge> --datei <datei>` | Credits laut Higgsfield, vorher anzeigen lassen |
| Eigene Aufnahme | Nutzer nimmt den Text auf (ruhiger Raum, Handy nah am Mund, WAV oder M4A), dann `ms stimme <folge> --datei <datei>` | gratis |

Steht nichts im PROFIL: den Nutzer fragen, nicht raten. Eine lokale Sprachsynthese gibt es im Paket nicht: was ein anderes Programm erzeugt, kommt wie eine eigene Aufnahme über `--datei`.
**Pilot (Phase B):** keine Stimme erzeugen. Der Pilot nimmt den Originalton: `ms stimme <pilot> --original [--von <s> --bis <s>]`, danach `ms woerter <pilot>`. `--tempo` bricht beim Pilot ab (Ablauf im Skill motion-kanal-lernen, Schritt 4).

## 2. Aussprache-Test (billig, vor dem großen Auftrag)
Nur nötig bei Namen, Marken, Fachwörtern und Abkürzungen, die neu sind (nicht schon in AUSSPRACHE.json).
- 2 bis 3 Schreibweisen in einem kurzen Satz testen, nicht das nackte Wort:
  `__HEIM__/ms stimme <folge> --probe "Der Server läuft mit Nginx." "Der Server läuft mit Engine-X." --elevenlabs --stimme <id>`
  Ohne `--ja` zeigt es die Kosten (meist unter 100 Credits). Nach Ja mit `--ja`. Whisper schreibt dazu, was es hört. Dateien liegen in `voice/proben/`.
- Der Nutzer hört die Proben an und wählt. Gewinner in `kanaele/<k>/AUSSPRACHE.json` eintragen (`{"Nginx": "Engine-X"}`). Ab dann setzt `ms stimme` die Schreibweise automatisch ein.
- Higgsfield: Proben im Agenten erzeugen und den Nutzer anhören lassen. Nicht mit `--datei` prüfen, das ersetzt den Roh-Take.

## 3. Stimme erzeugen
**ElevenLabs:**
```
__HEIM__/ms stimme <folge> --elevenlabs --stimme <voice_id> [--modell eleven_multilingual_v2] [--stabilitaet 0.4]
```
Zeigt Zeichen, Credits und ungefähre Dollar je Plan. Betrag dem Nutzer nennen, Ja holen, dann derselbe Befehl mit `--ja`.
Gleicher Text mit gleicher Stimme und gleichen Einstellungen wird nicht neu bezahlt (`voice/jobs.json`). Die Kosten trägt das Werkzeug selbst in STATUS ein.
**Higgsfield:** `__HEIM__/ms stimme <folge> --higgsfield` gibt den fertigen Sprechtext (mit Aussprache-Liste) und die Zeichenzahl aus. Kosten im MCP prüfen, Ja holen, erzeugen, herunterladen, `ms stimme <folge> --datei <datei>`, Kosten eintragen: `ms status <folge> --kosten <betrag> Credits "Higgsfield Stimme"`.
**Eigene Aufnahme:** `__HEIM__/ms stimme <folge> --datei <aufnahme>`.

Jede Übernahme macht automatisch die **Whisper-Gegenprobe** (`voice/roh_check.txt`): Anteil der erkannten Wörter.
- **Ziel ≥ 95 %.** Zahlen als Ziffern und Getrennt- oder Zusammenschreibung sind harmlos.
- Darunter: die genannten Stellen in `script.json` umformulieren oder anders schreiben (Homophone, Namen), neu erzeugen. Kostet erneut: Betrag nennen, Ja holen.
- Ersetzte Takes landen in `voice/_ueberholt/`, nichts wird gelöscht.

## 4. Tempo anpassen
```
__HEIM__/ms stimme <folge> --tempo                # Ziel-Tempo der Vorlage (Wörter pro Sekunde aus dem Transkript)
__HEIM__/ms stimme <folge> --tempo --wps 4.2      # festes Ziel
__HEIM__/ms stimme <folge> --tempo --faktor 1.0   # nur Pausen kürzen und Lautheit
```
Kürzt Pausen ab 0,12 s auf 0,06 s, streckt mit rubberband (Tonhöhe und Klang bleiben; ohne rubberband nimmt es ffmpeg atempo, etwas rauer), bringt alles auf −14 LUFS.
Faktor lesen:
- KI-Stimmen sprechen langsam: 1,2 bis 1,6 ist normal.
- Über 1,6 klingt es gequetscht: Skript kürzen (Füllwörter, nicht Aussagen), neu erzeugen.
- Unter 0,85 wird gedehnt und klingt zäh: Skript ergänzen oder `--pausen-lassen`.
- Eigene Aufnahme: meist 1,0 bis 1,25.
Pausen-Kürzung zerstört manchmal Plosive am Wortende (t, k, p). Klingt ein Wort abgeschnitten: `--pause 0.09` oder `--pausen-lassen`.

## 5. Wortzeiten und Captions
```
__HEIM__/ms woerter <folge>
```
Whisper hört `stimme.wav` wortgenau, jedes Wort aus `display` bekommt Start und Ende (`voice/woerter.json`). Dazu `voice/timing.txt` (jede Satzzeile als `wort@sekunde`, Grundlage fürs Storyboard) und `build/captions.json` (Gruppen nach dem Caption-Stil des Kanals: höchstens 3 Wörter und 18 Zeichen, Bruch an Satzzeichen und Pausen, Reste ausgeglichen).
- **Ziel ≥ 85 % zugeordnet.** Darunter `voice/woerter_check.txt` lesen: meist steht in display ein anderes Wort oder ein Satz fehlt in tts. display korrigieren, `ms woerter` neu.
- Nach jeder Änderung an der Stimme `ms woerter` neu ausführen, sonst laufen Captions und Aktionen neben der Stimme.

## Gate
1. Gegenprobe ≥ 95 % (`voice/roh_check.txt`).
2. Tempo-Faktor im Rahmen, Lautheit −14 LUFS ±0,5 (Ausgabe von `--tempo`, Werte in `voice/stimme.json`).
3. `ms woerter`: ≥ 85 % zugeordnet, timing.txt lesbar, Stimm-Ende plausibel (Wörter geteilt durch Ziel-Tempo, ±1 s).
4. Stichprobe: drei Wortzeiten aus timing.txt gegen die Whisper-Ausgabe in `woerter_check.txt` prüfen.
5. Kosten stehen in STATUS (ElevenLabs automatisch, Higgsfield mit `ms status … --kosten`).
6. `__HEIM__/ms status <folge> stimme --notiz "<Dauer> s, Faktor <x>, <Anbieter>"`.

## Fallen
- `ELEVENLABS_API_KEY` nie in den Chat oder in Dateien außer `__ARBEIT__/.env`. Fehlt er, das Setup (Skill motion-setup) machen lassen.
- Fehler 401: Schlüssel falsch. 402: Plan oder Guthaben reicht nicht. 404: voice_id falsch. Keine Datei = keine Kosten.
- Text über 9.500 Zeichen: Skript teilen (zwei Aufträge, dann die Dateien mit ffmpeg aneinanderhängen, `--datei`).
