"""Gemeinsame Ton-Hilfen für stimme, woerter, sound und mix (kein eigenes Werkzeug, wird importiert).

Dekodieren und Schreiben (immer über ffmpeg, nie ganze Videos)
  dekodiere(pfad, rate=48000, kanaele=1, von=None, bis=None, max_s=None, filt=None) -> float32 (n,) oder (n, k)
  schreibe_wav(pfad, x, rate=48000, gleitkomma=False)   16 bit PCM oder 32-bit-Gleitkomma
  auf_lufs(ein, aus, ziel=-14, tp=-1.5) -> float    Gain + Limiter, misst nach (ffmpeg ebur128)

Messen (Lautheit nach ITU-R BS.1770, K-gewichtet)
  k_filter(x)                -> K-gewichtetes Signal (48 kHz)
  k_laut(x)                  -> K-Lautheit des hörbaren Teils in LUFS (auch für 30-ms-Klicks, ohne Gating)
  lufs_integriert(x)         -> integrierte Lautheit mit Gating (wie ffmpeg ebur128)
  gleitend(xk, hop, win)     -> (Startindizes, Lautheit je Fenster in dB)
  messe(x)                   -> {dauer, lufs, peak, anschlag, hell, tief}
  anschlag(x)                -> Sekunde, in der der Sound „zuschlägt“ (10-ms-Hüllkurve > 30 % des Maximums)

Katalog der Sound-Bibliothek (<arbeit>/sounds/katalog.json)
  sounds_ordner(), katalog_lesen(), katalog_schreiben(k), index(k), familien_sync(k)
  familie_aus_text(text, familien) -> Familie zu einer Beschreibung ("confetti pop" -> plopp), Tabelle FAMILIE_WOERTER
Benötigt: numpy, scipy (K-Filter). Fehlen sie, kommt eine verständliche Meldung."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import _ms

SR = 48000
AUDIO_ENDUNGEN = {'.wav', '.mp3', '.ogg', '.flac', '.m4a', '.aif', '.aiff', '.opus', '.aac'}


def np_():
    try:
        import numpy
    except ImportError:
        raise SystemExit('FEHLER: numpy fehlt in der Studio-Umgebung. "ms check" zeigt, wie es installiert wird.')
    return numpy


# ---------------------------------------------------------------- Dekodieren und Schreiben

def dekodiere(pfad, rate=SR, kanaele=1, von=None, bis=None, max_s=None, filt=None):
    """Audio als float32. von/bis in Sekunden (Fenster), max_s begrenzt die Länge (Schutz bei langen Dateien)."""
    np = np_()
    if shutil.which('ffmpeg') is None:
        raise SystemExit('FEHLER: ffmpeg fehlt. "ms check" zeigt, wie es installiert wird.')
    cmd = ['ffmpeg', '-nostdin', '-v', 'error']
    if von:
        cmd += ['-ss', f'{float(von):.4f}']
    cmd += ['-i', str(pfad)]
    laenge = None
    if bis is not None:
        laenge = max(0.0, float(bis) - float(von or 0))
    if max_s is not None:
        laenge = min(laenge, float(max_s)) if laenge is not None else float(max_s)
    if laenge is not None:
        cmd += ['-t', f'{laenge:.4f}']
    if filt:
        cmd += ['-af', filt]
    cmd += ['-vn', '-f', 'f32le', '-ac', str(kanaele), '-ar', str(rate), '-']
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f'FEHLER: {pfad} lässt sich nicht lesen ({r.stderr.decode(errors="replace")[-300:].strip()}).')
    x = np.frombuffer(r.stdout, dtype=np.float32).copy()
    return x.reshape(-1, kanaele) if kanaele > 1 else x


def schreibe_wav(pfad, x, rate=SR, gleitkomma=False) -> Path:
    """Schreibt WAV: 16 bit (Standard, wird auf ±1 begrenzt) oder 32-bit-Gleitkomma (Zwischenstand ohne Übersteuern)."""
    np = np_()
    x = np.asarray(x, dtype=np.float32)
    k = 1 if x.ndim == 1 else x.shape[1]
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which('ffmpeg') is None:
        raise SystemExit('FEHLER: ffmpeg fehlt. "ms check" zeigt, wie es installiert wird.')
    daten = x if gleitkomma else np.clip(x, -1, 1)
    r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'f32le', '-ac', str(k), '-ar', str(rate), '-i', '-',
                        '-c:a', 'pcm_f32le' if gleitkomma else 'pcm_s16le', str(pfad)], input=daten.tobytes(), capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f'FEHLER: {pfad} ließ sich nicht schreiben ({r.stderr.decode(errors="replace")[-300:].strip()}).')
    return pfad


def auf_lufs(ein, aus, ziel=-14.0, tp=-1.5, rate=SR, runden=3) -> float:
    """Bringt eine Datei auf ziel LUFS (integriert): Gain, dann Limiter auf tp dBFS. Misst nach und korrigiert
    bis zu runden Mal (der Limiter frisst bei lauten Spitzen etwas Lautheit). Gibt die gemessene Lautheit zurück."""
    ein, aus = Path(ein), Path(aus)
    gemessen = _ms.lufs(ein)
    gain = ziel - gemessen
    limit = 10 ** (tp / 20)
    with tempfile.TemporaryDirectory() as tmp:
        quelle = Path(tmp) / 'quelle.wav'
        shutil.copy2(ein, quelle)
        ergebnis = gemessen
        for _ in range(runden):
            _ms.befehl(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(quelle), '-af',
                        f'volume={gain:.3f}dB,alimiter=limit={limit:.4f}:attack=2:release=60:level=false',
                        '-ar', str(rate), '-c:a', 'pcm_s16le', str(aus)])
            ergebnis = _ms.lufs(aus)
            if abs(ergebnis - ziel) <= 0.2:
                break
            gain += ziel - ergebnis
    return ergebnis


# ---------------------------------------------------------------- Messen

def k_filter(x):
    """ITU-R BS.1770 K-Filter (Koeffizienten für 48 kHz) auf ein Mono-Signal."""
    np = np_()
    try:
        from scipy.signal import lfilter
    except ImportError:
        raise SystemExit('FEHLER: scipy fehlt in der Studio-Umgebung (für die gehörgerechte Lautheit). "ms check" zeigt, wie es installiert wird.')
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585]
    b2, a2 = [1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621]
    return lfilter(b2, a2, lfilter(b1, a1, np.asarray(x, dtype=np.float64)))


def mono(x):
    return x.mean(axis=1) if x.ndim > 1 else x


def k_laut(x) -> float:
    """K-gewichtete Lautheit (LUFS-Skala) des hörbaren Teils. Ohne Gating, damit auch sehr kurze Sounds einen Wert haben."""
    np = np_()
    m = mono(x)
    if not len(m):
        return -120.0
    a = np.abs(m)
    k = k_filter(m)
    sel = a > max(a.max() * 0.03, 1e-8)
    if not sel.any():
        return -120.0
    return float(-0.691 + 10 * np.log10(np.mean(k[sel] ** 2) + 1e-12))


def gleitend(xk, hop, win):
    """Lautheit in Fenstern der Länge win (Samples), Schrittweite hop, auf einem schon K-gefilterten Signal."""
    np = np_()
    c = np.concatenate([[0.0], np.cumsum(np.asarray(xk, dtype=np.float64) ** 2)])
    n = len(xk)
    idx = np.arange(0, max(1, n - win), hop)
    return idx, -0.691 + 10 * np.log10((c[np.minimum(idx + win, n)] - c[idx]) / win + 1e-12)


def lufs_integriert(x, rate=SR) -> float:
    """Integrierte Lautheit nach BS.1770-4 (400-ms-Blöcke, 75 % Überlappung, Gates −70 LUFS und −10 LU)."""
    np = np_()
    kan = [x] if x.ndim == 1 else [x[:, i] for i in range(x.shape[1])]
    win, hop = int(0.4 * rate), int(0.1 * rate)
    z = None
    for c in kan:
        k = k_filter(c)
        cs = np.concatenate([[0.0], np.cumsum(k ** 2)])
        idx = np.arange(0, max(1, len(k) - win + 1), hop)
        zc = (cs[np.minimum(idx + win, len(k))] - cs[idx]) / win
        z = zc if z is None else z + zc
    if z is None or not len(z):
        return -120.0
    l = -0.691 + 10 * np.log10(z + 1e-12)
    z1 = z[l > -70]
    if not len(z1):
        return -120.0
    rel = -0.691 + 10 * np.log10(z1.mean()) - 10
    z2 = z[(l > -70) & (l > rel)]
    return float(-0.691 + 10 * np.log10(z2.mean() + 1e-12)) if len(z2) else -120.0


def anschlag(x, rate=SR) -> float:
    np = np_()
    m = mono(x)
    if not len(m):
        return 0.0
    w = max(1, rate // 100)
    env = np.sqrt(np.convolve(m * m, np.ones(w) / w, 'same'))
    return float(np.argmax(env > env.max() * 0.3) / rate) if env.max() > 0 else 0.0


def ende_hoerbar(x, rate=SR, unter_db=50.0) -> int:
    """Index nach dem letzten Sample, das lauter als (Spitze − unter_db) ist, plus 20 ms Ausklang."""
    np = np_()
    a = np.abs(mono(x))
    if not len(a) or a.max() <= 0:
        return len(a)
    laut = np.nonzero(a > a.max() * 10 ** (-unter_db / 20))[0]
    return int(min(len(a), laut[-1] + 1 + int(0.02 * rate))) if len(laut) else len(a)


def spektrum_anteile(x, rate=SR):
    """(Anteil Energie über 8 kHz, Anteil unter 150 Hz) des hörbaren Teils, höchstens 3 s."""
    np = np_()
    m = mono(x)
    a = np.abs(m)
    if not len(m) or a.max() <= 0:
        return 0.0, 0.0
    sel = np.nonzero(a > a.max() * 0.03)[0]
    seg = m[sel[0]:sel[-1] + 1][:3 * rate]
    if len(seg) < 64:
        return 0.0, 0.0
    X = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2
    f = np.fft.rfftfreq(len(seg), 1 / rate)
    ges = X.sum() + 1e-12
    return float(X[f > 8000].sum() / ges), float(X[f < 150].sum() / ges)


def messe(x, rate=SR) -> dict:
    np = np_()
    m = mono(x)
    peak = float(20 * np.log10(np.abs(m).max() + 1e-9)) if len(m) else -120.0
    hell, tief = spektrum_anteile(m, rate)
    return {'dauer': round(len(m) / rate, 3), 'lufs': round(k_laut(m), 1), 'peak': round(peak, 1),
            'anschlag': round(anschlag(m, rate), 3), 'hell': round(hell, 3), 'tief': round(tief, 3)}


def trim_geschaetzt(dauer: float, hell: float) -> float:
    """Geschätzte Lautheits-Korrektur für Sounds ohne Urteil. Erfahrung aus Hörtests: Sounds gleicher gemessener
    Lautheit wirken lauter, wenn sie länger als ca. 0,3 s klingen und viel Energie über 8 kHz haben."""
    import math
    return round(min(0.0, -0.4 - 0.55 * math.log2(max(dauer, 0.1) / 0.3) - 3.1 * hell) * 1.3, 1)


# ---------------------------------------------------------------- Text

def norm_wort(w: str) -> str:
    return ''.join(ch for ch in str(w).lower() if ch.isalnum())


# Beschreibung (meist englisch, aus build/sfx_<bauer>.json) -> Sound-Familie. Zentrale Tabelle: hier ergänzen.
# Zählt nur, wenn die Familie im Katalog existiert. Wortformen wie pops, landing, dropped passen mit.
FAMILIE_WOERTER = {
    'plopp': ('pop', 'appear'),
    'klick': ('click', 'tick'),
    'landen': ('thud', 'land', 'drop'),
    'whoosh': ('whoosh', 'woosh', 'swoosh', 'swipe'),
    'papier': ('paper', 'page'),
}
_ENDUNGEN = ('', 's', 'es', 'ed', 'd', 'ing', 'ping', 'ped', 'pping', 'pped')


def familie_aus_text(text: str, familien) -> str | None:
    """Familie für eine Sound-Beschreibung: zuerst ein Familienname im Text ("@whoosh", "plopp"), dann das erste Wort
    aus FAMILIE_WOERTER. Nur Familien, die es gibt (familien = Namen aus dem Katalog)."""
    vorhanden = set(familien or [])
    klein = str(text).lower()
    direkt = [f for f in vorhanden if f in klein]
    if direkt:
        return sorted(direkt, key=klein.index)[0]
    for wort in re.findall(r'[a-zäöüß]+', klein):
        for fam, staemme in FAMILIE_WOERTER.items():
            if fam in vorhanden and any(wort == s + e for s in staemme for e in _ENDUNGEN):
                return fam
    return None


# ---------------------------------------------------------------- Katalog

def sounds_ordner() -> Path:
    return _ms.arbeit() / 'sounds'


def katalog_lesen() -> dict:
    k = _ms.json_lesen(sounds_ordner() / 'katalog.json', None)
    if not k:
        k = {'schema': 1, 'hinweis': 'Sound-Bibliothek von Motion-Studio. Pflege über "ms sound …". urteil: behalten | raus | null. '
                                     'trim_db: Lautheits-Korrektur nach Gehör. gesperrt: darf nie in einen Mix.',
             'sounds': [], 'familien': {}}
    k.setdefault('sounds', [])
    k.setdefault('familien', {})
    return k


def familien_sync(k: dict) -> None:
    """Die Familien-Liste ist die Wahrheit. Das Feld 'familie' je Sound wird daraus gesetzt."""
    ids = {s['id'] for s in k['sounds']}
    zu = {}
    for name, f in k['familien'].items():
        f['mitglieder'] = [m for m in f.get('mitglieder', []) if m in ids]
        for m in f['mitglieder']:
            zu.setdefault(m, name)
    for s in k['sounds']:
        s['familie'] = zu.get(s['id'])


def katalog_schreiben(k: dict) -> Path:
    familien_sync(k)
    k['aktualisiert'] = _ms.jetzt()
    return _ms.json_schreiben(sounds_ordner() / 'katalog.json', k)


def index(k: dict) -> dict:
    return {s['id']: s for s in k['sounds']}


def sound_datei(s: dict) -> Path:
    return sounds_ordner() / s['datei']


def slug(s: str) -> str:
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', str(s))
    return re.sub(r'[^a-z0-9äöüß]+', '-', s.lower()).strip('-') or 'sound'


def ki_verfuegbar() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False


def hf_laden(klasse, modell_id: str):
    """Lädt ein Hugging-Face-Modell. Sucht zuerst in MS_HF_CACHE (mehrere Ordner mit ':' bzw. ';' getrennt) und
    config.json "hf_cache", dann im Standard-Cache; lädt nur herunter, wenn es nirgends liegt."""
    import os
    kandidaten = []
    for q in (os.environ.get('MS_HF_CACHE'), _ms.config().get('hf_cache')):
        if q:
            kandidaten += [p for p in str(q).split(os.pathsep) if p]
    for c in kandidaten:
        try:
            return klasse.from_pretrained(modell_id, cache_dir=os.path.expanduser(c), local_files_only=True)
        except Exception:
            pass
    try:
        return klasse.from_pretrained(modell_id, local_files_only=True)
    except Exception:
        if os.environ.get('HF_HUB_OFFLINE') == '1':
            raise SystemExit(f'FEHLER: Modell {modell_id} liegt nicht im Cache und HF_HUB_OFFLINE=1 verbietet den Download.')
        print(f'Lade Modell {modell_id} einmalig herunter (einige hundert MB) …', flush=True)
        return klasse.from_pretrained(modell_id)


def ki_geraet():
    import torch
    if torch.backends.mps.is_available():
        return 'mps'
    return 'cuda' if torch.cuda.is_available() else 'cpu'


def json_kurz(d) -> str:
    return json.dumps(d, ensure_ascii=False)
