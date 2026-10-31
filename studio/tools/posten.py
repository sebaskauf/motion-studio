"""Posten vorbereiten und Ergebnisse festhalten (das Hochladen selbst macht der Agent über Claude in Chrome, Skill motion-posten)
  ms posten [--kanal <k>] [--json]                    Stand: Plattformen, Freigaben, Vorrat, Pause-Grund
  ms posten pruefen <folge> [--json]                  darf diese Folge raus? (Code 1, wenn nicht) plus Dateien fürs Hochladen
  ms posten datei <folge>                             Video in voller Qualität für den Upload vorbereiten: upload/post.mp4 (Kopie
                                                      mit faststart) plus upload/stuecke/ (Stücke unter 10 MB + stuecke.json)
  ms posten js auffangen|pruefen|einsetzen|ablegen|aufraeumen <folge> [--feld <css>]
                                                      fertiges JavaScript für javascript_tool (Skill motion-video-hochladen)
  ms posten ergebnis <folge> --plattform instagram --link <url>        Post hat geklappt
  ms posten ergebnis <folge> --plattform instagram --fehler "<was>"    Post ist gescheitert: rot im Studio, Folge bleibt liegen
  ms posten erledigt <folge> [--plattform <p>]        Fehler erledigt (selbst hochgeladen oder neuer Versuch erlaubt)
  ms posten eigen <folge> --zitat "<Ja des Nutzers>"  Folge aus einer älteren Version (ohne quelle) als eigene markieren, NUR nach
                                                      Rückfrage: Ist der Inhalt seiner oder eine Nacherzählung? Nie Pilot, Nachbau oder Kopie.
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


STUECK_BYTES = 9_900_000   # Claude in Chrome: file_upload nimmt höchstens 10 MB je Aufruf (alle Dateien zusammen)
STUECK_RE = re.compile(r'^post\.mp4\.teil\d{3}$')


def _sha(pfad, start=0, laenge=None) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(pfad, 'rb') as f:
        f.seek(start)
        rest = laenge
        while rest is None or rest > 0:
            block = f.read(1 << 20 if rest is None else min(1 << 20, rest))
            if not block:
                break
            h.update(block)
            if rest is not None:
                rest -= len(block)
    return h.hexdigest()


def datei(fid: str) -> dict:
    """Upload in voller Qualität (Sebastian 31.10.2026, Methode vom 18.10.): Das Video wird nicht kleiner gerechnet, sondern in
    Stücke unter 10 MB geteilt. Der Agent lädt jedes Stück einzeln per file_upload in ein eigenes Dateifeld im Browser, prüft sie
    dort per SHA-256 und setzt sie zu einer Datei zusammen, die ins echte Upload-Feld der Plattform kommt (ms posten js).
    Das Original bleibt unverändert. Ohne split/ffmpeg-Neukodierung, läuft auch unter Windows."""
    d, st = _folge(fid)
    folge_id = V.folge_id(st)
    dateien = V.upload_dateien(d, folge_id)
    quelle = dateien['video']
    if not quelle:
        raise SystemExit('FEHLER: Kein Video im Upload-Ordner. Erst motion-folge Schritt 9 (Upload-Paket).')
    up = d / 'upload'
    ziel = up / 'post.mp4'
    if not ziel.exists() or ziel.stat().st_mtime < quelle.stat().st_mtime:
        _ms.befehl(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(quelle), '-map', '0', '-c', 'copy', '-movflags', '+faststart',
                    str(ziel)])
    groesse = ziel.stat().st_size
    ordner = up / 'stuecke'
    ordner.mkdir(exist_ok=True)
    manifest_pfad = ordner / 'stuecke.json'
    alt = _ms.json_lesen(manifest_pfad, {}) or {}
    if (alt.get('groesse') == groesse and alt.get('mtime') == int(ziel.stat().st_mtime)
            and all((ordner / x['name']).is_file() and (ordner / x['name']).stat().st_size == x['groesse'] for x in alt.get('stuecke', []))):
        return dict(alt, manifest=str(manifest_pfad), neu=False)
    for f in ordner.iterdir():   # nur eigene, alte Stücke ersetzen
        if STUECK_RE.match(f.name):
            f.unlink()
    stuecke = []
    with open(ziel, 'rb') as f:
        i = 0
        while True:
            block = f.read(STUECK_BYTES)
            if not block:
                break
            i += 1
            name = f'post.mp4.teil{i:03d}'
            (ordner / name).write_bytes(block)
            import hashlib
            stuecke.append({'name': name, 'pfad': str(ordner / name), 'groesse': len(block), 'sha256': hashlib.sha256(block).hexdigest()})
    if i > 999:
        raise SystemExit('FEHLER: Mehr als 999 Stücke (über 9,9 GB). Zu groß für den Upload.')
    m = {'folge': folge_id, 'datei': str(ziel), 'name': f'{folge_id}.mp4', 'mime': 'video/mp4', 'groesse': groesse,
         'mtime': int(ziel.stat().st_mtime), 'sha256': _sha(ziel), 'stueck_bytes': STUECK_BYTES, 'anzahl': len(stuecke),
         'stuecke': stuecke, 'erstellt': _ms.jetzt()}
    _ms.json_schreiben(manifest_pfad, m)
    return dict(m, manifest=str(manifest_pfad), neu=True)


def _manifest(fid: str) -> dict:
    d, st = _folge(fid)
    m = _ms.json_lesen(d / 'upload' / 'stuecke' / 'stuecke.json', {}) or {}
    if not m.get('stuecke'):
        raise SystemExit(f'FEHLER: Keine Stücke. Erst: ms posten datei {fid}')
    return m


JS_AUFFANGEN = """window.claudeChunks = window.claudeChunks || {};
if (!document.querySelector('input[aria-label="CLAUDE CHUNK UPLOAD"]')) {
  const u = document.createElement('input'); u.type = 'file'; u.multiple = true; u.setAttribute('aria-label', 'CLAUDE CHUNK UPLOAD');
  u.style.cssText = 'position:fixed;left:0;bottom:0;width:10px;height:10px;opacity:0.01;z-index:2147483647';
  u.addEventListener('change', () => { for (const f of u.files) window.claudeChunks[f.name] = f; });
  document.body.appendChild(u);
}
JSON.stringify({feld: !!document.querySelector('input[aria-label="CLAUDE CHUNK UPLOAD"]'), stuecke_im_browser: Object.keys(window.claudeChunks).length})"""

JS_AUFRAEUMEN = """delete window.claudeChunks; delete window.claudePruefung; delete window.claudeVideo;
document.querySelectorAll('input[aria-label="CLAUDE CHUNK UPLOAD"]').forEach(e => e.remove());
JSON.stringify({aufgeraeumt: true})"""


def js(schritt: str, fid: str | None = None, feld: str | None = None) -> str:
    """JavaScript für mcp__claude-in-chrome__javascript_tool. Jede Abfrage bleibt unter 30 s (das Werkzeug bricht bei 45 s ab)."""
    if schritt == 'auffangen':
        return JS_AUFFANGEN
    if schritt == 'aufraeumen':
        return JS_AUFRAEUMEN
    if not fid:
        raise SystemExit(f'FEHLER: ms posten js {schritt} braucht die Folge.')
    m = _manifest(fid)
    soll = {x['name']: [x['groesse'], x['sha256']] for x in m['stuecke']}
    kopf = (f"const SOLL = {json.dumps(soll, separators=(',', ':'))};\nconst GROESSE = {int(m['groesse'])};\n"
            f"const NAME = {json.dumps(m['name'])};\n")
    if schritt == 'pruefen':
        return kopf + """const c = window.claudeChunks || {};
