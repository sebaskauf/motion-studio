---
name: motion-folge
description: "Phase C von Motion-Studio: eine neue Folge im gelernten Kanal-Stil von der Vorlage bis zum geprüften Upload-Paket. Vorlage wählen, Skript, Stimme, Storyboard, Szenen parallel über motion-bauer, Ton-Mix, Render und QA, unabhängige Prüfung, Upload-Paket mit Video, CAPTION.md und Titelbild. Laden bei \"nächste Folge\", \"neues Video\", \"bau ein Reel\", \"nächstes Reel\", \"produzier\", \"mach eine Folge über\"."
---

# motion-folge (Phase C)

Ergebnis: `folgen/<id>/upload/` mit fertigem Video, CAPTION.md und Titelbild, geprüft (0 kritische Befunde), Status `fertig`.
Voraussetzung: ein Kanal mit Status `bereit` (sonst erst Skill motion-kanal-lernen). Geplant und gepostet setzt der Nutzer.

Nach jeder Phase: `__HEIM__/ms status <folge-id> <phase> --notiz "<Ergebnis mit Zahl>"`. Gate nicht bestanden heißt: beheben, nicht weitergehen.
Zeitbudget (Richtwert für 30 bis 45 s): Vorlage 5 · Skript 10 · Stimme 10 · Storyboard 10 · Szenen 30 bis 60 (parallel) · Ton 10 · Render und QA 15 · Prüfung 10 · Abschluss 10, zusammen rund 2 bis 2,5 Stunden. Die ersten Folgen dauern länger. Qualität vor Tempo.

## 0. Vor dem Start
1. `__HEIM__/ms status`: Ist eine Folge offen, dort weitermachen.
2. Lesen: `kanaele/<k>/REGELN.md`, `BIBEL.md`, `SKRIPT-BAUKASTEN.md`, `kit/KATALOG.md`, `__ARBEIT__/LERNLOG.md`, `__ARBEIT__/PROFIL.md` (Sprache, Stimme, Budget, „Skript vor dem Bau zeigen“).

## Effizienz (Token sparen, gemessen an Sebastians Reel-Studio, 22.10.2026)
Die Regie selbst macht 57 bis 70 % der Kosten einer Folge. Rund drei Viertel davon entstehen, weil sie bei jedem Schritt ihren immer längeren Verlauf neu liest. Jeder überflüssige Schritt wird also teurer, je später er kommt.
- **Jede Prüfung einmal.** Nachprüfen nur nach einer Änderung, und nur die geänderte Stelle (Einzelbild oder eine Szene). Kein zweiter Kontaktbogen-Durchgang ohne Änderung, kein Vollrender für eine Kleinigkeit.
- **motion-pruefer genau eine Runde.** Nach den Fixes prüfst du die gemeldeten Stellen selbst per Einzelbild, ohne zweiten Prüfauftrag.
- **Verlauf klein halten:**
  - Lange Ausgaben nie ganz holen (`tail -n 20`, `grep`).
  - Renders, Whisper und Tests im Hintergrund mit Log-Datei laufen lassen und nicht im Sekundentakt nachsehen.
- **motion-bauer mit engem Brief** (nur seine Szenen, seine Pfade) und kurzer Rückmeldung (höchstens 15 Zeilen).
- Qualität kommt aus einem sauberen ersten Durchgang (genaues Storyboard, genaue Treffer-Zeiten), nicht aus Prüfschleifen.
- **Autopilot-Bau** (Auftrag beginnt mit „Autopilot-Bau“):
  - ohne Rückfragen durcharbeiten
  - Bezahlte Schritte nur bis zur Grenze „Ohne Nachfrage frei bis“ aus PROFIL.md und im Monatsbudget, trotzdem buchen
  - Geht etwas nur mit dem Nutzer: `ms status <ziel> --wartet "<Frage>"` setzen, kurz melden und die Sitzung beenden. Das Dashboard zeigt die Frage in JETZT.

## 1. Vorlage (Phase `vorlage`)
Skill **motion-vorlagen-finden**: Das Register ist global (alle Vorbilder), deshalb nach dem Vorbild des Kanals filtern:
`__HEIM__/ms vorlagen liste --creator <vorbild> --faktor 2`. Regeln:
- Ausreißer bevorzugen (Views deutlich über dem Median des Creators).
- Keine Dublette: Vorlage nicht schon `genutzt`, Thema nicht schon in den letzten Folgen.
- Formatwechsel: nicht dreimal hintereinander dasselbe Format (zum Beispiel Liste, Vergleich, Geschichte).
Vorlage laden, falls noch nicht geladen: `__HEIM__/ms laden <id> --kanal <k>` (Video und Transkript). Erst danach
`__HEIM__/ms neu folge <slug> --kanal <k> --vorlage <id> --titel "<Arbeitstitel>"`, denn `ms neu` übernimmt Video- und
Transkript-Pfad aus dem Register (Wortzahl und Tempo der Vorlage hängen daran). Dann `__HEIM__/ms vorlagen set <id> genutzt`.
**Gate:** Begründung in SKRIPT.md (Views, Faktor, warum dieses Thema jetzt, was der eigene Twist ist).

