"""Vorrat und Posten-Stand: fertige EIGENE Folgen, die noch nicht überall gepostet sind.
Gemeinsam für ms autopilot (Puffer, Posten-Schritt), ms posten und das Studio.

Eigene Folge = STATUS art "folge" und quelle "eigen" (setzt `ms neu folge --idee …`). Pilot, Nachbau und Kopie eines fremden
Videos sind nie eigen und werden nie automatisch gepostet (Sebastian 30.10.2026). Alte Folgen ohne quelle zählen nicht.
Je Plattform steht das Ergebnis in STATUS.json unter posts: {"instagram": {"zeit", "ok": true, "link"} | {"zeit", "ok": false, "fehler"}}.
Freigabe je Kanal und Plattform: kanaele/<k>/posten/<plattform>.md (gespeicherter Ablauf) UND ein Eintrag in
kanaele/<k>/posten/freigabe.json (vom Nutzer bestätigter erster Lauf, `ms posten freigabe`). Erst dann postet der Autopilot dort."""
from __future__ import annotations

import re
from pathlib import Path

import _ms

PLATTFORMEN = ['instagram', 'tiktok', 'youtube', 'facebook']
NAMEN = {'instagram': 'Instagram', 'tiktok': 'TikTok', 'youtube': 'YouTube', 'facebook': 'Facebook'}
OFFEN = ('fertig', 'geplant')


def folge_id(st: dict) -> str:
    return str(st.get('id') or str(st.get('_ordner', '')).split('/', 1)[-1])


def ist_eigen(st: dict) -> bool:
    return (st.get('art') or 'folge') == 'folge' and st.get('quelle') == 'eigen'


def kanal_ordner(kanal: str) -> Path:
    return _ms.arbeit() / 'kanaele' / kanal


def plattformen_profil() -> list[str]:
    """Plattformen aus PROFIL.md (Zeile „- Plattformen: …“), in fester Reihenfolge."""
    p = _ms.arbeit() / 'PROFIL.md'
    try:
        text = p.read_text(encoding='utf-8')
    except OSError:
        return []
    m = re.search(r'^\s*-\s*Plattformen\s*:\s*(.+)$', text, re.M | re.I)
    if not m or m.group(1).strip().startswith('('):
        return []
    roh = m.group(1).lower()
    return [p for p in PLATTFORMEN if p in roh or (p == 'youtube' and 'shorts' in roh)]


def freigaben(kanal: str) -> dict:
    """{plattform: {zeit, zitat, ablauf}} nur für Plattformen mit gespeichertem Ablauf UND Freigabe des Nutzers."""
    d = kanal_ordner(kanal) / 'posten'
    roh = _ms.json_lesen(d / 'freigabe.json', {}) or {}
    return {p: dict(v, ablauf=f'kanaele/{kanal}/posten/{p}.md') for p, v in roh.items()
            if p in PLATTFORMEN and isinstance(v, dict) and (d / f'{p}.md').is_file()}


def ziel_plattformen(kanal: str) -> list[str]:
    """Wo diese Folgen hin sollen: Plattformen aus dem Profil, sonst die freigegebenen."""
    return plattformen_profil() or list(freigaben(kanal))


def posts(st: dict) -> dict:
    p = st.get('posts')
    return p if isinstance(p, dict) else {}


def offen_auf(st: dict, plattformen: list[str]) -> list[str]:
    ps = posts(st)
    return [p for p in plattformen if not (isinstance(ps.get(p), dict) and ps[p].get('ok'))]


def fehler_posten(st: dict) -> dict:
    """{plattform: fehlertext} der letzten fehlgeschlagenen Posts, die noch nicht erledigt sind."""
    return {p: str(v.get('fehler') or 'fehlgeschlagen') for p, v in posts(st).items()
            if isinstance(v, dict) and v.get('ok') is False and not v.get('erledigt')}


