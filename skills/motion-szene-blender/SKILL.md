---
name: motion-szene-blender
description: "3D-Szene für Motion-Studio in Blender bauen (headless per Python-Skript mit msblend), als Video rendern und in HyperFrames einbetten: wann Blender statt Three.js, Gerüst, Kamera und Licht, Assets (Poly Haven zuerst), fertige Figuren mit Rig und Bewegung (Mixamo, Tripo), Partikel, Render-Budget EEVEE/Cycles, Entwurf und Kontaktbogen, Fallen, Messschleife gegen das Original. Laden bei \"Blender\", \"Szene art blender\", \"Blender-Niveau\", \"fotoreal\", \"Produktshot 3D\", \"HDRI\", \"Mixamo\", \"Tripo\", \"Figur mit Rig\", \"baue Szene s4 (blender)\", \"ms blender\"."
---

# motion-szene-blender

Blender läuft ohne Oberfläche. Du schreibst ein Python-Szenenskript, `__HEIM__/ms blender render` startet Blender, rendert PNG-Bilder, macht daraus ein MP4 und einen Kontaktbogen. Die Szene kommt als Video in eine HyperFrames-Komposition, 2D-Ebenen liegen darüber.
Bibliothek im Skript: `msblend` (Quelle `__HEIM__/blender/msblend.py`, Kopf-Docstring = Inhaltsverzeichnis). Muster: `__HEIM__/blender/beispiel_szene.py`. Hintergrund und Quellen: `__HEIM__/referenz/BLENDER.md`.
Getestet mit Blender 4.3 und 5.2 LTS (gleiches Bild). Mindestens 4.2.

## 1. Blender oder Three.js?

Gemessen (Apple M3 Pro, Beispielszene, Rechner nebenbei ausgelastet):

| Weg | 1080×1920 pro Bild | 20-s-Reel (600 Bilder) |
|---|---|---|
| Three.js in HyperFrames (Kit-Beispiel 3D) | 0,25 s inkl. Kodieren | ca. 2,5 Min |
| Blender EEVEE, 64 Samples | 1,5 bis 1,9 s (+ erstes Bild 4 s Shader) | 15 bis 19 Min + 1 Min Einbetten |
| Blender Cycles, 64 Samples, GPU | ca. 12 bis 17 s (gemessen 3,6 bis 5 s bei 540×960) | 2 bis 3 Stunden |

Blender nehmen, wenn die BIBEL eines davon verlangt: echte Materialien (Lack, Metall, Glas, Stoff), weiche Schatten und Spiegelungen aus einem HDRI, fertige Modelle oder Figuren mit Rig und Bewegung, viele Partikel mit Bewegungsunschärfe, fotoreal wirkender Produktshot.
Three.js (Skill motion-szene-3d-web) bleibt Standard für Toon-Look, einfache Formen, Text und alles, was oft geändert wird: 6-mal schneller, Snapshots in Sekunden.
Dein Rechner: `__HEIM__/ms blender check` misst s/Bild und rechnet ein 20-s-Reel hoch (`--cycles` misst Cycles mit). Die Zahl steht auch in `__ARBEIT__/live/blender-check.json`. Sagt sie über 30 Min pro Reel: Blender nur für einzelne Szenen.

## 2. Gerüst

1. Erster Kontakt: `__HEIM__/ms blender render beispiel --stichprobe 6 --entwurf` zeigt in 15 s, ob Blender läuft und wie die Beispielszene aussieht.
   Ordner der Szene: `__ARBEIT__/folgen/<id>/blender/<sid>/`. Muster übernehmen: `__HEIM__/blender/beispiel_szene.py` mit Read lesen und mit Write als `__ARBEIT__/folgen/<id>/blender/<sid>/szene.py` anlegen (kein `cp`). Liegt im Kanal-Kit schon eine Blender-Szene (`kanaele/<k>/kit/beispiele/*.py`), die nehmen.
