"""Token-Verbrauch messen: je Folge und je Woche (aus den Sitzungsprotokollen von Claude Code, nur lesen)
  ms verbrauch                          Woche: gewichtete Token seit dem Reset, geschätzter Anteil am Wochenlimit, Bremse
  ms verbrauch <folge> [--eintragen]    eine Folge: Regie, Bauer, Prüfer, Analyse, Modelle; --eintragen schreibt STATUS „verbrauch“
                                        und eine Zeile ins Live-Log (Studio)
  ms verbrauch --eichen <prozent>       Ablesepunkt aus /usage („Current week“ in Prozent) direkt nach dem Ablesen: setzt die
                                        Umrechnung Token je Prozent für dieses Konto (autopilot.json limit_m_pro_prozent)
  ms verbrauch --reset "do 02:00"       Wochentag und Uhrzeit des Resets aus /usage („Resets Oct 29 at 2am“ war ein Donnerstag)
  --json für Maschinen.
Gewichtung: input + 1,25 × Cache-Schreiben + 0,1 × Cache-Lesen + 5 × Output (reel-studio, Eichung 18. bis 22.10.2026).
Ohne Eichung schätzt das Werkzeug nach Abo (ms autopilot abo …): Max 20x gemessen, Max 5x und Pro abgeleitet, also grob.
Sonnet zählt wie Opus, solange kein Ablesepunkt etwas anderes zeigt (eher zu hoch geschätzt, die Bremse greift dann früher)."""
from __future__ import annotations

import argparse
import json
import re
import sys

import _konfig
import _ms
import _verbrauch as V


def woche_text(w: dict, cfg: dict) -> str:
    z = [f'Woche seit {w["ab"][:16].replace("T", " ")}: {w["gewichtet_M"]} M gewichtete Token (davon Sonnet {w["sonnet_M"]} M)']
    if w.get('prozent') is None:
        z.append(f'Anteil am Wochenlimit: unbekannt ({w.get("grund") or "Abo fehlt"}).')
    else:
        z.append(f'Anteil am Wochenlimit: geschätzt {w["prozent"]:.0f} %' + (' (geeicht)' if w.get('geeicht') else f' (Schätzung für Abo {cfg["abo"]})')
                 + (f', Bremse bei {cfg["wochen_bremse"]} %' if cfg.get('wochen_bremse') else ', Bremse aus'))
    if not cfg.get('woche_reset'):
        z.append('Reset-Tag unbekannt: gezählt werden die letzten 7 Tage (ms verbrauch --reset "do 02:00" aus /usage).')
    return '\n'.join(z)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folge', nargs='?')
    ap.add_argument('--eintragen', action='store_true')
    ap.add_argument('--eichen', type=float, metavar='PROZENT')
    ap.add_argument('--reset', metavar='"do 02:00"')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    cfg = _konfig.konfig()

    def aus(d, text):
        print(json.dumps(d, ensure_ascii=False, indent=1, default=str) if a.json else text)

    if a.reset:
        if not re.match(r'^(mo|di|mi|do|fr|sa|so)\w*\s+\d{1,2}:\d\d$', a.reset.strip().lower()):
            raise SystemExit('FEHLER: --reset wie "do 02:00" (Wochentag kurz, Uhrzeit).')
        cfg['woche_reset'] = a.reset.strip().lower()
        _konfig.konfig_schreiben(cfg)
    if a.eichen is not None:
        if not 1 <= a.eichen <= 100:
            raise SystemExit('FEHLER: --eichen braucht den Prozentwert aus /usage (1 bis 100). Unter 1 % ist die Rundung zu grob.')
        w = V.wochen_anteil({**cfg, 'limit_m_pro_prozent': None, 'abo': cfg['abo'] or 'max20'})
        if w['gewichtet_M'] <= 0:
            raise SystemExit('FEHLER: In den Protokollen dieser Woche steht kein Verbrauch. Claude-Ordner richtig? (CLAUDE_CONFIG_DIR)')
        cfg['limit_m_pro_prozent'] = round(w['gewichtet_M'] / a.eichen, 3)
        _konfig.konfig_schreiben(cfg)
        return aus({'ok': True, 'limit_m_pro_prozent': cfg['limit_m_pro_prozent'], 'woche': w},
                   f'Geeicht: {w["gewichtet_M"]} M gewichtet = {a.eichen:g} % → {cfg["limit_m_pro_prozent"]} M je Prozent '
                   f'(100 % ≈ {cfg["limit_m_pro_prozent"] * 100:.0f} M). Gilt ab jetzt für die Wochenbremse.')
    if a.folge:
        ordner = _ms.ziel_pfad(a.folge)
        st = _ms.status_lesen(ordner)
        if not st:
            raise SystemExit(f'FEHLER: Folge {a.folge} gibt es nicht.')
        fid = str(st.get('id') or ordner.name)
        v = V.folge_verbrauch(fid)
        proz_m = V.limit_m_pro_prozent(cfg)
        v['prozent_woche'] = round(v['gesamt_M'] / proz_m, 1) if proz_m else None
        if a.eintragen and v['sitzungen']:
            _ms.status_setzen(ordner, None, None, verbrauch={'zeit': _ms.jetzt(), 'gewichtet_M': v['gesamt_M'], 'rollen': v['rollen'],
                                                            'modelle': v['modelle'], 'prozent_woche': v['prozent_woche']})
            _ms.log(f'Verbrauch {fid}: {v["gesamt_M"]} M gewichtet'
                    + (f' ≈ {v["prozent_woche"]} % der Woche' if v['prozent_woche'] is not None else ''), ziel=_ms.ziel_name(ordner), art='kosten')
        if not v['sitzungen']:
            return aus(v, f'Keine Sitzung gefunden, die hauptsächlich an {fid} gearbeitet hat ({v.get("grund") or v["ordner"]}). Liefen mehrere Folgen in einer Sitzung, zählt sie bei der meistgenannten.')
        z = [f'{fid}: {v["gesamt_M"]} M gewichtete Token' + (f' ≈ {v["prozent_woche"]} % einer Woche' if v['prozent_woche'] is not None else ''),
             '  je Rolle: ' + ', '.join(f'{k} {x} M' for k, x in sorted(v['rollen'].items(), key=lambda kv: -kv[1])),
             '  je Modell: ' + ', '.join(f'{k} {x} M' for k, x in v['modelle'].items())]
        for s in v['sitzungen']:
            z.append(f'  Sitzung {s["datei"][:8]}: {s["gewichtet_M"]} M' + (f' (auch: {", ".join(s["geteilt"])})' if s['geteilt'] else ''))
        return aus(v, '\n'.join(z))
    w = V.wochen_anteil(cfg)
    return aus(w, woche_text(w, cfg))


if __name__ == '__main__':
    sys.exit(main())
