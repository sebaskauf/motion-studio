---
name: motion-kanal-lernen
description: "Phase B von Motion-Studio: einen Motion-Design-Kanal lernen. Top-Videos des Vorbilds ins Register, 3 bis 5 laden und zerlegen (motion-analyse), Machbarkeit mit dem Nutzer klären, ein Video als Pilot fast 1:1 nachbauen, mit ms vergleich messen, unabhängig prüfen, daraus Kit, Regeln, Skript-Baukasten und den Stil-Skill des Kanals machen (Bauanleitung für jede neue Sitzung). Laden bei \"lern den Kanal\", \"neues Vorbild\", \"bau dieses Video nach\", \"Kanal nachbauen\", \"Stil lernen\", \"Pilot\"."
---

# motion-kanal-lernen (Phase B)

Ergebnis: Kanal `kanaele/<slug>/` mit Status `bereit`, darin BIBEL.md, REGELN.md, SKRIPT-BAUKASTEN.md, IDEEN.md, kit/ mit KATALOG.md
und ton-rezept.json, dazu ein gemessener Pilot-Nachbau und der **Stil-Skill** `__ARBEIT__/.claude/skills/stil-<slug>/SKILL.md`.
Danach produziert der Skill `motion-folge` eigene Folgen in diesem Stil.
Warum der Pilot 1:1 ist (Sebastian 30.10.2026): „das soll halt im allerersten Video 1:1 passieren, damit Claude das lernt“. Was
der Nachbau lehrt, landet im Stil-Skill, und der wird in jeder neuen Sitzung geladen. Eigene Folgen übernehmen nur noch die Form.

**Läuft automatisch durch** (Sebastian 23.10.2026):
- Ist das Vorbild gewählt, ist der 1:1-Nachbau Pflicht, bevor eigene Folgen kommen. Frag nicht, ob nachgebaut werden soll.
- Zu Beginn kommt ein kurzer Hinweis an den Nutzer, danach sieht er den Fortschritt im Studio (Schrittleiste mit Fertig-Zeit).
- Fragen nur in drei Fällen:
  - Kosten über „Ohne Nachfrage frei bis“
  - ein Fehler, den du nicht selbst löst
  - das Urteil zum fertigen Nachbau in Schritt 7

Grundregel: **erst messen, dann bauen, dann wieder messen.** Kein Schritt gilt als fertig ohne seinen Gate-Beleg.
Nach jedem Schritt: `__HEIM__/ms status kanal:<slug> <phase> --notiz "<Ergebnis mit Zahl>"` und ein Satz an den Nutzer.
Zeitbedarf (Richtwert): Vorlagen 15 min, Zerlegen 30 bis 60 min, Pilot 2 bis 4 Stunden, Kit 30 min.

## 1. Kanal anlegen und Vorlagen finden (Phase `vorbild`)
1. `__HEIM__/ms neu kanal <slug> --vorbild "<@handle oder Link>" --titel "<Name>"`. Slug kurz, nur a-z, 0-9, Bindestrich.
2. Skill **motion-vorlagen-finden** laden: Top-Videos des Vorbilds ins Register. YouTube und TikTok gratis (`__HEIM__/ms vorlagen yt …`, `… tiktok …`). Instagram nur über Apify mit Kostenansage und Ja, oder der Nutzer speichert Videos selbst (`__HEIM__/ms laden datei …`).
3. Ausreißer wählen: 3 bis 5 Videos mit den meisten Views im Verhältnis zum Kanal-Median (`__HEIM__/ms vorlagen liste --creator <vorbild> --faktor 2`, das Register ist global). Mischung aus typischen Formaten, keine fünf gleichen.
4. Laden: `__HEIM__/ms laden <id> --kanal <slug>` je Video (lädt Video und Transkript).
   Selbst gespeicherte Videos (`ms laden datei …`) haben oft keine Views: Zahl unter dem Video ablesen und `__HEIM__/ms vorlagen set <id> --views <N>`, gibt es keine: `__HEIM__/ms vorlagen set <id> --views-unbekannt`.
**Gate:** 3 bis 5 Videos liegen in `vorlagen/videos/`, jedes mit Transkript und mit Views im Register, falls bekannt (sonst als unbekannt vermerkt, dann zählt beim Auswählen das eigene Urteil statt des Faktors).
`__HEIM__/ms status kanal:<slug> vorbild --notiz "<n> Videos, Median <x> Views"`

