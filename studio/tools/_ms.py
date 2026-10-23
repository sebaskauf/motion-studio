"""Gemeinsame Bibliothek für alle Motion-Studio-Werkzeuge (Python >= 3.9, Mac/Windows/Linux).

Pfade
  HEIM            Installationsordner (~/.claude/motion-studio), enthält tools/, vorlagen/, referenz/, dashboard/, blender/, config.json
  arbeit()        Arbeitsordner des Nutzers (Standard ~/MotionStudio, sonst config.json "arbeitsordner" oder Umgebung MS_ARBEIT)
  ziel_pfad(x)    "2026-10-20-slug" | "folgen/<id>" | "kanal:<slug>" | absoluter Pfad  ->  Ordner mit STATUS.json

Status (Vertrag mit Dashboard und Agenten, Details in ARCHITEKTUR.md)
  status_lesen(ordner) / status_setzen(ordner, phase=None, notiz=None, **felder) / alle_status()
  log(text, wer=None, ziel=None, art="info")    eine Zeile nach <arbeit>/live/events.jsonl

Video und Ton (nie ein ganzes Video roh in den RAM laden: Frames werden gestreamt)
  probe(video) -> dict(breite, hoehe, fps, dauer, frames, ton)
  frames(video, fps=None, groesse=(w, h), start=None, ende=None, grau=False) -> Generator (t, ndarray)
  frame_bei(video, t, groesse=None) -> ndarray (H, W, 3) uint8
  kontaktbogen(video, zeiten, ziel, spalten=6, breite=270, titel=None) -> Pfad (JPG mit Zeitstempeln)
  wav_aus(video, ziel, rate=16000) -> Pfad
  lufs(audio) -> float (integrierte Lautheit)
  transkribiere(audio, sprache="auto") -> {"text", "sprache", "woerter": [{"w", "s", "e"}]}

Sonstiges
  json_lesen(pfad, standard=None) / json_schreiben(pfad, daten)   (atomar)
  env(name) -> Wert aus Umgebung oder <arbeit>/.env (Werte nie ausgeben!)
  befehl(liste, ...) -> subprocess.CompletedProcess (Fehler mit lesbarer Meldung)
  jetzt() -> ISO-Zeit mit Zeitzone
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

HEIM = Path(__file__).resolve().parent.parent
SYSTEM = platform.system()  # 'Darwin' | 'Windows' | 'Linux'

FOLGE_PHASEN = ['vorlage', 'skript', 'stimme', 'storyboard', 'szenen', 'ton', 'render', 'vergleich',
                'pruefung', 'fertig', 'geplant', 'gepostet']
KANAL_PHASEN = ['vorbild', 'zerlegt', 'bibel', 'pilot', 'gemessen', 'kit', 'bereit']
# Spalten im Dashboard: Phase -> Spalte
SPALTEN = {'vorlage': 'Vorlage', 'skript': 'Skript', 'stimme': 'Stimme', 'storyboard': 'Szenen', 'szenen': 'Szenen',
           'ton': 'Szenen', 'render': 'Render', 'vergleich': 'Render', 'pruefung': 'Prüfung', 'fertig': 'Fertig',
           'geplant': 'Geplant', 'gepostet': 'Gepostet'}


# ---------------------------------------------------------------- Allgemeines

def jetzt() -> str:
    return datetime.now().astimezone().isoformat(timespec='seconds')


def json_lesen(pfad, standard=None):
    p = Path(pfad)
    if not p.exists():
        return standard
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def json_schreiben(pfad, daten) -> Path:
    p = Path(pfad)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix='.' + p.name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(daten, f, ensure_ascii=False, indent=1)
            f.write('\n')
        os.replace(tmp, p)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)                 # keine halbe .tmp-Datei liegen lassen
        raise
    return p


def befehl(liste, pruefen=True, still=True, **kw) -> subprocess.CompletedProcess:
    """Startet ein Programm. Fehlt es, gibt es eine verständliche Meldung statt eines Tracebacks."""
    prog = str(liste[0])
    if shutil.which(prog) is None and not Path(prog).exists():
        raise SystemExit(f'FEHLER: Programm "{prog}" fehlt. Einmal "ms check" ausführen, das Setup zeigt, wie es installiert wird.')
    if still:
        kw.setdefault('capture_output', True)
        kw.setdefault('text', True)
    r = subprocess.run([str(x) for x in liste], **kw)
    if pruefen and r.returncode != 0:
        fehler = (r.stderr or '')[-1500:] if still else ''
        raise SystemExit(f'FEHLER: {" ".join(str(x) for x in liste[:4])} … (Code {r.returncode})\n{fehler}')
    return r


def ytdlp() -> str:
    """yt-dlp aus HEIM/.venv (über ms setup venv immer aktuell), sonst das aus dem PATH."""
    for p in (HEIM / '.venv/bin/yt-dlp', HEIM / '.venv/Scripts/yt-dlp.exe'):
        if p.exists():
            return str(p)
    return 'yt-dlp'


def config() -> dict:
    return json_lesen(HEIM / 'config.json', {}) or {}


def arbeit() -> Path:
    a = os.environ.get('MS_ARBEIT') or config().get('arbeitsordner') or str(Path.home() / 'MotionStudio')
    return Path(os.path.expanduser(a))


def env(name: str):
    """Liest einen Schlüssel aus der Umgebung oder <arbeit>/.env. Den Wert NIE ausgeben oder loggen."""
    if os.environ.get(name):
        return os.environ[name]
    p = arbeit() / '.env'
    if p.exists():
        for zeile in p.read_text(encoding='utf-8').splitlines():
            zeile = zeile.strip()
            if zeile and not zeile.startswith('#') and '=' in zeile:
                k, v = zeile.split('=', 1)
                if k.strip() == name:
                    return v.strip().strip('"').strip("'")
    return None


# ---------------------------------------------------------------- Ziele und Status

def ziel_pfad(ziel) -> Path:
    """Folge-ID, 'folgen/<id>', 'kanal:<slug>', 'kanaele/<slug>' oder Pfad -> Ordner."""
    s = str(ziel)
    if s.startswith('kanal:'):
        return arbeit() / 'kanaele' / s.split(':', 1)[1]
    p = Path(os.path.expanduser(s))
    if p.is_absolute() or p.exists():
        return p.resolve()
    if (arbeit() / s).exists():
        return arbeit() / s
    if (arbeit() / 'folgen' / s).exists():
        return arbeit() / 'folgen' / s
    if (arbeit() / 'kanaele' / s).exists():
        return arbeit() / 'kanaele' / s
    raise SystemExit(f'FEHLER: "{s}" gibt es nicht (gesucht in {arbeit()}/folgen und /kanaele).')


def ziel_name(ordner: Path) -> str:
    ordner = Path(ordner)
    try:
        return str(ordner.resolve().relative_to(arbeit().resolve()))
    except ValueError:
        return str(ordner)


def status_lesen(ordner) -> dict:
    return json_lesen(Path(ordner) / 'STATUS.json', {}) or {}


def status_setzen(ordner, phase: str | None = None, notiz: str | None = None, **felder) -> dict:
    """Setzt die Phase (setzt 'phase' und phasen[phase]) und beliebige Felder. Felder mit Wert None werden gelöscht
    (z. B. fehler=None). Schreibt zusätzlich ein Ereignis ins Live-Log."""
    ordner = Path(ordner)
    st = status_lesen(ordner)
    if not st:
        raise SystemExit(f'FEHLER: {ordner}/STATUS.json fehlt. Erst mit "ms neu folge|kanal" anlegen.')
    erlaubt = KANAL_PHASEN if st.get('art') == 'kanal' else FOLGE_PHASEN
    if phase:
        if phase not in erlaubt:
            raise SystemExit(f'FEHLER: Phase "{phase}" unbekannt. Erlaubt: {", ".join(erlaubt)}')
        st['phase'] = phase
        st.setdefault('phasen', {})[phase] = {'zeit': jetzt(), 'notiz': notiz or ''}
    for k, v in felder.items():
        if v is None:
            st.pop(k, None)
        else:
            st[k] = v
    st['aktualisiert'] = jetzt()
    json_schreiben(ordner / 'STATUS.json', st)
    if phase or notiz:
        log(notiz or f'Phase {phase} erreicht', ziel=ziel_name(ordner), art='fertig' if phase else 'info')
    return st


def alle_status() -> list[dict]:
    """Alle Folgen und Kanäle mit Status, neueste zuerst. Jeder Eintrag bekommt '_ordner' (relativ zu arbeit())."""
    aus = []
    for teil in ('kanaele', 'folgen'):
        basis = arbeit() / teil
        if not basis.exists():
            continue
        for d in sorted(basis.iterdir(), reverse=True):
            st = status_lesen(d) if d.is_dir() else {}
            if st:
                st['_ordner'] = f'{teil}/{d.name}'
                aus.append(st)
    return aus


def log(text: str, wer: str | None = None, ziel: str | None = None, art: str = 'info') -> None:
    zeile = {'zeit': jetzt(), 'wer': wer or os.environ.get('MS_AGENT') or 'motion-studio', 'ziel': ziel,
             'art': art, 'text': text}
    p = arbeit() / 'live' / 'events.jsonl'
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'a', encoding='utf-8') as f:
        f.write(json.dumps(zeile, ensure_ascii=False) + '\n')


# ---------------------------------------------------------------- Video

_PROBE_CACHE: dict = {}


def probe(video) -> dict:
    """Eckdaten eines Videos. Gemerkt pro Datei (Pfad, Größe, Änderungszeit), weil Kontaktbögen es pro Bild brauchen."""
    try:
        st = os.stat(video)
        schluessel = (str(Path(video).resolve()), st.st_size, st.st_mtime_ns)
    except OSError:
        schluessel = None
    if schluessel and schluessel in _PROBE_CACHE:
        return dict(_PROBE_CACHE[schluessel])
    info = _probe(video)
    if schluessel:
        _PROBE_CACHE[schluessel] = dict(info)
    return info


def _probe(video) -> dict:
    r = befehl(['ffprobe', '-v', 'error', '-print_format', 'json', '-show_streams', '-show_format', str(video)])
    d = json.loads(r.stdout)
    v = next((s for s in d['streams'] if s.get('codec_type') == 'video'), None)
    a = next((s for s in d['streams'] if s.get('codec_type') == 'audio'), None)
    if not v:
        raise SystemExit(f'FEHLER: {video} hat keine Videospur.')
    zaehler, nenner = (v.get('avg_frame_rate') or v.get('r_frame_rate') or '30/1').split('/')
    fps = float(zaehler) / float(nenner or 1) if float(nenner or 1) else 30.0
    dauer = float(v.get('duration') or d['format'].get('duration') or 0)
    breite, hoehe = int(v['width']), int(v['height'])
    rot = int((v.get('tags') or {}).get('rotate', 0) or 0)
    for sd in v.get('side_data_list') or []:
        rot = int(sd.get('rotation', rot) or rot)
    if abs(rot) in (90, 270):
        breite, hoehe = hoehe, breite
    return {'breite': breite, 'hoehe': hoehe, 'fps': round(fps, 3), 'dauer': round(dauer, 3),
            'frames': int(v.get('nb_frames') or round(dauer * fps)), 'ton': a is not None}


def _rohpipe(video, vf, start=None, ende=None, pix='rgb24'):
    cmd = ['ffmpeg', '-nostdin', '-v', 'error']
    if start is not None:
        cmd += ['-ss', f'{start:.3f}']
    cmd += ['-i', str(video)]
    if ende is not None:
        cmd += ['-t', f'{max(0.0, ende - (start or 0)):.3f}']
    cmd += ['-vf', vf, '-f', 'rawvideo', '-pix_fmt', pix, '-']
    if shutil.which('ffmpeg') is None:
        raise SystemExit('FEHLER: ffmpeg fehlt. "ms check" zeigt, wie es installiert wird.')
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)


def frames(video, fps=None, groesse=None, start=None, ende=None, grau=False):
    """Streamt Frames einzeln (nie das ganze Video im RAM). groesse=(w, h); ohne Angabe Originalgröße.
    Liefert (t, array) mit t in Sekunden ab Videobeginn."""
    import numpy as np
    info = probe(video)
    w, h = groesse or (info['breite'], info['hoehe'])
    filt = []
    if fps:
        filt.append(f'fps={fps}')
    filt.append(f'scale={w}:{h}:flags=area')
    kanaele = 1 if grau else 3
    pipe = _rohpipe(video, ','.join(filt), start, ende, 'gray' if grau else 'rgb24')
    n, schritt = 0, 1.0 / (fps or info['fps'] or 30)
    groesse_b = w * h * kanaele
    try:
        while True:
            buf = pipe.stdout.read(groesse_b)
            if len(buf) < groesse_b:
                break
            arr = np.frombuffer(buf, np.uint8).reshape((h, w) if grau else (h, w, 3))
            yield (start or 0) + n * schritt, arr
            n += 1
    finally:
        pipe.stdout.close()
        pipe.kill()
        pipe.wait()


def frame_bei(video, t, groesse=None):
    import numpy as np
    info = probe(video)
    w, h = groesse or (info['breite'], info['hoehe'])
    pipe = _rohpipe(video, f'scale={w}:{h}:flags=lanczos', start=max(0.0, float(t)))
    try:
        buf = pipe.stdout.read(w * h * 3)
    finally:
        pipe.stdout.close()
        pipe.kill()
        pipe.wait()
    if len(buf) < w * h * 3:
        raise SystemExit(f'FEHLER: kein Bild bei {t:.2f} s in {video} (Dauer {info["dauer"]} s).')
    return np.frombuffer(buf, np.uint8).reshape(h, w, 3).copy()


def _schrift(groesse: int):
    from PIL import ImageFont
    for kandidat in ('/System/Library/Fonts/Supplemental/Arial.ttf', '/System/Library/Fonts/Helvetica.ttc',
                     'C:/Windows/Fonts/arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(kandidat).exists():
            try:
                return ImageFont.truetype(kandidat, groesse)
            except OSError:
                pass
    return ImageFont.load_default()


def kontaktbogen(video, zeiten, ziel, spalten=6, breite=270, titel=None) -> Path:
    """Ein Bild pro Zeitpunkt, beschriftet mit der Sekunde. Liest jedes Bild einzeln (RAM-sicher)."""
    from PIL import Image, ImageDraw
    info = probe(video)
    hoehe = round(breite * info['hoehe'] / info['breite'])
    zeiten = [min(max(0.0, float(t)), max(0.0, info['dauer'] - 0.05)) for t in zeiten]
    zeilen = (len(zeiten) + spalten - 1) // spalten
    kopf = 34 if titel else 0
    bogen = Image.new('RGB', (spalten * breite, kopf + zeilen * (hoehe + 22)), (20, 20, 20))
    zeichne = ImageDraw.Draw(bogen)
    schrift = _schrift(16)
    if titel:
        zeichne.text((8, 7), str(titel), fill=(255, 255, 255), font=_schrift(20))
    for i, t in enumerate(zeiten):
        bild = Image.fromarray(frame_bei(video, t, (breite, hoehe)))
        x, y = (i % spalten) * breite, kopf + (i // spalten) * (hoehe + 22)
        bogen.paste(bild, (x, y + 22))
        zeichne.text((x + 6, y + 2), f'{t:.2f}s', fill=(255, 220, 90), font=schrift)
    ziel = Path(ziel)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    bogen.save(ziel, quality=88)
    return ziel


# ---------------------------------------------------------------- Ton

def wav_aus(video, ziel, rate=16000) -> Path:
    befehl(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(video), '-vn', '-ac', '1', '-ar', str(rate), str(ziel)])
    return Path(ziel)


def lufs(audio) -> float:
    r = befehl(['ffmpeg', '-nostdin', '-v', 'info', '-i', str(audio), '-af', 'ebur128=framelog=quiet', '-f', 'null', '-'],
               pruefen=False)
    m = re.findall(r'I:\s+(-?[\d.]+) LUFS', r.stderr or '')
    if not m:
        raise SystemExit(f'FEHLER: Lautheit von {audio} nicht messbar.')
    return float(m[-1])


def _whisper_modell() -> Path | None:
    kandidaten = [config().get('whisper_modell'), os.environ.get('MS_WHISPER_MODELL'),
                  Path.home() / '.cache/whisper-cpp/ggml-large-v3-turbo.bin',
                  HEIM / 'modelle' / 'ggml-large-v3-turbo.bin', HEIM / 'modelle' / 'ggml-small.bin']
    for k in kandidaten:
        if k and Path(os.path.expanduser(str(k))).exists():
            return Path(os.path.expanduser(str(k)))
    return None


def transkribiere(audio, sprache: str = 'auto') -> dict:
    """Wortgenaues Transkript. Reihenfolge: whisper-cli (whisper.cpp, schnell auf Mac) -> faster-whisper (pip, überall).
    Ergebnis: {"text", "sprache", "woerter": [{"w": "Wort", "s": 1.23, "e": 1.51}]}"""
    audio = Path(audio)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / 'a.wav'
        wav_aus(audio, wav)
        modell = _whisper_modell()
        if shutil.which('whisper-cli') and modell:
            basis = Path(tmp) / 'out'
            befehl(['whisper-cli', '-m', modell, '-l', sprache, '-ojf', '-ml', '1', '-sow', '-of', basis, wav])
            d = json.loads((basis.with_suffix('.json')).read_text(encoding='utf-8', errors='replace'))
            woerter = []
            for seg in d.get('transcription', []):
                for tok in seg.get('tokens', []):
                    txt = tok.get('text', '')
                    if not txt.strip() or txt.strip().startswith('[_'):
                        continue
                    s, e = tok['offsets']['from'] / 1000, tok['offsets']['to'] / 1000
                    if txt.startswith(' ') or not woerter:
                        woerter.append({'w': txt.strip(), 's': s, 'e': e})
                    else:
                        woerter[-1]['w'] += txt.strip()
                        woerter[-1]['e'] = e
            spr = (d.get('result') or {}).get('language') or sprache
            return {'text': ' '.join(w['w'] for w in woerter), 'sprache': spr, 'woerter': woerter}
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise SystemExit('FEHLER: Keine Transkription installiert (whisper-cli + Modell oder faster-whisper). '
                             '"ms check" zeigt, was fehlt.')
        m = WhisperModel(config().get('faster_whisper_modell', 'small'), device='auto', compute_type='int8')
        segs, info = m.transcribe(str(wav), language=None if sprache == 'auto' else sprache, word_timestamps=True)
        woerter = [{'w': w.word.strip(), 's': round(w.start, 3), 'e': round(w.end, 3)} for seg in segs for w in seg.words]
        return {'text': ' '.join(w['w'] for w in woerter), 'sprache': info.language, 'woerter': woerter}


if __name__ == '__main__':
    print(__doc__)
    print('HEIM   ', HEIM)
    print('ARBEIT ', arbeit())
    sys.exit(0)
