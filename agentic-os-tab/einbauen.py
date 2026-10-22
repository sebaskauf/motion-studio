"""STUDIO-Tab von Motion-Studio in ein bestehendes Agentic OS einbauen (macOS, Windows, Linux; nur Python-Standardbibliothek).
Sebastian 22.10.2026: „egal welche Form von Agentic OS gerade besteht“. Darum:
  - baut auf dem Quellordner auf, aus dem auch andere Tabs (CAROUSEL, BRIEFING …) schon eingebaut wurden, und bricht ab,
    wenn das installierte Plugin Tabs hat, die im Quellcode fehlen (ein Build würde sie sonst wegnehmen)
  - ändert nur App.tsx an vier Stellen und legt StudioView.tsx + loadStudio.ts dazu, keine CSS-Änderung
  - sichert main.js vor dem Kopieren und prüft das neue Bundle (alle alten Tabs + STUDIO drin)
Aufruf (Claude führt das im Setup aus, Schritt „Studio-Tab“):
  python3 einbauen.py --pruefen                    nur prüfen: Vault, Version, Tabs, Node; ändert nichts
  python3 einbauen.py [--vault <pfad>]             einbauen (fragt nicht, Claude hat vorher gefragt)
  Optionen: --quelle <ordner> (Standard ~/Documents/Projects/agentic-os), --heim <Motion-Studio-HEIM>, --trocken (bauen, nicht kopieren)
Exit-Codes: 0 fertig oder schon drin · 2 Nutzer muss entscheiden (mehrere Vaults, fremde Tabs, Version) · 1 Fehler."""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HIER = Path(__file__).resolve().parent
REPO_URL = 'https://github.com/sebaskauf/agentic-os.git'
KENNUNG = 'motion-studio-tab'
WIN = platform.system() == 'Windows'
TAB_RE = re.compile(r'\[\s*"([A-Z][A-Z0-9_]{1,20})"\s*,\s*"[^"\]]{1,24}"\s*\]')


def sag(text: str) -> None:
    print(text, flush=True)


def raus(code: int, text: str) -> None:
    sag(('FEHLER: ' if code == 1 else 'ENTSCHEIDUNG: ' if code == 2 else '') + text)
    sys.exit(code)


def obsidian_json() -> Path:
    if platform.system() == 'Darwin':
        return Path.home() / 'Library/Application Support/obsidian/obsidian.json'
    if WIN:
        return Path(os.environ.get('APPDATA', Path.home() / 'AppData/Roaming')) / 'obsidian/obsidian.json'
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'obsidian/obsidian.json'


def vaults_mit_agentic_os() -> list[Path]:
    p = obsidian_json()
    try:
        d = json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    aus = []
    for v in (d.get('vaults') or {}).values():
        pfad = Path(str(v.get('path') or ''))
        if (pfad / '.obsidian/plugins/agentic-os/manifest.json').is_file():
            aus.append(pfad)
    return aus


def version(p: Path) -> tuple[int, ...]:
    try:
        v = json.loads(p.read_text(encoding='utf-8')).get('version') or '0'
    except (OSError, ValueError):
        v = '0'
    return tuple(int(x) for x in re.findall(r'\d+', v)[:3]) or (0,)


def tabs_im_bundle(main_js: str) -> set[str]:
    """Tab-IDs aus dem gebauten Bundle: Die TABS-Liste bleibt beim Minifizieren als [["OVERVIEW","…"],["RESEARCH","…"],…] stehen."""
    m = re.search(r'\[\s*(\[\s*"OVERVIEW"\s*,\s*"[^"]*"\s*\](?:\s*,\s*\[\s*"[A-Z0-9_]+"\s*,\s*"[^"]*"\s*\])*)\s*,?\s*\]', main_js)
    return {x.group(1) for x in TAB_RE.finditer(m.group(1))} if m else set()


def tabs_im_quellcode(app: str) -> set[str]:
    m = re.search(r'TABS[^=]*=\s*\[(.*?)\];', app, re.S)
    return {x.group(1) for x in TAB_RE.finditer(m.group(1))} if m else set()


