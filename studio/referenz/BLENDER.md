# Blender-Spur: Hintergrund, Messwerte, Quellen, Grenzen

Recherche-Stand 19.10.2026 (Plan Motion-Studio, Abschnitt 5), Messungen und Tests 20.10.2026.
Kurzanleitung steht im Skill `motion-szene-blender`. Hier steht, warum es so gebaut ist und was belegt ist.

## 1. Kurzfassung

- Blender lässt sich komplett per Python steuern (`blender -b -P szene.py`). Szene, Licht, Kamera, Materialien, Partikel und fertige Figuren mit Bewegung klappen headless zuverlässig und reproduzierbar.
- EEVEE ist schnell genug für Serien (1,5 s pro Bild in 1080×1920, ein 20-s-Reel in rund 15 Minuten). Cycles nur für einzelne Shots (rund 12 s pro Bild).
- Three.js im Browser ist rund 6-mal schneller und bleibt Standard. Blender lohnt sich für echte Materialien, HDRI-Licht, fertige Modelle und Figuren.
- Der Engpass ist nicht der Zugriff, sondern Figuren und Schauspiel. Lösung: fertige Figuren mit Rig und fertigen Bewegungen (Mixamo, Tripo), nie selbst modellieren, und vor jedem Versprechen ein gemessener Probe-Shot.

## 2. Messwerte

Rechner: Apple M3 Pro, 18 GB. Szene: `beispiel_szene.py` (Hohlkehle, Sockel, Dose aus 4 Teilen, Text, 110 Funken, 80 Konfetti, Glühen, Bewegungsunschärfe im Vollrender). Beim Messen liefen 5 andere Arbeiten parallel: Systemlast 9 bis 12 bei 4.3, 19 bei 5.2. Die Werte sind eher zu hoch, der Unterschied zwischen den Versionen kommt vermutlich von der Last.

| Messung | Blender 4.3.2 | Blender 5.2.2 LTS |
|---|---|---|
| EEVEE 540×960, 16 Samples (Entwurf) | 0,22 bis 0,26 s/Bild | 0,24 bis 0,28 s/Bild |
| EEVEE 540×960, 64 Samples | 0,55 bis 0,80 s/Bild | 0,92 s/Bild |
| EEVEE 1080×1920, 64 Samples | 1,48 bis 1,50 s/Bild | 1,87 s/Bild |
| Erstes Bild (Shader kompilieren) | 3 bis 6 s | 3 bis 6 s |
| Hochrechnung 20-s-Reel EEVEE 1080×1920 | 15 Min | 19 Min |
| Cycles 540×960, 64 Samples, GPU (Metal) | 3,6 s/Bild | 5,0 s/Bild |
| Cycles 1080×1920 (geschätzt ×3,5) | 12,6 s/Bild, 20-s-Reel 2 h | 17 s/Bild, 20-s-Reel 3 h |
| Cycles allererster Start (Metal-Kernel kompilieren) | 91 s, danach Cache | 5,5 Min, bei neuen Shader-Arten erneut |

Zum Vergleich:
- Three.js-Szene aus dem Kit (`beispiel-3d.html`, 2,5 s) in HyperFrames 1080×1920: 75 Bilder in 18,4 s inklusive Kodieren, also 0,25 s/Bild.
- Blender-Video in HyperFrames einbetten (3 s, Entwurf): Render 4,4 s.
- Messung vom 19.10. (Plan, einfache Testszene, Blender 4.3.2, 1080×1920): EEVEE 64 Samples 1,2 s/Bild, Cycles 64 Samples mit Rauschfilter 17 s/Bild.
- Dichte Szenen (viele Lichter, Glas, Volumen, viele Figuren) brauchen länger. Faktor 2 bis 5 ist eine Schätzung, nicht gemessen. Immer mit `ms blender check` und dem ersten Entwurf nachmessen.

