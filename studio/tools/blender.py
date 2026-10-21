"""Blender-Spur: Blender finden und messen, 3D-Szenen headless rendern, als Video in HyperFrames einbetten.
  ms blender check [--json] [--ohne-benchmark] [--cycles]
  ms blender render <szene.py|beispiel> [--folge <id> --szene <sid>] [--von 1 --bis N] [--dauer 4] [--fps 30]
                    [--aufloesung 1080x1920|540x960] [--engine eevee|cycles] [--samples 64] [--entwurf]
                    [--stichprobe 6] [--ausgabe <ordner>] [--weiter] [--blend] [--seed 1] [-- eigene Szenen-Argumente]
  ms blender komposition <folge> <sid> [--dauer S] [--neu] [--lint]
                    schreibt build/compositions/<sid>.html (ein Platzhalter von "ms szenen" wird ersetzt, eine echte
                    Komposition nur mit --neu, die alte wandert nach _ueberholt/). Gibt es sie schon: mit --lint nur prüfen
Beispiele:
  ms blender check                                    Version, Sekunden pro Bild, Hochrechnung 20-s-Reel
  ms blender render beispiel --stichprobe 6 --entwurf          Beispielszene: 6 Bilder, Kontaktbogen
  ms blender render szene.py --folge 2026-10-20-probe --szene s2 --entwurf --dauer 3     Entwurf 540x960
  ms blender render szene.py --folge 2026-10-20-probe --szene s2 -- --text "Hallo"       voll 1080x1920
  ms blender komposition 2026-10-20-probe s2           build/compositions/s2.html mit dem Video
  ms blender komposition 2026-10-20-probe s2 --lint    vorhandene Komposition lassen, nur hyperframes lint im build-Ordner
Ergebnis mit --folge: Video folgen/<id>/build/assets/video/<sid>.mp4 (+ .json mit Messwerten),
Kontaktbogen folgen/<id>/snapshots/<sid>_blender.jpg, Bilder und Log in folgen/<id>/blender/<sid>/.
--entwurf: 540x960, wenige Samples, ohne Bewegungsunschärfe. --stichprobe N: nur N Bilder gleichmäßig verteilt.
Blender wird gesucht in: Umgebung MS_BLENDER, config.json "blender", PATH, Standardorte
(Mac /Applications/Blender.app, Windows C:\\Program Files\\Blender Foundation\\Blender*\\blender.exe,
Linux /usr/bin/blender, /snap/bin/blender, ~/blender*/blender). Mindestens Blender 4.2."""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import _ms

LIB = _ms.HEIM / 'blender'
BEISPIEL = LIB / 'beispiel_szene.py'
MIN_VERSION = (4, 2)
REEL_SEK, REEL_FPS = 20, 30


# ---------------------------------------------------------------- Blender finden

def _version_aus_pfad(p: str):
    m = re.search(r'(\d+)\.(\d+)', p)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def kandidaten() -> list:
    k = [os.environ.get('MS_BLENDER'), _ms.config().get('blender'), shutil.which('blender')]
    heim = Path.home()
    if _ms.SYSTEM == 'Darwin':
        for basis in ('/Applications', str(heim / 'Applications')):
            apps = sorted(glob.glob(f'{basis}/Blender*.app'), key=_version_aus_pfad, reverse=True)
            k += [f'{a}/Contents/MacOS/Blender' for a in apps]
    elif _ms.SYSTEM == 'Windows':
        for basis in (os.environ.get('ProgramFiles', r'C:\Program Files'), r'C:\Program Files'):
            k += sorted(glob.glob(basis + r'\Blender Foundation\Blender*\blender.exe'), key=_version_aus_pfad, reverse=True)
        k += sorted(glob.glob(str(heim / 'AppData/Local/Programs/Blender Foundation/Blender*/blender.exe')),
                    key=_version_aus_pfad, reverse=True)
    else:
        k += ['/usr/bin/blender', '/usr/local/bin/blender', '/snap/bin/blender']
        k += sorted(glob.glob(str(heim / 'blender*/blender')) + glob.glob('/opt/blender*/blender'),
                    key=_version_aus_pfad, reverse=True)
    gesehen, aus = set(), []
    for x in k:
        if x and x not in gesehen:
            gesehen.add(x)
            aus.append(x)
    return aus


