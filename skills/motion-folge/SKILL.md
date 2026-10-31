---
name: motion-folge
description: "Phase C von Motion-Studio: eine EIGENE Folge im gelernten Kanal-Stil, von der Idee bis zum geprüften Upload-Paket. Idee aus der Ideenliste, Vorlage nur als Bauplan (Form, Länge, Tempo, Hook-Formel), Skript neu, Stimme, Storyboard, Szenen parallel über frische motion-bauer, Ton-Mix, Render und QA, eine unabhängige Prüfung, Upload-Paket mit Video, CAPTION.md, TITEL.txt und Titelbild, Verbrauch. Laden bei \"nächste Folge\", \"neues Video\", \"bau ein Reel\", \"nächstes Reel\", \"produzier\", \"mach eine Folge über\", \"erste eigene Folge\"."
---

# motion-folge (Phase C)

Ergebnis: `folgen/<id>/upload/` mit fertigem Video, CAPTION.md, TITEL.txt und Titelbild, geprüft (0 kritische Befunde), Status `fertig`.
Voraussetzung: ein Kanal mit Status `bereit` und Stil-Skill (sonst erst Skill motion-kanal-lernen).
**Stil-Skill fehlt** (Kanal aus einer Motion-Studio-Version vor dem 31.10.2026, `ms stil <k> pruefen` meldet ihn als fehlend): Im Gespräch dem Nutzer sagen, dass der Kanal zuerst seinen Stil-Skill braucht (motion-kanal-lernen Schritt 9 inklusive Stil-Test, geschätzt 5 bis 15 M Token), nach seinem Ja anlegen und füllen, dann die Folge. Im Autopilot-Bau nichts anlegen: `ms status kanal:<k> --wartet "Stil-Skill fehlt (neu seit dem Update). In der Regie sagen: Leg den Stil-Skill für Kanal <k> an"` und die Sitzung beenden.
**Eigene Folge** (Sebastian 30.10.2026): Der Pilot war der 1:1-Nachbau zum Lernen. Ab jetzt kommt der INHALT aus der Ideenliste, der
Nische und dem Twist des Nutzers. Vom Vorbild übernimmst du nur Form, Länge, Tempo und die Hook-FORMEL, nie Geschichte, Sätze oder Hook-Inhalt.

Nach jeder Phase: `__HEIM__/ms status <folge-id> <phase> --notiz "<Ergebnis mit Zahl>"`. Gate nicht bestanden heißt: beheben, nicht weitergehen.
Zeitbudget (Richtwert für 30 bis 45 s): Idee 5 · Skript 15 · Stimme 10 · Storyboard 10 · Szenen 30 bis 60 (parallel) · Ton 10 · Render und QA 15 · Prüfung 10 · Abschluss 10, zusammen rund 2 bis 2,5 Stunden.

## 0. Vor dem Start
1. `__HEIM__/ms status`: Ist eine Folge offen, dort weitermachen.
2. **Frische Sitzung:** Hat diese Sitzung schon einen Kanal gelernt oder eine Folge gebaut, baust du die neue Folge nicht hier weiter (jeder Schritt würde den ganzen Verlauf neu lesen, gemessen bis zu 10-mal so teuer). Ein Thema des Nutzers zuerst eintragen (`ms ideen <k> neu "<Thema>" --eigen --oben`), dann `__HEIM__/ms starten folge --kanal <k>` und ihm sagen: Die Folge läuft in einer eigenen Sitzung, Fortschritt und Fragen siehst du im Studio.
3. Lesen, in dieser Reihenfolge: **Stil-Skill** `__ARBEIT__/.claude/skills/stil-<k>/SKILL.md` (Pflicht, die Bauanleitung des Stils), `kanaele/<k>/REGELN.md`, `SKRIPT-BAUKASTEN.md`, `__ARBEIT__/PROFIL.md` (Sprache, Stimme, Budget, „Skript vor dem Bau zeigen“), `__HEIM__/ms lernlog --kurz` (nicht das ganze LERNLOG.md), `__HEIM__/ms autopilot` (Zeile Modelle: welches Modell die Helfer bekommen). BIBEL.md nur bei Bedarf.