def befehl(args: list[str], cwd: Path, zeigen: str = '') -> subprocess.CompletedProcess:
    exe = shutil.which(args[0] + ('.cmd' if WIN and args[0] in ('npm', 'npx') else '')) or shutil.which(args[0])
    if not exe:
        raus(1, f'{args[0]} fehlt. ' + ('Node.js (LTS) von nodejs.org installieren.' if args[0] in ('node', 'npm', 'npx') else
                                     'Git installieren (Mac: xcode-select --install, Windows: winget install -e --id Git.Git).'))
    sag(f'> {zeigen or " ".join(args)}')
    r = subprocess.run([exe, *args[1:]], cwd=str(cwd), capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r


def heim_finden(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser()
    zeiger = Path.home() / '.motion-studio-heim'
    if zeiger.is_file() and Path(zeiger.read_text(encoding='utf-8').strip()).is_dir():
        return Path(zeiger.read_text(encoding='utf-8').strip())
    return Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude') / 'motion-studio'


def app_patchen(app: str) -> str:
    """Vier Stellen in App.tsx: Import, TabId, TABS, Render-Zweig. Jede genau einmal, sonst Abbruch mit Hinweis."""
    fehler = []
    if 'from "./StudioView"' not in app:
        n = len(re.findall(r'^import \{ CutterView \} from "\./CutterView";$', app, re.M))
        if n != 1:
            fehler.append('Import von CutterView nicht eindeutig gefunden')
        app = re.sub(r'^(import \{ CutterView \} from "\./CutterView";)$', r'\1\nimport { StudioView } from "./StudioView";', app, count=1, flags=re.M)
    m = re.search(r'type TabId\s*=\s*([^;]+);', app)
    if m and '"STUDIO"' not in m.group(1):
        app = app[:m.end(1)] + ' | "STUDIO"' + app[m.end(1):]
    m = re.search(r'(TABS[^=]*=\s*\[)(.*?)(\];)', app, re.S)
    if not m:
        fehler.append('TABS-Liste nicht gefunden')
    elif '"STUDIO"' not in m.group(2):
        inhalt = m.group(2).rstrip()
        komma = '' if inhalt.endswith(',') else ','
        neu = (inhalt + komma + (' ' if '\n' not in inhalt else '\n\t\t') + '["STUDIO", "STUDIO"]' + ('' if '\n' not in inhalt else ',\n\t'))
        app = app[:m.start(2)] + neu + app[m.end(2):]
    if 'tab === "STUDIO"' not in app:
        r = re.compile(r'(tab === "CUTTER" \? \(\s*<CutterView\s*/>\s*\)\s*:)')
        if len(r.findall(app)) != 1:
            fehler.append('Render-Zweig für CUTTER nicht eindeutig gefunden')
        else:
            app = r.sub(r'\1 tab === "STUDIO" ? (\n\t\t\t\t<StudioView />\n\t\t\t) :', app, count=1)
    if fehler:
        raus(1, 'App.tsx sieht anders aus als erwartet: ' + '; '.join(fehler) + '. Bau die vier Stellen von Hand ein (EINBAU.md, Schritt 3).')
    return app


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--vault')
    ap.add_argument('--quelle', default=str(Path.home() / 'Documents/Projects/agentic-os'))
    ap.add_argument('--heim')
    ap.add_argument('--pruefen', action='store_true')
    ap.add_argument('--trocken', action='store_true')
    a = ap.parse_args()

    # 1. Vault
    if a.vault:
        vault = Path(a.vault).expanduser()
        if not (vault / '.obsidian/plugins/agentic-os/manifest.json').is_file():
            raus(1, f'In {vault} liegt kein Agentic OS (.obsidian/plugins/agentic-os fehlt).')
    else:
        vs = vaults_mit_agentic_os()
        if not vs:
            raus(1, f'Kein Vault mit Agentic OS gefunden (gelesen: {obsidian_json()}). Pfad mit --vault angeben.')
        if len(vs) > 1:
            raus(2, 'Mehrere Vaults mit Agentic OS. Frag den Nutzer, welcher, und ruf mich mit --vault <pfad> auf:\n'
                 + '\n'.join(f'  {v}' for v in vs))
        vault = vs[0]
    plugin = vault / '.obsidian/plugins/agentic-os'
    main_js = (plugin / 'main.js').read_text(encoding='utf-8', errors='replace')
    v_inst = version(plugin / 'manifest.json')
    sag(f'Vault: {vault}\nAgentic OS im Vault: v{".".join(map(str, v_inst))}')
    if KENNUNG in main_js:
        raus(0, 'Der STUDIO-Tab von Motion-Studio ist schon eingebaut. Nichts zu tun.')
    inst_tabs = tabs_im_bundle(main_js)
    sag(f'Tabs im Vault: {", ".join(sorted(inst_tabs)) or "nicht lesbar"}')
    if 'STUDIO' in inst_tabs:
        raus(2, 'Im Vault gibt es schon einen anderen STUDIO-Tab (z. B. Sebastians eigener). Nicht überschreiben, den Nutzer fragen.')

    # 2. Motion-Studio-HEIM (Dashboard muss da sein)
    heim = heim_finden(a.heim)
    if not (heim / 'dashboard/server.py').is_file():
        raus(1, f'Motion-Studio ist nicht installiert ({heim / "dashboard/server.py"} fehlt). Erst SCHRITT 1 des Setup-Prompts.')
    sag(f'Motion-Studio: {heim}')

    # 3. Quellcode
    quelle = Path(a.quelle).expanduser()
    if a.pruefen:
        for prog in ('git', 'node', 'npm'):
            sag(f'{prog}: {"ok" if shutil.which(prog) or shutil.which(prog + ".cmd") else "FEHLT"}')
        sag(f'Quellordner: {quelle} ({"da" if (quelle / "src/App.tsx").is_file() else "wird geklont"})')
        if (quelle / 'src/App.tsx').is_file():
            fehlen = inst_tabs - tabs_im_quellcode((quelle / 'src/App.tsx').read_text(encoding='utf-8')) - {'STUDIO'}
            sag(f'Tabs, die im Quellcode fehlen: {", ".join(sorted(fehlen)) or "keine"}')
        raus(0, 'Prüfung fertig, nichts geändert.')
    if not (quelle / 'src/App.tsx').is_file():
        quelle.parent.mkdir(parents=True, exist_ok=True)
        r = befehl(['git', 'clone', REPO_URL, str(quelle)], quelle.parent)
        if r.returncode:
            raus(1, f'git clone ging nicht: {(r.stderr or r.stdout).strip()[-400:]}')
    else:
        r = befehl(['git', 'pull', '--ff-only'], quelle)
        if r.returncode:
            sag(f'Hinweis: git pull ging nicht ({(r.stderr or r.stdout).strip()[-200:]}). Ich baue mit dem vorhandenen Stand weiter.')
    v_quelle = version(quelle / 'manifest.json')
    if v_quelle < v_inst:
        raus(2, f'Das Plugin im Vault (v{".".join(map(str, v_inst))}) ist neuer als der Quellcode (v{".".join(map(str, v_quelle))}). '
             'Ein Build daraus würde neuere Teile wegnehmen. Erst den Quellordner aktualisieren.')
    app_pfad = quelle / 'src/App.tsx'
    app = app_pfad.read_text(encoding='utf-8')
    fehlen = inst_tabs - tabs_im_quellcode(app) - {'STUDIO'}
    if fehlen:
        raus(2, f'Dein Agentic OS hat Tabs, die im Quellcode {quelle} fehlen: {", ".join(sorted(fehlen))}. '
             'Ein Build würde sie wegnehmen. Erst deren Einbau-Anleitung (EINBAU.md des jeweiligen Systems) im Quellordner nachholen, '
             'dann mich noch einmal starten.')

    # 4. Dateien + App.tsx
    for n in ('StudioView.tsx', 'loadStudio.ts'):
        shutil.copy2(HIER / n, quelle / 'src' / n)
    neu = app_patchen(app)
    if neu != app:
        shutil.copy2(app_pfad, app_pfad.with_name('App.tsx.vor-studio'))
        app_pfad.write_text(neu, encoding='utf-8')
    sag('StudioView.tsx und loadStudio.ts liegen in src/, App.tsx ist angepasst.')

    # 5. Bauen (ohne native Builds: node-pty bleibt extern, das Vault hat seine eigenen Binaries)
    if not (quelle / 'node_modules/esbuild').is_dir():
        r = befehl(['npm', 'install', '--ignore-scripts', '--no-audit', '--no-fund'], quelle)
        if r.returncode:
            raus(1, f'npm install ging nicht: {(r.stderr or r.stdout).strip()[-500:]}')
    r = befehl(['npx', 'tsc', '-noEmit', '-skipLibCheck'], quelle)
    if r.returncode:
        raus(1, f'TypeScript meldet Fehler:\n{(r.stdout or r.stderr).strip()[-1500:]}')
    ziel = quelle / 'build-studio'
    ziel.mkdir(exist_ok=True)
    alt_main = quelle / 'main.js'
    r = befehl(['node', 'esbuild.config.mjs', 'production'], quelle)
    if r.returncode or not alt_main.is_file():
        raus(1, f'Build ging nicht: {(r.stderr or r.stdout).strip()[-800:]}')
    bundle = alt_main.read_text(encoding='utf-8', errors='replace')
    shutil.copy2(alt_main, ziel / 'main.js')

    # 6. Prüfen: Kennung + alle alten Tabs + STUDIO
    neu_tabs = tabs_im_bundle(bundle)
    fehlt = (inst_tabs | {'STUDIO'}) - neu_tabs
    if KENNUNG not in bundle or fehlt:
        raus(1, f'Das neue Bundle ist unvollständig (Kennung {"da" if KENNUNG in bundle else "fehlt"}, fehlende Tabs: '
             f'{", ".join(sorted(fehlt)) or "keine"}). Nichts kopiert.')
    sag(f'Neues Bundle geprüft: Tabs {", ".join(sorted(neu_tabs))}, Kennung {KENNUNG} drin.')

    # 7. Zeiger auf HEIM für den Tab, dann ins Vault (vorher sichern)
    (Path.home() / '.motion-studio-heim').write_text(str(heim), encoding='utf-8')
    if a.trocken:
        raus(0, f'Trocken: Bundle liegt in {ziel / "main.js"}, ins Vault kopiert habe ich nichts.')
    stempel = datetime.now().strftime('%Y%m%d-%H%M')
    sicherung = plugin / f'main.js.bak-vor-studio-{stempel}'
    shutil.copy2(plugin / 'main.js', sicherung)
    shutil.copy2(ziel / 'main.js', plugin / 'main.js')
    sag(f'Eingebaut. Sicherung: {sicherung}')
    sag('Jetzt Obsidian neu laden (Befehlspalette: „Reload app without saving“ bzw. Cmd/Strg+R). Dabei schließen sich offene '
        'Agentic-OS-Terminals. Danach gibt es oben den Tab STUDIO.')
    sag(f'Zurück auf den alten Stand: {sicherung.name} wieder in main.js umbenennen und Obsidian neu laden.')


if __name__ == '__main__':
    main()