const fehlt = Object.keys(SOLL).filter(n => !c[n]);
if (!window.claudePruefung || window.claudePruefung.anzahl !== Object.keys(c).length) {
  const P = window.claudePruefung = {status: 'laeuft', ok: [], falsch: [], anzahl: Object.keys(c).length};
  (async () => { for (const n of Object.keys(SOLL)) { if (!c[n]) continue;
    const h = [...new Uint8Array(await crypto.subtle.digest('SHA-256', await c[n].arrayBuffer()))].map(x => x.toString(16).padStart(2, '0')).join('');
    (h === SOLL[n][1] && c[n].size === SOLL[n][0] ? P.ok : P.falsch).push(n); } P.status = 'fertig'; })();
}
const t0 = Date.now(); while (window.claudePruefung.status !== 'fertig' && Date.now() - t0 < 25000) await new Promise(r => setTimeout(r, 500));
const P = window.claudePruefung;
JSON.stringify({status: P.status, soll: Object.keys(SOLL).length, ok: P.ok.length, fehlt, falsch: P.falsch,
  alles_gut: P.status === 'fertig' && fehlt.length === 0 && P.falsch.length === 0 && P.ok.length === Object.keys(SOLL).length})"""
    if schritt in ('einsetzen', 'ablegen'):
        feld_js = json.dumps(feld or '')
        basis = kopf + f"const FELD = {feld_js};\n" + """const c = window.claudeChunks || {}; const P = window.claudePruefung || {};