## 2. Skript (Phase `skript`)
Skill **motion-skript**: Vorlage in eigene Worte in der Kanalsprache, nach SKRIPT-BAUKASTEN (Hook, Re-Hook, Beleg, Nutzen, CTA). Sprechtext und Anzeigetext getrennt (`voice/script.json`), Aussprache-Liste für Namen.
**Gate:** Hook folgt einer Formel aus dem Baukasten. Länge ±15 % der Vorlage. Jede Behauptung belegt oder weggelassen (lieber Thema wechseln als raten). Steht im Profil „Skript vor dem Bau zeigen: ja“: Skript zeigen, `--wartet`, erst nach Ja weiter.

## 3. Stimme (Phase `stimme`)
Skill **motion-stimme**: TTS nach Profil (ElevenLabs, Higgsfield, eigene Aufnahme), Tempo an die Vorlage, Wortzeiten (`__HEIM__/ms stimme`, `__HEIM__/ms woerter`).
Kostet die Stimme etwas: vorher Betrag nennen, Ja holen. ElevenLabs bucht `ms stimme … --ja` selbst in STATUS (nicht doppelt buchen). Higgsfield danach von Hand: `__HEIM__/ms status <folge-id> --kosten <betrag> Credits "Higgsfield Stimme"`.
**Gate:** Whisper-Gegenprobe ≥ 95 % der Wörter erkannt, `voice/woerter.json` da, Tempo im Rahmen des Kanals, Stimme −14 LUFS ±0,5.

## 4. Storyboard (Phase `storyboard`)
Skill **motion-storyboard**: `STORYBOARD.md` und `build/scenes.json` auf den Wortzeiten. Eine sichtbare Aktion pro Aussage, genau auf dem Wort. Pro Szene ein Wow-Moment und ein Sound. Bausteine aus `kit/KATALOG.md` zuerst.
Dann Szenengruppen für die Bauer festlegen (zum Beispiel 2D-Szenen in zwei Gruppen, 3D in einer), je Gruppe einen Brief nach der Vorlage in motion-storyboard.
**Gate:** Jede Kernaussage hat Aktion, Zeit, Sound und Spur (2d, 3d-web, blender). `__HEIM__/ms szenen <folge-id> --check --plan` meldet keine Lücken (`--plan` prüft nur den Zeitplan, die Kompositionen kommen erst in Phase 5).
Danach, vor dem Start der Bauer: `__HEIM__/ms szenen <folge-id> --plan`. Das schreibt `build/index.html` und legt je Szene einen neutralen Platzhalter an (nie über eine vorhandene Komposition). Ohne index.html laufen lint und `ms snap` der Bauer nicht.

## 5. Szenen (Phase `szenen`)
Starte alle Bauer in EINER Nachricht parallel über das Agent-Tool (subagent_type "motion-bauer", name "bauer-1", "bauer-2" …), je Szenengruppe einer mit seinem Brief. `__HEIM__/ms log "Bauer gestartet: <Gruppen>" --wer motion-regie --ziel <folge-id>`.
Bauer warten nie auf Antworten: Unklares entscheiden sie als Annahme und melden es in `build/fertig_<name>.json` unter `"offen"`.
Währenddessen: `__HEIM__/ms log --zeige` und die vorhandenen `fertig_*.json` lesen, Annahmen entscheiden, Ton-Ereignisse vorbereiten (Schritt 6), Caption-Entwurf schreiben.
Jeder Bauer meldet fertig mit Snapshots der Kernaktionen. Sieh dir jeden Snapshot an (Read-Tool). Fehlt eine Kernaktion oder sitzt sie nicht auf dem Wort: per SendMessage an denselben Bauer (Name `bauer-1` …) zurück.
**Gate:** Alle Szenen gebaut (`__HEIM__/ms szenen <folge-id> --check` meldet kein „noch nicht gebaut“), jede Kernaktion im Snapshot sichtbar, jedes `"offen"` entschieden.

## 6. Ton (Phase `ton`)
Skill **motion-ton-mix**: Ereignisse aus der Sound-Bibliothek nach `kit/ton-rezept.json`, Familien reihum, Effekte unter der Stimme, Mix auf −14 LUFS.
**Gate:** Mix −14 LUFS ±0,5, Effekte hörbar unter der Stimme, gleiche Aktion gleiche Sound-Familie.

