"""Posten vorbereiten und Ergebnisse festhalten (das Hochladen selbst macht der Agent über Claude in Chrome, Skill motion-posten)
  ms posten [--kanal <k>] [--json]                    Stand: Plattformen, Freigaben, Vorrat, Pause-Grund
  ms posten pruefen <folge> [--json]                  darf diese Folge raus? (Code 1, wenn nicht) plus Dateien fürs Hochladen
  ms posten datei <folge> [--max-mb 9.5]              upload/post.mp4 unter der Upload-Grenze von Claude in Chrome (10 MB je Datei)
  ms posten ergebnis <folge> --plattform instagram --link <url>        Post hat geklappt
  ms posten ergebnis <folge> --plattform instagram --fehler "<was>"    Post ist gescheitert: rot im Studio, Folge bleibt liegen
  ms posten erledigt <folge> [--plattform <p>]        Fehler erledigt (selbst hochgeladen oder neuer Versuch erlaubt)
  ms posten freigabe <kanal> <plattform> --zitat "<Ja des Nutzers>"
                     NUR nach dem ersten Lauf, der vor „Veröffentlichen“ gestoppt hat und den der Nutzer mit Ja bestätigt hat.
                     Voraussetzung: kanaele/<k>/posten/<plattform>.md (gespeicherter Ablauf). Ab dann postet der Autopilot dort.
  ms posten freigabe <kanal> <plattform> --zurueck    Freigabe zurücknehmen (Ablauf-Datei bleibt)
Regeln (Sebastian 30.10.2026): Gepostet werden nur eigene, fertige, geprüfte Folgen (quelle eigen), nie Pilot, Nachbau oder Kopie.
Der erste Lauf je Plattform stoppt immer vor „Veröffentlichen“ und fragt. Plattformen: instagram, tiktok, youtube, facebook."""
from __future__ import annotations

import argparse
import json
import re
import sys

import _ms
import _vorrat as V

LINK_RE = re.compile(r'^https?://[^\s"\'<>`\\]{3,500}$')


def _folge(fid: str):
    d = _ms.ziel_pfad(fid)
    st = _ms.status_lesen(d)
    if not st or st.get('art') == 'kanal':
        raise SystemExit(f'FEHLER: Folge {fid} gibt es nicht (ms status --alle).')
    st['_ordner'] = _ms.ziel_name(d)
    return d, st


def _plattform(p: str) -> str:
    p = (p or '').strip().lower()
    if p not in V.PLATTFORMEN:
        raise SystemExit(f'FEHLER: Plattform "{p}" unbekannt. Erlaubt: {", ".join(V.PLATTFORMEN)}')
    return p


def stand(kanal: str | None = None) -> dict:
    """Für Terminal, Autopilot und Studio."""
    kanaele = [s for s in V._alle() if s.get('art') == 'kanal']
    namen = [kanal] if kanal else [str(k.get('id') or k['_ordner'].split('/', 1)[1]) for k in kanaele]
    aus = {'profil_plattformen': V.plattformen_profil(), 'kanaele': {}}
    for k in namen:
        vr = V.vorrat(k)
        aus['kanaele'][k] = {'freigaben': V.freigaben(k), 'ziel': V.ziel_plattformen(k),
                             'vorrat': vr, 'postbar': sum(1 for v in vr if v['postbar']),
                             'fehler': [v for v in vr if v['fehler']]}
    return aus


def pruefen(fid: str) -> dict:
    d, st = _folge(fid)
    e = V.eintrag(st)
    dateien = V.upload_dateien(d, V.folge_id(st))
    frei = V.freigaben(e['kanal'])
    e.update({'dateien': {k: str(v) if v else None for k, v in dateien.items()},
              'freigegeben': [p for p in e['offen'] if p in frei], 'erster_lauf': [p for p in e['offen'] if p not in frei],
              'abläufe': {p: frei[p]['ablauf'] for p in e['offen'] if p in frei}})
    return e