2. Aufbau jedes Skripts:
```python
import os, sys
sys.path.insert(0, os.environ.get('MS_BLENDER_LIB') or os.path.dirname(os.path.abspath(__file__)))
import msblend as mb

p = mb.start(dauer=4.2, farbe='neutral', bewegungsunschaerfe=True)   # Dauer = dur aus scenes.json
T_HIT = 1.35                                    # Zeiten in Sekunden ab Szenenbeginn, aus den Wortzeiten
TEXT = mb.arg('--text', 'NEU')                  # eigene Parameter, gesetzt hinter `--`
...                                             # Bühne, Objekte, Licht, Kamera, Bewegung, Partikel
mb.rendern(p)
```
3. Regeln in msblend: Zeiten in Sekunden (t=0 ist Bild 1, `mb.sek(t)` gibt die Bildnummer), Winkel in Grad, Längen in Metern, Z ist oben, Kamera schaut entlang +Y. Farben als Hex. ease wie GSAP: `power2.out`, `back.out`, `sine.inout`, `expo.in`, `bounce.out`, `linear`.
4. Deterministisch: kein `random` ohne Seed (`random.Random(p.seed)`), keine Uhrzeit, keine Simulation, die vom vorigen Bild abhängt. msblend rechnet Partikel vorab als Keyframes. Gemessen: gleiche Eingabe = bitgleiches Bild, auch wenn ein Bild einzeln gerendert wird.
5. Wichtige Bausteine:
   - Bühne: `mb.hohlkehle(farbe=…)` (Boden geht rund in die Wand über), `mb.boden()`, `mb.welt_farbe()`.
   - Formen: `mb.form('zylinder'|'wuerfel'|'kugel'|'kegel'|'torus'|'ebene', pos, groesse, rot, material, fase=0.03)`. Neonring: `mb.form('torus', pos, 2.4, rohr=0.035, material=mb.material_emission(farbe, 1.2))`.
   - Material: `mb.material_pbr(farbe, rauheit, metall, klarlack)`, `mb.material_toon(farbe, stufen=3)` + `mb.kontur(obj, 0.02)`, `mb.material_emission(farbe, staerke)`, Texturen `mb.material_pbr(texturen='polyhaven:<id>')`.
   - Text: `mb.text_objekt('Größe', groesse=0.9, tiefe=0.09, max_breite=1.7)`, dazu `mb.ploppen(text, T)`.
   - Bewegung: `mb.bewegen(obj, 'location', t0, t1, a, b, ease)`, `mb.schluessel(...)`, `mb.drehen(obj, t0, t1, umdrehungen)`, `mb.fallen_lassen(obj, t0, T_HIT)`, `mb.quetschen(obj, T_HIT)`.

## 3. Kamera und Licht

- `cam = mb.kamera(pos, ziel, brennweite)`: Kamera blickt immer aufs Ziel. Fahrten in zeitlicher Reihenfolge aufrufen, jede startet, wo die letzte endete: `mb.push_in(cam, t0, t1, faktor=0.8)`, `mb.orbit(cam, t0, t1, winkel=-10)`, `mb.dolly(cam, t0, t1, (x, y, z))`, `mb.blick(cam, t0, t1, neues_ziel)`, `mb.kamera_zoom(cam, t0, t1, 35)`, `mb.kamera_wackeln(cam, T_HIT, 0.3, 0.035)`.
- Hochformat 9:16, Brennweite 50: sichtbare Höhe ≈ 0,72 × Abstand, Breite ≈ 0,40 × Abstand. Bei 8 m Abstand sind es 5,8 m hoch und 3,2 m breit. Hauptobjekt ≥ 25 % der Bildbreite, Text höchstens 70 % (`max_breite`).
- Push-in auf einen Treffer 0,3 s vor dem Wort starten. Leichter Orbit (5 bis 12 Grad über die ganze Szene) macht 3D sichtbar. Keine Reißschwenks.
- Licht: `mb.licht_preset('drei_punkt'|'studio'|'sonne'|'hdri', ziel=…)` oder HDRI plus eine Kante: `mb.hdri('polyhaven:studio_small_09', drehung=260, hintergrund='#f1e7da')`. Mit `hintergrund` sieht die Kamera eine saubere Farbe, das Licht kommt trotzdem aus dem HDRI. `drehung` verschiebt Lichtrichtung und Schatten: zwei Werte als Stichprobe vergleichen.
- Leuchten: `mb.gluehen(staerke=0.55, schwelle=3.0)`. Nur Emission über 3 leuchtet (Funken 12, Neon 1 bis 3 ohne Schein).
- Farbraum in `mb.start(farbe=…)`: `neutral` für Produkte und Markenfarben mit echtem Licht, `Standard` für Toon (Hex = Bildfarbe), `AgX` für filmischen Look (entsättigt Markenfarben).

## 4. Assets: erst Poly Haven, dann der Rest

Als motion-bauer: nur Poly Haven selbst laden (gratis, ohne Konto). Alles mit Konto oder Kosten (Sketchfab, Blendkit, Mixamo, Tripo, Cascadeur) forderst du im Bericht und in `fertig_<name>.json` unter `"offen"` an. Die Regie klärt es mit dem Nutzer, er lädt mit seinem Konto herunter.

