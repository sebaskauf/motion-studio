---
name: motion-format-finden
description: Start der Produktion nach dem Setup. Zwei Fragen (Short-Form oder lange YouTube-Videos, welcher Stil von welchem Account mit Beispielen), dann automatisch Stil lernen und ein Video 1:1 nachbauen (eigene Sitzung, im Studio sichtbar), erst danach welche Arten von Videos und welcher eigene Twist. Laden beim ersten Produktionsstart ohne Kanal, bei „wie fange ich an“, „ich habe noch kein Format“, „welches Format“, „Ideen für einen Kanal“.
---

# Format finden: zwei Fragen, dann automatisch lernen

Kommt NACH dem Setup, als erster Schritt der Produktion (Sebastian 23.10.2026). Vor dem Lernen nur Frage 1 und 2, jede einzeln, Antwort sofort in `__ARBEIT__/PROFIL.md` (Abschnitt Kanal und Inhalt).

## 1. „Willst du Short-Form-Videos machen (Reels, TikTok, YouTube Shorts) oder lange YouTube-Videos?“
- **Short-Form:**
  - Das ist, was Motion-Studio baut: 9:16, 20 bis 90 Sekunden.
  - Im Profil eintragen: Plattformen und Format.
- **Lange YouTube-Videos:**
  - Ehrlich sagen: Motion-Studio baut heute nur Hochformat 9:16. Querformat 16:9 und Längen von 8 bis 15 Minuten sind noch nicht eingebaut.
  - Vorschlag: den Stil eines YouTube-Kanals als Shorts umsetzen. Das geht, und Shorts sind der schnellste Weg zu Reichweite.
  - Will er trotzdem lang: im Profil unter Notizen vermerken und mit Short-Form weitermachen.

## 2. „Welchen Stil willst du haben? Gibt es einen Account, dessen Stil du übernehmen willst?“
- **Ja:** Handle oder Link aufschreiben (Vorbild-Kanäle) und kurz, was ihm daran gefällt.
- **Nein oder unsicher:** Zeig die Beispiele unten, passend zu Antwort 1. Zu jedem gibt es einen Satz. Dazu:
  - Sag ihm, er soll sich die Accounts kurz ansehen.
  - Zusätzlich 10 Minuten selbst durch Instagram, TikTok oder YouTube scrollen: Reels-Tab, Suche nach seinem Thema plus „explained“, „animation“, „3D“. 2 bis 3 Videos merken, die er selbst so machen möchte, und dir die Links schicken.
  - Will er Zahlen zu einem Account: Skill motion-vorlagen-finden. YouTube und TikTok sind gratis, Instagram nur per Apify mit Kostenansage und Ja.
- Ehrlich zur Machbarkeit:
  - 2D ist am leichtesten.
  - 3D geht im Browser oder in Blender.
  - Figuren mit Schauspiel sind am schwersten.

## Danach automatisch: Stil lernen und ein Video 1:1 nachbauen
Nicht fragen, ob nachgebaut werden soll (Sebastian 23.10.: das muss vor eigenen Videos passieren).
1. Instagram-Vorbild und die Kosten (rund 3 Cent pro Video über Apify) liegen über „Ohne Nachfrage frei bis“: EINE Frage, „Zum Lernen hole ich 3 bis 5 Videos von @x, etwa 0,10 $. Okay?“ Sonst nichts fragen.
2. Kurzer Hinweis an den Nutzer, ein Absatz:
   „Ich bringe mir jetzt den Stil von @x bei: Videos laden, zerlegen, eins 1:1 nachbauen und messen.
   Das dauert etwa 2 bis 3 Stunden.
   Im Studio siehst du jeden Schritt, die Agenten bei der Arbeit und wann es ungefähr fertig ist.
   Wenn der Nachbau steht, zeige ich ihn dir und frage, was für Videos du damit machen willst.“
3. Starten als eigene Sitzung, damit dieser Chat frei bleibt und das Studio alles zeigt: `__HEIM__/ms starten kanal-lernen --url <@handle oder Link>`. Ohne tmux (Windows) öffnet sich ein eigenes Fenster.
4. Ablauf in dieser Sitzung: Skill motion-kanal-lernen. Er läuft ohne Zwischenfragen durch bis zum Urteil über den Nachbau.

## Teil B, erst NACH dem Nachbau (motion-kanal-lernen Schritt 7)
- „Welche Arten von Videos willst du in diesem Stil machen? Worüber?“ Zum Beispiel Technik erklärt, KI-News und Tools, Wissenschaft, Geschichte, Geld oder das eigene Fachgebiet. Eintragen: Nische und Thema, Zielgruppe.
- „Was soll bei dir anders sein, dein eigener Twist?“ Eintragen: Eigener Twist.
- Passt das Thema nicht zur Nische des Vorbilds, ist das gut: der Stil kommt vom Vorbild, die Inhalte kommen vom Nutzer.

Ein einzelnes fremdes Video ohne Kanal-Lernen nachbauen (Skill motion-nachbau) gibt es nur, wenn der Nutzer ausdrücklich genau das will („bau mir dieses Video nach“).

## Beispiele: Short-Form (9:16), Faceless Motion Design
| Account | Format | Schwierigkeit |
|---|---|---|
| @minitopias | von Sebastian empfohlen. Videos vor dem Vorschlagen kurz ansehen und den Stil in einem Satz beschreiben | ansehen |
| @speedy_devv | Technik erklärt in 3D-Makro (Touchscreen, Chips), dunkel, leuchtende Felder, ruhige Stimme, Wort-Captions | schwer (3D) |
| @scroll.engineer | Ingenieurs-Wunder erklärt, Low-Poly-3D, filmisches Abendlicht, Labels im Bild | schwer (3D) |
| @rick.theengineer | IT-Sicherheit und Backend erklärt, isometrisches Schnittmodell, UI-Fenster, Figur als Erzähler | sehr schwer (Figur) |

## Beispiele: YouTube (Stil-Vorbilder, lang)
| Kanal | Stil | Als Shorts machbar |
|---|---|---|
| Kurzgesagt (@kurzgesagt) | flaches 2D, kräftige Farben, Vögel als Figuren, Wissenschaft | ja, 2D |
| TED-Ed (@TEDEd) | wechselnde 2D-Illustrationsstile, Bildung | ja, 2D |
| 3Blue1Brown (@3blue1brown) | Mathe-Animation, dunkler Grund, Formeln bewegen sich | ja, 2D |
| PolyMatter (@PolyMatter) | Karten, Grafiken, kinetische Typo, Wirtschaft und Politik | ja, 2D |
| Branch Education (@BranchEducation) | Technik im 3D-Querschnitt (Chips, Geräte) | ja, 3D |
| Jared Owen (@JaredOwen) | 3D „How it works“, Gebäude und Maschinen | ja, 3D |
| Animagraffs (@Animagraffs) | detaillierte 3D-Mechanik (Motoren, Waffen, Fahrzeuge) | schwer, 3D |

Die Listen sind ein Startpunkt. Passt keiner zum Thema des Nutzers, sucht ihr gemeinsam über sein Thema.