Reproduzierbarkeit (gemessen): Zwei Läufe mit gleicher Eingabe ergeben bitgleiche Bilder. Ein Bild einzeln gerendert ist bitgleich zum selben Bild aus einer Reihe, seit msblend vor dem ersten Bild ein Vorlauf-Bild rechnet (vorher wich das erste Bild mit Bewegungsunschärfe an 2 % der Pixel ab).

## 3. So funktioniert die Spur

```
ms blender render szene.py --folge <id> --szene s4 [--entwurf | --stichprobe 6] [-- eigene Argumente]
  1. blender -b --factory-startup --python-exit-code 1 --python-expr "sys.path += HEIM/blender" -P szene.py -- …
  2. msblend.start() → Szene bauen → msblend.rendern(): PNG je Bild, druckt MSFRAME <bild> <sekunden>
  3. Bilder nach folgen/<id>/blender/s4/frames_<B>x<H>/f_0001.png …, Log nach render.log
  4. ffmpeg (H.264, yuv420p, CRF 18) → build/assets/video/s4.mp4 + s4.json (Messwerte)
  5. Kontaktbogen → snapshots/s4_blender.jpg, Live-Log und Notiz in STATUS.json
ms blender komposition <id> s4 → build/compositions/s4.html (Video + Ebene für 2D)
```
- `--factory-startup`: keine Add-ons und Einstellungen des Nutzers, damit jedes Bild überall gleich aussieht.
- `--python-exit-code 1`: ein Python-Fehler im Skript beendet Blender mit Fehlercode. Ohne diesen Schalter meldet Blender Erfolg, obwohl nichts gerendert wurde.
- Je Auflösung ein eigener Bilderordner: Entwurf und Endfassung mischen sich nie, `--weiter` ist sicher.
- Renders laufen mit `nice -n 10` (Mac und Linux), damit der Rechner bedienbar bleibt.

## 4. Blender-Versionen

msblend ist mit 4.3.2 und 5.2.2 LTS getestet (gleiches Bild, Kontaktbögen verglichen). Unterschiede, die msblend abfängt:

| Thema | bis 4.x | ab 5.x | msblend |
|---|---|---|---|
| Name der EEVEE-Engine | `BLENDER_EEVEE_NEXT` (4.2 bis 4.5) | `BLENDER_EEVEE` | sucht in der Liste der Engines |
| Keyframes | `action.fcurves` | Slot-Aktionen (ab 4.4, alte API ab 5.0 weg) | `_fcurves()` liest beide |
| Compositor | `scene.node_tree` | `scene.compositing_node_group` | `gluehen()` baut beides |
| Glare-Knoten | Eigenschaften (`glare_type`, `size` 6 bis 9, `mix`) | Eingänge (`Type`, `Size` 0 bis 1, `Strength`) | Werte umgerechnet, an 4.3 abgeglichen |
| HDRI-Sonne | weiche Schatten | scharfe Schatten bei gleichem Wert | `hdri()` setzt `sun_angle` 12 Grad |
| FBX-Import | `import_scene.fbx` | zusätzlich `wm.fbx_import` (ab 4.5) | nimmt, was da ist |

Unter 4.2 gibt es EEVEE Next nicht. `ms blender check` meldet dann „zu alt“.

## 5. Asset-Quellen

