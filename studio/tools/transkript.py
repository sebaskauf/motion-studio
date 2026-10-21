"""Wortgenaues Transkript mit Sprechtempo und Pausen (lokal und gratis: whisper.cpp oder faster-whisper).
  ms transkript <video|audio|register-id> [--sprache auto|de|en] [--out <ordner|datei.json>] [--neu]
  ms transkript --uebersicht <a.json> <b.json> …     Tabelle für den Skript-Baukasten: Dauer, Wörter, Tempo, Hook, Schluss
Beispiele:
  ms transkript vorlagen/videos/yt-abc.mp4             -> neben dem Video: yt-abc.json + yt-abc.txt
  ms transkript yt-abc                                 -> <arbeit>/vorlagen/transkripte/yt-abc.json (+ Register)
  ms transkript --uebersicht <Arbeitsordner>/vorlagen/transkripte/*.json
Ergebnis JSON: {text, sprache, woerter[{w,s,e}], saetze[{text,s,e,woerter}], stats{woerter, sprechdauer, woerter_pro_s, wpm,
pausen[{nach, s, dauer}] (> 0,4 s), laengste_pause, erstes_wort, letztes_wort}}. TXT: ein Satz pro Zeile mit Startzeit.
Hinweis: whisper setzt Wortgrenzen grob (±0,1 s). Pausen unter 0,2 s sind deshalb nicht belastbar."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import _ms

PAUSE_MIN = 0.4
MAX_SATZ = 30  # längere Wortfolgen ohne Satzzeichen werden an Pausen geteilt
SATZENDE = re.compile(r'[.!?…]["»“”\')\]]*$')


def _an_pausen_teilen(s: list) -> list:
    """Teilt eine zu lange Wortfolge an der größten Pause, bis jedes Stück höchstens MAX_SATZ Wörter hat."""
    if len(s) <= MAX_SATZ:
        return [s]
    luecken = [(s[i + 1]['s'] - s[i]['e'], i) for i in range(4, len(s) - 5)]
    _, i = max(luecken) if luecken else (0, len(s) // 2)
    return _an_pausen_teilen(s[:i + 1]) + _an_pausen_teilen(s[i + 1:])


def auswerten(roh: dict) -> dict:
    """Ergänzt ein Rohtranskript (_ms.transkribiere) um Sätze und Kennzahlen."""
    woerter = [w for w in roh.get('woerter', []) if str(w.get('w', '')).strip()]
    saetze, aktuell = [], []
    for w in woerter:
        aktuell.append(w)
        if SATZENDE.search(w['w']):
            saetze.append(aktuell)
            aktuell = []
    if aktuell:
        saetze.append(aktuell)
    ohne_zeichen = any(len(s) > MAX_SATZ for s in saetze)
    if ohne_zeichen:  # whisper hat (teilweise) keine Satzzeichen gesetzt: an Sprechpausen teilen
        saetze = [teil for s in saetze for teil in _an_pausen_teilen(s)]
    saetze_aus = [{'text': ' '.join(x['w'] for x in s), 's': round(s[0]['s'], 2), 'e': round(s[-1]['e'], 2),
                   'woerter': len(s)} for s in saetze]
    pausen = []
    for a, b in zip(woerter, woerter[1:]):
        luecke = b['s'] - a['e']
        if luecke > PAUSE_MIN:
            pausen.append({'nach': a['w'], 's': round(a['e'], 2), 'dauer': round(luecke, 2)})
    stats = {'woerter': len(woerter)}
    if woerter:
        dauer = max(0.01, woerter[-1]['e'] - woerter[0]['s'])
        stats.update({'sprechdauer': round(dauer, 2), 'woerter_pro_s': round(len(woerter) / dauer, 2),
                      'wpm': round(len(woerter) / dauer * 60), 'pausen': pausen, 'pausen_anzahl': len(pausen),
                      'laengste_pause': max((p['dauer'] for p in pausen), default=0.0),
                      'erstes_wort': round(woerter[0]['s'], 2), 'letztes_wort': round(woerter[-1]['e'], 2),
                      'saetze': len(saetze_aus), 'saetze_aus_pausen': ohne_zeichen,
                      'woerter_pro_satz': round(len(woerter) / max(1, len(saetze_aus)), 1)})
    return {'text': roh.get('text', ''), 'sprache': roh.get('sprache'), 'woerter': woerter, 'saetze': saetze_aus,
            'stats': stats, 'erstellt': _ms.jetzt()}


def txt_schreiben(t: dict, ziel: Path) -> Path:
    zeilen = [f"[{s['s']:6.2f} s] {s['text']}" for s in t.get('saetze', [])]
    ziel.write_text('\n'.join(zeilen) + '\n', encoding='utf-8')
    return ziel


def transkribieren(quelle, ziel_json, sprache='auto', neu=False) -> dict:
    """Transkribiert quelle, schreibt ziel_json + .txt. Liegt das Ergebnis schon vor, wird es geladen (außer neu=True)."""
    ziel_json = Path(ziel_json)
    if ziel_json.exists() and not neu:
        t = _ms.json_lesen(ziel_json)
        if t and 'stats' in t:
            return t
    info = _ms.probe(quelle) if Path(quelle).suffix.lower() not in ('.wav', '.m4a', '.mp3', '.aac', '.flac', '.ogg', '.aiff', '.aif', '.opus') else None
    if info is not None and not info.get('ton'):
        raise SystemExit(f'FEHLER: {quelle} hat keine Tonspur. Bei Instagram-Videos: Ton fehlt oft im Videolink, '
                         f'"ms laden <id>" holt ihn nach.')
    t = auswerten(_ms.transkribiere(quelle, sprache))
    t['quelle'] = str(quelle)
    _ms.json_schreiben(ziel_json, t)
    txt_schreiben(t, ziel_json.with_suffix('.txt'))
    return t


def kurzbericht(t: dict) -> str:
    s = t.get('stats', {})
    if not s.get('woerter'):
        return 'keine Sprache erkannt'
    return (f"{s['woerter']} Wörter in {s['sprechdauer']} s = {s['woerter_pro_s']} Wörter/s ({s['wpm']} wpm), "
            f"{s['saetze']} Sätze, {s['pausen_anzahl']} Pausen > {PAUSE_MIN} s, Sprache {t.get('sprache')}")


def uebersicht(dateien) -> str:
    """Markdown-Tabelle über mehrere Transkripte: Grundlage für SKRIPT-BAUKASTEN.md."""
    zeilen = ['| Datei | Sprechdauer | Wörter | Wörter/s | Sätze | Hook (1. Satz) | Hook-Dauer | Schluss (letzter Satz) |',
              '|---|---|---|---|---|---|---|---|']
    werte = []
    for d in dateien:
        t = _ms.json_lesen(d, {}) or {}
        if 'stats' not in t and 'woerter' in t:
            t = auswerten(t)
        s = t.get('stats', {})
        if not s.get('woerter'):
            zeilen.append(f'| {Path(d).stem} | - | 0 | - | - | (keine Sprache) | - | - |')
            continue
        saetze = t.get('saetze') or [{'text': t.get('text', ''), 's': 0, 'e': 0}]
        hook, schluss = saetze[0], saetze[-1]
        werte.append(s)
        zeilen.append(f"| {Path(d).stem} | {s['sprechdauer']} s | {s['woerter']} | {s['woerter_pro_s']} | {s['saetze']} | "
                      f"{hook['text'][:90]} | {hook['e'] - hook['s']:.1f} s | {schluss['text'][:70]} |")
    if werte:
        import statistics as st
        zeilen.append('')
        zeilen.append(f"Median: {st.median(w['sprechdauer'] for w in werte):.1f} s Sprechdauer, "
                      f"{st.median(w['woerter'] for w in werte):.0f} Wörter, {st.median(w['woerter_pro_s'] for w in werte):.2f} Wörter/s, "
                      f"{st.median(w['woerter_pro_satz'] for w in werte):.1f} Wörter pro Satz ({len(werte)} Transkripte).")
    return '\n'.join(zeilen)


def main():
    ap = argparse.ArgumentParser(prog='ms transkript', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('quelle', nargs='*')
    ap.add_argument('--sprache', default='auto')
    ap.add_argument('--out')
    ap.add_argument('--neu', action='store_true', help='neu transkribieren, auch wenn es das Ergebnis schon gibt')
    ap.add_argument('--uebersicht', action='store_true', help='Tabelle über mehrere Transkript-JSONs')
    a = ap.parse_args()
    if not a.quelle:
        ap.error('Datei oder Register-ID fehlt.')
    if a.uebersicht:
        print(uebersicht(a.quelle))
        return
    if len(a.quelle) > 1:
        ap.error('Bitte nur eine Datei (mehrere nur mit --uebersicht).')
    q = a.quelle[0]
    p = Path(q).expanduser()
    vid = None
    if not p.exists():
        import vorlagen as V
        e = V.finden(V.lesen(), q)
        if not e:
            raise SystemExit(f'FEHLER: "{q}" ist weder eine Datei noch eine Register-ID.')
        p = V.abs_pfad(e.get('video'))
        if not p or not p.exists():
            raise SystemExit(f'FEHLER: Zu {q} gibt es noch kein Video. Erst "ms laden {q}".')
        vid = q
    if a.out:
        ziel = Path(a.out).expanduser()
        ziel = ziel if ziel.suffix == '.json' else ziel / f'{p.stem}.json'
    elif vid:
        ziel = _ms.arbeit() / 'vorlagen' / 'transkripte' / f'{vid}.json'
    else:
        ziel = p.with_suffix('.json')
    print(f'Transkribiere {p.name} (lokal) …', flush=True)
    t = transkribieren(p, ziel, a.sprache, a.neu)
    if vid:
        import vorlagen as V
        V.status_setzen(vid, 'neu', transkript=V.rel(ziel))
    print(kurzbericht(t))
    for s in t.get('saetze', [])[:3]:
        print(f"  [{s['s']:5.1f} s] {s['text'][:110]}")
    print(ziel)
    print(ziel.with_suffix('.txt'))


if __name__ == '__main__':
    sys.exit(main())