def datei(fid: str, max_mb: float = 9.5) -> dict:
    """Kopie für den Upload, die unter die Grenze passt. Das Original bleibt unverändert."""
    d, st = _folge(fid)
    dateien = V.upload_dateien(d, V.folge_id(st))
    quelle = dateien['video']
    if not quelle:
        raise SystemExit('FEHLER: Kein Video im Upload-Ordner. Erst motion-folge Schritt 9 (Upload-Paket).')
    ziel = d / 'upload' / 'post.mp4'
    groesse = quelle.stat().st_size / 1e6
    if groesse <= max_mb:
        if not ziel.exists() or ziel.stat().st_size != quelle.stat().st_size:
            _ms.befehl(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(quelle), '-c', 'copy', '-movflags', '+faststart', str(ziel)])
        return {'datei': str(ziel), 'mb': round(ziel.stat().st_size / 1e6, 2), 'neu_kodiert': False}
    dauer = float(_ms.probe(quelle).get('dauer') or 0) or 60.0
    ton_k = 128
    bild_k = max(800, int(max_mb * 8000 * 0.94 / dauer) - ton_k)   # 6 % Reserve für Container und Schwankung
    _ms.befehl(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(quelle), '-c:v', 'libx264', '-preset', 'slow', '-b:v', f'{bild_k}k',
                '-maxrate', f'{int(bild_k * 1.3)}k', '-bufsize', f'{bild_k * 2}k', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', f'{ton_k}k',
                '-movflags', '+faststart', str(ziel)])
    mb = ziel.stat().st_size / 1e6
    if mb > max_mb:
        raise SystemExit(f'FEHLER: post.mp4 ist {mb:.1f} MB, Grenze {max_mb} MB. Mit --max-mb {max_mb - 1} noch einmal.')
    return {'datei': str(ziel), 'mb': round(mb, 2), 'neu_kodiert': True, 'bild_kbit': bild_k}


def ergebnis(fid: str, plattform: str, link: str | None, fehler: str | None) -> dict:
    d, st = _folge(fid)
    p = _plattform(plattform)
    if bool(link) == bool(fehler):
        raise SystemExit('FEHLER: Entweder --link (hat geklappt) oder --fehler (gescheitert).')
    ps = dict(V.posts(st))
    name = V.NAMEN[p]
    if link:
        if not LINK_RE.match(link):
            raise SystemExit('FEHLER: --link muss mit https:// beginnen.')
        ps[p] = {'zeit': _ms.jetzt(), 'ok': True, 'link': link}
        felder = {'posts': ps}
        rest = V.fehler_posten(dict(st, posts=ps))
        if str(st.get('fehler') or '').startswith('Posten') and not rest:
            felder['fehler'] = None
        offen = V.offen_auf(dict(st, posts=ps), V.ziel_plattformen(str(st.get('kanal') or '')) or [p])
        phase = None
        if not offen:
            phase = 'gepostet'
            felder['gepostet'] = {'zeit': _ms.jetzt(), 'link': link, 'plattform': p}
        neu = _ms.status_setzen(d, phase, f'Gepostet auf {name}' + ('' if offen else ', überall raus'), **felder)
        _ms.log(f'Gepostet auf {name}: {link}', ziel=_ms.ziel_name(d), art='fertig', wer='motion-posten')
        return {'ok': True, 'phase': neu.get('phase'), 'offen': offen}
    text = ' '.join(str(fehler).split())[:300]
    ps[p] = {'zeit': _ms.jetzt(), 'ok': False, 'fehler': text}
    _ms.status_setzen(d, None, None, posts=ps, fehler=f'Posten auf {name} fehlgeschlagen: {text}. Folge liegt zum selbst Hochladen '
                                                       f'in upload/. Danach: ms posten erledigt {V.folge_id(st)}')
    _ms.log(f'Posten auf {name} fehlgeschlagen: {text}', ziel=_ms.ziel_name(d), art='fehler', wer='motion-posten')
    return {'ok': False, 'fehler': text}


def erledigt(fid: str, plattform: str | None = None) -> dict:
    d, st = _folge(fid)
    ps = dict(V.posts(st))
    for p, v in ps.items():
        if isinstance(v, dict) and v.get('ok') is False and (not plattform or p == _plattform(plattform)):
            ps[p] = dict(v, erledigt=_ms.jetzt())
    felder = {'posts': ps}
    if str(st.get('fehler') or '').startswith('Posten') and not V.fehler_posten(dict(st, posts=ps)):
        felder['fehler'] = None
    _ms.status_setzen(d, None, None, **felder)
    return {'ok': True}


