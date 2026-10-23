"""Motion-Studio aktualisieren: neueste Fassung von GitHub holen, installieren, laufendes Studio neu starten
  ms update            holt (git pull), installiert (install.sh, Arbeitsordner und Einstellungen bleiben) und zeigt alte und neue Version
  ms update --pruefen  zeigt nur, ob es eine neuere Version gibt
Sebastian 23.10.2026: Ein Mitglied hatte das Repo gezogen, aber nicht neu installiert. Sein Studio blieb auf dem ersten Stand
(ohne Pixel-Crew). Darum ein Befehl für alles. Eigene Änderungen in der Installation gehen dabei verloren (sie gehören ins Repo)."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import _ms


def git(repo: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, encoding='utf-8', errors='replace')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--pruefen', action='store_true')
    a = ap.parse_args()
    cfg = _ms.config()
    repo = Path(cfg.get('repo') or '').expanduser()
    if not (repo / 'install.sh').is_file():
        raise SystemExit(f'FEHLER: Repo nicht gefunden ({repo}). Setup-Prompt noch einmal ausführen (klont neu).')
    if not shutil.which('git'):
        raise SystemExit('FEHLER: git fehlt.')
    alt = git(repo, 'log', '-1', '--format=%h vom %cs').stdout.strip()
    r = git(repo, 'fetch', '--quiet', 'origin')
    if r.returncode:
        raise SystemExit(f'FEHLER: git fetch: {(r.stderr or r.stdout).strip()[-300:]}')
    neu_remote = git(repo, 'log', '-1', '--format=%h vom %cs', 'origin/HEAD').stdout.strip() or git(repo, 'log', '-1', '--format=%h vom %cs', '@{u}').stdout.strip()
    installiert = cfg.get('version') or 'unbekannt (vor dem 23.10.)'
    print(f'Installiert: {installiert}\nRepo:        {alt}\nGitHub:      {neu_remote or "?"}')
    if a.pruefen:
        aktuell = neu_remote and installiert.split()[0] == neu_remote.split()[0]
        print('Aktuell.' if aktuell else 'Es gibt eine neuere Version: ms update')
        return
    r = git(repo, 'pull', '--ff-only')
    if r.returncode:
        raise SystemExit(f'FEHLER: git pull: {(r.stderr or r.stdout).strip()[-400:]}\nLokale Änderungen im Repo? Dann mit dem Agenten klären, nicht überschreiben.')
    bash = shutil.which('bash') or 'bash'
    r = subprocess.run([bash, str(repo / 'install.sh'), '--arbeit', str(_ms.arbeit())], cwd=str(repo), text=True,
                       capture_output=True, encoding='utf-8', errors='replace')
    print('\n'.join(l for l in (r.stdout or '').splitlines() if l.strip())[-1500:])
    if r.returncode:
        raise SystemExit(f'FEHLER: install.sh (Code {r.returncode}): {(r.stderr or "").strip()[-400:]}')
    print(f'Aktualisiert auf {git(repo, "log", "-1", "--format=%h vom %cs").stdout.strip()}. '
          'Claude Code einmal neu starten, damit neue Skills und Agenten geladen werden.')


if __name__ == '__main__':
    main()