| Quelle | Was | Lizenz | Zugang | Im Paket |
|---|---|---|---|---|
| Poly Haven, polyhaven.com | HDRIs, Texturen, Modelle | CC0, keine Namensnennung | API api.polyhaven.com ohne Schlüssel, eigener User-Agent nötig | `ms assets suche/laden polyhaven` |
| Sketchfab, sketchfab.com | sehr viele Modelle, auch Figuren | je Modell: CC0, CC-BY (Namensnennung), NC/ND (nicht nutzen), Store (kostet) | Download-API mit Konto und Token | Anleitung, dann `ms assets eintragen` |
| Blendkit, blendkit.com | Modelle, Materialien als Blender-Add-on | Gratis-Stufe begrenzt, Vollzugang ca. 9,90 $/Monat | Add-on in Blender mit Oberfläche | nur Anleitung |
| Mixamo, mixamo.com | Figuren mit Rig, tausende Bewegungen | gratis, kommerziell nutzbar (Adobe-Konto) | keine API, Altbestand von Adobe | Anleitung, `aktion_aus_datei` |
| Tripo, tripo3d.ai | Figur aus Bild oder Text, Auto-Rig, Bewegungen | Rechte je Plan laut AGB prüfen | API mit Credits | nur `ms assets kosten tripo` |
| Meshy, meshy.ai | wie Tripo | je Plan | API mit Credits, Credit-Preis nicht öffentlich belegt | nur Hinweis |
| Hunyuan3D (Tencent) | Bild zu 3D | Lizenz schließt die EU aus | | **nicht nutzen** |
| TRELLIS (Microsoft), Mac-Port | Bild zu 3D, lokal | Lizenz im Repo prüfen | braucht rund 24 GB RAM | nicht im Paket |
| HY-Motion | Bewegung aus Text | | braucht 24 bis 26 GB Grafikspeicher | nicht im Paket |

Lizenzen wandern mit: `ms assets` legt neben jede Datei eine `lizenz.json`. `ms assets liste --nennung` erzeugt die Namensnennung für die Caption.

## 6. Figuren: Wege und Kosten

| Weg | Kosten | Qualität | Aufwand |
|---|---|---|---|
| Mixamo-Figur + Mixamo-Bewegungen | gratis | solide, generischer Look | von Hand herunterladen, eintragen |
| Sketchfab-Figur mit Rig (CC-BY) | gratis, Namensnennung | sehr unterschiedlich, Knochennamen prüfen | Rig muss zu den Bewegungen passen |
| Tripo: Bild → Figur → Auto-Rig → Bewegung | ca. 0,55 $ pro Figur laut Suchtreffern (19.10.), unverifiziert. Eigene Rechnung 20.10.: 1 Credit = 0,01 $ (Tripo-Blog 08.04.2024), Modell 20 bis 120 Credits, Rig 25 bis 30, Bewegung 10 bis 20: 0,55 bis 1,70 $ pro Figur mit einer Bewegung | gut für Stil-Figuren, Hände und Gesichter schwach | API, Preis vorher mit `ms assets kosten tripo` nennen |
| Meshy | unbekannt | ähnlich Tripo | Preis vorher prüfen |
| Cascadeur Pro | ca. 33 €/Monat | eigene Bewegungen mit Physik-Hilfe, Python-API, läuft auf Apple Silicon | nur wenn Bewegungen fehlen |

Getestet (20.10.): Import einer geriggten FBX-Figur, Laden einer Bewegung aus einer zweiten FBX-Datei, Ablegen als NLA-Streifen ab einer Sekunde, Verformung des Netzes geprüft, in 4.3 und 5.2 (Slot-Aktionen) gleich. Die Testfigur war selbst erzeugt (zwei Knochen mit Mixamo-Namen). Eine echte Mixamo-Figur ist ungetestet, weil Mixamo ein Adobe-Konto verlangt.

## 7. Messwerkzeuge gegen das Original

- Standard: `ms vergleich` (ΔE2000 und SSIM pro Szene, Paarbögen). 3D-Ziel ΔE2000 ≤ 11 (grün), ≤ 15 (gelb). Unser bester 3D-Nachbau lag bei 12 bis 19.
- Von Hand im Paarbogen: Silhouette des Hauptobjekts (Umriss deckungsgleich?), Pose der Figur zum Wort, Proportionen, Kamerahöhe und Brennweite.
- Optional, nur mit KI-Paket und genug Speicher: Depth Anything 3 (Small oder Base, Tiefenkarte von Original und Nachbau vergleichen), GVHMR in einer Mac-Variante (Körperpose aus Video). Beides nicht im Gate.

