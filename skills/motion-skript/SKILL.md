---
name: motion-skript
description: "Skript einer Motion-Studio-Folge schreiben. Standard: EIGENE Folge, Inhalt neu aus der Idee (Ideenliste, Nische, Twist), von der Vorlage nur Form, Länge, Tempo und Hook-Formel aus SKRIPT-BAUKASTEN.md. Nur für eine Kopie (motion-nachbau) wird eine Vorlage Satz für Satz übertragen. Gesprochene Sprache, Wortzahl ±15 %, Belege mit Datum, CTA, SKRIPT.md und voice/script.json mit Sprechtext (tts) und Anzeigetext (display), Aussprache-Liste. Laden bei \"Skript\", \"Skript schreiben\", \"übersetzen\", \"Hook\", \"script.json\", \"Sprechtext\", \"Anzeigetext\", \"Aussprache\", Phase skript."
---

# motion-skript

Zwei Modi (Sebastian 30.10.2026, Pack 3 Prompt 2):
- **Eigene Folge (Standard, motion-folge):** Der Inhalt ist neu. Er kommt aus der Idee der Folge (STATUS `idee`, Ideenliste), der Nische, Zielgruppe und dem Twist aus PROFIL.md. Die Vorlage (STATUS `vorlage`, Rolle `bauplan`) ist nur der Bauplan: Form, Länge, Tempo, Aufbau und die Hook-FORMEL. Kein Satz, kein Beispiel, keine Geschichte aus der Vorlage.
- **Übertragung (nur Kopie, Skill motion-nachbau, STATUS art `kopie`):** Vorlage Satz für Satz in die Kanalsprache. Eine Kopie wird nie automatisch gepostet.

Eingang: `__ARBEIT__/PROFIL.md` (Sprache, Ton, Zielgruppe, Anrede, Nische, Twist), `kanaele/<k>/SKRIPT-BAUKASTEN.md` (Hook-Formeln, Aufbau, CTA-Muster), Stil-Skill `__ARBEIT__/.claude/skills/stil-<k>/SKILL.md` (Länge, Tempo), Transkript des Bauplans (`STATUS.json` Feld `vorlage.transkript`, sonst `__ARBEIT__/vorlagen/transkripte/<id>.json`), `kanaele/<k>/AUSSPRACHE.json`.
Ausgang: `folgen/<id>/SKRIPT.md` und `folgen/<id>/voice/script.json`. Danach `__HEIM__/ms status <folge> skript --notiz "<n> Wörter, Hook: <erste Wörter>"`.

## 1. Bauplan lesen (beide Modi)
- Transkript ganz lesen. Bausteine markieren (Hook, Re-Hook, Ursache, Mechanismus, Beleg, Nutzen, CTA) wie im SKRIPT-BAUKASTEN.
- Wortzahl notieren. Ziel: eigene Wortzahl ±15 %. Tempo (Wörter/s) und Satzlänge merken.
- Eigene Folge: Notiere nur die FORM (welcher Baustein an welcher Stelle, wie lang, welche Hook-Formel). Den Inhalt vergisst du wieder.

## 2a. Eigene Folge: neu schreiben
1. **Recherche zur Idee:** Was ist die eine Frage, die die Folge beantwortet? Zwei bis vier Fakten, die das tragen, jede mit Quelle und Datum (Websuche, wenn nötig). Was nicht belegt ist, kommt nicht rein.
2. **Hook nach Formel, Inhalt eigen:** Formel aus dem SKRIPT-BAUKASTEN wählen (z. B. „Du benutzt X jeden Tag, aber …“, „Dieses Y kann Z, und das ist der Grund“) und mit der eigenen Idee füllen. Der Hook darf inhaltlich nicht der Hook der Vorlage sein. Prüfstein: Würde ein Creator in dieser Sprache genau diesen Satz sagen?
3. **Aufbau wie der Bauplan:** gleiche Bausteine in gleicher Reihenfolge und ähnlicher Länge, aber mit dem eigenen Inhalt. Der Twist aus dem Profil muss erkennbar sein (Thema, Sprache, Storytelling, Sound oder Animation).
4. Gesprochene Sprache wie unten (Abschnitt 3), CTA wie unten (Abschnitt 5).
5. Selbstkontrolle: Lege Bauplan-Transkript und dein Skript nebeneinander. Steht irgendwo derselbe Satz, dasselbe Beispiel oder dieselbe Pointe: neu schreiben.

## 2b. Kopie: Satz für Satz übertragen
- Gleicher Inhalt, gleiche Reihenfolge, ähnliche Satzlänge. Keine neuen Abschnitte, keine gestrichenen Bausteine. Sprache der Vorlage gegen die Kanalsprache: anders → übertragen; gleich → neu formulieren (nie wörtlich übernehmen).
- Hook inhaltlich gleich wie die Vorlage, in der Zielsprache catchy.
- Ich-Sätze neutralisieren, die der Nutzer nicht selbst erlebt hat: „I tested 100 tools“ → „Es gibt hunderte Tools, aber diese fünf …“.

