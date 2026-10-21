"""Baukasten (Kit) eines Kanals pflegen: Katalog erzeugen und prüfen, dass keine Funktion verloren geht.
  ms kit <kanal> katalog                      kit/KATALOG.md aus kit/lib/*.js neu (Funktionen + Kommentar, Beispiele)
  ms kit <kanal> pruefen                      kit/lib gegen den Stand des letzten Katalogs: nichts darf verschwinden
  ms kit <kanal> pruefen --kandidat <pfad>    neue Fassung (Datei oder Ordner, z. B. build/assets/lib einer Folge)
                                              gegen kit/lib prüfen, BEVOR sie ins Kit kopiert wird
Beispiel nach einer Folge: ms kit mein-kanal pruefen --kandidat ~/MotionStudio/folgen/2026-10-20-x/build/assets/lib
  → OK? dann Dateien nach kanaele/<k>/kit/lib/ kopieren und ms kit <k> katalog
Erkannt werden: ES-Module (export function/const/class name) und globale Bibliotheken (OBJ.name = function (…)).
Doku einer Funktion = Kommentar direkt darüber (/* … */ oder // …). Der Teil von KATALOG.md ab einer Zeile "---"
(Rezepte, von Hand gepflegt) bleibt beim Neu-Erzeugen erhalten. Syntax-Prüfung jeder Datei mit node --check
(ein Syntaxfehler im Kit rendert jede Szene leer). Code 1, wenn etwas fehlt oder kaputt ist."""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import _ms

MUSTER_ES = re.compile(r'^export\s+(?:async\s+)?(function|const|let|class)\s+([A-Za-z0-9_$]+)\s*(\([^)]*\))?')
MUSTER_GLOBAL = re.compile(r'^\s*([A-Z][A-Za-z0-9_$]*)\.([A-Za-z0-9_$]+)\s*=\s*(?:async\s+)?function\s*(\([^)]*\))')
MUSTER_FENSTER = re.compile(r'^\s*window\.([A-Za-z0-9_$]+)\s*=\s*(?:async\s+)?function\s*(\([^)]*\))')
RAND = '\n---\n'
RAND_VORLAGE = ('\n---\n\n# Rezepte (von Hand gepflegt, bleibt beim Neu-Erzeugen erhalten)\n\n'
                'Hier kommen bewährte Kombinationen hin: Wow-Momente, Übergänge, Kamera-Muster, mit Szene und Datum,\n'
                'aus der sie stammen. Eine Zeile Wirkung, dann der Schnipsel. Fehler, die dabei passiert sind, nach REGELN.md.\n')


def kommentar_darueber(zeilen: list[str], i: int) -> str:
    """Zusammenhängender Kommentar direkt über Zeile i (Block /* */ oder // Zeilen)."""
    j, teile = i - 1, []
    while j >= 0 and not zeilen[j].strip():
        j -= 1
    if j >= 0 and zeilen[j].strip().endswith('*/'):
        while j >= 0:
            teile.insert(0, zeilen[j])
            if '/*' in zeilen[j]:
                break
            j -= 1
    else:
        while j >= 0 and zeilen[j].strip().startswith('//'):
            teile.insert(0, zeilen[j])
            j -= 1
    text = ' '.join(re.sub(r'^\s*(/\*+|\*+/?|//)\s?', '', t).replace('*/', '').strip() for t in teile)
    return re.sub(r'\s+', ' ', text).strip()


def funktionen(datei: Path) -> list[dict]:
    zeilen = datei.read_text(encoding='utf-8', errors='replace').splitlines()
    aus = []
    for i, z in enumerate(zeilen):
        m = MUSTER_ES.match(z)
        if m:
            aus.append({'name': m.group(2), 'art': m.group(1), 'sig': m.group(3) or '', 'doku': kommentar_darueber(zeilen, i)})
            continue
        m = MUSTER_GLOBAL.match(z)
        if m and m.group(1) not in ('Object', 'Math', 'JSON', 'Array'):
            aus.append({'name': f'{m.group(1)}.{m.group(2)}', 'art': 'function', 'sig': m.group(3), 'doku': kommentar_darueber(zeilen, i)})
            continue
        m = MUSTER_FENSTER.match(z)
        if m:
            aus.append({'name': m.group(1), 'art': 'function', 'sig': m.group(2), 'doku': kommentar_darueber(zeilen, i)})
    return aus