## 2. Zerlegen (Phasen `zerlegt`, `bibel`)
**Ein Analyse-Agent je Video** (Token-Diät: 3 bis 5 Videos in einem Kontext wären 150 bis 180 Bilder in einem Verlauf). Starte alle in EINER Nachricht parallel über das Agent-Tool (`subagent_type: "motion-analyse"`, `model` wie Helfer in `ms autopilot`), je Video ein Brief:
```
Modus: ein Video. Kanal <slug> (Vorbild <@handle>). Video: <id> (in __ARBEIT__/vorlagen/videos/, Transkript in __ARBEIT__/vorlagen/transkripte/).
Ziel: kanaele/<slug>/analyse/<id>/ (ANALYSE.md mit Korrekturen, Bewegungsliste). Szenenbögen: <alle, das ist der Pilot-Kandidat | nur Übersicht und Schnittbögen>.
Rückmeldung höchstens 30 Zeilen: Typ, Szenen, Palette, Kamera, Captions, Ton, Skript-Aufbau, Machbarkeit, eignet es sich als Pilot.
```
Szenenbögen voll nur für 1 bis 2 Pilot-Kandidaten (meiste Views, machbar), bei den übrigen Übersicht und Schnittbögen.
Sind alle zurück: noch EIN motion-analyse im Modus „Bibel“: „Modus: Bibel. Kanal <slug>. Lies die ANALYSE.md und analyse.json aller Videos in kanaele/<slug>/analyse/ (keine Bögen außer Stichproben) und schreib BIBEL.md und SKRIPT-BAUKASTEN.md, mit Pilot-Empfehlung.“
Während die Analyse läuft: dem Nutzer kurz sagen, was passiert und wie lange es dauert.
**Gate:** Je Video ein Analyse-Ordner mit Kontaktbogen, Schnittliste, Palette, Transkript. BIBEL.md trennt [B] beobachtet, [P] vermutet, [R] Regel. SKRIPT-BAUKASTEN.md mit Hook-Formeln und Längen. Zwei Stichproben: die BIBEL an zwei Stellen gegen je einen Bogen prüfen (Read-Tool), nicht alle Bögen noch einmal.
`ms status kanal:<slug> zerlegt`, dann `ms status kanal:<slug> bibel`.

## 3. Machbarkeit und Plan mit dem Nutzer (Gate)
Zeig in 6 bis 10 Zeilen: Was macht den Kanal aus (Look, Schnitt, Ton, Skript), welche Spur (2D, 3D-Web, Blender), was realistisch erreichbar ist, welches Video Pilot wird und warum, Zeit und Kosten (meist 0, Stimme beim Pilot entfällt).
Ehrlich: Figuren mit Rig und Schauspiel sind der schwerste Teil. Ist der Kanal davon getragen, sag es vorher.
Für den Pilot das Video wählen, das den Kanal am besten zeigt und am ehesten erreichbar ist. Bei gemischten Kanälen erst 2D.
Nicht warten:
- Plan als Notiz eintragen: `__HEIM__/ms status kanal:<slug> --notiz "Pilot <id>: <Spur>, <was realistisch ist>"`.
- Dem Nutzer einen Satz sagen.
- Direkt weiter mit Schritt 4.
- Trägt eine Figur mit Schauspiel den Kanal, das ehrlich in den Satz schreiben und trotzdem bauen.

## 4. Pilot bauen (Phase `pilot`)
**Originalton nur zum Messen.** Der Pilot übernimmt Ton, Zeitachse und Wortzeiten des Originals, damit Szene für Szene vergleichbar ist. Er wird nie veröffentlicht.
1. Anlegen: `__HEIM__/ms neu folge <slug>-pilot --kanal <slug> --pilot --vorlage <id>`. Trägt den Pilot im Kanal-Status ein und setzt dort die Phase `pilot` selbst.
2. Fenster wählen: ganzes Video oder ein Ausschnitt (bei langen Videos zuerst 10 bis 20 s, die den Kanal gut zeigen). Grenzen an Schnitte legen (Schnittliste in `kanaele/<slug>/analyse/<id>/analyse.json`, `szenen[]`).
3. Ton: `__HEIM__/ms stimme <pilot-id> --original [--von <s> --bis <s>]`. Ohne Angabe nimmt es die Vorlage aus STATUS.json. Ergebnis:
   - `voice/stimme.wav`: Originalton im Fenster, Tempo und Pausen unverändert, nur auf −14 LUFS gebracht. `--tempo` bricht beim Pilot ab.
   - `vorbild/ausschnitt.mp4`: das Original im selben Fenster, gleiche Zeitachse wie der Pilot (für `ms snap --gegen`, `ms vergleich`, den Prüfer).
   - `voice/script.json` (falls sie fehlt): gesprochener Text aus dem Transkript des Originals, tts = display.