## 3. Gesprochene Sprache (beide Modi)
- **Keine Schulübersetzung, kein Aufsatz.** Prüffrage für jeden Satz: Würde ein Creator in dieser Sprache genau so in die Kamera sprechen? Wenn nein: umbauen, bis es natürlich klingt.
  Schlecht: „Dieses Werkzeug wird es dir ermöglichen, Zeit einzusparen.“ Gut: „Mit dem Tool sparst du dir jeden Tag Stunden.“
- Kurze Sätze, Du- oder Sie-Form laut PROFIL. Fachbegriffe, die man im Original-Englisch sagt, bleiben englisch (Plugin, Repo, Prompt).
- Füllwörter sparsam, Tonfall-Marker aus dem SKRIPT-BAUKASTEN gezielt einsetzen.

## 4. Falsche oder veraltete Aussagen
- Nicht still ändern. Fällt dir eine grob falsche oder veraltete Aussage auf (falsche Zahl, eingestelltes Produkt, alter Modellname): dem Nutzer melden mit Vorschlag.
  `__HEIM__/ms status <folge> --wartet "Aussage X wirkt veraltet: … Vorschlag: … Ändern?"`, nach der Antwort `--wartet-weg`.
- Steht im PROFIL „Skript vor dem Bau zeigen: ja“, das ganze Skript zeigen und auf Ja warten.

## 5. CTA
Nach dem Muster aus SKRIPT-BAUKASTEN.md (Wortlaut, Platz, Keyword-Form). Keyword kurz, in Großbuchstaben, aus dem Thema. Der CTA verspricht nur, was es wirklich gibt.

## 6. voice/script.json
```json
{"sprache": "de",
 "tts": ["Satz 1 so, wie die Stimme ihn lesen soll.", "Satz 2 …"],
 "display": "Der ganze Text so, wie er in den Captions steht."}
```
- **tts** (Sprechtext): Zahlen ausgeschrieben („zwölf“, „dreihunderttausend“, „zehnmal“), Abkürzungen ausgeschrieben („zum Beispiel“), keine Klammern, keine Emojis, keine Schrägstriche. Namen in der Schreibweise aus `kanaele/<k>/AUSSPRACHE.json`. Ein Satz pro Listeneintrag.
- **display** (Anzeigetext): gleicher Wortlaut, aber Ziffern („300.000“, „10-mal“), richtige Schreibweise der Namen, Keyword groß.
- **Wortgrenzen müssen passen:** „dreihunderttausend“ ↔ „300.000“ ist ein Wort auf beiden Seiten, gut. Ein Satz, der nur in einem der beiden steht, senkt die Zuordnung in `ms woerter`.
- Homophone meiden: was Whisper falsch hört, hört der Zuschauer oft auch falsch.
- `sprache` = Sprachkürzel der Stimme (de, en, …), hilft Whisper.

## 7. AUSSPRACHE.json (pro Kanal)
```json
{"Nginx": "Engine-X", "SQL": "Es-Ku-El", "_hinweis": "Schreibweise im Text → so liest die Stimme"}
```
`ms stimme` wendet die Liste vor jeder Erzeugung automatisch auf tts an. Neue Einträge nur nach Hörprobe (Skill motion-stimme, Aussprache-Test). Schlüssel mit `_` werden ignoriert.

## 8. SKRIPT.md
Kopf: Idee, Twist, Bauplan (Link, Creator, Wortzahl, welche Form übernommen). Dann Tabelle: Baustein | Form im Bauplan (z. B. „Hook: Alltagsding + Überraschung, 9 Wörter“) | eigener Satz. Darunter Quellen mit Datum, Wortzahl, geschätzte Dauer, CTA-Keyword, offene Fragen an den Nutzer. Bei einer Kopie statt der Form-Spalte der Satz der Vorlage.

## Gate
1. `__HEIM__/ms stimme <folge> --text` (kostet nichts): Wortzahl im Rahmen ±15 % zur Vorlage, keine Warnung zu Sonderzeichen oder Ziffern im Sprechtext, tts und display gleich viele Wörter.
2. Eigene Folge: Hook folgt einer Formel, Inhalt eigen, kein Satz aus der Vorlage, jede Behauptung mit Quelle. Kopie: Hook inhaltlich wie die Vorlage. Beides: klingt gesprochen.
3. Kein Baustein des Bauplans fehlt, keine Aussage still verändert, Rückfragen gestellt.
4. `__HEIM__/ms status <folge> skript --notiz "…"`.
