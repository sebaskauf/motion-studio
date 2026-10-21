"""Richtet Motion-Studio ein: Python-Umgebung, Programme, Whisper-Modell, HyperFrames-Skills, Arbeitsordner, Schlüssel.
  ms setup venv [--whisper] [--ki --ja]          legt HEIM/.venv an und installiert requirements.txt
                                                 --whisper: dazu faster-whisper (Transkription unter Windows/Linux)
                                                 --ki: dazu requirements-ki.txt (Mac rund 1 GB, mit CUDA 3 GB+, nur mit --ja)
  ms setup programme --stufe basis [--ja]        fehlende Programme der Stufe zeigen, mit --ja installieren
                                                 (Mac: Homebrew, Windows: winget, Linux: nur Befehle zeigen, sudo machst du)
  ms setup whisper-modell [small|turbo|turbo-q5] [--ja]
                                                 ggml-Modell für whisper-cli nach HEIM/modelle laden, Größe vorher ansagen
  ms setup hyperframes-skills [--ja]             Stand zeigen, mit --ja "npx hyperframes skills" ausführen
  ms setup arbeitsordner <pfad>                  Arbeitsordner anlegen oder wechseln (PROFIL.md, LERNLOG.md, .env,
                                                 .claude/settings.json nur wenn fehlend), config.json + Agenten anpassen
  ms setup schluessel <NAME>                     Wert über die Standardeingabe in <arbeit>/.env schreiben (nie ausgegeben)
                                                 Beispiel: ms setup schluessel APIFY_TOKEN < datei_mit_wert
Ohne --ja wird bei Installationen nur gezeigt, was passieren würde."""
from __future__ import annotations

import argparse
import getpass
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import _ms
import _setup

SYSTEM = _setup.SYSTEM


def zeige(befehl: str):
    # Skill-Hinweise sind keine Befehle, deshalb ohne $
    print(f'  - {befehl}' if befehl.startswith('Skill ') else f'  $ {befehl}')


def ausfuehren(befehl, shell=False) -> int:
    """Startet einen Installationsbefehl sichtbar (Ausgabe direkt durchreichen)."""
    print(f'\n$ {befehl if isinstance(befehl, str) else " ".join(befehl)}', flush=True)
    try:
        return subprocess.call(befehl, shell=shell)
    except OSError as e:
        print(f'FEHLER: {e}')
        return 1


# ---------------------------------------------------------------- venv

def setup_venv(a):
    if sys.version_info[:2] < _setup.PY_MIN:
        raise SystemExit(f'FEHLER: Python {sys.version.split()[0]} ist zu alt, Motion-Studio braucht >= 3.9. '
                         f'Installieren: {_setup.INSTALL["python"][SYSTEM]}')
    venv = _ms.HEIM / '.venv'
    vp = _setup.venv_python()
    if a.ki and not a.ja:
        print('Die KI-Pakete (torch, torchaudio, transformers, faster-whisper) brauchen auf dem Mac rund 1 GB,')
        print('unter Windows/Linux mit NVIDIA-Karte (CUDA) 3 GB und mehr. Modelle laden beim ersten Lauf zusätzlich.')
        print('Sie sind optional: maschinelles Anhören von Sounds, Textsuche, Tiefe, Transkription ohne whisper-cli.')
        print('Installieren mit:')
        zeige(f'{_setup.ms_befehl()} setup venv --ki --ja')
        return 0
    if not vp:
        print(f'Lege Python-Umgebung an: {_setup.kurz_pfad(venv)} (Python {sys.version.split()[0]})')
        r = subprocess.run([sys.executable, '-m', 'venv', str(venv)], capture_output=True, text=True)
        if r.returncode != 0:
            hinweis = ''
            if SYSTEM == 'Linux':
                hinweis = '\nUnter Debian/Ubuntu fehlt oft das venv-Modul: sudo apt install -y python3-venv'
            raise SystemExit(f'FEHLER: venv anlegen ging nicht.\n{(r.stderr or "")[-800:]}{hinweis}')
        vp = _setup.venv_python()
        if not vp:
            raise SystemExit(f'FEHLER: venv angelegt, aber kein Python darin gefunden ({venv}).')
    else:
        print(f'Python-Umgebung ist schon da: {_setup.kurz_pfad(vp)}')
    pip = [str(vp), '-m', 'pip', 'install', '--disable-pip-version-check', '--progress-bar', 'off']
    dateien = [_ms.HEIM / 'requirements.txt']
    if a.ki:
        dateien.append(_ms.HEIM / 'requirements-ki.txt')
    befehl = pip + ['--upgrade', 'pip']
    subprocess.run(befehl, capture_output=True, text=True)
    for d in dateien:
        if not d.exists():
            raise SystemExit(f'FEHLER: {d} fehlt. Installation unvollständig, install.sh noch einmal ausführen.')
        print(f'Installiere {d.name} ({len(_setup.anforderungen(d))} Pakete) …', flush=True)
        r = subprocess.run(pip + ['-r', str(d)], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f'FEHLER: pip install -r {d.name} ging nicht.\n{(r.stdout + r.stderr)[-1500:]}')
    if a.whisper and not a.ki:
        print('Installiere faster-whisper …', flush=True)
        r = subprocess.run(pip + ['faster-whisper>=1.0'], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f'FEHLER: faster-whisper ging nicht.\n{(r.stdout + r.stderr)[-1500:]}')
    # Gegenprobe im venv selbst: jedes Paket importieren
    namen = _setup.anforderungen(_ms.HEIM / 'requirements.txt')
    if a.ki:
        namen += _setup.anforderungen(_ms.HEIM / 'requirements-ki.txt')
    if a.whisper:
        namen.append('faster-whisper')
    importe = sorted({_setup.IMPORT_NAMEN.get(n, n.replace('-', '_')) for n in namen})
    probe = 'import ' + ', '.join(importe) + '; print("ok")'
    r = subprocess.run([str(vp), '-c', probe], capture_output=True, text=True)
    if r.returncode != 0 or 'ok' not in r.stdout:
        raise SystemExit(f'FEHLER: Pakete installiert, aber Import schlägt fehl:\n{(r.stderr or "")[-1200:]}')
    print(f'OK: {len(importe)} Pakete importierbar ({", ".join(importe)}).')
    print(f'Die Werkzeuge nutzen ab jetzt {_setup.kurz_pfad(vp)}.')
    return 0


