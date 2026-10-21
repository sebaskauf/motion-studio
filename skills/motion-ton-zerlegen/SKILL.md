---
name: motion-ton-zerlegen
description: Den Ton eines Vorbild-Videos messen (Lautheit in LUFS, Sprechtempo in Wörtern pro Sekunde, Pausen, Musikbett ja/nein und wie leise darunter, Effekt-Momente mit AudioSet-Klassen). Laden bei "Ton analysieren", "wie laut", "wie schnell spricht er", "Musik drunter", "welche Soundeffekte", "Sound-Design zerlegen", "LUFS".
---

# Ton zerlegen

Ziel: `ton.json`, `TON.md` und `ton.png` im Analyse-Ordner des Videos, der Ton-Abschnitt steht auch in ANALYSE.md. Daraus entstehen die Ton-Regeln der BIBEL (Lautheit, Tempo, Bett, Effekte).

## Befehle

- Standard: `__HEIM__/ms ton-zerlegen <id> --kanal <slug>` (rund 15 bis 30 s für ein 30-s-Video).
- Genauer, wenn demucs installiert ist: `__HEIM__/ms ton-zerlegen <id> --kanal <slug> --trennen`. Trennt Stimme und Rest, sucht Effekte im Rest und misst, wie viele dB das Bett unter der Stimme liegt (rund 30 s zusätzlich auf der CPU).
- Video ohne Tonspur, Ton als eigene Datei: `--ton <datei.m4a>`. Liegt `<name>.m4a` oder `audio.m4a` neben dem Video, findet das Werkzeug sie selbst.
- Nur Transkript: `__HEIM__/ms transkript <id>` (schreibt `__ARBEIT__/vorlagen/transkripte/<id>.json` + `.txt`).

## Was du daraus liest

| Wert | Wo | Wofür |
|---|---|---|
| Lautheit (LUFS, LRA, True Peak) | `lufs`, `lra`, `true_peak` | Mix-Ziel. Kurzvideos liegen meist um −14 LUFS |
| Sprechtempo | `sprache.woerter_pro_s`, `wpm`, `pausen` | Tempo-Fit der eigenen Stimme, Wortbudget im Skript |
| Musik | `musik.urteil`, `grundpegel_db`, `abstand_db`, mit AST `ast.musik_wahrscheinlichkeit` | Bett ja/nein und wie leise unter der Stimme |
| Bett-Abstand (nur `--trennen`) | `trennung.rest_unter_stimme_db` | Pegel des Betts im eigenen Mix |
| Effekt-Kandidaten | `effekte[]` mit `t`, `staerke`, `breitband`, `in_pause`, `am_schnitt`, `urteil`, `effekt_klasse` | Wo sitzen Effekte, an Schnitten oder auf Aktionen? Welche Art (Whoosh, Pop, Ding)? |

`ton.png` zeigt Pegel, Sprechzeit (grün), gemessene Pausen (gelb), Kandidaten (rot = aus einer Pause, orange = breitbandig, dick = sicher) und Schnitte (grau). Beschriftet sind nur Kandidaten, bei denen AST einen Effekt hört.

## Ablauf

1. `ms ton-zerlegen` nach `ms zerlegen` laufen lassen, dann bekommen Kandidaten den Bezug zu den Schnitten (`am_schnitt`).
2. `ton.png` mit dem Read-Werkzeug ansehen.
3. In die BIBEL übernehmen: Lautheit und Tempo als [B] mit Zahl. Musik und Bett als [B], wenn AST oder die Trennung es stützen, sonst [P]. Effekt-Arten als [P], solange niemand sie angehört hat.
4. Den Nutzer bitten, 3 bis 5 Kandidaten mit "Effekt wahrscheinlich" kurz anzuhören (Zeitstempel nennen). Du selbst kannst nicht hören.

## Gate (fertig, wenn)

- `ton.json` vorhanden, Lautheit, Sprechtempo und Musik-Urteil stehen in ANALYSE.md.
- `ton.png` angesehen.
- In der BIBEL sind Ton-Aussagen als [B] oder [P] markiert, keine Effekt-Art als [B] ohne Anhören oder AST ≥ 0,15.

## Gemessen (Richtwerte)

- Zwei 30-s-Reels mit Stimme und Bett: −14,1 LUFS, 4,2 bis 4,3 Wörter/s (rund 255 wpm). Mit `--trennen`: Rest 12,4 dB unter der Stimme, das deckt sich mit einer früheren Handmessung (rund 12 dB).
- Ohne Trennung sind Effekte in dichter Sprache mit Musikbett schwer zu finden: viele Kandidaten heißen dann "eher Sprache". Mit `--trennen` hört AST im Rest echte Effekt-Klassen (Ding, Clink, Slap, Sound effect).

## Fallen

- whisper setzt Wortgrenzen lückenlos. Pausen kommen deshalb aus dem Pegel im Sprachband (300 bis 3400 Hz), nicht aus dem Transkript. Pausen unter 0,2 s sind nicht belastbar.
- Onsets sind keine bewiesenen Soundeffekte. Musik-Schläge und Silben erzeugen auch Einsätze. Das Urteil je Kandidat sagt, was AST hört.
- AST braucht torch und transformers, das Modell (rund 350 MB) lädt beim ersten Lauf. Ohne steht im Bericht "nicht installiert", der Rest läuft trotzdem.
- demucs auf Apple Silicon: das Werkzeug erzwingt `-d cpu`, weil MPS mit "Output channels > 65536" abbricht.
- Instagram-Videos aus Apify haben oft keine Tonspur. `ms laden` führt Video und Tonlink zusammen.
- Transkript ohne Satzzeichen (passiert bei Musik unter der Stimme): `saetze_aus_pausen` ist dann `true`, die Sätze sind an Pausen geschnitten.
- Nie Original-Musik oder Original-Effekte in eigene Folgen übernehmen. Gemessen wird nur, wie der Kanal klingt.