## Effizienz (Token sparen, gemessen 22. und 23.10.2026)
In den Nachbau-Tests gingen 72 % der Token an die Bauer, vor allem weil fertige Bauer per SendMessage weiterbenutzt wurden und dabei 340 bis 690 k Verlauf neu lasen. Jeder Schritt kostet Verlauf mal Schritte.
- **Frische Bauer, kleine Gruppen:** 1 bis 2 Szenen je Bauer. Ein Bauer, der fertig gemeldet hat, wird nie wieder angeschrieben. Korrektur = neuer Bauer `<name>-fix` mit kurzem Brief (Szene, Zeit, Bildpfad, gewünschte Änderung, Baunotiz aus `fertig_<name>.json`).
- **Warten ohne Abfragen:** `__HEIM__/ms warte <folge> --bauer bauer-1 bauer-2` bzw. `--render <name>` mit Bash `run_in_background`. Claude Code meldet sich, wenn es fertig ist. Kein Nachsehen im Minutentakt.
- **Jedes Bild einmal:** Die Bauer prüfen ihre Szenen, die Regie liest RENDER.md und die Übersicht (ein Bild), der Prüfer sieht jeden Szenenbogen. Die Regie schaut Szenenbögen nur an Stellen mit Befund an. `frame-*.png` in voller Größe nie öffnen, bei Verdacht `ms snap … --detail`.
- **Schleifen gedeckelt:** Bauer höchstens zwei Raster-Runden je Szene. Nach der Prüfung genau eine Korrekturrunde, Nachprüfung nur der geänderten Stellen per Einzelbild, kein zweiter Prüfauftrag. Bleibt danach ein kritischer Befund: Nutzer fragen (`--wartet`), nicht eine dritte Runde drehen.
- **Verlauf klein halten:** lange Ausgaben nie ganz holen (`tail -n 20`, `grep`), Renders und Whisper im Hintergrund mit Log-Datei.
- **Autopilot-Bau** (Auftrag beginnt mit „Bau die nächste Folge … Autopilot-Bau“):
  - ohne Rückfragen durcharbeiten
  - Bezahlte Schritte nur bis zur Grenze „Ohne Nachfrage frei bis“ aus PROFIL.md und im Monatsbudget, trotzdem buchen
  - Geht etwas nur mit dem Nutzer: `ms status <ziel> --wartet "<Frage>"` setzen, kurz melden und die Sitzung beenden. Das Studio zeigt die Frage in JETZT.
  - **Staffel-Bau:** Steht im Auftrag „Stufe A“: nur Schritte 1 bis 4, dann Übergabe (Schritt 4, Ende) und aufhören. „Stufe B für Folge X“: HANDOFF.md und STORYBOARD.md lesen und ab Schritt 5 weiter. Stufe A plant (Opus), Stufe B baut (Sonnet), jede in einer frischen Sitzung.

## 1. Idee und Bauplan (Phase `vorlage`)
1. `__HEIM__/ms ideen <k>`. Steht dort KNAPP: zuerst nach dem Schema auf 10 auffüllen (Skill **motion-ideen**, Schritt 3 und 4).
2. Thema: Hat der Nutzer eins genannt, ist es seins (vorher `ms ideen <k> neu "<Thema>" --eigen --oben`). Sonst `__HEIM__/ms ideen <k> naechste`: zuerst eigene Ideen, dann die vom System.
3. **Bauplan:** ein Top-Video des Vorbilds, dessen FORM zur Idee passt (Liste, Vergleich, Geschichte, Rätsel …): `__HEIM__/ms vorlagen liste --creator <vorbild> --faktor 2`. Ein Bauplan darf mehrfach dienen. Formatwechsel: nicht dreimal hintereinander dieselbe Form. Fehlen Video oder Transkript: `__HEIM__/ms laden <id> --kanal <k>`.
4. Anlegen: `__HEIM__/ms neu folge <slug> --kanal <k> --idee "<Idee wörtlich aus der Liste>" --vorlage <bauplan-id> --titel "<Arbeitstitel>"`. Das macht die Folge zur eigenen Folge (nur die werden gepostet) und hakt die Idee ab.
**Gate:** Kopf von SKRIPT.md: Idee, warum sie jetzt passt, Bauplan (Views, welche Form du übernimmst), Twist aus dem Profil.

## 2. Skript (Phase `skript`)
Skill **motion-skript**, Modus „eigene Folge“: Inhalt neu aus Idee und Recherche, Aufbau, Länge, Tempo und Hook-Formel aus SKRIPT-BAUKASTEN.md und dem Bauplan. Sprechtext und Anzeigetext getrennt (`voice/script.json`), Aussprache-Liste für Namen.
**Gate:** Hook folgt einer Formel aus dem Baukasten, der Inhalt ist eigen. Länge ±15 % des Bauplans. Jede Behauptung belegt (Quelle mit Datum in SKRIPT.md) oder weggelassen. Kein Satz aus der Vorlage übernommen. Steht im Profil „Skript vor dem Bau zeigen: ja“: Thema und Skript zeigen, `--wartet`, erst nach Ja weiter.