4. Wortzeiten: `__HEIM__/ms woerter <pilot-id>`. Beim Pilot kommen sie aus dem Transkript des ganzen Originals (verschoben um `--von`), genauer als Whisper auf dem Ausschnitt.
   **Caption-Gruppen wie im Original:** `ms woerter` gruppiert nach `kit/captions.json` (max_woerter, max_zeichen, Pausen). Zeigen die Paarbilder zur selben Zeit anderen Caption-Text als das Original, die Gruppen von Hand übernehmen:
   - Gruppen ablesen: Paarbilder an den Caption-Wechseln (`__HEIM__/ms snap <pilot-id> <zeiten> --gegen __ARBEIT__/folgen/<pilot-id>/vorbild/ausschnitt.mp4`) oder Beispiele und Caption-Zone in `analyse/<id>/ANALYSE.md`.
   - Zeiten nur aus `voice/woerter.json`, nie schätzen: Gruppe `s` = `s` ihres ersten Worts, `e` = `s` der nächsten Gruppe (letzte Gruppe: `e` des letzten Worts + 0,25).
   - `build/captions.json` schreiben, jede Gruppe mit `"hand": true` (dann überschreibt `ms woerter` die Datei nicht mehr, neu gruppieren nur mit `--captions-neu`):
     `[{"text": "As soon as", "s": 3.33, "e": 3.85, "hand": true, "woerter": [{"w": "As", "s": 3.33, "e": 3.45}, {"w": "soon", "s": 3.45, "e": 3.62}, {"w": "as", "s": 3.62, "e": 3.80}]}, …]`
     `w` = Schreibweise wie im Original (Versalien und Satzzeichen am Wortende regelt der Caption-Stil). Bei `erscheinen: "wort"` erscheint jedes Wort auf seinem `s`.
   - Shot ohne Captions im Original (z. B. Titelkarte): in `build/scenes.json` an der Szene `"captions": false`.
   - Danach `__HEIM__/ms szenen <pilot-id>` und die Paarbilder an den Wechseln erneut ansehen.
5. Storyboard nach Skill **motion-storyboard**, aber aus der Schnittliste des Originals: eine Szene pro Shot, gleicher Inhalt, Zeit im Pilot = Zeit im Original − von, Überlappung 0,06 s wie dort. `build/scenes.json` schreiben, `__HEIM__/ms szenen <pilot-id> --check --plan` (Ende = Fensterlänge + 0,47 s). Soll der Pilot genau so lang sein wie der Ausschnitt: hier und in Schritt 6 `--auslauf 0` anhängen (Ende = Fensterlänge). Sobald index.html so geschrieben ist, übernehmen `ms szenen` (auch `--check` der Bauer) und `ms render` den Auslauf von selbst. Captions, die über das Ende hinausragen, werden dort gekappt.
6. Vor dem Bau: `__HEIM__/ms szenen <pilot-id> --plan` (index.html und Platzhalter je Szene). Dazu die **Bewegungsliste** je Einstellung wie in Skill motion-nachbau Schritt 2.4 (wie Dinge auftauchen, was sich dauerhaft bewegt, Details) und je Szene in den Bauer-Brief übernehmen.
7. Bau über **motion-bauer**: Starte alle Bauer in EINER Nachricht parallel über das Agent-Tool (subagent_type "motion-bauer", name "bauer-1", "bauer-2" …, `model` wie Helfer), 1 bis 2 Szenen pro Bauer, Brief-Vorlage aus motion-storyboard. Gemeinsame Konstanten (Overlay, Scanlines, Grundfarbe) vorab für alle festlegen. Im Brief: Referenzbilder des Originals pro Szene (Pfade aus `analyse/<id>/`), Paarbilder mit `__HEIM__/ms snap <pilot-id> <zeiten> --gegen __ARBEIT__/folgen/<pilot-id>/vorbild/ausschnitt.mp4`, Ziel „so nah wie möglich, gemessen“. Warten mit `__HEIM__/ms warte <pilot-id> --bauer bauer-1 …` im Hintergrund, dann die `build/fertig_*.json` lesen. Korrekturen nur über frische Bauer (`<name>-fix`, Brief mit Baunotiz), nie SendMessage an einen fertigen Bauer.
8. Ton beim Pilot: der Originalton ist fertig gemischt, `ms mix` entfällt.
9. `__HEIM__/ms szenen <pilot-id>` (Gate „Prüfung: OK“, kein Platzhalter mehr), dann Skill **motion-qa** mit `__HEIM__/ms render <pilot-id> pilot-v1` (im Hintergrund, dauert Minuten).
**Gate:** Video gerendert, Schwarzbild-Scan nur an Schnitten, Kontaktbogen angesehen. `__HEIM__/ms status <pilot-id> render`.

