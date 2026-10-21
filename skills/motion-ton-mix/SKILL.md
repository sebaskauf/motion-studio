---
name: motion-ton-mix
description: "Ton einer Motion-Studio-Folge: Ereignisliste aus der Sound-Bibliothek (jedes sichtbare Ereignis, das zählt, bekommt einen Sound), Hook-Sound auf Bild 1, margins unter der Stimme, Familien reihum statt fester Allzweck-Sounds, Musikbett, Mix auf −14 LUFS, Gegenprobe im fertigen Mix (ms mix, ms sound gegenprobe). Laden bei \"Ton\", \"Sound-Effekte\", \"SFX\", \"Mix\", \"Ereignisliste\", \"ereignisse.json\", \"Musik drunter\", \"zu laut\", \"zu leise\", Phase ton."
---

# motion-ton-mix

Eingang: `STORYBOARD.md` (Sound pro Szene), `voice/timing.txt`, `build/sfx_<bauer>.json` (Vorschläge der Bauer), `kanaele/<k>/kit/ton-rezept.json`, Katalog der Bibliothek (`ms sound …`).
Ausgang: `build/assets/audio/ereignisse.json`, `mix.wav`, `_sfx_bus.wav`, `mix_bericht.json`.
Voraussetzung: `ms szenen <folge>` ist einmal gelaufen (die Gesamtdauer kommt aus `build/index.html`).

## Regeln
- **Nur Sounds aus der Bibliothek.** Nie Sounds aus Code erzeugen.
- **Jedes sichtbare Ereignis, das zählt, bekommt einen Sound:** etwas erscheint, landet, schlägt ein, wechselt, wird grün oder rot, Zahl springt. Keine Mikrobewegungen vertonen.
- **Hook-Sound auf Bild 1:** ein Ereignis bei 0,0 s mit margin 0 bis 2. Der erste Treffer muss sofort hörbar sein.
- **margin = dB unter der Stimme** in der Umgebung (kleiner = lauter):
  Hook 0 bis 2 · Haupttreffer 4 bis 6 · Begleitung 7 bis 9 · Kleinkram 10 bis 12.
  Die Lautheits-Korrektur je Sound (`trim_db`) macht der Mix selbst. Nicht per margin ausgleichen.
- **Familien statt fester Allzweck-Sounds:** `@plopp` (erscheint), `@whoosh` (Bewegung, Wechsel), `@klick` (Klick, Fokus), `@landen` (dumpf landen) und was der Kanal sonst hat (`ms sound familie`). Der Mix wechselt reihum, nie zweimal dieselbe Variante hintereinander.
  Festen Sound nur, wenn Größe oder Charakter zählt, oder als **Motiv** (gleiche Aktion, immer derselbe Sound, wiedererkennbar).
- **Gleiche Bedeutung, gleiche Familie.** Nischen-Sounds (Glas zerspringt, Kasse klingelt) nur für genau ihre Sache.
- **Reihen:** gleiche Aktion schnell hintereinander (Liste baut sich auf) = gleicher Eintrag mit steigenden Halbtönen innerhalb 0,45 s: `[4.10, "@klick", 9, 0], [4.25, "@klick", 9, 2], [4.40, "@klick", 9, 4]`. Bleibt ein Sound, klingt wie eine Treppe.
- **Lange, rauschende oder schleifende Sounds in Sprechpausen** legen, sonst überdecken sie Silben. Unter Rede höchstens als Kleinkram (margin 10 bis 12).
- **Sub-Boom nur mit Mitten-Impact:** Handylautsprecher geben unter 150 Hz fast nichts wieder. Tiefer Boom immer zusammen mit einem Schlag zur selben Zeit.
- **Zeit = Moment des sichtbaren Treffers.** Der Mix legt den Anschlag des Sounds genau darauf. Bei Whooshes und Risern liegt der Anschlag am Anfang des Anschwellens: Zeit = Beginn der Bewegung.
- Kein Teppich: höchstens 6 Sounds in 0,5 s.

## Ablauf
**1. Vorschläge holen.**
```
__HEIM__/ms mix <folge> --vorschlaege
```
Liest `build/sfx_*.json` der Bauer und sucht zu jeder Beschreibung passende Sounds. Beschreibungen wie pop/appear, click/tick, thud/land/drop, whoosh/swoosh/swipe, paper/page werden zur Familie (`@plopp`, `@klick`, `@landen`, `@whoosh`, `@papier`), sofern es sie im Katalog gibt (Tabelle `FAMILIE_WOERTER` in `__HEIM__/tools/_ton.py`). Ergebnis: `build/assets/audio/ereignisse_vorschlag.md` (zum Lesen: gewählte Familie, sonst bis zu 3 Kandidaten je Stelle) und `ereignisse_vorschlag.json` (Entwurf, margin aus `margin_db` der Bauer, ohne Angabe 8). Gemischt wird dabei nichts.

**2. Ereignisliste schreiben** (`build/assets/audio/ereignisse.json`, du kuratierst, nichts blind übernehmen):
```json
[[0.0, "kenney/impact-punch-heavy-000", 1],
 [0.62, "@plopp", 8],
 [2.88, "@whoosh", 9],
 [4.10, "@klick", 9, 0], [4.25, "@klick", 9, 2], [4.40, "@klick", 9, 4],
 [6.13, "@landen", 6]]
```
Format: `[zeit_s, "sound-id" oder "@familie", margin_db, halbtoene (optional)]`, Zeiten global (ab Folgenbeginn) aus `voice/timing.txt` oder STORYBOARD.md.
Sounds finden: `__HEIM__/ms sound suche "<was>"`, `ms sound familie`, Kandidaten aus dem Vorschlag. Richtwerte zur Dichte und Lieblings-Sounds des Kanals stehen in `kit/ton-rezept.json`.

