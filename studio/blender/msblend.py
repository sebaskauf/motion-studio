"""msblend: Hilfen für Motion-Studio-Szenen INNERHALB von Blender (bpy). Getestet mit Blender 4.2 LTS bis 5.x.

Gerüst eines Szenenskripts (gestartet mit `ms blender render szene.py ...`):

    import os, sys
    sys.path.insert(0, os.environ.get('MS_BLENDER_LIB') or os.path.dirname(os.path.abspath(__file__)))
    import msblend as mb

    p = mb.start(dauer=4.0)                     # Argumente lesen, Szene leeren, Render einstellen
    cam = mb.kamera((0, -8, 2), (0, 0, 1), brennweite=50)
    mb.licht_preset('drei_punkt', ziel=(0, 0, 1))
    box = mb.form('wuerfel', (0, 0, 0.5), 1.0, material=mb.material_pbr('#ff5a1f'), fase=0.05)
    mb.push_in(cam, 0.0, p.dauer, faktor=0.8)
    mb.rendern(p)                               # PNG-Sequenz nach p.ausgabe, misst Zeit pro Bild

Regeln (gelten für alle Funktionen)
  Zeiten immer in Sekunden ab Szenenbeginn (t=0 ist Bild 1). Umrechnen: sek(t) -> Bildnummer.
  Winkel immer in Grad. Längen in Metern. Blender: Z ist oben, die Kamera schaut meist entlang +Y.
  Farben als Hex ('#ff5a1f') oder sRGB 0..1; msblend rechnet in Blenders lineare Farben um.
  ease wie bei GSAP: 'linear', 'bezier', 'konstant', 'power2.out', 'sine.inout', 'back.out', 'expo.in', 'bounce.out', 'elastic.out'.
  Deterministisch: kein Zufall ohne seed. Gleiche Argumente ergeben das gleiche Bild.

Argumente nach `--` (setzt `ms blender render`): --aufloesung 1080x1920 --fps 30 --dauer 4 --von 1 --bis 120
  --engine eevee|cycles --samples 64 --ausgabe <ordner> --entwurf --seed 1 --blend <datei.blend> --nur-bauen --weiter
  --bilder 1,30,60 (nur diese Bilder, für Stichproben)
Eigene Argumente der Szene: mb.arg('--text', 'NEU').

Inhalt
  Start/Render   start, args, arg, szene_leeren, render_setup, farbraum, gluehen, rendern, sek, info, warnung
  Kamera         kamera, push_in, orbit, dolly, kamera_zoom, blick, kamera_wackeln
  Licht/Welt     licht, licht_preset, hdri, welt_farbe
  Assets         asset('polyhaven:<id>' | 'mixamo:<id>' | Pfad), auch direkt in hdri, glb_import, fbx_import, material_pbr
  Material       farbe_lin, material_pbr, material_toon, material_emission, kontur, material_setzen
  Objekte        form, leer, hohlkehle, boden, text_objekt, eltern, glb_import, fbx_import, armatur_finden,
                 aktion_aus_datei, aktion_legen
  Bewegung       schluessel, bewegen, kurve, ease_wert, drehen, ploppen, quetschen, fallen_lassen
  Partikel       partikel_einfach (Funken, Konfetti; vorab berechnet, deterministisch per seed)
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector

VERSION = tuple(bpy.app.version)
_ZUSTAND = {'fps': 30, 'p': None}


# ---------------------------------------------------------------- Ausgabe für das Werkzeug

def info(text):
    print(f'MSINFO {text}', flush=True)


def warnung(text):
    print(f'MSWARNUNG {text}', flush=True)


# ---------------------------------------------------------------- Argumente und Start

class Param:
    """Render-Parameter der Szene. Felder: breite, hoehe, fps, dauer, frames, von, bis, engine, samples, ausgabe,
    entwurf, seed, blend, nur_bauen, weiter, extra (eigene Argumente der Szene)."""

    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __repr__(self):
        return 'Param(' + ', '.join(f'{k}={v!r}' for k, v in self.__dict__.items() if k != 'extra') + ')'


def _argv():
    return sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(name, standard=None, typ=None):
    """Eigenes Szenen-Argument lesen, z. B. mb.arg('--text', 'NEU') oder mb.arg('--dichte', 1.0, float).
    Ein Schalter ohne Wert (z. B. --konfetti) liefert True."""
    a = _argv()
    if name not in a:
        return standard
    i = a.index(name)
    if i + 1 >= len(a) or a[i + 1].startswith('--'):
        return True
    wert = a[i + 1]
    typ = typ or (type(standard) if standard is not None and not isinstance(standard, bool) else str)
    try:
        return typ(wert)
    except ValueError:
        raise SystemExit(f'FEHLER: {name} erwartet {typ.__name__}, bekam "{wert}".')


def args(dauer=4.0, fps=30, aufloesung=(1080, 1920), engine='eevee', samples=None, seed=1) -> Param:
    """Liest die Standard-Argumente (nach `--`). Die Werte der Szene sind die Vorgaben, die Kommandozeile gewinnt."""
    auf = arg('--aufloesung', None, str)
    breite, hoehe = aufloesung
    if auf:
        try:
            breite, hoehe = (int(x) for x in auf.lower().split('x'))
        except ValueError:
            raise SystemExit(f'FEHLER: --aufloesung "{auf}" ungültig, Beispiel 1080x1920.')
    fps = arg('--fps', fps, int)
    dauer = arg('--dauer', float(dauer), float)
    frames = max(1, int(round(dauer * fps)))
    entwurf = bool(arg('--entwurf', False))
    engine = (arg('--engine', engine, str) or 'eevee').lower()
    sam = arg('--samples', None, int)
    if sam is None:
        sam = samples or ((16 if entwurf else 64) if engine.startswith('ee') else (24 if entwurf else 128))
    ausgabe = arg('--ausgabe', None, str) or os.environ.get('MS_FRAMES') or str(Path.cwd() / 'frames')
    p = Param(breite=breite, hoehe=hoehe, fps=fps, dauer=dauer, frames=frames,
              von=arg('--von', 1, int), bis=arg('--bis', frames, int), engine=engine, samples=sam,
              ausgabe=ausgabe, entwurf=entwurf, seed=arg('--seed', seed, int), blend=arg('--blend', None, str),
              nur_bauen=bool(arg('--nur-bauen', False)), weiter=bool(arg('--weiter', False)), extra=_argv())
    p.bis = min(max(p.von, p.bis), frames)
    bilder = arg('--bilder', None, str)
    p.bilder = sorted({min(frames, max(1, int(x))) for x in str(bilder).split(',') if x.strip()}) if bilder else None
    return p


def start(dauer=4.0, fps=30, aufloesung=(1080, 1920), engine='eevee', samples=None, farbe='AgX',
          bewegungsunschaerfe=False, transparent=False, seed=1) -> Param:
    """Ein Aufruf am Anfang jeder Szene: Argumente lesen, Szene leeren, Render einstellen, Zufall festlegen.
    bewegungsunschaerfe wird im Entwurf ausgeschaltet (spart Zeit)."""
    p = args(dauer, fps, aufloesung, engine, samples, seed)
    szene_leeren()
    render_setup(p.breite, p.hoehe, p.fps, p.engine, p.samples, farbe,
                 bewegungsunschaerfe and not p.entwurf, transparent, p.seed)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, p.frames
    random.seed(p.seed)
    _ZUSTAND['p'] = p
    info(f'Blender {bpy.app.version_string}, {p.breite}x{p.hoehe}, {p.fps} fps, {p.frames} Bilder, '
         f'{sc.render.engine} {p.samples} Samples{" (Entwurf)" if p.entwurf else ""}')
    return p


def szene_leeren():
    """Leere Szene ohne Standardwürfel, Licht und Kamera (Werkseinstellungen)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)


def sek(t) -> int:
    """Sekunde ab Szenenbeginn -> Bildnummer (t=0 ist Bild 1)."""
    return 1 + int(round(float(t) * _ZUSTAND['fps']))


def _eevee_name():
    ids = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    for k in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):  # 4.2 bis 4.x heißt EEVEE "NEXT", ab 5.0 wieder BLENDER_EEVEE
        if k in ids:
            return k
    return ids[0]