## 5. Messen (Phase `gemessen`)
1. Skill **motion-vergleich**: `__HEIM__/ms vergleich __ARBEIT__/folgen/<pilot-id>/vorbild/ausschnitt.mp4 __ARBEIT__/folgen/<pilot-id>/out/pilot-v1.mp4 --zeitversatz-suchen`. Der Ausschnitt hat dieselbe Zeitachse wie der Pilot. Wer das ganze Original übergibt: `ms vergleich` nimmt das Fenster dann aus `voice/stimme.json` (oder `--von/--bis`). Ergebnis: ΔE und SSIM pro Szene mit Ampel, Paarbögen (Original links, Nachbau rechts), Nebeneinander-Video. Die Gesamtwerte landen automatisch in der STATUS.json des Pilots (`messwerte`, Phase `vergleich`) und des Kanals.
2. Richtwerte aus unserem echten Nachbau (Spalte „grob“ im Ergebnis, so wurde dort gemessen):

   | Spur | erreicht | Ziel |
   |---|---|---|
   | 2D (Collage, Typo, UI) | ΔE 5,2, SSIM 0,84 | so nah wie dort |
   | 3D-Web (Three.js) | ΔE 16 | ΔE unter 15 (dort knapp verfehlt) |
   | Blender | nicht gemessen | erst Probe-Shot von 5 bis 8 s |
   Die Zahlen in der Tabelle sind die groben Werte von damals. Die Ampel pro Szene (grün, gelb, rot) rechnet das Werkzeug selbst mit feinem ΔE2000 und ist daran geeicht: 2D grün bei ΔE ≤ 6,5 und SSIM ≥ 0,65 (der abgenommene 2D-Nachbau ist damit komplett grün), 3D grün bei ΔE ≤ 11 (entspricht dem alten Ziel unter 15). ΔE heißt: wie weit die Farben auseinander liegen (unter 2 sieht man keinen Unterschied). SSIM heißt: wie ähnlich Formen und Kanten sind (1 = gleich).
3. Paarbögen immer selbst ansehen (Read-Tool). Eine gute Zahl beweist keinen gleichen Look.
4. **Eine Verbesserungsrunde** (wie motion-nachbau): die drei schlechtesten Szenen nach Zahlen plus die deutlichsten Bewegungs-Abweichungen, je Szene ein frischer Bauer mit Baunotiz, neu rendern, neu messen. Mehr Runden nur, wenn der Nutzer es nach seinem Urteil (Schritt 7) will.
**Gate:** jede Szene hat einen Messwert, keine Szene rot ohne Begründung, Gesamtwerte in der STATUS.json (`__HEIM__/ms status <folge-id>`).
`__HEIM__/ms status kanal:<slug> gemessen --notiz "ΔE <x>, SSIM <y> (grob), <n> Szenen grün"`.