**3. Mischen.**
```
__HEIM__/ms mix <folge>                       # Musik laut ton-rezept, sonst ohne
__HEIM__/ms mix <folge> --musik <datei>       # Musikbett 20 dB unter der Stimme, duckt beim Sprechen
__HEIM__/ms mix <folge> --musik aus
```
Der Mix bricht ab bei unbekannten oder gesperrten Sounds und nennt Alternativen. Ausgabe lesen:
- `Gesamt … LUFS` Soll −14 ±0,5.
- `Effekte vs. Stimme`: Median ≤ −12 dB, Max ≤ −10 dB (das Sicherheitsnetz hält den Effekt-Bus hart 10 dB unter der Stimme, solange sie spricht).
- `Hook-Abstand` ≤ 4 dB (sonst margin des ersten Treffers auf 0 bis 1).
- `Netz griff in … %`: über 25 % heißt, die margins sind insgesamt zu klein. margins erhöhen, nicht das Netz arbeiten lassen. Wo das Netz greift, ändert ein kleinerer margin nichts.
- `PRÜFEN:` Zeilen (Teppich, fester Sound öfter als 3×, Nische doppelt, Sounds ohne Urteil, Sub-Boom allein, lange Sounds unter Rede) einzeln bewerten und beheben.

**4. Gegenprobe im fertigen Mix.**
```
__HEIM__/ms sound gegenprobe <folge>                    # die 10 wichtigsten Ereignisse
__HEIM__/ms sound gegenprobe <folge> 2.88:Whoosh 6.13:Landen --fenster 0.45
```
Die Maschine (AST) hört kurze Fenster des Effekt-Busses. Hört sie etwas völlig anderes als gemeint (Klebeband → Taube, Applaus → Sprache), Sound tauschen. Braucht die KI-Stufe. Ohne KI: Liste der Haupttreffer mit Zeit dem Nutzer zum Anhören geben.

**5. Einbauen.** `__HEIM__/ms szenen <folge>` erneut, damit `index.html` die Mischung statt der nackten Stimme nimmt. Ändert sich danach die Stimme oder die Gesamtdauer: `ms mix` neu.

## Gate
- −14 LUFS ±0,5, Effekte vs. Stimme Median ≤ −12 dB und Max ≤ −10 dB, Hook-Abstand ≤ 4 dB, Netz unter 25 %.
- Hook-Sound auf Bild 1, jede Kernaktion aus dem Storyboard hat einen Sound, gleiche Aktion gleiche Familie.
- Keine `PRÜFEN:`-Zeile offen ohne Begründung. Sounds „ohne Urteil“ dem Nutzer für die Abhörseite melden (Skill motion-sound-bibliothek).
- `__HEIM__/ms status <folge> ton --notiz "<n> Ereignisse, <x> LUFS, Median <y> dB"`.

## kit/ton-rezept.json (pro Kanal, aus dem Pilot)
```json
{"wps": 4.2,
 "musik": null, "musik_abstand_db": 20, "musik_ducking_db": 4,
 "dichte": "1 Sound pro 0,8 s Sprechzeit",
 "hook": "kenney/impact-punch-heavy-000",
 "familien": {"erscheinen": "@plopp", "wechsel": "@whoosh", "zaehlen": "@klick", "landen": "@landen"},
 "motive": {"richtig": "kenney/confirmation-001", "falsch": "kenney/error-004"},
 "notizen": "Vorbild nutzt keine Musik, Effekte trocken und kurz."}
```
`ms stimme` liest `wps`, `ms mix` liest `musik` (Pfad relativ zum Kanalordner), `musik_abstand_db`, `musik_ducking_db`. Der Rest ist dein Rezept beim Schreiben der Ereignisliste.

## Format der Bauer-Vorschläge (`build/sfx_<bauer>.json`, wie im Agent motion-bauer)
```json
[{"t": 3.54, "szene": "s2", "event": "Würfel landet auf dem Sockel", "sound": "heavy impact thud", "margin_db": 5},
 {"t": 3.99, "szene": "s2", "event": "Konfetti platzt", "sound": "confetti pop sparkle", "margin_db": 8}]
```
`t` global in Sekunden (Moment des sichtbaren Treffers), `sound` kurze englische Beschreibung, `margin_db` wie oben (Hook 0 bis 2, Haupttreffer 4 bis 6, Begleitung 7 bis 9). Das Werkzeug liest auch direkte Einträge `[zeit, "id" oder "@familie", margin]`.

## Fallen
- Nie `trim_db` oder `urteil` selbst ändern: das ist das Ohr des Nutzers (Abhörseite).
- Musik aus freien Quellen kann Content-ID-Ansprüche auslösen (`__HEIM__/referenz/SOUND-QUELLEN.md`, Abschnitt Musik). Im Zweifel `--musik aus` und Musik beim Posten in der App wählen.
- Ein Ereignis nach dem Video-Ende wird übersprungen und gemeldet.
