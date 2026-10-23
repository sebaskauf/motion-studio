"""Dashboard STUDIO im Browser: Pipeline, Live-Log, Agenten-Sitzungen und feste Aufträge (nur 127.0.0.1).
  ms dashboard                    startet auf http://127.0.0.1:8777
  ms dashboard --port 8780        anderer Port
  ms dashboard --oeffnen          öffnet zusätzlich den Browser
  ms dashboard --adapter <datei.py>   zeigt eine eigene Pipeline statt des Arbeitsordners (ARCHITEKTUR.md §5)
Einbetten (z. B. iframe): http://127.0.0.1:8777/  optional ?thema=hell|dunkel
Adapter: Python-Modul mit stand() (Schema wie /api/stand, optional aktionen + kennzahlen als Listen), optional TITEL,
datei_wurzeln(), auftrag(art, params), sitzung(name, was), folge_gepostet/folge_geplant/ordner_oeffnen(id, daten).
Fehlt eine Funktion, blendet die Seite den Knopf aus. Ohne --adapter bleibt alles wie im Motion-Studio-Modus.
Sendeplan (Feld `sendeplan` {heute, morgen}): mit Adapter dessen Slots, eingebaut abgeleitet aus `geplant`/`gepostet` der Folgen.
JETZT (Feld `hinweise`): Klartext-Zeilen [{art, tag, text, knopf}], Sitzungs-Hinweise ergänzt die Seite selbst.
  Sonderarten: freigabe {folge, titel, freigabe} (Knöpfe aus freigabe.optionen, Antwort = auftrag „freigabe“ mit folge/id/kommentar),
  ceo {sitzung, sitzung_da, frage} (Antwortfeld schickt an /api/sitzung/<name>/antwort).
Weitere Adapter-Felder (alle optional, die Seite blendet aus, was fehlt): vorrat [{folge_id, titel, geplant, zwilling, guide_ok,
  caption, postbar, grund}] (Knopf = auftrag „posten“ mit folge/trial), posten {folge, laeuft, ok, text}, produktion {an, label, grund …},
  baue [{sitzung, folge, start, lebt}], ceo (Sitzung zum Ansehen), freigabe je Folge {frage, optionen:[{id, label, art gut|schlecht|neutral,
  kommentar, bestaetigen, hinweis}]}. In `aktionen`: versteckt (nicht im Menü), anzeige (Stand statt Knopf), icon.
STUDIO v3 (22.10.2026): crew [{id, name, figur, agent, rolle, text, modell, status {art, text, sitzungen}}] (Pixel-Crew, pixel.js),
  plattform {art instagram|tiktok|youtube, handle, name, bild, profil_link, follower, folgt, beitraege, zeitraum {views, reichweite,
  interaktionen, follower_neu, tage}, reels [{link, vorschau, views, likes, kommentare, folge_id}], stand, hinweis},
  steuerung {autopilot {an, text}, produktion {an, heute, pro_tag, parallel, laufend, fenster, text}, budget {prozent, grenze, text},
  knoepfe [art …]}. Sitzungen tragen frage (Menü: optionen, frei_nr, enter), nachricht und macht {art, text, werkzeug, agent}.
  POST /api/sitzung/<name>/wahl {nr, text} wählt eine Option (Adapter: sitzung(name, 'wahl', {nr, text})),
  GET /api/sitzung/<name>/verlauf liefert das Terminal als Gespräch (Adapter: sitzung(name, 'verlauf')).
Weitere Routen: /fonts/<datei>.woff2 (nur aus dashboard/fonts/), /pixel.js, POST /api/neustart (Token): antwortet, dann ersetzt sich
der Prozess per os.execv mit denselben Argumenten (neues Token, die Seite lädt danach neu).
Sicherheit: bindet nur 127.0.0.1, prüft bei jeder Anfrage den Host-Header (gegen DNS-Rebinding), POST nur mit
Sitzungs-Token (neu bei jedem Start) und passendem Origin, Knöpfe starten nur feste Aufträge (ms starten),
/datei liefert nur Bilder, Videos und .md aus dem Arbeitsordner. Schlüssel aus .env werden nie gelesen."""
from __future__ import annotations

import argparse
import hmac
import html as html_mod
import importlib.util
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent / 'tools'))
import _ms  # noqa: E402
import starten  # noqa: E402

FERTIG = ('fertig', 'geplant', 'gepostet')
SPALTEN = list(dict.fromkeys(_ms.SPALTEN[p] for p in _ms.FOLGE_PHASEN))
MD_DATEIEN = ['SKRIPT.md', 'STORYBOARD.md', 'PRUEFBERICHT.md', 'HANDOFF.md', 'CAPTION.md']
TYPEN = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp', '.gif': 'image/gif',
         '.mp4': 'video/mp4', '.m4v': 'video/mp4', '.mov': 'video/quicktime', '.webm': 'video/webm',
         '.md': 'text/plain; charset=utf-8'}
GEHEIM_RE = re.compile(r'token|secret|passw|schluessel|schlüssel|api_?key', re.I)
LINK_RE = re.compile(r'^https?://[^\s"\'<>`\\]{3,500}$')
FOLGE_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$')
SCHRIFT_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,80}\.woff2$')
SCHRIFTEN = HIER / 'fonts'
MAX_BODY = 10_000
ADAPTER = None   # Modul aus --adapter (eigene Pipeline), sonst eingebauter Motion-Studio-Modus
SITZUNG_WAS = ('weiter', 'oeffnen', 'stopp', 'antwort', 'wahl')
PIXEL_JS = HIER / 'pixel.js'
# Crew im Motion-Studio-Modus: die vier Agenten des Pakets (Pixel-Figuren in der Seite, pixel.js)
CREW_EINGEBAUT = [
    {'id': 'regie', 'name': 'Regie', 'figur': 'regie', 'agent': 'motion-regie', 'rolle': 'führt das Studio',
     'text': 'Plant jede Folge, schreibt Skript und Storyboard, verteilt die Arbeit an das Team und rendert am Ende.'},
    {'id': 'analyse', 'name': 'Analyse', 'figur': 'analyse', 'agent': 'motion-analyse', 'rolle': 'zerlegt Vorbilder',
     'text': 'Zerlegt Vorbild-Videos in Schnitte, Farben, Kamera, Text und Ton und schreibt daraus die Bibel des Kanals.'},
    {'id': 'bauer', 'name': 'Bauer', 'figur': 'bauer', 'agent': 'motion-bauer', 'rolle': 'baut die Szenen',
     'text': 'Baut die Szenen in 2D, als 3D im Browser oder in Blender. Oft laufen mehrere Bauer parallel.'},
    {'id': 'pruefer', 'name': 'Prüfer', 'figur': 'pruefer', 'agent': 'motion-pruefer', 'rolle': 'prüft mit frischen Augen',
     'text': 'Sieht das fertige Video ohne Bau-Kontext an und schreibt einen Prüfbericht mit Zeitstempeln.'},
]
SERVER_ID = secrets.token_hex(4)   # neu bei jedem Start: die Seite erkennt daran einen Neustart (Token veraltet)