def _cycles_gpu():
    """Schaltet die beste GPU für Cycles ein (Metal, OptiX, CUDA, HIP, oneAPI). Liefert den Typ oder None."""
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
    except (KeyError, AttributeError):
        return None
    for typ in ('METAL', 'OPTIX', 'CUDA', 'HIP', 'ONEAPI'):
        try:
            prefs.compute_device_type = typ
        except (TypeError, ValueError):
            continue
        try:
            (getattr(prefs, 'refresh_devices', None) or prefs.get_devices)()
        except Exception:
            pass
        geraete = [d for d in prefs.devices if d.type == typ]
        if geraete:
            for d in prefs.devices:
                d.use = d.type == typ
            return typ
    return None


def farbraum(art='AgX'):
    """'AgX' (filmisch, weiche Lichter, Farben etwas entsättigt), 'Standard' (Hex-Farbe = Bildfarbe, für Toon und
    Markenfarben), 'neutral' (Khronos PBR Neutral: Produktfarben nah am Hex, Lichter trotzdem weich)."""
    vs = bpy.context.scene.view_settings
    namen = {'agx': 'AgX', 'standard': 'Standard', 'neutral': 'Khronos PBR Neutral', 'filmic': 'Filmic'}
    ziel = namen.get(str(art).lower(), art)
    try:
        vs.view_transform = ziel
    except TypeError:
        warnung(f'Farbraum {ziel} gibt es in dieser Blender-Version nicht, nehme AgX.')
        vs.view_transform = 'AgX'
    try:
        vs.look = 'None'
    except TypeError:
        pass
    vs.exposure, vs.gamma = 0.0, 1.0


def render_setup(breite=1080, hoehe=1920, fps=30, engine='eevee', samples=64, farbe='AgX',
                 bewegungsunschaerfe=False, transparent=False, seed=1, strahlen=False):
    """Auflösung, Engine, Samples, Farbraum, Bewegungsunschärfe, PNG-Ausgabe.
    engine: 'eevee' (schnell, für Serien) oder 'cycles' (Pfadtracer, für Einzelshots).
    strahlen=True schaltet in EEVEE Raytracing ein (bessere Spiegelungen, kostet Zeit)."""
    sc = bpy.context.scene
    r = sc.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = int(breite), int(hoehe), 100
    r.fps, r.fps_base = int(fps), 1.0
    _ZUSTAND['fps'] = int(fps)
    if str(engine).lower().startswith('cyc'):
        r.engine = 'CYCLES'
        gpu = _cycles_gpu()
        sc.cycles.device = 'GPU' if gpu else 'CPU'
        sc.cycles.samples = int(samples or 128)
        sc.cycles.use_adaptive_sampling = True
        sc.cycles.use_denoising = True
        sc.cycles.seed = int(seed)
        sc.cycles.use_animated_seed = True  # Rauschen wechselt pro Bild, bleibt aber reproduzierbar
        r.use_persistent_data = True
        info(f'Cycles auf {gpu or "CPU"}')
    else:
        r.engine = _eevee_name()
        sc.eevee.taa_render_samples = int(samples or 64)
        if hasattr(sc.eevee, 'use_raytracing'):
            sc.eevee.use_raytracing = bool(strahlen)
    farbraum(farbe)
    if hasattr(r, 'use_motion_blur'):
        r.use_motion_blur = bool(bewegungsunschaerfe)
        r.motion_blur_shutter = 0.5
    elif hasattr(sc.eevee, 'use_motion_blur'):
        sc.eevee.use_motion_blur = bool(bewegungsunschaerfe)
    r.film_transparent = bool(transparent)
    bild = r.image_settings
    try:
        bild.file_format = 'PNG'
    except TypeError:  # ab 5.x: erst Medientyp Bild wählen
        bild.media_type = 'IMAGE'
        bild.file_format = 'PNG'
    bild.color_mode = 'RGBA' if transparent else 'RGB'
    bild.color_depth = '8'
    bild.compression = 15
    r.use_file_extension = True


def gluehen(staerke=0.5, schwelle=3.0, groesse=6):
    """Leuchten um helle Stellen (Funken, Neon) über den Compositor. Kostet wenig.
    schwelle: nur was heller ist, leuchtet. Unter 2 glüht auch eine hell beleuchtete Bühne (milchiges Bild).
    Fehlt die Funktion in einer Blender-Version, gibt es nur eine Warnung."""
    sc = bpy.context.scene
    try:
        if hasattr(sc, 'compositing_node_group'):  # Blender 5.x
            ng = bpy.data.node_groups.new('MS Komposit', 'CompositorNodeTree')
            sc.compositing_node_group = ng
            if not any(getattr(i, 'in_out', '') == 'OUTPUT' for i in ng.interface.items_tree):
                ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
            nodes, links = ng.nodes, ng.links
            rl = nodes.new('CompositorNodeRLayers')
            aus = nodes.new('NodeGroupOutput')
        else:
            sc.use_nodes = True
            nodes, links = sc.node_tree.nodes, sc.node_tree.links
            nodes.clear()
            rl = nodes.new('CompositorNodeRLayers')
            aus = nodes.new('CompositorNodeComposite')
        gl = nodes.new('CompositorNodeGlare')
        _knoten_wert(gl, 'glare_type', 'Type', 'BLOOM', 'FOG_GLOW')
        _knoten_wert(gl, 'threshold', 'Threshold', float(schwelle))
        if hasattr(gl, 'size'):  # bis 4.x: Größe als Stufe 6..9, Stärke über mix
            gl.size = int(groesse)
            if hasattr(gl, 'mix'):
                gl.mix = float(staerke) * 2 - 1
            else:
                _knoten_wert(gl, 'strength', 'Strength', float(staerke) * 2)
        else:  # ab 5.x: Eingänge, Größe 0..1 relativ zum Bild. Umrechnung an 4.3 abgeglichen (gleicher Look)
            _knoten_wert(gl, 'size', 'Size', min(1.0, max(0.05, (float(groesse) - 4) / 7.5)))
            _knoten_wert(gl, 'strength', 'Strength', float(staerke) * 4.5)
        links.new(rl.outputs['Image'], gl.inputs['Image'])
        links.new(gl.outputs['Image'], aus.inputs[0])
        sc.render.use_compositing = True
    except Exception as e:  # nie wegen Glühen abbrechen
        warnung(f'Glühen nicht gesetzt ({type(e).__name__}: {e}). Szene rendert ohne.')


def _knoten_wert(node, attr, socket, *werte):
    """Setzt eine Knoten-Einstellung, egal ob sie (je Version) Eigenschaft oder Eingang ist. Erster passender Wert gewinnt."""
    for w in werte:
        if hasattr(node, attr):
            try:
                setattr(node, attr, w)
                return True
            except (TypeError, ValueError):
                continue
        eingang = node.inputs.get(socket) if hasattr(node.inputs, 'get') else None
        if eingang is not None:
            try:
                eingang.default_value = w if not isinstance(w, str) else w.replace('_', ' ').title()
                return True
            except (TypeError, ValueError, AttributeError):
                continue
    return False


def rendern(p: Param = None, ordner=None, von=None, bis=None, weiter=None):
    """Rendert Bild für Bild als PNG nach <ordner>/f_0001.png und misst die Zeit pro Bild.
    --weiter überspringt Bilder, die schon da sind (Abbruch fortsetzen). --blend speichert vorher die .blend-Datei."""
    p = p or _ZUSTAND['p'] or args()
    sc = bpy.context.scene
    ordner = Path(ordner or p.ausgabe)
    ordner.mkdir(parents=True, exist_ok=True)
    von, bis = int(von or p.von), int(bis or p.bis)
    weiter = p.weiter if weiter is None else weiter
    if p.blend:
        Path(p.blend).parent.mkdir(parents=True, exist_ok=True)
        bpy.context.preferences.filepaths.save_version = 0  # keine .blend1-Kopien
        bpy.ops.wm.save_as_mainfile(filepath=str(Path(p.blend).resolve()), check_existing=False)
        info(f'Blend gespeichert: {p.blend}')
    ergebnis = {'von': von, 'bis': bis, 'frames_gesamt': p.frames, 'fps': p.fps, 'breite': p.breite, 'hoehe': p.hoehe,
                'engine': sc.render.engine, 'samples': p.samples, 'entwurf': p.entwurf,
                'blender': bpy.app.version_string, 'ausgabe': str(ordner), 'zeiten': {}}
    if p.nur_bauen:
        print('MSERGEBNIS ' + json.dumps(ergebnis), flush=True)
        return ergebnis
    liste = getattr(p, 'bilder', None) or list(range(von, bis + 1))
    unschaerfe = bool(getattr(sc.render, 'use_motion_blur', False))
    aufgewaermt = False
    ergebnis['bilder'] = liste
    print(f'MSSTART {liste[0]} {liste[-1]} {len(liste)}', flush=True)
    for f in liste:
        ziel = ordner / f'f_{f:04d}.png'
        if weiter and ziel.exists():
            continue
        t0 = time.time()
        if unschaerfe and not aufgewaermt:
            # EEVEE rechnet die Bewegungsunschärfe im ersten Render eines Laufs anders. Ein Vorlauf-Bild (nicht
            # gespeichert) macht jedes Bild gleich, egal ob es einzeln oder in einer Reihe gerendert wird.
            sc.frame_set(max(sc.frame_start, f - 1))
            bpy.ops.render.render(write_still=False)
            aufgewaermt = True
        sc.frame_set(f)
        sc.render.filepath = str(ziel)
        bpy.ops.render.render(write_still=True)
        dt = time.time() - t0
        ergebnis['zeiten'][f] = round(dt, 3)
        print(f'MSFRAME {f} {dt:.3f}', flush=True)
    print('MSERGEBNIS ' + json.dumps(ergebnis), flush=True)
    return ergebnis


