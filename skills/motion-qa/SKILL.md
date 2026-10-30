---
name: motion-qa
description: "Abnahme einer Motion-Studio-Folge vor der Übergabe: Vollrender im Hintergrund, Schwarzbild-Scan, Lautheit, Bildzahl, Übersicht für die Regie, Kontaktbögen jeder Szene für den Prüfer, Ausschlussfehler, eine Korrekturrunde, danach genau eine unabhängige Prüfung durch motion-pruefer. Der Nutzer darf keinen Fehler als Erster finden. Laden bei \"rendern\", \"Render\", \"QA\", \"abnehmen\", \"prüf das Video\", \"Kontaktbögen\", \"fertig machen\"."
---

# motion-qa

## 1. Vor dem Render (Gate)
- `__HEIM__/ms szenen <folge> --check` → „Prüfung: OK“ (keine Lücke, alle Dauern stimmen; eine 0,02-s-Lücke ist ein Schwarzbild).
- Jeder Bauer hat `build/fertig_<name>.json` geschrieben, kein Platzhalter mehr („noch nicht gebaut“ bricht den Render ab). Ton fertig: `build/assets/audio/mix.wav` mit −14 LUFS ±0,5 (Gate im Skill motion-ton-mix). Für einen ersten Bild-Entwurf darf der Mix fehlen (dann läuft die Stimme). Beim Pilot gibt es keinen Mix: der Originalton ist der Ton.

## 2. Render
```
__HEIM__/ms render <folge> <name> > __ARBEIT__/folgen/<folge>/out/render_<name>.log 2>&1
```
**Immer im Hintergrund** (Bash `run_in_background: true`): ein Render dauert 1 bis 10 Minuten, unter Last länger, und ein abgebrochener Render kostet einen Neustart.
Warten: `__HEIM__/ms warte <folge> --render <name>` ebenfalls im Hintergrund, Claude Code meldet sich, wenn es fertig ist. Nicht selbst nachsehen.
Namen hochzählen: `v1`, `v1b`, `v2`. Abgabe: `--qualitaet final`. Alte Fassungen gleichen Namens wandern nach `out/_ueberholt/`.
Fertig erst, wenn `out/<name>.mp4` existiert UND das Log mit `fertig:` endet. Das Werkzeug prüft selbst: Bildzahl gegen Soll (Dauer × 30; ±1 Bild ist erlaubt und kein Befund, erst darüber FEHLER), Schwarzbild-Scan, Lautheit, Kontaktbögen `out/qa_<name>/<szene>.jpg` (5 Bilder/s, `--dicht` 10), Übersicht `out/qa_<name>/uebersicht.jpg` (1 Bild/s), Bericht `out/qa_<name>/RENDER.md`, Status `render` mit Video und Vorschau.
Nur Prüfungen auf einem vorhandenen Video: `__HEIM__/ms render <folge> <name> --nur-qa`.

## 3. Ansehen (Token-Diät: jedes Bild einmal, gemessen ~5 k Token je Szenenbogen)
- **Regie:** RENDER.md lesen (Bildzahl, Lautheit, Schwarzbild-Treffer) und die Übersicht `uebersicht.jpg` ansehen (ein Bild für die ganze Folge). Szenenbögen nur dort öffnen, wo RENDER.md einen FEHLER oder HINWEIS meldet, die Übersicht etwas Auffälliges zeigt oder ein Bauer etwas als `"offen"` gemeldet hat.
- **Prüfer (Schritt 5):** sieht jeden Szenenbogen genau einmal.
Prüfliste je Stelle:
- Hauptmotiv groß und ganz im Bild, nicht angeschnitten, nicht verdeckt? In der ersten Szene ab dem ersten Bild?
- Jede Kernaktion auf ihrem Wort sichtbar und lesbar (STORYBOARD.md daneben)?
- Wow-Moment vorhanden? Stillstand über 1,5 s?
- Text lesbar, im Rahmen, nicht unter den Captions? Caption-Wörter richtig geschrieben?
- Übergänge sauber: kein Leerbild, kein Ruck, keine Lücke?
Schwarzbild-Scan: FEHLER außerhalb eines Schnitts immer ansehen. Unklare Stelle verkleinert statt in voller Größe:
`ffmpeg -nostdin -v error -ss <sek> -i out/<name>.mp4 -frames:v 1 -vf scale=540:-2 snapshots/pruef_<sek>.jpg` und ansehen.

## 4. Beheben, neu rendern (eine Runde)
Fehler in der Szene beheben (oder einem frischen Bauer `<name>-fix` mit Bildpfad und Baunotiz geben, nie dem fertigen Bauer per SendMessage), die Stelle per `__HEIM__/ms snap … --detail` prüfen, dann neu rendern (Name hochzählen). Befunde und Korrekturen in `HANDOFF.md` notieren.

## 5. Unabhängige Prüfung (genau eine Runde)
Agent **motion-pruefer** (`subagent_type: "motion-pruefer"`, `model` wie Helfer in `ms autopilot`), Prompt nur mit Pfaden:
„Prüfe die Folge <folge>. Video: out/<name>.mp4, Kontaktbögen: out/qa_<name>/, Skript: SKRIPT.md, Storyboard: STORYBOARD.md, Stil-Skill: __ARBEIT__/.claude/skills/stil-<k>/SKILL.md, Regeln: kanaele/<k>/REGELN.md, falls vorhanden (beim Pilot: die [R]-Regeln aus BIBEL.md), Referenz: <Pilot-Video oder abgenommene Folge>.“
Beim Pilot stattdessen der Brief aus Skill motion-kanal-lernen, Schritt 6 (Original-Ausschnitt, Vergleichsordner).
Kritische Befunde in EINER Runde beheben und neu rendern, die geänderten Stellen selbst per Einzelbild nachprüfen. Kein zweiter Prüfauftrag. Bleibt ein kritischer Befund: Nutzer fragen (`ms status <folge> --wartet …`). Kleinere beheben oder begründet lassen (HANDOFF.md). Danach `__HEIM__/ms status <folge> pruefung --notiz "<Urteil>, <n> Befunde behoben"`.
Abgabe-Render `final`: nur die automatischen Prüfungen aus RENDER.md, kein zweiter Durchgang durch die Bögen.

## Ausschlussfehler (dürfen nie raus)
Schwarzes oder leeres Bild · Hauptmotiv im ersten Bild nicht groß zu sehen · Figur/Objekt angeschnitten oder Gesicht verdeckt · Kernaktion nicht im Bild · Text unlesbar oder abgeschnitten · Caption-Wort falsch geschrieben · Lautheit im Render außerhalb −14 ±1 LUFS (Abgabe; das Gate ±0,5 gilt schon beim Mix) · Bildzahl mehr als 1 Bild neben dem Soll (±1 ist Rundung beim Render) · Ton und Bild versetzt · Sound eindeutig falsch oder lauter als die Stimme.
**Gate für „fertig“:** Render `final` ohne FEHLER-Befund, Übersicht angesehen, Prüfer hat jeden Bogen gesehen und meldet keinen offenen kritischen Befund.
