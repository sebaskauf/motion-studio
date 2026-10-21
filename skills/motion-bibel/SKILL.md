---
name: motion-bibel
description: BIBEL.md eines Kanals schreiben, die Stil-Bibel aus den Analysen mit klarer Trennung [B] beobachtet, [P] vermutet, [R] unsere Regel (Format, Typ und Machbarkeit, Bildwelt, Palette, Schriften, Captions, Kamera, Schnitt, Übergänge, Effekte, Figuren, Ton, Skript, Messlatte für den Pilot). Laden bei "Bibel schreiben", "Stil festhalten", "Produktionsbibel", "Regeln für den Kanal", "was macht den Stil aus".
---

# Bibel schreiben

Ziel: `__ARBEIT__/kanaele/<slug>/BIBEL.md`. Bauer, Prüfer und Regie lesen sie vor jeder Szene. Jede Aussage ist belegt oder als Vermutung oder Regel markiert.

## Eingaben

- Je Video `__ARBEIT__/kanaele/<slug>/analyse/<id>/`: `analyse.json`, `ANALYSE.md` (mit Ton-Abschnitt und deinen Korrekturen), `ton.json`, `boegen/`.
- `__ARBEIT__/kanaele/<slug>/SKRIPT-BAUKASTEN.md` (Skill motion-skript-zerlegen).
- `__ARBEIT__/PROFIL.md` (Sprache, Plattform, Nische des Nutzers).

## Ablauf

1. Vorlage übernehmen: `__HEIM__/vorlagen/BIBEL-VORLAGE.md` mit Read lesen und mit Write als `__ARBEIT__/kanaele/<slug>/BIBEL.md` anlegen (kein `cp`). Gibt es schon eine BIBEL.md: erst ihren Inhalt mit Write als `__ARBEIT__/kanaele/<slug>/_ueberholt/BIBEL-<JJJJ-MM-TT>.md` sichern, nie löschen.
2. Abschnitt für Abschnitt füllen. Zahlen aus `analyse.json` und `ton.json`, Bilder aus den Bögen. Über mehrere Videos: Spanne und Median nennen, nicht ein Einzelwert.
3. Markieren:
   - **[B]** nur mit Quelle, z. B. `[B, yt-abc 12,4 s, szene_05.jpg]` oder `[B, 3 von 4 Videos]`.
   - **[P]** für Herkunft und Wirkung ("vermutlich in After Effects gebaut", "der Weißblitz soll wecken").
   - **[R]** für unsere Entscheidungen (Schrift-Ersatz, Mix-Ziel, Messlatte).
4. Machbarkeit ehrlich in Abschnitt 2: Typ, Weg, erreichbare Ähnlichkeit, was nicht geht. Richtwerte aus gemessenen Nachbauten: 2D ΔE ≈ 5 und SSIM ≈ 0,84 erreicht; einfache 3D ΔE ≈ 16 (Ziel < 15 knapp verfehlt, Hauptfehler Figuren-Proportionen); Figuren-Animation auf Blender-Niveau offen; Realfilm/KI-Video nicht nachbaubar.
5. Messlatte für den Pilot festlegen (Abschnitt 14), bevor gebaut wird. Ziele je Typ, Ausschlussfehler.
6. Zweimal gegenprüfen: zwei zufällige Aussagen der BIBEL am Bogen nachsehen. Stimmt eine nicht, alle Aussagen dieser Art prüfen.
7. Offene Fragen an den Nutzer in Abschnitt 15 sammeln (z. B. "Figuren weglassen oder als Beta-Blender-Spur?").
8. Status: `__HEIM__/ms status kanal:<slug> bibel --notiz "BIBEL.md: <Typ>, Machbarkeit <kurz>"`.

## Gate (fertig, wenn)

- Jeder Abschnitt gefüllt oder ausdrücklich "offen" mit Grund.
- Kein [B] ohne Quelle. Keine Effekt-Art als [B], die niemand gehört hat (AST ≥ 0,15 zählt als Hinweis, nicht als Beleg).
- Messlatte mit Zahlen steht vor dem Pilot.
- Zwei Stichproben gegen die Bögen geprüft und in der Rückmeldung genannt.

## Fallen

- Einzelwerte aus einem Video als Kanal-Regel verkaufen. Mindestens 3 Videos, sonst [P].
- Automatische Typ- und Schriftwerte sind Vorschläge. Was du in den Bögen anders siehst, gilt (und gehört in ANALYSE.md unter Korrekturen).
- Fremde Schriften, Musik und Figuren nicht übernehmen. Die Regel nennt einen frei nutzbaren Ersatz, der nah dran ist.
- Kurz bleiben: Stichpunkte mit Zahl und Quelle, keine Fließtexte. Was in SKRIPT-BAUKASTEN.md steht, nur verlinken.
