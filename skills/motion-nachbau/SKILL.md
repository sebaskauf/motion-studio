---
name: motion-nachbau
description: Ein konkretes Vorbild-Video 1:1 nachbauen. Alles erkennen (Stimme und Transkript, Bilder und Schnitte, Musikbett, Soundeffekte), Szene für Szene nachbauen, gegen das Original messen und als postbare Kopie mit eigener Stimme und eigenen Sounds rendern. Laden bei "bau dieses Video nach", "1:1 nachbauen", "kopier dieses Video", "genau so ein Video", Link oder Datei eines einzelnen Videos.
---

# Ein Video 1:1 nachbauen

Für EIN konkretes Video (Sebastian 23.10.2026: „konkrete Videos eins zu eins nachbauen, alles erkennen“). Für einen ganzen Kanal mit Bibel und Baukasten ist motion-kanal-lernen da. Dieser Skill nutzt dieselben Werkzeuge, nur ohne Baukasten und ohne 3 bis 5 Vorlagen.

## 1. Laden
- Link: `__HEIM__/ms laden <url>`. Instagram scheitert ohne Login oft. Dann `__HEIM__/ms vorlagen apify …` (nur nach Kostenansage und Ja, wenige Cent) oder der Nutzer speichert das Video und du nimmst `__HEIM__/ms laden datei <pfad> --url <link>`.
- Datei: `__HEIM__/ms laden datei <pfad> [--url <link>] [--creator <name>]`. Das lädt auch das Transkript.
- Kanal für die Ablage: `__HEIM__/ms neu kanal nachbau-<creator> --vorbild "@creator"`, falls er fehlt.

## 2. Alles erkennen (Pflicht, bevor gebaut wird)
1. Bild: `__HEIM__/ms zerlegen <id> --kanal <slug>`. Danach die Übersichtsbögen selbst ansehen (Read-Tool). Notiere Schnitte, Szenen, Kamera, Palette, Text und Captions, Typ (2D, 3D, Figur).
2. Ton: `__HEIM__/ms ton-zerlegen <id> --kanal <slug> --trennen`. Das liefert:
   - Stimme ja/nein, Tempo
   - Musikbett ja/nein und wie leise
   - Soundeffekte mit Zeit und Art
3. Sprache: das Transkript aus `vorlagen/transkripte/<id>.txt` (aus `ms laden`). Gibt es Stimme, aber kein Transkript: noch einmal mit `ms laden … --neu`.
4. In `kanaele/<slug>/analyse/<id>/NACHBAU.md` festhalten:

   | Bereich | Was hinein muss |
   |---|---|
   | Stimme | ja/nein, Sprache, Tempo |
   | Transkript | erste Sätze |
   | Szenen | Liste mit Zeiten |
   | Musik | ja/nein, Pegel |
   | Soundeffekte | Zeit und Art |
   | Typ und Spur | 2D, 3D-Web oder Blender |
   | Schwierigstes | z. B. Figur mit Rig |

   Jede Zeile bekommt [B] für gemessen oder [P] für vermutet.

## 3. Fenster und Plan
- **Länge:**
  - Bis 30 s wird das ganze Video gebaut.
  - Länger: zuerst der Hook, die ersten 15 bis 20 s bis zu einem Schnitt. Den Rest erst, wenn der Hook gut gemessen ist und der Nutzer es will.
- **Kurzplan:** In 5 Zeilen an den Nutzer:
  - was nachgebaut wird
  - Spur
  - was realistisch ist (ehrlich: Figuren mit Schauspiel sind am schwersten)
  - Kosten
- Bei einem Autopilot- oder Testauftrag nicht warten, sondern den Plan in den Status schreiben und loslegen.

## 4. Nachbau mit Originalton (zum Messen)
Wie motion-kanal-lernen Schritt 4 bis 6:
1. `ms neu folge <slug>-nachbau --kanal <slug> --pilot --vorlage <id>`
2. `ms stimme <folge> --original [--von --bis]`
3. `ms woerter <folge>`, Caption-Gruppen wie im Original
4. Storyboard aus der Schnittliste: eine Szene pro Shot
5. `ms szenen <folge> --plan`
6. motion-bauer parallel. Im Brief stehen Referenzbilder je Szene und Paarbilder mit `ms snap … --gegen`.
7. `ms szenen <folge>`, dann `ms render <folge> nachbau-v1`

## 5. Messen
- `__HEIM__/ms vergleich <folge>`: ΔE (Farbabstand) und SSIM (Bildähnlichkeit) je Szene, dazu das Vergleichsvideo Original neben Nachbau.
- Danach EINE Verbesserungsrunde an den drei schlechtesten Szenen, nur dort neu rendern, noch einmal messen.
- Ergebnis in NACHBAU.md:
  - Messwerte vorher und nachher
  - was nah dran ist, was nicht und warum

## 6. Postbare Kopie (eigener Ton)
Den Originalton nie veröffentlichen. Für die Kopie:
1. **Text:** gleicher Inhalt in der Sprache aus PROFIL.md (übersetzen, wenn nötig), Hook-Satz möglichst wörtlich.
2. **Stimme:** nach Profil über `ms stimme <folge> …` (ElevenLabs, Higgsfield oder eigene Aufnahme), dann `ms woerter <folge>`. Die Szenen an die neuen Wortzeiten anpassen (`ms szenen`), statt sie neu zu bauen.
3. **Musik:** Gab es ein Bett, nimm ein ähnliches aus der Sound-Bibliothek, gleich leise unter der Stimme (Pegel aus `ton.json`).
4. **Soundeffekte:** an denselben Stellen wie im Original, gleiche Art aus der Bibliothek (Skill motion-sound-bibliothek, `ms sound`). Mischen nach motion-ton-mix.
5. Rendern mit `ms render <folge> kopie-v1`.

## 7. Abschluss
- Dem Nutzer zeigen:
  - Vergleichsvideo
  - Messwerte
  - Kopie
  - offene Punkte
  - Kosten
- `ms status <folge> fertig`
- Lernlog: 3 Zeilen

## Fallen
- Originalmusik und Original-Effekte nie in die Kopie übernehmen. Sie werden nur gemessen.
- Nicht schätzen, wo gemessen werden kann: Szenenzeiten, Wortzeiten und Pegel kommen aus den Werkzeugen.
- Jede Prüfung einmal (motion-folge, Effizienz). Kein zweiter voller Durchgang ohne Änderung.
