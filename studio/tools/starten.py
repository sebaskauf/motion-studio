"""Agenten starten und laufende Agenten-Sitzungen steuern (feste Aufträge, tmux oder neues Terminalfenster).
Aufträge (startet `claude --agent motion-regie "<Auftrag>"` im Arbeitsordner):
  ms starten einrichten                          Richte Motion-Studio mit mir ein.
  ms starten vorlagen --kanal <k>                Finde neue Vorlagen für Kanal <k> (Kosten nur nach Ja)
  ms starten kanal-lernen --url <link|@handle>   Lerne den Kanal: zerlegen, Pilot 1:1 nachbauen, messen, Baukasten
  ms starten folge --kanal <k>                   Bau die nächste Folge für Kanal <k>.
  ms starten weiter [--folge <id>]               Mach bei der offenen Arbeit (oder dieser Folge) weiter.
  ms starten pruefen --folge <id>                Folge unabhängig prüfen lassen
  Zusatz: --trocken zeigt nur den Befehl, startet nichts.
Sitzungen (nur tmux-Sitzungen mit Präfix ms-, fremde werden nie angefasst):
  ms starten liste [--json]                      alle ms-Sitzungen mit Zustand (arbeitet, wartet, fehler, beendet)
  ms starten zeige <sitzung> [--zeilen 40]       letzte Terminalzeilen
  ms starten weiter <sitzung>                    schickt „weiter“ + Enter (z. B. nach „API Error“)
  ms starten oeffnen <sitzung>                   Terminalfenster zum Zuschauen öffnen (Mac), sonst Befehl ausgeben
  ms starten stopp <sitzung>                     Sitzung beenden
Mit tmux (Mac/Linux): Sitzung ms-<auftrag>-<MMTT-HHMM> läuft unsichtbar weiter, zuschauen mit `tmux attach -t <sitzung>`.
Ohne tmux (Windows): neues Terminalfenster, das Dashboard zeigt dann nur den Live-Log.
Jede Sitzung bekommt MS_ARBEIT und, wenn der Claude-Ordner vom Standard ~/.claude abweicht (CLAUDE_CONFIG_DIR oder
config.json "claude_ordner"), auch CLAUDE_CONFIG_DIR, sonst findet sie motion-regie nicht. --trocken zeigt beides.
Umgebung: MS_CLAUDE_BEFEHL ersetzt den claude-Aufruf (für Tests, z. B. "bash -c 'echo API Error; sleep 600'"),
          MS_KEINE_FENSTER=1 öffnet keine Fenster (nur Befehl ausgeben)."""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import _ms

AGENT = 'motion-regie'
AUFTRAEGE = ['einrichten', 'vorlagen', 'kanal-lernen', 'folge', 'weiter', 'pruefen']
SITZUNG_RE = re.compile(r'^ms-[a-z0-9][a-z0-9-]{0,62}$')
KANAL_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$')
FOLGE_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$')
# Link: nur unkritische Zeichen (keine Anführungszeichen, kein ; % ^ ! < > | ` $ \ und keine Leerzeichen)
URL_RE = re.compile(r'^https?://[A-Za-z0-9.-]+(?::\d{1,5})?(?:/[A-Za-z0-9._~/?#@&=+,:-]*)?$')
HANDLE_RE = re.compile(r'^@?[A-Za-z0-9._-]{1,60}$')

AKTIV_S = 6          # so lange nach der letzten Ausgabe gilt eine Sitzung als „arbeitet“
HAENGER_S = 300      # keine Ausgabe trotz „esc to interrupt“ = Hänger
FEHLER_RE = re.compile(
    r'API Error|overloaded|rate.?limit|usage limit|limit reached|Too Many Requests|Request timed out|'
    r'Connection error|fetch failed|Credit balance|Internal server error|ECONNRESET|ETIMEDOUT|'
    r'^\W{0,6}(Error|Fehler|FEHLER)\b\s*[:!]', re.I | re.M)
