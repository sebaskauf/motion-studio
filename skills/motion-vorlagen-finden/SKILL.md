---
name: motion-vorlagen-finden
description: Vorbild-Videos eines Motion-Design-Kanals ins Register holen und die stärksten Ausreißer auswählen (Views, Faktor gegen den Kanal-Median). Laden bei "Vorlagen finden", "welche Videos laufen", "Kanal scannen", "Top-Videos", "Ausreißer", "YouTube-Shorts holen", "Reels holen", "TikToks holen", "Apify", "nächste Vorlage".
---

# Vorlagen finden

Ziel: Das Register `__ARBEIT__/vorlagen/register.json` kennt die Videos des Vorbilds mit Views und Datum. Daraus wählst du 3 bis 5 Ausreißer, die nachgebaut oder als Vorlage für Folgen genutzt werden.

## Quellen

| Quelle | Befehl | Kosten | Was du bekommst |
|---|---|---|---|
| YouTube-Shorts | `__HEIM__/ms vorlagen yt @kanal --max 60` | gratis | Views aus der Kanalliste, Datum und genaue Views der 15 neuesten aus dem RSS-Feed |
| YouTube genau | `__HEIM__/ms vorlagen yt @kanal --max 60 --genau` | gratis | Datum, Dauer, Likes für jedes Video, rund 1 s pro Video |
| Lange YouTube-Videos | `__HEIM__/ms vorlagen yt @kanal --tab videos` | gratis | wie oben, Tab "Videos" |
| TikTok | `__HEIM__/ms vorlagen tiktok @kanal --max 30` | gratis | Views, Likes, Datum. Scheitert ohne Login manchmal, dann Einzellinks |
| Instagram | `__HEIM__/ms vorlagen apify @kanal --anzahl 30` | ca. 0,0026 $ pro Reel (Free-Plan, Stand 20.10.2026) | Views, Likes, Datum, Dauer, Video- und Tonlink |
| Einzelner Link | `__HEIM__/ms vorlagen add <url> --views 250000` | gratis | ein Eintrag. Instagram-Views ohne Login nur von Hand |
| Apify-Export | `__HEIM__/ms vorlagen import <datei.json>` | gratis | Export aus der Apify-Konsole |

## Ablauf

1. Kanal lesen (Tabelle oben). Gratis-Quellen zuerst.
2. Instagram nur über Apify und nur mit Ja:
   - `__HEIM__/ms vorlagen apify @kanal --anzahl 30` zeigt nur die Schätzung und führt nichts aus.
   - Frage stellen: `__HEIM__/ms status kanal:<slug> --wartet "Apify: 30 Reels von @kanal für ca. 0,08 $ holen?"`
   - Erst nach dem Ja: derselbe Befehl mit `--ja`. Danach `--wartet-weg` und den Ist-Betrag buchen, nicht die Schätzung. Das Werkzeug bucht nicht selbst, es nennt den Betrag am Ende („Status SUCCEEDED, 30 Ergebnisse, Kosten 0.071 $“): `__HEIM__/ms status kanal:<slug> --kosten 0.071 USD "Apify 30 Reels @kanal"`.
   - Fehlt `APIFY_TOKEN` in `__ARBEIT__/.env`: Nutzer bitten, ihn dort einzutragen. Den Wert nie lesen oder ausgeben.
3. Ausreißer filtern: `__HEIM__/ms vorlagen liste --creator <name> --min-views 100000 --faktor 2`.
   Faktor = Views geteilt durch den Median des Creators auf derselben Plattform. Der Median zählt nur Videos, die mindestens 3 Tage alt sind, und braucht mindestens 3 Werte. Er steht über der Tabelle.
4. Auswählen (3 bis 5 IDs):
   - höchster Faktor zuerst, bei Gleichstand mehr Views
   - typisches Format des Kanals, nicht der eine Ausreißer in fremdem Look
   - Dauer 15 bis 90 s, mit Ton
   - für den Pilot: ein Video, das die Machbarkeit nicht sprengt (siehe motion-video-zerlegen, Typ)
5. Status pflegen: `__HEIM__/ms vorlagen set <id> uebersprungen --notiz "Repost von <id>"`. Status: `neu`, `geladen`, `zerlegt`, `genutzt`, `uebersprungen`. `ms laden` und `ms zerlegen` setzen ihren Status selbst.
6. Weiter: `__HEIM__/ms laden <id> --kanal <slug>` (Skill motion-video-zerlegen).

## Gate (fertig, wenn)

- Register enthält mindestens 10 Videos des Vorbilds mit Views, der Median wird angezeigt.
- 3 bis 5 ausgewählte IDs mit Begründung (Views, Faktor, Format) an die Regie gemeldet.
- Kein bezahlter Lauf ohne Ja des Nutzers, jede Ausgabe in STATUS.json gebucht.

## Fallen

- Videos jünger als 3 Tage sammeln noch Views. Nie nach ihnen auswählen, sie zählen auch nicht im Median.
- Der Shorts-Tab liefert gerundete Views (1,1M). Genaue Zahlen: RSS (neueste 15) oder `--genau`.
- Kanäle laden dasselbe Video oft doppelt hoch (anderer Titel, anderes Cover). Dauer und Titel vergleichen, Dublette auf `uebersprungen`.
- Apify-Videolinks laufen nach wenigen Tagen ab. Nach dem Import bald `ms laden`.
- yt-dlp aktuell halten. Alte Versionen brechen YouTube-Downloads bei rund 10 MB mit "403 Forbidden" ab.
- Nie Browser-Cookies oder Logins des Nutzers verwenden (kein `--cookies-from-browser`).
- Wenige Videos pro Creator (unter 3 mit Datum) ergeben keinen Faktor. Dann nur nach Views entscheiden und das sagen.
