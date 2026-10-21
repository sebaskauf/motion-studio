"""Prüft Programme, Pakete, Arbeitsordner und Profil (mit Version und Installationsbefehl fürs eigene System).
  ms check                          alle Stufen, eine Zeile pro Prüfung
  ms check --stufe basis            nur eine Stufe: basis | analyse | 3d-web | blender | sound | ki | alle
  ms check --kurz                   eine Zeile pro Stufe (für den Start jedes Agenten, ca. 3 bis 5 s)
  ms check --json                   Ergebnis als JSON (für Dashboard und Skripte)
Stufen: basis (Pflicht für alles) · analyse (Kanal zerlegen) · 3d-web (Three.js in HyperFrames) ·
        blender (optional, Beta) · sound (Sound-Bibliothek) · ki (optionale KI-Pakete)
Schlüssel aus <arbeit>/.env erscheinen nur als gesetzt/fehlt, nie mit Wert.
Exit-Code: 0 = Pflichtteile der gewählten Stufe(n) vollständig (bei "alle" zählt nur die Basis), 1 = es fehlt etwas."""
from __future__ import annotations

import argparse
import json
import platform
import sys

import _ms
import _setup

SYSTEM_NAME = {'Darwin': 'macOS', 'Windows': 'Windows', 'Linux': 'Linux'}.get(_setup.SYSTEM, _setup.SYSTEM)


def zeile_kurz(stand: dict) -> str:
    st = stand['stufe']
    if stand['ok'] and not stand['fehlt_optional']:
        return f'{st:<8} ok'
    teile = []
    if stand['fehlt_pflicht']:
        teile.append('fehlt: ' + ', '.join(p['name'] for p in stand['fehlt_pflicht']))
    if stand['fehlt_optional']:
        teile.append('optional: ' + ', '.join(p['name'] for p in stand['fehlt_optional']))
    return f'{st:<8} {"ok" if stand["ok"] else "FEHLT":<6} {" · ".join(teile)}'


def zeile_lang(p: dict) -> list[str]:
    if p['ok']:
        marke = 'ok'
    else:
        marke = 'FEHLT' if p['pflicht'] else 'fehlt'
    text = f'  {marke:<6} {p["name"]:<28} {p.get("version") or "":<12} {p.get("detail") or ""}'.rstrip()
    aus = [text]
    if not p['ok'] and p.get('installieren'):
        aus.append(f'         -> {p["installieren"]}')
    return aus


def naechster_schritt(stande: dict, basis: dict) -> str:
    if not basis['ok']:
        ids = {p['id'] for p in basis['fehlt_pflicht']}
        if ids <= {'profil'}:
            return 'Nur das Profil fehlt: Skill motion-setup (Interview) mit dem Nutzer durchgehen.'
        return 'Basis unvollständig: Skill motion-setup laden und die Stufe Basis durchgehen.'
    offen = [s for s, st in stande.items() if not st['ok']]
    if offen:
        return 'Basis vollständig. Offen (nur nötig, wenn du sie brauchst): ' + ', '.join(offen) + '.'
    return 'Alles bereit.' if len(stande) > 1 else f'Stufe {next(iter(stande))} bereit, Basis vollständig.'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--stufe', default='alle', choices=_setup.STUFEN + ['alle'])
    ap.add_argument('--kurz', action='store_true', help='eine Zeile pro Stufe')
    ap.add_argument('--json', action='store_true', help='Ausgabe als JSON')
    a = ap.parse_args()

    stufen = list(_setup.STUFEN) if a.stufe == 'alle' else [a.stufe]
    liste = _setup.pruefungen(stufen, kurz=a.kurz)
    stande = {s: _setup.stufe_stand(liste, s) for s in stufen}
    basis = _setup.stufe_stand(liste, 'basis')
    entscheidend = ['basis'] if a.stufe == 'alle' else stufen
    gesamt_ok = all(stande[s]['ok'] for s in entscheidend)

    if a.json:
        print(json.dumps({
            'ok': gesamt_ok, 'system': _setup.SYSTEM, 'architektur': platform.machine(),
            'heim': _setup.heim_aussen(), 'arbeit': _ms.arbeit().as_posix(), 'claude_ordner': _setup.claude_ordner().as_posix(),
            'stufen': {s: {'ok': st['ok'], 'fehlt_pflicht': [p['id'] for p in st['fehlt_pflicht']],
                           'fehlt_optional': [p['id'] for p in st['fehlt_optional']]} for s, st in stande.items()},
            'pruefungen': liste, 'naechster_schritt': naechster_schritt(stande, basis)}, ensure_ascii=False, indent=1))
        return 0 if gesamt_ok else 1

    if a.kurz:
        for s in stufen:
            print(zeile_kurz(stande[s]))
        print('->', naechster_schritt(stande, basis))
        return 0 if gesamt_ok else 1

    print(f'Motion-Studio Check ({SYSTEM_NAME} {platform.machine()})')
    print(f'  HEIM   {_setup.kurz_pfad(_ms.HEIM)}')
    print(f'  ARBEIT {_setup.kurz_pfad(_ms.arbeit())}')
    gezeigt = set()
    for s in stufen:
        st = stande[s]
        status = 'ok' if st['ok'] else 'FEHLT'
        if st['ok'] and st['fehlt_optional']:
            status = 'ok (optional fehlt etwas)'
        print(f'\n{s.upper()}  {status}')
        for p in st['pruefungen']:
            # Basis-Prüfungen, die auch zu einer anderen Stufe zählen, nur einmal ausführlich zeigen
            schluessel = p['id']
            if schluessel in gezeigt and s != p['stufe']:
                print(f'  {"ok" if p["ok"] else ("FEHLT" if p["pflicht"] else "fehlt"):<6} {p["name"]:<28} (siehe Basis)')
                continue
            gezeigt.add(schluessel)
            for z in zeile_lang(p):
                print(z)
    print(f'\n-> {naechster_schritt(stande, basis)}')
    return 0 if gesamt_ok else 1


if __name__ == '__main__':
    sys.exit(main())