1. Poly Haven (CC0, gratis, ohne Konto, ohne Namensnennung): `__HEIM__/ms assets suche polyhaven <begriff> [--typ hdris|models|textures]`, dann `__HEIM__/ms assets laden polyhaven <id> --aufloesung 1k`. 1k reicht für HDRI-Licht und kleine Modelle (1,6 MB statt 25 MB). Im Skript: `'polyhaven:<id>'`.
2. Sketchfab (Download nur mit Konto): nur Modelle mit CC0 oder CC-BY, nie NC (nicht kommerziell) und nie ND. Der Nutzer lädt die GLB herunter, dann `__HEIM__/ms assets eintragen <datei.glb> --quelle sketchfab --lizenz CC-BY-4.0 --autor "…" --url "…"`. CC-BY heißt: Namensnennung in die Caption, `__HEIM__/ms assets liste --nennung` gibt den Text.
3. Blendkit (Add-on in Blender, Gratis-Stufe begrenzt, Vollzugang ca. 9,90 $/Monat): nur nach Ja des Nutzers, Dateien danach eintragen.
4. Selbst modellieren nur bei einfachen Formen (Dose, Sockel, Karte, Logo als Extrusion). Alles Organische kommt fertig.
Ablage immer über `ms assets`, damit `lizenz.json` neben jeder Datei liegt. Im Skript dann `'<quelle>:<id>'` statt Pfad (`'sketchfab:roboter'`, `'mixamo:winken'`).

## 5. Figuren: fertig holen, nie selbst modellieren

Claude kann Szene, Licht und Kamera headless gut. Figuren modellieren, riggen und schauspielern scheitert. Deshalb:
1. **Fertige Figur mit Rig:** Mixamo (gratis mit Adobe-Konto, kommerziell frei, keine API): Figur als FBX „With Skin“ laden, jede Bewegung als FBX „Without Skin“, 30 fps. Der Nutzer lädt herunter, du trägst ein: `__HEIM__/ms assets eintragen ~/Downloads/figur.fbx --quelle mixamo --lizenz "Mixamo (Adobe), lizenzfrei" --typ figuren --id held`, jede Bewegung mit `--typ bewegungen --id winken`.
2. **Figur aus Bild oder Text:** Tripo (Rig und fertige Bewegungen inklusive, kostet Credits). Vorher `__HEIM__/ms assets kosten tripo --anzahl N`, Betrag nennen, nur nach Ja. Meshy: Preis vorher auf der Website prüfen. **Hunyuan3D nicht nutzen:** die Lizenz schließt die EU aus.
3. Im Skript:
```python
figur = mb.fbx_import('mixamo:held', pos=(0, 0, 0), hoehe=1.7)     # auf 1,7 m gebracht, Füße auf dem Boden
arm = mb.armatur_finden(figur)
winken = mb.aktion_aus_datei('mixamo:winken')                       # gleiche Knochennamen (Mixamo zu Mixamo)
mb.aktion_legen(arm, winken, t=1.2, ueberblenden=0.2)               # ab 1,2 s, letzte Pose bleibt stehen
```
4. Fehlt eine Bewegung: erst andere Mixamo-Bewegung suchen. Cascadeur (ca. 33 €/Monat) nur nach Ja des Nutzers.
5. Vor jedem Figuren-Versprechen: Probe-Shot (5 bis 8 s) bauen, messen, dem Nutzer zeigen. Siehe BLENDER.md, Abschnitt Grenzen.

## 6. Partikel

`mb.partikel_einfach(ort, t, anzahl, art='funken'|'konfetti', seed, tempo, dauer, richtung, streuung)`.
- Funken auf den Treffer (T_HIT), 80 bis 120 Stück, `tempo` 6 bis 7, dazu `mb.gluehen()` und `mb.kamera_wackeln()`.
- Konfetti 0,05 s nach dem Text, Startpunkt leicht vor dem Text (y kleiner), `tempo` 3 bis 4: es steigt kurz und segelt durchs Bild.
- Mehr als 300 Teilchen pro Ausbruch kosten spürbar Bauzeit (Keyframes), lieber zwei Ausbrüche.

## 7. Prüfen in drei Stufen (Gate vor dem Vollrender)