# ---------------------------------------------------------------- Farben und Ease

def farbe_lin(f, alpha=1.0):
    """'#ff5a1f' oder (r, g, b) in sRGB 0..1 -> lineares RGBA, wie Blender es in Knoten und Lichtern erwartet."""
    if isinstance(f, str):
        h = f.lstrip('#')
        if len(h) == 3:
            h = ''.join(c * 2 for c in h)
        rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    else:
        rgb = list(f)[:3]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return (lin[0], lin[1], lin[2], alpha)


_KURVE = {'sine': 'SINE', 'quad': 'QUAD', 'power1': 'QUAD', 'cubic': 'CUBIC', 'power2': 'CUBIC', 'quart': 'QUART',
          'power3': 'QUART', 'quint': 'QUINT', 'power4': 'QUINT', 'expo': 'EXPO', 'circ': 'CIRC', 'back': 'BACK',
          'elastic': 'ELASTIC', 'bounce': 'BOUNCE'}
_RICHTUNG = {'in': 'EASE_IN', 'out': 'EASE_OUT', 'inout': 'EASE_IN_OUT', 'in_out': 'EASE_IN_OUT'}


def _ease(ease):
    """'power2.out' -> ('CUBIC', 'EASE_OUT'). Ohne Richtung gilt 'out' (wie GSAP)."""
    e = str(ease or 'bezier').lower().replace('-', '.')
    if e in ('linear', 'none'):
        return 'LINEAR', 'AUTO'
    if e in ('konstant', 'step', 'constant'):
        return 'CONSTANT', 'AUTO'
    if e in ('bezier', 'sanft', 'auto'):
        return 'BEZIER', 'AUTO'
    name, _, richtung = e.partition('.')
    if name not in _KURVE:
        raise SystemExit(f'FEHLER: ease "{ease}" unbekannt. Beispiele: linear, bezier, power2.out, back.out, sine.inout.')
    return _KURVE[name], _RICHTUNG.get(richtung or 'out', 'EASE_OUT')


def _ease_in(name, x):
    if name in ('SINE',):
        return 1 - math.cos(x * math.pi / 2)
    if name == 'QUAD':
        return x ** 2
    if name == 'CUBIC':
        return x ** 3
    if name == 'QUART':
        return x ** 4
    if name == 'QUINT':
        return x ** 5
    if name == 'EXPO':
        return 0.0 if x <= 0 else 2 ** (10 * x - 10)
    if name == 'CIRC':
        return 1 - math.sqrt(max(0.0, 1 - x * x))
    if name == 'BACK':
        c1 = 1.70158
        return (c1 + 1) * x ** 3 - c1 * x ** 2
    if name == 'ELASTIC':
        if x in (0, 1):
            return float(x)
        return -(2 ** (10 * x - 10)) * math.sin((x * 10 - 10.75) * (2 * math.pi) / 3)
    if name == 'BOUNCE':
        return 1 - _bounce_out(1 - x)
    return x


def _bounce_out(x):
    n1, d1 = 7.5625, 2.75
    if x < 1 / d1:
        return n1 * x * x
    if x < 2 / d1:
        x -= 1.5 / d1
        return n1 * x * x + 0.75
    if x < 2.5 / d1:
        x -= 2.25 / d1
        return n1 * x * x + 0.9375
    x -= 2.625 / d1
    return n1 * x * x + 0.984375


def ease_wert(ease, x):
    """Ease als Zahl 0..1 (für vorab berechnete Bewegungen wie orbit und Partikel)."""
    x = min(1.0, max(0.0, float(x)))
    kurve, richtung = _ease(ease)
    if kurve in ('LINEAR', 'CONSTANT'):
        return x if kurve == 'LINEAR' else 0.0
    if kurve == 'BEZIER':
        kurve, richtung = 'SINE', 'EASE_IN_OUT'
    if richtung == 'EASE_IN':
        return _ease_in(kurve, x)
    if richtung == 'EASE_OUT':
        return 1 - _ease_in(kurve, 1 - x)
    return _ease_in(kurve, 2 * x) / 2 if x < 0.5 else 1 - _ease_in(kurve, 2 - 2 * x) / 2


# ---------------------------------------------------------------- Keyframes

def _fcurves(id_data):
    """F-Kurven eines Datenblocks, für alte Aktionen (bis 4.3) und Slot-Aktionen (ab 4.4, Pflicht ab 5.0)."""
    ad = getattr(id_data, 'animation_data', None)
    if not ad or not ad.action:
        return []
    act = ad.action
    if getattr(ad, 'action_slot', None) is not None:
        try:
            from bpy_extras import anim_utils
            cb = anim_utils.action_get_channelbag_for_slot(act, ad.action_slot)
            if cb is not None:
                return list(cb.fcurves)
        except (ImportError, AttributeError):
            pass
        kurven = []
        for layer in getattr(act, 'layers', []):
            for strip in layer.strips:
                for cb in getattr(strip, 'channelbags', []):
                    kurven += list(cb.fcurves)
        if kurven:
            return kurven
    return list(getattr(act, 'fcurves', []))


def _fcurve(ding, attr, index):
    pfad = ding.path_from_id(attr) if hasattr(ding, 'path_from_id') else attr
    for fc in _fcurves(ding.id_data):
        if fc.data_path == pfad and (index < 0 or fc.array_index == index):
            yield fc


def _wert_setzen(ding, attr, wert, index=-1):
    """Zahl bei index >= 0: nur diese Komponente. Zahl ohne index bei Vektor: alle Komponenten. Sonst Tupel."""
    if wert is None:
        return
    alt = getattr(ding, attr)
    if not hasattr(alt, '__len__'):
        setattr(ding, attr, wert)
        return
    neu = list(alt)
    if isinstance(wert, (int, float)):
        if index >= 0:
            neu[index] = wert
        else:
            neu = [wert] * len(alt)
    elif index >= 0 and len(wert) == len(alt):
        neu[index] = wert[index]
    else:
        neu = list(wert)
    setattr(ding, attr, tuple(neu))


def schluessel(ding, attr, t, wert=None, ease='bezier', index=-1):
    """Keyframe bei Sekunde t (optional mit Wert). ease gilt für die Strecke NACH diesem Keyframe.
    ding: Objekt, Kamera-/Lichtdaten oder Knoten-Eingang. Beispiel: schluessel(obj, 'location', 1.2, (0, 0, 2)).
    index: nur eine Komponente (0=x, 1=y, 2=z), Wert dann als Zahl oder als Tupel."""
    _wert_setzen(ding, attr, wert, index)
    f = sek(t)
    ding.keyframe_insert(data_path=attr, frame=f, index=index)
    interp, easing = _ease(ease)
    for fc in _fcurve(ding, attr, index):
        for kp in fc.keyframe_points:
            if abs(kp.co.x - f) < 0.5:
                kp.interpolation = interp
                kp.easing = easing
        fc.update()


def bewegen(ding, attr, t0, t1, a, b, ease='power2.inout', index=-1):
    """Von Wert a (bei t0) nach Wert b (bei t1) mit Ease. Danach steht ding auf b."""
    schluessel(ding, attr, t0, a, ease, index)
    schluessel(ding, attr, t1, b, ease, index)