## 3. Stimme (Phase `stimme`)
Skill **motion-stimme**: Anbieter nach Profil (ElevenLabs, Higgsfield, Voice Studio, eigene Aufnahme), Tempo an den Bauplan, Wortzeiten (`__HEIM__/ms stimme`, `__HEIM__/ms woerter`).
Kostet die Stimme etwas: vorher Betrag nennen, Ja holen. ElevenLabs bucht `ms stimme … --ja` selbst in STATUS (nicht doppelt buchen). Higgsfield danach von Hand: `__HEIM__/ms status <folge-id> --kosten <betrag> Credits "Higgsfield Stimme"`.
**Gate:** Whisper-Gegenprobe ≥ 95 % der Wörter erkannt, `voice/woerter.json` da, Tempo im Rahmen des Kanals, Stimme −14 LUFS ±0,5.

## 4. Storyboard (Phase `storyboard`)
Skill **motion-storyboard**: `STORYBOARD.md` und `build/scenes.json` auf den Wortzeiten. Je Szene ein **Szenentyp aus dem Stil-Skill**, Bausteine mit dem Aufruf von dort, Zeiten und Easing nach dessen Abschnitt „Bewegung“. Eine sichtbare Aktion pro Aussage, genau auf dem Wort. Pro Szene ein Wow-Moment und ein Sound.
Bauer-Gruppen: 1 bis 2 Szenen je Bauer. Gemeinsame Konstanten (Overlay, Farben, Schrift, Kamera) für alle vorab festlegen und in jeden Brief schreiben.
**Gate:** Jede Kernaussage hat Aktion, Zeit, Sound, Spur und Szenentyp. `__HEIM__/ms szenen <folge-id> --check --plan` meldet keine Lücken.
Danach, vor dem Start der Bauer: `__HEIM__/ms szenen <folge-id> --plan` (index.html und Platzhalter je Szene).
**Staffel Stufe A endet hier:** In HANDOFF.md den Abschnitt „Übergabe Stufe B“ schreiben (Bauer-Gruppen mit Szenen und Szenentyp, Farben, Schrift, gemeinsame Konstanten, offene Punkte), dann `__HEIM__/ms status <folge-id> --stufe A-fertig` und aufhören.

## 5. Szenen (Phase `szenen`)
Starte alle Bauer in EINER Nachricht parallel über das Agent-Tool (subagent_type "motion-bauer", name "bauer-1", "bauer-2" …, `model` wie in `ms autopilot` unter Helfer, Standard sonnet), je Gruppe ein Brief nach der Vorlage in motion-storyboard. Im Brief steht der Pfad des Stil-Skills. `__HEIM__/ms log "Bauer gestartet: <Gruppen>" --wer motion-regie --ziel <folge-id>`.
Dann `__HEIM__/ms warte <folge-id> --bauer bauer-1 bauer-2 …` im Hintergrund und währenddessen Ton-Ereignisse vorbereiten (Schritt 6), CAPTION.md und TITEL.txt entwerfen.
Jede `build/fertig_<name>.json` lesen: `"offen"` entscheiden, `"baunotiz"` für mögliche Korrekturen merken. Kontaktbögen der Bauer nur ansehen, wo `"offen"` oder ein Zweifel steht.
Korrektur: neuer Bauer `<name>-fix` mit Szene, Zeit, Bildpfad, gewünschter Änderung und Baunotiz. Nie SendMessage an einen Bauer, der fertig gemeldet hat.
**Gate:** `__HEIM__/ms szenen <folge-id> --check` meldet kein „noch nicht gebaut“, jedes `"offen"` entschieden.

## 6. Ton (Phase `ton`)
Skill **motion-ton-mix**: Ereignisse aus der Sound-Bibliothek nach `kit/ton-rezept.json` und Abschnitt „Ton“ im Stil-Skill, Familien reihum, Effekte unter der Stimme, Mix auf −14 LUFS.
**Gate:** Mix −14 LUFS ±0,5, Effekte hörbar unter der Stimme, gleiche Aktion gleiche Sound-Familie.

## 7. Render und QA (Phase `render`)
`__HEIM__/ms szenen <folge-id>`, dann Skill **motion-qa**: `__HEIM__/ms render <folge-id> v1 > __ARBEIT__/folgen/<folge-id>/out/render_v1.log 2>&1` im Hintergrund und `__HEIM__/ms warte <folge-id> --render v1`.
**Gate:** RENDER.md ohne FEHLER-Befund (Schwarzbild nur an Schnitten, Bildzahl, Lautheit), Übersicht `out/qa_v1/uebersicht.jpg` angesehen. Szenenbögen nur dort, wo RENDER.md oder die Übersicht etwas zeigt. Fehler beheben, neu rendern (`v2`).