def ist_modul(text: str) -> bool:
    return bool(re.search(r'^\s*(import|export)\s', text, re.M))


def syntax(datei: Path) -> str | None:
    """None = OK, sonst Fehlermeldung. Ohne node: Prüfung übersprungen (None)."""
    node = shutil.which('node')
    if not node:
        return None
    text = datei.read_text(encoding='utf-8', errors='replace')
    with tempfile.TemporaryDirectory() as tmp:
        ziel = Path(tmp) / (datei.stem + ('.mjs' if ist_modul(text) else '.cjs'))
        ziel.write_text(text, encoding='utf-8')
        r = subprocess.run([node, '--check', str(ziel)], capture_output=True, text=True)
    if r.returncode == 0:
        return None
    zeilen = [z.strip() for z in (r.stderr or r.stdout or 'unbekannt').strip().splitlines() if z.strip()]
    return ' | '.join(zeilen[:4])


def kurz(s: str, n=240) -> str:
    return s if len(s) <= n else s[: n - 1].rstrip() + '…'


def beispiele(ordner: Path, alle_namen: set[str]) -> list[str]:
    zeilen = []
    for p in sorted(ordner.glob('*')):
        if p.suffix.lower() not in ('.html', '.js', '.py') or p.name.startswith('.'):
            continue
        text = p.read_text(encoding='utf-8', errors='replace')
        m = re.search(r'<!--(.*?)-->', text, re.S) or re.search(r'/\*(.*?)\*/', text, re.S)
        zweck = re.sub(r'\s+', ' ', m.group(1)).strip() if m else ''
        benutzt = sorted({n for n in alle_namen if re.search(r'[\.\s(]' + re.escape(n.split('.')[-1]) + r'\s*\(', text)})
        zeilen.append(f'- `beispiele/{p.name}` · {kurz(zweck, 300)}' + (f' · benutzt: {", ".join(benutzt[:24])}' if benutzt else ''))
    return zeilen


def stand_lesen(kit: Path) -> dict:
    return _ms.json_lesen(kit / '.katalog_stand.json', {}) or {}


def katalog(kanal: Path) -> int:
    kit = kanal / 'kit'
    lib = kit / 'lib'
    dateien = sorted(p for p in lib.glob('*.js')) if lib.exists() else []
    alt = (kit / 'KATALOG.md').read_text(encoding='utf-8') if (kit / 'KATALOG.md').exists() else ''
    rest = alt[alt.index(RAND):] if RAND in alt else RAND_VORLAGE
    out = [f'# Kit-Katalog {kanal.name} (erzeugt mit "ms kit {kanal.name} katalog", Rezepte unten von Hand)', '',
           'Einbinden: Dateien mit "ms-global" in Zeile 1 lädt index.html automatisch (globales Objekt, z. B. MS2D).',
           'ES-Module (3D) lädt ms3dSzene({...}) und reicht sie als M an aufbau/zustand/kamera weiter.',
           'Neue Bausteine nur additiv: vorher "ms kit <kanal> pruefen --kandidat <datei>", danach diesen Katalog neu erzeugen.', '']
    stand, fehler, gesamt, namen = {}, [], 0, set()
    for d in dateien:
        fs = funktionen(d)
        stand[d.name] = sorted(f['name'] for f in fs)
        namen.update(f['name'] for f in fs)
        s = syntax(d)
        if s:
            fehler.append(f'{d.name}: Syntaxfehler: {s}')
        text = d.read_text(encoding='utf-8', errors='replace')
        m = re.match(r'\s*/\*(.*?)\*/', text, re.S)
        kopf = re.sub(r'^ms-global\s*', '', re.sub(r'\s+', ' ', m.group(1)).strip()) if m else ''
        out.append(f'## {d.name}{"  (ES-Modul)" if ist_modul(text) else "  (global)"}')
        if kopf:
            out.append('')
            out.append(kurz(kopf, 300))
        out.append('')
        for f in fs:
            out.append(f"- `{f['name']}{f['sig']}`" + (f" · {kurz(f['doku'])}" if f['doku'] else ''))
            gesamt += 1
        out.append('')
    bsp = beispiele(kit / 'beispiele', namen) if (kit / 'beispiele').exists() else []
    if bsp:
        out += ['## Beispiele', ''] + bsp + ['']
    (kit / 'KATALOG.md').write_text('\n'.join(out).rstrip() + '\n' + rest, encoding='utf-8')
    _ms.json_schreiben(kit / '.katalog_stand.json', {'zeit': _ms.jetzt(), 'dateien': stand})
    print(f'KATALOG.md: {len(dateien)} Dateien, {gesamt} Bausteine, {len(bsp)} Beispiele, Rezepte '
          f'{"erhalten" if RAND in alt else "als Vorlage angelegt"}')
    for f in fehler:
        print('  FEHLER:', f)
    print(kit / 'KATALOG.md')
    return 1 if fehler else 0


