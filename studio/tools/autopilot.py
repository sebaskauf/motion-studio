"""Autopilot: baut jeden Tag selbst neue Folgen (Tagesbau, token-sparsam)
  ms autopilot                       Stand: an/aus, heute gebaut, laufende Bauten, warum gerade nichts startet
  ms autopilot an --kanal <slug> [--pro-tag 5] [--parallel 2] [--fenster 08:00-22:00] [--modell sonnet|opus] [--puffer 10]
  ms autopilot einstellen [--pro-tag 6] [--fenster …] [--modell …] [--kanal …]   nur einstellen, an/aus bleibt
  ms autopilot aus                   keine neuen Bauten mehr (laufende laufen zu Ende)
  ms autopilot lauf                  ein Durchlauf (macht der Zeitplan alle 15 min)
  ms autopilot jetzt                 einen Bau sofort starten (zählt nicht zum Tagesziel)
  ms autopilot einrichten            Zeitplan anlegen: macOS launchd, Windows Aufgabenplanung, Linux cron
  ms autopilot austragen             Zeitplan entfernen
  Zusatz: --trocken zeigt nur, was passieren würde. --json für Maschinen.
Sebastian 22.10.2026: „jeden Tag 5 bis 8 Videos automatisch, mit dem token-optimierten System“. Token-Diät wie im reel-studio
gemessen: Bau-Sitzungen mit Sonnet 5.5, ohne Auto-Gedächtnis (~20 % weniger Startkontext), Effizienz-Regeln aus motion-folge,
eine frische Sitzung je Folge. Grenzen: Bau-Fenster, Tagesziel, höchstens N gleichzeitig, Puffer fertiger Folgen, Pause beim
Nutzungslimit. Gepostet wird nichts: fertige Folgen landen im Dashboard (Vorrat), Posten bleibt beim Nutzer.
Mit tmux (Mac/Linux) läuft jeder Bau als Sitzung ms-autobau-…, im Dashboard sichtbar und beantwortbar. Ohne tmux (Windows)
läuft er als `claude -p` ohne Fenster, Log unter <Arbeitsordner>/autopilot/; Rückfragen landen dann als WARTET im STATUS.
Dateien: <Arbeitsordner>/autopilot.json (Einstellungen), <Arbeitsordner>/autopilot/zustand.json, autopilot/log.txt."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import _ms
import starten

STANDARD = {'an': False, 'kanal': '', 'pro_tag': 5, 'parallel': 2, 'fenster': ['08:00', '22:00'], 'modell': 'claude-sonnet-5-5',
            'denkstufe': 'high', 'puffer': 10, 'ohne_gedaechtnis': True, 'max_stunden': 6}
MODELLE = {'sonnet': 'claude-sonnet-5-5', 'opus': 'claude-opus-5-5', 'fable': 'claude-fable-5-1'}
LIMIT_RE = re.compile(r'usage limit|limit reached|rate.?limit|weekly limit|5-hour limit|/rate-limit-options|resets? (at|in)', re.I)
API_RE = re.compile(r'API Error|Connection (lost|error)|overloaded|Internal server error|ECONNRESET|ETIMEDOUT', re.I)
ERLEDIGT_S = 15 * 60     # wartet eine Bau-Sitzung so lange ohne Frage am Prompt, ist sie fertig: schließen, Platz frei
LABEL = 'de.motionstudio.autopilot'
AUFGABE_WIN = 'MotionStudio Autopilot'


def ordner() -> Path:
    o = _ms.arbeit() / 'autopilot'
    o.mkdir(parents=True, exist_ok=True)
    return o


def konfig() -> dict:
    d = _ms.json_lesen(_ms.arbeit() / 'autopilot.json', {}) or {}
    return {**STANDARD, **{k: v for k, v in d.items() if k in STANDARD}}


def konfig_schreiben(cfg: dict) -> None:
    _ms.json_schreiben(_ms.arbeit() / 'autopilot.json', {k: cfg[k] for k in STANDARD})


def zustand() -> dict:
    return _ms.json_lesen(ordner() / 'zustand.json', {}) or {}


def zustand_schreiben(z: dict) -> None:
    _ms.json_schreiben(ordner() / 'zustand.json', z)


def merke(text: str, art: str = 'info') -> None:
    zeile = f'{datetime.now():%Y-%m-%d %H:%M} {text}'
    with open(ordner() / 'log.txt', 'a', encoding='utf-8') as f:
        f.write(zeile + '\n')
    _ms.log(text, wer='autopilot', art=art)


@contextmanager
def sperre():
    """Ein Durchlauf zur Zeit (auch unter Windows: Sperrdatei mit O_EXCL, alte Sperren nach 10 min verfallen)."""
    p = ordner() / 'lauf.sperre'
    try:
        if p.exists() and time.time() - p.stat().st_mtime > 600:
            p.unlink()
        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise SystemExit('Ein anderer Durchlauf läuft gerade.')
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        p.unlink(missing_ok=True)


def _pid_lebt(pid: int) -> bool:
    if pid <= 0:
        return False
    if _ms.SYSTEM == 'Windows':
        r = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'], capture_output=True, text=True)
        return str(pid) in (r.stdout or '')
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _folgen() -> list[dict]:
    try:
        return _ms.alle_status()
    except Exception:  # eine kaputte STATUS.json soll den Autopilot nicht stoppen
        return []


def kanal_bereit(slug: str) -> bool:
    return any((s.get('art') == 'kanal') and (s.get('id') == slug or str(s.get('_ordner', '')).endswith('/' + slug))
               and s.get('phase') == 'bereit' for s in _folgen())


def fertig_ungepostet() -> int:
    return sum(1 for s in _folgen() if s.get('art') != 'kanal' and s.get('phase') == 'fertig')


def im_fenster(cfg: dict, jetzt: datetime) -> bool:
    von, bis = (list(cfg.get('fenster') or ['00:00', '23:59']) + ['23:59'])[:2]
    return von <= f'{jetzt:%H:%M}' < bis


def aufraeumen(z: dict, jetzt: datetime) -> None:
    """Bauten nachsehen: beendet, fertig (wartet ohne Frage am Prompt), Limit erreicht, läuft zu lange."""
    sitzungen = {s['name']: s for s in (starten.liste() if starten._tmux() else [])}
    bleiben = []
    for b in z.get('baue') or []:
        alter_h = (jetzt - datetime.fromisoformat(b['start'])).total_seconds() / 3600
        if b.get('art') == 'tmux':
            s = sitzungen.get(b['sitzung'])
            if not s or s.get('tot'):
                merke(f'Bau {b["sitzung"]} beendet ({alter_h:.1f} h).', 'fertig')
                if s and s.get('tot'):
                    try:
                        starten.stopp(b['sitzung'], wer='autopilot', protokoll=False)
                    except SystemExit:
                        pass
                continue
            text = '\n'.join(s.get('zeilen') or [])
            if LIMIT_RE.search(text):
                z['limit_bis'] = (jetzt + timedelta(hours=1)).isoformat(timespec='minutes')
            # Abgerissene Verbindung zur API (kommt vor): selbst „weiter“ schicken statt auf den Nutzer zu warten, höchstens 3 Mal je Bau
            elif s.get('zustand') == 'fehler' and API_RE.search(str(s.get('grund') or '')) and b.get('weiter', 0) < 3:
                try:
                    starten.weiter(b['sitzung'], wer='autopilot', protokoll=False)
                    b['weiter'] = b.get('weiter', 0) + 1
                    merke(f'Bau {b["sitzung"]}: API-Abbruch, „weiter“ geschickt ({b["weiter"]}/3).', 'warnung')
                except SystemExit:
                    pass
            if s.get('zustand') == 'wartet' and not s.get('frage') and (s.get('macht') or {}).get('art') == 'wartet' \
                    and s.get('still_seit', 0) >= ERLEDIGT_S:
                starten.stopp(b['sitzung'], wer='autopilot', protokoll=False)
                merke(f'Bau {b["sitzung"]} fertig, Sitzung geschlossen ({alter_h:.1f} h).', 'fertig')
                continue
        else:
            if not _pid_lebt(int(b.get('pid') or 0)):
                merke(f'Bau {b.get("log")} beendet ({alter_h:.1f} h).', 'fertig')
                continue
            try:
                ende = Path(b['log']).read_text(encoding='utf-8', errors='replace')[-4000:]
                if LIMIT_RE.search(ende):
                    z['limit_bis'] = (jetzt + timedelta(hours=1)).isoformat(timespec='minutes')
            except OSError:
                pass
        if alter_h > float(konfig().get('max_stunden') or 6) and not b.get('gewarnt'):
            merke(f'Bau {b.get("sitzung") or b.get("log")} läuft schon {alter_h:.1f} h. Bitte im Dashboard nachsehen.', 'warnung')
            b['gewarnt'] = True
        bleiben.append(b)
    z['baue'] = bleiben


def warum_nicht(cfg: dict, z: dict, jetzt: datetime) -> str | None:
    """None = ein Bau darf starten, sonst der Grund in Klartext."""
    if not cfg['an']:
        return 'Der Autopilot ist aus.'
    if z.get('limit_bis') and z['limit_bis'] > jetzt.isoformat(timespec='minutes'):
        return f'Claude-Nutzungslimit erreicht, Pause bis {z["limit_bis"][11:16]}.'
    if not cfg['kanal']:
        return 'Kein Kanal eingestellt (ms autopilot an --kanal <slug>).'
    if not kanal_bereit(cfg['kanal']):
        return f'Kanal {cfg["kanal"]} ist noch nicht fertig gelernt.'
    if not im_fenster(cfg, jetzt):
        return f'Gebaut wird zwischen {cfg["fenster"][0]} und {cfg["fenster"][1]} Uhr.'
    if (z.get('tage') or {}).get(jetzt.date().isoformat(), 0) >= int(cfg['pro_tag']):
        return f'Tagesziel erreicht ({cfg["pro_tag"]} Bauten), morgen geht es weiter.'
    if len(z.get('baue') or []) >= int(cfg['parallel']):
        return f'{cfg["parallel"]} Bauten laufen gleichzeitig, das ist das Maximum.'
    if fertig_ungepostet() >= int(cfg['puffer']):
        return f'{cfg["puffer"]} fertige Folgen warten aufs Posten (Puffer voll).'
    return None


def bau_starten(cfg: dict, z: dict, trocken=False, extra=False) -> dict:
    kw = {'modell': cfg['modell'], 'denkstufe': cfg['denkstufe'], 'ohne_gedaechtnis': bool(cfg['ohne_gedaechtnis']),
          'bypass': True}   # unbeaufsichtigt: keine Freigabe-Fragen, an denen der Bau hängen bliebe (Sebastian 23.10.)
    jetzt = datetime.now()
    if starten._tmux():
        erg = starten.starten('autobau', kanal=cfg['kanal'], trocken=trocken, wer='autopilot', **kw)
        eintrag = {'art': 'tmux', 'sitzung': erg.get('sitzung'), 'start': jetzt.isoformat(timespec='seconds')}
    else:
        text = starten.auftrag_text('autobau', kanal=cfg['kanal'])
        cmd = starten.claude_befehl(text, kopflos=True, **kw)
        log = ordner() / f'bau-{jetzt:%m%d-%H%M%S}.log'
        erg = {'befehl_text': ' '.join(cmd), 'log': str(log)}
        eintrag = {'art': 'kopflos', 'log': str(log), 'start': jetzt.isoformat(timespec='seconds')}
        if not trocken:
            umg = dict(os.environ, **starten._umgebung())
            flags = {'creationflags': 0x00000008 | 0x00000200} if _ms.SYSTEM == 'Windows' else {'start_new_session': True}
            with open(log, 'a', encoding='utf-8') as f:
                p = subprocess.Popen(cmd, cwd=str(starten._arbeitsordner()), env=umg, stdin=subprocess.DEVNULL, stdout=f,
                                     stderr=subprocess.STDOUT, **flags)
            eintrag['pid'] = p.pid
    if trocken:
        return {'trocken': True, **erg}
    if _ms.SYSTEM == 'Darwin' and shutil.which('caffeinate'):   # Mac während des Baus wach halten (Deckel offen)
        subprocess.Popen(['caffeinate', '-i', '-t', str(int(float(cfg['max_stunden']) * 3600))],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    z.setdefault('baue', []).append(eintrag)
    if not extra:
        tag = jetzt.date().isoformat()
        tage = z.setdefault('tage', {})
        tage[tag] = tage.get(tag, 0) + 1
        z['tage'] = dict(sorted(tage.items())[-14:])
    merke(f'Bau gestartet ({eintrag.get("sitzung") or "ohne Fenster"}, {cfg["modell"]})' + (', zusätzlich' if extra else ''))
    return erg


def lauf(trocken=False) -> dict:
    with sperre():
        cfg, z, jetzt = konfig(), zustand(), datetime.now()
        aufraeumen(z, jetzt)
        grund = warum_nicht(cfg, z, jetzt)
        erg = {'gestartet': False, 'grund': grund}
        while grund is None:
            erg.update(bau_starten(cfg, z, trocken=trocken))
            erg['gestartet'] = True
            if trocken:
                break
            grund = warum_nicht(cfg, z, datetime.now())
        z['letzter_lauf'] = jetzt.isoformat(timespec='seconds')
        if not trocken:
            zustand_schreiben(z)
        return erg


def stand() -> dict:
    """Für Terminal und Dashboard (Panel STEUERUNG)."""
    cfg, z, jetzt = konfig(), zustand(), datetime.now()
    heute = (z.get('tage') or {}).get(jetzt.date().isoformat(), 0)
    grund = warum_nicht(cfg, z, jetzt)
    return {'konfig': cfg, 'heute': heute, 'laufend': len(z.get('baue') or []), 'baue': z.get('baue') or [],
            'grund': grund, 'zeitplan': zeitplan_da(), 'letzter_lauf': z.get('letzter_lauf'), 'limit_bis': z.get('limit_bis')}


# ---------------------------------------------------------------- Zeitplan (alle 15 min)

def _python() -> str:
    for p in (_ms.HEIM / '.venv/bin/python', _ms.HEIM / '.venv/Scripts/python.exe'):
        if p.exists():
            return str(p)
    return sys.executable


def _pfad() -> str:
    """PATH für den Zeitplan: dort fehlen sonst Homebrew, tmux, node und claude."""
    teile = [str(Path(shutil.which('claude') or '').parent), str(Path(shutil.which('node') or '').parent),
             str(Path(shutil.which('tmux') or '').parent), '/opt/homebrew/bin', '/usr/local/bin', str(Path.home() / '.local/bin'),
             '/usr/bin', '/bin', '/usr/sbin', '/sbin']
    return os.pathsep.join(dict.fromkeys(t for t in teile if t and t != '.'))


def zeitplan_da() -> bool:
    if _ms.SYSTEM == 'Darwin':
        return (Path.home() / f'Library/LaunchAgents/{LABEL}.plist').exists()
    if _ms.SYSTEM == 'Windows':
        return subprocess.run(['schtasks', '/Query', '/TN', AUFGABE_WIN], capture_output=True).returncode == 0
    r = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
    return 'autopilot.py lauf' in (r.stdout or '')


def einrichten(trocken=False) -> str:
    skript, py, arbeit = str(Path(__file__).resolve()), _python(), str(_ms.arbeit())
    if _ms.SYSTEM == 'Darwin':
        plist = Path.home() / f'Library/LaunchAgents/{LABEL}.plist'
        log = str(ordner() / 'launchd.log')
        inhalt = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
 <key>Label</key><string>{LABEL}</string>
 <key>ProgramArguments</key><array><string>{py}</string><string>{skript}</string><string>lauf</string></array>
 <key>EnvironmentVariables</key><dict><key>MS_ARBEIT</key><string>{arbeit}</string><key>PATH</key><string>{_pfad()}</string>
  <key>PYTHONIOENCODING</key><string>utf-8</string></dict>
 <key>StartInterval</key><integer>900</integer><key>RunAtLoad</key><true/>
 <key>StandardOutPath</key><string>{log}</string><key>StandardErrorPath</key><string>{log}</string>
</dict></plist>
'''
        if trocken:
            return f'Würde {plist} anlegen und laden.'
        plist.parent.mkdir(parents=True, exist_ok=True)
        plist.write_text(inhalt, encoding='utf-8')
        uid = os.getuid()
        subprocess.run(['launchctl', 'bootout', f'gui/{uid}', str(plist)], capture_output=True)
        r = subprocess.run(['launchctl', 'bootstrap', f'gui/{uid}', str(plist)], capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(f'FEHLER: launchctl: {(r.stderr or r.stdout).strip()[:300]}')
        return f'Zeitplan aktiv: launchd {LABEL}, alle 15 min.'
    if _ms.SYSTEM == 'Windows':
        tr = f'"{py}" "{skript}" lauf'
        cmd = ['schtasks', '/Create', '/SC', 'MINUTE', '/MO', '15', '/TN', AUFGABE_WIN, '/TR', tr, '/F']
        if trocken:
            return 'Würde ausführen: ' + subprocess.list2cmdline(cmd)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(f'FEHLER: schtasks: {(r.stderr or r.stdout).strip()[:300]}')
        return f'Zeitplan aktiv: Aufgabenplanung „{AUFGABE_WIN}“, alle 15 min (nur solange du angemeldet bist).'
    zeile = f'*/15 * * * * MS_ARBEIT="{arbeit}" PATH="{_pfad()}" "{py}" "{skript}" lauf >> "{ordner() / "cron.log"}" 2>&1'
    if trocken:
        return f'Würde in crontab eintragen: {zeile}'
    alt = subprocess.run(['crontab', '-l'], capture_output=True, text=True).stdout or ''
    neu = '\n'.join(z for z in alt.splitlines() if 'autopilot.py lauf' not in z) + '\n' + zeile + '\n'
    subprocess.run(['crontab', '-'], input=neu.lstrip('\n'), text=True, check=True)
    return 'Zeitplan aktiv: cron, alle 15 min.'


def austragen() -> str:
    if _ms.SYSTEM == 'Darwin':
        plist = Path.home() / f'Library/LaunchAgents/{LABEL}.plist'
        subprocess.run(['launchctl', 'bootout', f'gui/{os.getuid()}', str(plist)], capture_output=True)
        plist.unlink(missing_ok=True)
    elif _ms.SYSTEM == 'Windows':
        subprocess.run(['schtasks', '/Delete', '/TN', AUFGABE_WIN, '/F'], capture_output=True)
    else:
        alt = subprocess.run(['crontab', '-l'], capture_output=True, text=True).stdout or ''
        subprocess.run(['crontab', '-'], input='\n'.join(z for z in alt.splitlines() if 'autopilot.py lauf' not in z) + '\n', text=True)
    return 'Zeitplan entfernt.'


# ---------------------------------------------------------------- Kommandozeile

def _zeit(s: str) -> str:
    if not re.match(r'^\d\d:\d\d$', s):
        raise SystemExit(f'FEHLER: Uhrzeit „{s}“ bitte als HH:MM.')
    return s


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('was', nargs='?', default='stand', choices=['stand', 'an', 'einstellen', 'aus', 'lauf', 'jetzt', 'einrichten', 'austragen'])
    ap.add_argument('--kanal')
    ap.add_argument('--pro-tag', type=int)
    ap.add_argument('--parallel', type=int)
    ap.add_argument('--fenster', help='z. B. 08:00-22:00')
    ap.add_argument('--modell', help='sonnet (Standard, sparsam), opus oder fable')
    ap.add_argument('--puffer', type=int)
    ap.add_argument('--trocken', action='store_true')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    def aus(d, text):
        print(json.dumps(d, ensure_ascii=False, indent=1) if a.json else text)

    if a.was == 'stand':
        s = stand()
        c = s['konfig']
        zeilen = [f'Autopilot: {"an" if c["an"] else "aus"} · Kanal {c["kanal"] or "–"} · {s["heute"]} von {c["pro_tag"]} Bauten heute · '
                  f'{s["laufend"]} laufen (max. {c["parallel"]}) · {c["fenster"][0]}–{c["fenster"][1]} Uhr · {c["modell"]}',
                  f'Zeitplan: {"aktiv" if s["zeitplan"] else "fehlt (ms autopilot einrichten)"}',
                  f'Jetzt: {s["grund"] or "der nächste Durchlauf startet einen Bau"}']
        zeilen += [f'  läuft: {b.get("sitzung") or b.get("log")} seit {b["start"][11:16]}' for b in s['baue']]
        return aus(s, '\n'.join(zeilen))
    if a.was in ('an', 'einstellen'):
        cfg = konfig()
        if a.kanal:
            cfg['kanal'] = starten._kanal_pruefen(a.kanal)
        for feld, wert in (('pro_tag', a.pro_tag), ('parallel', a.parallel), ('puffer', a.puffer)):
            if wert is not None:
                if not 1 <= wert <= 20:
                    raise SystemExit(f'FEHLER: {feld} zwischen 1 und 20.')
                cfg[feld] = wert
        if a.fenster:
            von, _, bis = a.fenster.partition('-')
            cfg['fenster'] = [_zeit(von), _zeit(bis)]
        if a.modell:
            cfg['modell'] = MODELLE.get(a.modell, a.modell)
        if a.was == 'einstellen':
            if not a.trocken:
                konfig_schreiben(cfg)
            return aus({'ok': True, 'konfig': cfg}, f'Eingestellt: {cfg["pro_tag"]} pro Tag, {cfg["parallel"]} parallel, '
                                                     f'{cfg["fenster"][0]}–{cfg["fenster"][1]} Uhr, {cfg["modell"]}. Autopilot ist {"an" if cfg["an"] else "aus"}.')
        if not cfg['kanal']:
            raise SystemExit('FEHLER: Welcher Kanal? ms autopilot an --kanal <slug> (ms status zeigt die Kanäle).')
        cfg['an'] = True
        if not a.trocken:
            konfig_schreiben(cfg)
            merke(f'Autopilot an: Kanal {cfg["kanal"]}, {cfg["pro_tag"]} pro Tag, {cfg["parallel"]} parallel, {cfg["modell"]}')
        hinweis = '' if zeitplan_da() else ' Der Zeitplan fehlt noch: ms autopilot einrichten.'
        return aus({'ok': True, 'konfig': cfg}, f'Autopilot ist an.{hinweis}')
    if a.was == 'aus':
        cfg = konfig()
        cfg['an'] = False
        if not a.trocken:
            konfig_schreiben(cfg)
            merke('Autopilot aus (laufende Bauten laufen zu Ende)', 'warnung')
        return aus({'ok': True}, 'Autopilot ist aus. Laufende Bauten laufen zu Ende.')
    if a.was == 'lauf':
        e = lauf(trocken=a.trocken)
        return aus(e, ('Bau gestartet.' if e['gestartet'] else 'Kein Bau gestartet: ' + str(e['grund'])))
    if a.was == 'jetzt':
        cfg = konfig()
        if not cfg['kanal']:
            raise SystemExit('FEHLER: Kein Kanal eingestellt (ms autopilot an --kanal <slug>).')
        with sperre():
            z = zustand()
            e = bau_starten(cfg, z, trocken=a.trocken, extra=True)
            if not a.trocken:
                zustand_schreiben(z)
        return aus(e, 'Bau gestartet (zusätzlich).' if not e.get('trocken') else f'Trocken: {e.get("befehl_text") or e.get("start_text")}')
    if a.was == 'einrichten':
        return aus({'ok': True}, einrichten(trocken=a.trocken))
    if a.was == 'austragen':
        return aus({'ok': True}, austragen())


if __name__ == '__main__':
    main()
