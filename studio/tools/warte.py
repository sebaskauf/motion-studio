"""Blockierend warten, bis Bauer fertig sind oder ein Render steht, statt den Stand alle paar Sekunden abzufragen
  ms warte <folge> --bauer bauer-1 bauer-2 [--max 90]   bis build/fertig_<name>.json für alle genannten Bauer da ist
  ms warte <folge> --render v1 [--max 30]               bis out/v1.mp4 da ist und out/render_v1.log mit „fertig:“ endet
Gedacht für Claude Code: in Bash mit run_in_background starten. Claude Code meldet sich, sobald der Befehl endet,
dazwischen kostet das Warten keine Schritte (Token-Diät: gemessen 37 bis 53 Abfrage-Schritte der Regie je Nachbau, 23.10.2026).
Ausgabe: eine Zeile je fertigem Teil, am Ende eine Zusammenfassung. Code 0 = fertig, 1 = Render-Fehler, 2 = Zeit abgelaufen."""
from __future__ import annotations

import argparse
import json
import sys
import time

import _ms


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folge')
    ap.add_argument('--bauer', nargs='+')
    ap.add_argument('--render')
    ap.add_argument('--max', type=float, default=90, help='Minuten')
    ap.add_argument('--takt', type=float, default=15, help='Sekunden zwischen zwei Blicken auf die Dateien')
    a = ap.parse_args()
    if bool(a.bauer) == bool(a.render):
        raise SystemExit('FEHLER: Entweder --bauer <namen> oder --render <name>.')
    d = _ms.ziel_pfad(a.folge)
    if not (d / 'STATUS.json').is_file():
        raise SystemExit(f'FEHLER: Folge {a.folge} gibt es nicht.')
    ende = time.time() + a.max * 60
    start = time.time()
    if a.bauer:
        offen = set(a.bauer)
        while offen and time.time() < ende:
            for n in sorted(offen):
                f = d / 'build' / f'fertig_{n}.json'
                if f.is_file():
                    try:
                        j = json.loads(f.read_text(encoding='utf-8'))
                    except ValueError:
                        continue                           # wird gerade geschrieben
                    offen.discard(n)
                    print(f'{n} fertig nach {(time.time() - start) / 60:.0f} min: Szenen {", ".join(j.get("szenen") or [])}'
                          + (f' · offen: {"; ".join(map(str, j["offen"]))[:300]}' if j.get('offen') else ''), flush=True)
            if offen:
                time.sleep(a.takt)
        if offen:
            print(f'Zeit abgelaufen ({a.max:.0f} min). Noch nicht fertig: {", ".join(sorted(offen))}. '
                  f'Live-Log ansehen (ms log --zeige) und erneut warten.')
            return 2
        print('Alle Bauer fertig.')
        return 0
    video, log = d / 'out' / f'{a.render}.mp4', d / 'out' / f'render_{a.render}.log'
    while time.time() < ende:
        text = log.read_text(encoding='utf-8', errors='replace') if log.is_file() else ''
        letzte = [z for z in text.splitlines() if z.strip()][-3:]
        abbruch = [z for z in text.splitlines() if z.startswith(('FEHLER', 'ABBRUCH'))]
        if abbruch:
            print('Render abgebrochen:\n' + '\n'.join(abbruch)[-1500:])
            return 1
        if video.is_file() and letzte and letzte[-1].lstrip().startswith('fertig:'):
            print(f'Render {a.render} fertig nach {(time.time() - start) / 60:.0f} min: ' + ' | '.join(letzte)[-600:])
            return 0
        time.sleep(a.takt)
    print(f'Zeit abgelaufen ({a.max:.0f} min), Render {a.render} noch nicht fertig. Letzte Zeilen: ' + ' | '.join(letzte)[-400:])
    return 2


if __name__ == '__main__':
    sys.exit(main())