1. **Stichprobe:** `__HEIM__/ms blender render <szene.py> --folge <id> --szene <sid> --stichprobe 6 --entwurf` (6 Bilder 540×960, unter 15 s). Kontaktbogen `snapshots/<sid>_blender_stichprobe.jpg` mit dem Read-Tool ansehen.
2. **Entwurf:** `… --entwurf` (alle Bilder 540×960, 16 Samples, ohne Bewegungsunschärfe, ca. 0,25 s/Bild). Ergebnis `build/assets/video/<sid>.mp4` (Entwurf, wird später ersetzt), Kontaktbogen `snapshots/<sid>_blender.jpg` mit 12 Bildern.
3. **Voll:** ohne `--entwurf` (1080×1920, 64 Samples, Bewegungsunschärfe an). Erst nach Stufe 2 ohne Befund. Im Hintergrund starten, das Werkzeug meldet Fortschritt und Restzeit ins Live-Log.
Beim Ansehen prüfen: Hauptobjekt ganz im Bild und groß genug? Text lesbar (keine hellen Flanken, kein Glanz)? Aktion genau auf dem Wort (Zeit im Bogen)? Licht: Vorder- und Rückseite getrennt, keine harte Linie im Hintergrund? Nichts durchdringt sich? Erstes und letztes Bild sinnvoll (Szenenübergang)?
Teilbereich nachrendern: `--von 40 --bis 60` (landet in `blender/<sid>/`, ersetzt nicht das Szenenvideo). Abbruch fortsetzen: `--weiter`. Zum Öffnen in Blender: `--blend` speichert `blender/<sid>/<sid>.blend`.
**Gate:** Stichprobe und Entwurf angesehen, Befunde behoben, Zeit pro Bild bekannt.
Gelungene Szene fürs Kit vormerken: Skript nach `kanaele/<k>/kit/beispiele/<name>.py` (Skill motion-kanal-kit).

## 8. Einbetten in HyperFrames

1. `__HEIM__/ms blender komposition <folge> <sid>` schreibt `build/compositions/<sid>.html` und ersetzt dabei den Platzhalter von `ms szenen`: das Video füllt das Bild, darüber `#<sid>-ebene` für 2D (Text, Pfeile, Zahlen), Timeline mit Szenendauer. Dauer kommt aus `scenes.json`.
2. 2D-Ebenen von Hand in diese Datei (Read, dann Edit), ids mit `<sid>-` beginnen, GSAP-Zeiten lokal zur Szene (Regeln aus motion-szene-2d). Eine echte Komposition überschreibt das Werkzeug nicht (`--neu` schiebt die alte nach `_ueberholt/`).
3. `"art": "blender"` steht schon in `build/scenes.json` (Regie, Storyboard). Der Bauer ändert scenes.json nicht und ruft `ms szenen` nicht. Prüfen mit `__HEIM__/ms blender komposition <folge> <sid> --lint` (lässt die vorhandene Datei stehen, prüft nur) und `__HEIM__/ms snap <folge> --szene <sid> --raster 0.25 --name <bauer>_<sid>`.
4. Transparenter Hintergrund (3D über 2D legen): im Skript `mb.start(…, transparent=True)`, rendern mit `--alpha`. Es entsteht zusätzlich `<sid>.webm` mit Alphakanal, die Komposition nimmt sie automatisch. Geprüft: Snapshot und Render von HyperFrames behalten die Transparenz.
5. Ton nie im Blender-Video: das Video ist stumm (`muted`), Sounds kommen über motion-ton-mix.

## 9. Bekannte Fallen (alle gemessen oder passiert)

