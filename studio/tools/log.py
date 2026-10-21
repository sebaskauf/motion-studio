"""Eine Zeile ins Live-Log schreiben (das Dashboard zeigt sie unter „Was gerade passiert“).
  ms log "Baue Szene s3 (3D, Blender)" [--ziel <folge-id|kanal:slug>] [--art info|warnung|fehler|frage|kosten] [--wer motion-bauer]
  ms log --zeige [--n 30]        die letzten Einträge lesen"""
import argparse
import json
import sys

import _ms


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('text', nargs='?')
    ap.add_argument('--ziel')
    ap.add_argument('--art', default='info', choices=['info', 'fertig', 'warnung', 'fehler', 'frage', 'kosten'])
    ap.add_argument('--wer')
    ap.add_argument('--zeige', action='store_true')
    ap.add_argument('--n', type=int, default=30)
    a = ap.parse_args()
    if a.zeige:
        p = _ms.arbeit() / 'live' / 'events.jsonl'
        zeilen = p.read_text(encoding='utf-8').splitlines()[-a.n:] if p.exists() else []
        for z in zeilen:
            e = json.loads(z)
            print(f"{e['zeit'][11:19]} {e.get('art', ''):<7} {e.get('wer') or '':<15} {e.get('ziel') or '':<30} {e['text']}")
        return
    if not a.text:
        ap.error('Text fehlt.')
    ziel = _ms.ziel_name(_ms.ziel_pfad(a.ziel)) if a.ziel else None
    _ms.log(a.text, wer=a.wer, ziel=ziel, art=a.art)


if __name__ == '__main__':
    sys.exit(main())
