"""Gemeinsame Teile für ms check und ms setup (Bereich Setup).

  pruefungen(stufen, kurz=False) -> list[dict]   alle Prüfungen der Stufen, parallel ausgeführt
  STUFEN, SCHLUESSEL                              Stufen und bekannte Schlüssel in <arbeit>/.env
  installbefehl(id) -> str                        Installationsbefehl fürs aktuelle System
  claude_ordner(), venv_python(), blender_pfad(), heim_aussen()
  arbeitsordner_anlegen(pfad) -> dict             Ordner, PROFIL.md, LERNLOG.md, .env, .claude/settings.json (nur wenn fehlend)
  settings_inhalt(heim, arbeit, cfg) -> dict      erlaubte Befehle für Claude Code im Arbeitsordner
  config_setzen(**werte)                          Schlüssel in HEIM/config.json setzen (Rest bleibt)
Jede Prüfung: {id, name, stufe, pflicht, ok, version, detail, installieren}
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import _ms

SYSTEM = _ms.SYSTEM  # 'Darwin' | 'Windows' | 'Linux'
STUFEN = ['basis', 'analyse', '3d-web', 'blender', 'sound', 'ki']
NODE_MIN = 22          # HyperFrames verlangt Node >= 22 (package.json engines)
PY_MIN = (3, 9)
BLENDER_MIN = (4, 2)   # EEVEE Next ab 4.2

# Name in <arbeit>/.env, wofür, Stufe. Werte werden NIE ausgegeben, nur gesetzt/fehlt.
SCHLUESSEL = [
    ('APIFY_TOKEN', 'Vorlagen von Instagram/TikTok über Apify laden (kostet)', 'analyse'),
    ('ELEVENLABS_API_KEY', 'Stimme und Sound-Effekte über ElevenLabs (kostet)', 'sound'),
    ('FREESOUND_API_KEY', 'Sound-Suche auf Freesound (gratis)', 'sound'),
    ('TRIPO_API_KEY', '3D-Figuren aus Text oder Bild über Tripo (kostet)', 'blender'),
]

# pip-Name -> Importname, wo die beiden abweichen
IMPORT_NAMEN = {
    'pillow': 'PIL', 'faster-whisper': 'faster_whisper', 'scikit-image': 'skimage', 'scikit-learn': 'sklearn',
    'opencv-python': 'cv2', 'opencv-python-headless': 'cv2', 'pyyaml': 'yaml', 'beautifulsoup4': 'bs4',
    'python-dotenv': 'dotenv', 'imageio-ffmpeg': 'imageio_ffmpeg', 'open-clip-torch': 'open_clip',
    'pytesseract': 'pytesseract', 'kokoro-onnx': 'kokoro_onnx',
    'pyobjc-framework-vision': 'Vision', 'pyobjc-framework-quartz': 'Quartz',
}

WHISPER_MODELLE = {  # Name -> (Datei, Bytes laut huggingface.co, geprüft 20.10.2026)
    'small': ('ggml-small.bin', 487601967),
    'turbo': ('ggml-large-v3-turbo.bin', 1624555275),
    'turbo-q5': ('ggml-large-v3-turbo-q5_0.bin', 574041195),
}
WHISPER_URL = 'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/'

BREW_INSTALL = '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'


# ---------------------------------------------------------------- Pfade

def heim_aussen() -> str:
    """HEIM als Pfad mit Schrägstrichen (Windows: C:/Users/…), so wie Agenten ihn aufrufen."""
    return _ms.HEIM.as_posix()


def ms_befehl() -> str:
    return f'"{heim_aussen()}/ms"'


def claude_ordner() -> Path:
    if os.environ.get('CLAUDE_CONFIG_DIR'):
        return Path(os.path.expanduser(os.environ['CLAUDE_CONFIG_DIR']))
    if _ms.config().get('claude_ordner'):
        return Path(os.path.expanduser(_ms.config()['claude_ordner']))
    if _ms.HEIM.name == 'motion-studio':
        return _ms.HEIM.parent
    return Path.home() / '.claude'


def venv_python(heim: Path | None = None) -> Path | None:
    heim = heim or _ms.HEIM
    for p in (heim / '.venv' / 'bin' / 'python', heim / '.venv' / 'Scripts' / 'python.exe'):
        if p.exists():
            return p
    return None


def im_venv() -> bool:
    try:
        return Path(sys.prefix).resolve() == (_ms.HEIM / '.venv').resolve()
    except OSError:
        return False


def kurz_pfad(p) -> str:
    s = str(p)
    h = str(Path.home())
    return '~' + s[len(h):] if s.startswith(h) else s


def blender_pfad() -> Path | None:
    """Sucht Blender: config.json "blender", MS_BLENDER, übliche Orte je System, dann PATH."""
    kandidaten = [_ms.config().get('blender'), os.environ.get('MS_BLENDER')]
    if SYSTEM == 'Darwin':
        kandidaten += ['/Applications/Blender.app/Contents/MacOS/Blender',
                       str(Path.home() / 'Applications/Blender.app/Contents/MacOS/Blender')]
    elif SYSTEM == 'Windows':
        for basis in {os.environ.get('ProgramFiles', 'C:/Program Files'), 'C:/Program Files'}:
            treffer = glob.glob(os.path.join(basis, 'Blender Foundation', 'Blender*', 'blender.exe'))
            kandidaten += sorted(treffer, key=lambda t: [int(x) for x in re.findall(r'\d+', t)] or [0], reverse=True)
    else:
        kandidaten += ['/snap/bin/blender', '/usr/bin/blender', '/usr/local/bin/blender']
    kandidaten.append(shutil.which('blender'))
    for k in kandidaten:
        if k and Path(os.path.expanduser(str(k))).exists():
            return Path(os.path.expanduser(str(k)))
    return None


# ---------------------------------------------------------------- Hilfen

def lauf(liste, timeout=25, env=None) -> tuple[int, str]:
    """Startet ein Programm still. (Code, stdout+stderr). Code 127 = fehlt, 124 = Zeitüberschreitung."""
    prog = shutil.which(str(liste[0])) or (str(liste[0]) if Path(str(liste[0])).exists() else None)
    if not prog:
        return 127, ''
    umg = dict(os.environ, **(env or {}))
    try:
        r = subprocess.run([prog] + [str(x) for x in liste[1:]], capture_output=True, text=True, timeout=timeout,
                           env=umg, stdin=subprocess.DEVNULL, encoding='utf-8', errors='replace')
        return r.returncode, (r.stdout or '') + (r.stderr or '')
    except subprocess.TimeoutExpired:
        return 124, ''
    except OSError as e:
        return 126, str(e)


def version_aus(text: str, muster: str = r'(\d+(?:\.\d+)+)') -> str | None:
    m = re.search(muster, text or '')
    return m.group(1) if m else None


def version_tupel(v: str | None) -> tuple:
    return tuple(int(x) for x in re.findall(r'\d+', v or '')[:3])


def anforderungen(datei: Path) -> list[str]:
    """pip-Namen aus einer requirements-Datei (ohne Versionen und Kommentare)."""
    if not datei.exists():
        return []
    namen = []
    for zeile in datei.read_text(encoding='utf-8').splitlines():
        zeile = zeile.split('#', 1)[0].strip()
        if not zeile or zeile.startswith('-'):
            continue
        if ';' in zeile:                                   # Plattform-Marker (z. B. sys_platform == "darwin")
            marker = zeile.split(';', 1)[1]
            m = re.search(r'sys_platform\s*==\s*["\'](\w+)["\']', marker)
            if m and m.group(1) != sys.platform:
                continue
        namen.append(re.split(r'[<>=!~\[; ]', zeile, maxsplit=1)[0].strip().lower())
    return [n for n in namen if n]


def paket_da(pip_name: str) -> tuple[bool, str | None]:
    import importlib.util
    try:
        from importlib import metadata
    except ImportError:  # pragma: no cover
        metadata = None
    imp = IMPORT_NAMEN.get(pip_name, pip_name.replace('-', '_'))
    try:
        da = importlib.util.find_spec(imp) is not None
    except (ImportError, ValueError):
        da = False
    ver = None
    if da and metadata:
        try:
            ver = metadata.version(pip_name)
        except Exception:
            ver = None
    return da, ver


# ---------------------------------------------------------------- Installationsbefehle

def _cmd(mac=None, win=None, linux=None, alle=None) -> dict:
    return {'Darwin': mac or alle, 'Windows': win or alle, 'Linux': linux or alle}


INSTALL = {
    'ffmpeg': _cmd('brew install ffmpeg', 'winget install -e --id Gyan.FFmpeg', 'sudo apt install -y ffmpeg'),
    'python': _cmd('brew install python@3.12', 'winget install -e --id Python.Python.3.12',
                   'sudo apt install -y python3 python3-venv python3-pip'),
    'node': _cmd('brew install node', 'winget install -e --id OpenJS.NodeJS.LTS',
                 'curl -fsSL https://deb.nodesource.com/setup_22.x -o nodesource_setup.sh && sudo -E bash nodesource_setup.sh '
                 '&& sudo apt install -y nodejs'),
    'hyperframes': _cmd(alle='npx --yes hyperframes --version'),
    'chrome': _cmd(alle='npx --yes hyperframes browser ensure'),
    'yt-dlp': _cmd('brew install yt-dlp', 'winget install -e --id yt-dlp.yt-dlp',
                   'sudo apt install -y pipx && pipx install yt-dlp'),
    'whisper-cli': _cmd('brew install whisper-cpp', None, None),
    'tmux': _cmd('brew install tmux', None, 'sudo apt install -y tmux'),
    'tesseract': _cmd('brew install tesseract', 'winget install -e --id UB-Mannheim.TesseractOCR',
                      'sudo apt install -y tesseract-ocr'),
    'git': _cmd('xcode-select --install', 'winget install -e --id Git.Git', 'sudo apt install -y git'),
    'claude': _cmd('curl -fsSL https://claude.ai/install.sh | bash', 'winget install -e --id Anthropic.ClaudeCode',
                   'curl -fsSL https://claude.ai/install.sh | bash'),
    'blender': _cmd('brew install --cask blender', 'winget install -e --id BlenderFoundation.Blender',
                    'sudo snap install blender --classic'),
}


def installbefehl(pid: str) -> str:
    ms = ms_befehl()
    if pid == 'pakete' or pid.startswith('paket:'):
        return f'{ms} setup venv'
    if pid.startswith('ki:'):
        return f'{ms} setup venv --ki --ja'
    if pid == 'hf-skills':
        return f'{ms} setup hyperframes-skills --ja'
    if pid == 'transkription':
        if SYSTEM == 'Darwin':
            return f'brew install whisper-cpp && {ms} setup whisper-modell turbo --ja'
        return f'{ms} setup venv --whisper'
    if pid == 'whisper-modell':
        return f'{ms} setup whisper-modell turbo --ja'
    if pid == 'arbeitsordner':
        return f'{ms} setup arbeitsordner "{kurz_pfad(_ms.arbeit())}"'
    if pid == 'profil':
        return 'Skill motion-setup (Interview), danach steht "setup: fertig" in PROFIL.md'
    if pid == 'sound-bibliothek':
        return 'Skill motion-sound-bibliothek'
    if pid.startswith('schluessel:'):
        return f'in {kurz_pfad(_ms.arbeit() / ".env")} eintragen oder: {ms} setup schluessel {pid.split(":", 1)[1]}'
    if pid == 'ffprobe':
        pid = 'ffmpeg'
    return (INSTALL.get(pid) or {}).get(SYSTEM) or ''


# ---------------------------------------------------------------- Einzelprüfungen

def _p(pid, name, stufe, pflicht, ok, version=None, detail='', installieren=None):
    return {'id': pid, 'name': name, 'stufe': stufe, 'pflicht': pflicht, 'ok': bool(ok), 'version': version,
            'detail': detail, 'installieren': '' if ok else (installieren if installieren is not None else installbefehl(pid))}


def p_programm(pid, name, stufe, pflicht, args, muster=r'(\d+(?:\.\d+)+)', prog=None):
    code, out = lauf([prog or pid] + args)
    if code == 127:
        return _p(pid, name, stufe, pflicht, False, detail='nicht gefunden')
    v = version_aus(out, muster)
    if pid == 'yt-dlp' and v:                             # YouTube ändert laufend etwas: ältere yt-dlp-Versionen brechen mit 403 ab
        import datetime
        try:
            alter = (datetime.date.today() - datetime.date(*[int(x) for x in v.split('.')[:3]])).days
        except ValueError:
            alter = 0
        if alter > 90:
            upd = {'Darwin': 'brew upgrade yt-dlp', 'Windows': 'winget upgrade -e --id yt-dlp.yt-dlp'}.get(_ms.SYSTEM, 'pipx upgrade yt-dlp')
            return _p(pid, name, stufe, pflicht, False, v, f'{alter} Tage alt, YouTube-Downloads brechen dann oft mit 403 ab', installieren=upd)
    return _p(pid, name, stufe, pflicht, True, v, '' if v or code == 0 else f'antwortet mit Code {code}')


def p_python():
    v = '.'.join(str(x) for x in sys.version_info[:3])
    ok = sys.version_info[:2] >= PY_MIN
    wo = 'venv' if im_venv() else ('System, venv fehlt' if not venv_python() else 'System')
    return _p('python', 'Python', 'basis', True, ok, v, f'{wo}, braucht >= {PY_MIN[0]}.{PY_MIN[1]}' if not ok else wo)


def p_venv():
    vp = venv_python()
    return _p('venv', 'Python-Umgebung (.venv)', 'basis', False, vp is not None,
              detail=kurz_pfad(vp) if vp else 'fehlt', installieren=f'{ms_befehl()} setup venv')


def p_pakete(datei: Path, stufe: str, pflicht: bool, praefix: str):
    aus = []
    for name in anforderungen(datei):
        da, ver = paket_da(name)
        aus.append(_p(f'{praefix}{name}', f'Paket {name}', stufe, pflicht, da, ver, '' if da else 'nicht installiert'))
    return aus


def p_node():
    code, out = lauf(['node', '-v'])
    if code == 127:
        return _p('node', 'Node.js', 'basis', True, False, detail='nicht gefunden')
    v = version_aus(out)
    ok = version_tupel(v)[:1] >= (NODE_MIN,)
    return _p('node', 'Node.js', 'basis', True, ok, v, '' if ok else f'zu alt, HyperFrames braucht >= {NODE_MIN}')


def p_hyperframes():
    code, out = lauf(['npx', '--no-install', 'hyperframes', '--version'], timeout=40)
    if code == 127:
        return _p('hyperframes', 'HyperFrames (npx)', 'basis', True, False, detail='npx fehlt (kommt mit Node.js)',
                  installieren=installbefehl('node'))
    v = version_aus(out.strip().splitlines()[-1] if out.strip() else '')
    if code != 0 or not v:
        return _p('hyperframes', 'HyperFrames (npx)', 'basis', True, False, detail='noch nicht geladen')
    return _p('hyperframes', 'HyperFrames (npx)', 'basis', True, True, v)


HF_KERN = ['hyperframes', 'hyperframes-core']


def hf_skills_stand(mit_check: bool = True, timeout: int = 40) -> dict:
    """Stand der HyperFrames-Skills im Claude-Ordner von Motion-Studio (claude_ordner()/skills), für ms check und
    ms setup hyperframes-skills gleich. "hyperframes skills check" sucht ohne --dir selbst (immer ~/.claude, auch bei
    CLAUDE_CONFIG_DIR), deshalb geht der Ordner ausdrücklich mit. Rückgabe: ordner, fehlen (Kern), anzahl,
    check (summary von skills check oder None), check_ort (Ordner, den skills check geprüft hat)."""
    sk = claude_ordner() / 'skills'
    aus = {'ordner': sk, 'fehlen': [k for k in HF_KERN if not (sk / k / 'SKILL.md').exists()],
           'anzahl': len(list(sk.glob('hyperframes*/SKILL.md'))) if sk.exists() else 0, 'check': None, 'check_ort': None}
    if mit_check and sk.exists():
        code, out = lauf(['npx', '--no-install', 'hyperframes', 'skills', 'check', '--json', '--dir', str(sk)],
                         timeout=timeout, env={'CLAUDE_CONFIG_DIR': str(claude_ordner())})
        if code in (0, 1) and '{' in out:   # Code 1 heißt bei skills check: Updates verfügbar
            try:
                d = json.loads(out[out.index('{'):])
                aus['check'], aus['check_ort'] = d.get('summary') or {}, d.get('location')
            except (ValueError, AttributeError):
                pass
    return aus


def p_hf_skills(kurz: bool):
    st = hf_skills_stand(mit_check=not kurz)
    sk = st['ordner']
    if st['fehlen']:
        return _p('hf-skills', 'HyperFrames-Skills', 'basis', True, False,
                  detail=f'fehlt in {kurz_pfad(sk)}: {", ".join(st["fehlen"])}')
    detail = f'{st["anzahl"]} hyperframes-Skills in {kurz_pfad(sk)}'
    s = st['check'] or {}
    if s.get('outdated'):
        detail += f', {s["outdated"]} veraltet (Update: {ms_befehl()} setup hyperframes-skills --ja)'
    return _p('hf-skills', 'HyperFrames-Skills', 'basis', True, True, detail=detail)


def p_chrome(stufe='basis'):
    code, out = lauf(['npx', '--no-install', 'hyperframes', 'browser', 'path'], timeout=40)
    zeilen = [z.strip() for z in out.strip().splitlines() if z.strip()]
    pfad = zeilen[-1] if zeilen else ''
    ok = code == 0 and bool(pfad) and Path(pfad).exists()
    return _p('chrome', 'Chrome für HyperFrames', stufe, True, ok, detail=kurz_pfad(pfad) if ok else 'nicht geladen')


def p_transkription():
    modell = _ms._whisper_modell()  # nur lesen
    cli = shutil.which('whisper-cli')
    fw, fw_ver = paket_da('faster-whisper')
    if cli and modell:
        groesse = modell.stat().st_size / 1e9
        code, out = lauf(['whisper-cli', '--version'])
        v = version_aus(out, r'version:?\s*(\d+(?:\.\d+)+)')
        return _p('transkription', 'Transkription', 'basis', True, True, v,
                  f'whisper-cli + {modell.name} ({groesse:.1f} GB)')
    if fw:
        return _p('transkription', 'Transkription', 'basis', True, True, fw_ver, 'faster-whisper (Modell lädt beim ersten Lauf)')
    if cli and not modell:
        return _p('transkription', 'Transkription', 'basis', True, False, detail='whisper-cli da, Modell fehlt',
                  installieren=installbefehl('whisper-modell'))
    return _p('transkription', 'Transkription', 'basis', True, False,
              detail='weder whisper-cli + Modell noch faster-whisper')


def p_arbeitsordner():
    a = _ms.arbeit()
    ok = a.is_dir() and os.access(str(a), os.W_OK)
    return _p('arbeitsordner', 'Arbeitsordner', 'basis', True, ok, detail=kurz_pfad(a) + ('' if ok else ' fehlt'))


def p_profil():
    p = _ms.arbeit() / 'PROFIL.md'
    if not p.exists():
        return _p('profil', 'PROFIL.md', 'basis', True, False, detail='fehlt')
    text = p.read_text(encoding='utf-8', errors='replace')
    m = re.search(r'^setup:\s*(\S+)', text, re.M)
    stand = m.group(1) if m else 'unbekannt'
    return _p('profil', 'PROFIL.md', 'basis', True, stand == 'fertig', detail=f'setup: {stand}')


def p_blender(kurz: bool):
    pfad = blender_pfad()
    if not pfad:
        return _p('blender', 'Blender', 'blender', True, False, detail='nicht gefunden (optionale Beta-Spur)')
    v = None
    if not kurz:
        code, out = lauf([str(pfad), '--version'], timeout=60)
        v = version_aus(out, r'Blender\s+(\d+(?:\.\d+)+)')
    ok = v is None or version_tupel(v)[:2] >= BLENDER_MIN
    detail = kurz_pfad(pfad) + ('' if ok else f', empfohlen ab {BLENDER_MIN[0]}.{BLENDER_MIN[1]}')
    return _p('blender', 'Blender', 'blender', True, ok, v, detail)


def p_sound():
    a = _ms.arbeit() / 'sounds'
    kat = _ms.json_lesen(a / 'katalog.json', None)
    n = 0
    if isinstance(kat, list):
        n = len(kat)
    elif isinstance(kat, dict):
        for k in ('sounds', 'eintraege', 'dateien', 'items'):
            if isinstance(kat.get(k), list):
                n = len(kat[k])
                break
        else:
            n = len(kat)
    if n:
        return _p('sound-bibliothek', 'Sound-Bibliothek', 'sound', True, True, detail=f'{n} Sounds im Katalog')
    dateien = 0
    if (a / 'files').exists():
        for _wurzel, _ordner, namen in os.walk(a / 'files'):
            dateien += sum(1 for x in namen if x.lower().endswith(('.wav', '.mp3', '.ogg', '.flac', '.aif', '.aiff', '.m4a')))
            if dateien > 5000:
                break
    detail = f'{dateien} Dateien, aber kein Katalog' if dateien else 'leer'
    return _p('sound-bibliothek', 'Sound-Bibliothek', 'sound', True, False, detail=detail)


def p_schluessel():
    aus = []
    for name, wofuer, stufe in SCHLUESSEL:
        gesetzt = bool(_ms.env(name))  # Wert wird nie ausgegeben
        aus.append(_p(f'schluessel:{name}', name, stufe, False, gesetzt, detail=('gesetzt' if gesetzt else 'fehlt') + f', {wofuer}'))
    return aus


# ---------------------------------------------------------------- Zusammenstellen

# Basis-Prüfungen, die eine Stufe zusätzlich braucht (zählen dort mit, angezeigt bei --stufe <x>)
AUCH = {
    'analyse': ['ffmpeg', 'ffprobe', 'yt-dlp', 'transkription', 'paket:numpy', 'paket:pillow'],
    '3d-web': ['node', 'hyperframes', 'hf-skills', 'chrome'],
    'blender': ['ffmpeg'],
    'sound': ['ffmpeg', 'paket:numpy', 'paket:scipy'],
    'ki': ['python', 'venv'],
}


def pruefungen(stufen: list[str], kurz: bool = False) -> list[dict]:
    """Alle Prüfungen der gewünschten Stufen (die Basis läuft immer mit, sie ist das Fundament).
    Langsame Aufrufe laufen parallel, Gesamtzeit ca. 3 bis 5 s. Jede Prüfung bekommt 'stufen' (alle Stufen, für die sie zählt)."""
    aufgaben = []

    def auf(fn, *args):
        aufgaben.append((fn, args))

    auf(p_programm, 'ffmpeg', 'ffmpeg', 'basis', True, ['-version'], r'version\s+n?(\d+(?:\.\d+)*)')
    auf(p_programm, 'ffprobe', 'ffprobe', 'basis', True, ['-version'], r'version\s+n?(\d+(?:\.\d+)*)')
    auf(p_python)
    auf(p_venv)
    auf(p_node)
    auf(p_hyperframes)
    auf(p_hf_skills, kurz)
    auf(p_chrome)
    auf(p_programm, 'yt-dlp', 'yt-dlp', 'basis', True, ['--version'], r'(\d{4}\.\d+\.\d+)')
    auf(p_transkription)
    auf(p_programm, 'git', 'git', 'basis', True, ['--version'])
    auf(p_programm, 'claude', 'Claude Code', 'basis', False, ['--version'])
    if SYSTEM != 'Windows':
        auf(p_programm, 'tmux', 'tmux', 'basis', False, ['-V'], r'tmux\s+(\S+)')
    auf(p_arbeitsordner)
    auf(p_profil)
    if 'analyse' in stufen:
        auf(p_programm, 'tesseract', 'tesseract (Texterkennung)', 'analyse', False, ['--version'])
    if 'blender' in stufen:
        auf(p_blender, kurz)

    with ThreadPoolExecutor(max_workers=8) as pool:
        laeufe = [pool.submit(fn, *args) for fn, args in aufgaben]
        ergebnis = [f.result() for f in laeufe]

    pos = next((i for i, p in enumerate(ergebnis) if p['id'] == 'venv'), len(ergebnis) - 1) + 1
    ergebnis[pos:pos] = p_pakete(_ms.HEIM / 'requirements.txt', 'basis', True, 'paket:')
    if 'sound' in stufen:
        ergebnis.append(p_sound())
    if 'ki' in stufen:
        ergebnis += p_pakete(_ms.HEIM / 'requirements-ki.txt', 'ki', True, 'ki:')
    for p in p_schluessel():
        if p['stufe'] in stufen:
            ergebnis.append(p)
    for p in ergebnis:
        p['stufen'] = [p['stufe']] + [s for s, ids in AUCH.items() if p['id'] in ids and s in stufen]
    return ergebnis


def stufe_stand(liste: list[dict], stufe: str) -> dict:
    """Zusammenfassung einer Stufe: ok (alle Pflicht-Prüfungen ok), fehlt_pflicht, fehlt_optional."""
    teil = [p for p in liste if stufe in p.get('stufen', [p['stufe']])]
    fp = [p for p in teil if p['pflicht'] and not p['ok']]
    fo = [p for p in teil if not p['pflicht'] and not p['ok']]
    return {'stufe': stufe, 'ok': not fp, 'fehlt_pflicht': fp, 'fehlt_optional': fo, 'pruefungen': teil}


# ---------------------------------------------------------------- Konfiguration und Arbeitsordner

def config_setzen(**werte) -> dict:
    cfg = _ms.config()
    cfg.update({k: v for k, v in werte.items() if v is not None})
    _ms.json_schreiben(_ms.HEIM / 'config.json', cfg)
    return cfg


def _posix_regel(p: Path) -> str:
    """Pfad für Read/Edit-Regeln: //Users/… bzw. unter Windows //c/Users/… (Claude Code normalisiert so)."""
    s = p.as_posix()
    m = re.match(r'^([A-Za-z]):/(.*)$', s)
    if m:
        s = f'/{m.group(1).lower()}/{m.group(2)}'
    return '/' + s