# ---------------------------------------------------------------- Daten

def _ohne_geheimes(d):
    """Felder, deren Name nach Schlüssel klingt, nie ausliefern (Schutz, falls ein Agent so etwas in STATUS schreibt)."""
    if isinstance(d, dict):
        return {k: _ohne_geheimes(v) for k, v in d.items() if not GEHEIM_RE.search(str(k))}
    if isinstance(d, list):
        return [_ohne_geheimes(x) for x in d]
    return d


def _relativ(ordner: str, pfad) -> str | None:
    """Pfad aus STATUS (relativ zum Folgen-Ordner oder absolut) -> relativ zu ARBEIT, nur wenn die Datei existiert."""
    if not pfad or not isinstance(pfad, str):
        return None
    basis = _ms.arbeit().resolve()
    p = Path(pfad)
    p = p if p.is_absolute() else basis / ordner / p
    try:
        p = p.resolve()
        rel = p.relative_to(basis)
    except (ValueError, OSError):
        return None
    return rel.as_posix() if p.is_file() else None


def _log_ende(n=50) -> list[dict]:
    p = _ms.arbeit() / 'live' / 'events.jsonl'
    if not p.exists():
        return []
    with open(p, 'rb') as f:
        f.seek(0, 2)
        groesse = f.tell()
        block = min(groesse, 256 * 1024)
        f.seek(groesse - block)
        zeilen = f.read().decode('utf-8', 'replace').splitlines()
    if block < groesse:
        zeilen = zeilen[1:]
    aus = []
    for z in zeilen[-n:]:
        try:
            aus.append(json.loads(z))
        except ValueError:
            pass
    return list(reversed(aus))


def _kosten(eintraege) -> dict:
    monat = datetime.now().strftime('%Y-%m')
    summe, gesamt = {}, {}
    for k in eintraege:
        try:
            betrag = float(k.get('betrag') or 0)
        except (TypeError, ValueError):
            continue
        einheit = str(k.get('einheit') or 'USD')
        gesamt[einheit] = round(gesamt.get(einheit, 0) + betrag, 4)
        if str(k.get('zeit', ''))[:7] == monat:
            summe[einheit] = round(summe.get(einheit, 0) + betrag, 4)
    return {'monat': summe, 'gesamt': gesamt}


def _zuletzt_kanal(folgen, kanaele) -> str | None:
    vorhanden = {k.get('id') or k['_ordner'].split('/', 1)[1] for k in kanaele}
    for f in sorted(folgen, key=lambda s: s.get('aktualisiert') or '', reverse=True):
        if f.get('kanal') in vorhanden:
            return f['kanal']
    for k in sorted(kanaele, key=lambda s: (s.get('phase') == 'bereit', s.get('aktualisiert') or ''), reverse=True):
        return k.get('id') or k['_ordner'].split('/', 1)[1]
    return None


def _vorschlag(folgen, kanaele, sitzungen, profil_da, zuletzt) -> dict:
    """Was „Einfach weitermachen“ tut: das Naheliegende, ohne einen zweiten Agenten auf dieselbe Arbeit zu setzen."""
    lebend = [s for s in sitzungen if not s['tot']]
    for zustand in ('fehler',):
        s = next((x for x in lebend if x['zustand'] == zustand), None)
        if s:
            return {'typ': 'sitzung_weiter', 'sitzung': s['name'], 'text': 'Hängenden Agenten mit „weiter“ anstoßen'}
    s = next((x for x in lebend if x['zustand'] == 'wartet'), None)
    if s:
        return {'typ': 'ansehen', 'sitzung': s['name'], 'text': 'Der Agent wartet auf deine Antwort im Terminal'}
    s = next((x for x in lebend if x['zustand'] == 'arbeitet'), None)
    if s:
        return {'typ': 'ansehen', 'sitzung': s['name'], 'text': 'Der Agent arbeitet gerade, zuschauen'}
    if not profil_da:
        return {'typ': 'auftrag', 'art': 'einrichten', 'text': 'Motion-Studio einrichten'}
    offen_f = [f for f in folgen if f.get('phase') not in FERTIG]
    offen_k = [k for k in kanaele if k.get('phase') and k.get('phase') != 'bereit']
    if len(offen_f) == 1 and not offen_k:
        f = offen_f[0]
        return {'typ': 'auftrag', 'art': 'weiter', 'folge': f.get('id') or f['_ordner'].split('/', 1)[1],
                'text': f'Bei „{f.get("titel") or f.get("id")}“ weitermachen'}
    if offen_f or offen_k:
        return {'typ': 'auftrag', 'art': 'weiter', 'text': 'Bei der offenen Arbeit weitermachen'}
    if zuletzt:
        k = next((x for x in kanaele if (x.get('id') or x['_ordner'].split('/', 1)[1]) == zuletzt), {})
        return {'typ': 'auftrag', 'art': 'folge', 'kanal': zuletzt,
                'text': f'Nächste Folge für {k.get("titel") or zuletzt}'}
    return {'typ': 'dialog', 'art': 'kanal-lernen', 'text': 'Ersten Kanal lernen'}


def _alle_status_sicher() -> list[dict]:
    """Wie _ms.alle_status(), aber eine kaputte STATUS.json legt nicht das ganze Dashboard lahm."""
    aus = []
    for teil in ('kanaele', 'folgen'):
        basis = _ms.arbeit() / teil
        if not basis.is_dir():
            continue
        for d in sorted(basis.iterdir(), reverse=True):
            if not (d / 'STATUS.json').is_file():
                continue
            try:
                st = _ms.status_lesen(d)
            except (ValueError, OSError) as e:
                st = {'id': d.name, 'art': 'kanal' if teil == 'kanaele' else 'folge', 'titel': d.name,
                      'fehler': f'STATUS.json nicht lesbar ({type(e).__name__}). Agent fragen: „Repariere STATUS.json von {d.name}“.'}
            if isinstance(st, dict) and st:
                st['_ordner'] = f'{teil}/{d.name}'
                aus.append(st)
    return aus


