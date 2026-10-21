"""Beispielszene (Muster für den Bauer): Produkt fällt auf eine Bühne, Funken beim Aufprall, Text ploppt auf,
Kamera fährt langsam ran und kreist leicht. Licht aus HDRI (falls angegeben), sonst Drei-Punkt-Licht.

Start (Entwurf, 540x960):
  ms blender render __HEIM__/blender/beispiel_szene.py --folge <id> --szene s1 --entwurf --dauer 3
Voll (1080x1920) mit eigenem Text und HDRI:
  ms blender render __HEIM__/blender/beispiel_szene.py --folge <id> --szene s1 -- --text "NEU" --hdri polyhaven:studio_small_09

Eigene Parameter (nach den ms-Parametern, hinter `--`):
  --text "NEU"            Text über dem Produkt (Umlaute gehen)
  --farbe "#ff5a1f"       Markenfarbe (Dose)
  --akzent "#1f2433"      zweite Farbe (Sockel, Text)
  --buehne "#f1e7da"      Farbe der Bühne
  --hdri polyhaven:<id>   Licht aus HDRI (vorher: ms assets laden polyhaven <id> --aufloesung 1k) oder Pfad .hdr/.exr
  --hdri-drehung 260      HDRI drehen (Grad), verschiebt Lichtrichtung und Schatten
  --modell polyhaven:<id> statt der Dose ein fertiges Modell (.glb/.gltf/.fbx oder Poly-Haven-Modell)
  --schrift <datei.ttf>   eigene Schrift
  --ohne-konfetti         kein Konfetti beim Text

Aufbau zum Abschauen: Zeiten als Anteil der Dauer (Szene skaliert mit --dauer), alles über msblend, kein Zufall ohne seed.
"""
import os
import sys

sys.path.insert(0, os.environ.get('MS_BLENDER_LIB') or os.path.dirname(os.path.abspath(__file__)))
import msblend as mb  # noqa: E402

# 1) Start: Argumente, leere Szene, Render. 'neutral' hält Produktfarben nah am Hex-Wert.
p = mb.start(dauer=3.0, farbe='neutral', bewegungsunschaerfe=True)
D = p.dauer
TEXT = mb.arg('--text', 'NEU')
FARBE = mb.arg('--farbe', '#ff5a1f')
AKZENT = mb.arg('--akzent', '#1f2433')
BUEHNE = mb.arg('--buehne', '#f1e7da')
HDRI = mb.arg('--hdri', None)
HDRI_DREHUNG = mb.arg('--hdri-drehung', 260.0, float)
MODELL = mb.arg('--modell', None)
SCHRIFT = mb.arg('--schrift', None)
KONFETTI = not mb.arg('--ohne-konfetti', False)

# 2) Zeitplan (Sekunden)
T_AUFPRALL = 0.30 * D
T_TEXT = T_AUFPRALL + 0.18
T_KONFETTI = T_TEXT + 0.05

# 3) Bühne und Sockel
mb.hohlkehle(farbe=BUEHNE, wand_y=3.5)
sockel_mat = mb.material_pbr(AKZENT, rauheit=0.32, klarlack=0.6, name='Sockel')
mb.form('zylinder', (0, 0, 0.25), (2.3, 2.3, 0.5), material=sockel_mat, fase=0.04, name='Sockel')
ring = mb.form('torus', (0, 0, 0.5), 2.42, rohr=0.035, material=mb.material_emission(FARBE, 1.2), name='Ring')
OBEN = 0.5  # Oberkante Sockel

# 4) Produkt: eine Dose aus Grundformen (oder ein fertiges Modell)
if MODELL:
    produkt = (mb.fbx_import if str(MODELL).lower().endswith('.fbx') else mb.glb_import)(
        MODELL, pos=(0, 0, OBEN), hoehe=1.3, name='Produkt')
else:
    produkt = mb.leer('Produkt', (0, 0, OBEN))
    lack = mb.material_pbr(FARBE, rauheit=0.22, klarlack=1.0, name='Dosenlack')
    alu = mb.material_pbr('#d9dde3', rauheit=0.18, metall=1.0, name='Alu')
    weiss = mb.material_pbr('#fbf7f0', rauheit=0.35, name='Etikett')
    teile = [mb.form('zylinder', (0, 0, 0.66), (0.84, 0.84, 1.18), material=lack, fase=0.03, name='Dose'),
             mb.form('zylinder', (0, 0, 1.27), (0.76, 0.76, 0.06), material=alu, fase=0.015, name='Deckel'),
             mb.form('zylinder', (0, 0, 0.05), (0.76, 0.76, 0.1), material=alu, fase=0.02, name='Boden'),
             mb.form('zylinder', (0, 0, 0.72), (0.852, 0.852, 0.2), material=weiss, name='Band')]
    for teil in teile:
        mb.eltern(teil, produkt)

# 5) Bewegung: fällt, Aufprall mit Squash, dreht sich langsam (Drehteller)
mb.fallen_lassen(produkt, 0.0, T_AUFPRALL, hoehe=4.0, nachhuepfen=0.22, quetsch=0.22)
produkt.rotation_euler.z = 0.35
mb.drehen(produkt, 0.0, D, umdrehungen=0.3, ease='sine.inout')
mb.ploppen(ring, T_AUFPRALL, dauer=0.4, ease='expo.out')

# 6) Funken beim Aufprall, Leuchten
mb.partikel_einfach((0, 0, OBEN + 0.02), T_AUFPRALL, anzahl=110, art='funken', seed=p.seed, tempo=7.0,
                    dauer=0.9, streuung=80)
mb.gluehen(staerke=0.55, schwelle=3.0, groesse=7)

# 7) Text ploppt auf (passt sich der Bildbreite an)
text_mat = mb.material_pbr(AKZENT, rauheit=0.55, name='Textlack')  # matt: glänzender Text spiegelt Softboxen weg
text = mb.text_objekt(TEXT, schrift=SCHRIFT, groesse=0.9, tiefe=0.09, fase=0.015, pos=(0, 0.2, 2.8),
                      material=text_mat, max_breite=1.7)
mb.ploppen(text, T_TEXT, dauer=0.45, ease='back.out')
if KONFETTI:
    mb.partikel_einfach((0, -0.8, 3.3), T_KONFETTI, anzahl=80, art='konfetti', seed=p.seed + 1, tempo=4.0,
                        dauer=max(0.5, D - T_KONFETTI), richtung=(0, 0, 1), streuung=65)

# 8) Licht: HDRI (Hintergrundfarbe bleibt die Bühne) oder Drei-Punkt
if HDRI:
    mb.hdri(HDRI, staerke=1.1, drehung=HDRI_DREHUNG, hintergrund=BUEHNE)
    mb.licht('AREA', (2.6, 3.0, 1.4), (0, 0, 0.9), 300, '#ffffff', 1.2, 'Kante')  # unter Texthöhe, trennt nur das Produkt
else:
    mb.licht_preset('drei_punkt', ziel=(0, 0, 1.2))

# 9) Kamera: Push-in mit leichtem Orbit, kurzes Wackeln beim Aufprall
cam = mb.kamera((0, -8.2, 2.1), (0, 0, 1.55), brennweite=50)
mb.orbit(cam, 0.0, D, winkel=-10, ease='sine.inout')
mb.push_in(cam, 0.0, D, faktor=0.8, ease='sine.inout')
mb.kamera_wackeln(cam, T_AUFPRALL, dauer=0.3, staerke=0.035, seed=p.seed)

# 10) Rendern (PNG-Sequenz, Zeit pro Bild wird gemessen)
mb.rendern(p)