# ---------------------------------------------------------------- Programme

def _paketmanager_befehle(fehlend: list[dict]) -> tuple[list[str], list[str], list[str]]:
    """(automatisch per Paketmanager, automatisch per npx, nur zeigen)"""
    pm, npx, zeigen = [], [], []
    brew_formeln, brew_casks = [], []
    for p in fehlend:
        b = p.get('installieren') or ''
        if not b:
            continue
        if b.startswith('npx '):
            npx.append(b)
        elif b.startswith('brew install --cask '):
            brew_casks.append(b.split('brew install --cask ', 1)[1])
        elif b.startswith('brew install ') and '&&' not in b:
            brew_formeln += b.split('brew install ', 1)[1].split()
        elif b.startswith('brew install whisper-cpp && '):
            brew_formeln.append('whisper-cpp')
            zeigen.append(b.split('&& ', 1)[1])
        elif b.startswith('winget install '):
            pm.append(b + ' --accept-source-agreements --accept-package-agreements')
        else:
            zeigen.append(b)
    if brew_formeln:
        pm.insert(0, 'brew install ' + ' '.join(dict.fromkeys(brew_formeln)))
    for c in dict.fromkeys(brew_casks):
        pm.append(f'brew install --cask {c}')
    return list(dict.fromkeys(pm)), list(dict.fromkeys(npx)), list(dict.fromkeys(zeigen))