MENUE_RE = re.compile(r'Do you want|Möchtest du|❯\s*1\.|\(y/n\)|\[y/N\]|\[Y/n\]', re.I)
LAEUFT_RE = re.compile(r'esc to interrupt', re.I)


# ---------------------------------------------------------------- Aufträge

def _kanal_pruefen(kanal):
    if not kanal:
        raise SystemExit('FEHLER: --kanal fehlt. Welcher Kanal? (ms status --alle zeigt alle)')
    if not KANAL_RE.match(kanal) or not (_ms.arbeit() / 'kanaele' / kanal / 'STATUS.json').exists():
        raise SystemExit(f'FEHLER: Kanal "{kanal}" gibt es nicht. Erst einen Kanal lernen (ms starten kanal-lernen --url …).')
    return kanal


def _folge_pruefen(folge):
    if not folge:
        raise SystemExit('FEHLER: --folge fehlt.')
    if not FOLGE_RE.match(folge) or '..' in folge or not (_ms.arbeit() / 'folgen' / folge / 'STATUS.json').exists():
        raise SystemExit(f'FEHLER: Folge "{folge}" gibt es nicht (ms status --alle zeigt alle).')
    return folge


def _url_pruefen(url):
    url = (url or '').strip()
    if not url:
        raise SystemExit('FEHLER: --url fehlt (Link zum Kanal oder @handle).')
    if len(url) > 300 or not (URL_RE.match(url) or HANDLE_RE.match(url)):
        raise SystemExit('FEHLER: Das sieht nicht wie ein Link (https://…) oder @handle aus.')
    return url


def auftrag_text(art: str, kanal=None, url=None, folge=None) -> str:
    """Feste Auftrags-Vorlagen. Nur geprüfte Werte werden eingesetzt, nie freier Text."""
    if art == 'einrichten':
        return 'Richte Motion-Studio mit mir ein.'
    if art == 'vorlagen':
        k = _kanal_pruefen(kanal)
        return f'Finde neue Vorlagen für Kanal {k}. Nenne vor jedem bezahlten Lauf die Kosten und frag mich.'
    if art == 'kanal-lernen':
        u = _url_pruefen(url)
        return f'Lerne den Kanal {u}: zerlegen, Pilot 1:1 nachbauen, messen, Baukasten.'
    if art == 'folge':
        k = _kanal_pruefen(kanal)
        return f'Bau die nächste Folge für Kanal {k}.'
    if art == 'weiter':
        if folge:
            return f'Mach bei Folge {_folge_pruefen(folge)} weiter.'
        return 'Mach bei der offenen Arbeit weiter.'
    if art == 'pruefen':
        f = _folge_pruefen(folge)
        return f'Lass Folge {f} unabhängig von motion-pruefer prüfen und zeig mir die Befunde.'
    raise SystemExit(f'FEHLER: Auftrag "{art}" gibt es nicht. Erlaubt: {", ".join(AUFTRAEGE)}')


def _programm(name: str) -> str:
    """Absoluter Pfad (der tmux-Server hat evtl. einen anderen PATH)."""
    if os.path.isabs(name):
        return name
    return shutil.which(name) or name


def claude_befehl(text: str) -> list[str]:
    ersatz = os.environ.get('MS_CLAUDE_BEFEHL')
    basis = shlex.split(ersatz) if ersatz else ['claude']
    basis[0] = _programm(basis[0])
    return basis + ['--agent', AGENT, text]


def _tmux() -> str | None:
    return shutil.which('tmux')


def _arbeitsordner() -> Path:
    a = _ms.arbeit()
    return a if a.is_dir() else Path.home()


def _neuer_name(art: str) -> str:
    basis = f'ms-{art}-{datetime.now():%m%d-%H%M}'
    belegt = {s['name'] for s in liste()}
    name, n = basis, 2
    while name in belegt:
        name, n = f'{basis}-{n}', n + 1
    return name