## 7. Render und QA (Phase `render`)
`__HEIM__/ms szenen <folge-id>`, dann Skill **motion-qa**: `__HEIM__/ms render <folge-id> v1` (Entwurf, im Hintergrund starten, dauert Minuten).
**Gate:** Schwarzbild-Scan zeigt nur Szenenschnitte, alle Kontaktbögen in voller Auflösung angesehen, Lautheit im Render −14 LUFS (das Gate ±0,5 hat der Mix geprüft; außerhalb ±1 ist ein Ausschlussfehler). Fehler beheben, neu rendern (`v2`, `v3`). Alte Renders bleiben liegen oder wandern nach `_ueberholt/`.

## 8. Prüfung (Phase `pruefung`)
Agent **motion-pruefer** (`subagent_type: "motion-pruefer"`) mit Pfaden: Video, Kontaktbögen, SKRIPT.md, STORYBOARD.md, `kanaele/<k>/REGELN.md` und `BIBEL.md`, Pilot als Referenz. Kein Bau-Kontext.
**Gate:** 0 kritische Befunde. Befunde abarbeiten, neu rendern, bei Bedarf erneut prüfen. Nach drei Runden an derselben Stelle: Nutzer fragen.
Danach die Abgabe-Fassung: `__HEIM__/ms render <folge-id> final --qualitaet final`, Kontaktbögen kurz gegenprüfen.

## 9. Fertig (Phase `fertig`)
1. `folgen/<id>/CAPTION.md`: genau der Text, der gepostet wird. Sprache und Plattform aus dem Profil. Erster Satz trägt den Hook, dann Nutzen in 1 bis 2 Sätzen, 3 bis 6 Hashtags. Nur Aussagen, die im Video belegt sind.
2. Upload-Paket `folgen/<id>/upload/` (ohne `cp`, nur mit erlaubten Befehlen): Video `ffmpeg -nostdin -v error -i __ARBEIT__/folgen/<id>/out/final.mp4 -c copy __ARBEIT__/folgen/<id>/upload/<id>.mp4`, CAPTION.md mit Read lesen und mit Write nach `upload/CAPTION.md`, Titelbild `titelbild.jpg` (stärkstes Bild aus dem Video: `ffmpeg -nostdin -v error -ss <sekunde> -i __ARBEIT__/folgen/<id>/out/final.mp4 -frames:v 1 -q:v 2 __ARBEIT__/folgen/<id>/upload/titelbild.jpg`, ansehen, bevor du es nimmst).
3. `HANDOFF.md`: Szenen-Tabelle (Start, Dauer, Spur, Inhalt), neue Bausteine fürs Kit, Ton (Anzahl Ereignisse, LUFS), Prüfbefunde und Korrekturen, Kosten, bewusst gelassene Punkte.
4. Neue wiederverwendbare Bausteine nach Skill motion-kanal-kit ins Kit übernehmen: erst `__HEIM__/ms kit <k> pruefen --kandidat <folge>/build/assets/lib`, nur bei OK übernehmen (Read, dann Write nach `kanaele/<k>/kit/lib/`), dann `__HEIM__/ms kit <k> katalog`. Nur hinzufügen, nichts überschreiben.
5. `__HEIM__/ms status <folge-id> fertig --video upload/<id>.mp4 --vorschau upload/titelbild.jpg --notiz "<Dauer>, <Kosten>"`.
6. Lernlog: 3 bis 5 Zeilen. Video für den Nutzer öffnen und kurz melden: Pfad, Thema und Vorlage, stärkste Momente, bewusst Gelassenes, Kosten, Dauer.
**Gate:** upload/ enthält Video, CAPTION.md und Titelbild, STATUS zeigt `fertig` mit `video` und `vorschau`.

## Danach (Nutzer)
Geplant: im Dashboard oder `__HEIM__/ms status <folge-id> --geplant 2026-10-21T18:00`. Gepostet: `__HEIM__/ms status <folge-id> --gepostet <link>`.
Du postest nie selbst.

## Bekannte Fallen
- Szene sieht im Snapshot gut aus, sitzt aber nicht auf dem Wort: immer gegen `voice/woerter.json` prüfen.
- Gleicher Sound für verschiedene Bedeutungen verwirrt. Gleiche Aktion, gleiche Familie, Varianten reihum.
- Nie ein ganzes Video roh in den Arbeitsspeicher laden, Frames streamen.
- Nichts löschen. Ersetztes nach `_ueberholt/`.