def settings_inhalt(heim: Path, arbeit: Path, cfg: Path) -> dict:
    heim_a = heim.as_posix()
    erlaubt = [f'Bash({heim_a}/ms *)']
    if SYSTEM == 'Windows':
        erlaubt.append(f'Bash({_posix_regel(heim)[1:]}/ms *)')
    erlaubt += ['Bash(ffmpeg *)', 'Bash(ffprobe *)', 'Bash(npx hyperframes *)', 'Bash(yt-dlp *)',
                'Bash(whisper-cli *)', 'Bash(tmux *)',
                f'Read({_posix_regel(arbeit)}/**)', f'Edit({_posix_regel(arbeit)}/**)',
                f'Read({_posix_regel(heim)}/**)', f'Read({_posix_regel(cfg)}/skills/**)']   # motion-* und HyperFrames-Skills
    env_regel = f'{_posix_regel(arbeit)}/.env'
    return {'permissions': {'allow': erlaubt, 'deny': [f'Read({env_regel})', f'Edit({env_regel})']}}


ENV_VORLAGE = """# Motion-Studio: Schlüssel für bezahlte oder angemeldete Dienste.
# Nur hier eintragen, nie in andere Dateien. Claude liest diese Datei nicht (gesperrt in .claude/settings.json),
# die Werkzeuge lesen sie selbst. Eintragen: NAME=wert (ohne Leerzeichen um das =).
# Alles ist optional. "ms check" zeigt nur gesetzt/fehlt.
#
# APIFY_TOKEN=            Vorlagen von Instagram/TikTok laden (kostet pro Lauf, immer erst nach Ja)
# ELEVENLABS_API_KEY=     Stimme und Sound-Effekte (kostet je nach Plan)
# FREESOUND_API_KEY=      Sound-Suche auf freesound.org (gratis, Key: freesound.org/apiv2/apply)
# TRIPO_API_KEY=          3D-Figuren aus Text oder Bild (kostet pro Figur)
"""


