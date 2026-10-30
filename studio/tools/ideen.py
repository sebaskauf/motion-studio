"""Ideenliste eines Kanals (kanaele/<k>/IDEEN.md): eigene Ideen zuerst, dann die nach dem Schema gefundenen
  ms ideen <kanal> [--json]                          Liste: offen (eigene zuerst), erledigt, knapp ja/nein
  ms ideen <kanal> naechste [--json]                 nächste Idee für eine Folge (erste offene eigene, sonst erste offene vom System)
  ms ideen <kanal> neu "<Idee>" [--eigen] [--notiz "<warum>"] [--oben]   Idee anhängen (--oben: als nächste)
  ms ideen <kanal> nutzen "<Idee oder Nr>" --folge <folge-id>          als erledigt abhaken
  ms ideen <kanal> anlegen                          IDEEN.md aus der Vorlage anlegen, falls sie fehlt
Format (von Hand in Obsidian oder jedem Editor pflegbar, eine Idee pro Zeile):
  - [ ] eigen | <Idee> | <Notiz>          offen, vom Nutzer
  - [ ] system | <Idee> | <Begründung>    offen, nach dem Schema gefunden
  - [x] eigen | <Idee> | Folge 2026-10-30-slug
Abschnitt „## Schema“ beschreibt, wie das System selbst Ideen findet (Pack 4 Prompt 2). Knapp heißt: weniger als 3 offene
Ideen, dann füllt die nächste Bau-Sitzung zuerst nach dem Schema auf 10 bis 20 auf, und das Studio zeigt einen Hinweis."""
from __future__ import annotations

import argparse
import json
import re
import sys

import _ms

KNAPP = 3
ZEILE_RE = re.compile(r'^\s*-\s*\[( |x|X)\]\s*(eigen|system)\s*\|\s*([^|]+?)\s*(?:\|\s*(.*?))?\s*$')


def pfad(kanal: str):
    d = _ms.arbeit() / 'kanaele' / kanal
    if not (d / 'STATUS.json').is_file():
        raise SystemExit(f'FEHLER: Kanal {kanal} gibt es nicht (ms status --alle).')
    return d / 'IDEEN.md'


def anlegen(kanal: str) -> bool:
    p = pfad(kanal)
    if p.exists():
        return False
    vorlage = _ms.HEIM / 'vorlagen' / 'IDEEN-START.md'
    text = vorlage.read_text(encoding='utf-8') if vorlage.exists() else '# Ideenliste\n\n## Schema\n\n## Ideen\n'
    p.write_text(text.replace('__KANAL__', kanal), encoding='utf-8')
    return True


def lesen(kanal: str) -> dict:
    p = pfad(kanal)
    if not p.exists():
        return {'kanal': kanal, 'datei': str(p), 'da': False, 'offen': [], 'erledigt': [], 'knapp': True, 'schema': False}
    zeilen = p.read_text(encoding='utf-8').splitlines()
    offen, erledigt = [], []
    schema, im_schema = [], False
    for i, z in enumerate(zeilen):
        if z.startswith('## '):
            im_schema = z[3:].strip().lower().startswith('schema')
            continue
        if im_schema and z.strip() and not z.strip().startswith(('<!--', '(')):
            schema.append(z)
        m = ZEILE_RE.match(z)
        if not m:
            continue
        e = {'zeile': i, 'von': m.group(2), 'idee': m.group(3).strip(), 'notiz': (m.group(4) or '').strip()}
        (erledigt if m.group(1).lower() == 'x' else offen).append(e)
    offen.sort(key=lambda e: (e['von'] != 'eigen', e['zeile']))
    for n, e in enumerate(offen, 1):
        e['nr'] = n
    return {'kanal': kanal, 'datei': _ms.ziel_name(p), 'da': True, 'offen': offen, 'erledigt': erledigt,
            'eigen_offen': sum(1 for e in offen if e['von'] == 'eigen'), 'knapp': len(offen) < KNAPP,
            'schema': bool(schema)}


def naechste(kanal: str) -> dict | None:
    d = lesen(kanal)
    return d['offen'][0] if d['offen'] else None