def _agent_hinweis() -> str | None:
    if os.environ.get('MS_CLAUDE_BEFEHL'):
        return None
    if shutil.which('claude') is None:
        return 'Claude Code (Befehl "claude") nicht gefunden. Installation prüfen.'
    import _setup
    agenten = _setup.claude_ordner() / 'agents'          # CLAUDE_CONFIG_DIR, config.json "claude_ordner", sonst ~/.claude
    if not (agenten / f'{AGENT}.md').exists():
        return f'Agent {AGENT} nicht in {agenten} gefunden. Installation prüfen (./install.sh).'
    return None


def _umgebung() -> dict:
    """Umgebung, die jede Agenten-Sitzung braucht: MS_ARBEIT immer, CLAUDE_CONFIG_DIR nur, wenn der Claude-Ordner
    vom Standard ~/.claude abweicht (CLAUDE_CONFIG_DIR oder config.json "claude_ordner"). Sonst findet die Sitzung
    motion-regie nicht. Beim Standard bleibt die Variable weg, weil Claude Code mit ihr seine Einstellungen woanders sucht."""
    import _setup
    umg = {'MS_ARBEIT': str(_ms.arbeit())}
    cfg = _setup.claude_ordner()
    try:
        abweichend = cfg.resolve() != (Path.home() / '.claude').resolve()
    except OSError:
        abweichend = True
    if abweichend:
        umg['CLAUDE_CONFIG_DIR'] = str(cfg)
    return umg


def _as_text(s: str) -> str:
    """Text als AppleScript-Zeichenkette."""
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _fenster_aus() -> bool:
    return os.environ.get('MS_KEINE_FENSTER') == '1'