def setup_programme(a):
    stufen = list(_setup.STUFEN) if a.stufe == 'alle' else [a.stufe]
    liste = _setup.pruefungen(stufen, kurz=True)
    fehlend = [p for p in liste if not p['ok'] and any(s in stufen for s in p['stufen'])
               and not p['id'].startswith('schluessel:') and p['id'] not in ('profil',)]
    if not fehlend:
        print(f'Stufe {a.stufe}: alles da, nichts zu installieren.')
        return 0
    print(f'Stufe {a.stufe}: es fehlt')
    for p in fehlend:
        print(f'  - {p["name"]}{" (optional)" if not p["pflicht"] else ""}: {p.get("detail") or ""}')
    pm, npx, zeigen = _paketmanager_befehle(fehlend)

    if SYSTEM == 'Darwin' and any(b.startswith('brew ') for b in pm) and not shutil.which('brew'):
        print('\nHomebrew fehlt. Der Installer fragt nach deinem Mac-Passwort, das geht nur in deinem eigenen Terminal.')
        print('Öffne das Programm "Terminal", füge diese Zeile ein und folge den Anweisungen (am Ende die zwei "echo"-Zeilen, die er anzeigt):')
        zeige(_setup.BREW_INSTALL)
        print('Danach hier noch einmal: ' + f'{_setup.ms_befehl()} setup programme --stufe {a.stufe}')
        return 1
    if SYSTEM == 'Windows' and pm and not shutil.which('winget'):
        print('\nwinget fehlt. Es kommt mit dem "App Installer" aus dem Microsoft Store (Windows 10/11).')
        return 1

    if SYSTEM == 'Linux':
        zeigen = pm + zeigen
        pm = []
    if pm or npx:
        print('\nDiese Befehle würden laufen:' if not a.ja else '\nIch führe aus:')
        for b in pm + npx:
            zeige(b)
    if zeigen:
        print('\nDanach (selbst oder als eigener Schritt):')
        for b in zeigen:
            zeige(b)
    if SYSTEM == 'Linux' and any(b.startswith('sudo') for b in zeigen):
        print('\nsudo fragt nach deinem Passwort. Führ die sudo-Zeilen bitte selbst im Terminal aus.')
    if not a.ja:
        print(f'\nNichts installiert. Mit Ja ausführen: {_setup.ms_befehl()} setup programme --stufe {a.stufe} --ja')
        return 0

    fehler = 0
    for b in pm:
        code = ausfuehren(b, shell=True)
        if code != 0:
            fehler += 1
            print(f'FEHLER: "{b}" endete mit Code {code}. Meldung oben lesen, nicht als erledigt melden.')
    for b in npx:
        if shutil.which('npx'):
            code = ausfuehren(b, shell=True)
            if code != 0:
                fehler += 1
                print(f'FEHLER: "{b}" endete mit Code {code}.')
        else:
            print(f'Übersprungen (npx fehlt noch, erst Node.js): {b}')
    if SYSTEM == 'Windows' and pm:
        print('\nWichtig unter Windows: Neue Programme sind erst in einem NEUEN Terminal im PATH. '
              'Claude Code einmal schließen und neu starten, dann ms check.')
    print(f'\nJetzt prüfen: {_setup.ms_befehl()} check --stufe {a.stufe}')
    return 1 if fehler else 0


# ---------------------------------------------------------------- Whisper-Modell

def setup_whisper(a):
    datei, groesse = _setup.WHISPER_MODELLE[a.modell]
    ziel = _ms.HEIM / 'modelle' / datei
    vorhanden = _ms._whisper_modell()  # nur lesen
    print(f'Modell {a.modell}: {datei}, {groesse / 1e9:.2f} GB, Ziel {_setup.kurz_pfad(ziel)}')
    if not shutil.which('whisper-cli'):
        print('Hinweis: whisper-cli fehlt noch. ' + (f'Installieren: brew install whisper-cpp' if SYSTEM == 'Darwin' else
              f'Unter {SYSTEM} ist faster-whisper einfacher: {_setup.ms_befehl()} setup venv --whisper'))
    if ziel.exists() and ziel.stat().st_size == groesse:
        _setup.config_setzen(whisper_modell=ziel.as_posix())
        print(f'Schon geladen. config.json zeigt jetzt darauf. Fertig.')
        return 0
    if vorhanden and not a.ja:
        print(f'Es ist schon ein Modell da und wird genutzt: {_setup.kurz_pfad(vorhanden)}. Ein zweites brauchst du nicht.')
    if not a.ja:
        print(f'Nichts geladen. Laden mit: {_setup.ms_befehl()} setup whisper-modell {a.modell} --ja')
        print('Wahl: small (0,49 GB, schwächere Rechner) · turbo (1,62 GB, beste Wortzeiten) · turbo-q5 (0,57 GB, fast wie turbo)')
        return 0
    frei = shutil.disk_usage(str(_ms.HEIM)).free
    if frei < groesse * 1.2:
        raise SystemExit(f'FEHLER: zu wenig Platz ({frei / 1e9:.1f} GB frei, gebraucht {groesse / 1e9:.1f} GB).')
    ziel.parent.mkdir(parents=True, exist_ok=True)
    teil = ziel.with_suffix('.part')
    url = _setup.WHISPER_URL + datei
    print(f'Lade {url}', flush=True)
    try:
        with urllib.request.urlopen(url, timeout=60) as antwort, open(teil, 'wb') as f:
            gesamt = int(antwort.headers.get('Content-Length') or groesse)
            geladen, naechste = 0, 10
            while True:
                stueck = antwort.read(1 << 20)
                if not stueck:
                    break
                f.write(stueck)
                geladen += len(stueck)
                if geladen * 100 / gesamt >= naechste:
                    print(f'  {naechste} % ({geladen / 1e9:.2f} GB)', flush=True)
                    naechste += 10
    except OSError as e:
        raise SystemExit(f'FEHLER: Download abgebrochen ({e}). Noch einmal starten, die halbe Datei wird überschrieben.')
    if teil.stat().st_size != groesse:
        raise SystemExit(f'FEHLER: Datei unvollständig ({teil.stat().st_size} statt {groesse} Bytes). Noch einmal starten.')
    os.replace(teil, ziel)
    _setup.config_setzen(whisper_modell=ziel.as_posix())
    print(f'OK: {_setup.kurz_pfad(ziel)} geladen, config.json "whisper_modell" gesetzt.')
    return 0


