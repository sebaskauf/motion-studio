"""Lernlog knapp lesen und deckeln (Token-Diät: das ganze LERNLOG.md bei jedem Start zu lesen wächst ohne Grenze)
  ms lernlog --kurz [--letzte 8]          Startwissen, Abschnitt „## Lehren“ und die letzten Einträge (das liest die Regie beim Start)
  ms lernlog archivieren [--behalten 30]  ältere Einträge nach LERNLOG-ARCHIV.md verschieben (nichts geht verloren)
Ein Eintrag beginnt unter „## Einträge“ mit „### …“ oder „- <Datum> …“ (z. B. „- 30.10.2026 · …“), alles darunter gehört dazu.
Lehren, die für jede Folge gelten, gehören nach „## Lehren“ (kurz, eine Zeile je Lehre) oder in REGELN.md des Kanals."""
from __future__ import annotations

import argparse
import re
import sys

import _ms

START_RE = re.compile(r'^(### |- (\d{1,2}\.\d{1,2}\.\d{2,4}|\d{4}-\d\d-\d\d))')
GRENZE = 40


def zerlegen(text: str) -> tuple[list[str], list[list[str]], list[str]]:
    """(Teil vor „## Einträge“ inklusive Überschrift, Einträge als Zeilenblöcke, Teil nach den Einträgen)."""
    zeilen = text.splitlines()
    i = next((n for n, z in enumerate(zeilen) if z.strip().lower().startswith('## einträge')), None)
    if i is None:
        return zeilen, [], []
    kopf, rest = zeilen[:i + 1], zeilen[i + 1:]
    ende = next((n for n, z in enumerate(rest) if z.startswith('## ')), len(rest))
    eintraege: list[list[str]] = []
    for z in rest[:ende]:
        if START_RE.match(z) or not eintraege:
            if not z.strip() and not eintraege:
                continue
            eintraege.append([z])
        else:
            eintraege[-1].append(z)
    eintraege = [e for e in eintraege if any(x.strip() for x in e)]
    return kopf, eintraege, rest[ende:]


def kurz(letzte: int = 8) -> str:
    p = _ms.arbeit() / 'LERNLOG.md'
    if not p.exists():
        return 'Noch kein LERNLOG.md.'
    kopf, eintraege, nach = zerlegen(p.read_text(encoding='utf-8'))
    aus = [z for z in kopf if not z.startswith('Nach jeder Folge') and not z.startswith('was geklappt') and not z.startswith('Motion-Studio liest')]
    aus += nach
    zeigen = eintraege[-letzte:]
    if len(eintraege) > len(zeigen):
        aus.append(f'({len(eintraege) - len(zeigen)} ältere Einträge nicht gezeigt'
                   + (f'; über {GRENZE}: ms lernlog archivieren' if len(eintraege) > GRENZE else '') + ')')
    for e in zeigen:
        aus += [z[:400] for z in e]
    return '\n'.join(aus).strip()


def archivieren(behalten: int = 30) -> str:
    p = _ms.arbeit() / 'LERNLOG.md'
    kopf, eintraege, nach = zerlegen(p.read_text(encoding='utf-8'))
    if len(eintraege) <= behalten:
        return f'Nichts zu tun: {len(eintraege)} Einträge (Grenze {behalten}).'
    alt, neu = eintraege[:-behalten], eintraege[-behalten:]
    archiv = _ms.arbeit() / 'LERNLOG-ARCHIV.md'
    vorher = archiv.read_text(encoding='utf-8') if archiv.exists() else '# Lernlog-Archiv\n\nÄltere Einträge aus LERNLOG.md, älteste oben.\n'
    archiv.write_text(vorher.rstrip('\n') + '\n\n' + '\n'.join('\n'.join(e) for e in alt) + '\n', encoding='utf-8')
    p.write_text('\n'.join(kopf + [z for e in neu for z in e] + nach).rstrip('\n') + '\n', encoding='utf-8')
    return f'{len(alt)} Einträge nach LERNLOG-ARCHIV.md verschoben, {len(neu)} bleiben.'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('was', nargs='?', default='kurz', choices=['kurz', 'archivieren'])
    ap.add_argument('--kurz', action='store_true')
    ap.add_argument('--letzte', type=int, default=8)
    ap.add_argument('--behalten', type=int, default=30)
    a = ap.parse_args()
    print(archivieren(a.behalten) if a.was == 'archivieren' else kurz(a.letzte))


if __name__ == '__main__':
    sys.exit(main())
