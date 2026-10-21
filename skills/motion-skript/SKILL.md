---
name: motion-skript
description: "Skript einer Motion-Studio-Folge schreiben: Vorlage Satz für Satz in die Kanalsprache aus PROFIL.md übertragen, Hook inhaltlich gleich und in der Zielsprache catchy, gesprochene Sprache statt Schulübersetzung, Wortzahl ±15 %, eigene Note statt Kopie, CTA nach SKRIPT-BAUKASTEN.md, SKRIPT.md und voice/script.json mit Sprechtext (tts) und Anzeigetext (display), Aussprache-Liste. Laden bei \"Skript\", \"Skript schreiben\", \"übersetzen\", \"Hook\", \"script.json\", \"Sprechtext\", \"Anzeigetext\", \"Aussprache\", Phase skript."
---

# motion-skript

Eingang: Transkript der Vorlage (`STATUS.json` Feld `vorlage.transkript`, sonst `__ARBEIT__/vorlagen/transkripte/<id>.json`), `__ARBEIT__/PROFIL.md` (Sprache, Ton, Zielgruppe, Anrede), `kanaele/<k>/SKRIPT-BAUKASTEN.md` (Hook-Formeln, Aufbau, CTA-Muster), `kanaele/<k>/BIBEL.md`, `kanaele/<k>/AUSSPRACHE.json`.
Ausgang: `folgen/<id>/SKRIPT.md` und `folgen/<id>/voice/script.json`. Danach `__HEIM__/ms status <folge> skript --notiz "<n> Wörter, Hook: <erste Wörter>"`.

## 1. Vorlage verstehen
- Transkript ganz lesen. Bausteine markieren (Hook, Re-Hook, Ursache, Mechanismus, Beleg, Nutzen, CTA) wie im SKRIPT-BAUKASTEN.
- Wortzahl der Vorlage notieren. Ziel: eigene Wortzahl ±15 %.
- Sprache der Vorlage gegen die Kanalsprache im PROFIL: anders → übertragen; gleich → neu formulieren (nie wörtlich übernehmen).

## 2. Satz für Satz übertragen
- Gleicher Inhalt, gleiche Reihenfolge, ähnliche Satzlänge. Keine neuen Abschnitte, keine gestrichenen Bausteine.
- **Gesprochene Sprache, keine Schulübersetzung.** Prüffrage für jeden Satz: Würde ein Creator in dieser Sprache genau so in die Kamera sprechen? Wenn nein: umbauen, bis es natürlich klingt.
  Schlecht: „Dieses Werkzeug wird es dir ermöglichen, Zeit einzusparen.“ Gut: „Mit dem Tool sparst du dir jeden Tag Stunden.“
- Kurze Sätze, Du- oder Sie-Form laut PROFIL. Fachbegriffe, die man im Original-Englisch sagt, bleiben englisch (Plugin, Repo, Prompt).
- **Eigene Note statt Kopie:** Beispiele, Bilder und Vergleiche gern auf die Zielgruppe aus dem PROFIL drehen, Ton des Kanals treffen. Die Aussage bleibt gleich.
- **Ich-Sätze neutralisieren**, die der Nutzer nicht selbst erlebt hat: „I tested 100 tools“ → „Es gibt hunderte Tools, aber diese fünf …“.
- Füllwörter sparsam, Tonfall-Marker aus dem SKRIPT-BAUKASTEN gezielt einsetzen.

## 3. Hook (erster Satz, zuerst prüfen)
- **Inhaltlich gleich wie die Vorlage**, nicht entschärfen, nicht neu erfinden.
- In der Zielsprache catchy: dort umbauen, wo die wörtliche Fassung holpert oder fremd klingt. Prüfstein: Würde ein Creator in dieser Sprache genau diesen Satz sagen?
- Die Hook-Formel aus dem SKRIPT-BAUKASTEN muss erkennbar bleiben.

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
Kopf mit Vorlage (Link, Creator, Wortzahl). Dann Tabelle: Baustein | Vorlage | eigener Satz. Darunter Wortzahl, geschätzte Dauer, CTA-Keyword, offene Fragen an den Nutzer.

## Gate
1. `__HEIM__/ms stimme <folge> --text` (kostet nichts): Wortzahl im Rahmen ±15 % zur Vorlage, keine Warnung zu Sonderzeichen oder Ziffern im Sprechtext, tts und display gleich viele Wörter.
2. Hook inhaltlich wie die Vorlage, Formel erkennbar, klingt gesprochen.
3. Kein Baustein fehlt, keine Aussage still verändert, Rückfragen gestellt.
4. `__HEIM__/ms status <folge> skript --notiz "…"`.
