"""Original gegen Nachbau messen: ΔE2000 und SSIM pro Szene und gesamt, Paarbögen, Nebeneinander-Video, Ampel.
  ms vergleich <original.mp4> <nachbau.mp4>                       Szenen aus der Folge des Nachbaus (build/scenes.json)
  ms vergleich <original.mp4> <nachbau.mp4> --szenen scenes.json  Szenen-Datei angeben (Zeiten im Nachbau)
  ms vergleich <original.mp4> <nachbau.mp4> --zeitversatz-suchen  besten Versatz per Bewegungs-Kurve finden und benutzen
                                                                   (verlässlich ab Korrelation 0,6, darunter WARNUNG)
  --versatz 0.12    Nachbau läuft 0,12 s später als das Original (nachbau_t = original_t + versatz)
  --von 5 --bis 15  Zeitfenster im Original: Nachbau-Zeit 0 = Original-Zeit 5 (Pilot über einen Ausschnitt).
                    Ohne Angabe beim Pilot automatisch aus voice/stimme.json ("ms stimme --original --von/--bis"),
                    wenn das ganze Original übergeben wird. Einfacher: vorbild/ausschnitt.mp4 der Pilot-Folge nehmen
                    (gleiche Zeitachse wie der Pilot, dann kein Fenster nötig).
  --fps 4           Messbilder pro Sekunde (Standard 4)
  --out <ordner>    Ergebnis-Ordner (Standard: <folge>/out/vergleich_<nachbau>/ bzw. neben dem Nachbau)
  --ohne-video      kein Nebeneinander-Video (spart 10 bis 30 s)
Beispiel Pilot: ms vergleich <pilot>/vorbild/ausschnitt.mp4 <pilot>/out/pilot-v3.mp4 --zeitversatz-suchen

Messwerte (beide Videos auf 540×960 skaliert, hochkant; quer 960×540)
  ΔE2000  mittlerer Farbabstand in Lab (CIEDE2000) über alle Pixel. 0 = gleich, < 2 kaum sichtbar.
  SSIM    Strukturähnlichkeit der Helligkeit (Fenster 7×7). 1 = gleich.
  grob    ΔE76 + SSIM auf 90×160: so wurde im Referenz-Nachbau gemessen (vergleichbar mit den Richtwerten unten).
Ampel pro Szene (Art aus scenes.json), kalibriert an einem echten, abgenommenen Nachbau (Skill motion-vergleich):
  2D: grün ΔE2000 ≤ 6,5 und SSIM ≥ 0,65 · gelb ΔE2000 ≤ 9 und SSIM ≥ 0,5 · sonst rot
      (abgenommener 2D-Nachbau: ΔE2000 2,8 bis 6,5, SSIM 0,67 bis 0,90; grob ΔE76 5,3 / SSIM 0,84)
  3D: grün ΔE2000 ≤ 11 · gelb ΔE2000 ≤ 15 · sonst rot
      (3D-Nachbau: ΔE2000 12 bis 19 = grob ΔE76 16 bis 25; altes Ziel ΔE76 < 15 entspricht ΔE2000 ≈ 11)
Ergebnis: vergleich.json, VERGLEICH.md, paar_<szene>.jpg (Original links | Nachbau rechts), nebeneinander.mp4.
Liegt der Nachbau in einer Folge, landen die Gesamtwerte in STATUS.json (messwerte), beim Pilot auch Phase "vergleich"."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import _bau
import _ms

KORR_MIN = 0.6   # ab dieser Korrelation der Bewegungs-Kurven ist ein gesuchter Zeitversatz verlässlich
GRENZEN = {  # (grün ΔE2000, grün SSIM, gelb ΔE2000, gelb SSIM), kalibriert 20.10.2026 an einem 2D- und einem 3D-Nachbau
    '2d': (6.5, 0.65, 9.0, 0.5),
    '3d': (11.0, 0.0, 15.0, 0.0),
}


# ---------------------------------------------------------------- Farbe und Struktur (numpy, keine weiteren Pakete)

def lab(rgb):
    """sRGB uint8 (H, W, 3) -> CIE Lab (D65), float32."""
    import numpy as np
    c = rgb.astype(np.float32) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]],
                 dtype=np.float32)
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883], dtype=np.float32)
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def delta_e2000(lab1, lab2):
    """CIEDE2000 pro Pixel (Sharma, Wu, Dalal 2005), vektorisiert."""
    import numpy as np
    L1, a1, b1 = lab1[..., 0], lab1[..., 1], lab1[..., 2]
    L2, a2, b2 = lab2[..., 0], lab2[..., 1], lab2[..., 2]
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2)
    Cm7 = ((C1 + C2) / 2) ** 7
    G = 0.5 * (1 - np.sqrt(Cm7 / (Cm7 + 25.0 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    dh = h2p - h1p
    dh = np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh))
    dh = np.where(C1p * C2p == 0, 0, dh)
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh / 2))
    Lpm, Cpm = (L1 + L2) / 2, (C1p + C2p) / 2
    hs = h1p + h2p
    hpm = np.where(np.abs(h1p - h2p) > 180, np.where(hs < 360, (hs + 360) / 2, (hs - 360) / 2), hs / 2)
    hpm = np.where(C1p * C2p == 0, hs, hpm)
    T = (1 - 0.17 * np.cos(np.radians(hpm - 30)) + 0.24 * np.cos(np.radians(2 * hpm))
         + 0.32 * np.cos(np.radians(3 * hpm + 6)) - 0.20 * np.cos(np.radians(4 * hpm - 63)))
    dtheta = 30 * np.exp(-(((hpm - 275) / 25) ** 2))
    Cpm7 = Cpm ** 7
    Rc = 2 * np.sqrt(Cpm7 / (Cpm7 + 25.0 ** 7))
    Sl = 1 + 0.015 * (Lpm - 50) ** 2 / np.sqrt(20 + (Lpm - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cpm, 1 + 0.015 * Cpm * T
    Rt = -np.sin(np.radians(2 * dtheta)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def _box(x, w):
    import numpy as np
    s = np.pad(x, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    return (s[w:, w:] - s[:-w, w:] - s[w:, :-w] + s[:-w, :-w]) / (w * w)


def ssim(g1, g2, w=7, bereich=255.0):
    """SSIM wie scikit-image (gleichförmiges 7×7-Fenster, Stichproben-Kovarianz), Mittel über das gültige Bild."""
    import numpy as np
    x, y = g1.astype(np.float64), g2.astype(np.float64)
    n = w * w
    k = n / (n - 1)
    ux, uy = _box(x, w), _box(y, w)
    vx = k * (_box(x * x, w) - ux * ux)
    vy = k * (_box(y * y, w) - uy * uy)
    vxy = k * (_box(x * y, w) - ux * uy)
    c1, c2 = (0.01 * bereich) ** 2, (0.03 * bereich) ** 2
    s = ((2 * ux * uy + c1) * (2 * vxy + c2)) / ((ux * ux + uy * uy + c1) * (vx + vy + c2))
    return float(s.mean())


def luma(rgb):
    import numpy as np
    return rgb.astype(np.float32) @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def messen(a, b):
    """Ein Bildpaar (gleiche Größe, uint8 RGB) -> (ΔE2000 fein, SSIM fein, ΔE76 grob, SSIM grob)."""
    import numpy as np
    from PIL import Image
    de = float(delta_e2000(lab(a), lab(b)).mean())
    ss = ssim(luma(a), luma(b))
    klein = (90, 160) if a.shape[0] >= a.shape[1] else (160, 90)
    ka = np.asarray(Image.fromarray(a).resize(klein, Image.BOX))
    kb = np.asarray(Image.fromarray(b).resize(klein, Image.BOX))
    de76 = float(np.sqrt(((lab(ka) - lab(kb)) ** 2).sum(-1)).mean())
    ss_g = ssim(ka.astype(np.float32).mean(-1), kb.astype(np.float32).mean(-1))
    return de, ss, de76, ss_g


# ---------------------------------------------------------------- Zeitversatz

def energie(video, fps=10, start=0.0, ende=None):
    import numpy as np
    kurve, vorher = [], None
    for _, g in _ms.frames(video, fps=fps, groesse=(54, 96), grau=True, start=start, ende=ende):
        g = g.astype(np.float32)
        kurve.append(0.0 if vorher is None else float(np.abs(g - vorher).mean()))
        vorher = g
    return np.array(kurve, dtype=np.float64)


def versatz_suchen(original, nachbau, max_s=2.0, fps=10, start_o=0.0, ende_o=None):
    """Bester Versatz (Sekunden, nachbau_t = (original_t - start_o) + v) per normierter Korrelation der Bewegungs-Energie.
    start_o/ende_o: Zeitfenster im Original (Pilot über einen Ausschnitt)."""
    import numpy as np
    eo, en = energie(original, fps, start=start_o, ende=ende_o), energie(nachbau, fps)
    if len(eo) < 5 or len(en) < 5:
        return 0.0, 0.0
    eo = (eo - eo.mean()) / (eo.std() + 1e-6)
    en = (en - en.mean()) / (en.std() + 1e-6)
    best, best_r = 0, -9.0
    for lag in range(-int(max_s * fps), int(max_s * fps) + 1):
        if lag >= 0:
            x, y = eo[: len(eo) - lag] if lag else eo, en[lag:]
        else:
            x, y = eo[-lag:], en[: len(en) + lag]
        n = min(len(x), len(y))
        if n < 10:
            continue
        r = float(np.mean(x[:n] * y[:n]))
        if r > best_r:
            best, best_r = lag, r
    return best / fps, best_r


# ---------------------------------------------------------------- Ausgabe

def ampel(art: str, de: float, ss: float) -> str:
    g = GRENZEN['3d' if str(art).lower().startswith(('3d', 'blender')) else '2d']
    if de <= g[0] and ss >= g[1]:
        return 'grün'
    if de <= g[2] and ss >= g[3]:
        return 'gelb'
    return 'rot'


def paarbogen(paare, ziel: Path, titel: str, spalten=6, breite=180):
    """paare = [(t_original, t_nachbau, bild_o, bild_n, ΔE)] -> Bogen: je Kachel Original links | Nachbau rechts."""
    from PIL import Image, ImageDraw
    if not paare:
        return None
    h = paare[0][2].shape[0] * breite // paare[0][2].shape[1]
    kw, kh = 2 * breite + 4, h + 20
    zeilen = math.ceil(len(paare) / spalten)
    b = Image.new('RGB', (spalten * (kw + 8), 32 + zeilen * (kh + 8)), (24, 24, 24))
    z = ImageDraw.Draw(b)
    z.text((8, 6), titel + '   (links Original | rechts Nachbau)', fill=(255, 255, 255), font=_ms._schrift(18))
    klein = _ms._schrift(13)
    for i, (to, tn, a, c, de) in enumerate(paare):
        x, y = (i % spalten) * (kw + 8), 32 + (i // spalten) * (kh + 8)
        k = Image.new('RGB', (kw, kh), (255, 0, 255))
        k.paste(Image.fromarray(a).resize((breite, h), Image.LANCZOS), (0, 20))
        k.paste(Image.fromarray(c).resize((breite, h), Image.LANCZOS), (breite + 4, 20))
        dz = ImageDraw.Draw(k)
        dz.rectangle((0, 0, kw, 19), fill=(0, 0, 0))
        dz.text((3, 2), f'{to:.2f}s  ΔE {de:.1f}', fill=(255, 230, 90), font=klein)
        b.paste(k, (x, y))
    ziel.parent.mkdir(parents=True, exist_ok=True)
    b.save(ziel, quality=88)
    return ziel


def nebeneinander(original, nachbau, versatz, ziel: Path, laenge=None):
    eo = ['-ss', f'{-versatz:.3f}'] if versatz < 0 else []
    en = ['-ss', f'{versatz:.3f}'] if versatz > 0 else []
    fc = '[0:v]scale=-2:960,setsar=1[a];[1:v]scale=-2:960,setsar=1[b];[a][b]hstack=inputs=2:shortest=1[v]'
    dauer = ['-t', f'{laenge:.3f}'] if laenge else []
    _ms.befehl(['ffmpeg', '-nostdin', '-v', 'error', '-y', *eo, '-i', original, *en, '-i', nachbau, '-filter_complex', fc,
                '-map', '[v]', '-map', '1:a?', '-c:v', 'libx264', '-crf', '20', '-preset', 'veryfast', '-c:a', 'aac',
                *dauer, '-shortest', ziel])
    return ziel


def folge_von(pfad: Path):
    try:
        rel = pfad.resolve().relative_to((_ms.arbeit() / 'folgen').resolve())
    except ValueError:
        return None
    d = _ms.arbeit() / 'folgen' / rel.parts[0]
    return d if (d / 'STATUS.json').exists() else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('original')
    ap.add_argument('nachbau')
    ap.add_argument('--szenen')
    ap.add_argument('--fps', type=float, default=4.0)
    ap.add_argument('--versatz', type=float, default=0.0)
    ap.add_argument('--von', type=float, help='Zeitfenster im Original: Beginn in s (= Nachbau-Zeit 0)')
    ap.add_argument('--bis', type=float, help='Zeitfenster im Original: Ende in s')
    ap.add_argument('--zeitversatz-suchen', action='store_true')
    ap.add_argument('--max-versatz', type=float, default=2.0)
    ap.add_argument('--out')
    ap.add_argument('--ohne-video', action='store_true')
    a = ap.parse_args()
    try:
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        raise SystemExit('FEHLER: numpy und Pillow fehlen in der Studio-Python-Umgebung ("ms check").')

    org, nach = Path(a.original).resolve(), Path(a.nachbau).resolve()
    for p in (org, nach):
        if not p.exists():
            raise SystemExit(f'FEHLER: {p} gibt es nicht.')
    fo = folge_von(nach)
    out = Path(a.out).resolve() if a.out else ((fo / 'out' if fo else nach.parent) / f'vergleich_{nach.stem}')
    out.mkdir(parents=True, exist_ok=True)
    io, inn = _ms.probe(org), _ms.probe(nach)
    hoch = io['hoehe'] >= io['breite']
    groesse = (540, 960) if hoch else (960, 540)

    von, bis = a.von, a.bis
    if von is None and bis is None and fo:
        si = _ms.json_lesen(fo / 'voice' / 'stimme.json', {}) or {}
        if si.get('original_von') is not None and si.get('original'):
            q = Path(si['original']).expanduser()
            q = q if q.is_absolute() else _ms.arbeit() / q
            if q.exists() and q.resolve() == org:
                von, bis = float(si['original_von']), si.get('original_bis')
                print(f'Pilot-Fenster aus voice/stimme.json: Original {von:.2f} bis {float(bis or io["dauer"]):.2f} s = Nachbau ab 0.')
    von = max(0.0, float(von or 0.0))
    if bis is not None and float(bis) <= von + 0.2:
        raise SystemExit('FEHLER: --bis muss nach --von liegen.')
    versatz, korr = a.versatz - von, None
    if a.zeitversatz_suchen:
        fein, korr = versatz_suchen(org, nach, a.max_versatz, start_o=von, ende_o=bis)
        versatz = fein - von
        print(f'Zeitversatz: {fein:+.2f} s (Korrelation {korr:.2f}; nachbau_t = original_t {versatz:+.2f})')
        if korr < KORR_MIN:
            print(f'WARNUNG: Korrelation {korr:.2f} unter {KORR_MIN:.1f}, der gefundene Versatz ist nicht verlässlich '
                  f'(Bewegung von Original und Nachbau zu verschieden oder zu wenig Bewegung). Paarbögen ansehen, '
                  f'bei Zweifel ohne --zeitversatz-suchen messen (oder --versatz von Hand).')
    so, sn = max(0.0, -versatz), max(0.0, versatz)
    laenge = min(io['dauer'] - so, inn['dauer'] - sn)
    if bis is not None:
        laenge = min(laenge, float(bis) - so)
    if laenge <= 0.2:
        raise SystemExit('FEHLER: nach dem Versatz bleibt keine gemeinsame Zeit übrig.')

    szenen = None
    sz_datei = Path(a.szenen) if a.szenen else (fo / 'build' / 'scenes.json' if fo else None)
    if sz_datei and sz_datei.exists():
        roh = _ms.json_lesen(sz_datei)
        szenen = sorted((roh.get('szenen') if isinstance(roh, dict) else roh) or [], key=lambda s: float(s['start']))
    if not szenen:
        schritt = 2.0
        szenen = [{'id': f'a{i + 1}', 'start': sn + i * schritt, 'dur': schritt, 'art': '2d', 'inhalt': 'Abschnitt'}
                  for i in range(int(math.ceil(laenge / schritt)))]
        print('Keine scenes.json: Abschnitte à 2 s, Ampel nach 2D-Grenzen.')

    def szene_bei(tn):
        kand = [s for s in szenen if float(s['start']) <= tn < float(s['start']) + float(s['dur'])]
        return max(kand, key=lambda s: s.get('track', 1)) if kand else None

    # Welche Bilder kommen in die Paarbögen (höchstens 12 pro Szene, gleichmäßig)
    n_bilder = int(laenge * a.fps)
    proszene = {}
    for k in range(n_bilder):
        s = szene_bei(sn + k / a.fps)
        if s:
            proszene.setdefault(s['id'], []).append(k)
    behalten = set()
    for ks in proszene.values():
        schritt = max(1, math.ceil(len(ks) / 12))
        behalten.update(ks[::schritt])

    print(f'Messe {n_bilder} Bildpaare ({a.fps:g}/s, {groesse[0]}×{groesse[1]}) …', flush=True)
    werte, paare = [], {}
    strom_o = _ms.frames(org, fps=a.fps, groesse=groesse, start=so, ende=so + laenge)
    strom_n = _ms.frames(nach, fps=a.fps, groesse=groesse, start=sn, ende=sn + laenge)
    for k, ((to, bo), (tn, bn)) in enumerate(zip(strom_o, strom_n)):
        de, ss, de76, ssg = messen(bo, bn)
        s = szene_bei(tn)
        werte.append({'t_original': round(to, 3), 't_nachbau': round(tn, 3), 'szene': s['id'] if s else None,
                      'de2000': round(de, 3), 'ssim': round(ss, 4), 'de76_grob': round(de76, 3), 'ssim_grob': round(ssg, 4)})
        if k in behalten and s:
            from PIL import Image
            import numpy as np
            klein = (180, 320) if hoch else (320, 180)
            paare.setdefault(s['id'], []).append((to, tn, np.asarray(Image.fromarray(bo).resize(klein, Image.BOX)),
                                                  np.asarray(Image.fromarray(bn).resize(klein, Image.BOX)), de))
    if not werte:
        raise SystemExit('FEHLER: keine Bilder gelesen (Videos beschädigt?).')

    def mittel(liste, k):
        return round(sum(w[k] for w in liste) / len(liste), 3) if liste else None

    ergebnis_szenen = []
    for s in szenen:
        ws = [w for w in werte if w['szene'] == s['id']]
        if not ws:
            continue
        de, ss = mittel(ws, 'de2000'), mittel(ws, 'ssim')
        ergebnis_szenen.append({'id': s['id'], 'art': s.get('art', '2d'), 'start': float(s['start']), 'dur': float(s['dur']),
                                'bilder': len(ws), 'de2000': de, 'de2000_max': round(max(w['de2000'] for w in ws), 3),
                                'ssim': ss, 'de76_grob': mittel(ws, 'de76_grob'), 'ssim_grob': mittel(ws, 'ssim_grob'),
                                'ampel': ampel(s.get('art', '2d'), de, ss)})
    gesamt = {'de2000': mittel(werte, 'de2000'), 'ssim': mittel(werte, 'ssim'), 'de76_grob': mittel(werte, 'de76_grob'),
              'ssim_grob': mittel(werte, 'ssim_grob'), 'bilder': len(werte)}
    gesamt['ampel'] = 'rot' if any(s['ampel'] == 'rot' for s in ergebnis_szenen) else (
        'gelb' if any(s['ampel'] == 'gelb' for s in ergebnis_szenen) else 'grün')

    boegen = []
    for s in ergebnis_szenen:
        b = paarbogen(paare.get(s['id'], []), out / f"paar_{s['id']}.jpg",
                      f"{s['id']} ({s['art']})  ΔE2000 {s['de2000']:.1f}  SSIM {s['ssim']:.2f}  {s['ampel']}")
        if b:
            boegen.append(b)
    video = None
    if not a.ohne_video:
        print('Nebeneinander-Video …', flush=True)
        video = nebeneinander(org, nach, versatz, out / 'nebeneinander.mp4', laenge if (von or bis is not None) else None)

    erg = {'original': str(org), 'nachbau': str(nach), 'versatz': versatz, 'korrelation': korr, 'fps': a.fps,
           'fenster_original': [round(so, 3), round(so + laenge, 3)],
           'groesse': list(groesse), 'gesamt': gesamt, 'szenen': ergebnis_szenen, 'grenzen': GRENZEN,
           'paarboegen': [b.name for b in boegen], 'video': video.name if video else None, 'bilder': werte,
           'zeit': _ms.jetzt()}
    _ms.json_schreiben(out / 'vergleich.json', erg)
    schlecht = sorted(ergebnis_szenen, key=lambda s: -s['de2000'])
    md = [f'# Vergleich {nach.name} gegen {org.name}', '',
          f'Gesamt: **ΔE2000 {gesamt["de2000"]:.2f} · SSIM {gesamt["ssim"]:.3f}** (grob wie Referenz: ΔE76 {gesamt["de76_grob"]:.1f} · '
          f'SSIM {gesamt["ssim_grob"]:.3f}) · Ampel **{gesamt["ampel"]}**',
          f'Versatz {versatz:+.2f} s' + (f' (gesucht, Korrelation {korr:.2f}'
                                         + (f', **unter {KORR_MIN:.1f}: Versatz unsicher**' if korr < KORR_MIN else '') + ')'
                                         if korr is not None else '') +
          (f' · Original {so:.2f} bis {so + laenge:.2f} s' if so > 0.001 else '') +
          f' · {len(werte)} Bildpaare à {a.fps:g}/s auf {groesse[0]}×{groesse[1]}', '',
          '| Szene | Art | Zeit (Nachbau) | ΔE2000 | ΔE max | SSIM | ΔE76 grob | SSIM grob | Ampel |',
          '|---|---|---|---|---|---|---|---|---|']
    for s in ergebnis_szenen:
        md.append(f"| {s['id']} | {s['art']} | {s['start']:.2f} bis {s['start'] + s['dur']:.2f} | {s['de2000']:.2f} | {s['de2000_max']:.1f} | "
                  f"{s['ssim']:.3f} | {s['de76_grob']:.1f} | {s['ssim_grob']:.3f} | {s['ampel']} |")
    md += ['', '## Richtwerte', '',
           '- 2D grün: ΔE2000 ≤ 6,5 und SSIM ≥ 0,65, gelb: ΔE2000 ≤ 9 und SSIM ≥ 0,5. 3D grün: ΔE2000 ≤ 11, gelb ≤ 15.',
           '- Referenz abgenommener 2D-Nachbau: ΔE2000 4,8 / SSIM 0,78 (grob ΔE76 5,3 / SSIM 0,84). '
           '3D-Nachbau: ΔE2000 12 bis 19 je Szene (grob ΔE76 16, Ziel < 15 knapp verfehlt).',
           '- Das Original gegen sich selbst mit kleinen Abweichungen (Figuren leicht gedreht) lag schon bei ΔE76 11: 3D nie auf 0 jagen.',
           '', '## Als Nächstes', '',
           f"- Schlechteste Szene zuerst: {', '.join(s['id'] + ' ' + str(s['de2000']) for s in schlecht[:3])}",
           '- Paarbogen der Szene ansehen, EINE Ursache benennen (Farbe, Lage, Größe, Timing), eine Variable ändern, neu messen.',
           '- Nach 3 Fehlversuchen an einer Szene: Mensch fragen (Bilder mitschicken).', '', '## Dateien', '']
    md += [f'- {b.name}' for b in boegen] + ([f'- {video.name}'] if video else []) + ['- vergleich.json (alle Bildpaare)']
    (out / 'VERGLEICH.md').write_text('\n'.join(md) + '\n', encoding='utf-8')

    if fo:
        mw = {'delta_e': gesamt['de2000'], 'ssim': gesamt['ssim'], 'delta_e76_grob': gesamt['de76_grob'],
              'ssim_grob': gesamt['ssim_grob'], 'ampel': gesamt['ampel'], 'video': nach.name,
              'szenen': {s['id']: {'de': s['de2000'], 'ssim': s['ssim'], 'ampel': s['ampel']} for s in ergebnis_szenen}}
        st = _ms.status_lesen(fo)
        notiz = f'Vergleich {nach.name}: ΔE2000 {gesamt["de2000"]:.2f}, SSIM {gesamt["ssim"]:.3f}, {gesamt["ampel"]}'
        _ms.status_setzen(fo, 'vergleich' if st.get('art') == 'pilot' else None, notiz, messwerte=mw)
        kanal = _bau.kanal_ordner(fo)
        if kanal and _ms.status_lesen(kanal).get('pilot') == f'folgen/{fo.name}':
            _ms.status_setzen(kanal, None, None, messwerte=mw)
        if st.get('art') != 'pilot':
            _ms.log(notiz, ziel=_ms.ziel_name(fo))

    print(f'Gesamt: ΔE2000 {gesamt["de2000"]:.2f} · SSIM {gesamt["ssim"]:.3f} · grob ΔE76 {gesamt["de76_grob"]:.2f} / '
          f'SSIM {gesamt["ssim_grob"]:.3f} · Ampel {gesamt["ampel"]}')
    for s in ergebnis_szenen:
        print(f"  {s['id']:<6} {s['art']:<7} ΔE2000 {s['de2000']:6.2f}  SSIM {s['ssim']:.3f}  grob {s['de76_grob']:5.1f}/{s['ssim_grob']:.3f}  {s['ampel']}")
    print(out / 'VERGLEICH.md')
    for b in boegen:
        print(b)
    if video:
        print(video)
    return 0


if __name__ == '__main__':
    sys.exit(main())
