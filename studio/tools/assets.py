"""3D-Assets suchen, laden und mit Lizenz ablegen (Poly Haven: HDRIs, Modelle, Texturen, CC0, gratis).
  ms assets suche polyhaven <begriff> [--typ hdris|models|textures] [--n 15]
  ms assets laden polyhaven <id> [--aufloesung 1k|2k|4k] [--typ hdris|models|textures] [--format hdr|exr|gltf|fbx|blend] [--ja]
  ms assets liste [--quelle polyhaven] [--nennung]
  ms assets eintragen <datei-oder-ordner> --quelle sketchfab|mixamo|tripo|meshy|blendkit|eigen --lizenz "CC-BY-4.0"
                      [--autor "Name"] [--url "https://…"] [--id name] [--typ models|hdris|textures|figuren]
  ms assets kosten tripo --anzahl 5
Beispiele:
  ms assets suche polyhaven studio --typ hdris
  ms assets laden polyhaven studio_small_09 --aufloesung 1k
  ms assets laden polyhaven rubber_duck_toy --aufloesung 1k          (Modell als glTF)
  ms assets eintragen ~/Downloads/robot.glb --quelle sketchfab --lizenz CC-BY-4.0 --autor "Jane Doe" --url https://sketchfab.com/3d-models/…
Ablage: ARBEIT/assets/<quelle>/<typ>/<id>/ mit lizenz.json (Quelle, Lizenz, Autor, Link, Hauptdatei).
In Blender-Szenen: mb.hdri("polyhaven:<id>"), mb.glb_import("polyhaven:<id>"), mb.material_pbr(texturen="polyhaven:<id>").
Sketchfab, Mixamo, Blendkit, Tripo und Meshy werden nicht automatisch geladen (Konto, Lizenz, Kosten): Anleitung im
Skill motion-szene-blender, danach mit `ms assets eintragen` ablegen, damit die Lizenz mitwandert."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import _ms

API = 'https://api.polyhaven.com'
UA = 'MotionStudio/1.0 (local motion design tool; asset download)'  # Header nur ASCII
TYPEN = ('hdris', 'models', 'textures')
TYP_NR = {0: 'hdris', 1: 'textures', 2: 'models'}
GROSS_MB = 300  # darüber nur mit --ja

# Preise Tripo (Stand der Recherche 20.10.2026, NICHT gegen die aktuelle Preisseite geprüft: die ist eine Web-App)
TRIPO = {
    'stand': '20.10.2026',
    'usd_pro_credit': 0.01,  # Tripo-Blog 08.04.2024: "$0.01 each, topping up with units of 100 credits"
    'gratis_credits': 2000,  # gleicher Blogpost: einmalig beim ersten API-Schlüssel
    'quellen': ['https://www.tripo3d.ai/blog/announcement-tripo-openapi-platform-payment-system',
                'https://developers.tripo3d.com/llms-full.txt (Changelog 2026-08: P2 100 Credits ohne, 110-130 mit Textur)'],
    'guenstig': {'modell': 20, 'rig': 25, 'bewegung': 10, 'quelle': 'Suchtreffer (V-Serie, Entwurf)'},
    'aktuell': {'modell': 120, 'rig': 30, 'bewegung': 20, 'quelle': 'Doku-Beispiele + Changelog P2 (mit Textur)'},
}


# ---------------------------------------------------------------- Netz

def _holen(url, ziel=None, md5=None, versuche=3):
    """GET mit User-Agent (Poly Haven verlangt einen eigenen). Ohne ziel: JSON zurück. Mit ziel: Datei, md5 geprüft."""
    letzter = None
    for i in range(versuche):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                if ziel is None:
                    return json.loads(r.read().decode('utf-8'))
                ziel = Path(ziel)
                ziel.parent.mkdir(parents=True, exist_ok=True)
                tmp = ziel.with_name('.' + ziel.name + '.teil')
                h = hashlib.md5()
                with open(tmp, 'wb') as f:
                    while True:
                        block = r.read(1 << 20)
                        if not block:
                            break
                        h.update(block)
                        f.write(block)
                if md5 and h.hexdigest() != md5:
                    tmp.unlink()
                    raise ValueError(f'Prüfsumme falsch bei {ziel.name}')
                tmp.replace(ziel)
                return ziel
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise SystemExit(f'FEHLER: nicht gefunden ({url}). Id prüfen: ms assets suche polyhaven <begriff>')
            letzter = e
            time.sleep(1.5 * (i + 1))
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            letzter = e
            time.sleep(1.5 * (i + 1))
    raise SystemExit(f'FEHLER: Download fehlgeschlagen ({url}): {letzter}. Internet prüfen, später nochmal.')


def _md5(p: Path):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def _basis():
    return _ms.arbeit() / 'assets'


# ---------------------------------------------------------------- Poly Haven

def _katalog(typ):
    """Liste aller Poly-Haven-Assets eines Typs, 24 h zwischengespeichert."""
    cache = _basis() / 'polyhaven' / '_katalog' / f'{typ}.json'
    if cache.exists() and time.time() - cache.stat().st_mtime < 86400:
        return _ms.json_lesen(cache, {})
    d = _holen(f'{API}/assets?t={typ}')
    _ms.json_schreiben(cache, d)
    return d


def suche(a):
    if a.quelle != 'polyhaven':
        raise SystemExit(f'FEHLER: Suche gibt es nur für polyhaven. {a.quelle}: Anleitung im Skill motion-szene-blender.')
    worte = [w.lower() for w in a.begriff]
    treffer = []
    for typ in ([a.typ] if a.typ else TYPEN):
        for aid, info in _katalog(typ).items():
            text = ' '.join([aid, info.get('name', '')] + info.get('tags', []) + info.get('categories', [])).lower()
            if all(w in text for w in worte):
                treffer.append((info.get('download_count', 0), typ, aid, info))
    treffer.sort(key=lambda x: -x[0])
    if not treffer:
        print(f'Nichts gefunden für "{" ".join(a.begriff)}". Englische Begriffe probieren (studio, sunset, wood, chair).')
        return
    print(f'{len(treffer)} Treffer, die {min(a.n, len(treffer))} beliebtesten (CC0, Namensnennung nicht nötig):')
    for dl, typ, aid, info in treffer[:a.n]:
        kat = ', '.join(c for c in info.get('categories', []) if not c.startswith('collection'))[:42]
        print(f'  {aid:<34} {typ:<9} {info.get("name", "")[:30]:<30} {kat:<42} {dl:>8} Downloads')
    print(f'Laden: ms assets laden polyhaven <id> --aufloesung 1k   Vorschau: https://polyhaven.com/a/{treffer[0][2]}')


def _dateien_waehlen(typ, files, aufl, fmt):
    """Liefert (hauptdatei_rel, [(rel, url, size, md5)])."""
    liste = []
    if typ == 'hdris':
        fmt = fmt or 'hdr'
        stufe = files.get('hdri', {}).get(aufl) or {}
        e = stufe.get(fmt)
        if not e:
            raise SystemExit(f'FEHLER: HDRI in {aufl}/{fmt} nicht vorhanden. Da: {", ".join(files.get("hdri", {}))}')
        rel = Path(e['url']).name
        return rel, [(rel, e['url'], e.get('size', 0), e.get('md5'))]
    if typ == 'models':
        fmt = fmt or 'gltf'
        stufe = (files.get(fmt) or {}).get(aufl) or {}
        e = stufe.get(fmt)
        if not e:
            raise SystemExit(f'FEHLER: Modell in {aufl}/{fmt} nicht vorhanden. Formate: '
                             f'{", ".join(k for k in files if k in ("gltf", "fbx", "blend", "usd"))}')
        rel = Path(e['url']).name
        liste.append((rel, e['url'], e.get('size', 0), e.get('md5')))
        for inc_rel, inc in (e.get('include') or {}).items():
            liste.append((inc_rel, inc['url'], inc.get('size', 0), inc.get('md5')))
        return rel, liste
    # Texturen: alle Maps als jpg (Normal in OpenGL-Variante, die Blender erwartet)
    fmt = fmt or 'jpg'
    for karte, stufen in files.items():
        if karte in ('blend', 'gltf', 'fbx', 'usd', 'mtlx', 'nor_dx') or not isinstance(stufen, dict):
            continue
        e = (stufen.get(aufl) or {}).get(fmt) or (stufen.get(aufl) or {}).get('png')
        if e and 'url' in e:
            liste.append((Path(e['url']).name, e['url'], e.get('size', 0), e.get('md5')))
    if not liste:
        raise SystemExit(f'FEHLER: Keine Textur-Maps in {aufl}/{fmt}.')
    haupt = next((r for r, *_ in liste if '_diff' in r), liste[0][0])
    return haupt, liste


def laden(a):
    if a.quelle != 'polyhaven':
        raise SystemExit(f'FEHLER: Automatisch laden geht nur bei polyhaven. {a.quelle}: von Hand laden, dann '
                         f'"ms assets eintragen <datei> --quelle {a.quelle} --lizenz …".')
    aid = a.id
    info = _holen(f'{API}/info/{aid}')
    if not isinstance(info, dict) or 'type' not in info:
        raise SystemExit(f'FEHLER: Poly-Haven-Asset "{aid}" gibt es nicht. Suchen: ms assets suche polyhaven <begriff>')
    typ = a.typ or TYP_NR.get(info['type'], 'models')
    files = _holen(f'{API}/files/{aid}')
    haupt, liste = _dateien_waehlen(typ, files, a.aufloesung, a.format)
    mb = sum(x[2] or 0 for x in liste) / 1e6
    if mb > GROSS_MB and not a.ja:
        raise SystemExit(f'Groß: {mb:.0f} MB in {a.aufloesung}. Kleinere Auflösung nehmen (--aufloesung 1k) oder mit --ja laden.')
    ordner = _basis() / 'polyhaven' / typ / aid
    neu = 0
    for rel, url, size, md5 in liste:
        ziel = ordner / rel
        if ziel.exists() and (not md5 or _md5(ziel) == md5):
            continue
        _holen(url, ziel, md5)
        neu += 1
    autoren = list((info.get('authors') or {}).keys())
    _ms.json_schreiben(ordner / 'lizenz.json', {
        'quelle': 'polyhaven', 'id': aid, 'name': info.get('name', aid), 'typ': typ, 'lizenz': 'CC0-1.0',
        'lizenz_url': 'https://polyhaven.com/license', 'seite': f'https://polyhaven.com/a/{aid}', 'autoren': autoren,
        'namensnennung_noetig': False, 'aufloesung': a.aufloesung, 'format': a.format or Path(haupt).suffix[1:],
        'hauptdatei': haupt, 'dateien': [r for r, *_ in liste], 'geladen': _ms.jetzt()})
    _ms.log(f'Asset geladen: polyhaven {aid} ({typ}, {a.aufloesung}, {mb:.1f} MB)', art='info')
    print(f'OK {aid} ({info.get("name")}, {typ}, {a.aufloesung}, {mb:.1f} MB, {neu} Dateien neu), Lizenz CC0')
    print(f'  Hauptdatei: {ordner / haupt}')
    print(f'  In Blender: mb.{"hdri" if typ == "hdris" else "glb_import" if typ == "models" else "material_pbr"}'
          f'({"texturen=" if typ == "textures" else ""}"polyhaven:{aid}")')
    print(ordner)


# ---------------------------------------------------------------- Liste, Eintragen, Kosten

def liste(a):
    basis = _basis()
    if not basis.exists():
        print('Noch keine Assets. Start: ms assets suche polyhaven studio --typ hdris')
        return
    zeilen, nennungen, ohne = [], [], []
    for quelle in sorted(p for p in basis.iterdir() if p.is_dir() and not p.name.startswith('_')):
        if a.quelle and quelle.name != a.quelle:
            continue
        for typ in sorted(p for p in quelle.iterdir() if p.is_dir() and not p.name.startswith('_')):
            for d in sorted(p for p in typ.iterdir() if p.is_dir()):
                lz = _ms.json_lesen(d / 'lizenz.json')
                if not lz:
                    ohne.append(d)
                    continue
                groesse = sum(f.stat().st_size for f in d.rglob('*') if f.is_file()) / 1e6
                n = '  NENNUNG' if lz.get('namensnennung_noetig') else ''
                zeilen.append(f'  {quelle.name:<10} {typ.name:<9} {lz.get("id", d.name):<32} {lz.get("lizenz", "?"):<14} '
                              f'{groesse:6.1f} MB{n}')
                if lz.get('namensnennung_noetig'):
                    nennungen.append(lz.get('nennung') or f'"{lz.get("name")}" von {lz.get("autor", "?")} '
                                                           f'({lz.get("url", "")}), {lz.get("lizenz")}')
    print(f'{len(zeilen)} Assets in {basis}:')
    print('\n'.join(zeilen) if zeilen else '  (keine)')
    for d in ohne:
        print(f'  LIZENZ FEHLT: {d}  -> ms assets eintragen {d} --quelle … --lizenz …')
    if a.nennung or nennungen:
        print(f'\nNamensnennung für die Caption ({len(nennungen)}):' if nennungen else '\nKeine Namensnennung nötig.')
        for n in nennungen:
            print(f'  {n}')


def eintragen(a):
    quelle = Path(a.pfad).expanduser()
    if not quelle.exists():
        raise SystemExit(f'FEHLER: {quelle} gibt es nicht.')
    aid = a.id or quelle.stem.lower().replace(' ', '-')
    ziel = _basis() / a.quelle / a.typ / aid
    if ziel.exists() and any(ziel.iterdir()):
        raise SystemExit(f'FEHLER: {ziel} gibt es schon. Andere --id wählen.')
    ziel.mkdir(parents=True, exist_ok=True)
    if quelle.is_dir():
        shutil.copytree(quelle, ziel, dirs_exist_ok=True)
        kandidaten = [p for p in ziel.rglob('*') if p.suffix.lower() in ('.glb', '.gltf', '.fbx', '.blend', '.hdr', '.exr', '.obj')]
        haupt = str(kandidaten[0].relative_to(ziel)) if kandidaten else ''
    else:
        shutil.copy2(quelle, ziel / quelle.name)
        haupt = quelle.name
    lic = a.lizenz.upper()
    nennung_noetig = 'BY' in lic or a.quelle == 'sketchfab' and 'CC0' not in lic
    nennung = f'"{aid}" von {a.autor or "?"} ({a.url or a.quelle}), {a.lizenz}' if nennung_noetig else ''
    _ms.json_schreiben(ziel / 'lizenz.json', {
        'quelle': a.quelle, 'id': aid, 'name': aid, 'typ': a.typ, 'lizenz': a.lizenz, 'autor': a.autor or '',
        'url': a.url or '', 'namensnennung_noetig': nennung_noetig, 'nennung': nennung, 'hauptdatei': haupt,
        'eingetragen': _ms.jetzt()})
    print(f'OK eingetragen: {ziel}' + (f'\n  Namensnennung nötig: {nennung}' if nennung_noetig else ''))
    if 'NC' in lic:
        print('  WARNUNG: NC = nicht kommerziell. Für Kanäle mit Werbung/Verkauf nicht verwenden.')
    if not haupt:
        print('  Hinweis: keine 3D-Datei erkannt (.glb/.gltf/.fbx/.blend/.hdr/.exr). Pfad im Szenenskript direkt angeben.')


def kosten(a):
    if a.dienst != 'tripo':
        raise SystemExit('Nur "tripo" hat eine Schätzung. Meshy: Credit-Preis nicht öffentlich belegt, auf meshy.ai/pricing '
                         'nachsehen. Higgsfield 3D: Preis im Higgsfield-Konto anzeigen lassen.')
    t = TRIPO
    print(f'Tripo-Schätzung für {a.anzahl} Figur(en) mit Rig und je {a.bewegungen} Bewegung(en). Stand {t["stand"]}, '
          'UNVERIFIZIERT:')
    for name in ('guenstig', 'aktuell'):
        s = t[name]
        credits = a.anzahl * (s['modell'] + s['rig'] + s['bewegung'] * a.bewegungen)
        print(f'  {name:<9} {credits:>6} Credits = {credits * t["usd_pro_credit"]:6.2f} USD   '
              f'(Modell {s["modell"]} + Rig {s["rig"]} + {a.bewegungen}x Bewegung {s["bewegung"]}; {s["quelle"]})')
    print(f'  1 Credit = {t["usd_pro_credit"]} USD, Aufladen in 100er-Schritten. Einmalig {t["gratis_credits"]} Gratis-Credits '
          'beim ersten API-Schlüssel (Stand 2024, kann sich geändert haben).')
    print('  Vor dem Kauf auf platform.tripo3d.ai (Billing) prüfen. Fehlgeschlagene Aufträge kosten laut Doku nichts.')
    print('  Quellen: ' + ' | '.join(t['quellen']))
    print('  Nichts wurde ausgeführt. Dieses Werkzeug kauft und lädt nichts bei Tripo.')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='was', required=True)
    s = sub.add_parser('suche', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s.add_argument('quelle')
    s.add_argument('begriff', nargs='+')
    s.add_argument('--typ', choices=TYPEN)
    s.add_argument('--n', type=int, default=15)
    lp = sub.add_parser('laden', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    lp.add_argument('quelle')
    lp.add_argument('id')
    lp.add_argument('--aufloesung', default='1k', choices=['1k', '2k', '4k', '8k'])
    lp.add_argument('--typ', choices=TYPEN)
    lp.add_argument('--format')
    lp.add_argument('--ja', action='store_true')
    li = sub.add_parser('liste', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    li.add_argument('--quelle')
    li.add_argument('--nennung', action='store_true')
    e = sub.add_parser('eintragen', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    e.add_argument('pfad')
    e.add_argument('--quelle', required=True, choices=['sketchfab', 'mixamo', 'tripo', 'meshy', 'blendkit', 'higgsfield', 'eigen'])
    e.add_argument('--lizenz', required=True)
    e.add_argument('--autor')
    e.add_argument('--url')
    e.add_argument('--id')
    e.add_argument('--typ', default='models', choices=['models', 'hdris', 'textures', 'figuren', 'bewegungen'])
    k = sub.add_parser('kosten', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    k.add_argument('dienst')
    k.add_argument('--anzahl', type=int, default=1)
    k.add_argument('--bewegungen', type=int, default=1)
    a = ap.parse_args()
    {'suche': suche, 'laden': laden, 'liste': liste, 'eintragen': eintragen, 'kosten': kosten}[a.was](a)


if __name__ == '__main__':
    sys.exit(main())