def starten(art: str, kanal=None, url=None, folge=None, trocken=False, wer='studio') -> dict:
    text = auftrag_text(art, kanal, url, folge)
    cmd = claude_befehl(text)
    cwd = _arbeitsordner()
    umg = _umgebung()
    aus = {'auftrag': art, 'text': text, 'befehl': cmd, 'befehl_text': shlex.join(cmd), 'ordner': str(cwd),
           'umgebung': umg, 'hinweis': _agent_hinweis()}
    tmux = _tmux()
    if tmux:
        name = _neuer_name(art)
        umgebung = [x for k, v in umg.items() for x in ('-e', f'{k}={v}')] + ['-e', f'PATH={os.environ.get("PATH", "")}']
        tcmd = [tmux, '-u', 'new-session', '-d', '-s', name, '-x', '120', '-y', '36', '-c', str(cwd), *umgebung, *cmd,
                ';', 'set-option', '-w', '-t', f'={name}:', 'remain-on-exit', 'on',
                ';', 'set-option', '-t', f'={name}:', '@ms_auftrag', text,
                ';', 'set-option', '-t', f'={name}:', '@ms_art', art]
        anzeige = [x for i, x in enumerate(tcmd)  # PATH ist lang und uninteressant: aus der Anzeige nehmen
                   if not x.startswith('PATH=') and not (x == '-e' and tcmd[i + 1].startswith('PATH='))]
        aus.update({'sitzung': name, 'tmux': True, 'zuschauen': f'tmux attach -t {name}',
                    'start_text': shlex.join(anzeige)})
        if trocken:
            aus['trocken'] = True
            return aus
        if not os.environ.get('MS_CLAUDE_BEFEHL') and shutil.which('claude') is None:
            raise SystemExit('FEHLER: Claude Code (Befehl "claude") nicht gefunden. Erst installieren (Skill motion-setup).')
        r = subprocess.run(tcmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f'FEHLER: tmux konnte die Sitzung nicht starten: {(r.stderr or "").strip()[:300]}')
        time.sleep(0.4)
        info = next((s for s in liste() if s['name'] == name), None)
        if not info:
            raise SystemExit('FEHLER: Sitzung sofort wieder weg. Mit --trocken den Befehl ansehen und von Hand testen.')
        if info['tot']:
            letzte = ' | '.join(info['zeilen'][-4:])
            raise SystemExit(f'FEHLER: Agent sofort beendet (Code {info.get("exit_code")}): {letzte[:300]}')
        _ms.log(f'Agent gestartet: {text} (Sitzung {name})', wer=wer, art='info')
        return aus

    # ohne tmux: neues Terminalfenster. Die Umgebung (MS_ARBEIT, ggf. CLAUDE_CONFIG_DIR) geht mit:
    # Mac als Zuweisung vor dem Befehl in der Terminal-Zeile, sonst über env des neuen Prozesses.
    aus['tmux'] = False
    env_neu = dict(os.environ, **umg)
    zuweisung = ' '.join(f'{k}={shlex.quote(v)}' for k, v in umg.items())
    if _ms.SYSTEM == 'Darwin':
        aus['start_text'] = f'cd {shlex.quote(str(cwd))} && {zuweisung} {shlex.join(cmd)}'
    elif _ms.SYSTEM == 'Windows':
        # wt reicht die Umgebung nicht in jeder Version an den neuen Tab weiter: mit eigenem Claude-Ordner deshalb cmd
        aus['start_text'] = ('cmd /k ' if ('CLAUDE_CONFIG_DIR' in umg or not shutil.which('wt')) else 'wt cmd /k ') + \
            subprocess.list2cmdline(cmd)
    else:
        aus['start_text'] = f'{zuweisung} {shlex.join(cmd)}'
    if trocken:
        aus['trocken'] = True
        return aus
    if not os.environ.get('MS_CLAUDE_BEFEHL') and shutil.which('claude') is None:
        raise SystemExit('FEHLER: Claude Code (Befehl "claude") nicht gefunden. Erst installieren (Skill motion-setup).')
    if _ms.SYSTEM == 'Windows':
        if shutil.which('wt') and 'CLAUDE_CONFIG_DIR' not in umg:
            subprocess.Popen(['wt', '-d', str(cwd), 'cmd', '/k', *cmd], cwd=str(cwd), env=env_neu)
        else:
            subprocess.Popen(['cmd', '/k', *cmd], cwd=str(cwd), env=env_neu,
                             creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0x10))
    elif _ms.SYSTEM == 'Darwin':
        subprocess.run(['osascript', '-e', 'tell application "Terminal"', '-e', 'activate',
                        '-e', f'do script {_as_text(aus["start_text"])}', '-e', 'end tell'], capture_output=True, check=False)
    else:
        term = shutil.which('x-terminal-emulator') or shutil.which('gnome-terminal') or shutil.which('konsole') \
            or shutil.which('xterm')
        if not term:
            raise SystemExit('FEHLER: Kein tmux und kein Terminal gefunden. tmux installieren oder den Befehl selbst '
                             f'im Ordner {cwd} ausführen:\n  {aus["start_text"]}')
        if term.endswith('gnome-terminal'):
            subprocess.Popen([term, '--', *cmd], cwd=str(cwd), env=env_neu)
        else:
            subprocess.Popen([term, '-e', *cmd], cwd=str(cwd), env=env_neu)
    aus['fenster'] = True
    _ms.log(f'Agent gestartet (eigenes Fenster): {text}', wer=wer, art='info')
    return aus


# ---------------------------------------------------------------- Sitzungen