def blender_version(pfad):
    try:
        r = subprocess.run([str(pfad), '--version'], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r'Blender (\d+)\.(\d+)(?:\.(\d+))?', r.stdout or '')
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)) if m else None


def blender_finden(pflicht=True):
    """Liefert (pfad, version) des ersten lauffähigen Blenders, sonst None oder Abbruch mit Anleitung."""
    for k in kandidaten():
        if Path(k).exists():
            v = blender_version(k)
            if v:
                return Path(k), v
    if pflicht:
        raise SystemExit('FEHLER: Blender nicht gefunden. Installieren: https://www.blender.org/download/ '
                         '(4.2 LTS oder neuer; Mac: in /Applications ziehen; Linux: snap install blender --classic). '
                         'Oder Pfad setzen: MS_BLENDER=/pfad/zu/blender. Danach: ms blender check')
    return None


# ---------------------------------------------------------------- Blender starten und mitlesen

def _befehl(blender, szene, szene_args):
    vorne = ['nice', '-n', '10'] if _ms.SYSTEM != 'Windows' and shutil.which('nice') else []
    pfad_expr = f'import sys; sys.path.insert(0, {str(LIB)!r})'
    return vorne + [str(blender), '-b', '--factory-startup', '--python-exit-code', '1',
                    '--python-expr', pfad_expr, '-P', str(szene), '--'] + [str(x) for x in szene_args]


def blender_lauf(blender, szene, szene_args, log_datei, fortschritt=None, umgebung=None, still=False):
    """Startet Blender headless, schreibt alles ins Log, liest MS-Zeilen mit. Liefert dict mit zeiten, ergebnis,
    fehlertext, code, gesamt_s."""
    env = dict(os.environ)
    env.update({'MS_BLENDER_LIB': str(LIB), 'MS_ARBEIT': str(_ms.arbeit())})
    env.update(umgebung or {})
    log_datei = Path(log_datei)
    log_datei.parent.mkdir(parents=True, exist_ok=True)
    zeiten, ergebnis, warnungen, start_zeile = {}, {}, [], None
    t0 = time.time()
    with open(log_datei, 'w', encoding='utf-8') as log:
        proc = subprocess.Popen(_befehl(blender, szene, szene_args), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding='utf-8', errors='replace', bufsize=1, env=env)
        for zeile in proc.stdout:
            log.write(zeile)
            z = zeile.strip()
            if z.startswith('MSFRAME '):
                _, f, s = z.split()[:3]
                zeiten[int(f)] = float(s)
                if fortschritt:
                    fortschritt(int(f), float(s), zeiten, start_zeile)
            elif z.startswith('MSSTART '):
                start_zeile = [int(x) for x in z.split()[1:]]
            elif z.startswith('MSERGEBNIS '):
                ergebnis = json.loads(z[len('MSERGEBNIS '):])
            elif z.startswith('MSWARNUNG '):
                warnungen.append(z[10:])
                if not still:
                    print(f'  Warnung: {z[10:]}')
            elif z.startswith('MSINFO ') and not still:
                print(f'  {z[7:]}')
        code = proc.wait()
    fehlertext = ''
    if code != 0 or not ergebnis:
        text = log_datei.read_text(encoding='utf-8', errors='replace').splitlines()
        idx = max((i for i, z in enumerate(text) if z.startswith('Traceback')), default=None)
        auszug = text[idx:idx + 30] if idx is not None else [z for z in text if 'rror' in z][-12:] or text[-15:]
        fehlertext = '\n'.join(auszug)
    return {'zeiten': zeiten, 'ergebnis': ergebnis, 'warnungen': warnungen, 'code': code,
            'fehlertext': fehlertext, 'gesamt_s': round(time.time() - t0, 2)}


def _warm(zeiten: dict):
    """Zeiten ohne das erste Bild (Shader kompilieren)."""
    werte = [zeiten[k] for k in sorted(zeiten)]
    return werte[1:] if len(werte) > 1 else werte


# ---------------------------------------------------------------- check