## 6. Unabhängige Prüfung
Agent **motion-pruefer** (`subagent_type: "motion-pruefer"`), Brief nur mit Pfaden, kein Bau-Kontext:
„Prüfe den Pilot <pilot-id>. Video: out/pilot-v<n>.mp4, Original-Ausschnitt: vorbild/ausschnitt.mp4, Vergleich: out/vergleich_pilot-v<n>/, Kontaktbögen: out/qa_pilot-v<n>/, Storyboard: STORYBOARD.md, Regeln: kanaele/<slug>/BIBEL.md ([R]-Regeln, REGELN.md gibt es beim Pilot noch nicht).“
**Gate:** 0 kritische Befunde. Genau eine Prüfrunde: Befunde abarbeiten, neu rendern, neu messen, die geänderten Stellen selbst per Paarbild nachprüfen, kein zweiter Prüfauftrag. `ms status <folge-id> pruefung`.

## 7. Urteil des Nutzers (Gate)
Nebeneinander-Video öffnen (Original links, Nachbau rechts). Sag, was gleich ist, was nicht und warum, mit Messwerten.
`ms status kanal:<slug> --wartet "Pilot ansehen: passt der Stil so?"`. Sein Urteil wörtlich ins Lernlog.
Will er mehr Nähe: zurück zu Schritt 5. Passt es, dann erst jetzt die zwei Fragen (Teil B aus motion-format-finden), einzeln:
1. „Welche Arten von Videos willst du in diesem Stil machen? Worüber?“ → PROFIL.md: Nische und Thema, Zielgruppe.
2. „Was soll bei dir anders sein als beim Vorbild, dein eigener Twist?“ → PROFIL.md: Eigener Twist. Er fließt in REGELN.md und den Skript-Baukasten ein.
Dann weiter mit Schritt 8.

## 8. Baukasten (Phase `kit`)
Skill **motion-kanal-kit**: aus dem Pilot wiederverwendbare Bausteine nach `kanaele/<slug>/kit/` (lib, fonts, tex, beispiele), `kit/KATALOG.md`, `REGELN.md` (was den Stil ausmacht, als prüfbare Regeln), `kit/ton-rezept.json`, Captions-Stil.
**Gate:** KATALOG.md listet jeden Baustein mit Beispiel, REGELN.md hat mindestens 8 prüfbare Regeln, ton-rezept.json existiert. Weiter mit Schritt 9, der Status `kit` kommt erst mit dem Stil-Skill.