def _zeit_lokal(iso) -> datetime | None:
    """ISO-Zeit (mit oder ohne Zone) -> Ortszeit mit Zone."""
    try:
        t = datetime.fromisoformat(str(iso).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return t.astimezone() if t.tzinfo else t.astimezone()


def _sendeplan_eingebaut(folgen) -> dict:
    """Ohne Autopilot gibt es keine festen Sendezeiten: der Plan zeigt, was heute und morgen geplant oder gepostet ist.
    Geplant und Zeit vorbei, aber nicht als gepostet markiert: zustand vorbei (Motion-Studio postet nicht selbst)."""
    jetzt = datetime.now().astimezone()
    tage = {'heute': jetzt.date(), 'morgen': jetzt.date() + timedelta(days=1)}
    aus = {name: [] for name in tage}
    for f in folgen:
        fid = f.get('id') or f['_ordner'].split('/', 1)[1]
        g = f.get('gepostet') if isinstance(f.get('gepostet'), dict) else {}
        if f.get('phase') == 'gepostet' and g.get('zeit'):
            t, zustand, grund = _zeit_lokal(g['zeit']), 'gepostet', ''
        elif f.get('geplant'):
            t = _zeit_lokal(f['geplant'])
            zustand, grund = ('geplant', '') if t and t > jetzt else ('vorbei', 'noch nicht als gepostet markiert')
        else:
            continue
        if not t:
            continue
        link = str(g.get('link') or '')
        for name, tag in tage.items():
            if t.date() == tag:
                aus[name].append({'slot': None, 'zeit': t.isoformat(timespec='minutes'), 'art': 'post', 'zustand': zustand,
                                  'folge_id': fid, 'titel': f.get('titel') or fid, '_vorschau': f.get('_vorschau'),
                                  'link': link if LINK_RE.match(link) else '', 'trial': bool(f.get('trial')), 'grund': grund})
    for liste in aus.values():
        liste.sort(key=lambda e: e['zeit'])
    aus['sendezeiten'] = []
    return aus


def _hinweise_eingebaut(folgen, kanaele, profil_da) -> list[dict]:
    """JETZT-Zeilen im Motion-Studio-Modus: Einrichtung, Fehler, offene Fragen. Hängende Agenten ergänzt die Seite."""
    h = []
    if not profil_da:
        h.append({'art': 'info', 'tag': 'EINRICHTEN', 'text': 'Motion-Studio ist noch nicht eingerichtet. Der Agent prüft die '
                  'Programme und fragt nach deinem Profil.', 'knopf': {'label': 'Einrichten', 'aktion': 'dialog', 'art': 'einrichten'}})
    for x in folgen + kanaele:
        kanal = x.get('art') == 'kanal'
        xid = x.get('id') or x['_ordner'].split('/', 1)[1]
        name = f'Kanal „{x.get("titel") or xid}“' if kanal else f'„{x.get("titel") or xid}“'
        knopf = {'label': 'Weitermachen', 'aktion': 'los'} if kanal else {'label': 'Ansehen', 'aktion': 'detail', 'folge': xid}
        if x.get('fehler'):
            h.append({'art': 'fehler', 'tag': 'FEHLER', 'text': f'{name}: {x["fehler"]}', 'knopf': knopf, 'folge': None if kanal else xid})
        if x.get('wartet_auf'):
            h.append({'art': 'wartet', 'tag': 'WARTET', 'text': f'{name} fragt: {x["wartet_auf"]}', 'knopf': knopf,
                      'folge': None if kanal else xid})
    return h


def stand() -> dict:
    if ADAPTER is not None:
        return _adapter_stand()
    arbeit = _ms.arbeit()
    alle = [_ohne_geheimes(s) for s in _alle_status_sicher()]
    kanaele = [s for s in alle if s.get('art') == 'kanal']
    folgen = [s for s in alle if s.get('art') != 'kanal']
    for f in folgen:
        f['_spalte'] = _ms.SPALTEN.get(f.get('phase') or 'vorlage', 'Vorlage')
        f['_video'] = _relativ(f['_ordner'], f.get('video'))
        f['_vorschau'] = _relativ(f['_ordner'], f.get('vorschau'))
        f['_dateien'] = [n for n in MD_DATEIEN if (arbeit / f['_ordner'] / n).is_file()]
        f['_kosten'] = _kosten(f.get('kosten') or [])
    for k in kanaele:
        k['_kosten'] = _kosten(k.get('kosten') or [])
    try:
        sitzungen = starten.liste()
    except (SystemExit, OSError) as e:
        sitzungen = []
        print(f'Hinweis: Sitzungen nicht lesbar: {e}', file=sys.stderr)
    alle_kosten = [k for s in alle for k in (s.get('kosten') or []) if isinstance(k, dict)]
    _kanal_eta(kanaele, sitzungen)
    profil_da = (arbeit / 'PROFIL.md').is_file()
    zuletzt = _zuletzt_kanal(folgen, kanaele)
    phasen = [f.get('phase') for f in folgen]
    return {
        'jetzt': _ms.jetzt(), 'arbeit_da': arbeit.is_dir(), 'system': _ms.SYSTEM, 'tmux': bool(starten._tmux()),
        'spalten': SPALTEN, 'phase_spalte': _ms.SPALTEN, 'folge_phasen': _ms.FOLGE_PHASEN,
        'kanal_phasen': _ms.KANAL_PHASEN, 'auftraege': starten.AUFTRAEGE,
        'folgen': folgen, 'kanaele': kanaele, 'log': _log_ende(50), 'sitzungen': sitzungen,
        'kosten': _kosten(alle_kosten),
        'kennzahlen': {'gepostet': phasen.count('gepostet'), 'geplant': phasen.count('geplant'),
                       'fertig': phasen.count('fertig'), 'in_arbeit': sum(1 for p in phasen if p not in FERTIG)},
        'profil': {'vorhanden': profil_da, 'zuletzt_kanal': zuletzt,
                   'kanaele': [{'slug': k.get('id') or k['_ordner'].split('/', 1)[1], 'titel': k.get('titel'),
                                'phase': k.get('phase')} for k in kanaele]},
        'vorschlag': _vorschlag(folgen, kanaele, sitzungen, profil_da, zuletzt),
        'adapter': False, 'titel': 'Motion-Studio', 'faehig': {'gepostet': True, 'geplant': True, 'ordner': True},
        'sendeplan': _sendeplan_eingebaut(folgen), 'hinweise': _hinweise_eingebaut(folgen, kanaele, profil_da),
        'crew': starten.crew_status(CREW_EINGEBAUT, sitzungen, folgen) + [_autopilot_figur()],
        'version': _ms.config().get('version'),
        **_steuerung_eingebaut(kanaele, zuletzt),
    }


AUTOPILOT_ARTEN = ('produktion-an', 'produktion-aus', 'bauen', 'anstossen')


def _ap():
    import autopilot  # noqa: E402  (studio/tools, liegt im Pfad)
    return autopilot


def _autopilot_figur() -> dict:
    s = _ap().stand()
    c = s['konfig']
    if not c['an']:
        st = {'art': 'schlaeft', 'text': 'Tagesbau ist aus', 'an': False, 'sitzungen': []}
    elif s['laufend']:
        st = {'art': 'arbeitet', 'text': f'{s["laufend"]} Bau{"ten" if s["laufend"] != 1 else ""} läuft', 'an': True,
              'sitzungen': [b['sitzung'] for b in s['baue'] if b.get('sitzung')]}
    else:
        st = {'art': 'wartet', 'text': s['grund'] or 'startet beim nächsten Durchlauf einen Bau', 'an': True, 'sitzungen': []}
    return {'id': 'autopilot', 'name': 'Autopilot', 'figur': 'autopilot', 'rolle': 'startet den Tagesbau', 'modell': 'alle 15 min',
            'text': 'Startet jeden Tag im Bau-Fenster neue Folgen für deinen Kanal, höchstens zwei gleichzeitig, token-sparsam mit Sonnet '
                    'und ohne Auto-Gedächtnis. Erreicht Claude das Nutzungslimit, macht er Pause. Gepostet wird nichts.', 'status': st}


def _steuerung_eingebaut(kanaele: list[dict], zuletzt: str | None) -> dict:
    """Panel STEUERUNG im Motion-Studio-Modus: Tagesbau (ms autopilot) als Schalter, sofort bauen, Durchlauf anstoßen."""
    ap = _ap()
    s = ap.stand()
    c = s['konfig']
    kanal = _ap_kanal(c, kanaele, zuletzt)
    modell = {'claude-sonnet-5-5': 'Sonnet 5.5', 'claude-opus-5-5': 'Opus 5.5', 'claude-fable-5-1': 'Fable 5.1'}.get(c['modell'], c['modell'])
    text = (f'{s["heute"]} von {c["pro_tag"]} Bauten heute · {c["parallel"]} gleichzeitig · {c["fenster"][0]} bis {c["fenster"][1]} Uhr · '
            f'{modell}{f" · Kanal {kanal}" if kanal else ""}. ')
    text += (s['grund'] if c['an'] and s['grund'] else 'Der nächste Durchlauf startet einen Bau.' if c['an'] else
             'Aus. Eingeschaltet baut Motion-Studio jeden Tag selbst neue Folgen.' if kanal else 'Erst einen Kanal fertig lernen, dann geht der Tagesbau.')
    if c['an'] and not s['zeitplan']:
        text += ' Der Zeitplan fehlt: einmal aus- und wieder einschalten.'
    aktionen = []
    if c['an']:
        aktionen.append({'art': 'produktion-aus', 'label': 'Tagesbau stoppen', 'versteckt': True,
                         'bestaetigen': 'Tagesbau stoppen? Es starten keine neuen Bauten mehr, laufende laufen zu Ende.'})
    elif kanal:
        aktionen.append({'art': 'produktion-an', 'label': 'Tagesbau starten', 'versteckt': True,
                         'bestaetigen': f'Tagesbau starten? Motion-Studio baut dann jeden Tag bis zu {c["pro_tag"]} Folgen für Kanal {kanal}, '
                                        f'höchstens {c["parallel"]} gleichzeitig, zwischen {c["fenster"][0]} und {c["fenster"][1]} Uhr, mit {modell} '
                                        'und ohne Rückfragen. Bezahlte Schritte nur bis „Ohne Nachfrage frei bis“ aus deinem Profil, darüber wartet der Bau auf dich. Ein Zeitplan '
                                        '(alle 15 min) wird angelegt. Gepostet wird nichts.'})
    knoepfe = []
    if kanal:
        aktionen.append({'art': 'bauen', 'label': '1 Folge jetzt bauen', 'versteckt': True,
                         'bestaetigen': f'Jetzt eine Folge für Kanal {kanal} bauen? Der Agent startet sofort ({modell}), zählt nicht zum Tagesziel.'})
        knoepfe.append({'art': 'bauen', 'label': '1 Folge jetzt bauen', 'primaer': True, 'icon': 'plus'})
    if c['an']:
        aktionen.append({'art': 'anstossen', 'label': 'Durchlauf jetzt', 'versteckt': True})
        knoepfe.append({'art': 'anstossen', 'label': 'Produktion jetzt anstoßen', 'icon': 'neu',
                        'hinweis': 'führt den Autopilot sofort aus statt in bis zu 15 min'})
    return {'steuerung': {'produktion': {'an': bool(c['an']), 'heute': s['heute'], 'pro_tag': c['pro_tag'], 'parallel': c['parallel'],
                                         'laufend': s['laufend'], 'fenster': c['fenster'], 'text': text},
                          'knoepfe': knoepfe, 'zahl': modell}, 'aktionen': aktionen}


def _ap_kanal(c: dict, kanaele: list[dict] | None = None, zuletzt: str | None = None) -> str:
    """Kanal für den Tagesbau: der eingestellte, sonst der zuletzt benutzte oder erste fertig gelernte."""
    if kanaele is None:
        kanaele = [s for s in _alle_status_sicher() if s.get('art') == 'kanal']
    bereit = [k.get('id') or k['_ordner'].split('/', 1)[1] for k in kanaele if k.get('phase') == 'bereit']
    return c['kanal'] if c['kanal'] in bereit else (zuletzt if zuletzt in bereit else (bereit[0] if bereit else ''))


def _autopilot_auftrag(art: str) -> dict:
    ap = _ap()
    c = ap.konfig()
    kanal = _ap_kanal(c)
    if art == 'produktion-aus':
        c['an'] = False
        ap.konfig_schreiben(c)
        ap.merke('Tagesbau aus (Dashboard)', 'warnung')
        return {'meldung': 'Tagesbau ist aus. Laufende Bauten laufen zu Ende.'}
    if not kanal:
        raise SystemExit('FEHLER: Erst einen Kanal fertig lernen.')
    if art == 'bauen':
        with ap.sperre():
            z = ap.zustand()
            c['kanal'] = kanal
            erg = ap.bau_starten(c, z, extra=True)
            ap.zustand_schreiben(z)
        sitz = erg.get('sitzung')
        return {'meldung': f'Bau gestartet{f" ({sitz})" if sitz else ""}. Rechts bei „Agenten“ zuschauen.'}
    if art == 'produktion-an':
        c.update(an=True, kanal=kanal)
        ap.konfig_schreiben(c)
        hinweis = '' if ap.zeitplan_da() else ' ' + ap.einrichten()
        ap.merke(f'Tagesbau an (Dashboard): Kanal {kanal}, {c["pro_tag"]} pro Tag')
    erg = ap.lauf()
    return {'meldung': ('Tagesbau ist an.' if art == 'produktion-an' else 'Durchlauf fertig.')
            + (' Der erste Bau läuft.' if erg['gestartet'] else f' Gerade startet nichts: {erg["grund"]}')
            + (hinweis if art == 'produktion-an' else '')}


# Kanal lernen: Richtwerte je Schritt in Minuten (gemessen 23.10.: Hook-Nachbau 0 bis 18 s in rund 80 min)
KANAL_MINUTEN = {'vorbild': 15, 'zerlegt': 40, 'bibel': 10, 'pilot': 100, 'gemessen': 15, 'kit': 30, 'bereit': 0}


def _kanal_eta(kanaele: list[dict], sitzungen: list[dict]) -> None:
    """Fertig-Zeit für Kanäle, die gerade lernen (Sebastian 23.10.: „im Studio steht, wann es fertig wird“). Nur wenn eine
    Lern-Sitzung läuft, sonst pausiert. Grob: Summe der Richtwerte der offenen Schritte ab jetzt."""
    lernt = any(not s.get('tot') and s.get('art') in ('kanal-lernen', 'weiter') for s in sitzungen or [])
    phasen = list(_ms.KANAL_PHASEN)
    for k in kanaele:
        if k.get('phase') == 'bereit':
            continue
        i = phasen.index(k['phase']) if k.get('phase') in phasen else -1
        rest = sum(KANAL_MINUTEN.get(p, 0) for p in phasen[i + 1:])
        k['_laeuft'] = lernt
        k['_eta'] = (datetime.now() + timedelta(minutes=rest)).astimezone().isoformat(timespec='minutes') if lernt and rest else None


# ---------------------------------------------------------------- Adapter (eigene Pipeline)

def adapter_laden(pfad: str):
    """Lädt die Adapter-Datei als Modul. Sie läuft im Server-Prozess (vertrauenswürdiger Code des Nutzers)."""
    p = Path(pfad).expanduser().resolve()
    if not p.is_file() or p.suffix != '.py':
        raise SystemExit(f'FEHLER: Adapter {p} gibt es nicht (erwartet eine .py-Datei).')
    spec = importlib.util.spec_from_file_location('ms_adapter', p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['ms_adapter'] = mod
    vorher, sys.dont_write_bytecode = sys.dont_write_bytecode, True   # kein __pycache__ im Repo des Adapters anlegen
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = vorher
    if not callable(getattr(mod, 'stand', None)):
        raise SystemExit(f'FEHLER: Adapter {p.name} braucht eine Funktion stand().')
    return mod


def _titel() -> str:
    return str(getattr(ADAPTER, 'TITEL', '') or 'Motion-Studio') if ADAPTER is not None else 'Motion-Studio'


def _faehig(name: str) -> bool:
    return ADAPTER is not None and callable(getattr(ADAPTER, name, None))


def _wurzeln() -> list[Path]:
    """Erlaubte Wurzeln für /datei: eingebaut der Arbeitsordner, mit Adapter dessen datei_wurzeln()."""
    if ADAPTER is None:
        return [_ms.arbeit().resolve()]
    f = getattr(ADAPTER, 'datei_wurzeln', None)
    aus = []
    for w in (f() if callable(f) else []):
        try:
            aus.append(Path(w).expanduser().resolve())
        except (OSError, TypeError):
            pass
    return aus


def _token(pfad, wurzeln: list[Path], ordner=False) -> str | None:
    """Absoluter Pfad aus dem Adapter -> "<n>/<relativ>" (n = Index der Wurzel), nur wenn er existiert und darin liegt."""
    if not pfad or not isinstance(pfad, (str, Path)):
        return None
    try:
        p = Path(pfad).expanduser().resolve()
        if not (p.is_dir() if ordner else p.is_file()):
            return None
    except (OSError, ValueError):
        return None
    for i, w in enumerate(wurzeln):
        try:
            rel = p.relative_to(w)
        except ValueError:
            continue
        return f'{i}/{rel.as_posix()}' if rel.parts else str(i)
    return None


def _adapter_stand() -> dict:
    """stand() des Adapters auf das Schema der Seite bringen. Pfade (ordner, video, vorschau) rechnet nur der Server
    in /datei-Pfade um, damit die Seite nie etwas außerhalb der erlaubten Wurzeln anfragen kann."""
    d = ADAPTER.stand()
    if not isinstance(d, dict):
        raise SystemExit('FEHLER: Adapter: stand() liefert kein dict.')
    d = _ohne_geheimes(d)
    wurzeln = _wurzeln()
    folgen = [f for f in (d.get('folgen') or []) if isinstance(f, dict)]
    for f in folgen:
        f.setdefault('art', 'folge')
        f['_spalte'] = f.get('_spalte') or _ms.SPALTEN.get(f.get('phase') or 'vorlage', 'Vorlage')
        ordner = f.pop('ordner', None)
        f['_ordner'] = _token(ordner, wurzeln, ordner=True) or ''
        f['_video'] = _token(f.pop('video', None), wurzeln)
        f['_vorschau'] = _token(f.pop('vorschau', None), wurzeln)
        namen = f.pop('dateien', None) or MD_DATEIEN
        f['_dateien'] = [n for n in namen if f['_ordner'] and isinstance(n, str) and n.endswith('.md') and '/' not in n
                         and '\\' not in n and not n.startswith('.') and (Path(ordner) / n).is_file()]
        f['_kosten'] = _kosten(f.get('kosten') or [])
    kanaele = [k for k in (d.get('kanaele') or []) if isinstance(k, dict)]
    plan = d.get('sendeplan') if isinstance(d.get('sendeplan'), dict) else {}
    for tag in ('heute', 'morgen'):   # Vorschaubilder der Slots wie bei den Folgen nur als /datei-Pfad
        slots = [e for e in (plan.get(tag) or []) if isinstance(e, dict)]
        for e in slots:
            e['_vorschau'] = _token(e.pop('vorschau', None), wurzeln)
            if not LINK_RE.match(str(e.get('link') or '')):
                e['link'] = ''
        plan[tag] = slots
    if plan:
        d['sendeplan'] = plan
    pf = d.get('plattform')
    if isinstance(pf, dict):   # Profilbild und Reel-Vorschauen nur als /datei-Pfad, Links nur http(s)
        pf['_bild'] = _token(pf.pop('bild', None), wurzeln)
        for r in [r for r in (pf.get('reels') or []) if isinstance(r, dict)]:
            r['_vorschau'] = _token(r.pop('vorschau', None), wurzeln)
            if not LINK_RE.match(str(r.get('link') or '')):
                r['link'] = ''
        if not LINK_RE.match(str(pf.get('profil_link') or '')):
            pf['profil_link'] = ''
    if not isinstance(d.get('hinweise'), list):
        d['hinweise'] = []
    else:
        d['hinweise'] = [h for h in d['hinweise'] if isinstance(h, dict) and h.get('text')]
    alle_kosten = [k for s in folgen + kanaele for k in (s.get('kosten') or []) if isinstance(k, dict)]
    aus = {'jetzt': _ms.jetzt(), 'arbeit_da': True, 'system': _ms.SYSTEM, 'tmux': bool(starten._tmux()),
           'spalten': SPALTEN, 'phase_spalte': _ms.SPALTEN, 'folge_phasen': _ms.FOLGE_PHASEN,
           'kanal_phasen': _ms.KANAL_PHASEN, 'auftraege': [], 'log': [], 'sitzungen': [],
           'kosten': _kosten(alle_kosten), 'profil': {'vorhanden': True, 'zuletzt_kanal': None, 'kanaele': []},
           'vorschlag': None}
    aus.update({k: v for k, v in d.items() if v is not None})
    aus.update({'folgen': folgen, 'kanaele': kanaele, 'adapter': True, 'titel': _titel(),
                'aktionen': [a for a in (d.get('aktionen') or []) if isinstance(a, dict) and a.get('art') and a.get('label')]
                if isinstance(d.get('aktionen'), list) else [],
                'faehig': {'gepostet': _faehig('folge_gepostet'), 'geplant': _faehig('folge_geplant'),
                           'ordner': _faehig('ordner_oeffnen')}})
    if not callable(getattr(ADAPTER, 'sitzung', None)):
        for s in aus.get('sitzungen') or []:
            if isinstance(s, dict):
                s['nur_ansehen'] = True
    return aus


def _adapter_arten() -> set:
    """Erlaubte Auftrags-Arten = die Knöpfe aus `aktionen` (Funktion aktionen() oder Liste, sonst aus stand())."""
    a = getattr(ADAPTER, 'aktionen', None)
    liste = a() if callable(a) else a if isinstance(a, list) else (ADAPTER.stand() or {}).get('aktionen') or []
    return {str(x.get('art')) for x in liste if isinstance(x, dict) and x.get('art')}


# ---------------------------------------------------------------- Aktionen

def _folge_ordner(fid: str) -> Path:
    if not FOLGE_RE.match(fid or '') or '..' in fid:
        raise SystemExit('FEHLER: Ungültige Folge.')
    basis = (_ms.arbeit() / 'folgen').resolve()
    d = (basis / fid).resolve()
    if d.parent != basis or not (d / 'STATUS.json').is_file():
        raise SystemExit(f'FEHLER: Folge {fid} gibt es nicht.')
    return d


def _plattform(link: str) -> str:
    host = urlparse(link).hostname or ''
    for name, teil in (('instagram', 'instagram.'), ('tiktok', 'tiktok.'), ('youtube', 'youtu'), ('x', 'x.com'),
                       ('x', 'twitter.'), ('linkedin', 'linkedin.'), ('facebook', 'facebook.')):
        if teil in host:
            return name
    return 'web'


def folge_gepostet(fid: str, daten: dict) -> dict:
    d = _folge_ordner(fid)
    link = str(daten.get('link') or '').strip()
    if not LINK_RE.match(link):
        raise SystemExit('FEHLER: Bitte den Link zum Beitrag einfügen (beginnt mit https://).')
    st = _ms.status_setzen(d, 'gepostet', 'Als gepostet markiert (Dashboard)',
                           gepostet={'zeit': _ms.jetzt(), 'link': link, 'plattform': _plattform(link)})
    return {'phase': st.get('phase')}


def folge_geplant(fid: str, daten: dict) -> dict:
    d = _folge_ordner(fid)
    roh = str(daten.get('zeit') or '').strip()
    try:
        t = datetime.fromisoformat(roh)
    except ValueError:
        raise SystemExit('FEHLER: Zeit fehlt oder ist ungültig.')
    if not 2020 <= t.year <= 2100:
        raise SystemExit('FEHLER: Zeit ist ungültig.')
    if t.tzinfo is None:
        t = t.astimezone()
    st = _ms.status_setzen(d, 'geplant', f'Geplant für {t:%d.%m.%Y %H:%M}', geplant=t.isoformat(timespec='minutes'))
    return {'phase': st.get('phase'), 'geplant': st.get('geplant')}


def ordner_oeffnen(fid: str, daten: dict) -> dict:
    d = _folge_ordner(fid)
    welcher = str(daten.get('welcher') or 'upload')
    if welcher not in ('upload', 'out', 'folge'):
        raise SystemExit('FEHLER: Unbekannter Ordner.')
    ziel = d / welcher if welcher != 'folge' else d
    if not ziel.is_dir():
        ziel = d / 'out' if (d / 'out').is_dir() else d
    rel = _ms.ziel_name(ziel)
    if os.environ.get('MS_KEINE_FENSTER') == '1':
        return {'pfad': rel, 'geoeffnet': False}
    if _ms.SYSTEM == 'Darwin':
        subprocess.Popen(['open', str(ziel)])
    elif _ms.SYSTEM == 'Windows':
        os.startfile(str(ziel))  # type: ignore[attr-defined]
    else:
        subprocess.Popen(['xdg-open', str(ziel)])
    return {'pfad': rel, 'geoeffnet': True}


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = 'MotionStudio'
    sys_version = ''
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):  # still: kein Zugriffs-Log im Terminal
        pass

    # --- Prüfungen
    def _host_ok(self) -> bool:
        host = (self.headers.get('Host') or '').strip().lower()
        m = re.match(r'^(127\.0\.0\.1|localhost)(?::(\d{1,5}))?$', host)
        return bool(m) and (m.group(2) is None or int(m.group(2)) == self.server.server_port)

    def _origin_ok(self) -> bool:
        origin = self.headers.get('Origin')
        if origin is None:
            return True
        port = self.server.server_port
        return origin in (f'http://127.0.0.1:{port}', f'http://localhost:{port}')

    def _token_ok(self) -> bool:
        return hmac.compare_digest(self.headers.get('X-MS-Token') or '', self.server.token)

    # --- Antworten
    def _kopf(self, code, typ, laenge, extra=None):
        self.send_response(code)
        self.send_header('Content-Type', typ)
        self.send_header('Content-Length', str(laenge))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()

    def _json(self, code, daten):
        roh = json.dumps(daten, ensure_ascii=False).encode('utf-8')
        self._kopf(code, 'application/json; charset=utf-8', len(roh),
                   {'Cache-Control': 'no-store', 'Cross-Origin-Resource-Policy': 'same-origin'})
        self.wfile.write(roh)

    def _fehler(self, code, text):
        self._json(code, {'ok': False, 'fehler': text})

    # --- GET
    def do_GET(self):
        if not self._host_ok():
            return self._fehler(403, 'Host nicht erlaubt')
        url = urlparse(self.path)
        try:
            if url.path in ('/', '/index.html'):
                return self._seite()
            if url.path == '/api/stand':
                return self._json(200, {**stand(), 'server_id': SERVER_ID})
            if url.path == '/datei':
                return self._datei(parse_qs(url.query).get('pfad', [''])[0])
            if url.path.startswith('/fonts/'):
                return self._schrift(url.path[len('/fonts/'):])
            if url.path == '/pixel.js':
                roh = PIXEL_JS.read_bytes()
                self._kopf(200, 'text/javascript; charset=utf-8', len(roh), {'Cache-Control': 'no-store'})
                self.wfile.write(roh)
                return None
            teile = [t for t in url.path.split('/') if t]
            if len(teile) == 4 and teile[:2] == ['api', 'sitzung'] and teile[3] == 'verlauf':
                return self._json(200, {'ok': True, **self._verlauf(teile[2])})
            return self._fehler(404, 'Gibt es nicht')
        except (BrokenPipeError, ConnectionResetError):
            pass
        except SystemExit as e:
            return self._fehler(400, str(e).replace('FEHLER: ', ''))
        except Exception as e:  # z. B. kaputte STATUS.json: Seite soll weiterlaufen
            return self._fehler(500, f'Interner Fehler: {type(e).__name__}: {e}')

    def _verlauf(self, name: str) -> dict:
        """Terminal als Gespräch (nur lesen). Mit Adapter nur, wenn er sitzung(name, 'verlauf') kann."""
        if ADAPTER is not None:
            if not _faehig('sitzung'):
                raise SystemExit('FEHLER: Dieser Adapter zeigt keinen Verlauf.')
            return ADAPTER.sitzung(name, 'verlauf') or {}
        return starten.verlauf(name)

    def _seite(self):
        html = (HIER / 'index.html').read_text(encoding='utf-8').replace('__MS_TOKEN__', self.server.token) \
            .replace('__MS_TITEL__', html_mod.escape(_titel()))
        roh = html.encode('utf-8')
        csp = ("default-src 'self'; img-src 'self' data:; media-src 'self'; style-src 'self' 'unsafe-inline'; "
               "script-src 'self' 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'")
        self._kopf(200, 'text/html; charset=utf-8', len(roh),
                   {'Cache-Control': 'no-store', 'Content-Security-Policy': csp})
        self.wfile.write(roh)

    def _schrift(self, name: str):
        """Nur .woff2 direkt aus dashboard/fonts/ (kein Unterordner, kein Pfad-Ausbruch)."""
        if not SCHRIFT_RE.match(name or '') or '..' in name:
            return self._fehler(404, 'Gibt es nicht')
        basis = SCHRIFTEN.resolve()
        try:
            ziel = (basis / name).resolve()
        except OSError:
            return self._fehler(404, 'Gibt es nicht')
        if ziel.parent != basis or not ziel.is_file():
            return self._fehler(404, 'Gibt es nicht')
        roh = ziel.read_bytes()
        self._kopf(200, 'font/woff2', len(roh), {'Cache-Control': 'public, max-age=604800, immutable',
                                                 'Cross-Origin-Resource-Policy': 'same-origin'})
        self.wfile.write(roh)

    def _datei(self, rel: str):
        if not rel or '\x00' in rel or rel.startswith(('/', '\\')) or re.match(r'^[A-Za-z]:', rel):
            return self._fehler(403, 'Pfad nicht erlaubt')
        teile = Path(rel.replace('\\', '/')).parts
        if any(t.startswith('.') for t in teile):
            return self._fehler(403, 'Pfad nicht erlaubt')
        if ADAPTER is None:
            basis = _ms.arbeit().resolve()
        else:  # "<n>/<pfad>": n = Index in datei_wurzeln() des Adapters
            wurzeln = _wurzeln()
            if len(teile) < 2 or not teile[0].isdigit() or int(teile[0]) >= len(wurzeln):
                return self._fehler(403, 'Pfad nicht erlaubt')
            basis, rel = wurzeln[int(teile[0])], '/'.join(teile[1:])
        try:
            ziel = (basis / rel).resolve()
            ziel.relative_to(basis)
        except (ValueError, OSError):
            return self._fehler(403, 'Pfad nicht erlaubt')
        typ = TYPEN.get(ziel.suffix.lower())
        if not typ:
            return self._fehler(403, 'Dateityp nicht erlaubt')
        if not ziel.is_file():
            return self._fehler(404, 'Datei fehlt')
        groesse = ziel.stat().st_size
        start, ende, code = 0, groesse - 1, 200
        bereich = self.headers.get('Range')
        extra = {'Accept-Ranges': 'bytes', 'Cache-Control': 'no-cache', 'Cross-Origin-Resource-Policy': 'same-origin'}
        if bereich:
            m = re.match(r'^bytes=(\d*)-(\d*)$', bereich.strip())
            if not m or (not m.group(1) and not m.group(2)):
                self._kopf(416, 'text/plain', 0, {'Content-Range': f'bytes */{groesse}'})
                return
            if m.group(1):
                start = int(m.group(1))
                ende = min(int(m.group(2)), groesse - 1) if m.group(2) else groesse - 1
            else:
                start = max(0, groesse - int(m.group(2)))
            if start >= groesse or start > ende:
                self._kopf(416, 'text/plain', 0, {'Content-Range': f'bytes */{groesse}'})
                return
            code = 206
            extra['Content-Range'] = f'bytes {start}-{ende}/{groesse}'
        laenge = ende - start + 1 if groesse else 0
        self._kopf(code, typ, laenge, extra)
        with open(ziel, 'rb') as f:
            f.seek(start)
            rest = laenge
            while rest > 0:
                stueck = f.read(min(256 * 1024, rest))
                if not stueck:
                    break
                self.wfile.write(stueck)
                rest -= len(stueck)

    # --- POST
    def do_POST(self):
        if not self._host_ok():
            return self._fehler(403, 'Host nicht erlaubt')
        if not self._origin_ok() or not self._token_ok():
            return self._fehler(403, 'Nicht erlaubt (Seite neu laden)')
        try:
            laenge = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            return self._fehler(400, 'Ungültige Anfrage')
        if laenge > MAX_BODY:
            return self._fehler(413, 'Zu groß')
        try:
            daten = json.loads(self.rfile.read(laenge).decode('utf-8') or '{}') if laenge else {}
        except ValueError:
            return self._fehler(400, 'Ungültiges JSON')
        if not isinstance(daten, dict):
            return self._fehler(400, 'Ungültiges JSON')
        teile = [t for t in urlparse(self.path).path.split('/') if t]
        try:
            if teile == ['api', 'neustart']:
                return self._neustart()
            if ADAPTER is not None:
                return self._adapter_post(teile, daten)
            if teile == ['api', 'auftrag'] and str(daten.get('art') or '') in AUTOPILOT_ARTEN:
                return self._json(200, {'ok': True, **_autopilot_auftrag(str(daten['art']))})
            if teile == ['api', 'auftrag']:
                art = str(daten.get('art') or '')
                if art not in starten.AUFTRAEGE:
                    return self._fehler(400, 'Unbekannter Auftrag')
                erg = starten.starten(art, kanal=daten.get('kanal') or None, url=daten.get('url') or None,
                                      folge=daten.get('folge') or None, wer='dashboard')
                erg.pop('befehl', None)
                erg.pop('start_text', None)
                return self._json(200, {'ok': True, **erg})
            if len(teile) == 4 and teile[:2] == ['api', 'sitzung']:
                name, was = teile[2], teile[3]
                if was == 'weiter':
                    return self._json(200, {'ok': True, **starten.weiter(name, wer='dashboard')})
                if was == 'oeffnen':
                    return self._json(200, {'ok': True, **starten.oeffnen(name)})
                if was == 'stopp':
                    return self._json(200, {'ok': True, **starten.stopp(name, wer='dashboard')})
                if was == 'antwort':
                    return self._json(200, {'ok': True, **starten.antworten(name, daten.get('text'), wer='dashboard')})
                if was == 'wahl':
                    return self._json(200, {'ok': True, **starten.waehlen(name, daten.get('nr'), daten.get('text'), wer='dashboard')})
            if len(teile) == 4 and teile[:2] == ['api', 'folge']:
                if teile[3] == 'gepostet':
                    return self._json(200, {'ok': True, **folge_gepostet(teile[2], daten)})
                if teile[3] == 'geplant':
                    return self._json(200, {'ok': True, **folge_geplant(teile[2], daten)})
            if len(teile) == 3 and teile[:2] == ['api', 'ordner']:
                return self._json(200, {'ok': True, **ordner_oeffnen(teile[2], daten)})
            return self._fehler(404, 'Gibt es nicht')
        except SystemExit as e:
            return self._fehler(400, str(e).replace('FEHLER: ', ''))
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            return self._fehler(500, f'Interner Fehler: {type(e).__name__}: {e}')

    def _neustart(self):
        """Antwortet zuerst, dann ersetzt sich der Prozess mit denselben Argumenten (neues Token, Adapter frisch geladen).
        Das Lausch-Socket schließt beim execv (nicht vererbbar), der neue Prozess bindet denselben Port neu."""
        self._json(200, {'ok': True, 'neustart': True})
        self.wfile.flush()
        self.close_connection = True
        print(f'Neustart angefordert (Dashboard) {datetime.now():%H:%M:%S}', flush=True)

        def ersetzen():
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            finally:
                os.execv(sys.executable, [sys.executable, str(Path(sys.argv[0]).resolve()), *sys.argv[1:]])
        threading.Timer(0.35, ersetzen).start()

    def _adapter_post(self, teile, daten):
        """Gleiche Prüfungen wie oben (Host, Origin, Token) sind schon gelaufen. Nur Arten aus `aktionen`."""
        if teile == ['api', 'auftrag']:
            art = str(daten.get('art') or '')
            if not _faehig('auftrag') or art not in _adapter_arten():
                return self._fehler(400, 'Unbekannter Auftrag (Seite neu laden)')
            params = {k: v for k, v in daten.items() if k != 'art'}
            return self._json(200, {'ok': True, **(ADAPTER.auftrag(art, params) or {})})
        if len(teile) == 4 and teile[:2] == ['api', 'sitzung'] and teile[3] in SITZUNG_WAS and _faehig('sitzung'):
            if teile[3] == 'antwort':
                return self._json(200, {'ok': True, **(ADAPTER.sitzung(teile[2], 'antwort', daten.get('text')) or {})})
            if teile[3] == 'wahl':
                return self._json(200, {'ok': True, **(ADAPTER.sitzung(teile[2], 'wahl', {'nr': daten.get('nr'), 'text': daten.get('text')}) or {})})
            return self._json(200, {'ok': True, **(ADAPTER.sitzung(teile[2], teile[3]) or {})})
        if len(teile) == 4 and teile[:2] == ['api', 'folge'] and teile[3] in ('gepostet', 'geplant') \
                and _faehig(f'folge_{teile[3]}'):
            return self._json(200, {'ok': True, **(getattr(ADAPTER, f'folge_{teile[3]}')(teile[2], daten) or {})})
        if len(teile) == 3 and teile[:2] == ['api', 'ordner'] and _faehig('ordner_oeffnen'):
            return self._json(200, {'ok': True, **(ADAPTER.ordner_oeffnen(teile[2], daten) or {})})
        return self._fehler(404, 'Gibt es nicht')

    def do_PUT(self):
        self._fehler(405, 'Nicht erlaubt')

    do_DELETE = do_PATCH = do_PUT


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        """Abgebrochene Verbindungen (z. B. Video-Range beim Spulen, Tab zu) still schlucken statt Traceback ins Log."""
        fehler = sys.exc_info()[1]
        if isinstance(fehler, (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=8777)
    ap.add_argument('--oeffnen', action='store_true', help='Browser öffnen')
    ap.add_argument('--adapter', help='Python-Datei mit stand() usw.: zeigt eine eigene Pipeline (ARCHITEKTUR.md §5)')
    a = ap.parse_args()
    global ADAPTER
    if a.adapter:
        ADAPTER = adapter_laden(a.adapter)
    try:
        srv = Server(('127.0.0.1', a.port), Handler)
    except OSError:
        raise SystemExit(f'FEHLER: Port {a.port} ist belegt. Läuft das Dashboard schon? Sonst: ms dashboard --port 8780')
    srv.token = secrets.token_urlsafe(32)
    url = f'http://127.0.0.1:{a.port}/'
    print(f'Dashboard STUDIO: {url}', flush=True)
    if ADAPTER is not None:
        print(f'Adapter:          {Path(a.adapter).expanduser()} ({_titel()})', flush=True)
    else:
        print(f'Arbeitsordner:    {_ms.arbeit()}', flush=True)
    print('Beenden mit Strg+C.', flush=True)
    if a.oeffnen:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nDashboard beendet.')
    finally:
        srv.server_close()


if __name__ == '__main__':
    sys.exit(main())
