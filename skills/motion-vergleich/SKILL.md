---
name: motion-vergleich
description: "Original gegen Nachbau messen und gezielt annähern (Pilot einer Kanal-Lernphase): ΔE2000 und SSIM pro Szene mit Ampel, Zeitversatz suchen, Paarbögen und Nebeneinander-Video ansehen, eine Variable pro Versuch, nach 3 Fehlversuchen an einer Szene den Menschen fragen. Laden bei \"vergleichen\", \"messen\", \"wie nah ist der Nachbau\", \"Delta E\", \"SSIM\", \"Pilot messen\", \"Nachbau verbessern\"."
---

# motion-vergleich

## Wann messen
- Nach jedem Pilot-Render (`out/pilot-v<n>.mp4`), immer gegen dasselbe Original.
- Während des Baus einer Szene schneller: `__HEIM__/ms snap <folge> <zeiten> --gegen __ARBEIT__/folgen/<pilot>/vorbild/ausschnitt.mp4` (Paar-Bilder ohne Vollrender, Ausschnitt mit gleicher Zeitachse aus `ms stimme --original`). Zum Ansehen `snapshots/<name>/kontaktbogen_paar.jpg`: je Zeitpunkt Original links, Nachbau rechts.
- Bei normalen Folgen gibt es kein Original: dort nicht messen, sondern Skill motion-qa.

## Messen
```
__HEIM__/ms vergleich __ARBEIT__/folgen/<pilot>/vorbild/ausschnitt.mp4 __ARBEIT__/folgen/<pilot>/out/pilot-v1.mp4 --zeitversatz-suchen
```
- Original: am besten `vorbild/ausschnitt.mp4` der Pilot-Folge (gleiches Zeitfenster und gleiche Zeitachse wie der Pilot).
  Das ganze Original (`__ARBEIT__/vorlagen/videos/<id>.mp4`) geht auch: Das Werkzeug liest dann das Fenster aus `voice/stimme.json`
  oder nimmt `--von <s> --bis <s>` (Nachbau-Zeit 0 = Original-Zeit von). Ohne Fenster misst es Pilot 0 gegen Original 0, also falsch.
- Szenen kommen aus `build/scenes.json` der Pilot-Folge (Zeiten im Nachbau). Andere Datei: `--szenen`.
- `--zeitversatz-suchen` findet den Versatz über die Bewegungs-Kurven (Korrelation ≥ 0,6 ist verlässlich, darunter gibt das Werkzeug eine WARNUNG aus und VERGLEICH.md markiert den Versatz als unsicher: dann ohne Suche messen und die Paarbögen entscheiden lassen). Ist er nicht 0: erst die Zeitachse des Nachbaus korrigieren (Szenenstarts), dann wieder ohne Versatz messen.
- Ergebnis in `out/vergleich_<name>/`: `VERGLEICH.md` (Tabelle mit Ampel), `paar_<szene>.jpg` (links Original, rechts Nachbau), `nebeneinander.mp4`, `vergleich.json` (jedes Bildpaar). Die Gesamtwerte landen in der STATUS.json des Pilots (`messwerte`, Phase `vergleich`) und des Kanals.
- Dauer: 30-s-Video etwa 25 s (4 Messbilder pro Sekunde auf 540×960).

## Ampel lesen
| Art | grün | gelb | rot |
|---|---|---|---|
| 2D | ΔE2000 ≤ 6,5 und SSIM ≥ 0,65 | ΔE2000 ≤ 9 und SSIM ≥ 0,5 | sonst |
| 3D-Web, Blender | ΔE2000 ≤ 11 | ΔE2000 ≤ 15 | sonst |

Kalibriert an einem echten, abgenommenen Nachbau: 2D-Szenen lagen bei ΔE2000 2,8 bis 6,5 (gesamt 4,8, SSIM 0,78). 3D-Szenen lagen bei 12 bis 19, das Ziel war 11.
Die Spalte „grob“ (ΔE76 und SSIM auf 90×160) entspricht der alten Messweise: dort 2D 5,3 / 0,84 und 3D 16 (Ziel unter 15).
ΔE heißt: wie weit die Farben auseinander liegen (unter 2 sieht man keinen Unterschied). SSIM heißt: wie ähnlich Formen und Kanten sind (1 = gleich).
Grenze der Messung: Das Original gegen sich selbst mit leicht gedrehten Figuren lag schon bei ΔE76 11. 3D nie auf 0 jagen.

## Ansehen, dann ändern
1. **Paarbogen der schlechtesten Szene** mit dem Read-Tool öffnen. Eine gute Zahl beweist keinen gleichen Look, eine schlechte sagt nicht, warum.
2. **Eine Ursache benennen**, sichtbar im Bild: Farbe/Helligkeit (Grading, Licht), Lage/Größe (Kamera, Abstand, fov), Timing (Aktion zu früh/spät), Form (Proportionen), fehlendes Element, **Bewegung** (taucht anders auf, Dauerbewegung fehlt, anderes Tempo oder Easing).
   Bewegung zeigen Standbilder und Zahlen nicht. Für die Einträge der Bewegungsliste Streifen ansehen: `__HEIM__/ms snap <folge> <t> --streifen --gegen <ausschnitt>` (6 Bilder im Abstand von 0,08 s, Original | Nachbau). Eine grüne Szene kann sich trotzdem falsch bewegen.
3. **Eine Variable pro Versuch.** Ändern, Szene per `ms snap --gegen` prüfen, dann neu rendern und neu messen.
4. Jeden Versuch in `VERSUCHE.md` der Folge notieren: `| Szene | Versuch | geänderte Variable | ΔE vorher → nachher | Urteil |`.
5. Reihenfolge: rote Szenen zuerst, dann gelbe. Grün reicht, nicht weiter polieren.

## Nach 3 Fehlversuchen an einer Szene
Aufhören. `__HEIM__/ms status <folge> --wartet "Szene <id> kommt nicht unter <x>: <Ursache>. Paarbogen: <pfad>. Weiter versuchen oder so lassen?"`, dem Nutzer die drei Versuche mit Zahlen und den Paarbogen zeigen. Erst nach seiner Antwort weiter, dann `--wartet-weg`.

## Fallen
- Unterschiedliche Bildgröße oder Zuschnitt (Original mit Rand, Untertitel des Originals): Werte sind dann alle schlecht. Erst Format angleichen.
- Captions im Original, aber nicht im Nachbau (oder anders): drückt SSIM in jeder Szene. Beim Pilot Captions möglichst gleich nachbauen: Stil in `kit/captions.json` (Felder: Skill motion-kanal-kit), Gruppen wie im Original von Hand in `build/captions.json` mit `"hand": true` (Format und Ablauf: Skill motion-kanal-lernen, Schritt 4), Shots ohne Captions mit `"captions": false` in scenes.json.
- Versatz von wenigen Bildern zerstört SSIM bei schneller Bewegung: immer erst `--zeitversatz-suchen`.
- Kompressions-Artefakte des Originals: kleine Restwerte (ΔE2000 um 1) sind normal.
