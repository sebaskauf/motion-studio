---
name: motion-skript-zerlegen
description: Aus 3 bis 5 Transkripten eines Vorbild-Kanals einen Skript-Baukasten machen (Bausteine Hook, Ursache, Mechanismus, Re-Hook, Beleg, Nutzen, CTA, Hook-Formeln, Wortzahl, Dauer, Tempo, Themen-Muster). Ergebnis kanaele/<slug>/SKRIPT-BAUKASTEN.md. Laden bei "Skript zerlegen", "wie sind die Skripte gebaut", "Hook-Formeln", "Skript-Baukasten", "Wortbudget", "Themen des Kanals".
---

# Skript zerlegen

Ziel: `__ARBEIT__/kanaele/<slug>/SKRIPT-BAUKASTEN.md`, mit dem der Skill motion-skript neue Skripte im Ton des Kanals schreibt. Struktur übernehmen, Wortlaut nie.

## Eingaben

- 3 bis 5 Transkripte der stärksten Videos (`__ARBEIT__/vorlagen/transkripte/<id>.json` und `.txt`, entstehen bei `ms laden`).
- Views und Faktor je Video (`__HEIM__/ms vorlagen liste --creator <name>`).
- Optional: `analyse/<id>/ANALYSE.md` für Schnitt-Rhythmus und Captions.

## Ablauf

1. Kennzahlen holen:
   `__HEIM__/ms transkript --uebersicht __ARBEIT__/vorlagen/transkripte/<id1>.json __ARBEIT__/vorlagen/transkripte/<id2>.json …`
   Ergibt je Video Sprechdauer, Wörter, Wörter/s, Sätze, ersten Satz (Hook) mit Dauer und letzten Satz, dazu den Median.
2. Jeden Satz einem Baustein zuordnen (eine Tabelle pro Video mit Zeit und Anteil an der Laufzeit):

   | Baustein | Frage, die er beantwortet |
   |---|---|
   | Hook | Warum bleibe ich? (erste 1 bis 3 s) |
   | Ursache | Was ist passiert, was steckt dahinter? |
   | Mechanismus | Wie funktioniert es? |
   | Re-Hook | Neue Spannung in der Mitte ("Und jetzt kommt's …") |
   | Beleg | Zahl, Vergleich, Demo, Quelle |
   | Einschränkung | Wo gilt es nicht? |
   | Nutzen | Was habe ich davon? |
   | CTA | Was soll ich tun (Kommentar-Stichwort, Folgen, Speichern)? |

   Reihenfolge und fehlende Bausteine notieren. Re-Hook-Position in Prozent der Laufzeit angeben.
3. Hook-Formeln bestimmen. Jede Hook einer Formel zuordnen, neue Formeln ergänzen. Das ist eine Ordnung, kein Wirkungsbeweis:
   - Neuheit + Marke: "X hat gerade Y gebracht"
   - Zahl oder Vergleich: "A schlägt B um 30 %"
   - Problem und Lösung: "Wenn dir X passiert, mach Y"
   - Gegen die Erwartung: "Alle machen X falsch"
   - Frage: "Was passiert, wenn …?"
   - Was-wäre-wenn: "Was, wenn du nie wieder schläfst?"
   - Du + Nutzen: "Damit sparst du …"
   - Warnung: "Hör auf, X zu tun"
   - Geheimnis: "Das zeigt dir keiner"
   - Vorher und nachher
   - Liste: "3 Dinge, die …"
4. Tempo und Länge: Median Wörter/s, Sprechdauer, Wörter pro Satz, Hook-Dauer. Wortbudget = Wörter/s × Zieldauer, aber mit der eigenen Stimme nachmessen (andere Sprache, andere Silbenzahl).
5. Themen-Muster: Welche Themen, welcher Anlass (News, Erklärung, Mythos, Anleitung), wiederkehrende Bildidee pro Abschnitt (z. B. ein Objekt, dessen Zustand das Ergebnis trägt).
6. SKRIPT-BAUKASTEN.md schreiben (Gliederung unten), jede Aussage mit [B] beobachtet, [P] vermutet oder [R] unsere Regel und mit Quelle (Video-ID, Zeit).

## Gliederung von SKRIPT-BAUKASTEN.md

```
# Skript-Baukasten <Kanal>
Quellen: <id> (Views, Faktor), …
## Messwerte            Tabelle aus ms transkript --uebersicht + Median, Wortbudget für 30/45/60 s
## Bausteine            Reihenfolge-Varianten mit Anteil an der Laufzeit, Re-Hook-Position
## Hook-Formeln         Formel, Original-Beispiel (kurz), Schablone in Zielsprache, wie oft
## Beleg und Nutzen     Arten von Belegen (Zahl, Demo, Vergleich), wie konkret
## CTA                  Wortlaut-Muster, Dauer, Position
## Themen-Muster        was läuft, was nie vorkommt, Anlass
## Regeln [R]           6 bis 10 Regeln für neue Skripte
## Offen                was 3 bis 5 Videos nicht beantworten
```

## Gate (fertig, wenn)

- Mindestens 3 Transkripte ausgewertet, Messwerte-Tabelle mit Median.
- Jeder Baustein mit mindestens einem Beispiel (Zeit, Video-ID).
- Mindestens 3 Hook-Formeln mit Schablone in der Zielsprache.
- Wortbudget für die Ziel-Längen steht da.
- Alle Aussagen mit [B], [P] oder [R] markiert.

## Fallen

- Häufigkeit ist kein Wirkungsbeweis. Fünf Top-Videos zeigen, was bei Top-Videos vorkommt, nicht was sie erfolgreich macht.
- Transkripte ohne Satzzeichen (`saetze_aus_pausen: true`) sind an Pausen geschnitten: Sätze nach Sinn selbst setzen.
- Whisper verhört Marken- und Fachbegriffe. Im Zweifel die Captions im Video (ANALYSE.md, Abschnitt Captions) gegenlesen.
- Kein Satz wird 1:1 übernommen. Formeln und Längen ja, Wortlaut nein.
- Tempo nicht blind übertragen: Deutsch braucht oft mehr Silben pro Aussage als Englisch. Das endgültige Timing kommt aus der eigenen Stimmspur.