- **Farbraum:** AgX entsättigt Markenfarben (Orange wird lachsfarben). Produkte `neutral`, Toon `Standard`. Leuchtfarben über Stärke 2 werden in `neutral` weißlich: Neon mit Stärke 1 bis 1,5.
- **Harte Linie zwischen Boden und Wand:** Flächenlichter werfen auf großen glatten Flächen Schattenkanten. `mb.hohlkehle` wirft deshalb keinen eigenen Schatten. Eigene Böden: `obj.visible_shadow = False`.
- **Schleier über dem Bild:** Glühen mit Schwelle unter 2 lässt die ganze hell beleuchtete Bühne leuchten. Schwelle 3.
- **Text unlesbar:** glänzender 3D-Text spiegelt Softboxen weiß weg, ein Kantenlicht hinter dem Text macht die Flanken weiß. Text matt (`rauheit` 0,55), Tiefe 0,09, Kantenlicht unter Texthöhe.
- **HDRI-Schatten:** EEVEE macht aus der hellsten Stelle des HDRI eine Sonne. Blender 5.x zeichnet deren Schatten scharf (Text-Schatten auf dem Boden). `mb.hdri()` setzt den Sonnenwinkel auf 12 Grad (weich, in 4.x und 5.x gleich).
- **Toon-Stufen fehlen:** `material_toon` schaltet nach Lichtmenge. Starke Sonne (über 2) macht alles hell. Sonne 1 bis 1,5 oder `kante` höher.
- **Kontur in Cycles:** ist gelöst (Hülle nur für Kamerastrahlen), Toon selbst gibt es in Cycles nicht (Ersatz mit Warnung). Toon-Looks immer EEVEE.
- **Normalen:** importierte Modelle mit schwarzen Flecken oder Löchern: Normalen falsch herum. In Blender öffnen (`--blend`), Mesh, Normals, Recalculate Outside, oder anderes Modell nehmen.
- **Maßstab:** Mixamo-FBX kommt in Zentimetern, GLB in Metern. Immer `hoehe=` beim Import setzen, nie Rohmaß vertrauen.
- **Bewegungsunschärfe:** nur im Vollrender an. msblend rendert vor dem ersten Bild ein Vorlauf-Bild, sonst sieht das erste Bild eines Laufs anders aus (gemessen 2 % der Pixel, an Funken bis 189 von 255).
- **Erstes Bild langsam:** EEVEE kompiliert Shader (3 bis 6 s). Cycles auf dem Mac (Metal) kompiliert beim ersten Start 1,5 bis 6 Min und erneut, wenn eine Szene neue Shader-Arten nutzt. Cycles-Stichproben deshalb nie als Zeitmessung nehmen.
- **Alpha:** nur mit `transparent=True` UND `--alpha`. MP4 hat nie Transparenz. Hintergrund-Welt bleibt als Licht wirksam.
- **Neue Blender-Version:** msblend fängt die Unterschiede ab (EEVEE-Name, Slot-Aktionen ab 4.4, Compositor ab 5.0, Glühen-Werte). Bei Fehlern `ms blender check` und das Log `blender/<sid>/render.log` lesen.

## 10. Messschleife gegen das Original (Pilot)

1. Kamera am Original messen: Horizont und Fluchtpunkte, Objektgröße im Bild. Daraus Abstand und Brennweite (Formel aus Abschnitt 3), erst dann Licht.
2. Stichprobe zu den gleichen Zeiten wie das Original rendern, Paare nebeneinander ansehen.
3. Nach dem Render (macht die Regie): `__HEIM__/ms vergleich <folge>/vorbild/ausschnitt.mp4 <folge>/out/pilot-v<n>.mp4 --zeitversatz-suchen` (Skill motion-vergleich). Während des Baus: `__HEIM__/ms snap <folge> <zeiten> --gegen <folge>/vorbild/ausschnitt.mp4`. Ziel 3D: ΔE2000 ≤ 11 grün, ≤ 15 gelb.
4. Silhouette und Pose prüfst du von Hand im Paarbogen: Umriss des Hauptobjekts deckungsgleich? Figur in gleicher Pose zum gleichen Wort? Proportionen zuerst, dann Licht, dann Farbe. Eine Variable pro Versuch, nach 3 Fehlversuchen den Nutzer fragen.
5. Optional (KI-Paket): Tiefe mit Depth Anything 3, Pose mit GVHMR (siehe BLENDER.md). Nicht nötig für das Gate.

## 11. Andere Wege (optional, nicht im Standardablauf)

- **Higgsfield „use Blender“** (`fnf-blender-mcp`, MIT): steuert ein lokales Hintergrund-Blender ohne Add-on. Ungetestet, braucht Higgsfield-Konto.
- **Higgsfield „3D Jutsu“:** gehostetes Blender mit Katalog-Assets, ca. 5 Min pro Schritt, Kosten unbekannt: vorher im Konto prüfen und nennen.
- **Offizieller Blender-MCP** (Blender Lab, seit 04/2026): braucht ein laufendes Blender mit Oberfläche und führt Code ohne Schutz aus. Für dieses headless-Paket nicht nötig.
- **After Effects** (`fnf-after-effects-mcp`): nur mit eigener AE-Lizenz.
Alle Kosten verursachenden Wege klärt die Regie: erst Schätzung, dann Ja des Nutzers, dann `ms status <folge> --kosten …` mit dem Ist-Betrag. Als motion-bauer forderst du sie nur im Bericht an.