# ---------------------------------------------------------------- HyperFrames-Skills

def setup_hf_skills(a):
    cfg = _setup.claude_ordner()
    env = {'CLAUDE_CONFIG_DIR': str(cfg)}
    if not shutil.which('npx'):
        raise SystemExit(f'FEHLER: npx fehlt (kommt mit Node.js). Erst: {_setup.INSTALL["node"][SYSTEM]}')
    if not shutil.which('git'):
        raise SystemExit(f'FEHLER: git fehlt, die Skills werden per git geladen. Erst: {_setup.INSTALL["git"][SYSTEM]}')
    # Gleiche Prüfung wie ms check: derselbe Claude-Ordner (_setup.claude_ordner), skills check mit --dir auf genau ihn
    st = _setup.hf_skills_stand(timeout=60)
    ort = _setup.kurz_pfad(st['ordner'])
    print(f'HyperFrames-Skills in {ort}: Kern ' + (f'fehlt ({", ".join(st["fehlen"])})' if st['fehlen'] else 'da')
          + f', {st["anzahl"]} hyperframes-Skills')
    s = st['check']
    if s is not None:
        print(f'  laut "hyperframes skills check" für {ort}: {s.get("current", 0)} aktuell, {s.get("outdated", 0)} veraltet, '
              f'{s.get("missing", 0)} nicht installiert')
    elif not st['ordner'].exists():
        print(f'  {ort} gibt es noch nicht.')
    else:
        print('  HyperFrames ist noch nicht geladen, der genaue Stand lässt sich erst danach prüfen.')
    befehl = 'npx --yes hyperframes skills'
    print('Der Befehl installiert alle HyperFrames- und GSAP-Skills (öffentlich, von HeyGen) für Claude Code')
    print(f'nach {_setup.kurz_pfad(cfg / "skills")} und zusätzlich nach ~/.agents/skills (für andere KI-Werkzeuge).')
    if not a.ja:
        print('Nichts installiert. Mit Ja ausführen:')
        zeige(f'{_setup.ms_befehl()} setup hyperframes-skills --ja')
        return 0
    print(f'\n$ {befehl}', flush=True)
    code = subprocess.call(befehl, shell=True, env=dict(os.environ, **env))
    if code != 0:
        raise SystemExit(f'FEHLER: "{befehl}" endete mit Code {code}. Meldung oben lesen.')
    fehlen = _setup.hf_skills_stand(mit_check=False)['fehlen']
    if fehlen:
        raise SystemExit(f'FEHLER: nach der Installation fehlen noch {", ".join(fehlen)} in {cfg / "skills"}.')
    print('OK: HyperFrames-Skills installiert. Claude Code einmal neu starten, damit sie geladen werden.')
    return 0


# ---------------------------------------------------------------- Arbeitsordner

