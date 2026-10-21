"""Gemeinsame Helfer für Bau, Render und Prüfung (szenen, snap, render, vergleich, kit). Kein eigenes Werkzeug.

Folge und Projekt
  folge(ziel) -> Ordner der Folge (mit build/)
  szenen_lesen(folge) -> [{"id", "start", "dur", "track", "art", "inhalt"}] sortiert nach start
  stimme_finden(folge) / ton_finden(folge) -> Path | None
  gesamtdauer(folge, auslauf) -> (sekunden, quelle)
  kanal_ordner(folge) -> kanaele/<k> | None
  caption_stil(folge) -> dict (Standard + kit/captions.json des Kanals)
HyperFrames
  hf(args, cwd) -> CompletedProcess   (npx --yes hyperframes@<version>, Version aus config.json "hyperframes")
  lint(build) -> (fehler, warnungen, text)
Zahlen
  dauer(datei) -> Sekunden (ffprobe)
  index_dauer(build) -> data-duration der Wurzel in build/index.html (oder None)
  index_auslauf(build) -> Auslauf, mit dem ms szenen index.html gebaut hat (oder None)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import _ms

HF_STANDARD = 'hyperframes@0.8.181'
AUSLAUF = 0.47          # Sekunden Bild nach dem letzten Ton (bewährt: Stimm-Ende + 0,47)
UEBERLAPP = 0.06        # Szenen überlappen so viel (Start nächste = Ende − 0,06)
LUECKE_GRENZE = 0.02    # weniger Überlappung als das zählt als Lücke (0,02 s Lücke = Schwarzbild)

CAPTION_STANDARD = {
    'an': True,                 # false = Kanal ohne Untertitel
    'schrift': 'Montserrat',    # in HyperFrames eingebaut (offline, deterministisch); eigene Schrift: schrift_datei
    'schrift_datei': None,      # z. B. "fonts/MeineSchrift.ttf" (relativ zu build/assets/, kommt aus kit/fonts)
    'gewicht': 900,
    'groesse': 74,              # px bei 1080 breit
    'versalien': True,
    'farbe': '#ffffff',
    'kontur': '#000000',        # null = ohne Kontur
    'kontur_breite': 12,        # px (liegt hinter der Schrift)
    'schatten': '0 8px 0 rgba(0,0,0,0.35)',
    'hintergrund': None,        # Kasten pro Wort, z. B. "#0f5a46"
    'hintergrund_radius': 14,
    'innenabstand': '8px 20px 10px',
    'hervorhebung': {'farbe': '#ffd23f', 'hintergrund': None, 'skala': 1.08},
    'y': 1470,                  # Oberkante der Caption-Zeile (Wichtiges im Bild bleibt oberhalb)
    'seitenrand': 70,
    'zeilenabstand': 1.08,
    'wortabstand': 18,
    'max_woerter': 3,
    'max_zeichen': 18,
    'pause_bruch': 0.35,        # längere Pause zwischen zwei Wörtern beginnt eine neue Gruppe
    'erscheinen': 'wort',       # wort = Wörter ploppen nacheinander auf | gruppe = Gruppe steht, aktuelles Wort leuchtet
    'animation': 'pop',         # pop | auf | keine
    'satzzeichen_weg': '.,;:',  # diese Zeichen am Wortende nicht anzeigen
}


def folge(ziel) -> Path:
    d = _ms.ziel_pfad(ziel)
    if not (d / 'build').is_dir():
        raise SystemExit(f'FEHLER: {d} hat keinen Ordner build/. Ist das eine Folge? (ms neu folge …)')
    return d


def dauer(datei) -> float:
    r = _ms.befehl(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(datei)])
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise SystemExit(f'FEHLER: Dauer von {datei} nicht lesbar.')


def szenen_lesen(fo: Path) -> list[dict]:
    p = Path(fo) / 'build' / 'scenes.json'
    if not p.exists():
        raise SystemExit(f'FEHLER: {p} fehlt. Erst das Storyboard schreiben (Skill motion-storyboard).')
    try:
        sc = json.loads(p.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        raise SystemExit(f'FEHLER: {p} ist kein gültiges JSON ({e}).')
    if isinstance(sc, dict):
        sc = sc.get('szenen') or sc.get('scenes') or []
    if not isinstance(sc, list) or not sc:
        raise SystemExit(f'FEHLER: {p} muss eine Liste von Szenen sein.')
    ids = set()
    for i, s in enumerate(sc):
        for k in ('id', 'start', 'dur'):
            if k not in s:
                raise SystemExit(f'FEHLER: scenes.json Eintrag {i + 1} ohne "{k}".')
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', str(s['id'])):
            raise SystemExit(f'FEHLER: Szenen-id "{s["id"]}" ungültig (Buchstabe zuerst, dann a-z 0-9 _ -).')
        if s['id'] in ids:
            raise SystemExit(f'FEHLER: Szenen-id "{s["id"]}" doppelt.')
        ids.add(s['id'])
        s['start'] = float(s['start'])
        s['dur'] = float(s['dur'])
        s.setdefault('track', 1)
        s.setdefault('art', s.get('kind', '2d'))
        if s['dur'] <= 0:
            raise SystemExit(f'FEHLER: Szene {s["id"]} hat Dauer {s["dur"]}.')
    return sorted(sc, key=lambda s: (s['start'], s['track']))


def stimme_finden(fo: Path) -> Path | None:
    v = Path(fo) / 'voice'
    for name in ('stimme.wav', 'stimme_fit.wav', 'stimme.mp3', 'voice.wav'):
        if (v / name).exists():
            return v / name
    kand = [p for p in v.glob('*') if p.suffix.lower() in ('.wav', '.mp3', '.m4a') and not p.name.startswith('.')]
    return max(kand, key=lambda p: p.stat().st_mtime) if kand else None


def ton_finden(fo: Path) -> Path | None:
    mix = Path(fo) / 'build' / 'assets' / 'audio' / 'mix.wav'
    return mix if mix.exists() else stimme_finden(fo)


def gesamtdauer(fo: Path, auslauf: float = AUSLAUF, szenen: list | None = None) -> tuple[float, str]:
    st = stimme_finden(fo)
    if st:
        return round(dauer(st) + auslauf, 2), f'Stimme {st.name} + {auslauf:.2f} s'
    sc = szenen or szenen_lesen(fo)
    return round(max(s['start'] + s['dur'] for s in sc), 2), 'Ende der letzten Szene (keine Stimme gefunden)'


def kanal_ordner(fo: Path) -> Path | None:
    k = _ms.status_lesen(fo).get('kanal')
    if not k:
        return None
    d = _ms.arbeit() / 'kanaele' / k
    return d if d.exists() else None


def caption_stil(fo: Path) -> dict:
    stil = json.loads(json.dumps(CAPTION_STANDARD))
    k = kanal_ordner(fo)
    eigen = _ms.json_lesen(k / 'kit' / 'captions.json', {}) if k else {}
    for key, wert in (eigen or {}).items():
        if key.startswith('_'):
            continue
        if isinstance(wert, dict) and isinstance(stil.get(key), dict):
            stil[key].update(wert)
        else:
            stil[key] = wert
    return stil


def hf_paket() -> str:
    return _ms.config().get('hyperframes') or HF_STANDARD


def hf(args: list, cwd: Path, pruefen: bool = False, nett: bool = False, **kw) -> subprocess.CompletedProcess:
    """npx --yes hyperframes@<version> <args> im Ordner cwd. nett=True: mit niedriger Priorität (nice -n 10, Mac/Linux)."""
    npx = shutil.which('npx') or shutil.which('npx.cmd')
    if not npx:
        raise SystemExit('FEHLER: npx (Node.js) fehlt. "ms check" zeigt, wie Node installiert wird.')
    kw.setdefault('capture_output', True)
    kw.setdefault('text', True)
    vorne = ['nice', '-n', '10'] if nett and os.name == 'posix' and shutil.which('nice') else []
    r = subprocess.run(vorne + [npx, '--yes', hf_paket()] + [str(a) for a in args], cwd=str(cwd), **kw)
    if pruefen and r.returncode != 0:
        raise SystemExit(f'FEHLER: hyperframes {" ".join(map(str, args[:3]))} (Code {r.returncode})\n'
                         f'{((r.stdout or "") + (r.stderr or ""))[-2000:]}')
    return r


ANSI = re.compile(r'\x1b\[[0-9;]*m')


def lint(build: Path) -> tuple[int, int, str]:
    """Führt hyperframes lint aus. Ergebnis: (Fehler, Warnungen, Text ohne Farbcodes)."""
    r = hf(['lint', '.'], build)
    text = ANSI.sub('', (r.stdout or '') + (r.stderr or ''))
    fehler = warn = 0
    m = re.search(r'(\d+)\s+error', text)
    if m:
        fehler = int(m.group(1))
    m = re.search(r'(\d+)\s+warning', text)
    if m:
        warn = int(m.group(1))
    if not m and '✗' in text:
        fehler = max(fehler, text.count('✗'))
    if r.returncode != 0 and fehler == 0:
        fehler = 1
    return fehler, warn, text.strip()


def index_dauer(build: Path):
    p = Path(build) / 'index.html'
    if not p.exists():
        return None
    for tag in re.findall(r'<[a-zA-Z][^>]*data-composition-id="main"[^>]*>', p.read_text(encoding='utf-8', errors='replace')):
        m = re.search(r'data-duration="([\d.]+)"', tag)
        if m:
            return float(m.group(1))
    return None


AUSLAUF_MARKE = 'ms-auslauf'   # Kommentar in index.html: <!-- ms-auslauf 0.470 -->, damit render dieselbe Dauer rechnet


def index_auslauf(build: Path):
    """Auslauf, mit dem "ms szenen" index.html gebaut hat (Kommentar <!-- ms-auslauf X -->), sonst None."""
    p = Path(build) / 'index.html'
    if not p.exists():
        return None
    m = re.search(r'<!--\s*%s\s+([\d.]+)\s*-->' % AUSLAUF_MARKE, p.read_text(encoding='utf-8', errors='replace'))
    return float(m.group(1)) if m else None