def _tmux_lauf(args, pruefen=False) -> subprocess.CompletedProcess:
    tmux = _tmux()
    if not tmux:
        raise SystemExit('FEHLER: tmux fehlt. Ohne tmux laufen Agenten in eigenen Fenstern.')
    r = subprocess.run([tmux, '-u', *args], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if pruefen and r.returncode != 0:
        raise SystemExit(f'FEHLER: tmux {args[0]}: {(r.stderr or "").strip()[:300]}')
    return r


def _bildschirm(name: str, zeilen: int = 0) -> list[str]:
    args = ['capture-pane', '-p', '-J', '-t', f'={name}:']
    if zeilen:
        args += ['-S', f'-{int(zeilen)}']
    r = _tmux_lauf(args)
    out = [z.rstrip() for z in (r.stdout or '').splitlines() if not z.startswith('Pane is dead')]
    while out and not out[-1].strip():
        out.pop()
    while out and not out[0].strip():
        out.pop(0)
    return out


def _zustand(zeilen: list[str], tot: bool, still: int, exit_code) -> tuple[str, str, bool]:
    """(zustand, grund, haenger). Zustände: arbeitet | wartet | fehler | beendet."""
    rest = [z for z in zeilen if z.strip()]
    unten = '\n'.join(rest[-15:])
    if tot:
        return 'beendet', (f'beendet (Code {exit_code})' if exit_code not in (None, '', '0', 0) else 'beendet'), False
    if still < AKTIV_S:
        return 'arbeitet', '', False
    fehler = [z.strip(' │|>⎿●*') for z in rest[-15:] if FEHLER_RE.search(z)]
    if fehler:
        return 'fehler', fehler[-1][:200], False
    if still >= HAENGER_S and LAEUFT_RE.search(unten):
        return 'fehler', f'keine Ausgabe seit {still // 60} Min.', True
    if MENUE_RE.search(unten):
        return 'wartet', 'fragt nach einer Auswahl im Terminal', False
    return 'wartet', 'wartet auf Eingabe', False


def liste(muster: re.Pattern | None = None) -> list[dict]:
    """Alle tmux-Sitzungen mit Präfix ms- (oder passend zu `muster`, z. B. für einen Dashboard-Adapter mit eigenem Präfix).
    Ohne tmux oder ohne Server: leere Liste."""
    muster = muster or SITZUNG_RE
    if not _tmux():
        return []
    fmt = '\t'.join(['#{session_name}', '#{window_activity}', '#{pane_dead}', '#{pane_dead_status}',
                     '#{session_created}', '#{@ms_art}', '#{session_attached}', '#{@ms_auftrag}'])
    r = _tmux_lauf(['list-panes', '-a', '-F', fmt])
    if r.returncode != 0:
        return []
    jetzt = int(time.time())
    aus, gesehen = [], set()
    for zeile in (r.stdout or '').splitlines():
        teile = zeile.split('\t')
        if len(teile) < 8:
            continue
        name, aktiv, tot, code, erstellt, art, angehaengt, auftrag = teile[:8]
        if not muster.match(name) or name in gesehen:
            continue
        gesehen.add(name)
        zeilen = _bildschirm(name, 60)  # etwas History mitlesen: beim Beenden rutscht Text nach oben weg
        still = max(0, jetzt - int(aktiv or jetzt))
        zustand, grund, haenger = _zustand(zeilen, tot == '1', still, code or None)
        aus.append({
            'name': name, 'art': art, 'auftrag': auftrag, 'zustand': zustand, 'grund': grund, 'haenger': haenger,
            'still_seit': still, 'tot': tot == '1', 'exit_code': code or None, 'angehaengt': angehaengt not in ('', '0'),
            'letzte_ausgabe': datetime.fromtimestamp(int(aktiv or jetzt)).astimezone().isoformat(timespec='seconds'),
            'erstellt': datetime.fromtimestamp(int(erstellt or jetzt)).astimezone().isoformat(timespec='seconds'),
            'zeilen': zeilen[-14:], 'zuschauen': f'tmux attach -t {name}'})
    aus.sort(key=lambda s: s['erstellt'], reverse=True)
    return aus


def _sitzung(name: str, muster: re.Pattern | None = None) -> dict:
    if not name or not (muster or SITZUNG_RE).match(name):
        raise SystemExit('FEHLER: Nur Motion-Studio-Sitzungen (Name beginnt mit ms-) sind erlaubt.' if muster is None
                         else 'FEHLER: Diese Sitzung gehört nicht zu dieser Pipeline.')
    s = next((x for x in liste(muster) if x['name'] == name), None)
    if not s:
        raise SystemExit(f'FEHLER: Sitzung {name} gibt es nicht (ms starten liste).')
    return s


def zeige(name: str, zeilen: int = 40) -> list[str]:
    _sitzung(name)
    return _bildschirm(name, zeilen)[-zeilen:]


def weiter(name: str, wer='studio', muster: re.Pattern | None = None, protokoll=True) -> dict:
    """muster/protokoll: für Adapter mit eigenem Sitzungs-Präfix (protokoll=False schreibt nicht ins Motion-Studio-Log)."""
    s = _sitzung(name, muster)
    if s['tot']:
        raise SystemExit(f'FEHLER: Sitzung {name} ist beendet. Neu starten statt weiter.')
    _tmux_lauf(['send-keys', '-t', f'={name}:', '-l', 'weiter'], pruefen=True)
    time.sleep(0.4)  # sonst hält die Oberfläche Text + Enter für eingefügten Text
    _tmux_lauf(['send-keys', '-t', f'={name}:', 'Enter'], pruefen=True)
    if protokoll:
        _ms.log(f'„weiter“ an Sitzung {name} geschickt', wer=wer, art='info')
    return {'sitzung': name, 'gesendet': 'weiter'}


def antworten(name: str, text: str, wer='studio', muster: re.Pattern | None = None, protokoll=True) -> dict:
    """Schickt eine Antwort des Nutzers (aus dem Dashboard) als eine Zeile + Enter in die Sitzung (Sebastian 20.10.2026:
    „Da sollte es einen Knopf geben“, statt im Terminal antworten zu müssen). Zeilenumbrüche werden zu Leerzeichen,
    sonst schickt die Claude-Oberfläche den Text schon beim ersten Umbruch ab."""
    text = ' '.join(str(text or '').split())
    if not text:
        raise SystemExit('FEHLER: Antwort ist leer.')
    if len(text) > 2000:
        raise SystemExit('FEHLER: Antwort ist zu lang (höchstens 2000 Zeichen).')
    s = _sitzung(name, muster)
    if s['tot']:
        raise SystemExit(f'FEHLER: Sitzung {name} ist beendet. Neu starten statt antworten.')
    _tmux_lauf(['send-keys', '-t', f'={name}:', '-l', text], pruefen=True)
    time.sleep(0.4)
    _tmux_lauf(['send-keys', '-t', f'={name}:', 'Enter'], pruefen=True)
    if protokoll:
        _ms.log(f'Antwort an Sitzung {name}: {text[:80]}', wer=wer, art='info')
    return {'sitzung': name, 'gesendet': text}


def oeffnen(name: str, muster: re.Pattern | None = None) -> dict:
    _sitzung(name, muster)
    tmux = _tmux()
    befehl = f'tmux attach -t {name}'
    if _fenster_aus():
        return {'sitzung': name, 'befehl': befehl, 'geoeffnet': False}
    if _ms.SYSTEM == 'Darwin':
        r = subprocess.run(['osascript', '-e', 'tell application "Terminal"', '-e', 'activate',
                            '-e', f'do script {_as_text(f"{shlex.quote(tmux)} attach -t {name}")}', '-e', 'end tell'],
                           capture_output=True, text=True)
        return {'sitzung': name, 'befehl': befehl, 'geoeffnet': r.returncode == 0}
    if _ms.SYSTEM == 'Linux' and os.environ.get('DISPLAY') and shutil.which('x-terminal-emulator'):
        subprocess.Popen(['x-terminal-emulator', '-e', tmux, 'attach', '-t', name])
        return {'sitzung': name, 'befehl': befehl, 'geoeffnet': True}
    return {'sitzung': name, 'befehl': befehl, 'geoeffnet': False}


def stopp(name: str, wer='studio', muster: re.Pattern | None = None, protokoll=True) -> dict:
    _sitzung(name, muster)
    _tmux_lauf(['kill-session', '-t', f'={name}'], pruefen=True)
    if protokoll:
        _ms.log(f'Sitzung {name} beendet', wer=wer, art='warnung')
    return {'sitzung': name, 'gestoppt': True}


# ---------------------------------------------------------------- Kommandozeile

def _dauer(s: int) -> str:
    return f'{s} s' if s < 90 else (f'{s // 60} Min.' if s < 5400 else f'{s // 3600} Std.')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('was', choices=AUFTRAEGE + ['liste', 'zeige', 'oeffnen', 'stopp'])
    ap.add_argument('sitzung', nargs='?', help='Name der Sitzung (ms-…) für zeige/weiter/oeffnen/stopp')
    ap.add_argument('--kanal')
    ap.add_argument('--url')
    ap.add_argument('--folge')
    ap.add_argument('--trocken', action='store_true', help='nur zeigen, nichts starten')
    ap.add_argument('--zeilen', type=int, default=40)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    def ausgabe(d, text):
        print(json.dumps(d, ensure_ascii=False, indent=1) if a.json else text)

    if a.was == 'liste':
        ls = liste()
        if a.json:
            print(json.dumps(ls, ensure_ascii=False, indent=1))
            return
        if not _tmux():
            print('tmux fehlt: Agenten laufen in eigenen Fenstern, hier gibt es keine Liste.')
            return
        if not ls:
            print('Keine Motion-Studio-Sitzung aktiv.')
        for s in ls:
            print(f"{s['name']:<32} {s['zustand']:<9} still {_dauer(s['still_seit']):<9} {s['grund'] or s['auftrag']}")
        return
    if a.was in ('zeige', 'oeffnen', 'stopp') or (a.was == 'weiter' and a.sitzung):
        if not a.sitzung:
            raise SystemExit(f'FEHLER: Sitzung fehlt: ms starten {a.was} <sitzung> (ms starten liste).')
        if a.was == 'zeige':
            print('\n'.join(zeige(a.sitzung, a.zeilen)))
        elif a.was == 'weiter':
            ausgabe(weiter(a.sitzung, wer='ms'), f'„weiter“ an {a.sitzung} geschickt.')
        elif a.was == 'oeffnen':
            d = oeffnen(a.sitzung)
            ausgabe(d, 'Terminalfenster geöffnet.' if d['geoeffnet'] else f"Zum Zuschauen im Terminal: {d['befehl']}")
        else:
            ausgabe(stopp(a.sitzung, wer='ms'), f'Sitzung {a.sitzung} beendet.')
        return
    if a.sitzung:
        raise SystemExit(f'FEHLER: "{a.sitzung}" passt hier nicht. Werte mit --kanal, --url oder --folge angeben.')

    d = starten(a.was, kanal=a.kanal, url=a.url, folge=a.folge, trocken=a.trocken, wer='ms')
    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return
    zeilen = ['Trocken, nichts gestartet:' if d.get('trocken') else 'Gestartet:',
              f"  Auftrag:  {d['text']}", f"  Ordner:   {d['ordner']}", f"  Befehl:   {d['befehl_text']}",
              '  Umgebung: ' + ' '.join(f'{k}={v}' for k, v in d['umgebung'].items())]
    if d.get('tmux'):
        zeilen += [f"  Sitzung:  {d['sitzung']}", f"  Zuschauen: {d['zuschauen']}"]
        if d.get('trocken'):
            zeilen.append(f"  tmux:     {d['start_text']}")
    else:
        zeilen.append('  Ohne tmux: ' + ('würde ein neues Terminalfenster öffnen mit:' if d.get('trocken')
                                         else 'läuft in einem neuen Terminalfenster:'))
        zeilen.append(f"            {d['start_text']}")
    if d.get('hinweis'):
        zeilen.append(f"  Hinweis:  {d['hinweis']}")
    print('\n'.join(zeilen))


if __name__ == '__main__':
    sys.exit(main())