def check(a):
    gefunden = blender_finden(pflicht=False)
    aus = {'gefunden': bool(gefunden), 'gesucht': kandidaten(), 'zeit': _ms.jetzt()}
    if not gefunden:
        aus['hinweis'] = 'https://www.blender.org/download/ (4.2 LTS oder neuer), dann ms blender check'
        if a.json:
            print(json.dumps(aus, ensure_ascii=False, indent=1))
        else:
            print('Blender: FEHLT. Gesucht in:\n  ' + '\n  '.join(aus['gesucht']) + f'\nInstallieren: {aus["hinweis"]}')
        return 1
    pfad, v = gefunden
    aus.update({'pfad': str(pfad), 'version': '.'.join(map(str, v)), 'version_ok': v[:2] >= MIN_VERSION})
    if not a.json:
        print(f'Blender {aus["version"]}: {pfad}' + ('' if aus['version_ok'] else '  (ZU ALT, mindestens 4.2 LTS)'))
    if not a.ohne_benchmark:
        aus['benchmark'] = benchmark(pfad, a.cycles, still=a.json)
        _ms.json_schreiben(_ms.arbeit() / 'live' / 'blender-check.json', aus)
    if a.json:
        print(json.dumps(aus, ensure_ascii=False, indent=1))
    return 0 if aus['version_ok'] else 1


def benchmark(blender, mit_cycles=False, still=False):
    """Beispielszene: 6 Bilder EEVEE 540x960 (64 Samples, wie im fertigen Render) und 3 Bilder 1080x1920.
    Das erste Bild jedes Laufs kompiliert Shader und zählt nicht. Hochrechnung: 20-s-Reel = 600 Bilder 1080x1920."""
    tmp = _ms.arbeit() / 'blender-tests' / '_benchmark'
    laeufe = [('eevee_540', ['--aufloesung', '540x960', '--engine', 'eevee', '--samples', '64', '--bilder', '30,40,45,50,55,60']),
              ('eevee_1080', ['--aufloesung', '1080x1920', '--engine', 'eevee', '--samples', '64', '--bilder', '30,45,60'])]
    if mit_cycles:
        laeufe.append(('cycles_540', ['--aufloesung', '540x960', '--engine', 'cycles', '--samples', '64', '--bilder', '30,45,60']))
    erg = {}
    for name, argv in laeufe:
        if not still:
            print(f'  Messe {name} …', flush=True)
        r = blender_lauf(blender, BEISPIEL, argv + ['--ausgabe', str(tmp / name), '--dauer', '3'], tmp / f'{name}.log',
                         still=still)
        if r['code'] != 0 or not r['zeiten']:
            raise SystemExit(f'FEHLER: Benchmark {name} abgebrochen.\n{r["fehlertext"]}\nLog: {tmp / f"{name}.log"}')
        warm = _warm(r['zeiten'])
        erg[name] = {'s_pro_bild': round(statistics.median(warm), 3), 'erstes_bild_s': r['zeiten'][min(r['zeiten'])],
                     'start_bis_ende_s': r['gesamt_s'], 'bilder': len(r['zeiten'])}
    s1080 = erg['eevee_1080']['s_pro_bild']
    erg['reel_20s_1080_eevee_min'] = round((s1080 * REEL_SEK * REEL_FPS + erg['eevee_1080']['erstes_bild_s']) / 60, 1)
    erg['entwurf_3s_540_min'] = round((erg['eevee_540']['s_pro_bild'] * 0.4 * 90 + erg['eevee_540']['erstes_bild_s']) / 60, 1)
    if mit_cycles:
        sc = erg['cycles_540']['s_pro_bild'] * 3.5  # 4x Pixel, Rauschfilter skaliert nicht ganz linear: Schätzung
        erg['cycles_1080_s_pro_bild_geschaetzt'] = round(sc, 1)
        erg['reel_20s_1080_cycles_min_geschaetzt'] = round(sc * REEL_SEK * REEL_FPS / 60, 0)
    try:
        last = os.getloadavg()[0]
        erg['systemlast'] = round(last, 1)
    except (AttributeError, OSError):
        pass
    if not still:
        e5, e1 = erg['eevee_540'], erg['eevee_1080']
        print(f'  EEVEE 540x960, 64 Samples:   {e5["s_pro_bild"]:.2f} s/Bild (erstes Bild {e5["erstes_bild_s"]:.1f} s Shader)')
        print(f'  EEVEE 1080x1920, 64 Samples: {e1["s_pro_bild"]:.2f} s/Bild (erstes Bild {e1["erstes_bild_s"]:.1f} s)')
        print(f'  Hochrechnung 20-s-Reel 1080x1920 EEVEE: ca. {erg["reel_20s_1080_eevee_min"]} Min '
              '(Beispielszene; dichte Szenen länger, geschätzt 2-5x: am ersten Entwurf messen)')
        if mit_cycles:
            print(f'  Cycles 540x960, 64 Samples: {erg["cycles_540"]["s_pro_bild"]:.2f} s/Bild, 1080x1920 geschätzt '
                  f'{erg["cycles_1080_s_pro_bild_geschaetzt"]} s/Bild, 20-s-Reel ca. {erg["reel_20s_1080_cycles_min_geschaetzt"]:.0f} Min')
        if erg.get('systemlast', 0) > os.cpu_count():
            print(f'  Achtung: Rechner war beim Messen ausgelastet (Last {erg["systemlast"]}), Werte eher zu hoch.')
    return erg