def kurve(ding, attr, zeiten, werte, index=0, ease='linear'):
    """Viele Keyframes auf einmal (schnell), z. B. vorab berechnete Bewegung. zeiten in Sekunden, werte Zahlen."""
    if not zeiten:
        return
    frames = [sek(t) for t in zeiten]
    alt = getattr(ding, attr)
    if hasattr(alt, '__len__'):
        neu = list(alt)
        neu[index] = werte[0]
        setattr(ding, attr, neu)
    else:
        setattr(ding, attr, werte[0])
    ding.keyframe_insert(data_path=attr, frame=frames[0], index=index if hasattr(alt, '__len__') else -1)
    interp, easing = _ease(ease)
    for fc in _fcurve(ding, attr, index if hasattr(alt, '__len__') else -1):
        punkte = fc.keyframe_points
        start = len(punkte)
        punkte.add(len(frames) - 1)
        for i, (f, w) in enumerate(zip(frames[1:], werte[1:])):
            kp = punkte[start + i]
            kp.co = (f, w)
            kp.handle_left = (f - 0.3, w)
            kp.handle_right = (f + 0.3, w)
        for kp in punkte:
            kp.interpolation = interp
            kp.easing = easing
        fc.update()
        break


def drehen(obj, t0, t1, umdrehungen=1.0, achse='Z', ease='linear'):
    """Dreht um die eigene Achse (Drehteller). Mehrere Umdrehungen gehen, Winkel addieren sich."""
    i = 'XYZ'.index(achse.upper())
    a = obj.rotation_euler[i]
    bewegen(obj, 'rotation_euler', t0, t1, a, a + math.radians(360 * umdrehungen), ease, index=i)


def ploppen(obj, t, dauer=0.35, ease='back.out', von=0.0):
    """Erscheint mit Überschwingen: Skala von 'von' auf die aktuelle Skala. Vor t unsichtbar (Skala 0)."""
    ziel = tuple(obj.scale)
    if t > 0:
        schluessel(obj, 'scale', max(0.0, t - 1 / _ZUSTAND['fps']), (von,) * 3, 'konstant')
    bewegen(obj, 'scale', t, t + dauer, (von,) * 3, ziel, ease)


def quetschen(obj, t, staerke=0.25, dauer=0.3):
    """Squash und Stretch beim Aufprall: flach und breit, dann elastisch zurück."""
    s = tuple(obj.scale)
    schluessel(obj, 'scale', t, s, 'power2.out')
    breit = (s[0] * (1 + staerke), s[1] * (1 + staerke), s[2] * (1 - staerke))
    schluessel(obj, 'scale', t + dauer * 0.25, breit, 'elastic.out')
    schluessel(obj, 'scale', t + dauer, s, 'bezier')


def fallen_lassen(obj, t0, t1, hoehe=5.0, nachhuepfen=0.2, quetsch=0.25):
    """Objekt fällt von oben auf seine aktuelle Position (Aufprall bei t1), hüpft kurz nach. Liefert t1."""
    z = obj.location.z
    schluessel(obj, 'location', t0, (obj.location.x, obj.location.y, z + hoehe), 'power2.in', index=2)
    schluessel(obj, 'location', t1, (obj.location.x, obj.location.y, z), 'power2.out', index=2)
    if nachhuepfen > 0:
        hoch = t1 + 0.16
        schluessel(obj, 'location', hoch, (obj.location.x, obj.location.y, z + nachhuepfen), 'power2.in', index=2)
        schluessel(obj, 'location', hoch + 0.16, (obj.location.x, obj.location.y, z), 'bezier', index=2)
    if quetsch:
        quetschen(obj, t1, quetsch)
    return t1


# ---------------------------------------------------------------- Objekte und Hilfen

def _verlinken(obj, sammlung=None):
    (sammlung or bpy.context.scene.collection).objects.link(obj)
    return obj


def leer(name='Leer', pos=(0, 0, 0), sammlung=None):
    o = bpy.data.objects.new(name, None)
    o.empty_display_size = 0.3
    o.location = pos
    return _verlinken(o, sammlung)


def eltern(kind, eltern_obj):
    """Hängt kind an eltern_obj, ohne dass es springt."""
    bpy.context.view_layer.update()
    welt = kind.matrix_world.copy()
    kind.parent = eltern_obj
    kind.matrix_world = welt
    return kind


def _grad(rot):
    return tuple(math.radians(r) for r in rot)