def pruefen(kanal: Path, kandidat: str | None) -> int:
    kit = kanal / 'kit'
    lib = kit / 'lib'
    befunde, hinweise = [], []
    if kandidat:
        k = Path(kandidat).expanduser().resolve()
        if not k.exists():
            raise SystemExit(f'FEHLER: {k} gibt es nicht.')
        neue = [k] if k.is_file() else sorted(k.glob('*.js'))
        for d in neue:
            s = syntax(d)
            if s:
                befunde.append(f'{d.name}: Syntaxfehler: {s}')
            jetzt = {f['name'] for f in funktionen(d)}
            alt_datei = lib / d.name
            if not alt_datei.exists():
                hinweise.append(f'{d.name}: neue Datei im Kit ({len(jetzt)} Bausteine)')
                continue
            vorher = {f['name'] for f in funktionen(alt_datei)}
            weg, neu = sorted(vorher - jetzt), sorted(jetzt - vorher)
            if weg:
                befunde.append(f'{d.name}: würde verschwinden: {", ".join(weg)}')
            if neu:
                hinweise.append(f'{d.name}: neu: {", ".join(neu)}')
            if not weg and not neu:
                hinweise.append(f'{d.name}: gleiche Bausteine ({len(jetzt)})')
    else:
        stand = stand_lesen(kit).get('dateien')
        if not stand:
            raise SystemExit(f'FEHLER: noch kein Katalog-Stand. Erst "ms kit {kanal.name} katalog".')
        for name, vorher in stand.items():
            d = lib / name
            if not d.exists():
                befunde.append(f'{name}: Datei fehlt im Kit (vorher {len(vorher)} Bausteine)')
                continue
            jetzt = {f['name'] for f in funktionen(d)}
            weg, neu = sorted(set(vorher) - jetzt), sorted(jetzt - set(vorher))
            if weg:
                befunde.append(f'{name}: verschwunden: {", ".join(weg)}')
            if neu:
                hinweise.append(f'{name}: neu seit dem Katalog: {", ".join(neu)} (Katalog neu erzeugen)')
        for d in sorted(lib.glob('*.js')):
            s = syntax(d)
            if s:
                befunde.append(f'{d.name}: Syntaxfehler: {s}')
            if d.name not in stand:
                hinweise.append(f'{d.name}: neue Datei seit dem Katalog')
    print('Prüfung:', 'OK' if not befunde else f'{len(befunde)} Fehler')
    for b in befunde:
        print('  FEHLER:', b)
    for h in hinweise:
        print('  Hinweis:', h)
    return 1 if befunde else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('kanal')
    ap.add_argument('was', choices=['katalog', 'pruefen'])
    ap.add_argument('--kandidat')
    a = ap.parse_args()
    kanal = _ms.ziel_pfad(a.kanal if a.kanal.startswith(('kanal:', '/', '~')) else f'kanal:{a.kanal}')
    if not (kanal / 'STATUS.json').exists():
        raise SystemExit(f'FEHLER: Kanal {a.kanal} gibt es nicht ({kanal}).')
    (kanal / 'kit' / 'lib').mkdir(parents=True, exist_ok=True)
    return katalog(kanal) if a.was == 'katalog' else pruefen(kanal, a.kandidat)


if __name__ == '__main__':
    sys.exit(main())