# ---------------------------------------------------------------- render

def _aufloesung(text):
    try:
        w, h = (int(x) for x in text.lower().split('x'))
    except ValueError:
        raise SystemExit(f'FEHLER: --aufloesung "{text}" ungültig, Beispiel 1080x1920.')
    if w % 2 or h % 2:
        raise SystemExit('FEHLER: Breite und Höhe müssen gerade sein (Videoformat yuv420p).')
    return w, h


def _bogen_aus_bildern(bilder, ziel, fps, titel, spalten=6, breite=270):
    """Kontaktbogen direkt aus PNG-Bildern (für Stichproben ohne Video)."""
    from PIL import Image, ImageDraw
    ims = [Image.open(b).convert('RGB') for b, _ in bilder]
    w0, h0 = ims[0].size
    hoehe = round(breite * h0 / w0)
    zeilen = (len(ims) + spalten - 1) // spalten
    bogen = Image.new('RGB', (min(spalten, len(ims)) * breite, 34 + zeilen * (hoehe + 22)), (20, 20, 20))
    zeichne = ImageDraw.Draw(bogen)
    zeichne.text((8, 7), titel, fill=(255, 255, 255), font=_ms._schrift(20))
    for i, (im, (_, f)) in enumerate(zip(ims, bilder)):
        x, y = (i % spalten) * breite, 34 + (i // spalten) * (hoehe + 22)
        bogen.paste(im.resize((breite, hoehe)), (x, y + 22))
        zeichne.text((x + 6, y + 2), f'{(f - 1) / fps:.2f}s  #{f}', fill=(255, 220, 90), font=_ms._schrift(16))
    Path(ziel).parent.mkdir(parents=True, exist_ok=True)
    bogen.save(ziel, quality=88)
    return Path(ziel)


def _verschieben_ueberholt(datei: Path, ordner: Path):
    if datei.exists():
        ordner.mkdir(parents=True, exist_ok=True)
        ziel = ordner / f'{datei.stem}-{time.strftime("%Y%m%d-%H%M%S")}{datei.suffix}'
        datei.replace(ziel)
        return ziel
    return None


def render(a, szene_args):
    blender, v = blender_finden()
    szene = BEISPIEL if a.szene == 'beispiel' else Path(a.szene).expanduser()
    if not szene.exists():
        raise SystemExit(f'FEHLER: Szenenskript {szene} fehlt.')
    szene = szene.resolve()
    aufl = a.aufloesung or ('540x960' if a.entwurf or a.stichprobe else '1080x1920')
    w, h = _aufloesung(aufl)
    folge = None
    if a.folge:
        folge = _ms.ziel_pfad(a.folge)
        if not (folge / 'STATUS.json').exists():
            raise SystemExit(f'FEHLER: {folge} ist keine Folge (STATUS.json fehlt).')
        if not a.szene_id:
            raise SystemExit('FEHLER: --szene <sid> fehlt (z. B. s3, wie in build/scenes.json).')
        arbeitsordner = folge / 'blender' / a.szene_id
        name = a.szene_id
    else:
        name = a.szene_id or szene.stem
        arbeitsordner = Path(a.ausgabe).expanduser() if a.ausgabe else _ms.arbeit() / 'blender-tests' / name
    # eigener Bilderordner je Auflösung: Entwurf und Endfassung mischen sich nie (wichtig für --weiter)
    bilder_ordner = arbeitsordner / ('stichprobe' if a.stichprobe else f'frames_{w}x{h}')
    argv = ['--aufloesung', f'{w}x{h}', '--fps', a.fps, '--engine', a.engine, '--ausgabe', bilder_ordner]
    for schalter, wert in (('--dauer', a.dauer), ('--samples', a.samples), ('--seed', a.seed), ('--von', a.von),
                           ('--bis', a.bis)):
        if wert is not None:
            argv += [schalter, wert]
    if a.entwurf:
        argv.append('--entwurf')
    if a.weiter:
        argv.append('--weiter')
    if a.blend:
        argv += ['--blend', arbeitsordner / f'{name}.blend']
    if a.stichprobe:
        # Gesamtzahl erst nach dem Szenenstart bekannt: Szene einmal nur bauen lassen
        probe = blender_lauf(blender, szene, argv + ['--nur-bauen'] + szene_args, arbeitsordner / 'bauen.log',
                             still=True)
        if probe['code'] != 0:
            _abbruch(folge, name, szene, probe, arbeitsordner / 'bauen.log')
        n = probe['ergebnis']['frames_gesamt']
        k = max(1, min(a.stichprobe, n))
        liste = sorted({1 + round(i * (n - 1) / max(1, k - 1)) for i in range(k)}) if k > 1 else [1 + n // 2]
        argv += ['--bilder', ','.join(map(str, liste))]
    argv += szene_args
    ziel_txt = _ms.ziel_name(folge) if folge else None
    _ms.log(f'Blender rendert {name} ({w}x{h}, {a.engine}{", Entwurf" if a.entwurf else ""}'
            f'{f", Stichprobe {a.stichprobe}" if a.stichprobe else ""})', ziel=ziel_txt)
    print(f'Blender {".".join(map(str, v))} rendert {szene.name} -> {bilder_ordner} ({w}x{h}, {a.engine})')
    log_datei = arbeitsordner / 'render.log'
    gemeldet = {'viertel': 0}

    def fortschritt(f, s, zeiten, start):
        n_ges = start[2] if start and len(start) > 2 else None
        fertig = len(zeiten)
        if fertig == 1:
            print(f'  Bild {f}: {s:.1f} s (erstes Bild, Shader kompilieren)', flush=True)
            return
        if not n_ges:
            return
        schritt = max(1, n_ges // 10)
        if fertig % schritt == 0 or fertig == n_ges:
            warm = _warm(zeiten)
            mittel = sum(warm) / len(warm)
            rest = (n_ges - fertig) * mittel
            print(f'  {fertig}/{n_ges} Bilder, {mittel:.2f} s/Bild, noch ca. {rest / 60:.1f} Min', flush=True)
            viertel = int(4 * fertig / n_ges)
            if folge and viertel > gemeldet['viertel'] and viertel < 4:
                gemeldet['viertel'] = viertel
                _ms.log(f'Blender {name}: {fertig}/{n_ges} Bilder, noch ca. {rest / 60:.0f} Min', ziel=ziel_txt)

    r = blender_lauf(blender, szene, argv, log_datei, fortschritt,
                     {'MS_FOLGE': str(folge or ''), 'MS_SZENE': name})
    if r['code'] != 0 or not r['ergebnis']:
        _abbruch(folge, name, szene, r, log_datei)
    erg = r['ergebnis']
    fps = erg['fps']
    liste = erg.get('bilder') or list(range(erg['von'], erg['bis'] + 1))
    fehlend = [f for f in liste if not (bilder_ordner / f'f_{f:04d}.png').exists()]
    if fehlend:
        raise SystemExit(f'FEHLER: {len(fehlend)} Bilder fehlen (z. B. {fehlend[:5]}). Log: {log_datei}')
    warm = _warm(r['zeiten'])
    s_bild = round(statistics.median(warm), 3) if warm else None
    if not warm:
        print('  Alle Bilder waren schon da (--weiter), nichts neu gerendert.')
    messwerte = {'szene': name, 'skript': str(szene), 'blender': erg['blender'], 'aufloesung': f'{w}x{h}', 'fps': fps,
                 'engine': erg['engine'], 'samples': erg['samples'], 'entwurf': erg['entwurf'], 'bilder': len(liste),
                 'frames_gesamt': erg['frames_gesamt'], 's_pro_bild': s_bild, 'erstes_bild_s': r['zeiten'].get(liste[0]),
                 'gesamt_s': r['gesamt_s'], 'zeit': _ms.jetzt(), 'argumente': [str(x) for x in szene_args]}
    titel = f'{name}  {w}x{h}  {erg["engine"].replace("BLENDER_", "")} {erg["samples"]}spp  {s_bild or 0:.2f} s/Bild'
    if a.stichprobe:
        bogen_ziel = (folge / 'snapshots' / f'{name}_blender_stichprobe.jpg') if folge else arbeitsordner / 'stichprobe.jpg'
        bogen = _bogen_aus_bildern([(bilder_ordner / f'f_{f:04d}.png', f) for f in liste], bogen_ziel, fps,
                                   titel + '  STICHPROBE')
        print(f'Stichprobe fertig: {len(liste)} Bilder, {s_bild or 0:.2f} s/Bild, gesamt {r["gesamt_s"]:.0f} s')
        print(f'  Kontaktbogen (ansehen!): {bogen}')
        _ms.log(f'Blender {name}: Stichprobe {len(liste)} Bilder, {s_bild or 0:.2f} s/Bild', ziel=ziel_txt)
        return
    # Video bauen
    voll = erg['von'] == 1 and erg['bis'] == erg['frames_gesamt']
    if folge and voll:
        video = folge / 'build' / 'assets' / 'video' / f'{name}.mp4'
    else:
        video = arbeitsordner / (f'{name}.mp4' if voll else f'{name}_{erg["von"]}-{erg["bis"]}.mp4')
    alt = _verschieben_ueberholt(video, arbeitsordner / '_ueberholt')
    video.parent.mkdir(parents=True, exist_ok=True)
    tmp = video.with_name('.' + video.name)
    _ms.befehl(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-framerate', fps, '-start_number', erg['von'],
                '-i', bilder_ordner / 'f_%04d.png', '-frames:v', len(liste), '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                '-crf', '18', '-preset', 'medium', '-movflags', '+faststart', '-f', 'mp4', tmp])
    tmp.replace(video)
    if a.alpha:
        webm = video.with_suffix('.webm')
        _verschieben_ueberholt(webm, arbeitsordner / '_ueberholt')
        _ms.befehl(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-framerate', fps, '-start_number', erg['von'],
                    '-i', bilder_ordner / 'f_%04d.png', '-frames:v', len(liste), '-c:v', 'libvpx-vp9',
                    '-pix_fmt', 'yuva420p', '-b:v', '0', '-crf', '30', '-row-mt', '1', webm])
        messwerte['alpha_video'] = str(webm)
    info = _ms.probe(video)
    k = 12 if info['dauer'] >= 2 else 6
    zeiten = [i * (info['dauer'] - 1 / fps) / (k - 1) for i in range(k)]
    bogen_ziel = (folge / 'snapshots' / f'{name}_blender.jpg') if folge and voll else arbeitsordner / f'{video.stem}_bogen.jpg'
    bogen = _ms.kontaktbogen(video, zeiten, bogen_ziel, spalten=6, breite=270,
                             titel=titel + ('  ENTWURF' if erg['entwurf'] else ''))
    messwerte.update({'video': str(video), 'dauer': info['dauer'], 'kontaktbogen': str(bogen)})
    _ms.json_schreiben(video.with_suffix('.json'), messwerte)
    notiz = (f'Blender {name}: {len(liste)} Bilder {w}x{h} {erg["engine"].replace("BLENDER_", "")}, {s_bild or 0:.2f} s/Bild, '
             f'{r["gesamt_s"] / 60:.1f} Min{" (Entwurf)" if erg["entwurf"] else ""}')
    if folge:
        _ms.status_setzen(folge, None, notiz)
    else:
        _ms.log(notiz)
    print(f'Fertig: {notiz}')
    if r['warnungen']:
        print(f'  {len(r["warnungen"])} Warnung(en), siehe oben und {log_datei}')
    if alt:
        print(f'  Altes Video verschoben: {alt}')
    print(f'  Video: {video} ({info["dauer"]:.2f} s)')
    print(f'  Kontaktbogen (ansehen!): {bogen}')
    if folge and voll:
        print(f'  Einbetten: ms blender komposition {folge.name} {name}')


def _abbruch(folge, name, szene, r, log_datei):
    zeilen = r['fehlertext'].strip().splitlines() or ['?']
    treffer = [z for z in zeilen if re.match(r'^(\w+(Error|Exception)\b|FEHLER)', z) and 'script failed' not in z]
    kurz = (treffer or zeilen)[-1][:200]
    _ms.log(f'Blender {name} abgebrochen: {kurz}', ziel=_ms.ziel_name(folge) if folge else None, art='fehler')
    raise SystemExit(f'FEHLER: Blender-Szene {szene.name} abgebrochen (Code {r["code"]}).\n'
                     f'{r["fehlertext"]}\nGanzes Log: {log_datei}')


# ---------------------------------------------------------------- komposition

KOMPOSITION = """<!doctype html>
<html lang="de"><head><meta charset="UTF-8" /></head><body><template>
<style>
  #{id}-root {{ position: absolute; inset: 0; overflow: hidden; background: {hg}; }}
  #{id}-video {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
  #{id}-ebene {{ position: absolute; inset: 0; pointer-events: none; }}
</style>
<div id="{id}-root" data-composition-id="{id}" data-width="{w}" data-height="{h}" data-duration="{dur}">
  <!-- 3D aus Blender ({quelle}). Ton kommt aus dem Mix, deshalb muted. Neu rendern: ms blender render ... --szene {id} -->
  <video id="{id}-video" src="assets/video/{datei}" muted playsinline data-start="0" data-duration="{dur}" data-track-index="0"></video>
  <!-- 2D-Ebenen über dem 3D-Bild (Text, Pfeile, Zahlen): hier als Kinder von #{id}-ebene einfügen, ids mit "{id}-" beginnen. -->
  <div id="{id}-ebene"></div>
</div>
<script>
(function () {{
  const ID = "{id}", DUR = {dur};
  const tl = gsap.timeline({{ paused: true }});
  tl.set({{}}, {{}}, DUR);
  // 2D-Animationen hier, Zeiten in Sekunden ab Szenenbeginn, Beispiel:
  // tl.fromTo("#{id}-titel", {{ opacity: 0, y: 40 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: "power3.out" }}, 1.2);
  window.__timelines[ID] = tl;
}})();
</script>
</template></body></html>
"""


def _lint(build: Path, index: Path) -> None:
    """hyperframes lint im build-Ordner (gleiche Version wie ms snap und ms render)."""
    if not index.exists():
        print('  Lint übersprungen: build/index.html fehlt (die Regie führt ms szenen <folge> aus).')
        return
    import _bau
    fehler, warn, text = _bau.lint(build)
    if fehler:
        print('\n'.join(z for z in text.splitlines() if '✗' in z or 'error' in z.lower()) or text[-1500:])
        raise SystemExit(f'FEHLER: hyperframes lint meldet {fehler} Fehler (siehe oben).')
    print(f'  hyperframes lint: 0 Fehler, {warn} Warnungen')


def komposition(a):
    folge = _ms.ziel_pfad(a.folge)
    build = folge / 'build'
    sid = a.sid
    ziel = build / 'compositions' / f'{sid}.html'
    index = build / 'index.html'
    platzhalter = ziel.exists() and 'data-platzhalter="1"' in ziel.read_text(encoding='utf-8', errors='replace')
    if a.lint and ziel.exists() and not a.neu and not platzhalter:
        print(f'{ziel} gibt es schon, bleibt unverändert. Prüfe nur.')
        _lint(build, index)
        return
    mp4 = build / 'assets' / 'video' / f'{sid}.mp4'
    webm = mp4.with_suffix('.webm')
    mess = _ms.json_lesen(mp4.with_suffix('.json'), {}) or {}
    video = webm if mess.get('alpha_video') and webm.exists() else mp4
    if not video.exists():
        raise SystemExit(f'FEHLER: {mp4} fehlt. Erst: ms blender render <szene.py> --folge {folge.name} --szene {sid}')
    info = _ms.probe(mp4)
    szenen = _ms.json_lesen(build / 'scenes.json', []) or []
    eintrag = next((s for s in szenen if isinstance(s, dict) and s.get('id') == sid), None)
    dur = a.dauer or (eintrag or {}).get('dur') or info['dauer']
    w, h = 1080, 1920
    if index.exists():
        m = re.search(r'data-composition-id="[^"]+"[^>]*?data-width="(\d+)"[^>]*?data-height="(\d+)"',
                      index.read_text(encoding='utf-8'))
        if m:
            w, h = int(m.group(1)), int(m.group(2))
    if ziel.exists() and not a.neu and not platzhalter:
        raise SystemExit(f'FEHLER: {ziel} gibt es schon (vielleicht mit 2D-Ebenen). Nur prüfen: --lint. '
                         f'Neu schreiben: --neu (verschiebt die alte nach _ueberholt/).')
    if ziel.exists() and not platzhalter:
        alt = _verschieben_ueberholt(ziel, folge / '_ueberholt' / 'compositions')  # außerhalb von build/ (lint)
        print(f'  Alte Komposition verschoben: {alt}')
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(KOMPOSITION.format(id=sid, w=w, h=h, dur=f'{float(dur):.2f}', datei=video.name,
                                       hg='transparent' if video.suffix == '.webm' else '#000',
                                       quelle=Path(mess.get('skript', '?')).name), encoding='utf-8')
    print(f'OK {ziel} (Dauer {float(dur):.2f} s, Video {info["dauer"]:.2f} s, {info["breite"]}x{info["hoehe"]})')
    if info['dauer'] + 0.5 / max(1, info['fps']) < float(dur):
        print(f'  WARNUNG: Video ({info["dauer"]:.2f} s) kürzer als die Szene ({float(dur):.2f} s). Länger rendern: --dauer {float(dur):.2f}')
    if mess.get('entwurf'):
        print('  Hinweis: Das Video ist ein ENTWURF (540x960, wenige Samples). Vor dem Endrender voll rendern.')
    if not eintrag:
        print(f'  Hinweis: {sid} steht nicht in build/scenes.json. Eintrag mit "art": "blender" ergänzen, dann ms szenen.')
    if platzhalter:
        print('  Platzhalter von ms szenen ersetzt.')
    if a.lint:
        _lint(build, index)


# ---------------------------------------------------------------- main

def main():
    argv = sys.argv[1:]
    szene_args = []
    if '--' in argv:
        i = argv.index('--')
        argv, szene_args = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='was', required=True)
    c = sub.add_parser('check', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    c.add_argument('--json', action='store_true')
    c.add_argument('--ohne-benchmark', action='store_true')
    c.add_argument('--cycles', action='store_true', help='zusätzlich Cycles messen (dauert länger)')
    r = sub.add_parser('render', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    r.add_argument('szene')
    r.add_argument('--folge')
    r.add_argument('--szene', dest='szene_id')
    r.add_argument('--von', type=int)
    r.add_argument('--bis', type=int)
    r.add_argument('--dauer', type=float)
    r.add_argument('--fps', type=int, default=30)
    r.add_argument('--aufloesung')
    r.add_argument('--engine', default='eevee', choices=['eevee', 'cycles'])
    r.add_argument('--samples', type=int)
    r.add_argument('--seed', type=int)
    r.add_argument('--entwurf', action='store_true')
    r.add_argument('--stichprobe', type=int, metavar='N')
    r.add_argument('--ausgabe')
    r.add_argument('--weiter', action='store_true', help='vorhandene Bilder nicht neu rendern')
    r.add_argument('--blend', action='store_true', help='.blend-Datei zum Öffnen in Blender mitspeichern')
    r.add_argument('--alpha', action='store_true', help='zusätzlich .webm mit Transparenz (Szene mit transparent=True)')
    k = sub.add_parser('komposition', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    k.add_argument('folge')
    k.add_argument('sid')
    k.add_argument('--dauer', type=float)
    k.add_argument('--neu', action='store_true')
    k.add_argument('--lint', action='store_true')
    a, rest = ap.parse_known_args(argv)
    if rest:
        if a.was != 'render':
            ap.error(f'unbekannt: {" ".join(rest)}')
        szene_args = rest + szene_args  # unbekannte Schalter gehen an die Szene
    if a.was == 'check':
        return check(a)
    if a.was == 'render':
        return render(a, szene_args)
    return komposition(a)


if __name__ == '__main__':
    sys.exit(main())