## 9. Stil-Skill (Pflicht vor `bereit`)
Der Stil-Skill ist die Bauanleitung, mit der jede spätere Sitzung ohne den Pilot-Kontext Szenen genau in diesem Stil baut.
1. `__HEIM__/ms stil <slug> anlegen` legt `__ARBEIT__/.claude/skills/stil-<slug>/SKILL.md` an: Zahlen, Palette, Captions, Bausteine, eigene Funktionen des Pilots und Pilot-Szenen füllt das Werkzeug selbst, alles andere ist mit AUSFÜLLEN markiert.
2. Jede AUSFÜLLEN-Stelle füllen, aus dem, was du beim Pilot gebaut und gemessen hast. Quelle sind die Pilot-Kompositionen (`folgen/<pilot>/build/compositions/*.html`), BIBEL, NACHBAU.md bzw. ANALYSE.md (Bewegungsliste), VERGLEICH.md, der Prüfbericht und die Korrekturen des Nutzers. Maßstab: **Eine frische Sitzung, die nur diesen Skill liest, baut eine Szene, die neben dem Pilot nicht auffällt.** Deshalb:
   - **Szenentypen** (mindestens vier, je `### <Name>`): wann, Ebenen von außen nach innen, Bausteine mit genauem Aufruf und Werten, Zeiten in s (Auftauchen, Halten, Abgang), Easing, Kamera, Beispiel mit Datei und Zeit.
   - **Bausteine:** Wie jeder im Pilot benutzte Baustein im Stil aufgerufen wird, mit den Werten aus dem Pilot (`MS2D.kameraPunch(tl, kamera, 2.40, {staerke: 1.08})`, nicht „Kamera-Punch nutzen“). Eigene Funktionen des Pilots, die wiederkommen werden: ins Kit (Skill motion-kanal-kit) und hier mit Aufruf.
   - **Bewegung, Übergänge:** Zahlen statt Adjektive (s, %, px, Easing-Name).
   - **Farben und Schrift:** jede Farbe mit Rolle, Schrift mit Gewicht und Größe in px.
   - **Abnahme:** mindestens acht prüfbare Kriterien mit Schwelle (z. B. „Caption-Oberkante y 1470 ±10 px“, „Hintergrund #101010, ΔE gegen Pilot unter 3“).
   - **Beispiele:** mindestens drei Pilot-Stellen mit Datei und Zeit.
3. `__HEIM__/ms stil <slug> pruefen` muss OK melden (keine AUSFÜLLEN-Stelle, Mindestzahlen erreicht).
4. **Stil-Test (eine Szene, frischer Bauer, Test für Entscheidung 2):** Kann eine frische Sitzung NUR mit dem Skill eine Szene im Stil bauen?
   - `__HEIM__/ms neu folge <slug>-stiltest --kanal <slug> --stiltest --vorlage <id des Pilot-Videos>` (wie ein Pilot mit Originalton, wird nie gepostet, ändert den Kanal nicht).
   - `__HEIM__/ms stimme <test-id> --original --von <start> --bis <ende>` mit dem Fenster EINER typischen Pilot-Szene (3 bis 6 s), `ms woerter <test-id>`, `build/scenes.json` mit dieser einen Szene, `ms szenen <test-id> --plan`.
   - Frischer motion-bauer `stiltest`, Brief nur mit Szene, Wortzeiten, Szenentyp, Inhalt und dem Pfad des Stil-Skills. Kein Pilot-Code, keine Referenzbilder, keine Bewegungsliste: Der Skill muss reichen.
   - Danach `__HEIM__/ms snap <test-id> --szene s1 --raster 0.5 --gegen __ARBEIT__/folgen/<test-id>/vorbild/ausschnitt.mp4` und den Paarbogen ansehen (Original links, Test rechts), daneben den Pilot-Bogen derselben Stelle.
   - Weicht der Test sichtbar ab (Farbe, Schrift, Bewegung, Kamera, Ebenen): Im Skill fehlt etwas. Den Skill ergänzen, nicht die Testszene reparieren. Ergebnis (gleich / Abweichungen / was ergänzt wurde) als Zeile unter „Pflege“ und im Lernlog.
`ms status kanal:<slug> kit --notiz "Stil-Skill OK, Stil-Test <ergebnis>"`.

## 10. Bereit
1. Ideenliste anlegen, falls sie fehlt: `__HEIM__/ms ideen <slug> anlegen`. Hat der Nutzer in Schritt 7 schon Themen genannt: `ms ideen <slug> neu "<Thema>" --eigen`. Schema und Auffüllen macht Skill motion-ideen (Pack 4 Prompt 2), das muss nicht jetzt sein.
2. `__HEIM__/ms status kanal:<slug> bereit --notiz "Pilot ΔE <x>, Kit <n> Bausteine, Stil-Skill OK"`, Pilot `ms status <folge-id> fertig`.
3. Lernlog: Datum, Kanal, Spur, Messwerte, was schwer war, Dauer, Kosten, `__HEIM__/ms verbrauch <pilot-id>`.
4. Dem Nutzer den nächsten Schritt nennen: die erste eigene Folge. Sie startet in einer **frischen Sitzung** (diese hier ist nach dem Lernen sehr lang, jeder weitere Schritt wäre teuer): `__HEIM__/ms starten folge --kanal <slug>` bzw. „Bau die nächste Folge“ in einer neuen Regie-Sitzung. Die Fragen der Folge erscheinen im Studio.

## Bekannte Fallen
- Instagram lädt ohne Login fast nie. Keine Browser-Cookies verwenden. Apify (mit Ja) oder selbst speichern.
- Eine Kennzahl beweist keinen gleichen Look. Immer auch die Paarbögen ansehen.
- Der Pilot ist eine Übung und wird nie gepostet (fremde Inhalte, fremde Stimme). `ms posten pruefen` lässt ihn nicht durch.
- Stil-Skill mit Adjektiven statt Zahlen („dynamisch“, „weich“) hilft keiner frischen Sitzung. Jede Aussage mit Zahl, Aufruf oder Beispiel.
- Szenen nicht schätzen, sondern aus der Schnittliste übernehmen. Ein Versatz von 0,2 s verdirbt den Vergleich.