def neu(kanal: str, idee: str, eigen: bool, notiz: str = '', oben: bool = False) -> dict:
    anlegen(kanal)
    p = pfad(kanal)
    idee = ' '.join(idee.split()).replace('|', '/')
    if not idee:
        raise SystemExit('FEHLER: Die Idee ist leer.')
    notiz = ' '.join((notiz or '').split()).replace('|', '/')
    zeile = f'- [ ] {"eigen" if eigen else "system"} | {idee}' + (f' | {notiz}' if notiz else '')
    zeilen = p.read_text(encoding='utf-8').splitlines()
    ideen_idx = [i for i, z in enumerate(zeilen) if ZEILE_RE.match(z)]
    kopf = next((i for i, z in enumerate(zeilen) if z.strip().lower().startswith('## ideen')), None)
    if oben:
        pos = (ideen_idx[0] if ideen_idx else (kopf + 1 if kopf is not None else len(zeilen)))
    else:
        pos = (ideen_idx[-1] + 1 if ideen_idx else (kopf + 1 if kopf is not None else len(zeilen)))
    zeilen.insert(pos, zeile)
    p.write_text('\n'.join(zeilen) + '\n', encoding='utf-8')
    _ms.log(f'Idee {"(eigen) " if eigen else ""}notiert: {idee[:80]}', ziel=f'kanal:{kanal}', art='info')
    return lesen(kanal)


def nutzen(kanal: str, welche: str, folge: str) -> dict:
    d = lesen(kanal)
    w = welche.strip()
    treffer = next((e for e in d['offen'] if str(e['nr']) == w), None) or \
        next((e for e in d['offen'] if e['idee'].lower() == w.lower()), None) or \
        next((e for e in d['offen'] if w.lower() in e['idee'].lower()), None)
    if not treffer:
        raise SystemExit(f'FEHLER: Keine offene Idee „{w}“ (ms ideen {kanal}).')
    p = pfad(kanal)
    zeilen = p.read_text(encoding='utf-8').splitlines()
    zeilen[treffer['zeile']] = f'- [x] {treffer["von"]} | {treffer["idee"]} | Folge {folge}'
    p.write_text('\n'.join(zeilen) + '\n', encoding='utf-8')
    _ms.log(f'Idee umgesetzt: {treffer["idee"][:80]} ({folge})', ziel=f'kanal:{kanal}', art='info')
    return lesen(kanal)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('kanal')
    ap.add_argument('was', nargs='?', default='liste', choices=['liste', 'naechste', 'neu', 'nutzen', 'anlegen'])
    ap.add_argument('text', nargs='?')
    ap.add_argument('--eigen', action='store_true')
    ap.add_argument('--notiz', default='')
    ap.add_argument('--oben', action='store_true')
    ap.add_argument('--folge')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    def aus(d, text):
        print(json.dumps(d, ensure_ascii=False, indent=1) if a.json else text)

    if a.was == 'anlegen':
        neu_da = anlegen(a.kanal)
        return aus({'ok': True, 'neu': neu_da}, f'{_ms.ziel_name(pfad(a.kanal))} {"angelegt" if neu_da else "gibt es schon"}.')
    if a.was == 'naechste':
        e = naechste(a.kanal)
        return aus(e or {}, f'Nächste Idee ({e["von"]}): {e["idee"]}' + (f' · {e["notiz"]}' if e['notiz'] else '') if e
                   else f'Keine offene Idee. Nach dem Schema in {_ms.ziel_name(pfad(a.kanal))} neue finden und mit ms ideen {a.kanal} neu … eintragen.')
    if a.was == 'neu':
        d = neu(a.kanal, a.text or '', a.eigen, a.notiz, a.oben)
        return aus(d, f'Notiert. Offen: {len(d["offen"])} (davon eigene {d["eigen_offen"]}).')
    if a.was == 'nutzen':
        if not a.folge:
            raise SystemExit('FEHLER: --folge fehlt.')
        d = nutzen(a.kanal, a.text or '', a.folge)
        return aus(d, f'Abgehakt. Offen: {len(d["offen"])}{" (knapp, bitte auffüllen)" if d["knapp"] else ""}.')
    d = lesen(a.kanal)
    if not d['da']:
        return aus(d, f'Noch keine Ideenliste. Anlegen: ms ideen {a.kanal} anlegen')
    z = [f'Ideenliste {a.kanal}: {len(d["offen"])} offen (eigene {d["eigen_offen"]}), {len(d["erledigt"])} umgesetzt'
         + (' · KNAPP, nach dem Schema auffüllen' if d['knapp'] else '') + ('' if d['schema'] else ' · Schema fehlt')]
    z += [f'  {e["nr"]:>2}. [{e["von"]}] {e["idee"]}' + (f' · {e["notiz"]}' if e['notiz'] else '') for e in d['offen']]
    return aus(d, '\n'.join(z))


if __name__ == '__main__':
    sys.exit(main())