def setup_arbeitsordner(a):
    neu = Path(os.path.expanduser(a.pfad)).resolve()
    alt = _ms.config().get('arbeitsordner')
    erg = _setup.arbeitsordner_anlegen(neu)
    _setup.config_setzen(arbeitsordner=neu.as_posix())
    print(f'Arbeitsordner: {neu}')
    if erg['angelegt']:
        print('  angelegt: ' + ', '.join(erg['angelegt']))
    else:
        print('  alles war schon da, nichts überschrieben')
    # Agenten und Skills enthalten den Pfad fest (install.sh hat __ARBEIT__ ersetzt): alten Pfad gegen neuen tauschen
    if alt and Path(os.path.expanduser(alt)).resolve() != neu:
        cfg = _setup.claude_ordner()
        liste = (_ms.HEIM / '.installiert')
        geaendert = 0
        if liste.exists():
            for zeile in liste.read_text(encoding='utf-8').splitlines():
                if not zeile.endswith('.md') or not (zeile.startswith('agents/') or zeile.startswith('skills/')):
                    continue
                f = cfg / zeile
                if f.exists():
                    text = f.read_text(encoding='utf-8')
                    # nur ganze Pfade tauschen, nicht /x/arbeit in /x/arbeit2
                    muster = re.escape(alt.rstrip('/')) + r'(?=[/"`\'\s)]|$)'
                    neu_text = re.sub(muster, lambda _m: neu.as_posix(), text)
                    if neu_text != text:
                        f.write_text(neu_text, encoding='utf-8')
                        geaendert += 1
        print(f'  Pfad in {geaendert} Agent-/Skill-Dateien angepasst (alt: {alt}).')
        print(f'  Der alte Ordner bleibt unverändert stehen. Inhalte ziehst du bei Bedarf selbst um.')
    print(f'Claude Code im Arbeitsordner starten, damit die erlaubten Befehle greifen: cd "{neu.as_posix()}" && claude')
    return 0


# ---------------------------------------------------------------- Schlüssel

def setup_schluessel(a):
    name = a.name.strip()
    if not re.match(r'^[A-Z][A-Z0-9_]*$', name):
        raise SystemExit('FEHLER: Name nur aus Großbuchstaben, Ziffern und _, z. B. APIFY_TOKEN.')
    if sys.stdin.isatty():
        wert = getpass.getpass(f'{name} (Eingabe bleibt unsichtbar): ')
    else:
        wert = sys.stdin.read()
    wert = wert.strip().strip('"').strip("'")
    if not wert or '\n' in wert:
        raise SystemExit('FEHLER: Kein Wert bekommen (oder mehrere Zeilen). Nichts geändert.')
    datei = _ms.arbeit() / '.env'
    datei.parent.mkdir(parents=True, exist_ok=True)
    zeilen = datei.read_text(encoding='utf-8').splitlines() if datei.exists() else _setup.ENV_VORLAGE.splitlines()
    neu, gesetzt = [], False
    for z in zeilen:
        k = z.split('=', 1)[0].strip()
        if not z.lstrip().startswith('#') and '=' in z and k == name:
            if not gesetzt:
                neu.append(f'{name}={wert}')
                gesetzt = True
            continue
        neu.append(z)
    if not gesetzt:
        neu.append(f'{name}={wert}')
    datei.write_text('\n'.join(neu) + '\n', encoding='utf-8')
    try:
        os.chmod(datei, 0o600)
    except OSError:
        pass
    print(f'{name} gesetzt in {_setup.kurz_pfad(datei)} (Wert wird nicht angezeigt).')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='was')
    v = sub.add_parser('venv', help='Python-Umgebung anlegen und Pakete installieren')
    v.add_argument('--ki', action='store_true')
    v.add_argument('--whisper', action='store_true')
    v.add_argument('--ja', action='store_true')
    p = sub.add_parser('programme', help='fehlende Programme einer Stufe installieren')
    p.add_argument('--stufe', default='basis', choices=_setup.STUFEN + ['alle'])
    p.add_argument('--ja', action='store_true')
    w = sub.add_parser('whisper-modell', help='ggml-Modell für whisper-cli laden')
    w.add_argument('modell', nargs='?', default='turbo', choices=list(_setup.WHISPER_MODELLE))
    w.add_argument('--ja', action='store_true')
    h = sub.add_parser('hyperframes-skills', help='HyperFrames-Skills für Claude Code installieren')
    h.add_argument('--ja', action='store_true')
    o = sub.add_parser('arbeitsordner', help='Arbeitsordner anlegen oder wechseln')
    o.add_argument('pfad')
    s = sub.add_parser('schluessel', help='Schlüssel in .env schreiben (Wert über stdin)')
    s.add_argument('name')
    a = ap.parse_args()
    aktionen = {'venv': setup_venv, 'programme': setup_programme, 'whisper-modell': setup_whisper,
                'hyperframes-skills': setup_hf_skills, 'arbeitsordner': setup_arbeitsordner, 'schluessel': setup_schluessel}
    if not a.was:
        ap.print_help()
        return 0
    return aktionen[a.was](a)


if __name__ == '__main__':
    sys.exit(main())
