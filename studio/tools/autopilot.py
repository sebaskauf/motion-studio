"""Autopilot: baut jeden Tag selbst eigene Folgen und postet sie nach Freigabe (Tagesbau, token-sparsam)
  ms autopilot                       Stand: an/aus, heute gebaut, laufende Bauten, Wochenanteil, warum gerade nichts startet
  ms autopilot an --kanal <slug> [--pro-tag 1] [--parallel 1] [--fenster 08:00-22:00] [--puffer 5]
  ms autopilot einstellen [--pro-tag 2] [--fenster …] [--kanal …] [--bremse 60] [--staffel an|aus]   nur einstellen
  ms autopilot abo pro|max5|max20    Vorschlag je Abo setzen (Folgen pro Tag, gleichzeitig, Wochenbremse) und erklären
  ms autopilot posten an|aus [--zeit 18:00] [--pro-tag 1]   täglich posten (nur freigegebene Plattformen, Skill motion-posten)
  ms autopilot aus                   keine neuen Bauten mehr (laufende laufen zu Ende)
  ms autopilot lauf                  ein Durchlauf (macht der Zeitplan alle 15 min)
  ms autopilot jetzt                 einen Bau sofort starten (zählt nicht zum Tagesziel)
  ms autopilot anstossen             in 20 s einen Durchlauf (wiederholt, solange ein anderer läuft): ms status --stufe A-fertig
                                     ruft das abgekoppelt auf, damit Stufe B ohne Warten auf den Zeitplan startet
  ms autopilot einrichten            Zeitplan anlegen: macOS launchd, Windows Aufgabenplanung, Linux cron
  ms autopilot austragen             Zeitplan entfernen
  Zusatz: --trocken zeigt nur, was passieren würde. --json für Maschinen.
Standard 1 Folge am Tag (Sebastian 30.10.2026), Vorschlag je Abo über `ms autopilot abo`. Token-Diät wie im reel-studio:
frische Sitzungen, ohne Auto-Gedächtnis, nur nötige MCP-Server, Staffel-Bau (Stufe A Idee bis Storyboard mit Opus, Stufe B
Szenen bis fertig mit Sonnet, je eine frische Sitzung; Modelle in autopilot.json, siehe _konfig.py).
Sonnet spart keine Token (gemessen 22.10.: je Videosekunde rund 20 % mehr als Opus), ob es weniger aufs Limit zählt, ist offen.
Grenzen: Bau-Fenster, Tagesziel, höchstens N gleichzeitig, Puffer (ungepostete EIGENE Folgen des Kanals, Pilot und Nachbau
zählen nicht), Wochenbremse (geschätzter Anteil am Wochenlimit aus den Sitzungsprotokollen, ms verbrauch), Pause beim
Nutzungslimit bis zur Reset-Zeit aus der Meldung.
Posten (aus, bis `ms autopilot posten an`): einmal täglich ab post_zeit die älteste postbare eigene Folge, nur auf Plattformen
mit gespeichertem Ablauf und Freigabe (ms posten). Ein Fehlschlag steht rot im Studio, danach postet der Autopilot nicht weiter,
bis der Fehler erledigt ist (ms posten erledigt <folge>).
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

import _konfig
import _ms
import _verbrauch
import _vorrat
import starten

STANDARD = _konfig.STANDARD
LIMIT_RE = re.compile(r'usage limit|limit reached|hit your (weekly|session|usage|daily) limit|rate.?limit|weekly limit|5-hour limit|'
                      r'/rate-limit-options|HTTP 429', re.I)
RESET_RE = re.compile(r'resets?\s+(?:at\s+|on\s+)?(?:(?P<mon>[A-Z][a-z]{2})\s+(?P<tag>\d{1,2})(?:,)?\s+(?:at\s+)?)?'
                      r'(?P<h>\d{1,2})(?::(?P<m>\d\d))?\s*(?P<ap>am|pm)?', re.I)
RESET_IN_RE = re.compile(r'resets?\s+in\s+(?:(?P<h>\d+)\s*h(?:ours?)?)?\s*(?:(?P<m>\d+)\s*m(?:in(?:utes?)?)?)?', re.I)
MONATE = {m: i + 1 for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'])}
API_RE = re.compile(r'API Error|Connection (lost|error)|overloaded|Internal server error|ECONNRESET|ETIMEDOUT', re.I)
ERLEDIGT_S = 15 * 60     # wartet eine Bau-Sitzung so lange ohne Frage am Prompt, ist sie fertig: schließen, Platz frei
LABEL = 'de.motionstudio.autopilot'
AUFGABE_WIN = 'MotionStudio Autopilot'


def ordner() -> Path:
    o = _ms.arbeit() / 'autopilot'
    o.mkdir(parents=True, exist_ok=True)
    return o


def konfig() -> dict:
    return _konfig.konfig()


def konfig_schreiben(cfg: dict) -> None:
    _konfig.konfig_schreiben(cfg)


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


def fertig_ungepostet(kanal: str | None = None) -> int:
    """Puffer: ungepostete EIGENE Folgen des Kanals. Pilot, Nachbau, Kopie und Gepostetes zählen nicht (Sebastian 30.10.)."""
    return _vorrat.ungepostet(kanal or None, _folgen())


def im_fenster(cfg: dict, jetzt: datetime) -> bool:
    von, bis = (list(cfg.get('fenster') or ['00:00', '23:59']) + ['23:59'])[:2]
    return von <= f'{jetzt:%H:%M}' < bis


# ---------------------------------------------------------------- Limit und Wochenbremse

def reset_zeit(text: str, jetzt: datetime) -> datetime | None:
    """Reset-Zeitpunkt aus der Limit-Meldung von Claude Code („resets 3pm“, „Resets Oct 29 at 2am“, „resets in 2h 10m“)."""
    m = RESET_IN_RE.search(text or '')
    if m and (m.group('h') or m.group('m')):
        return jetzt + timedelta(hours=int(m.group('h') or 0), minutes=int(m.group('m') or 0))
    for m in RESET_RE.finditer(text or ''):
        h, mi, ap = int(m.group('h')), int(m.group('m') or 0), (m.group('ap') or '').lower()
        if not ap and not m.group('m'):
            continue                                   # eine nackte Zahl ist keine Uhrzeit
        if ap == 'pm' and h < 12:
            h += 12
        if ap == 'am' and h == 12:
            h = 0
        if h > 23 or mi > 59:
            continue
        t = jetzt.replace(hour=h, minute=mi, second=0, microsecond=0)
        if m.group('mon') and m.group('mon').lower() in MONATE:
            try:
                t = t.replace(month=MONATE[m.group('mon').lower()], day=int(m.group('tag')))
            except ValueError:
                continue
            if t < jetzt - timedelta(days=200):
                t = t.replace(year=t.year + 1)
        elif t <= jetzt:
            t += timedelta(days=1)
        return t
    return None


def limit_merken(z: dict, text: str, jetzt: datetime) -> None:
    """Pause bis zum Reset aus der Meldung (+2 min), sonst neuer Versuch in 1 h."""
    t = reset_zeit(text, jetzt)
    bis = (t + timedelta(minutes=2)) if t else jetzt + timedelta(hours=1)
    if not z.get('limit_bis') or z['limit_bis'] < bis.isoformat(timespec='minutes'):
        z['limit_bis'] = bis.isoformat(timespec='minutes')
        z['limit_reset'] = bool(t)
        merke(f'Claude-Nutzungslimit erreicht, Pause bis {bis:%d.%m. %H:%M}' + ('' if t else ' (kein Reset-Zeitpunkt sichtbar, neuer Versuch)'), 'warnung')


def woche(cfg: dict, z: dict, messen: bool = False) -> dict:
    """Geschätzter Anteil am Wochenlimit (ms verbrauch). Gemessen wird nur im Durchlauf, das Studio liest den letzten Wert."""
    if messen:
        try:
            _verbrauch.wochen_anteil(cfg, cache=z)
        except Exception as e:  # Protokolle nicht lesbar: Bremse greift dann nicht, aber der Grund steht im Stand
            z['woche'] = {'prozent': None, 'grund': f'nicht messbar: {type(e).__name__}: {e}', 'zeit': time.time()}
    return z.get('woche') or {}


# ---------------------------------------------------------------- Bauten nachsehen

def _status(fid: str | None) -> dict:
    if not fid:
        return {}
    return _ms.json_lesen(_ms.arbeit() / 'folgen' / fid / 'STATUS.json', {}) or {}


def folge_von(b: dict, alle: list[dict]) -> str | None:
    """Folge eines Baus: STATUS „sitzung“ (ms neu folge schreibt MS_SITZUNG hinein), sonst die beim Start bekannte."""
    if b.get('folge'):
        return b['folge']
    name = b.get('sitzung') or Path(str(b.get('log') or '')).stem
    if not name:
        return None
    return next((_vorrat.folge_id(s) for s in alle if s.get('art') != 'kanal' and s.get('sitzung') == name), None)


def _sitzung_starten(art: str, cfg: dict, kanal: str | None = None, folge: str | None = None, trocken=False) -> tuple[dict, dict]:
    """Startet eine Agenten-Sitzung: mit tmux sichtbar und beantwortbar, sonst kopflos (`claude -p`) mit Log-Datei."""
    jetzt = datetime.now()
    if starten._tmux():
        erg = starten.starten(art, kanal=kanal, folge=folge, trocken=trocken, wer='autopilot')
        return erg, {'art': 'tmux', 'sitzung': erg.get('sitzung'), 'start': jetzt.isoformat(timespec='seconds')}
    text = starten.auftrag_text(art, kanal=kanal, folge=folge)
    o = starten.optionen(art)
    cmd = starten.claude_befehl(text, kopflos=True, **o)
    log = ordner() / f'{art}-{jetzt:%m%d-%H%M%S}.log'
    erg = {'befehl_text': ' '.join(cmd), 'log': str(log), 'optionen': o}
    eintrag = {'art': 'kopflos', 'log': str(log), 'start': jetzt.isoformat(timespec='seconds')}
    if not trocken:
        umg = dict(os.environ, **starten._umgebung(log.stem))
        flags = {'creationflags': 0x00000008 | 0x00000200} if _ms.SYSTEM == 'Windows' else {'start_new_session': True}
        with open(log, 'a', encoding='utf-8') as f:
            p = subprocess.Popen(cmd, cwd=str(starten._arbeitsordner()), env=umg, stdin=subprocess.DEVNULL, stdout=f,
                                 stderr=subprocess.STDOUT, **flags)
        eintrag['pid'] = p.pid
    return erg, eintrag


def _beenden(b: dict) -> None:
    if b.get('art') == 'tmux' and b.get('sitzung'):
        try:
            starten.stopp(b['sitzung'], wer='autopilot', protokoll=False)
        except SystemExit:
            pass


def stufe_b(cfg: dict, b: dict) -> dict:
    """Stufe A ist fertig: alte Sitzung schließen, Stufe B (Szenen bis fertig) in einer frischen Sitzung mit dem Bau-Modell."""
    _beenden(b)
    erg, neu = _sitzung_starten('autobau-b', cfg, folge=b['folge'])
    neu.update(folge=b['folge'], stufe='B', bau_start=b.get('bau_start') or b['start'],
               stufen=(b.get('stufen') or []) + [{'stufe': 'A', 'sitzung': b.get('sitzung') or b.get('log'), 'ende': _ms.jetzt()}])
    merke(f'Folge {b["folge"]}: Stufe A fertig, Stufe B gestartet ({neu.get("sitzung") or "ohne Fenster"}, {_konfig.anzeige(cfg["modell"])})')
    return neu


def aufraeumen(z: dict, jetzt: datetime) -> None:
    """Bauten nachsehen: Stufe A fertig (Stufe B starten), Folge fertig, beendet, Limit erreicht, läuft zu lange."""
    sitzungen = {s['name']: s for s in (starten.liste() if starten._tmux() else [])}
    cfg, alle = konfig(), _folgen()
    bleiben = []
    for b in z.get('baue') or []:
        alter_h = (jetzt - datetime.fromisoformat(b.get('bau_start') or b['start'])).total_seconds() / 3600
        b['folge'] = folge_von(b, alle)
        st = _status(b['folge'])
        if b.get('stufe') == 'A' and st.get('stufe') == 'A-fertig':
            try:
                bleiben.append(stufe_b(cfg, b))
            except SystemExit as e:
                merke(f'Folge {b["folge"]}: Stufe B ließ sich nicht starten: {e}', 'fehler')
            continue
        fertig = st.get('phase') in ('fertig', 'geplant', 'gepostet')
        name = b.get('sitzung') or b.get('log')
        if b.get('art') == 'tmux':
            s = sitzungen.get(b['sitzung'])
            if not s or s.get('tot'):
                merke(f'Bau {name} beendet ({alter_h:.1f} h)' + ('' if fertig or not b['folge'] else f', Folge {b["folge"]} steht in Phase {st.get("phase")}'),
                      'fertig' if fertig else 'warnung')
                if s and s.get('tot'):
                    _beenden(b)
                continue
            text = '\n'.join(s.get('zeilen') or [])
            if LIMIT_RE.search(text):
                limit_merken(z, text, jetzt)
            # Abgerissene Verbindung zur API (kommt vor): selbst „weiter“ schicken statt auf den Nutzer zu warten, höchstens 3 Mal je Bau
            elif s.get('zustand') == 'fehler' and API_RE.search(str(s.get('grund') or '')) and b.get('weiter', 0) < 3:
                try:
                    starten.weiter(b['sitzung'], wer='autopilot', protokoll=False)
                    b['weiter'] = b.get('weiter', 0) + 1
                    merke(f'Bau {name}: API-Abbruch, „weiter“ geschickt ({b["weiter"]}/3).', 'warnung')
                except SystemExit:
                    pass
            if s.get('zustand') == 'wartet' and not s.get('frage') and (s.get('macht') or {}).get('art') == 'wartet' \
                    and (s.get('still_seit', 0) >= ERLEDIGT_S or (fertig and s.get('still_seit', 0) >= 120)):
                _beenden(b)
                merke(f'Bau {name} fertig, Sitzung geschlossen ({alter_h:.1f} h).', 'fertig')
                continue
        else:
            if not _pid_lebt(int(b.get('pid') or 0)):
                merke(f'Bau {name} beendet ({alter_h:.1f} h).', 'fertig' if fertig else 'warnung')
                continue
            try:
                ende = Path(b['log']).read_text(encoding='utf-8', errors='replace')[-4000:]
                if LIMIT_RE.search(ende):
                    limit_merken(z, ende, jetzt)
            except OSError:
                pass
        if alter_h > float(cfg.get('max_stunden') or 6) and not b.get('gewarnt'):
            merke(f'Bau {name} läuft schon {alter_h:.1f} h. Bitte im Studio nachsehen.', 'warnung')
            b['gewarnt'] = True
        bleiben.append(b)
    z['baue'] = bleiben
    posten_aufraeumen(z, sitzungen, jetzt)


# ---------------------------------------------------------------- Gründe, Bauen, Posten

def stopp(cfg: dict, z: dict, jetzt: datetime) -> tuple[str, str] | None:
    """None = ein Bau darf starten, sonst (art, Grund in Klartext). Arten: aus, limit, kanal, fenster, tagesziel, parallel,
    bremse, puffer. Das Studio zeigt puffer rot, limit und bremse gelb."""
    if not cfg['an']:
        return 'aus', 'Der Autopilot ist aus.'
    if z.get('limit_bis') and z['limit_bis'] > jetzt.isoformat(timespec='minutes'):
        return 'limit', (f'Claude-Nutzungslimit erreicht, Pause bis {z["limit_bis"][8:10]}.{z["limit_bis"][5:7]}. {z["limit_bis"][11:16]} Uhr'
                         + ('' if z.get('limit_reset', True) else ' (dann neuer Versuch)') + '.')
    if not cfg['kanal']:
        return 'kanal', 'Kein Kanal eingestellt (ms autopilot an --kanal <slug>).'
    if not kanal_bereit(cfg['kanal']):
        return 'kanal', f'Kanal {cfg["kanal"]} ist noch nicht fertig gelernt.'
    if not (_ms.arbeit() / '.claude' / 'skills' / f'stil-{cfg["kanal"]}' / 'SKILL.md').is_file():   # Kanäle von vor dem 31.10.2026
        return 'stil', (f'Kanal {cfg["kanal"]} hat noch keinen Stil-Skill (neu seit dem Update). Sag der Regie: '
                        f'„Leg den Stil-Skill für Kanal {cfg["kanal"]} an“, danach baut der Tagesbau weiter.')
    if not im_fenster(cfg, jetzt):
        return 'fenster', f'Gebaut wird zwischen {cfg["fenster"][0]} und {cfg["fenster"][1]} Uhr.'
    if (z.get('tage') or {}).get(jetzt.date().isoformat(), 0) >= int(cfg['pro_tag']):
        return 'tagesziel', f'Tagesziel erreicht ({cfg["pro_tag"]} {"Bau" if int(cfg["pro_tag"]) == 1 else "Bauten"}), morgen geht es weiter.'
    if len(z.get('baue') or []) >= int(cfg['parallel']):
        return 'parallel', f'{cfg["parallel"]} {"Bau läuft" if int(cfg["parallel"]) == 1 else "Bauten laufen"} gleichzeitig, das ist das Maximum.'
    w = z.get('woche') or {}
    if cfg.get('wochen_bremse') and w.get('prozent') is not None and float(w['prozent']) >= float(cfg['wochen_bremse']):
        return 'bremse', (f'Wochenbremse: geschätzt {w["prozent"]:.0f} % deines Wochenlimits verbraucht (Grenze {cfg["wochen_bremse"]} %). '
                          'Neue Bauten erst nach dem Reset, damit dir Claude für deine eigene Arbeit bleibt.')
    n = fertig_ungepostet(cfg['kanal'])
    if n + len(z.get('baue') or []) >= int(cfg['puffer']):
        return 'puffer', (f'Puffer voll: {n} fertige eigene {"Folge wartet" if n == 1 else "Folgen warten"} aufs Posten (Puffer {cfg["puffer"]}). '
                          'Poste sie (oder schalte das Posten an) oder erhöhe den Puffer, dann baut der Tagesbau weiter.')
    return None


def warum_nicht(cfg: dict, z: dict, jetzt: datetime) -> str | None:
    g = stopp(cfg, z, jetzt)
    return g[1] if g else None


def bau_starten(cfg: dict, z: dict, trocken=False, extra=False) -> dict:
    erg, eintrag = _sitzung_starten('autobau', cfg, kanal=cfg['kanal'], trocken=trocken)
    eintrag['stufe'] = 'A' if cfg['staffel'] else 'ganz'
    if trocken:
        return {'trocken': True, **erg}
    jetzt = datetime.now()
    if _ms.SYSTEM == 'Darwin' and shutil.which('caffeinate'):   # Mac während des Baus wach halten (Deckel offen)
        subprocess.Popen(['caffeinate', '-i', '-t', str(int(float(cfg['max_stunden']) * 3600))],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    z.setdefault('baue', []).append(eintrag)
    if not extra:
        tag = jetzt.date().isoformat()
        tage = z.setdefault('tage', {})
        tage[tag] = tage.get(tag, 0) + 1
        z['tage'] = dict(sorted(tage.items())[-14:])
    modell = cfg['modell_planung'] if cfg['staffel'] else cfg['modell']
    merke(f'Bau gestartet ({eintrag.get("sitzung") or "ohne Fenster"}, {"Stufe A, " if cfg["staffel"] else ""}{_konfig.anzeige(modell)})'
          + (', zusätzlich' if extra else ''))
    return erg


def posten_stopp(cfg: dict, z: dict, jetzt: datetime) -> tuple[tuple[str, str] | None, dict | None]:
    """(None, Folge) = jetzt posten, sonst ((art, Grund), None). Arten: aus, limit, laeuft, frei, zeit, heute, fehler, leer."""
    if not cfg['posten']:
        return ('aus', 'Automatisches Posten ist aus (ms autopilot posten an).'), None
    if z.get('limit_bis') and z['limit_bis'] > jetzt.isoformat(timespec='minutes'):
        return ('limit', 'Claude-Nutzungslimit erreicht, gepostet wird nach der Pause.'), None
    if z.get('post'):
        return ('laeuft', f'Gerade läuft ein Post ({z["post"].get("folge")}).'), None
    kanal = cfg['kanal']
    if not kanal:
        return ('frei', 'Kein Kanal eingestellt.'), None
    frei = _vorrat.freigaben(kanal)
    if not frei:
        return ('frei', 'Noch keine Plattform freigegeben. Erst einmal einrichten (erster Lauf stoppt vor „Veröffentlichen“): '
                        'im Studio „Posten einrichten“ oder ms starten posten-einrichten --kanal ' + kanal), None
    vr = _vorrat.vorrat(kanal, _folgen())
    kaputt = next((v for v in vr if v['fehler']), None)
    if kaputt:
        return ('fehler', f'Posten pausiert: „{kaputt["titel"]}“ ist gescheitert ({kaputt["grund"].split(": ", 1)[-1]}). '
                          f'Selbst hochladen oder neu versuchen, dann ms posten erledigt {kaputt["folge_id"]}.'), None
    if f'{jetzt:%H:%M}' < str(cfg['post_zeit']):
        return ('zeit', f'Gepostet wird ab {cfg["post_zeit"]} Uhr.'), None
    if (z.get('post_tage') or {}).get(jetzt.date().isoformat(), 0) >= int(cfg['posts_pro_tag']):
        return ('heute', 'Heute ist schon gepostet.'), None
    kand = next((v for v in vr if v['postbar'] and any(p in frei for p in v['offen'])), None)
    if not kand:
        return ('leer', 'Keine postbare eigene Folge im Vorrat.'), None
    return None, kand


def post_starten(cfg: dict, z: dict, kand: dict, trocken=False) -> dict:
    erg, eintrag = _sitzung_starten('autopost', cfg, folge=kand['folge_id'], trocken=trocken)
    if trocken:
        return {'trocken': True, **erg}
    eintrag.update(folge=kand['folge_id'], titel=kand['titel'])
    z['post'] = eintrag
    tag = datetime.now().date().isoformat()
    pt = z.setdefault('post_tage', {})
    pt[tag] = pt.get(tag, 0) + 1
    z['post_tage'] = dict(sorted(pt.items())[-14:])
    merke(f'Posten gestartet: „{kand["titel"]}“ ({eintrag.get("sitzung") or "ohne Fenster"})')
    return erg


def posten_aufraeumen(z: dict, sitzungen: dict, jetzt: datetime) -> None:
    """Läuft ein Post: fertig, wenn die Sitzung endet oder ohne Frage still wartet. Ohne Ergebnis in STATUS = Fehler (rot)."""
    p = z.get('post')
    if not p:
        return
    alter_min = (jetzt - datetime.fromisoformat(p['start'])).total_seconds() / 60
    if p.get('art') == 'tmux':
        s = sitzungen.get(p.get('sitzung'))
        if s and not s.get('tot'):
            text = '\n'.join(s.get('zeilen') or [])
            if LIMIT_RE.search(text):
                limit_merken(z, text, jetzt)
            ruhig = s.get('zustand') == 'wartet' and not s.get('frage') and s.get('still_seit', 0) >= 180
            if not ruhig and alter_min < 90:
                return
        _beenden(p)
    elif _pid_lebt(int(p.get('pid') or 0)) and alter_min < 90:
        return
    st = _status(p.get('folge'))
    neu = {k: v for k, v in _vorrat.posts(st).items() if isinstance(v, dict) and str(v.get('zeit') or '') >= p['start'][:16]}
    if not neu:
        import posten
        frei = [x for x in _vorrat.freigaben(str(st.get('kanal') or '')) if x in _vorrat.offen_auf(st, list(_vorrat.PLATTFORMEN))]
        try:
            posten.ergebnis(p['folge'], (frei or ['instagram'])[0], None,
                            f'Posten-Sitzung endete nach {alter_min:.0f} min ohne Ergebnis (Log: {p.get("sitzung") or p.get("log")})')
        except SystemExit:
            pass
        ok, text = False, 'ohne Ergebnis beendet'
    else:
        ok = all(v.get('ok') for v in neu.values())
        text = ', '.join(f'{_vorrat.NAMEN.get(k, k)} {"ok" if v.get("ok") else "Fehler"}' for k, v in neu.items())
    z['post_letzt'] = {'folge': p.get('folge'), 'titel': p.get('titel'), 'ok': ok, 'text': text, 'zeit': _ms.jetzt()}
    z['post'] = None
    merke(f'Posten „{p.get("titel")}“: {text}', 'fertig' if ok else 'fehler')


def lauf(trocken=False) -> dict:
    with sperre():
        cfg, z, jetzt = konfig(), zustand(), datetime.now()
        aufraeumen(z, jetzt)
        if cfg['an']:
            woche(cfg, z, messen=True)
        g = stopp(cfg, z, jetzt)
        erg = {'gestartet': False, 'grund': g[1] if g else None, 'stopp': g[0] if g else None}
        while g is None:
            erg.update(bau_starten(cfg, z, trocken=trocken))
            erg['gestartet'] = True
            if trocken:
                break
            g = stopp(cfg, z, datetime.now())
        pg, kand = posten_stopp(cfg, z, jetzt)
        erg['posten'] = {'gestartet': False, 'grund': pg[1] if pg else None, 'stopp': pg[0] if pg else None}
        if kand:
            erg['posten'].update(post_starten(cfg, z, kand, trocken=trocken), gestartet=True, folge=kand['folge_id'])
        z['letzter_lauf'] = jetzt.isoformat(timespec='seconds')
        if not trocken:
            zustand_schreiben(z)
        return erg


def stand() -> dict:
    """Für Terminal und Studio (Panel STEUERUNG, Kopfzeile, Vorrat). Misst nichts neu (das macht lauf)."""
    cfg, z, jetzt = konfig(), zustand(), datetime.now()
    heute = (z.get('tage') or {}).get(jetzt.date().isoformat(), 0)
    g = stopp(cfg, z, jetzt)
    pg, kand = posten_stopp(cfg, z, jetzt)
    return {'konfig': cfg, 'heute': heute, 'laufend': len(z.get('baue') or []), 'baue': z.get('baue') or [],
            'grund': g[1] if g else None, 'stopp': g[0] if g else None, 'zeitplan': zeitplan_da(),
            'letzter_lauf': z.get('letzter_lauf'), 'limit_bis': z.get('limit_bis'), 'woche': z.get('woche') or {},
            'puffer_belegt': fertig_ungepostet(cfg['kanal']) if cfg['kanal'] else 0,
            'posten': {'an': bool(cfg['posten']), 'grund': pg[1] if pg else None, 'stopp': pg[0] if pg else None,
                       'naechste': kand, 'laeuft': z.get('post'), 'letzt': z.get('post_letzt')}}


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


def _stand_text(s: dict) -> str:
    c, w, po = s['konfig'], s['woche'], s['posten']
    proz = f'{w["prozent"]:.0f} %' if w.get('prozent') is not None else (w.get('grund') or 'noch nicht gemessen')
    z = [f'Autopilot: {"an" if c["an"] else "aus"} · Kanal {c["kanal"] or "–"} · Abo {c["abo"] or "nicht eingestellt"} · '
         f'{s["heute"]} von {c["pro_tag"]} Bauten heute · {s["laufend"]} laufen (max. {c["parallel"]}) · {c["fenster"][0]}–{c["fenster"][1]} Uhr',
         f'Modelle: Planung (Stufe A) {_konfig.anzeige(c["modell_planung"])} · Bau (Stufe B) {_konfig.anzeige(c["modell"])} · '
         f'Regie im Gespräch {_konfig.anzeige(c["modell_regie"])} · Helfer {_konfig.anzeige(c["modell_helfer"])}'
         + ('' if c['staffel'] else ' · Staffel aus: eine Sitzung je Folge mit dem Bau-Modell'),
         f'MCP in Bau-Sitzungen: Stimme {c["mcp_stimme"] if c["mcp_stimme"] == "alle" else (", ".join(c["mcp_stimme"]) or "keine")}, '
         f'Posten nur Claude in Chrome',
         f'Woche: {proz} vom Limit (Bremse {c["wochen_bremse"] or "aus"} %) · Puffer {s["puffer_belegt"]}/{c["puffer"]} eigene Folgen',
         f'Zeitplan: {"aktiv" if s["zeitplan"] else "fehlt (ms autopilot einrichten)"}',
         f'Jetzt: {s["grund"] or "der nächste Durchlauf startet einen Bau"}',
         f'Posten: {"an" if po["an"] else "aus"} · ' + (po['grund'] or f'nächster Post: {po["naechste"]["titel"]}')]
    z += [f'  läuft: {b.get("sitzung") or b.get("log")} seit {b["start"][11:16]}' + (f' (Stufe {b["stufe"]}, {b.get("folge") or "Folge noch offen"})' if b.get('stufe') else '')
          for b in s['baue']]
    return '\n'.join(z)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('was', nargs='?', default='stand',
                    choices=['stand', 'an', 'einstellen', 'aus', 'lauf', 'jetzt', 'einrichten', 'austragen', 'abo', 'posten', 'anstossen'])
    ap.add_argument('wert', nargs='?', help='bei abo: pro|max5|max20, bei posten: an|aus')
    ap.add_argument('--kanal')
    ap.add_argument('--pro-tag', type=int)
    ap.add_argument('--parallel', type=int)
    ap.add_argument('--fenster', help='z. B. 08:00-22:00')
    ap.add_argument('--modell', help='Bau-Modell (Stufe B): sonnet (Standard), opus oder fable')
    ap.add_argument('--modell-planung', help='Stufe A: opus (Standard) oder sonnet')
    ap.add_argument('--modell-regie', help='Regie in Sitzungen aus dem Studio: opusplan (Standard), sonnet oder opus')
    ap.add_argument('--modell-helfer', help='Bauer, Prüfer, Analyse: sonnet (Standard) oder opus (die Regie gibt es beim Agent-Tool mit)')
    ap.add_argument('--mcp-stimme', help='MCP-Server für die Stimme in Bau-Sitzungen: voicestudio, alle oder keine')
    ap.add_argument('--puffer', type=int)
    ap.add_argument('--bremse', type=int, help='Wochenbremse in Prozent des Wochenlimits (0 = aus)')
    ap.add_argument('--staffel', choices=['an', 'aus'])
    ap.add_argument('--zeit', help='bei posten: ab wann gepostet wird, z. B. 18:00')
    ap.add_argument('--trocken', action='store_true')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    def aus(d, text):
        print(json.dumps(d, ensure_ascii=False, indent=1, default=str) if a.json else text)

    if a.was == 'stand':
        s = stand()
        return aus(s, _stand_text(s))
    if a.was == 'abo':
        if a.wert not in _konfig.ABO:
            raise SystemExit('FEHLER: ms autopilot abo pro|max5|max20')
        cfg = _konfig.abo_setzen(konfig(), a.wert)
        if not a.trocken:
            konfig_schreiben(cfg)
        return aus({'ok': True, 'konfig': cfg, 'text': _konfig.ABO[a.wert]['text']},
                   f'{_konfig.ABO[a.wert]["text"]}\nEingestellt: {cfg["pro_tag"]} pro Tag, {cfg["parallel"]} gleichzeitig, Wochenbremse {cfg["wochen_bremse"]} %.')
    if a.was == 'posten':
        cfg = konfig()
        if a.wert not in ('an', 'aus', None):
            raise SystemExit('FEHLER: ms autopilot posten an|aus [--zeit 18:00] [--pro-tag 1]')
        if a.wert:
            cfg['posten'] = a.wert == 'an'
        if a.zeit:
            cfg['post_zeit'] = _zeit(a.zeit)
        if a.pro_tag is not None:
            if not 1 <= a.pro_tag <= 5:
                raise SystemExit('FEHLER: --pro-tag beim Posten zwischen 1 und 5.')
            cfg['posts_pro_tag'] = a.pro_tag
        if not a.trocken:
            konfig_schreiben(cfg)
            merke(f'Posten {"an" if cfg["posten"] else "aus"} (ab {cfg["post_zeit"]} Uhr, {cfg["posts_pro_tag"]} am Tag)')
        pg, _ = posten_stopp(cfg, zustand(), datetime.now())
        return aus({'ok': True, 'konfig': cfg, 'grund': pg[1] if pg else None},
                   f'Posten ist {"an" if cfg["posten"] else "aus"}: ab {cfg["post_zeit"]} Uhr, {cfg["posts_pro_tag"]} am Tag.'
                   + (f' Gerade: {pg[1]}' if pg and cfg['posten'] else ''))
    if a.was in ('an', 'einstellen'):
        cfg = konfig()
        if a.kanal:
            cfg['kanal'] = starten._kanal_pruefen(a.kanal)
        for feld, wert in (('pro_tag', a.pro_tag), ('parallel', a.parallel), ('puffer', a.puffer)):
            if wert is not None:
                if not 1 <= wert <= 20:
                    raise SystemExit(f'FEHLER: {feld} zwischen 1 und 20.')
                cfg[feld] = wert
        if a.bremse is not None:
            if not 0 <= a.bremse <= 100:
                raise SystemExit('FEHLER: --bremse zwischen 0 (aus) und 100.')
            cfg['wochen_bremse'] = a.bremse
        if a.staffel:
            cfg['staffel'] = a.staffel == 'an'
        if a.modell_helfer:
            if a.modell_helfer not in _konfig.HELFER:
                raise SystemExit(f'FEHLER: --modell-helfer {", ".join(_konfig.HELFER)}')
            cfg['modell_helfer'] = a.modell_helfer
        if a.mcp_stimme:
            w = a.mcp_stimme.strip().lower()
            if w == 'alle':
                cfg['mcp_stimme'] = 'alle'
            elif w in ('keine', 'aus', '-'):
                cfg['mcp_stimme'] = []
            elif re.match(r'^[a-z0-9_.-]+(,[a-z0-9_.-]+)*$', w):
                cfg['mcp_stimme'] = w.split(',')
            else:
                raise SystemExit('FEHLER: --mcp-stimme voicestudio | alle | keine (mehrere mit Komma)')
        if a.fenster:
            von, _, bis = a.fenster.partition('-')
            cfg['fenster'] = [_zeit(von), _zeit(bis)]
        for feld, wert in (('modell', a.modell), ('modell_planung', a.modell_planung), ('modell_regie', a.modell_regie)):
            if wert:
                if not re.match(r'^[a-z0-9.\[\]-]{3,40}$', wert):
                    raise SystemExit(f'FEHLER: Modell „{wert}“ sieht nicht gültig aus (sonnet, opus, opusplan, fable).')
                cfg[feld] = _konfig.MODELLE.get(wert, wert)
        if a.was == 'einstellen':
            if not a.trocken:
                konfig_schreiben(cfg)
            return aus({'ok': True, 'konfig': cfg}, f'Eingestellt: {cfg["pro_tag"]} pro Tag, {cfg["parallel"]} gleichzeitig, '
                                                     f'{cfg["fenster"][0]}–{cfg["fenster"][1]} Uhr, Puffer {cfg["puffer"]}, Bremse {cfg["wochen_bremse"]} %. '
                                                     f'Autopilot ist {"an" if cfg["an"] else "aus"}.')
        if not cfg['kanal']:
            raise SystemExit('FEHLER: Welcher Kanal? ms autopilot an --kanal <slug> (ms status zeigt die Kanäle).')
        cfg['an'] = True
        if not a.trocken:
            konfig_schreiben(cfg)
            merke(f'Autopilot an: Kanal {cfg["kanal"]}, {cfg["pro_tag"]} pro Tag, {cfg["parallel"]} gleichzeitig')
        hinweis = '' if zeitplan_da() else ' Der Zeitplan fehlt noch: ms autopilot einrichten.'
        if not cfg['abo']:
            hinweis += ' Abo noch nicht eingestellt (ms autopilot abo pro|max5|max20), die Wochenbremse schätzt ohne Abo nichts.'
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
        text = ('Bau gestartet.' if e['gestartet'] else 'Kein Bau gestartet: ' + str(e['grund']))
        if e.get('trocken'):
            text = 'Trocken, nichts gestartet. Würde bauen: ' + str(e.get('start_text') or e.get('befehl_text'))
        po = e.get('posten') or {}
        text += '\nPosten: ' + ('gestartet.' if po.get('gestartet') and not po.get('trocken') else
                                 f'würde {po.get("folge")} posten.' if po.get('gestartet') else str(po.get('grund')))
        return aus(e, text)
    if a.was == 'anstossen':
        for i in range(8):                       # wie reel-studio staffel.py: erst warten, bis die Stufe-A-Sitzung zur Ruhe kommt
            time.sleep(20 if i == 0 else 30)
            try:
                e = lauf()
                return aus(e, 'Durchlauf angestoßen.')
            except SystemExit:                   # anderer Durchlauf hält die Sperre
                continue
        return aus({'ok': False}, 'Durchlauf nicht möglich, die Sperre war 4 min belegt. Der Zeitplan holt es nach.')
    if a.was == 'jetzt':
        cfg = konfig()
        if not cfg['kanal']:
            raise SystemExit('FEHLER: Kein Kanal eingestellt (ms autopilot an --kanal <slug>).')
        with sperre():
            z = zustand()
            e = bau_starten(cfg, z, trocken=a.trocken, extra=True)
            if not a.trocken:
                zustand_schreiben(z)
        return aus(e, 'Bau gestartet (zusätzlich).' if not e.get('trocken') else f'Trocken: {e.get("start_text") or e.get("befehl_text")}')
    if a.was == 'einrichten':
        return aus({'ok': True}, einrichten(trocken=a.trocken))
    if a.was == 'austragen':
        return aus({'ok': True}, austragen())


if __name__ == '__main__':
    main()