## 8. Prüfung (Phase `pruefung`)
Agent **motion-pruefer** (`subagent_type: "motion-pruefer"`, `model` wie Helfer) genau einmal, mit Pfaden: Video, Kontaktbögen, SKRIPT.md, STORYBOARD.md, Stil-Skill, `kanaele/<k>/REGELN.md`, Pilot als Referenz. Kein Bau-Kontext.
**Gate:** 0 kritische Befunde. Befunde in EINER Runde abarbeiten (frische Bauer für Szenen), neu rendern, die geänderten Stellen selbst per `ms snap --detail` oder Einzelbild nachprüfen. Kein zweiter Prüfauftrag. Bleibt ein kritischer Befund offen: Nutzer fragen.
Danach die Abgabe-Fassung: `__HEIM__/ms render <folge-id> final --qualitaet final` (im Hintergrund, `ms warte … --render final`). Nur die automatischen Prüfungen aus RENDER.md, kein zweiter Durchgang durch die Bögen.

## 9. Fertig (Phase `fertig`)
1. `folgen/<id>/CAPTION.md`: genau der Text, der gepostet wird. Sprache und Plattform aus dem Profil. Erster Satz trägt den Hook, dann Nutzen in 1 bis 2 Sätzen, 3 bis 6 Hashtags. Nur Aussagen, die im Video belegt sind.
2. Upload-Paket `folgen/<id>/upload/` (ohne `cp`, nur mit erlaubten Befehlen): Video `ffmpeg -nostdin -v error -i __ARBEIT__/folgen/<id>/out/final.mp4 -c copy __ARBEIT__/folgen/<id>/upload/<id>.mp4`, CAPTION.md mit Read lesen und mit Write nach `upload/CAPTION.md`, `upload/TITEL.txt` (YouTube-Titel, höchstens 100 Zeichen, Hook als Frage oder Aussage), Titelbild `titelbild.jpg` (stärkstes Bild: `ffmpeg -nostdin -v error -ss <sekunde> -i __ARBEIT__/folgen/<id>/out/final.mp4 -frames:v 1 -q:v 2 __ARBEIT__/folgen/<id>/upload/titelbild.jpg`, ansehen, bevor du es nimmst).
3. `HANDOFF.md`: Szenen-Tabelle (Start, Dauer, Spur, Szenentyp, Inhalt), neue Bausteine fürs Kit, Ton (Anzahl Ereignisse, LUFS), Prüfbefunde und Korrekturen, Kosten, bewusst gelassene Punkte.
4. **Kit und Stil-Skill pflegen** (Skill motion-kanal-kit, Schritt 6): neue Bausteine additiv ins Kit, dann `__HEIM__/ms stil <k> sichern`, im Stil-Skill ergänzen, was neu ist (Szenentyp, Baustein mit Aufruf, Regel, Beispiel mit Datei und Zeit), Zeile unter „Pflege“, `__HEIM__/ms stil <k> pruefen` (nichts darf verschwinden).
5. `__HEIM__/ms status <folge-id> fertig --video upload/<id>.mp4 --vorschau upload/titelbild.jpg --notiz "<Dauer>, <Kosten>"`.
6. `__HEIM__/ms verbrauch <folge-id> --eintragen` (Token je Folge und Anteil an der Woche, steht dann im Studio).
7. Lernlog: 3 bis 5 Zeilen (Datum, Folge, Idee, was geklappt hat, was nicht, Verbrauch, Kosten). Gilt eine Lehre für jede Folge: als eine Zeile unter `## Lehren` oder als Vorschlag für REGELN.md. Meldet `ms lernlog --kurz` mehr als 40 Einträge: `__HEIM__/ms lernlog archivieren`.
8. Video für den Nutzer öffnen und kurz melden: Pfad, Idee und Bauplan, Twist, stärkste Momente, bewusst Gelassenes, Kosten, Verbrauch, Dauer.
**Gate:** upload/ enthält Video, CAPTION.md, TITEL.txt und Titelbild, STATUS zeigt `fertig` mit `video` und `vorschau`, `ms stil <k> pruefen` OK.

## Danach
Posten: Skill **motion-posten** (nur auf Auftrag des Nutzers oder durch den Autopiloten auf freigegebenen Plattformen). Von Hand: `__HEIM__/ms status <folge-id> --geplant 2026-10-21T18:00` bzw. `__HEIM__/ms posten ergebnis <folge-id> --plattform instagram --link <url>`.

## Bekannte Fallen
- Szene sieht im Snapshot gut aus, sitzt aber nicht auf dem Wort: immer gegen `voice/woerter.json` prüfen.
- Gleicher Sound für verschiedene Bedeutungen verwirrt. Gleiche Aktion, gleiche Familie, Varianten reihum.
- Inhalt vom Vorbild abgeschrieben, nur umformuliert: Das ist keine eigene Folge. Neu anfangen mit einer Idee aus der Liste.
- Nie ein ganzes Video roh in den Arbeitsspeicher laden, Frames streamen.
- Nichts löschen. Ersetztes nach `_ueberholt/`.