def form(art='wuerfel', pos=(0, 0, 0), groesse=1.0, rot=(0, 0, 0), material=None, fase=0.0, glatt=True,
         name=None, segmente=64, rohr=None):
    """Grundform: 'wuerfel', 'zylinder', 'kugel', 'kegel', 'torus', 'ebene', 'ikosaeder'.
    groesse: Zahl oder (x, y, z) in Metern (Außenmaß). fase: abgerundete Kanten in Metern (Bevel).
    rohr (nur torus): Rohrradius in Metern, groesse ist dann der Außendurchmesser (Neonring: rohr=0.03)."""
    g = (groesse,) * 3 if isinstance(groesse, (int, float)) else tuple(groesse)
    if art == 'torus' and rohr:
        bpy.ops.mesh.primitive_torus_add(major_radius=g[0] / 2 - rohr, minor_radius=rohr, major_segments=segmente * 2,
                                         minor_segments=16)
        obj = bpy.context.active_object
        obj.name = name or 'Ring'
        obj.location, obj.rotation_euler = pos, _grad(rot)
        for poly in obj.data.polygons:
            poly.use_smooth = True
        if material:
            material_setzen(obj, material)
        return obj
    ops = bpy.ops.mesh
    if art == 'wuerfel':
        ops.primitive_cube_add(size=1)
    elif art == 'zylinder':
        ops.primitive_cylinder_add(vertices=segmente, radius=0.5, depth=1)
    elif art == 'kugel':
        ops.primitive_uv_sphere_add(segments=segmente, ring_count=max(16, segmente // 2), radius=0.5)
    elif art == 'kegel':
        ops.primitive_cone_add(vertices=segmente, radius1=0.5, depth=1)
    elif art == 'torus':
        ops.primitive_torus_add(major_radius=0.4, minor_radius=0.1, major_segments=segmente, minor_segments=24)
    elif art == 'ebene':
        ops.primitive_plane_add(size=1)
    elif art == 'ikosaeder':
        ops.primitive_ico_sphere_add(subdivisions=1, radius=0.5)
    else:
        raise SystemExit(f'FEHLER: Form "{art}" unbekannt.')
    obj = bpy.context.active_object
    obj.name = name or art.capitalize()
    obj.location = pos
    obj.rotation_euler = _grad(rot)
    obj.scale = g
    if fase:
        # Maßstab in die Geometrie übernehmen, damit die Fase überall gleich breit ist
        obj.data.transform(_skala_matrix(g))
        obj.scale = (1, 1, 1)
        if hasattr(obj.data, 'set_sharp_from_angle'):
            obj.data.set_sharp_from_angle(angle=math.radians(40))
        m = obj.modifiers.new('Fase', 'BEVEL')
        m.width = float(fase)
        m.segments = 4
        m.limit_method = 'ANGLE'
        m.angle_limit = math.radians(40)
        try:
            m.harden_normals = True
        except AttributeError:
            pass
    if glatt and (fase or art not in ('wuerfel', 'ebene')):
        for poly in obj.data.polygons:
            poly.use_smooth = True
        if not fase and hasattr(obj.data, 'set_sharp_from_angle') and art in ('zylinder', 'kegel'):
            obj.data.set_sharp_from_angle(angle=math.radians(40))
    if material:
        material_setzen(obj, material)
    return obj


def _skala_matrix(g):
    from mathutils import Matrix
    return Matrix.Diagonal((g[0], g[1], g[2], 1.0))


def material_setzen(obj, material):
    """Setzt ein Material (ersetzt vorhandene)."""
    if obj.type in ('MESH', 'CURVE', 'FONT', 'SURFACE', 'META'):
        obj.data.materials.clear()
        obj.data.materials.append(material)
    return obj


def hohlkehle(breite=30.0, tiefe=14.0, hoehe=14.0, radius=3.0, wand_y=4.0, farbe='#efe6da', material=None,
              name='Hohlkehle'):
    """Endlose Studiobühne: Boden geht in einer Rundung in die Rückwand über (keine sichtbare Kante).
    Boden auf z=0, Rückwand bei y=wand_y. Kamera schaut entlang +Y auf die Wand."""
    profil = [(-tiefe, 0.0), (wand_y - radius - 2, 0.0), (wand_y - radius, 0.0)]
    for i in range(1, 17):
        w = math.radians(90 * i / 16)
        profil.append((wand_y - radius + radius * math.sin(w), radius - radius * math.cos(w)))
    profil += [(wand_y, radius + 2), (wand_y, hoehe)]
    verts, faces = [], []
    for y, z in profil:
        verts += [(-breite / 2, y, z), (breite / 2, y, z)]
    for i in range(len(profil) - 1):
        a = 2 * i
        faces.append((a, a + 1, a + 3, a + 2))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    for poly in me.polygons:
        poly.use_smooth = True
    obj = _verlinken(bpy.data.objects.new(name, me))
    # Die Bühne wirft keinen Schatten auf sich selbst: sonst zeigt EEVEE eine harte Linie am Übergang
    # Boden/Wand (Schattenkanten der Flächenlichter). Schatten anderer Objekte empfängt sie weiter.
    if hasattr(obj, 'visible_shadow'):
        obj.visible_shadow = False
    material_setzen(obj, material or material_pbr(farbe, rauheit=0.65, name=f'{name}_Mat'))
    return obj


def boden(groesse=40.0, farbe='#d9d4cc', material=None, z=0.0):
    """Einfacher Boden (Ebene)."""
    return form('ebene', (0, 0, z), (groesse, groesse, 1), material=material or material_pbr(farbe, rauheit=0.7))


def text_objekt(text, schrift=None, groesse=1.0, tiefe=0.08, fase=0.012, pos=(0, 0, 0), rot=(90, 0, 0),
                material=None, ausrichtung='mitte', max_breite=None, zeilenabstand=1.0, name=None):
    """3D-Text. Steht mit rot=(90, 0, 0) aufrecht und schaut zur Kamera bei -Y.
    schrift: Pfad zu .ttf/.otf (sonst Blenders eingebaute Schrift, kann Umlaute).
    max_breite: Text wird so verkleinert, dass er höchstens so breit ist (Meter)."""
    cu = bpy.data.curves.new(name or 'Text', 'FONT')
    cu.body = text
    cu.size = float(groesse)
    cu.extrude = float(tiefe)
    cu.bevel_depth = float(fase)
    cu.bevel_resolution = 3
    cu.space_line = float(zeilenabstand)
    cu.align_x = {'mitte': 'CENTER', 'links': 'LEFT', 'rechts': 'RIGHT'}.get(ausrichtung, 'CENTER')
    cu.align_y = 'CENTER'
    if schrift:
        if not Path(schrift).exists():
            raise SystemExit(f'FEHLER: Schrift {schrift} fehlt.')
        cu.font = bpy.data.fonts.load(str(schrift), check_existing=True)
    obj = _verlinken(bpy.data.objects.new(name or 'Text', cu))
    obj.location = pos
    obj.rotation_euler = _grad(rot)
    if material:
        material_setzen(obj, material)
    if max_breite:
        bpy.context.view_layer.update()
        b = obj.dimensions.x
        if b > max_breite > 0:
            f = max_breite / b
            obj.scale = (f, f, f)
    return obj


# ---------------------------------------------------------------- Kamera

def kamera(pos=(0, -8, 2), ziel=(0, 0, 1), brennweite=50, name='Kamera', aktiv=True):
    """Kamera mit Rig: Rig-Leerobjekt im Ziel (für orbit und dolly), Ziel-Leerobjekt (Blickpunkt), Kamera blickt
    immer aufs Ziel. Kamerafahrten in zeitlicher Reihenfolge aufrufen, jede startet dort, wo die letzte endete."""
    ziel = Vector(ziel)
    rig = leer(f'{name}_Rig', ziel)
    blick_obj = leer(f'{name}_Ziel', (0, 0, 0))
    blick_obj.parent = rig
    cd = bpy.data.cameras.new(name)
    cd.lens = float(brennweite)
    cd.clip_start, cd.clip_end = 0.05, 1000
    cd.sensor_fit = 'AUTO'
    cam = _verlinken(bpy.data.objects.new(name, cd))
    cam.parent = rig
    cam.location = Vector(pos) - ziel
    c = cam.constraints.new('TRACK_TO')
    c.target = blick_obj
    c.track_axis, c.up_axis = 'TRACK_NEGATIVE_Z', 'UP_Y'
    cam['ms_rig'], cam['ms_ziel'] = rig.name, blick_obj.name
    if aktiv:
        bpy.context.scene.camera = cam
    return cam


def _rig(cam):
    return bpy.data.objects[cam['ms_rig']]


def _blick(cam):
    return bpy.data.objects[cam['ms_ziel']]


def push_in(cam, t0, t1, faktor=0.75, ease='power2.inout'):
    """Kamera fährt aufs Ziel zu. faktor 0.75 = Abstand am Ende 75 % vom Anfang. faktor > 1 = Pull-out."""
    a = cam.location.copy()
    z = _blick(cam).location
    bewegen(cam, 'location', t0, t1, a, z + (a - z) * float(faktor), ease)


def dolly(cam, t0, t1, versatz=(1, 0, 0), ease='power2.inout'):
    """Kamera und Ziel verschieben sich gemeinsam (Truck/Dolly/Kran). versatz in Metern (Welt)."""
    rig = _rig(cam)
    a = rig.location.copy()
    bewegen(rig, 'location', t0, t1, a, a + Vector(versatz), ease)


def orbit(cam, t0, t1, winkel=30.0, ease='power2.inout'):
    """Kamera kreist ums Ziel (um die senkrechte Achse). winkel in Grad, positiv = gegen den Uhrzeiger von oben."""
    rig = _rig(cam)
    a = rig.rotation_euler.z
    bewegen(rig, 'rotation_euler', t0, t1, a, a + math.radians(winkel), ease, index=2)


def blick(cam, t0, t1, neues_ziel, ease='power2.inout'):
    """Blickpunkt wandert (Schwenk/Neigung), Kamera bleibt stehen. neues_ziel in Welt-Koordinaten."""
    b = _blick(cam)
    bpy.context.view_layer.update()
    lokal = _rig(cam).matrix_world.inverted() @ Vector(neues_ziel)
    bewegen(b, 'location', t0, t1, b.location.copy(), lokal, ease)


def kamera_zoom(cam, t0, t1, brennweite, ease='power2.inout'):
    """Brennweite ändern (Zoom, Vertigo zusammen mit push_in)."""
    bewegen(cam.data, 'lens', t0, t1, cam.data.lens, float(brennweite), ease)


def kamera_wackeln(cam, t, dauer=0.35, staerke=0.05, seed=7):
    """Kurzes Wackeln (Aufprall). Nutzt delta_location, stört also keine anderen Fahrten."""
    rnd = random.Random(seed)
    n = max(2, int(dauer * _ZUSTAND['fps']))
    zeiten = [t + i / _ZUSTAND['fps'] for i in range(n + 1)]
    for achse in range(3):
        werte = [0.0] + [staerke * (1 - i / n) ** 2 * rnd.uniform(-1, 1) for i in range(1, n)] + [0.0]
        kurve(cam, 'delta_location', zeiten, werte, index=achse)


# ---------------------------------------------------------------- Licht und Welt

def licht(art='AREA', pos=(3, -4, 5), ziel=(0, 0, 1), energie=500.0, farbe='#ffffff', groesse=1.0, name=None,
          winkel_sonne=3.0):
    """Ein Licht. art: 'AREA' (weich), 'SPOT', 'POINT', 'SUN'. energie in Watt (Sonne: Stärke ~1-5).
    groesse: Kantenlänge (Fläche) bzw. Radius. Das Licht zeigt auf ziel."""
    ld = bpy.data.lights.new(name or art.title(), art)
    ld.energy = float(energie)
    ld.color = farbe_lin(farbe)[:3]
    if art == 'AREA':
        ld.size = float(groesse)
    elif art == 'SUN':
        ld.angle = math.radians(winkel_sonne)
    else:
        ld.shadow_soft_size = float(groesse)
    obj = _verlinken(bpy.data.objects.new(name or art.title(), ld))
    obj.location = pos
    richtung = Vector(ziel) - Vector(pos)
    obj.rotation_euler = richtung.to_track_quat('-Z', 'Y').to_euler()
    return obj


def _welt():
    sc = bpy.context.scene
    if not sc.world:
        sc.world = bpy.data.worlds.new('Welt')
    w = sc.world
    try:
        w.use_nodes = True
    except AttributeError:
        pass
    return w


def welt_farbe(farbe='#202020', staerke=1.0):
    """Einfarbige Umgebung (Hintergrund und schwaches Umgebungslicht)."""
    nt = _welt().node_tree
    nt.nodes.clear()
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = farbe_lin(farbe)
    bg.inputs['Strength'].default_value = float(staerke)
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    return bg


def hdri(pfad, staerke=1.0, drehung=0.0, hintergrund=None, hintergrund_staerke=1.0, schatten_weich=12.0):
    """Licht und Spiegelungen aus einem HDRI (.hdr/.exr, z. B. Poly Haven, siehe asset()).
    hintergrund=None: das HDRI ist sichtbar. hintergrund='#f2e8dc': die Kamera sieht diese Farbe, das Licht
    kommt trotzdem aus dem HDRI (sauberer Motion-Design-Hintergrund). drehung in Grad (Lichtrichtung).
    schatten_weich: EEVEE zieht die hellste Stelle des HDRI als Sonne heraus; deren Winkel in Grad. Klein = harte
    Schatten (Blender 5.x zeichnet sie schärfer als 4.x), 12 = weicher Studio-Schatten in beiden Versionen."""
    pfad = asset(pfad, 'hdris')
    w = _welt()
    if hasattr(w, 'sun_angle'):
        w.sun_angle = math.radians(schatten_weich)
    nt = w.node_tree
    nt.nodes.clear()
    tk = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value = (0, 0, math.radians(drehung))
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    env.image = bpy.data.images.load(str(pfad), check_existing=True)
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = float(staerke)
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(tk.outputs['Generated'], mp.inputs['Vector'])
    nt.links.new(mp.outputs['Vector'], env.inputs['Vector'])
    nt.links.new(env.outputs['Color'], bg.inputs['Color'])
    if hintergrund is None:
        nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    else:
        bg2 = nt.nodes.new('ShaderNodeBackground')
        bg2.inputs['Color'].default_value = farbe_lin(hintergrund)
        bg2.inputs['Strength'].default_value = float(hintergrund_staerke)
        lp = nt.nodes.new('ShaderNodeLightPath')
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
        nt.links.new(bg.outputs['Background'], mix.inputs[1])
        nt.links.new(bg2.outputs['Background'], mix.inputs[2])
        nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    return env


def licht_preset(art='drei_punkt', ziel=(0, 0, 1), abstand=6.0, staerke=1.0, hdri_pfad=None, welt='#1c1c22'):
    """Fertige Lichtaufbauten. Liefert die Lichter (Liste).
    'drei_punkt': Führung vorne links oben, Aufheller vorne rechts, Kante hinten rechts (Kontur).
    'studio':     große Softbox oben, zwei Streifenlichter seitlich hinten (Produktlook).
    'sonne':      Sonne schräg von vorn links, weicher Schatten, Himmelsfarbe als Umgebung.
    'hdri':       nur HDRI (hdri_pfad), plus schwache Kante für Trennung vom Hintergrund."""
    z = Vector(ziel)
    k = (abstand / 6.0) ** 2 * float(staerke)
    if art == 'drei_punkt':
        welt_farbe(welt, 0.6)
        return [licht('AREA', z + Vector((-0.55, -0.75, 0.55)) * abstand, z, 900 * k, '#fff1e0', 2.5, 'Fuehrung'),
                licht('AREA', z + Vector((0.8, -0.6, 0.1)) * abstand, z, 280 * k, '#e4ecff', 4.0, 'Aufheller'),
                licht('AREA', z + Vector((0.45, 0.85, 0.6)) * abstand, z, 1100 * k, '#ffffff', 1.5, 'Kante')]
    if art == 'studio':
        welt_farbe(welt, 0.8)
        return [licht('AREA', z + Vector((0, -0.2, 1.0)) * abstand, z, 1300 * k, '#ffffff', 5.0, 'Softbox'),
                licht('AREA', z + Vector((-0.7, 0.4, 0.2)) * abstand, z, 500 * k, '#ffffff', 2.0, 'Streifen_L'),
                licht('AREA', z + Vector((0.7, 0.4, 0.2)) * abstand, z, 500 * k, '#ffffff', 2.0, 'Streifen_R')]
    if art == 'sonne':
        welt_farbe('#9fb8d8', 0.9)
        return [licht('SUN', z + Vector((-4, -6, 8)), z, 3.5 * staerke, '#fff2df', name='Sonne', winkel_sonne=4.0)]
    if art == 'hdri':
        if not hdri_pfad:
            raise SystemExit('FEHLER: licht_preset("hdri") braucht hdri_pfad (z. B. "polyhaven:studio_small_09").')
        hdri(hdri_pfad, staerke)
        return [licht('AREA', z + Vector((0.45, 0.85, 0.6)) * abstand, z, 500 * k, '#ffffff', 1.5, 'Kante')]
    raise SystemExit(f'FEHLER: Lichtaufbau "{art}" unbekannt (drei_punkt, studio, sonne, hdri).')


def asset(pfad_oder_id, typ=None):
    """Pfad zu einer Asset-Datei. Akzeptiert einen echten Pfad oder '<quelle>:<id>', z. B. 'polyhaven:studio_small_09'
    (geladen mit `ms assets laden`) oder 'mixamo:winken', 'sketchfab:roboter' (abgelegt mit `ms assets eintragen`).
    Gesucht wird in ARBEIT/assets/<quelle>/<typ>/<id>/lizenz.json, Feld "hauptdatei"."""
    s = str(pfad_oder_id)
    p = Path(os.path.expanduser(s))
    if p.exists():
        return p
    quelle, _, aid = s.partition(':')
    if not aid or len(quelle) < 2 or not quelle.isalpha():
        raise SystemExit(f'FEHLER: Datei {p} fehlt.')
    basis = Path(os.path.expanduser(os.environ.get('MS_ARBEIT') or '~/MotionStudio')) / 'assets' / quelle
    typen = ([typ] if typ else []) + sorted(d.name for d in basis.iterdir() if d.is_dir()) if basis.exists() else []
    for t in typen:
        lz = basis / t / aid / 'lizenz.json'
        if lz.exists():
            d = json.loads(lz.read_text(encoding='utf-8'))
            if not d.get('hauptdatei'):
                raise SystemExit(f'FEHLER: {lz} nennt keine Hauptdatei. Pfad direkt angeben.')
            return lz.parent / d['hauptdatei']
    if quelle == 'polyhaven':
        raise SystemExit(f'FEHLER: Poly-Haven-Asset {aid} nicht geladen. Erst: ms assets laden polyhaven {aid} --aufloesung 1k')
    raise SystemExit(f'FEHLER: Asset {s} nicht gefunden. Erst: ms assets eintragen <datei> --quelle {quelle} --id {aid} …')


# ---------------------------------------------------------------- Materialien

def _eingang(node, *namen):
    for n in namen:
        if n in node.inputs:
            return node.inputs[n]
    return None


def _neues_material(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except AttributeError:
        pass
    return m


def material_pbr(farbe='#cccccc', rauheit=0.4, metall=0.0, klarlack=0.0, emission=None, emission_staerke=0.0,
                 transmission=0.0, ior=1.45, alpha=1.0, texturen=None, skala=1.0, name=None):
    """Physikalisches Material (Principled BSDF). texturen: Ordner mit Poly-Haven-Maps (…_diff_, _rough_, _nor_gl_,
    _metal_, _arm_) oder 'polyhaven:<id>'. Dann ersetzen die Maps farbe/rauheit/metall."""
    m = _neues_material(name or f'PBR_{farbe}')
    nt = m.node_tree
    bsdf = nt.nodes.get('Principled BSDF') or nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = farbe_lin(farbe)
    bsdf.inputs['Roughness'].default_value = float(rauheit)
    bsdf.inputs['Metallic'].default_value = float(metall)
    _setze(bsdf, ('IOR',), ior)
    _setze(bsdf, ('Coat Weight', 'Clearcoat'), klarlack)
    _setze(bsdf, ('Transmission Weight', 'Transmission'), transmission)
    if emission:
        e = _eingang(bsdf, 'Emission Color', 'Emission')
        if e is not None:
            e.default_value = farbe_lin(emission)
        _setze(bsdf, ('Emission Strength',), emission_staerke)
    if alpha < 1:
        bsdf.inputs['Alpha'].default_value = float(alpha)
        if hasattr(m, 'surface_render_method'):
            m.surface_render_method = 'BLENDED'
        elif hasattr(m, 'blend_method'):
            m.blend_method = 'BLEND'
    if texturen:
        _texturen_anschliessen(m, bsdf, texturen, skala)
    return m


def _setze(node, namen, wert):
    e = _eingang(node, *namen)
    if e is not None:
        e.default_value = float(wert)


def _texturen_anschliessen(m, bsdf, texturen, skala):
    ordner = asset(texturen, 'textures')
    ordner = ordner if ordner.is_dir() else ordner.parent
    bilder = sorted(p for p in ordner.rglob('*') if p.suffix.lower() in ('.jpg', '.jpeg', '.png', '.exr', '.tif'))

    def finde(*muster):
        for p in bilder:
            n = p.stem.lower()
            if any(mu in n for mu in muster):
                return p
        return None

    nt = m.node_tree
    tk = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (skala, skala, skala)
    nt.links.new(tk.outputs['UV'], mp.inputs['Vector'])

    def bild(p, farbig):
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = bpy.data.images.load(str(p), check_existing=True)
        if not farbig:
            n.image.colorspace_settings.name = 'Non-Color'
        nt.links.new(mp.outputs['Vector'], n.inputs['Vector'])
        return n

    diff = finde('_diff', '_albedo', '_basecolor', '_col')
    if diff:
        nt.links.new(bild(diff, True).outputs['Color'], bsdf.inputs['Base Color'])
    arm = finde('_arm')
    rough, metal = finde('_rough'), finde('_metal')
    if rough:
        nt.links.new(bild(rough, False).outputs['Color'], bsdf.inputs['Roughness'])
    if metal:
        nt.links.new(bild(metal, False).outputs['Color'], bsdf.inputs['Metallic'])
    if arm and not (rough and metal):
        tr = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(bild(arm, False).outputs['Color'], tr.inputs['Color'])
        if not rough:
            nt.links.new(tr.outputs[1], bsdf.inputs['Roughness'])
        if not metal:
            nt.links.new(tr.outputs[2], bsdf.inputs['Metallic'])
    nor = finde('_nor_gl', '_normal', '_nrm')
    if nor:
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nt.links.new(bild(nor, False).outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])


def material_emission(farbe='#ffffff', staerke=5.0, name=None):
    """Selbstleuchtend (Funken, Neon, Bildschirme). Mit gluehen() entsteht ein Schein."""
    m = _neues_material(name or f'Leucht_{farbe}')
    nt = m.node_tree
    nt.nodes.clear()
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = farbe_lin(farbe)
    em.inputs['Strength'].default_value = float(staerke)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    return m


def material_toon(farbe='#ff5a1f', schatten=None, stufen=2, kante=0.45, name=None):
    """Toon-Look (Cel-Shading): harte Licht/Schatten-Stufen. Funktioniert in EEVEE (Shader to RGB).
    In Cycles gibt es kein Shader to RGB: dort entsteht ein mattes PBR-Material als Ersatz (mit Warnung).
    Für exakte Markenfarben farbe='Standard' in start() setzen (AgX verschiebt Farben)."""
    lin = farbe_lin(farbe)
    if schatten is None:
        schatten_lin = (lin[0] * 0.42, lin[1] * 0.38, lin[2] * 0.5, 1.0)
    else:
        schatten_lin = farbe_lin(schatten)
    if bpy.context.scene.render.engine == 'CYCLES':
        warnung('material_toon in Cycles: Ersatz durch mattes PBR (Toon braucht EEVEE).')
        return material_pbr(farbe, rauheit=1.0, name=name)
    m = _neues_material(name or f'Toon_{farbe}')
    nt = m.node_tree
    nt.nodes.clear()
    diff = nt.nodes.new('ShaderNodeBsdfDiffuse')
    s2r = nt.nodes.new('ShaderNodeShaderToRGB')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    em = nt.nodes.new('ShaderNodeEmission')
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    cr = ramp.color_ramp
    cr.interpolation = 'CONSTANT'
    cr.elements[0].position, cr.elements[0].color = 0.0, schatten_lin
    cr.elements[1].position, cr.elements[1].color = float(kante), lin
    if stufen >= 3:
        mitte = tuple((a + b) / 2 for a, b in zip(schatten_lin[:3], lin[:3])) + (1.0,)
        el = cr.elements.new(float(kante) * 0.45)
        el.color = mitte
    nt.links.new(diff.outputs['BSDF'], s2r.inputs['Shader'])
    nt.links.new(s2r.outputs['Color'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], em.inputs['Color'])
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    return m


def kontur(obj, dicke=0.02, farbe='#141414'):
    """Umriss-Linie (Inverted Hull): Solidify mit gedrehten Normalen. Die zur Kamera zeigende Hülle ist durchsichtig
    (Backfacing), sichtbar bleibt nur der Rand. Funktioniert in EEVEE und Cycles."""
    m = _neues_material(f'Kontur_{farbe}')
    nt = m.node_tree
    nt.nodes.clear()
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = farbe_lin(farbe)
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    lp = nt.nodes.new('ShaderNodeLightPath')
    nicht_kamera = nt.nodes.new('ShaderNodeMath')
    nicht_kamera.operation = 'SUBTRACT'
    nicht_kamera.inputs[0].default_value = 1.0
    oder = nt.nodes.new('ShaderNodeMath')
    oder.operation = 'MAXIMUM'
    durch = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    # durchsichtig, wenn Rückseite ODER kein Kamerastrahl (sonst wirft die Hülle in Cycles Schatten aufs Objekt)
    nt.links.new(lp.outputs['Is Camera Ray'], nicht_kamera.inputs[1])
    nt.links.new(geo.outputs['Backfacing'], oder.inputs[0])
    nt.links.new(nicht_kamera.outputs['Value'], oder.inputs[1])
    nt.links.new(oder.outputs['Value'], mix.inputs['Fac'])
    nt.links.new(em.outputs['Emission'], mix.inputs[1])
    nt.links.new(durch.outputs['BSDF'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    m.use_backface_culling = True
    if hasattr(m, 'use_transparent_shadow'):
        m.use_transparent_shadow = True
    obj.data.materials.append(m)
    mod = obj.modifiers.new('Kontur', 'SOLIDIFY')
    mod.thickness = -abs(dicke)
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.material_offset = len(obj.data.materials) - 1
    return mod


# ---------------------------------------------------------------- Import (Modelle, Figuren, Bewegungen)

def _import_neu(fn):
    vorher = set(bpy.data.objects)
    fn()
    return [o for o in bpy.data.objects if o not in vorher]


def _normalisieren(neu, name, pos, hoehe, skala, rot):
    wurzel = leer(name, (0, 0, 0))
    for o in neu:
        if o.parent is None:
            o.parent = wurzel
    bpy.context.view_layer.update()
    if hoehe:
        ecken = [o.matrix_world @ Vector(c) for o in neu if o.type == 'MESH' for c in o.bound_box]
        if ecken:
            zmin, zmax = min(v.z for v in ecken), max(v.z for v in ecken)
            mx = (min(v.x for v in ecken) + max(v.x for v in ecken)) / 2
            my = (min(v.y for v in ecken) + max(v.y for v in ecken)) / 2
            f = float(hoehe) / max(1e-6, zmax - zmin)
            for o in neu:
                if o.parent == wurzel:
                    o.location = (o.location - Vector((mx, my, zmin))) * f
                    o.scale = o.scale * f
    wurzel.location = pos
    wurzel.rotation_euler = _grad(rot)
    wurzel.scale = (skala,) * 3
    bpy.context.view_layer.update()
    return wurzel


def glb_import(pfad, pos=(0, 0, 0), hoehe=None, skala=1.0, rot=(0, 0, 0), name=None):
    """Lädt .glb/.gltf (Poly Haven, Sketchfab, Tripo, Meshy) unter ein Leerobjekt. hoehe: auf diese Höhe in Metern
    bringen, Unterkante auf den Boden, mittig. Liefert das Leerobjekt (zum Bewegen)."""
    p = asset(pfad, 'models')
    neu = _import_neu(lambda: bpy.ops.import_scene.gltf(filepath=str(p)))
    if not neu:
        raise SystemExit(f'FEHLER: In {p} keine Objekte gefunden.')
    return _normalisieren(neu, name or p.stem, pos, hoehe, skala, rot)


def _fbx_laden(p):
    if hasattr(bpy.ops.import_scene, 'fbx'):
        try:
            return bpy.ops.import_scene.fbx(filepath=str(p))
        except (AttributeError, RuntimeError):
            pass
    return bpy.ops.wm.fbx_import(filepath=str(p))  # neuer FBX-Import (ab 4.5)


def fbx_import(pfad, pos=(0, 0, 0), hoehe=None, skala=1.0, rot=(0, 0, 0), name=None):
    """Lädt .fbx (z. B. Mixamo-Figur 'With Skin'). Wie glb_import. Bewegungen danach mit aktion_legen()."""
    p = asset(pfad, 'models')
    neu = _import_neu(lambda: _fbx_laden(p))
    if not neu:
        raise SystemExit(f'FEHLER: In {p} keine Objekte gefunden.')
    return _normalisieren(neu, name or p.stem, pos, hoehe, skala, rot)


def armatur_finden(wurzel):
    """Erste Armatur (Skelett) unter einem Objekt."""
    stapel = [wurzel]
    while stapel:
        o = stapel.pop(0)
        if o.type == 'ARMATURE':
            return o
        stapel += list(o.children)
    return None


def aktion_aus_datei(pfad, name=None):
    """Lädt eine Bewegung (Mixamo 'Without Skin' .fbx oder .glb mit Animation) und liefert die Aktion.
    Die mitgeladenen Objekte werden wieder aus der Szene genommen. Gleiche Knochennamen nötig (Mixamo zu Mixamo)."""
    p = asset(pfad, 'models')
    vorher_akt = set(bpy.data.actions)
    neu = _import_neu(lambda: (_fbx_laden(p) if p.suffix.lower() == '.fbx'
                               else bpy.ops.import_scene.gltf(filepath=str(p))))
    akt = [a for a in bpy.data.actions if a not in vorher_akt]
    for o in neu:
        bpy.data.objects.remove(o, do_unlink=True)
    if not akt:
        raise SystemExit(f'FEHLER: In {p} keine Bewegung gefunden.')
    akt = max(akt, key=lambda a: a.frame_range[1] - a.frame_range[0])
    akt.use_fake_user = True
    if name:
        akt.name = name
    return akt


def aktion_legen(armatur, aktion, t, wiederholen=1.0, tempo=1.0, ueberblenden=0.2):
    """Legt eine Bewegung ab Sekunde t auf das Skelett (NLA-Streifen, jede Bewegung auf eigener Spur,
    spätere überdecken frühere, letzte Pose bleibt stehen). ueberblenden in Sekunden."""
    ad = armatur.animation_data or armatur.animation_data_create()
    ad.action = None
    spur = ad.nla_tracks.new()
    spur.name = f'{aktion.name}_{t:.2f}s'
    streifen = spur.strips.new(aktion.name, sek(t), aktion)
    if hasattr(streifen, 'action_slot') and streifen.action_slot is None and len(getattr(aktion, 'slots', [])):
        streifen.action_slot = aktion.slots[0]
    streifen.repeat = float(wiederholen)
    streifen.scale = 1.0 / float(tempo)
    streifen.blend_in = float(ueberblenden) * _ZUSTAND['fps']
    streifen.extrapolation = 'HOLD_FORWARD' if len(ad.nla_tracks) > 1 else 'HOLD'
    return streifen


# ---------------------------------------------------------------- Partikel

def partikel_einfach(ort=(0, 0, 0), t=0.0, anzahl=60, art='funken', seed=1, farben=None, groesse=None,
                     tempo=None, dauer=1.0, richtung=(0, 0, 1), streuung=70.0, schwerkraft=9.81, leuchten=12.0,
                     name=None):
    """Partikel-Ausbruch bei Sekunde t an ort. art 'funken' (leuchtende Striche, fliegen in Flugrichtung, fallen,
    verglühen) oder 'konfetti' (bunte Plättchen, taumeln, segeln langsam). Die Bahnen werden vorab mit seed
    berechnet und als Keyframes gesetzt: gleiche Eingabe = gleiches Bild, jedes Bild einzeln renderbar.
    streuung: Öffnungswinkel um richtung in Grad. Liefert die Sammlung."""
    fps = _ZUSTAND['fps']
    rnd = random.Random(seed)
    konfetti = art == 'konfetti'
    farben = farben or (['#ff4d6d', '#ffd166', '#06d6a0', '#118ab2', '#f78c6b', '#ffffff'] if konfetti
                        else ['#fff4d6', '#ffd27a', '#ff9a3c'])
    groesse = groesse or (0.07 if konfetti else 0.06)
    tempo = tempo or (5.0 if konfetti else 6.0)
    sammlung = bpy.data.collections.new(name or f'Partikel_{art}_{seed}')
    bpy.context.scene.collection.children.link(sammlung)
    netze = []
    for i, fa in enumerate(farben):
        me = bpy.data.meshes.new(f'{sammlung.name}_{i}')
        if konfetti:
            a, b = groesse, groesse * 0.55
            me.from_pydata([(-a / 2, -b / 2, 0), (a / 2, -b / 2, 0), (a / 2, b / 2, 0), (-a / 2, b / 2, 0)], [],
                           [(0, 1, 2, 3)])
            mat = material_pbr(fa, rauheit=0.45, emission=fa, emission_staerke=0.35, name=f'Konfetti_{fa}')
        else:  # schmaler Strich entlang -Z (zeigt nach der Ausrichtung in Flugrichtung)
            d, l = groesse * 0.12, groesse
            v = [(-d, -d, 0), (d, -d, 0), (d, d, 0), (-d, d, 0), (-d, -d, -l), (d, -d, -l), (d, d, -l), (-d, d, -l)]
            f = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
            me.from_pydata(v, [], f)
            mat = material_emission(fa, leuchten, name=f'Funke_{fa}')
        me.materials.append(mat)
        netze.append(me)
    achse = Vector(richtung).normalized()
    hilf = Vector((1, 0, 0)) if abs(achse.z) > 0.9 else Vector((0, 0, 1))
    u = achse.cross(hilf).normalized()
    w = achse.cross(u).normalized()
    ort = Vector(ort)
    dt = 1.0 / fps
    for n in range(anzahl):
        obj = bpy.data.objects.new(f'{sammlung.name}_{n:03d}', netze[n % len(netze)])
        sammlung.objects.link(obj)
        # Startrichtung im Kegel um die Achse
        theta = math.radians(streuung) * math.sqrt(rnd.random())
        phi = rnd.uniform(0, 2 * math.pi)
        dirv = (achse * math.cos(theta) + (u * math.cos(phi) + w * math.sin(phi)) * math.sin(theta)).normalized()
        v = dirv * tempo * rnd.uniform(0.55, 1.0)
        pos = ort + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * groesse
        leben = dauer * rnd.uniform(0.55, 1.0)
        geburt = t + rnd.uniform(0, 0.04)
        drall = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * (14 if konfetti else 0)
        rot = Vector((rnd.uniform(0, 6.3), rnd.uniform(0, 6.3), rnd.uniform(0, 6.3)))
        wind = rnd.uniform(0, 6.3)
        zeiten, lx, ly, lz, rx, ry, rz, sk = [], [], [], [], [], [], [], []
        schritte = max(2, int(leben * fps))
        prev = None
        for s in range(schritte + 1):
            alter = s * dt
            zeiten.append(geburt + alter)
            lx.append(pos.x)
            ly.append(pos.y)
            lz.append(pos.z)
            if konfetti:
                e = rot + drall * alter
                rx.append(e.x)
                ry.append(e.y)
                rz.append(e.z)
                luft = 3.2  # starker Luftwiderstand: Konfetti segelt
                v += (Vector((math.sin(wind + alter * 5) * 1.5, 0, -schwerkraft * 0.6)) - v * luft) * dt
            else:
                if v.length > 1e-4:
                    quat = v.normalized().to_track_quat('-Z', 'Y')
                    q = quat.to_euler('XYZ', prev) if prev is not None else quat.to_euler('XYZ')
                else:
                    q = prev
                prev = q
                rx.append(q.x)
                ry.append(q.y)
                rz.append(q.z)
                v += (Vector((0, 0, -schwerkraft)) - v * 1.2) * dt
            pos = pos + v * dt
            rest = 1 - alter / leben
            sk.append(1.0 if konfetti and rest > 0.25 else max(0.0, rest / (0.25 if konfetti else 1.0)) ** 0.7)
        zeiten.append(zeiten[-1] + dt)
        for liste in (lx, ly, lz, rx, ry, rz):
            liste.append(liste[-1])
        sk.append(0.0)
        if geburt > 1.5 / fps:  # vor der Geburt unsichtbar
            zeiten.insert(0, geburt - dt)
            for liste in (lx, ly, lz, rx, ry, rz):
                liste.insert(0, liste[0])
            sk.insert(0, 0.0)
        for i, werte in enumerate((lx, ly, lz)):
            kurve(obj, 'location', zeiten, werte, index=i)
        for i, werte in enumerate((rx, ry, rz)):
            kurve(obj, 'rotation_euler', zeiten, werte, index=i)
        for i in range(3):
            kurve(obj, 'scale', zeiten, sk, index=i)
    return sammlung