## 8. Andere Wege (MCP und Programme)

- Higgsfield „use Blender“ (`fnf-blender-mcp` 0.2.2, MIT): lokales Hintergrund-Blender ohne Add-on. Ungetestet.
- Higgsfield „3D Jutsu“: gehostetes Blender 5.2 mit Katalog-Assets, ca. 5 Min pro Schritt, Kosten unbekannt.
- Offizieller Blender-Lab-MCP (v1.0.0 seit 27.04.2026): braucht laufendes Blender und führt Code ohne Schutz aus.
- „MCP for Blender“ (ahujasid): nur mit offener Oberfläche, Telemetrie ist an.
- After Effects über Higgsfield (`fnf-after-effects-mcp` 0.1.6, ExtendScript): nur mit AE-Lizenz.
Für dieses Paket reicht headless Blender per Skript: kein Add-on, kein laufendes Fenster, jedes Bild reproduzierbar.

## 9. Ehrliche Grenzen

- **Figuren-Schauspiel auf Zack-D.-Films-Niveau ist nicht belegt.** Dort arbeiten menschliche Vertrags-Animatoren in einer Blender-Pipeline (Stellenanzeige, Animaster Studio). Es gibt keinen öffentlichen Beleg, dass ein Agent das erreicht. Praxisberichte: Szene, Licht und Kamera klappen, Figuren, Rig und Schauspiel scheitern.
- **Vor jedem Versprechen ein Probe-Shot:** ein Shot von 5 bis 8 s mit der gewünschten Figur und Bewegung, gerendert, mit `ms vergleich` gegen das Original gemessen und dem Nutzer gezeigt. Erst dann eine Serie zusagen.
- Hände, Gesichter, Lippen-Synchronität, Kontakt (Figur greift Gegenstand) sind die Stellen, an denen fertige Bewegungen nicht passen. Lieber Bildausschnitt und Schnitt so wählen, dass sie nicht im Fokus stehen.
- Render-Zeit ist echt: ein 20-s-Reel in Blender braucht 15 Minuten statt 2,5 Minuten in Three.js. Änderungen am Ende kosten jedes Mal diese Zeit. Deshalb Stichprobe und Entwurf vor dem Vollrender.
- Cycles-Qualität (Glas, Kaustik, echtes Global Illumination) kostet rund 2 Stunden pro Reel auf einem Laptop. Nur für einzelne Hero-Shots.

## 10. Was in diesem Paket getestet ist (20.10.2026)

- `ms blender check`: Blender gefunden, Version, Benchmark (Werte oben), auch mit `--cycles` und `--json`.
- `ms assets`: Poly-Haven-Suche, HDRI 1k, Modell (glTF) 1k, Textur 1k mit Prüfsumme und `lizenz.json`, `liste`, `kosten tripo`.
- `ms blender render`: Stichprobe, Entwurf, Teilbereich, `--weiter`, `--blend`, `--alpha`, Cycles, Fehler im Skript (Traceback wird gezeigt, Live-Log `fehler`).
- `ms blender komposition` + `ms szenen` + `npx hyperframes lint` (0 Fehler) + Snapshot + Render: das Blender-Video erscheint in HyperFrames, auch mit Transparenz über einer anderen Szene.
- msblend: HDRI mit eigener Hintergrundfarbe, Drei-Punkt, Studio, Sonne, PBR mit Poly-Haven-Texturen, Toon mit Kontur (EEVEE und Cycles), Text mit Umlauten, GLB-Import mit Höhe, FBX-Figur mit Bewegung (NLA), Funken, Konfetti, Glühen, alle Kamerafahrten, Easing (gleiche Werte in 4.3 und 5.2).
- Nicht getestet: Windows und Linux (Suchpfade und `nice` sind abgefangen), echte Mixamo-, Sketchfab- und Tripo-Dateien, Blender 4.2 und 4.4/4.5 (dazwischen, sollte laufen), MCP-Wege.