def freigabe(kanal: str, plattform: str, zitat: str | None, zurueck=False) -> dict:
    p = _plattform(plattform)
    d = V.kanal_ordner(kanal)
    if not (d / 'STATUS.json').is_file():
        raise SystemExit(f'FEHLER: Kanal {kanal} gibt es nicht.')
    datei_f = d / 'posten' / 'freigabe.json'
    roh = _ms.json_lesen(datei_f, {}) or {}
    if zurueck:
        roh.pop(p, None)
        _ms.json_schreiben(datei_f, roh)
        _ms.log(f'Posten auf {V.NAMEN[p]} für {kanal}: Freigabe zurückgenommen', ziel=f'kanal:{kanal}', art='warnung')
        return {'ok': True, 'freigaben': sorted(roh)}
    if not (d / 'posten' / f'{p}.md').is_file():
        raise SystemExit(f'FEHLER: kanaele/{kanal}/posten/{p}.md fehlt. Erst den ersten Lauf bis vor „Veröffentlichen“ machen, '
                         'den Ablauf dort festhalten und das Ja des Nutzers holen (Skill motion-posten).')
    zitat = ' '.join(str(zitat or '').split())
    if len(zitat) < 2:
        raise SystemExit('FEHLER: --zitat fehlt: das Ja des Nutzers wörtlich (z. B. "ja, passt so").')
    roh[p] = {'zeit': _ms.jetzt(), 'zitat': zitat[:200]}
    _ms.json_schreiben(datei_f, roh)
    _ms.log(f'Posten auf {V.NAMEN[p]} für {kanal} freigegeben', ziel=f'kanal:{kanal}', art='fertig')
    return {'ok': True, 'freigaben': sorted(roh)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('was', nargs='?', default='stand', choices=['stand', 'pruefen', 'datei', 'ergebnis', 'erledigt', 'freigabe'])
    ap.add_argument('ziel', nargs='?', help='Folge-ID, bei freigabe der Kanal')
    ap.add_argument('plattform_pos', nargs='?', metavar='plattform')
    ap.add_argument('--kanal')
    ap.add_argument('--plattform')
    ap.add_argument('--link')
    ap.add_argument('--fehler')
    ap.add_argument('--zitat')
    ap.add_argument('--zurueck', action='store_true')
    ap.add_argument('--max-mb', type=float, default=9.5)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    def aus(d, text):
        print(json.dumps(d, ensure_ascii=False, indent=1, default=str) if a.json else text)

    if a.was == 'stand':
        s = stand(a.kanal)
        z = [f'Plattformen im Profil: {", ".join(V.NAMEN[p] for p in s["profil_plattformen"]) or "keine (PROFIL.md, Zeile Plattformen)"}']
        for k, w in s['kanaele'].items():
            frei = ', '.join(V.NAMEN[p] for p in w['freigaben']) or 'noch keine (erster Lauf mit Stopp vor Veröffentlichen fehlt)'
            z.append(f'Kanal {k}: freigegeben {frei} · Vorrat {len(w["vorrat"])}, davon postbar {w["postbar"]}')
            z += [f'  {v["folge_id"]:<40} {"postbar" if v["postbar"] else v["grund"]}' for v in w['vorrat']]
        return aus(s, '\n'.join(z))
    if not a.ziel:
        raise SystemExit(f'FEHLER: ms posten {a.was} braucht {"den Kanal" if a.was == "freigabe" else "die Folge"}.')
    if a.was == 'pruefen':
        e = pruefen(a.ziel)
        text = (f'{e["folge_id"]}: {"darf raus" if e["postbar"] else "darf NICHT raus: " + e["grund"]}\n'
                f'  offen auf: {", ".join(e["offen"]) or "-"} · freigegeben: {", ".join(e["freigegeben"]) or "-"} · '
                f'erster Lauf (Stopp vor Veröffentlichen): {", ".join(e["erster_lauf"]) or "-"}\n'
                + '\n'.join(f'  {k}: {v}' for k, v in e['dateien'].items() if v))
        aus(e, text)
        return 0 if e['postbar'] else 1
    if a.was == 'datei':
        e = datei(a.ziel, a.max_mb)
        return aus(e, f'{e["datei"]} ({e["mb"]} MB{", neu kodiert" if e["neu_kodiert"] else ""})')
    if a.was == 'ergebnis':
        e = ergebnis(a.ziel, a.plattform or a.plattform_pos or '', a.link, a.fehler)
        return aus(e, ('OK, eingetragen.' + (' Überall gepostet.' if not e['offen'] else f' Offen: {", ".join(e["offen"])}'))
                   if e['ok'] else f'Fehler eingetragen, im Studio rot: {e["fehler"]}')
    if a.was == 'erledigt':
        return aus(erledigt(a.ziel, a.plattform or a.plattform_pos), 'Erledigt.')
    if a.was == 'freigabe':
        e = freigabe(a.ziel, a.plattform or a.plattform_pos or '', a.zitat, a.zurueck)
        return aus(e, f'Freigaben für {a.ziel}: {", ".join(e["freigaben"]) or "keine"}')


if __name__ == '__main__':
    sys.exit(main())