def upload_dateien(ordner: Path, fid: str) -> dict:
    up = ordner / 'upload'
    videos = sorted(up.glob('*.mp4')) if up.is_dir() else []
    haupt = up / f'{fid}.mp4'
    video = haupt if haupt.is_file() else next((v for v in videos if v.name != 'post.mp4'), None)
    return {'video': video, 'post': up / 'post.mp4' if (up / 'post.mp4').is_file() else None,
            'caption': up / 'CAPTION.md' if (up / 'CAPTION.md').is_file() else None,
            'titel': up / 'TITEL.txt' if (up / 'TITEL.txt').is_file() else None,
            'titelbild': up / 'titelbild.jpg' if (up / 'titelbild.jpg').is_file() else None}


def pruefurteil(ordner: Path) -> str:
    try:
        text = (ordner / 'PRUEFBERICHT.md').read_text(encoding='utf-8').lower()
    except OSError:
        return ''
    for urteil in ('nicht abnahmefähig', 'gut mit mängeln', 'sehr gut'):
        if urteil in text[:1500]:
            return urteil
    return 'unklar'


def eintrag(st: dict, kanal_plattformen: list[str] | None = None) -> dict:
    """Ein Vorrat-Eintrag mit postbar/grund in Klartext."""
    fid = folge_id(st)
    ordner = _ms.arbeit() / (st.get('_ordner') or f'folgen/{fid}')
    kanal = str(st.get('kanal') or '')
    plattf = kanal_plattformen if kanal_plattformen is not None else ziel_plattformen(kanal)
    dateien = upload_dateien(ordner, fid)
    caption = ''
    if dateien['caption']:
        try:
            caption = dateien['caption'].read_text(encoding='utf-8').strip()[:2200]
        except OSError:
            pass
    offen = offen_auf(st, plattf)
    fehler = fehler_posten(st)
    grund = ''
    if not ist_eigen(st):
        grund = 'Pilot oder Nachbau, wird nie gepostet' if st.get('art') in ('pilot', 'kopie') else 'keine eigene Folge (quelle fehlt, ältere Version: Nutzer fragen, dann ms posten eigen)'
    elif st.get('phase') not in OFFEN:
        grund = 'noch nicht fertig' if st.get('phase') != 'gepostet' else 'schon gepostet'
    elif not dateien['video']:
        grund = 'Video im Upload-Ordner fehlt'
    elif not caption:
        grund = 'CAPTION.md im Upload-Ordner fehlt'
    elif pruefurteil(ordner) == 'nicht abnahmefähig':
        grund = 'Prüfung nicht bestanden'
    elif not plattf:
        grund = 'keine Plattform im Profil'
    elif not offen:
        grund = 'auf allen Plattformen gepostet'
    elif fehler:
        grund = 'Posten fehlgeschlagen: ' + '; '.join(f'{NAMEN.get(p, p)}: {t}' for p, t in fehler.items())
    return {'folge_id': fid, 'titel': st.get('titel') or fid, 'kanal': kanal, 'phase': st.get('phase'),
            'postbar': not grund, 'grund': grund, 'caption': caption, 'caption_da': bool(caption),
            'video': str(dateien['video']) if dateien['video'] else None, 'plattformen': plattf, 'offen': offen,
            'fehler': fehler, 'geplant': st.get('geplant'), 'erstellt': st.get('erstellt')}


def _alle() -> list[dict]:
    try:
        return _ms.alle_status()
    except Exception:  # eine kaputte STATUS.json soll Autopilot und Studio nicht stoppen
        return []


def vorrat(kanal: str | None = None, alle: list[dict] | None = None) -> list[dict]:
    """Eigene Folgen in fertig/geplant (also noch nicht überall gepostet), älteste zuerst."""
    alle = _alle() if alle is None else alle
    cache: dict = {}
    aus = []
    for st in alle:
        if st.get('art') == 'kanal' or not ist_eigen(st) or st.get('phase') not in OFFEN:
            continue
        if kanal and st.get('kanal') != kanal:
            continue
        k = str(st.get('kanal') or '')
        if k not in cache:
            cache[k] = ziel_plattformen(k)
        aus.append(eintrag(st, cache[k]))
    return sorted(aus, key=lambda e: str(e.get('erstellt') or ''))


def ungepostet(kanal: str | None = None, alle: list[dict] | None = None) -> int:
    """Puffer-Zahl: ungepostete eigene Folgen des Kanals (Pilot, Nachbau, Kopie und Gepostetes zählen nicht)."""
    return len(vorrat(kanal, alle))
