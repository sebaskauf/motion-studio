"""Stand von Folgen und Kanälen lesen und setzen (STATUS.json, Grundlage fürs Dashboard).
  ms status                                  alle offenen Folgen/Kanäle (zum Weitermachen)
  ms status --alle                           auch fertige und gepostete
  ms status <ziel>                           eine Folge/einen Kanal zeigen (ziel = Folge-ID, Ordner oder kanal:<slug>)
  ms status <ziel> <phase> [--notiz "…"]     Phase als erreicht setzen
  Felder (beliebig kombinierbar, auch ohne Phase):
    --titel T  --video out/x.mp4  --vorschau out/x.jpg  --geplant 2026-10-21T18:00
    --fehler "…" | --fehler-weg      --wartet "Frage an den Nutzer" | --wartet-weg
    --kosten 0.42 USD "Apify 30 Reels"  --gepostet <link> [--plattform instagram]
Phasen Folge: vorlage skript stimme storyboard szenen ton render vergleich pruefung fertig geplant gepostet
Phasen Kanal: vorbild zerlegt bibel pilot gemessen kit bereit"""
import argparse
import json
import sys

import _ms

FERTIG = {'fertig', 'geplant', 'gepostet', 'bereit'}


def zeile(st):
    teile = [f"{st.get('_ordner', st.get('id', '?')):<42}", f"{st.get('phase') or 'neu':<10}"]
    if st.get('wartet_auf'):
        teile.append(f"WARTET: {st['wartet_auf']}")
    if st.get('fehler'):
        teile.append(f"FEHLER: {st['fehler']}")
    teile.append(st.get('titel') or '')
    return '  '.join(t for t in teile if t)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('ziel', nargs='?')
    ap.add_argument('phase', nargs='?')
    ap.add_argument('--notiz')
    ap.add_argument('--alle', action='store_true')
    ap.add_argument('--titel')
    ap.add_argument('--video')
    ap.add_argument('--vorschau')
    ap.add_argument('--geplant')
    ap.add_argument('--fehler')
    ap.add_argument('--fehler-weg', action='store_true')
    ap.add_argument('--wartet')
    ap.add_argument('--wartet-weg', action='store_true')
    ap.add_argument('--kosten', nargs=3, metavar=('BETRAG', 'EINHEIT', 'WAS'))
    ap.add_argument('--gepostet')
    ap.add_argument('--plattform', default='instagram')
    ap.add_argument('--json', action='store_true', help='Ausgabe als JSON')
    a = ap.parse_args()

    if not a.ziel:
        liste = [s for s in _ms.alle_status() if a.alle or s.get('phase') not in FERTIG]
        if a.json:
            print(json.dumps(liste, ensure_ascii=False, indent=1))
            return
        if not liste:
            print('Nichts offen.' if not a.alle else 'Noch keine Folgen oder Kanäle angelegt.')
        for st in liste:
            print(zeile(st))
        return

    ordner = _ms.ziel_pfad(a.ziel)
    felder = {}
    for k in ('titel', 'video', 'vorschau', 'geplant'):
        if getattr(a, k):
            felder[k] = getattr(a, k)
    if a.fehler:
        felder['fehler'] = a.fehler
    if a.fehler_weg:
        felder['fehler'] = None
    if a.wartet:
        felder['wartet_auf'] = a.wartet
    if a.wartet_weg:
        felder['wartet_auf'] = None
    st = _ms.status_lesen(ordner)
    if a.kosten:
        betrag, einheit, was = a.kosten
        felder['kosten'] = (st.get('kosten') or []) + [{'zeit': _ms.jetzt(), 'betrag': float(betrag.replace(',', '.')),
                                                         'einheit': einheit, 'was': was}]
    if a.gepostet:
        felder['gepostet'] = {'zeit': _ms.jetzt(), 'link': a.gepostet, 'plattform': a.plattform}
        a.phase = a.phase or 'gepostet'

    if a.phase or a.notiz or felder:
        st = _ms.status_setzen(ordner, a.phase, a.notiz, **felder)
        if a.fehler:
            _ms.log(a.fehler, ziel=_ms.ziel_name(ordner), art='fehler')
        if a.wartet:
            _ms.log(a.wartet, ziel=_ms.ziel_name(ordner), art='frage')
        if a.kosten:
            _ms.log(f'Kosten: {a.kosten[0]} {a.kosten[1]} für {a.kosten[2]}', ziel=_ms.ziel_name(ordner), art='kosten')
    print(json.dumps(st, ensure_ascii=False, indent=1) if (a.json or not (a.phase or felder)) else
          f"OK {_ms.ziel_name(ordner)}: Phase {st.get('phase')}")


if __name__ == '__main__':
    sys.exit(main())