def arbeitsordner_anlegen(pfad) -> dict:
    """Legt den Arbeitsordner an. Vorhandene Dateien des Nutzers bleiben unangetastet."""
    a = Path(os.path.expanduser(str(pfad))).resolve()
    angelegt = []
    for teil in ('kanaele', 'folgen', 'vorlagen/videos', 'vorlagen/transkripte', 'sounds/files', 'live', '.claude'):
        (a / teil).mkdir(parents=True, exist_ok=True)
    for ziel, vorlage in (('PROFIL.md', 'PROFIL-START.md'), ('LERNLOG.md', 'LERNLOG-START.md')):
        q = _ms.HEIM / 'vorlagen' / vorlage
        if not (a / ziel).exists() and q.exists():
            text = q.read_text(encoding='utf-8').replace('__ARBEIT__', a.as_posix()).replace('__HEIM__', heim_aussen())
            (a / ziel).write_text(text, encoding='utf-8')
            angelegt.append(ziel)
    if not (a / '.env').exists():
        (a / '.env').write_text(ENV_VORLAGE, encoding='utf-8')
        try:
            os.chmod(a / '.env', 0o600)
        except OSError:
            pass
        angelegt.append('.env')
    st = a / '.claude' / 'settings.json'
    if not st.exists():
        _ms.json_schreiben(st, settings_inhalt(_ms.HEIM, a, claude_ordner()))
        angelegt.append('.claude/settings.json')
    return {'pfad': a, 'angelegt': angelegt}