const namen = Object.keys(SOLL).sort();
const bereit = namen.every(n => c[n]) && P.status === 'fertig' && P.falsch.length === 0 && P.ok.length === namen.length;
let erg = {bereit};
if (bereit) {
  const datei = window.claudeVideo = new File(namen.map(n => c[n]), NAME, {type: 'video/mp4', lastModified: Date.now()});
  erg.groesse_ok = datei.size === GROESSE; erg.groesse = datei.size;
"""
        if schritt == 'einsetzen':
            return basis + """  const unser = e => e.getAttribute('aria-label') === 'CLAUDE CHUNK UPLOAD';
  let kand = FELD ? [...document.querySelectorAll(FELD)] : [...document.querySelectorAll('input[type=file]')].filter(e => !unser(e));
  const video = kand.filter(e => !e.accept || /video|\\*|mp4|mov/i.test(e.accept));
  const ziel = (video.length ? video : kand).pop();
  erg.felder = kand.map(e => ({accept: e.accept || '', name: e.name || '', id: e.id || '', multiple: e.multiple}));
  if (ziel && erg.groesse_ok) {
    const dt = new DataTransfer(); dt.items.add(datei); ziel.files = dt.files;
    ziel.dispatchEvent(new Event('input', {bubbles: true})); ziel.dispatchEvent(new Event('change', {bubbles: true}));
    erg.eingesetzt = true; erg.feld = {accept: ziel.accept || '', name: ziel.name || '', id: ziel.id || ''};
  } else { erg.eingesetzt = false; erg.grund = ziel ? 'Größe stimmt nicht' : 'kein Dateifeld auf der Seite (Upload-Dialog offen?)'; }
} else { erg.grund = 'Stücke fehlen oder nicht geprüft: erst ms posten js pruefen'; }
JSON.stringify(erg)"""
        return basis + """  const ziel = FELD ? document.querySelector(FELD) : null;
  if (ziel && erg.groesse_ok) {
    const dt = new DataTransfer(); dt.items.add(datei);
    for (const t of ['dragenter', 'dragover', 'drop']) ziel.dispatchEvent(new DragEvent(t, {bubbles: true, cancelable: true, dataTransfer: dt}));
    erg.abgelegt = true;
  } else { erg.abgelegt = false; erg.grund = ziel ? 'Größe stimmt nicht' : 'Ablagefläche nicht gefunden (--feld "<css>")'; }
} else { erg.grund = 'Stücke fehlen oder nicht geprüft: erst ms posten js pruefen'; }
JSON.stringify(erg)"""
    raise SystemExit('FEHLER: ms posten js auffangen|pruefen|einsetzen|ablegen|aufraeumen <folge>')


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


def eigen(fid: str, zitat: str | None) -> dict:
    """Migration (31.10.2026): Folgen aus Motion-Studio vor v4 haben kein quelle-Feld und gelten nicht als eigene, also postet
    das System sie nie. Nach ausdrücklichem Ja des Nutzers (der Inhalt ist seiner) wird quelle auf eigen gesetzt."""
    d, st = _folge(fid)
    if st.get('art') != 'folge':
        raise SystemExit('FEHLER: Pilot, Nachbau, Kopie oder Stil-Test werden nie gepostet und nie als eigene markiert.')
    if st.get('quelle'):
        return {'ok': True, 'quelle': st['quelle'], 'neu': False}
    zitat = ' '.join(str(zitat or '').split())
    if len(zitat) < 2:
        raise SystemExit('FEHLER: --zitat fehlt: das Ja des Nutzers wörtlich, dass der Inhalt seiner ist.')
    _ms.status_setzen(d, None, None, quelle='eigen', quelle_bestaetigt={'zeit': _ms.jetzt(), 'zitat': zitat[:200]})
    _ms.log(f'Folge {V.folge_id(st)} als eigene markiert (ältere Version, Ja des Nutzers)', ziel=_ms.ziel_name(d), art='info')
    return {'ok': True, 'quelle': 'eigen', 'neu': True}


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
    ap.add_argument('was', nargs='?', default='stand', choices=['stand', 'pruefen', 'datei', 'js', 'ergebnis', 'erledigt', 'eigen', 'freigabe'])
    ap.add_argument('ziel', nargs='?', help='Folge-ID, bei freigabe der Kanal')
    ap.add_argument('plattform_pos', nargs='?', metavar='plattform')
    ap.add_argument('--kanal')
    ap.add_argument('--plattform')
    ap.add_argument('--link')
    ap.add_argument('--fehler')
    ap.add_argument('--zitat')
    ap.add_argument('--zurueck', action='store_true')
    ap.add_argument('--feld', help='bei js einsetzen/ablegen: CSS-Selektor des Upload-Felds bzw. der Ablagefläche')
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
    if a.was == 'js':   # ms posten js <schritt> [<folge>]
        print(js(a.ziel or '', a.plattform_pos, a.feld))
        return 0
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
        e = datei(a.ziel)
        z = [f'{e["datei"]} ({e["groesse"] / 1e6:.1f} MB, volle Qualität) in {e["anzahl"]} Stücken unter 10 MB:',
             *[f'  {x["pfad"]}' for x in e['stuecke']],
             f'Weiter mit Skill motion-video-hochladen: ms posten js auffangen, je Stück ein file_upload, '
             f'ms posten js pruefen {e["folge"]}, ms posten js einsetzen {e["folge"]}.']
        return aus({k: v for k, v in e.items()}, '\n'.join(z))
    if a.was == 'ergebnis':
        e = ergebnis(a.ziel, a.plattform or a.plattform_pos or '', a.link, a.fehler)
        return aus(e, ('OK, eingetragen.' + (' Überall gepostet.' if not e['offen'] else f' Offen: {", ".join(e["offen"])}'))
                   if e['ok'] else f'Fehler eingetragen, im Studio rot: {e["fehler"]}')
    if a.was == 'erledigt':
        return aus(erledigt(a.ziel, a.plattform or a.plattform_pos), 'Erledigt.')
    if a.was == 'eigen':
        e = eigen(a.ziel, a.zitat)
        return aus(e, 'Als eigene Folge markiert.' if e['neu'] else f'Hat schon quelle: {e["quelle"]}.')
    if a.was == 'freigabe':
        e = freigabe(a.ziel, a.plattform or a.plattform_pos or '', a.zitat, a.zurueck)
        return aus(e, f'Freigaben für {a.ziel}: {", ".join(e["freigaben"]) or "keine"}')


if __name__ == '__main__':
    sys.exit(main())
