"""Video zerlegen: Schnitte, Szenen, Kontaktbögen, Palette, Bewegung und Kamera, Text (OCR), Captions, Rhythmus, Typ.
  ms zerlegen <video|register-id> [--kanal <slug>] [--out <ordner>]
Optionen:
  --schwelle 3.0          Schnitt = Bilddifferenz mindestens so oft über ihrer Umgebung (kleiner = mehr Schnitte)
  --abstand 0.2           Mindestabstand zweier Schnitte in s
  --ocr-fps 2             Bilder pro Sekunde für Texterkennung, Palette und Typ (höchstens 240 Bilder)
  --sprachen de-DE,en-US  OCR-Sprachen (Standard: automatisch)
  --ohne-ocr  --ohne-boegen
Beispiele:
  ms zerlegen yt-abc123xyz00 --kanal mein-kanal     -> kanaele/mein-kanal/analyse/yt-abc123xyz00/
  ms zerlegen ~/Downloads/vorbild.mp4           -> ~/Downloads/vorbild-analyse/
Ergebnis: analyse.json, ANALYSE.md, boegen/uebersicht_NN.jpg (1 Bild/s, Szenennummer + roter Balken am Szenenwechsel),
boegen/szene_NN.jpg (4 Bilder/s), boegen/schnitte_NN.jpg (je Schnitt 2 Bilder davor, 2 danach), boegen/energie.png.
Bewegung: ruhige Phasen, Kamera je Szene, dazu Kamera-Ereignisse IN einer Szene (kurze Bewegungs-Spitze ohne Schnitt mit
Zoom oder Ruck, z. B. Punch rein +30 % in 0,5 s) und Bewegungs-Spitzen ohne Kamera (Objekt ploppt oder wächst).
Texterkennung: macOS Vision (pyobjc oder ocr_vision.swift), sonst tesseract, sonst ohne Text.
Gestreamt, nie das ganze Video im RAM. Typ und Machbarkeit sind ein Vorschlag aus Messwerten: die Bögen entscheiden."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter, deque
from pathlib import Path

import _ms

# ---------------------------------------------------------------- Grenzwerte (an zwei gemessenen Nachbauten geeicht)
ABS_MIN = 9.0          # harter Schnitt: mittlere Grauwert-Differenz (0-255) mindestens so groß
HIST_MIN = 0.12        # und die Farbverteilung ändert sich mindestens so stark (0-1)
STRUKTUR_MAX = 0.55    # und die Kanten-Korrelation der Nachbarbilder liegt darunter (Lichtwechsel/Pops bleiben darüber)
WISCH_MIN = 10.0       # Wisch-Übergang: mehrere Frames hintereinander mit hoher Differenz
UEBERBL_MIN = 12.0     # Überblendung: Unterschied Anfang/Ende des Fensters
STILL_MAX = 0.25       # ruhige Phase: geglättete Differenz (auf 30 fps umgerechnet) darunter
SPITZE_MIN = 2.0       # Energie-Spitze in einer Szene: geglättete Differenz (auf 30 fps) mindestens so hoch
SPITZE_FAKTOR = 4.0    # und so oft über dem ruhigen Umfeld (Median über 1 s)
SPITZE_DAUER = (0.08, 1.0)   # s: kürzer = Flackern, länger = Kamerafahrt (steht dann in der Kamera-Spalte der Szene)
ZOOM_MIN = 0.06        # Skalenänderung ab 6 % während der Spitze = schneller Zoom / Punch
LAGE_MIN = 6.0         # Verschiebung in % der Bildbreite = Ruck/Schwenk (neben einem Zoom erst ab 10)
STILL_DAUER = 1.5      # s
# Typ-Grenzen, geeicht an: 2D-Vektor (flach >= 0,75, <= 30 Farbtöne), 2D-Papiercollage (flach 0,3-0,7, 30-90 Farbtöne,
# Paletten-Abdeckung >= 0,65), 3D-Toon (100-240 Farbtöne, Abdeckung 0,27-0,6), KI-Video (flach < 0,3, Verlauf > 0,5).
# Schärfe = Anteil harter Kanten an allen Kanten: 2D 0,10-0,48, 3D-Toon 0,01-0,20, KI-Video 0,00-0,09.
TYP_GRENZEN = {'flach_2d': 0.60, 'schaerfe_real': 0.10, 'verlauf_real': 0.45, 'farben_3d': 100, 'abdeckung_3d': 0.60,
               'text_ui': 0.12, 'farben_blender': 300, 'verlauf_blender': 0.45}

TYPEN = {
    '2d': ('2D-Collage/Typo', 'gut nachbaubar mit HyperFrames und GSAP (Skill motion-szene-2d)',
           'Richtwert aus einem gemessenen Nachbau (30-s-Collage): ΔE ≈ 5, SSIM ≈ 0,84 erreicht'),
    'ui': ('UI/Screen', 'gut nachbaubar als HTML/CSS-Oberfläche in HyperFrames (motion-szene-2d)',
           'Richtwert wie 2D (ΔE ≈ 5), wenn die Schriften gefunden werden'),
    '3d-web': ('3D, Web-tauglich', 'machbar mit Three.js in HyperFrames (motion-szene-3d-web)',
               'Richtwert einfache 3D-Szenen: ΔE ≈ 16 erreicht, Ziel < 15 knapp verfehlt. Hauptfehler: Figuren-Proportionen'),
    '3d-blender': ('3D, Blender-Niveau', 'nur mit der Blender-Spur (motion-szene-blender, Beta)',
                   'Szene, Licht, Kamera klappen. Figuren, Rig und Acting sind offen: erst eine Probe von 5-8 s messen'),
    'realfilm': ('Realfilm/KI-Video', 'als Nachbau NICHT machbar',
                 'Nur Schnitt, Captions, Ton und Struktur übernehmen. Bild: eigene Aufnahmen oder KI-Video'),
}


# ---------------------------------------------------------------- Ziel auflösen

def ziel_aufloesen(arg, kanal=None, out=None):
    """Video-Datei oder Register-ID -> (video, id, ausgabeordner, registereintrag|None)."""
    import vorlagen as V
    p = Path(arg).expanduser()
    eintrag = None
    if p.exists():
        video = p.resolve()
        for e in V.lesen()['eintraege']:
            q = V.abs_pfad(e.get('video'))
            if q and q.exists() and q.resolve() == video:
                eintrag = e
                break
        vid = eintrag['id'] if eintrag else re.sub(r'[^A-Za-z0-9_-]+', '-', video.stem).strip('-') or 'video'
    else:
        eintrag = V.finden(V.lesen(), arg)
        if not eintrag:
            raise SystemExit(f'FEHLER: "{arg}" ist weder eine Datei noch eine Register-ID (ms vorlagen liste).')
        video = V.abs_pfad(eintrag.get('video'))
        if not video or not video.exists():
            raise SystemExit(f'FEHLER: Zu {arg} gibt es noch kein Video. Erst "ms laden {arg}".')
        vid = arg
    if out:
        ordner = Path(out).expanduser()
    elif kanal:
        k = _ms.arbeit() / 'kanaele' / kanal
        if not (k / 'STATUS.json').exists():
            raise SystemExit(f'FEHLER: Kanal {kanal} gibt es nicht. Erst "ms neu kanal {kanal} --vorbild …".')
        ordner = k / 'analyse' / vid
    else:
        ordner = video.parent / f'{video.stem}-analyse'
    return video, vid, ordner.resolve(), eintrag


# ---------------------------------------------------------------- Mathe-Helfer (nur numpy)

def _np():
    import numpy as np
    return np


_FENSTER = {}


def phasenkorrelation(a, b):
    """Globale Verschiebung a -> b in Pixeln (dx > 0: Inhalt wandert nach rechts), mit Subpixel-Spitze."""
    np = _np()
    if a.shape not in _FENSTER:
        _FENSTER[a.shape] = np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1])).astype(np.float32)
    w = _FENSTER[a.shape]
    A = np.fft.rfft2((a - a.mean()) * w)
    B = np.fft.rfft2((b - b.mean()) * w)
    R = B * np.conj(A)
    R /= np.abs(R) + 1e-9
    r = np.fft.irfft2(R, s=a.shape)
    iy, ix = np.unravel_index(int(np.argmax(r)), r.shape)
    hh, ww = r.shape
    c = r[iy, ix]

    def sub(m, p):
        den = m - 2 * c + p
        return 0.5 * (m - p) / den if abs(den) > 1e-9 else 0.0
    dy = iy + sub(r[(iy - 1) % hh, ix], r[(iy + 1) % hh, ix])
    dx = ix + sub(r[iy, (ix - 1) % ww], r[iy, (ix + 1) % ww])
    if dy > hh / 2:
        dy -= hh
    if dx > ww / 2:
        dx -= ww
    return float(dx), float(dy), float(c)


def kamera_schritt(a, b):
    """Schwenk (dx, dy) und grober Zoom aus vier Bildvierteln: wandern die Viertel nach außen, wird hineingezoomt."""
    dx, dy, p = phasenkorrelation(a, b)
    h, w = a.shape
    hy, hx = h // 2, w // 2
    zaehler = nenner = 0.0
    spitzen = []
    for ys, xs, cx, cy in ((slice(0, hy), slice(0, hx), -w / 4, -h / 4), (slice(0, hy), slice(hx, w), w / 4, -h / 4),
                           (slice(hy, h), slice(0, hx), -w / 4, h / 4), (slice(hy, h), slice(hx, w), w / 4, h / 4)):
        qx, qy, qp = phasenkorrelation(a[ys, xs], b[ys, xs])
        spitzen.append(qp)
        zaehler += (qx - dx) * cx + (qy - dy) * cy
        nenner += cx * cx + cy * cy
    return dx, dy, p, zaehler / nenner, min(spitzen)


def lab(rgb):
    np = _np()
    c = rgb.astype(np.float32) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]], np.float32)
    xyz = (c @ m.T) / np.array([0.95047, 1.0, 1.08883], np.float32)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def kmeans(px, k, iter_=15, seed=7):
    """Einfaches k-Means (k-means++ Start, deterministisch). px: (n, 3). Gibt Zentren und Zuordnung zurück."""
    np = _np()
    rng = np.random.default_rng(seed)
    z = [px[rng.integers(len(px))]]
    for _ in range(1, k):
        d2 = ((px[:, None, :] - np.array(z)[None]) ** 2).sum(-1).min(1)
        if d2.sum() <= 0:
            break
        z.append(px[rng.choice(len(px), p=d2 / d2.sum())])
    z = np.array(z, np.float32)
    for _ in range(iter_):
        zu = ((px[:, None, :] - z[None]) ** 2).sum(-1).argmin(1)
        neu = np.array([px[zu == j].mean(0) if (zu == j).any() else z[j] for j in range(len(z))], np.float32)
        fertig = np.abs(neu - z).max() < 0.3
        z = neu
        if fertig:
            break
    abst = ((px[:, None, :] - z[None]) ** 2).sum(-1)
    return z, abst.argmin(1), np.sqrt(abst.min(1))


def hexfarbe(rgb) -> str:
    return '#' + ''.join(f'{int(round(min(255, max(0, float(v))))):02x}' for v in rgb)


def palette(rgb_px, k=6, min_anteil=0.02):
    """Palette aus Pixeln (n, 3) uint8: k-Means in Lab, ähnliche Farben (ΔE < 7) zusammengelegt. [{hex, anteil}]"""
    np = _np()
    if len(rgb_px) > 24000:
        rgb_px = rgb_px[np.random.default_rng(1).choice(len(rgb_px), 24000, replace=False)]
    l = lab(rgb_px)
    z, zu, _ = kmeans(l, k)
    gruppen = [[j] for j in range(len(z))]
    # ähnliche Zentren zusammenlegen
    zusammen = True
    while zusammen:
        zusammen = False
        for i in range(len(gruppen)):
            for j in range(i + 1, len(gruppen)):
                ci = l[np.isin(zu, gruppen[i])].mean(0) if np.isin(zu, gruppen[i]).any() else None
                cj = l[np.isin(zu, gruppen[j])].mean(0) if np.isin(zu, gruppen[j]).any() else None
                if ci is not None and cj is not None and np.linalg.norm(ci - cj) < 7:
                    gruppen[i] += gruppen.pop(j)
                    zusammen = True
                    break
            if zusammen:
                break
    aus = []
    for g in gruppen:
        m = np.isin(zu, g)
        if m.mean() >= min_anteil:
            aus.append({'hex': hexfarbe(np.median(rgb_px[m], axis=0)), 'anteil': round(float(m.mean()), 3),
                        '_lab': l[m].mean(0)})
    aus.sort(key=lambda x: -x['anteil'])
    return aus


def kanten_gewicht(rgb):
    np = _np()
    return rgb.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)


def merkmale(klein_rgb, mitte_grau):
    """Bildmerkmale für die Typ-Bestimmung. klein_rgb: ~120 px breit. mitte_grau: Ausschnitt in Originalauflösung."""
    np = _np()
    g = kanten_gewicht(klein_rgb)
    grad = np.abs(np.diff(g, axis=1))[:-1, :] + np.abs(np.diff(g, axis=0))[:, :-1]
    q = (klein_rgb >> 4).astype(np.int32)
    idx = (q[..., 0] << 8) | (q[..., 1] << 4) | q[..., 2]
    p = np.bincount(idx.ravel(), minlength=4096) / idx.size
    p = p[p > 0]
    c = mitte_grau.astype(np.float32)
    pad = np.pad(c, 1, mode='edge')
    blur = sum(pad[dy:dy + c.shape[0], dx:dx + c.shape[1]] for dy in range(3) for dx in range(3)) / 9.0
    rest = np.abs(c - blur)
    gb = np.abs(np.diff(blur, axis=1))[:-1, :] + np.abs(np.diff(blur, axis=0))[:, :-1]
    ruhig = gb < 4
    rest = rest[:-1, :-1]
    koernung = float(np.median(rest[ruhig])) if ruhig.mean() > 0.05 else float(np.median(rest))
    gm = np.maximum(np.abs(np.diff(c, axis=1))[:-1, :], np.abs(np.diff(c, axis=0))[:, :-1])
    schaerfe = float((gm > 40).sum() / max(1, (gm > 8).sum()))
    return {'schaerfe': schaerfe, 'flach': float((grad < 3).mean()), 'verlauf': float(((grad >= 3) & (grad < 20)).mean()),
            'kante': float((grad >= 20).mean()), 'farben': float(np.exp(-(p * np.log(p)).sum())), 'koernung': koernung}


# ---------------------------------------------------------------- Durchgang 1: alle Frames, klein, gestreamt

def _gerade(x) -> int:
    return max(4, int(round(x / 4)) * 4)


def messen(video, info):
    np = _np()
    B, H = info['breite'], info['hoehe']
    lang = 384
    w, h = (lang, _gerade(lang * H / B)) if B >= H else (_gerade(lang * B / H), lang)
    fps = info['fps'] or 30.0
    kam_schritt = max(1, int(round(fps / 6)))
    gew = np.array([0.299, 0.587, 0.114], np.float32)
    d, hd, hell, streu, h64, zeiten, kamera, ueberbl, struktur = [], [], [], [], [], [], [], [], []
    fenster = sorted({max(4, int(round(x * fps))) for x in (0.2, 0.33, 0.53)})  # Überblendung: zeitbasiert
    ring = deque(maxlen=fenster[-1] + 1)
    prev_k = prev_h = prev_cam = None
    prev_cam_t = 0.0
    for i, (t, f) in enumerate(_ms.frames(video, groesse=(w, h))):
        grau = f.astype(np.float32) @ gew
        k = grau.reshape(h // 4, 4, w // 4, 4).mean(axis=(1, 3))
        q = (f[::4, ::4] >> 5).astype(np.int32)
        hist = np.bincount(((q[..., 0] << 6) | (q[..., 1] << 3) | q[..., 2]).ravel(), minlength=512).astype(np.float32)
        hist /= hist.sum()
        h64.append(hist.reshape(4, 2, 4, 2, 4, 2).sum(axis=(1, 3, 5)).ravel())
        hell.append(float(k.mean()))
        streu.append(float(k.std()))
        kg = np.abs(np.diff(k, axis=1))[:-1, :] + np.abs(np.diff(k, axis=0))[:, :-1]
        if prev_k is None:
            d.append(0.0)
            hd.append(0.0)
            struktur.append(1.0)
        else:
            d.append(float(np.abs(k - prev_k).mean()))
            hd.append(float(0.5 * np.abs(hist - prev_h).sum()))
            a_, b_ = prev_kg - prev_kg.mean(), kg - kg.mean()
            struktur.append(float((a_ * b_).sum() / (np.sqrt((a_ * a_).sum() * (b_ * b_).sum()) + 1e-6)))
        prev_kg = kg
        ring.append(k)
        for L in fenster:  # Überblendung: Mitte = Mischung aus Anfang und Ende, kein Einzelsprung
            if len(ring) > L:
                a, b, m = ring[-1 - L], ring[-1], ring[-1 - L // 2]
                D = float(np.abs(b - a).mean())
                if D > UEBERBL_MIN:
                    fen = d[-L:]
                    if max(fen) < 0.45 * D and sum(fen) < 1.6 * D:
                        fehler = float(np.abs(m - (a + b) / 2).mean())
                        if fehler < 0.25 * D:
                            ueberbl.append((i - L, i, D))
        if i % kam_schritt == 0:
            if prev_cam is not None:
                kamera.append((prev_cam_t, t) + kamera_schritt(prev_cam, grau))
            prev_cam, prev_cam_t = grau, t
        prev_k, prev_h = k, hist
        zeiten.append(t)
    if not d:
        raise SystemExit(f'FEHLER: Aus {video} kam kein einziges Bild. Datei kaputt?')
    return {'d': np.array(d), 'hd': np.array(hd), 'hell': np.array(hell), 'streu': np.array(streu), 'struktur': np.array(struktur),
            'h64': np.array(h64, np.float32), 't': np.array(zeiten), 'kamera': kamera, 'ueberbl': ueberbl,
            'kam_breite': w, 'kam_hoehe': h, 'fps': fps}


def _rollmedian(x, r, aus=1):
    np = _np()
    n = len(x)
    m = np.zeros(n)
    for k in range(n):
        nb = np.concatenate([x[max(1, k - r):max(1, k - aus)], x[k + aus + 1:k + r + 1]])
        m[k] = float(np.median(nb)) if len(nb) else 0.0
    return m


def grenzen_finden(m, schwelle, abstand):
    """Harte Schnitte, Wisch-Übergänge, Überblendungen, Blitze -> sortierte Szenengrenzen."""
    np = _np()
    d, hd, fps = m['d'], m['hd'], m['fps']
    n = len(d)
    basis = _rollmedian(d, max(6, int(round(0.4 * fps))))
    weit = _rollmedian(d, max(15, int(round(1.0 * fps))), aus=0)
    grenzen, wechsel = [], []
    for k in range(1, n):
        if d[k] < ABS_MIN or d[k] < schwelle * basis[k] + 2 or hd[k] < HIST_MIN:
            continue
        if d[k] < d[max(1, k - 2):k + 3].max():
            continue
        g = {'frame': k, 'art': 'hart', 'staerke': round(float(d[k] / (basis[k] + 1)), 1),
             'struktur': round(float(m['struktur'][k]), 2), 'von_frame': k - 1, 'bis_frame': k}
        if m['struktur'][k] >= STRUKTUR_MAX:  # Bildaufbau bleibt: Lichtwechsel, Pop oder Textwechsel, kein Schnitt
            g['art'] = 'licht/inhalt'
            g['t'] = round(k / fps, 3)
            wechsel.append(g)
            continue
        grenzen.append(g)
    # Wisch: 3 bis ~0,35 s lange Folge hoher Differenz, vorher und nachher andere Farbverteilung
    hoch = d >= np.maximum(WISCH_MIN, 3 * weit)
    k, max_len = 1, max(4, int(round(0.35 * fps)))
    wische = []
    while k < n:
        if hoch[k]:
            e = k
            while e + 1 < n and hoch[e + 1]:
                e += 1
            laenge = e - k + 1
            nah_max = int((d[k:e + 1] >= 0.5 * d[k:e + 1].max()).sum())
            if 3 <= laenge <= max_len and nah_max >= 3 and k >= 2 and e + 1 < n:
                tv = float(0.5 * np.abs(m['h64'][k - 1] - m['h64'][e + 1]).sum())
                if tv >= 0.25:
                    wische.append({'frame': k, 'art': 'wisch', 'staerke': round(float(d[k:e + 1].mean() / (weit[k] + 1)), 1),
                                   'frames': laenge, 'von_frame': k - 1, 'bis_frame': e + 1})
            k = e + 1
        else:
            k += 1
    for w in wische:  # harte Schnitte innerhalb eines Wischs gehören zum Wisch
        grenzen = [g for g in grenzen if not (w['frame'] - 1 <= g['frame'] <= w['frame'] + w['frames'])]
    grenzen += wische
    # Überblendungen zusammenfassen
    ub = []
    for a, b, D in sorted(m['ueberbl']):
        if ub and a <= ub[-1][1]:
            ub[-1] = (ub[-1][0], max(ub[-1][1], b), max(ub[-1][2], D))
        else:
            ub.append((a, b, D))
    for a, b, D in ub:
        if any(a <= g['frame'] <= b for g in grenzen) or (b - a) > 0.9 * fps:  # längere Ketten = Bewegung, keine Blende
            continue
        grenzen.append({'frame': (a + b) // 2, 'art': 'ueberblendung', 'staerke': round(D, 1), 'frames': b - a,
                        'von_frame': a, 'bis_frame': b})
    # Blitze (Weiß/Schwarz)
    blitze = []
    weiss = (m['hell'] > 225) & (m['streu'] < 30)
    schwarz = (m['hell'] < 18) & (m['streu'] < 12)
    for maske, art in ((weiss, 'weiss'), (schwarz, 'schwarz')):
        k = 0
        while k < n:
            if maske[k]:
                e = k
                while e + 1 < n and maske[e + 1]:
                    e += 1
                blitze.append({'frame': k, 'frames': e - k + 1, 'art': art, 't': round(k / fps, 3)})
                k = e + 1
            else:
                k += 1
    for b in blitze:
        for g in grenzen:
            if abs(g['frame'] - b['frame']) <= 2 and g['art'] == 'hart':
                g['art'] = f"hart+{b['art']}blitz"
    # Mindestabstand: die stärkere Grenze bleibt
    grenzen.sort(key=lambda g: g['frame'])
    mind = max(1, int(round(abstand * fps)))
    sauber = []
    for g in grenzen:
        if sauber and g['frame'] - sauber[-1]['frame'] < mind:
            if g['staerke'] > sauber[-1]['staerke']:
                sauber[-1] = g
            continue
        sauber.append(g)
    for g in sauber:
        g['t'] = round(g['frame'] / fps, 3)
    return sauber, blitze, wechsel


def szenen_bauen(grenzen, n, fps):
    starts = [0] + [g['frame'] for g in grenzen]
    enden = [g['frame'] for g in grenzen] + [n]
    arten = ['start'] + [g['art'] for g in grenzen]
    szenen = []
    for i, (a, e, art) in enumerate(zip(starts, enden, arten)):
        szenen.append({'nr': i + 1, 'id': f's{i + 1:02d}', 'start': round(a / fps, 3), 'ende': round(e / fps, 3),
                       'dauer': round((e - a) / fps, 3), 'frames': [a, e - 1], 'uebergang': art})
    return szenen


def bewegung(m, szenen):
    np = _np()
    d, fps = m['d'], m['fps']
    n = len(d)
    fen = max(1, int(round(0.2 * fps)))
    glatt = np.convolve(d, np.ones(fen) / fen, mode='same')
    still = glatt * (fps / 30.0) < STILL_MAX  # bei 60 fps ist die Differenz je Frame nur halb so groß
    stillstaende = []
    k = 0
    while k < n:
        if still[k]:
            e = k
            while e + 1 < n and still[e + 1]:
                e += 1
            if (e - k + 1) / fps >= STILL_DAUER:
                stillstaende.append({'von': round(k / fps, 2), 'bis': round((e + 1) / fps, 2), 'dauer': round((e - k + 1) / fps, 2)})
            k = e + 1
        else:
            k += 1
    bewegt = glatt > 1.5
    dup = bewegt & (d < 0.15 * glatt)
    dup_anteil = float(dup.sum() / max(1, bewegt.sum()))
    # Kamera je Szene
    W = m['kam_breite']
    for s in szenen:
        a, e = s['start'], s['ende']
        schritte = [k for k in m['kamera'] if k[0] >= a - 1e-6 and k[1] <= e + 1e-6]
        a_fr, e_fr = s['frames'][0], s['frames'][1] + 1
        s['energie'] = round(float(d[a_fr + 1:e_fr].mean()) if e_fr - a_fr > 1 else 0.0, 2)
        s['still_anteil'] = round(float(still[a_fr:e_fr].mean()), 2)
        if not schritte or s['dauer'] < 0.4:
            s['kamera'] = {'urteil': 'zu kurz', 'schwenk_x': 0, 'schwenk_y': 0, 'zoom': 0, 'sicherheit': 0}
            continue
        def robust(werte):
            # Median je Schritt mal Schrittzahl, aber nur wenn mindestens 65 % der Schritte in dieselbe Richtung zeigen
            w = np.array(werte)
            med = float(np.median(w))
            gleich = float((np.sign(w) == np.sign(med)).mean()) if med else 0.0
            return med * len(w) if gleich >= 0.65 else 0.0
        sx = robust([k[2] for k in schritte]) / W * 100 / s['dauer']
        sy = robust([k[3] for k in schritte]) / W * 100 / s['dauer']
        zoom = robust([k[5] for k in schritte]) * 100
        sicher = float(np.median([k[4] for k in schritte]))
        teile = []
        if sicher < 0.06:
            teile.append('unklar (viel Eigenbewegung)')
        else:
            if sx > 3:
                teile.append('Schwenk links (Inhalt wandert nach rechts)')
            elif sx < -3:
                teile.append('Schwenk rechts (Inhalt wandert nach links)')
            if sy > 3:
                teile.append('kippt hoch (Inhalt wandert nach unten)')
            elif sy < -3:
                teile.append('kippt runter (Inhalt wandert nach oben)')
            if zoom > 2.5:
                teile.append(f'Zoom rein ({zoom:+.0f} %)')
            elif zoom < -2.5:
                teile.append(f'Zoom raus ({zoom:+.0f} %)')
        s['kamera'] = {'urteil': ', '.join(teile) or 'ruhig', 'schwenk_x': round(sx, 1), 'schwenk_y': round(sy, 1),
                       'zoom': round(zoom, 1), 'sicherheit': round(sicher, 2)}
    energie_10hz = [round(float(glatt[int(i * fps / 10)]), 2) for i in range(int(n / fps * 10)) if int(i * fps / 10) < n]
    if dup_anteil >= 0.35:
        animation = f'Doppelbilder in {dup_anteil:.0%} der bewegten Frames: animiert vermutlich auf Zweien (~{fps / 2:.0f} Bilder/s)'
    else:
        animation = f'Doppelbilder in {dup_anteil:.0%} der bewegten Frames: Bewegung in voller Bildrate ({fps:.0f} Bilder/s)'
    return {'stillstaende': stillstaende, 'doppelbild_anteil': round(dup_anteil, 2), 'animation': animation,
            'energie_10hz': energie_10hz, 'energie_mittel': round(float(d.mean()), 2)}, glatt


def kamera_ereignisse(m, szenen, grenzen, blitze):
    """Schnelle Zooms, Kamera-Punches und Rucke INNERHALB einer Szene: kurze Energie-Spitze (0,08 bis 1 s, kein Schnitt,
    keine Blende, kein Blitz in der Nähe) plus Skalen- oder Lageänderung aus den Kamera-Schritten in diesem Fenster.
    Spitzen ohne Kamera-Änderung (Objekt ploppt, wächst, fliegt) kommen mit art "aktion" zurück.
    Geeicht an einem 2D-Vorbild (60 fps): Punch 3,9 bis 4,4 s = Zoom rein +31 %, 58,3 bis 58,9 s = Zoom raus mit Schwenk,
    19,2 bis 19,6 s = Kreis wächst ohne Kamera (aktion). Ein großes Objekt, das mittig wächst, kann wie ein Zoom aussehen:
    im Szenenbogen prüfen."""
    np = _np()
    d, fps = m['d'], m['fps']
    n = len(d)
    if n < 10:
        return []
    fen = max(1, int(round(0.1 * fps)))
    glatt = np.convolve(d, np.ones(fen) / fen, mode='same') * (fps / 30.0)
    basis = _rollmedian(glatt, max(15, int(round(1.0 * fps))), aus=max(2, int(round(0.25 * fps))))
    hoch = glatt >= np.maximum(SPITZE_MIN, SPITZE_FAKTOR * basis + 0.6)
    W = m['kam_breite']
    aus, k = [], 0
    while k < n:
        if not hoch[k]:
            k += 1
            continue
        e = k
        while e + 1 < n and hoch[e + 1]:
            e += 1
        k0, a_t, e_t = k, k / fps, (e + 1) / fps
        k = e + 1
        if not (SPITZE_DAUER[0] <= e_t - a_t <= SPITZE_DAUER[1]):
            continue
        if any(g['von_frame'] / fps - 0.15 <= e_t and g['bis_frame'] / fps + 0.15 >= a_t for g in grenzen):
            continue
        if any(b['frame'] / fps - 0.1 <= e_t and (b['frame'] + b['frames']) / fps + 0.1 >= a_t for b in blitze):
            continue
        schritte = [s for s in m['kamera'] if s[1] > a_t - 0.05 and s[0] < e_t + 0.05]
        skala = float(np.prod([1 + s[5] for s in schritte])) if schritte else 1.0
        sx = sum(s[2] for s in schritte) / W * 100
        sy = sum(s[3] for s in schritte) / W * 100
        sicher = float(np.median([s[6] for s in schritte])) if schritte else 0.0
        zoom = skala - 1.0
        teile = []
        if abs(zoom) >= ZOOM_MIN:
            teile.append(f"schneller Zoom {'rein' if zoom > 0 else 'raus'} {zoom * 100:+.0f} %")
        grenze = 10.0 if teile else LAGE_MIN
        if abs(sx) >= grenze:
            teile.append('Schwenk links (Inhalt wandert nach rechts)' if sx > 0 else 'Schwenk rechts (Inhalt wandert nach links)')
        if abs(sy) >= grenze:
            teile.append('kippt hoch (Inhalt wandert nach unten)' if sy > 0 else 'kippt runter (Inhalt wandert nach oben)')
        art = 'kamera' if teile else 'aktion'
        if art == 'kamera' and zoom >= ZOOM_MIN and e_t - a_t <= 0.7:
            teile[0] += ' (Punch)'
        if art == 'kamera' and sicher < 0.06:
            teile.append('Kamera-Werte unsicher')
        sz = next((s for s in szenen if s['start'] - 1e-6 <= a_t < s['ende']), szenen[-1])
        aus.append({'von': round(a_t, 2), 'bis': round(e_t, 2), 'dauer': round(e_t - a_t, 2), 'art': art,
                    'szene': sz['nr'], 'zoom_prozent': round(zoom * 100, 1), 'schwenk_x': round(sx, 1), 'schwenk_y': round(sy, 1),
                    'energie': round(float(glatt[k0:e + 1].max()), 2), 'sicherheit': round(sicher, 2),
                    'text': ', '.join(teile) if teile else 'Bewegungs-Spitze ohne Kamera (Objekt ploppt, wächst oder fliegt)'})
    for ev in aus:
        if ev['art'] != 'kamera':
            continue
        s = szenen[ev['szene'] - 1]
        kam = s.setdefault('kamera', {'urteil': 'ruhig'})
        kam.setdefault('ereignisse', []).append({k2: ev[k2] for k2 in ('von', 'bis', 'zoom_prozent', 'schwenk_x', 'schwenk_y', 'text')})
        neu = f"{ev['text']} bei {_sek(ev['von'])} s"
        kam['urteil'] = neu if kam.get('urteil') in (None, '', 'ruhig', 'zu kurz') else f"{kam['urteil']}; {neu}"
    return aus


# ---------------------------------------------------------------- Durchgang 2: Schlüsselbilder (OCR, Palette, Typ)

def schluesselbilder(video, info, ocr_fps, ordner_png):
    """Streamt ocr_fps Bilder pro Sekunde, schreibt sie als PNG (für OCR) und misst Merkmale. Ein Bild im RAM."""
    np = _np()
    from PIL import Image
    B, H = info['breite'], info['hoehe']
    fak = min(1.0, 1080 / max(1, min(B, H)))
    wk, hk = int(round(B * fak / 2)) * 2, int(round(H * fak / 2)) * 2
    kl_w = 120 if B <= H else 213
    kl_h = int(round(kl_w * H / B))
    bilder = []
    for i, (t, f) in enumerate(_ms.frames(video, fps=ocr_fps, groesse=(wk, hk))):
        name = f'{i:06d}.png'
        bild = Image.fromarray(f)
        bild.save(ordner_png / name, compress_level=1)
        klein = np.asarray(bild.resize((kl_w, kl_h), Image.BILINEAR))
        cy, cx = hk // 2, wk // 2
        g = kanten_gewicht(f[max(0, cy - 160):cy + 160, max(0, cx - 160):cx + 160])
        bilder.append({'datei': name, 't': round(float(t), 3), 'klein': klein, 'merkmale': merkmale(klein, g)})
    return bilder, (wk, hk)


# ---------------------------------------------------------------- Texterkennung

def _ocr_pyobjc(dateien, sprachen):
    import objc
    import Quartz
    import Vision
    from Foundation import NSURL, NSRange
    aus = {}
    for p in dateien:
        with objc.autorelease_pool():
            quelle = Quartz.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(str(p)), None)
            bild = Quartz.CGImageSourceCreateImageAtIndex(quelle, 0, None)
            W, H = Quartz.CGImageGetWidth(bild), Quartz.CGImageGetHeight(bild)
            req = Vision.VNRecognizeTextRequest.alloc().init()
            req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
            req.setUsesLanguageCorrection_(False)
            if sprachen:
                req.setRecognitionLanguages_(sprachen)
            elif hasattr(req, 'setAutomaticallyDetectsLanguage_'):
                req.setAutomaticallyDetectsLanguage_(True)
            Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(bild, None).performRequests_error_([req], None)

            def px(bb):
                return [round(bb.origin.x * W), round((1 - bb.origin.y - bb.size.height) * H),
                        round(bb.size.width * W), round(bb.size.height * H)]
            obs = []
            for o in (req.results() or []):
                kand = o.topCandidates_(1)
                if not kand:
                    continue
                c = kand[0]
                s = str(c.string())
                woerter = []
                for mm in re.finditer(r'\S+', s):
                    bb, _ = c.boundingBoxForRange_error_(NSRange(mm.start(), mm.end() - mm.start()), None)
                    if bb is not None:
                        woerter.append({'w': mm.group(0), 'box': px(bb.boundingBox())})
                obs.append({'text': s, 'conf': round(float(c.confidence()), 3), 'box': px(o.boundingBox()), 'woerter': woerter})
            aus[p.name] = obs
    return aus


def _ocr_swift(ordner, sprachen):
    quelle = Path(__file__).with_name('ocr_vision.swift')
    if not quelle.exists() or not shutil.which('swiftc'):
        return None
    kennung = hashlib.sha1(quelle.read_bytes()).hexdigest()[:10]
    cache = _ms.arbeit() / '.cache'
    exe = cache / f'ocr_vision-{kennung}'
    kaputt = cache / f'ocr_vision-{kennung}.kaputt'
    if kaputt.exists():
        return None
    if not exe.exists():
        cache.mkdir(parents=True, exist_ok=True)
        print('Baue die Texterkennung (einmalig, 1-2 Minuten) …', flush=True)
        try:
            r = subprocess.run(['swiftc', '-O', '-o', str(exe), str(quelle)], capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            r = None
        if r is None or r.returncode != 0:
            kaputt.write_text((r.stderr if r else 'Zeitüberschreitung')[-3000:], encoding='utf-8')
            print('Hinweis: Swift-Compiler läuft nicht (oft: Command Line Tools passen nicht zum SDK). Weiter ohne.')
            return None
    r = subprocess.run([str(exe), str(ordner)] + ([','.join(sprachen)] if sprachen else []), capture_output=True, text=True)
    if r.returncode != 0:
        return None
    aus = {}
    for z in r.stdout.splitlines():
        if z.strip().startswith('{'):
            d = json.loads(z)
            aus[d['datei']] = [{'text': o['text'], 'conf': round(o['conf'], 3), 'box': o['box'],
                                'woerter': o.get('woerter', [])} for o in d['obs']]
    return aus


def _ocr_tesseract(dateien):
    r = subprocess.run(['tesseract', '--list-langs'], capture_output=True, text=True)
    vorhanden = set(r.stdout.split())
    sprachen = '+'.join(s for s in ('eng', 'deu') if s in vorhanden) or 'eng'
    aus = {}
    for p in dateien:
        r = subprocess.run(['tesseract', str(p), 'stdout', '--psm', '11', '-l', sprachen, 'tsv'], capture_output=True, text=True)
        zeilen = {}
        for z in r.stdout.splitlines()[1:]:
            t = z.split('\t')
            if len(t) < 12 or t[0] != '5' or not t[11].strip() or float(t[10]) < 0:
                continue
            schluessel = (t[2], t[3], t[4])
            x, y, w, h = (int(v) for v in t[6:10])
            zeilen.setdefault(schluessel, []).append({'w': t[11], 'box': [x, y, w, h], 'conf': float(t[10]) / 100})
        obs = []
        for ws in zeilen.values():
            x0 = min(w['box'][0] for w in ws)
            y0 = min(w['box'][1] for w in ws)
            x1 = max(w['box'][0] + w['box'][2] for w in ws)
            y1 = max(w['box'][1] + w['box'][3] for w in ws)
            obs.append({'text': ' '.join(w['w'] for w in ws), 'conf': round(sum(w['conf'] for w in ws) / len(ws), 3),
                        'box': [x0, y0, x1 - x0, y1 - y0], 'woerter': [{'w': w['w'], 'box': w['box']} for w in ws]})
        aus[p.name] = obs
    return aus


def ocr(ordner, sprachen):
    dateien = sorted(ordner.glob('*.png'))
    if sys.platform == 'darwin':
        try:
            return 'vision (pyobjc)', _ocr_pyobjc(dateien, sprachen)
        except ImportError:
            pass
        r = _ocr_swift(ordner, sprachen)
        if r is not None:
            return 'vision (swift)', r
    if shutil.which('tesseract'):
        return 'tesseract', _ocr_tesseract(dateien)
    return 'aus', {}


# ---------------------------------------------------------------- Text auswerten

def _norm(s):
    return re.sub(r'[^0-9a-zäöüß]+', '', s.lower())


def schrift_px(text, hoehe):
    """Grobe Schriftgröße aus der Vision-Zeilenbox. Großbuchstaben: Box ≈ 0,87 em (geeicht an einem Banner in Inter 900,
    76 px, Box 64-66 px). Gemischte Schreibung: Box ≈ 1,05 em (Ober- bis Unterlänge, nicht geeicht)."""
    buchst = [c for c in text if c.isalpha()]
    gross = buchst and all(c.isupper() for c in buchst)
    return int(round(hoehe / (0.87 if gross else 1.05)))


def textfarben(png, obs_liste, fak):
    """Textfarbe und Hintergrund je Box: Rand der Box = Hintergrund, abweichende Pixel innen = Schrift."""
    np = _np()
    from PIL import Image
    bild = np.asarray(Image.open(png).convert('RGB'))
    H, W = bild.shape[:2]
    aus = []
    for o in obs_liste:
        for wort in (o.get('woerter') or [{'w': o['text'], 'box': o['box']}]):
            x, y, w, h = [int(round(v / fak)) for v in wort['box']]
            r = 5
            x0, y0, x1, y1 = max(0, x - r), max(0, y - r), min(W, x + w + r), min(H, y + h + r)
            if x1 - x0 < 6 or y1 - y0 < 6:
                continue
            crop2d = bild[y0:y1, x0:x1].astype(np.float32)
            crop = crop2d.reshape(-1, 3)
            ring = np.concatenate([bild[y0:y0 + 3, x0:x1].reshape(-1, 3), bild[y1 - 3:y1, x0:x1].reshape(-1, 3),
                                   bild[y0:y1, x0:x0 + 3].reshape(-1, 3), bild[y0:y1, x1 - 3:x1].reshape(-1, 3)]).astype(np.float32)
            bg = np.median(ring, axis=0)
            abst = np.sqrt(((crop - bg) ** 2).sum(1))
            schrift = crop[abst > 60]
            if len(schrift) < 10:
                continue
            # Füllung und Kontur/Schatten trennen (z. B. weiße Schrift mit schwarzem Rand): zwei Gruppen
            fuell, kontur = np.median(schrift, axis=0), None
            if len(schrift) >= 40:
                z, zu, _ = kmeans(schrift, 2, iter_=8)
                if len(z) == 2:
                    n0, n1 = int((zu == 0).sum()), int((zu == 1).sum())
                    if min(n0, n1) >= 0.15 * len(schrift) and np.linalg.norm(z[0] - z[1]) > 100:
                        # Kontur = die Gruppe, die öfter direkt an den Hintergrund grenzt; Füllung liegt innen
                        karte = np.zeros(abst.shape, np.int8)
                        idx = np.flatnonzero(abst > 60)
                        karte[idx] = zu + 1
                        karte = karte.reshape(crop2d.shape[:2])
                        grund = karte == 0
                        nachbar = np.zeros_like(grund)
                        nachbar[1:, :] |= grund[:-1, :]
                        nachbar[:-1, :] |= grund[1:, :]
                        nachbar[:, 1:] |= grund[:, :-1]
                        nachbar[:, :-1] |= grund[:, 1:]
                        rand = [float((nachbar & (karte == j + 1)).sum()) / max(1, int((karte == j + 1).sum())) for j in (0, 1)]
                        innen, aussen = (0, 1) if rand[0] < rand[1] else (1, 0)
                        fuell, kontur = z[innen], z[aussen]
            aus.append({'wort': wort['w'], 'text': hexfarbe(fuell), 'grund': hexfarbe(bg), '_t': fuell, '_g': bg,
                        '_k': kontur})
    return aus


def farben_buendeln(werte, schwelle=45):
    """Gruppiert RGB-Werte grob (Abstand < schwelle), gibt [{hex, anteil}] zurück."""
    np = _np()
    gruppen = []
    for v in werte:
        for g in gruppen:
            if np.linalg.norm(g['summe'] / g['n'] - v) < schwelle:
                g['summe'] += v
                g['n'] += 1
                break
        else:
            gruppen.append({'summe': v.astype(np.float64).copy(), 'n': 1})
    gesamt = sum(g['n'] for g in gruppen) or 1
    gruppen.sort(key=lambda g: -g['n'])
    return [{'hex': hexfarbe(g['summe'] / g['n']), 'anteil': round(g['n'] / gesamt, 2)} for g in gruppen[:4]
            if g['n'] / gesamt >= 0.08]


def text_auswerten(ocr_roh, bilder, groesse_k, info, ordner_png, vokabel=None):
    """Caption-Zone (wiederkehrender, wechselnder Text in einem Höhenband) und Einblendungen (Titel, Labels)."""
    np = _np()
    wk, hk = groesse_k
    fak = info['breite'] / wk
    H = info['hoehe']
    zeit = {b['datei']: b['t'] for b in bilder}
    eintraege = []
    for datei, obs in ocr_roh.items():
        for o in obs:
            if o['conf'] < 0.4 or not o['text'].strip() or o['box'][3] < 0.008 * hk:
                continue
            x, y, w, h = [v * fak for v in o['box']]
            eintraege.append({'datei': datei, 't': zeit.get(datei, 0), 'text': o['text'].strip(), 'conf': o['conf'],
                              'box': [round(x), round(y), round(w), round(h)], 'ym': (y + h / 2) / H,
                              'woerter': [{'w': ww['w'], 'box': [v * fak for v in ww['box']]} for ww in o.get('woerter', [])],
                              '_roh': o})
    n_bilder = max(1, len(bilder))
    # Caption-Kandidaten: kein stehender Text (gleicher Text >= 4 Bilder im selben Band) und, wenn ein Transkript da ist,
    # überwiegend gesprochene Wörter. So fallen Titel und Grafik-Beschriftungen heraus.
    reihe = {b['datei']: i for i, b in enumerate(sorted(bilder, key=lambda b: b['t']))}
    je_index = {}
    for e in eintraege:
        je_index.setdefault(reihe.get(e['datei'], -1), []).append((_norm(e['text']), e['ym']))

    def lauflaenge(e):
        i, nt, n = reihe.get(e['datei'], -1), _norm(e['text']), 1
        for richtung in (-1, 1):
            j = i + richtung
            while any(t == nt and abs(y - e['ym']) < 0.03 for t, y in je_index.get(j, [])):
                n += 1
                j += richtung
        return n
    kandidaten = [e for e in eintraege if lauflaenge(e) < 3]  # >= 3 Bilder am selben Ort = stehender Text
    if vokabel:
        def gesprochen(e):
            ws = [_norm(w) for w in e['text'].split() if len(_norm(w)) >= 2]
            return bool(ws) and sum(w in vokabel for w in ws) / len(ws) >= 0.6
        kandidaten = [e for e in kandidaten if gesprochen(e)]
    # Caption-Zone suchen: gleitende Bänder von 12 % Bildhöhe (3 x 4 %). Captions = in vielen Bildern Text, der oft wechselt
    beste = None
    for zb in range(0, 23):
        ze = zb + 2
        drin = [e for e in kandidaten if zb <= int(e['ym'] * 25) <= ze]
        je_bild = {}
        for e in sorted(drin, key=lambda e: (e['box'][1], e['box'][0])):
            je_bild.setdefault(e['datei'], []).append(e)
        folge = [' '.join(x['text'] for x in je_bild[k]) for k in sorted(je_bild)]
        if len(folge) < 4:
            continue
        wechsel = sum(1 for a, c in zip(folge, folge[1:]) if _norm(a) != _norm(c)) / (len(folge) - 1)
        woerter = [len(f.split()) for f in folge]
        anteil = len(je_bild) / n_bilder
        punkte = anteil * wechsel
        if anteil >= 0.25 and wechsel >= 0.45 and float(np.median(woerter)) <= 8 and (not beste or punkte > beste['punkte'] + 0.02):
            beste = {'punkte': punkte, 'zb': zb, 'ze': ze, 'drin': drin, 'je_bild': je_bild, 'folge': folge,
                     'wechsel': wechsel, 'anteil': anteil, 'woerter': woerter}
    captions = None
    in_caption = set()
    if beste:
        drin = beste['drin']
        in_caption = {id(e) for e in drin}
        hoehen = [e['box'][3] for e in drin]
        alle_buchst = ''.join(c for e in drin for c in e['text'] if c.isalpha())
        gross = sum(1 for c in alle_buchst if c.isupper()) / max(1, len(alle_buchst))
        farben, gruende, konturen, hervor, gruppen_n = [], [], [], 0, 0
        for datei in list(beste['je_bild'])[:40]:
            fb = textfarben(ordner_png / datei, [e['_roh'] for e in beste['je_bild'][datei]], fak)
            if not fb:
                continue
            gruppen_n += 1
            farben += [f['_t'] for f in fb]
            gruende += [f['_g'] for f in fb]
            konturen += [f['_k'] for f in fb if f['_k'] is not None]
            if len(fb) >= 2 and max(np.linalg.norm(a['_t'] - c['_t']) for a in fb for c in fb) > 80:
                hervor += 1
        def zeilen_zahl(obs):
            ys = sorted(e['box'][1] + e['box'][3] / 2 for e in obs)
            hm = float(np.median([e['box'][3] for e in obs]))
            return 1 + sum(1 for a_, b_ in zip(ys, ys[1:]) if b_ - a_ > 0.6 * hm)
        zeilen = [zeilen_zahl(v) for v in beste['je_bild'].values()]
        y0 = int(np.percentile([e['box'][1] for e in drin], 5))
        y1 = int(np.percentile([e['box'][1] + e['box'][3] for e in drin], 95))
        captions = {
            'zone_px': [y0, y1], 'zone_rel': [round(y0 / H, 3), round(y1 / H, 3)],
            'mitte_rel': round(float(np.median([e['ym'] for e in drin])), 3),
            'zeilenhoehe_px': int(np.median(hoehen)), 'schrift_px_ca': schrift_px('A' if gross > 0.8 else 'a', float(np.median(hoehen))),
            'woerter_pro_gruppe': float(np.median(beste['woerter'])),
            'woerter_verteilung': dict(sorted(Counter(min(w, 8) for w in beste['woerter']).items())),
            'zeilen_pro_gruppe': float(np.median(zeilen)), 'grossbuchstaben': round(gross, 2),
            'textfarben': farben_buendeln(farben), 'hintergrund': farben_buendeln(gruende),
            'kontur': farben_buendeln(konturen) if len(konturen) >= 0.3 * max(1, len(farben)) else [],
            'hervorhebung_anteil': round(hervor / max(1, gruppen_n), 2), 'sichtbar_anteil': round(beste['anteil'], 2),
            'wechselrate': round(beste['wechsel'], 2),
            'beispiele': [{'t': zeit.get(k, 0), 'text': ' '.join(x['text'] for x in v)} for k, v in list(beste['je_bild'].items())[:12]],
            'abgleich_transkript': bool(vokabel),
        }
    # Einblendungen: alle übrigen Texte zu Spuren über die Zeit zusammenfassen
    spuren = []
    schritt = (bilder[1]['t'] - bilder[0]['t']) if len(bilder) > 1 else 0.5
    for e in sorted((e for e in eintraege if id(e) not in in_caption), key=lambda e: e['t']):
        passt = None
        for s in spuren:
            if e['t'] - s['bis'] > schritt * 1.6 or abs(s['ym'] - e['ym']) > 0.08:
                continue
            if difflib.SequenceMatcher(None, _norm(s['texte'][-1]), _norm(e['text'])).ratio() >= 0.75:
                passt = s
                break
        if passt:
            passt['bis'] = e['t']
            passt['texte'].append(e['text'])
            passt['hoehen'].append(e['box'][3])
            passt['conf'].append(e['conf'])
        else:
            spuren.append({'von': e['t'], 'bis': e['t'], 'texte': [e['text']], 'box': e['box'], 'ym': e['ym'],
                           'hoehen': [e['box'][3]], 'conf': [e['conf']]})
    einblendungen = []
    for s in spuren:
        text = Counter(s['texte']).most_common(1)[0][0]
        if len(_norm(text)) < 2 or (len(s['texte']) == 1 and (len(_norm(text)) < 4 or min(s['conf']) < 0.8)):
            continue
        h = float(np.median(s['hoehen']))
        einblendungen.append({'von': s['von'], 'bis': round(s['bis'] + schritt, 3), 'text': text, 'box': s['box'],
                              'hoehe_px': int(h), 'schrift_px_ca': schrift_px(text, h),
                              'conf': round(float(np.mean(s['conf'])), 2), 'bilder': len(s['texte'])})
    # Textfläche je Bild (ohne Captions) für die Typ-Bestimmung
    flaeche = {}
    for e in eintraege:
        if id(e) not in in_caption:
            flaeche[e['datei']] = flaeche.get(e['datei'], 0) + e['box'][2] * e['box'][3] / (info['breite'] * H)
    return captions, einblendungen, flaeche


# ---------------------------------------------------------------- Typ

def typ_szene(mk):
    """Typ einer Szene aus Merkmalen -> (typ, grund, sicherheit). Nur ein Vorschlag, das Auge entscheidet."""
    g = TYP_GRENZEN
    f, v, fa, ab, sch = mk['flach'], mk['verlauf'], mk['farben'], mk.get('abdeckung', 1.0), mk.get('schaerfe', 0.2)
    if mk.get('text', 0) >= g['text_ui'] and f >= 0.5:
        return 'ui', f"viel Text ({mk['text']:.0%} der Fläche) auf flachen Flächen ({f:.0%})", 'mittel'
    if f >= g['flach_2d']:
        return '2d', f"flache Farbflächen ({f:.0%}), {fa:.0f} Farbtöne, harte Kanten ({sch:.2f})", 'hoch' if f >= 0.7 else 'mittel'
    if fa >= g['farben_3d'] and ab < g['abdeckung_3d']:
        if fa >= g['farben_blender'] and v >= g['verlauf_blender']:
            return '3d-blender', f"sehr viele Farbtöne ({fa:.0f}) und weiche Schattierung ({v:.0%})", 'niedrig'
        return '3d-web', (f"viele Farbtöne ({fa:.0f}), Palette deckt nur {ab:.0%} ab: Schattierung/Licht wie gerendert"),\
            'hoch' if (fa >= 140 and ab < 0.5) else 'mittel'
    if sch < g['schaerfe_real'] and v >= g['verlauf_real']:
        return 'realfilm', (f"weiche Kanten (Schärfe {sch:.2f}) und Verläufe überall ({v:.0%}), wenig flache Flächen ({f:.0%}): "
                            f"wie Kamera- oder KI-Bild"), 'mittel' if sch < 0.06 else 'niedrig'
    return '2d', (f"{fa:.0f} Farbtöne, Palette deckt {ab:.0%} ab, harte Kanten ({sch:.2f}) mit Texturen/Verläufen ({v:.0%}): "
                  f"Collage-artig"), 'mittel' if sch >= 0.15 else 'niedrig'


def szenen_merkmale(szenen, bilder, flaeche):
    np = _np()
    for s in szenen:
        drin = [b for b in bilder if s['start'] + 0.05 <= b['t'] < s['ende'] - 0.02] or \
               [min(bilder, key=lambda b: abs(b['t'] - (s['start'] + s['ende']) / 2))]
        mk = {k: round(float(np.mean([b['merkmale'][k] for b in drin])), 3) for k in drin[0]['merkmale']}
        mk['text'] = round(float(np.mean([flaeche.get(b['datei'], 0) for b in drin])), 3)
        s['merkmale'] = mk
        px = np.concatenate([b['klein'].reshape(-1, 3) for b in drin])
        pal = palette(px, k=6)
        # Hintergrund: welche Palettenfarbe dominiert den Bildrand?
        rand = np.concatenate([np.concatenate([b['klein'][:4].reshape(-1, 3), b['klein'][-4:].reshape(-1, 3),
                                               b['klein'][:, :4].reshape(-1, 3), b['klein'][:, -4:].reshape(-1, 3)])
                               for b in drin])
        if pal:
            zl = np.array([p['_lab'] for p in pal])
            zu = ((lab(rand)[:, None, :] - zl[None]) ** 2).sum(-1).argmin(1)
            c = Counter(zu.tolist()).most_common(1)[0]
            s['hintergrund'] = pal[c[0]]['hex'] if c[1] / len(zu) >= 0.5 else None
            probe = px[np.random.default_rng(2).choice(len(px), min(len(px), 20000), replace=False)]
            nah = np.sqrt(((lab(probe)[:, None, :] - zl[None]) ** 2).sum(-1).min(1))
            s['merkmale']['abdeckung'] = round(float((nah < 10).mean()), 3)
        s['palette'] = [{'hex': p['hex'], 'anteil': p['anteil']} for p in pal]
        s['schluesselbilder'] = len(drin)
        s['typ'], s['typ_grund'], s['typ_sicherheit'] = typ_szene(s['merkmale'])


def typ_gesamt(szenen, dauer):
    anteile = Counter()
    for s in szenen:
        anteile[s['typ']] += s['dauer']
    anteile = {k: round(v / max(dauer, 0.01), 2) for k, v in anteile.most_common()}
    haupt = next(iter(anteile))
    name, weg, richtwert = TYPEN[haupt]
    zweit = [k for k, v in anteile.items() if k != haupt and v >= 0.2]
    vorschlag = name + (f" (Mischform mit {', '.join(TYPEN[k][0] for k in zweit)})" if zweit else '')
    relevant = [k for k, v in anteile.items() if v >= 0.2] or [haupt]
    schwerster = max(relevant, key=lambda k: list(TYPEN).index(k))
    machbar = TYPEN[schwerster][1] if schwerster != haupt else weg
    klein = [k for k, v in anteile.items() if v < 0.2 and list(TYPEN).index(k) > list(TYPEN).index(schwerster)]
    return {'vorschlag': vorschlag, 'haupt': haupt, 'anteile': anteile,
            'machbarkeit': machbar, 'richtwert': TYPEN[haupt][2],
            'schwerster_teil': {'typ': schwerster, 'name': TYPEN[schwerster][0], 'richtwert': TYPEN[schwerster][2]},
            'kleine_teile': [f"{TYPEN[k][0]} {anteile[k]:.0%}: in den Bögen prüfen" for k in klein],
            'hinweis': 'Vorschlag aus Messwerten (Flächen, Kanten, Verläufe, Farbtöne, Text). Mit Blick auf die Bögen '
                       'bestätigen oder korrigieren: Figuren, echte Kamera und KI-Video erkennt nur das Auge sicher.'}


# ---------------------------------------------------------------- Bögen und Grafik

KACHEL = 216
SPALTEN = 8


def _kachel_hoehe(info, breite=KACHEL):
    return round(breite * info['hoehe'] / info['breite'])


def bogen_markieren(pfad, zeiten, szenen, info, spalten=SPALTEN, breite=KACHEL, titel=True):
    """Schreibt Szenennummern in die Kacheln eines Kontaktbogens, roter Balken = neue Szene seit der Kachel davor."""
    from PIL import Image, ImageDraw
    bild = Image.open(pfad)
    zeichne = ImageDraw.Draw(bild)
    hoehe = _kachel_hoehe(info, breite)
    kopf = 34 if titel else 0
    vorher = None
    for i, t in enumerate(zeiten):
        s = next((x for x in szenen if x['start'] <= t < x['ende']), szenen[-1])
        x, y = (i % spalten) * breite, kopf + (i // spalten) * (hoehe + 22)
        zeichne.text((x + breite - 34, y + 2), f"S{s['nr']}", fill=(120, 220, 255), font=_ms._schrift(15))
        if vorher is not None and s['nr'] != vorher:
            zeichne.rectangle([x, y + 22, x + 5, y + 22 + hoehe], fill=(255, 40, 40))
        vorher = s['nr']
    bild.save(pfad, quality=88)


def boegen_bauen(video, info, szenen, grenzen, ordner):
    np = _np()
    d = ordner / 'boegen'
    if d.exists():
        for alt in d.glob('*.jpg'):
            alt.unlink()
    d.mkdir(parents=True, exist_ok=True)
    dauer = info['dauer']
    fps = info['fps'] or 30
    aus = {'uebersicht': [], 'szenen': {}, 'schnitte': []}
    zeiten = [i + 0.5 for i in range(int(dauer))] or [dauer / 2]
    pro = SPALTEN * 4
    for j in range(0, len(zeiten), pro):
        teil = zeiten[j:j + pro]
        p = _ms.kontaktbogen(video, teil, d / f'uebersicht_{j // pro + 1:02d}.jpg', spalten=SPALTEN, breite=KACHEL,
                             titel=f'Übersicht 1 Bild/s, {teil[0]:.0f} bis {teil[-1] + 0.5:.0f} s · {Path(video).name}')
        bogen_markieren(p, teil, szenen, info)
        aus['uebersicht'].append(f'boegen/{p.name}')
    def szene_bogen(s):
        ts = list(np.arange(s['start'] + 0.02, s['ende'] - 0.01, 0.25)) or [s['start'] + s['dauer'] / 2]
        if len(ts) > 32:
            ts = list(np.linspace(s['start'] + 0.02, s['ende'] - 0.04, 32))
        k = s['kamera']['urteil'] if isinstance(s.get('kamera'), dict) else ''
        return _ms.kontaktbogen(video, ts, d / f"szene_{s['nr']:02d}.jpg", spalten=SPALTEN, breite=KACHEL,
                                titel=f"Szene {s['nr']} · {s['start']:.2f} bis {s['ende']:.2f} s ({s['dauer']:.2f} s) · "
                                      f"rein: {s['uebergang']} · Kamera: {k}")
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as pool:  # je Bild ein ffmpeg-Aufruf: drei parallel, mehr bremst andere Arbeit
        for s, p in zip(szenen, pool.map(szene_bogen, szenen)):
            s['bogen'] = f'boegen/{p.name}'
            aus['szenen'][s['id']] = s['bogen']
    # Schnitte: je Grenze die Frames f-2, f-1 | f, f+1 (zwei Grenzen pro Zeile)
    for j in range(0, len(grenzen), 24):
        teil = grenzen[j:j + 24]
        ts = []
        for g in teil:
            a_, b_ = g.get('von_frame', g['frame'] - 1), g.get('bis_frame', g['frame'])
            if b_ - a_ <= 1:
                fr = [a_ - 1, a_, b_, b_ + 1]
            else:  # Wisch/Überblendung: vor dem Übergang, Anfang, Ende, danach
                fr = [a_ - 2, a_, b_, b_ + 2]
            ts += [max(0.0, (f - 0.5) / fps) for f in fr]  # -ss (f-0,5)/fps liefert genau Frame f
        p = _ms.kontaktbogen(video, ts, d / f'schnitte_{j // 24 + 1:02d}.jpg', spalten=8, breite=180,
                             titel='Grenzen: je 2 Bilder davor | 2 danach, bei Wisch/Überblendung Anfang und Ende (' +
                                   ', '.join(f"S{szenen[j + i + 1]['nr']} {g['art']} {g['t']:.2f}s" for i, g in enumerate(teil[:6])) +
                                   (' …' if len(teil) > 6 else '') + ')')
        aus['schnitte'].append(f'boegen/{p.name}')
    return aus


def energie_bild(ziel, m, glatt, szenen, grenzen, bew, dauer, wechsel=(), kam_ev=()):
    np = _np()
    from PIL import Image, ImageDraw
    W, H, L, O, U = 1600, 340, 40, 30, 30
    bild = Image.new('RGB', (W, H), (250, 250, 247))
    z = ImageDraw.Draw(bild)
    schrift = _ms._schrift(13)
    d = m['d']
    fps = m['fps']
    ymax = max(5.0, float(np.percentile(d, 99.5)))

    def xp(t):
        return L + (W - L - 10) * t / max(dauer, 0.01)

    def yp(v):
        return H - U - (H - O - U) * min(v, ymax) / ymax
    for s in bew['stillstaende']:
        z.rectangle([xp(s['von']), O, xp(s['bis']), H - U], fill=(225, 232, 240))
    pts = [(xp(i / fps), yp(v)) for i, v in enumerate(d)]
    z.line(pts, fill=(170, 170, 170), width=1)
    z.line([(xp(i / fps), yp(v)) for i, v in enumerate(glatt)], fill=(40, 90, 200), width=2)
    for w in wechsel:
        z.line([(xp(w['t']), O + 20), (xp(w['t']), H - U)], fill=(150, 150, 150), width=1)
    for e in kam_ev:
        farbe = (20, 150, 70) if e['art'] == 'kamera' else (120, 190, 140)
        z.rectangle([xp(e['von']), O + 24, max(xp(e['bis']), xp(e['von']) + 2), O + 30], fill=farbe)
        if e['art'] == 'kamera' and abs(e['zoom_prozent']) >= ZOOM_MIN * 100:
            z.text((xp(e['von']), O + 32), f"Z{e['zoom_prozent']:+.0f}%", fill=farbe, font=schrift)
    farben = {'hart': (220, 40, 40), 'wisch': (150, 60, 200), 'ueberblendung': (240, 140, 20)}
    for i, g in enumerate(grenzen):
        f = farben.get(g['art'].split('+')[0], (220, 40, 40))
        z.line([(xp(g['t']), O), (xp(g['t']), H - U)], fill=f, width=2)
        z.text((xp(g['t']) + 3, O - 16 + (i % 2) * 12), f"S{szenen[i + 1]['nr']}", fill=f, font=schrift)
    for t in range(0, int(dauer) + 1, 5):
        z.line([(xp(t), H - U), (xp(t), H - U + 5)], fill=(60, 60, 60))
        z.text((xp(t) - 6, H - U + 7), f'{t}s', fill=(60, 60, 60), font=schrift)
    z.text((L, 6), 'Bewegung je Frame (grau), geglättet (blau), Schnitte rot, Wisch lila, Überblendung orange, '
                   'ruhige Phase hellblau, Wechsel ohne Schnitt grau, Kamera-Ereignis grün (Z = Zoom)', fill=(30, 30, 30), font=schrift)
    z.text((4, O), f'{ymax:.0f}', fill=(90, 90, 90), font=schrift)
    bild.save(ziel)


# ---------------------------------------------------------------- Bericht

def _sek(x):
    return f'{x:.2f}'.replace('.', ',')


def ton_abschnitt(ordner):
    ton = _ms.json_lesen(ordner / 'ton.json')
    if not ton:
        return ''
    try:
        import ton_zerlegen
        return ton_zerlegen.md_abschnitt(ton)
    except Exception:  # noqa: BLE001 (Bericht soll nie am Ton-Teil scheitern)
        return ''


def bericht(a):
    info, sz, ty, rh, bew, tx = a['probe'], a['szenen'], a['typ'], a['rhythmus'], a['bewegung'], a['text']
    z = [f"# Analyse {a['id']}", '',
         f"Datei: `{a['datei']}`  ",
         f"Format: {info['breite']}×{info['hoehe']}, {info['fps']} fps, {_sek(info['dauer'])} s, Ton: {'ja' if info['ton'] else 'nein'}  ",
         f"Erstellt: {a['erstellt'][:16].replace('T', ' ')}, Laufzeit {a['laufzeit_s']:.0f} s", '',
         '## Typ und Machbarkeit (Vorschlag, mit den Bögen prüfen)', '',
         f"- **Typ:** {ty['vorschlag']}",
         f"- **Anteile nach Bildschirmzeit:** " + ', '.join(f"{TYPEN[k][0]} {v:.0%}" for k, v in ty['anteile'].items()),
         f"- **Machbarkeit:** {ty['machbarkeit']}",
         f"- **Erreichbare Ähnlichkeit:** {ty['richtwert']}"]
    if ty['schwerster_teil']['typ'] != ty['haupt']:
        z.append(f"- **Schwerster Teil:** {ty['schwerster_teil']['name']}: {ty['schwerster_teil']['richtwert']}")
    for k in ty.get('kleine_teile', []):
        z.append(f"- Kleiner Anteil: {k}")
    z += [f"- {ty['hinweis']}", '',
          '## Rhythmus', '',
          f"- {rh['szenen']} Szenen, {rh['schnitte']} Übergänge ({rh['arten']})",
          f"- {_sek(rh['schnitte_pro_10s'])} Schnitte pro 10 s, Szenenlänge Mittel {_sek(rh['szene_mittel'])} s, "
          f"Median {_sek(rh['szene_median'])} s, kürzeste {_sek(rh['szene_min'])} s, längste {_sek(rh['szene_max'])} s",
          f"- Verlauf (Schnitte je 10-s-Fenster): {rh['verlauf']}", '',
          '## Szenen', '',
          '| Szene | Start | Dauer | rein | Typ | Kamera | Energie | Hintergrund | Palette |',
          '|---|---|---|---|---|---|---|---|---|']
    for s in sz:
        pal = ' '.join(f"{p['hex']} {p['anteil']:.0%}" for p in s.get('palette', [])[:4])
        z.append(f"| [{s['nr']}]({s.get('bogen', '')}) | {_sek(s['start'])} | {_sek(s['dauer'])} | {s['uebergang']} | {s['typ']} | "
                 f"{s['kamera']['urteil']} | {s['energie']} | {s.get('hintergrund') or 'uneinheitlich'} | {pal} |")
    z += ['', 'Typ-Gründe je Szene: ' + '; '.join(f"S{s['nr']} {s['typ_grund']}" for s in sz), '',
          '## Bewegung', '',
          f"- Mittlere Bewegung je Frame: {bew['energie_mittel']} (Grauwert-Differenz 0-255, Kurve in `boegen/energie.png`)",
          f"- {bew['animation']}",
          '- Ruhige Phasen > 1,5 s (stehendes Bild oder sehr langsame Drift): ' +
          (', '.join(f"{_sek(s['von'])} bis {_sek(s['bis'])} s" for s in bew['stillstaende']) or 'keine')]
    if a['ereignisse'].get('wechsel_im_bild'):
        z.append('- Wechsel im Bild ohne Schnitt (Licht, Pop, Text; Bildaufbau bleibt): ' +
                 ', '.join(f"{_sek(w['t'])} s" for w in a['ereignisse']['wechsel_im_bild'][:30]))
    if a['ereignisse'].get('kamera'):
        z.append('- Kamera-Ereignisse in einer Szene (kurze Bewegungs-Spitze ohne Schnitt, mit Zoom oder Ruck; im Szenenbogen '
                 'prüfen, ein mittig wachsendes Objekt sieht für die Messung wie ein Zoom aus): ' +
                 '; '.join(f"{_sek(e['von'])} bis {_sek(e['bis'])} s (S{e['szene']}) {e['text']}" for e in a['ereignisse']['kamera'][:30]))
    if a['ereignisse'].get('spitzen'):
        z.append('- Bewegungs-Spitzen ohne Kamera-Änderung (Objekt ploppt, wächst oder fliegt): ' +
                 ', '.join(f"{_sek(e['von'])} bis {_sek(e['bis'])} s (S{e['szene']})" for e in a['ereignisse']['spitzen'][:30]))
    if a['ereignisse']['blitze']:
        z.append('- Blitze: ' + ', '.join(f"{b['art']} bei {_sek(b['t'])} s ({b['frames']} Frames)" for b in a['ereignisse']['blitze']))
    z += ['', '## Text und Captions', '', f"Texterkennung: {tx['ocr']}", '']
    c = tx.get('captions')
    if c:
        z += [f"- **Captions:** Zone {c['zone_px'][0]} bis {c['zone_px'][1]} px ({c['zone_rel'][0]:.0%} bis {c['zone_rel'][1]:.0%} der Höhe), "
              f"sichtbar in {c['sichtbar_anteil']:.0%} der Bilder, wechseln in {c['wechselrate']:.0%} der Schritte",
              f"- Zeilenhöhe {c['zeilenhoehe_px']} px (Schrift ca. {c['schrift_px_ca']} px), {c['woerter_pro_gruppe']:.0f} Wörter pro Gruppe "
              f"(Verteilung {c['woerter_verteilung']}), {c['zeilen_pro_gruppe']:.0f} Zeile(n), Großbuchstaben {c['grossbuchstaben']:.0%}",
              f"- Schriftfarben: " + ', '.join(f"{f['hex']} {f['anteil']:.0%}" for f in c['textfarben']) +
              f"; Kontur/Schatten: " + (', '.join(f"{f['hex']} {f['anteil']:.0%}" for f in c.get('kontur', [])) or 'keine') +
              f"; Grund hinter der Schrift: " + ', '.join(f"{f['hex']} {f['anteil']:.0%}" for f in c['hintergrund']),
              f"- Hervorhebung (zwei Schriftfarben in einer Gruppe): in {c['hervorhebung_anteil']:.0%} der Gruppen",
              '- Beispiele: ' + ' | '.join(f"{_sek(b['t'])} s „{b['text'][:40]}“" for b in c['beispiele'][:8])]
    elif tx['ocr'] != 'aus':
        z.append('- Keine Caption-Zone erkannt (kein wiederkehrender, wechselnder Text in einem Höhenband).')
    if tx.get('einblendungen'):
        z += ['', '| von | bis | Text | Box (x, y, b, h) | Schrift ca. |', '|---|---|---|---|---|']
        for e in tx['einblendungen'][:40]:
            z.append(f"| {_sek(e['von'])} | {_sek(e['bis'])} | {e['text'][:60]} | {e['box']} | {e['schrift_px_ca']} px |")
        if len(tx['einblendungen']) > 40:
            z.append(f"| … | | {len(tx['einblendungen']) - 40} weitere in analyse.json | | |")
    z += ['', '## Gesamtpalette', '', ' '.join(f"`{p['hex']}` {p['anteil']:.0%}" for p in a['palette']), '',
          '## Bögen (alle ansehen, bevor du etwas behauptest)', '']
    for p in a['boegen']['uebersicht']:
        z.append(f'- Übersicht: `{p}`')
    for p in a['boegen']['schnitte']:
        z.append(f'- Schnitte: `{p}` (jede Grenze gegen das Auge prüfen: falscher Alarm? fehlender Schnitt?)')
    z.append(f"- Szenen: `boegen/szene_01.jpg` bis `szene_{len(sz):02d}.jpg`, Bewegung: `boegen/energie.png`")
    ton = ton_abschnitt(Path(a['_ordner']))
    if ton:
        z += ['', '<!-- ton:start -->', ton.strip(), '<!-- ton:end -->']
    return '\n'.join(z) + '\n'


# ---------------------------------------------------------------- Ablauf

def vokabel_finden(video, ordner, eintrag):
    """Gesprochene Wörter (für den Caption-Abgleich) aus dem Register-Transkript oder ordner/transkript.json."""
    kandidaten = [ordner / 'transkript.json', Path(video).with_suffix('.json')]
    if eintrag and eintrag.get('transkript'):
        import vorlagen as V
        kandidaten.insert(0, V.abs_pfad(eintrag['transkript']))
    for k in kandidaten:
        t = _ms.json_lesen(k) if k and k.exists() else None
        if t and t.get('woerter'):
            return {_norm(w['w']) for w in t['woerter'] if len(_norm(w['w'])) >= 2}, str(k)
    return None, None


def zerlegen(video, vid, ordner, a, eintrag=None):
    np = _np()
    start = time.time()
    info = _ms.probe(video)
    ordner.mkdir(parents=True, exist_ok=True)
    print(f"Zerlege {Path(video).name}: {info['breite']}x{info['hoehe']}, {info['fps']} fps, {info['dauer']:.1f} s", flush=True)
    m = messen(video, info)
    fps = m['fps']
    grenzen, blitze, wechsel = grenzen_finden(m, a.schwelle, a.abstand)
    szenen = szenen_bauen(grenzen, len(m['d']), fps)
    bew, glatt = bewegung(m, szenen)
    kam_ev = kamera_ereignisse(m, szenen, grenzen, blitze)
    print(f"  Durchgang 1: {len(m['d'])} Frames, {len(szenen)} Szenen, "
          f"{sum(1 for e in kam_ev if e['art'] == 'kamera')} Kamera-Ereignisse in Szenen ({time.time() - start:.0f} s)", flush=True)
    dauer = len(m['d']) / fps
    ocr_fps = a.ocr_fps if dauer * a.ocr_fps <= 240 else 240 / dauer
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bilder, groesse_k = schluesselbilder(video, info, ocr_fps, tmp)
        methode, roh = ('aus', {}) if a.ohne_ocr else ocr(tmp, [s for s in (a.sprachen or '').split(',') if s])
        print(f"  Durchgang 2: {len(bilder)} Schlüsselbilder, Texterkennung: {methode} ({time.time() - start:.0f} s)", flush=True)
        vokabel, tquelle = vokabel_finden(video, ordner, eintrag)
        captions, einbl, flaeche = text_auswerten(roh, bilder, groesse_k, info, tmp, vokabel) if roh else (None, [], {})
    szenen_merkmale(szenen, bilder, flaeche)
    gesamt_px = np.concatenate([b['klein'][::2, ::2].reshape(-1, 3) for b in bilder])
    gesamt_pal = [{'hex': p['hex'], 'anteil': p['anteil']} for p in palette(gesamt_px, k=8)]
    typ = typ_gesamt(szenen, dauer)
    laengen = [s['dauer'] for s in szenen]
    verlauf = [sum(1 for g in grenzen if j * 10 <= g['t'] < (j + 1) * 10) for j in range(int(np.ceil(dauer / 10)))]
    rhythmus = {'szenen': len(szenen), 'schnitte': len(grenzen),
                'arten': ', '.join(f'{v}× {k}' for k, v in Counter(g['art'] for g in grenzen).items()) or 'keine',
                'schnitte_pro_10s': round(len(grenzen) / max(dauer, 0.01) * 10, 2),
                'szene_mittel': round(float(np.mean(laengen)), 2), 'szene_median': round(float(np.median(laengen)), 2),
                'szene_min': round(min(laengen), 2), 'szene_max': round(max(laengen), 2), 'verlauf': verlauf}
    boegen = {'uebersicht': [], 'szenen': {}, 'schnitte': []}
    if not a.ohne_boegen:
        boegen = boegen_bauen(video, info, szenen, grenzen, ordner)
        print(f"  Bögen fertig ({time.time() - start:.0f} s)", flush=True)
    (ordner / 'boegen').mkdir(exist_ok=True)
    energie_bild(ordner / 'boegen' / 'energie.png', m, glatt, szenen, grenzen, bew, dauer, wechsel, kam_ev)
    boegen['energie'] = 'boegen/energie.png'
    analyse = {'version': 1, 'id': vid, 'datei': str(video), 'erstellt': _ms.jetzt(), 'probe': info,
               'parameter': {'schwelle': a.schwelle, 'abstand': a.abstand, 'ocr_fps': round(ocr_fps, 3)},
               'szenen': szenen, 'schnitte': grenzen,
               'ereignisse': {'blitze': blitze, 'wechsel_im_bild': wechsel,
                              'kamera': [e for e in kam_ev if e['art'] == 'kamera'],
                              'spitzen': [e for e in kam_ev if e['art'] == 'aktion'],
                              'wische': [g for g in grenzen if g['art'] == 'wisch'],
                              'ueberblendungen': [g for g in grenzen if g['art'] == 'ueberblendung']},
               'rhythmus': rhythmus, 'bewegung': bew, 'palette': gesamt_pal,
               'text': {'ocr': methode, 'transkript': tquelle, 'captions': captions, 'einblendungen': einbl},
               'typ': typ, 'boegen': boegen, 'laufzeit_s': round(time.time() - start, 1)}
    _ms.json_schreiben(ordner / 'analyse.json', analyse)
    analyse['_ordner'] = str(ordner)
    (ordner / 'ANALYSE.md').write_text(bericht(analyse), encoding='utf-8')
    return analyse


def main():
    ap = argparse.ArgumentParser(prog='ms zerlegen', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video')
    ap.add_argument('--kanal')
    ap.add_argument('--out')
    ap.add_argument('--schwelle', type=float, default=3.0)
    ap.add_argument('--abstand', type=float, default=0.2)
    ap.add_argument('--ocr-fps', type=float, default=2.0)
    ap.add_argument('--sprachen', default='')
    ap.add_argument('--ohne-ocr', action='store_true')
    ap.add_argument('--ohne-boegen', action='store_true')
    a = ap.parse_args()
    try:
        import numpy  # noqa: F401
        import PIL  # noqa: F401
    except ImportError:
        raise SystemExit('FEHLER: numpy und pillow fehlen in der Studio-Umgebung. "ms check" zeigt, wie es installiert wird.')
    video, vid, ordner, eintrag = ziel_aufloesen(a.video, a.kanal, a.out)
    ziel_log = f'kanaele/{a.kanal}' if a.kanal else None
    _ms.log(f'Zerlege {vid}', wer='motion-analyse', ziel=ziel_log)
    an = zerlegen(video, vid, ordner, a, eintrag)
    if eintrag:
        import vorlagen as V
        V.status_setzen(vid, 'zerlegt', analyse=V.rel(ordner))
    ty, rh = an['typ'], an['rhythmus']
    print(f"Typ: {ty['vorschlag']} · Machbarkeit: {ty['machbarkeit']}")
    print(f"Rhythmus: {rh['szenen']} Szenen, {rh['schnitte_pro_10s']} Schnitte/10 s, Szene im Mittel {rh['szene_mittel']} s")
    c = an['text']['captions']
    print('Captions: ' + (f"Zone {c['zone_rel'][0]:.0%} bis {c['zone_rel'][1]:.0%}, {c['woerter_pro_gruppe']:.0f} Wörter/Gruppe"
                          if c else f"keine erkannt (OCR: {an['text']['ocr']})"))
    _ms.log(f"Zerlegt {vid}: {rh['szenen']} Szenen, Typ {ty['haupt']}", wer='motion-analyse', ziel=ziel_log)
    print(ordner / 'ANALYSE.md')
    print(ordner / 'analyse.json')
    print(ordner / 'boegen')


if __name__ == '__main__':
    sys.exit(main())
