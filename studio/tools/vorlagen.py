"""Vorlagen-Register: Videos von Vorbild-Kanälen sammeln, Views vergleichen, Ausreißer finden.
  ms vorlagen add <url> [--views N] [--creator name] [--titel "…"] [--notiz "…"] [--ohne-info]
  ms vorlagen yt <kanal-url|@handle> [--max 60] [--tab shorts|videos] [--genau]
  ms vorlagen tiktok <@handle> [--max 30]
  ms vorlagen apify <@instagram-handle> [--anzahl 30] [--seit 2026-08-01] [--art reels|posts] [--ja]
  ms vorlagen import <apify.json>
  ms vorlagen liste [--min-views 100000] [--faktor 2] [--creator name] [--status neu] [--plattform youtube] [--n 40] [--json]
  ms vorlagen zeige <id>
  ms vorlagen set <id> [<status>] [--views N | --views-unbekannt] [--notiz "…"]
                                   z. B. nach "ms laden datei" ohne --views: ms vorlagen set <id> --views 250000
Beispiele:
  ms vorlagen yt @kanalname --max 60          YouTube-Shorts, gratis (yt-dlp ohne Login, Datum über den RSS-Feed)
  ms vorlagen apify @kanal --anzahl 30         nur Kostenschätzung, mit --ja echter Lauf (APIFY_TOKEN in .env)
  ms vorlagen liste --faktor 2 --min-views 100000
Register: <arbeit>/vorlagen/register.json, Status: neu | geladen | zerlegt | genutzt | uebersprungen.
Faktor = Views / Median des Creators auf derselben Plattform. Der Median zählt nur Videos, die mindestens
3 Tage alt sind (frische Videos sammeln noch Views), und braucht mindestens 3 Werte."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

import _ms

STATI = ['neu', 'geladen', 'zerlegt', 'genutzt', 'uebersprungen']
FELDER = ['id', 'plattform', 'url', 'creator', 'views', 'likes', 'datum', 'dauer', 'titel', 'status', 'faktor',
          'video', 'transkript', 'notiz']
MIN_ALTER_TAGE = 3
MIN_WERTE_MEDIAN = 3

# Apify-Preise in USD pro Ergebnis (Free-Plan, also der teuerste Fall). Geprüft am 20.10.2026 auf apify.com:
# instagram-reel-scraper 2,60 $ / 1.000 Reels, instagram-scraper 2,70 $ / 1.000 Ergebnisse (bezahlte Pläne günstiger).
APIFY_STAND = '2026-10-20'
APIFY = {'reels': ('apify~instagram-reel-scraper', 0.0026),
         'posts': ('apify~instagram-scraper', 0.0027)}
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)'}


# ---------------------------------------------------------------- Register

def reg_pfad() -> Path:
    return _ms.arbeit() / 'vorlagen' / 'register.json'


def lesen() -> dict:
    reg = _ms.json_lesen(reg_pfad(), None) or {'eintraege': []}
    reg.setdefault('eintraege', [])
    return reg


def schreiben(reg: dict) -> Path:
    faktoren_berechnen(reg)
    return _ms.json_schreiben(reg_pfad(), reg)


def finden(reg: dict, vid: str) -> dict | None:
    return next((e for e in reg['eintraege'] if e.get('id') == vid), None)


def rel(pfad) -> str:
    """Pfad relativ zum Arbeitsordner speichern (Ordner bleibt verschiebbar)."""
    p = Path(pfad).resolve()
    try:
        return p.relative_to(_ms.arbeit().resolve()).as_posix()
    except ValueError:
        return str(p)


def abs_pfad(pfad) -> Path | None:
    if not pfad:
        return None
    p = Path(pfad)
    return p if p.is_absolute() else _ms.arbeit() / p


def neuer_eintrag(**werte) -> dict:
    e = {k: None for k in FELDER}
    e.update({'status': 'neu', 'notiz': ''})
    e.update({k: v for k, v in werte.items() if v is not None})
    e['hinzugefuegt'] = _ms.jetzt()
    return e


def einfuegen(reg: dict, neu: dict) -> tuple[dict, bool]:
    """Fügt ein oder aktualisiert Zahlen und Metadaten. Status, Notiz, video, transkript bleiben erhalten."""
    alt = finden(reg, neu['id'])
    if not alt:
        reg['eintraege'].append(neu)
        return neu, True
    for k, v in neu.items():
        if k in ('status', 'notiz', 'video', 'transkript', 'analyse', 'hinzugefuegt'):
            if not alt.get(k) and v:
                alt[k] = v
            continue
        if v not in (None, '', 0):
            alt[k] = v
    alt['aktualisiert'] = _ms.jetzt()
    return alt, False


def _alter_tage(d: str | None) -> int | None:
    if not d:
        return None
    try:
        return (date.today() - date.fromisoformat(str(d)[:10])).days
    except ValueError:
        return None


def faktoren_berechnen(reg: dict) -> dict:
    """Faktor = Views / Median des Creators (gleiche Plattform, nur Videos >= 3 Tage alt, mind. 3 Werte)."""
    gruppen: dict = {}
    for e in reg['eintraege']:
        if not e.get('views'):
            continue
        alter = _alter_tage(e.get('datum'))
        if alter is None:
            alter = _alter_tage(e.get('aelter_als'))
        if alter is None or alter < MIN_ALTER_TAGE:
            continue
        gruppen.setdefault((e.get('plattform'), (e.get('creator') or '').lower()), []).append(e['views'])
    mediane = {k: statistics.median(v) for k, v in gruppen.items() if len(v) >= MIN_WERTE_MEDIAN}
    for e in reg['eintraege']:
        m = mediane.get((e.get('plattform'), (e.get('creator') or '').lower()))
        e['faktor'] = round(e['views'] / m, 2) if (m and e.get('views')) else None
    reg['mediane'] = {f'{p}:{c}': round(m) for (p, c), m in mediane.items()}
    return mediane


# ---------------------------------------------------------------- URLs

def id_aus_url(url: str) -> dict:
    """Plattform, ID und saubere URL aus einem Link. ID ohne Doppelpunkt (Dateinamen unter Windows)."""
    u = url.strip()
    m = re.search(r'(?:youtube\.com/shorts/|youtu\.be/|youtube\.com/watch\?v=|youtube\.com/embed/)([\w-]{11})', u)
    if m:
        kurz = 'shorts/' in u
        return {'plattform': 'youtube', 'id': f'yt-{m.group(1)}',
                'url': f'https://www.youtube.com/shorts/{m.group(1)}' if kurz else f'https://www.youtube.com/watch?v={m.group(1)}'}
    m = re.search(r'instagram\.com/(?:[\w.]+/)?(?:reel|reels|p|tv)/([\w-]+)', u)
    if m:
        return {'plattform': 'instagram', 'id': f'ig-{m.group(1)}', 'url': f'https://www.instagram.com/reel/{m.group(1)}/'}
    m = re.search(r'tiktok\.com/@([\w.]+)/video/(\d+)', u)
    if m:
        return {'plattform': 'tiktok', 'id': f'tt-{m.group(2)}', 'url': f'https://www.tiktok.com/@{m.group(1)}/video/{m.group(2)}',
                'creator': m.group(1)}
    if not re.match(r'https?://', u):
        raise SystemExit(f'FEHLER: "{url}" ist kein Link. Beispiel: https://www.youtube.com/shorts/<id>')
    return {'plattform': 'web', 'id': 'web-' + hashlib.sha1(u.encode()).hexdigest()[:10], 'url': u}


def _creator(name) -> str | None:
    return str(name).lstrip('@').strip() if name else None


def _datum(roh) -> str | None:
    """'20261019', '2026-10-19T…', Unix-Zeit -> '2026-10-19'."""
    if roh in (None, ''):
        return None
    if isinstance(roh, (int, float)):
        return datetime.fromtimestamp(roh).date().isoformat()
    s = str(roh)
    if re.fullmatch(r'\d{8}', s):
        return f'{s[:4]}-{s[4:6]}-{s[6:]}'
    return s[:10] if re.match(r'\d{4}-\d{2}-\d{2}', s) else None


# ---------------------------------------------------------------- yt-dlp

def ytdlp_json(args: list, zeit=600) -> dict:
    """yt-dlp ohne Cookies, Ausgabe als JSON. Fehler kommen als lesbare Meldung zurück (kein Traceback)."""
    import subprocess
    try:
        r = _ms.befehl(['yt-dlp', '--no-warnings', '--no-update', *args], pruefen=False, timeout=zeit,
                       stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f'keine Antwort nach {zeit} s')
    if r.returncode != 0 or not r.stdout.strip():
        fehler = (r.stderr or '').strip().splitlines()
        raise RuntimeError(next((z for z in reversed(fehler) if 'ERROR' in z), fehler[-1] if fehler else 'unbekannt'))
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        raise RuntimeError('Antwort von yt-dlp nicht lesbar')


def info_holen(url: str) -> dict:
    """Metadaten eines einzelnen Videos (Views, Likes, Datum, Dauer, Titel, Creator) ohne Download."""
    d = ytdlp_json(['-J', '--skip-download', '--no-playlist', url], zeit=120)
    return {'views': d.get('view_count'), 'likes': d.get('like_count'), 'datum': _datum(d.get('upload_date') or d.get('timestamp')),
            'dauer': round(d['duration'], 1) if d.get('duration') else None, 'titel': (d.get('title') or '')[:160],
            'creator': _creator(d.get('uploader_id') or d.get('channel') or d.get('uploader'))}


def _rss_shorts(channel_id: str, tab: str) -> dict:
    """Datum und genaue Views der 15 neuesten Videos aus dem YouTube-RSS-Feed (gratis, ohne Login).
    UUSH… = nur Shorts, UULF… = nur lange Videos."""
    if not channel_id or not channel_id.startswith('UC'):
        return {}
    pl = ('UUSH' if tab == 'shorts' else 'UULF') + channel_id[2:]
    try:
        req = urllib.request.Request(f'https://www.youtube.com/feeds/videos.xml?playlist_id={pl}', headers=UA)
        with urllib.request.urlopen(req, timeout=30) as f:
            wurzel = ET.fromstring(f.read())
    except (urllib.error.URLError, ET.ParseError, TimeoutError, OSError):
        return {}
    ns = {'a': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015',
          'm': 'http://search.yahoo.com/mrss/'}
    aus = {}
    for e in wurzel.findall('a:entry', ns):
        vid = e.findtext('yt:videoId', namespaces=ns)
        stat = e.find('m:group/m:community/m:statistics', ns)
        aus[vid] = {'datum': _datum(e.findtext('a:published', namespaces=ns)),
                    'views': int(stat.get('views')) if stat is not None and stat.get('views') else None}
    return aus


def cmd_yt(a):
    quelle = a.quelle.strip()
    tab = a.tab
    if quelle.startswith('@'):
        url = f'https://www.youtube.com/{quelle}/{tab}'
    elif 'youtube.com' in quelle:
        url = re.sub(r'/(shorts|videos|featured|streams|reels)/?$', '', quelle.rstrip('/')) + f'/{tab}'
    else:
        url = f'https://www.youtube.com/@{quelle}/{tab}'
    print(f'Lese {url} (max. {a.max}, gratis, ohne Login) …')
    args = ['-J', '--playlist-end', str(a.max), url]
    if not a.genau:
        args.insert(0, '--flat-playlist')
    try:
        d = ytdlp_json(args, zeit=60 + (a.max * 4 if a.genau else 0))
    except RuntimeError as ex:
        raise SystemExit(f'FEHLER: YouTube-Kanal nicht lesbar: {ex}\nPrüfe den Link (z. B. https://www.youtube.com/@name) '
                         f'und ob yt-dlp aktuell ist (pip install -U yt-dlp bzw. brew upgrade yt-dlp).')
    creator = _creator(d.get('uploader_id') or d.get('channel') or d.get('uploader'))
    eintraege = [e for e in (d.get('entries') or []) if e and e.get('id')]
    rss = {} if a.genau else _rss_shorts(d.get('channel_id') or '', tab)
    aeltestes_rss = min((v['datum'] for v in rss.values() if v.get('datum')), default=None)
    reg = lesen()
    neu = 0
    for e in eintraege:
        r = rss.get(e['id'], {})
        werte = {'plattform': 'youtube', 'id': f"yt-{e['id']}",
                 'url': f"https://www.youtube.com/shorts/{e['id']}" if tab == 'shorts' else f"https://www.youtube.com/watch?v={e['id']}",
                 'creator': creator, 'views': r.get('views') or e.get('view_count'), 'likes': e.get('like_count'),
                 'datum': r.get('datum') or _datum(e.get('upload_date') or e.get('timestamp')),
                 'dauer': round(e['duration'], 1) if e.get('duration') else None, 'titel': (e.get('title') or '')[:160]}
        if not werte['datum'] and aeltestes_rss and len(rss) >= 15:
            werte['aelter_als'] = aeltestes_rss  # liegt hinter den 15 neuesten, also älter
        _, ist_neu = einfuegen(reg, neuer_eintrag(**werte))
        neu += ist_neu
    schreiben(reg)
    ohne_datum = sum(1 for e in reg['eintraege'] if e.get('creator') == creator and not e.get('datum') and not e.get('aelter_als'))
    print(f'{len(eintraege)} Videos von {creator or "?"} gelesen, {neu} neu im Register. Datum aus RSS für {len(rss)} Videos.')
    if ohne_datum:
        print(f'Hinweis: {ohne_datum} Videos ohne Datum zählen nicht für den Median. Genauer: --genau (langsamer, je Video ~1 s).')
    _ms.log(f'Vorlagen: {len(eintraege)} YouTube-Videos von {creator} gelesen ({neu} neu)', wer='motion-analyse')
    _liste_drucken(reg, _nach_views([e for e in reg['eintraege'] if e.get('creator') == creator]), 15)
    print(reg_pfad())


def cmd_tiktok(a):
    handle = a.handle.lstrip('@').strip()
    url = f'https://www.tiktok.com/@{handle}'
    print(f'Lese {url} (max. {a.max}, gratis, ohne Login) …')
    try:
        d = ytdlp_json(['--flat-playlist', '-J', '--playlist-end', str(a.max), url], zeit=180)
    except RuntimeError as ex:
        raise SystemExit(
            f'FEHLER: TikTok gibt die Liste ohne Login nicht heraus ({str(ex)[:160]}).\n'
            'Das ist bei TikTok häufig und kein Fehler von dir. Wege:\n'
            '  1) yt-dlp aktualisieren und Browser-Nachahmung installieren: pip install -U "yt-dlp[curl-cffi]", dann nochmal\n'
            '  2) einzelne Videos von Hand eintragen: ms vorlagen add <tiktok-video-link> --views <zahl>\n'
            '  3) bezahlter Scraper (z. B. Apify) nur nach Kostenansage und deinem Ja')
    reg = lesen()
    neu = 0
    eintraege = [e for e in (d.get('entries') or []) if e and e.get('id')]
    for e in eintraege:
        werte = {'plattform': 'tiktok', 'id': f"tt-{e['id']}", 'url': e.get('url') or f'{url}/video/{e["id"]}',
                 'creator': handle, 'views': e.get('view_count'), 'likes': e.get('like_count'),
                 'datum': _datum(e.get('timestamp') or e.get('upload_date')),
                 'dauer': round(e['duration'], 1) if e.get('duration') else None,
                 'titel': (e.get('title') or e.get('description') or '')[:160]}
        _, ist_neu = einfuegen(reg, neuer_eintrag(**werte))
        neu += ist_neu
    schreiben(reg)
    print(f'{len(eintraege)} TikToks von @{handle}, {neu} neu im Register.')
    _liste_drucken(reg, _nach_views([e for e in reg['eintraege'] if e.get('creator') == handle and e['plattform'] == 'tiktok']), 15)


def cmd_add(a):
    werte = id_aus_url(a.url)
    if not a.ohne_info and werte['plattform'] in ('youtube', 'tiktok', 'web'):
        try:
            werte.update({k: v for k, v in info_holen(werte['url']).items() if v not in (None, '')})
        except RuntimeError as ex:
            print(f'Hinweis: Metadaten nicht lesbar ({str(ex)[:120]}). Eintrag kommt trotzdem ins Register.')
    elif werte['plattform'] == 'instagram' and not a.views:
        print('Hinweis: Instagram gibt Views ohne Login nicht heraus. Zahl von Hand mit --views N angeben '
              '(steht unter dem Reel) oder per ms vorlagen apify (kostet) nachholen.')
    for k in ('views', 'creator', 'titel', 'notiz'):
        if getattr(a, k):
            werte[k] = _creator(a.creator) if k == 'creator' else getattr(a, k)
    if a.datum:
        werte['datum'] = _datum(a.datum)
    reg = lesen()
    e, ist_neu = einfuegen(reg, neuer_eintrag(**werte))
    schreiben(reg)
    print(f"{'Neu' if ist_neu else 'Aktualisiert'}: {e['id']}  {e.get('views') or '?'} Views  {e.get('creator') or '?'}  "
          f"{e.get('titel') or ''}")
    print(reg_pfad())


# ---------------------------------------------------------------- Apify (kostet Geld)

def _apify(methode, url, token, daten=None, zeit=120):
    req = urllib.request.Request(url, data=json.dumps(daten).encode() if daten is not None else None, method=methode,
                                 headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'})
    try:
        with urllib.request.urlopen(req, timeout=zeit) as f:
            return json.loads(f.read())
    except urllib.error.HTTPError as ex:
        text = ex.read().decode('utf-8', 'replace')[:300]
        raise SystemExit(f'FEHLER: Apify antwortet {ex.code}: {text}')
    except urllib.error.URLError as ex:
        raise SystemExit(f'FEHLER: Apify nicht erreichbar ({ex.reason}). Internet prüfen.')


def cmd_apify(a):
    handle = a.handle.lstrip('@').strip()
    actor, preis = APIFY[a.art]
    schaetzung = a.anzahl * preis
    deckel = round(max(0.05, schaetzung * 1.5), 2)
    print(f'Apify {actor.replace("~", "/")} für @{handle}: bis {a.anzahl} {"Reels" if a.art == "reels" else "Posts"}'
          f'{f" seit {a.seit}" if a.seit else ""}.')
    print(f'Kostenschätzung: {a.anzahl} × {preis:.4f} $ = {schaetzung:.2f} $ (Preis Free-Plan, Stand {APIFY_STAND}; '
          f'harter Deckel für den Lauf: {deckel:.2f} $).')
    if not a.ja:
        print(f'Nichts ausgeführt. Nach dem Ja des Nutzers: ms vorlagen apify @{handle} --anzahl {a.anzahl}'
              f'{f" --seit {a.seit}" if a.seit else ""}{" --art posts" if a.art == "posts" else ""} --ja')
        return
    token = _ms.env('APIFY_TOKEN')
    if not token:
        raise SystemExit(f'FEHLER: APIFY_TOKEN fehlt. Konto auf apify.com anlegen, Token unter Settings → API & Integrations '
                         f'kopieren und als Zeile APIFY_TOKEN=… in {_ms.arbeit() / ".env"} eintragen (nie in Chats posten).')
    if a.art == 'reels':
        eingabe = {'username': [handle], 'resultsLimit': a.anzahl}
    else:
        eingabe = {'directUrls': [f'https://www.instagram.com/{handle}/'], 'resultsType': 'posts', 'resultsLimit': a.anzahl}
    if a.seit:
        eingabe['onlyPostsNewerThan'] = a.seit
    _ms.log(f'Apify-Lauf gestartet: @{handle}, {a.anzahl} {a.art}, Schätzung {schaetzung:.2f} $', wer='motion-analyse', art='kosten')
    lauf = _apify('POST', f'https://api.apify.com/v2/acts/{actor}/runs?maxTotalChargeUsd={deckel}', token, eingabe)['data']
    print('Lauf gestartet, warte auf Ergebnis …', flush=True)
    start = time.time()
    while True:
        time.sleep(8)
        st = _apify('GET', f"https://api.apify.com/v2/actor-runs/{lauf['id']}", token)['data']
        if st['status'] not in ('READY', 'RUNNING'):
            break
        if time.time() - start > 1200:
            raise SystemExit(f"FEHLER: Apify-Lauf {lauf['id']} läuft seit 20 Minuten. In der Apify-Konsole nachsehen.")
    items = _apify('GET', f"https://api.apify.com/v2/datasets/{st['defaultDatasetId']}/items?clean=true&format=json", token,
                   zeit=300)
    kosten = float(st.get('usageTotalUsd') or 0)
    ziel = _ms.arbeit() / 'vorlagen' / 'apify' / f'{handle}-{datetime.now():%Y-%m-%d-%H%M}.json'
    _ms.json_schreiben(ziel, items)
    print(f"Status {st['status']}, {len(items)} Ergebnisse, Kosten {kosten:.3f} $. Rohdaten: {ziel}")
    _ms.log(f'Apify @{handle}: {len(items)} Ergebnisse, {kosten:.3f} USD', wer='motion-analyse', art='kosten')
    _importieren(ziel)


def _importieren(pfad: Path):
    roh = _ms.json_lesen(pfad, None)
    if roh is None:
        raise SystemExit(f'FEHLER: {pfad} gibt es nicht.')
    items = roh.get('items', roh) if isinstance(roh, dict) else roh
    reg = lesen()
    neu = gesamt = 0
    for i in items:
        code = i.get('shortCode') or i.get('code')
        if not code or not (i.get('videoUrl') or i.get('type') == 'Video' or i.get('productType') == 'clips'):
            continue
        gesamt += 1
        cap = ' '.join((i.get('caption') or '').split())
        werte = {'plattform': 'instagram', 'id': f'ig-{code}', 'url': f'https://www.instagram.com/reel/{code}/',
                 'creator': _creator(i.get('ownerUsername')), 'views': i.get('videoPlayCount') or i.get('videoViewCount'),
                 'likes': i.get('likesCount'), 'datum': _datum(i.get('timestamp')),
                 'dauer': round(i['videoDuration'], 1) if i.get('videoDuration') else None, 'titel': cap[:160],
                 'video_url': i.get('videoUrl'), 'audio_url': i.get('audioUrl'), 'cover_url': i.get('displayUrl'),
                 'quelle': rel(pfad), 'kommentare': i.get('commentsCount')}
        _, ist_neu = einfuegen(reg, neuer_eintrag(**werte))
        neu += ist_neu
    schreiben(reg)
    print(f'{gesamt} Videos importiert, {neu} neu. Hinweis: Apify-Videolinks laufen nach einigen Tagen ab, '
          f'also bald mit "ms laden <id>" holen.')
    _liste_drucken(reg, _nach_views([e for e in reg['eintraege'] if e.get('quelle') == rel(pfad)]), 20)


def cmd_import(a):
    _importieren(Path(a.datei).expanduser().resolve())


# ---------------------------------------------------------------- Liste, Zeigen, Status

def _zahl(n) -> str:
    if not n:
        return '-'
    return f'{n / 1e6:.1f}M' if n >= 1e6 else (f'{n / 1e3:.0f}k' if n >= 1e3 else str(n))


def _nach_views(es):
    return sorted(es, key=lambda e: -(e.get('views') or 0))


def _liste_drucken(reg, eintraege, n):
    if not eintraege:
        print('Keine passenden Einträge.')
        return
    print(f"{'id':<16} {'views':>7} {'faktor':>6} {'creator':<18} {'datum':<10} {'dauer':>5} {'status':<13} titel")
    for e in eintraege[:n]:
        f = e.get('faktor')
        print(f"{e['id']:<16} {_zahl(e.get('views')):>7} {(f'{f:.1f}x' if f else '-'):>6} {(e.get('creator') or '-')[:18]:<18} "
              f"{(e.get('datum') or '-'):<10} {(str(e.get('dauer')) if e.get('dauer') else '-'):>5} {e.get('status') or '':<13} "
              f"{(e.get('titel') or '')[:60]}")
    if len(eintraege) > n:
        print(f'… {len(eintraege) - n} weitere (--n erhöhen)')


def cmd_liste(a):
    reg = lesen()
    faktoren_berechnen(reg)
    es = reg['eintraege']
    if a.creator:
        c = a.creator.lstrip('@').lower()
        es = [e for e in es if (e.get('creator') or '').lower() == c]
    if a.plattform:
        es = [e for e in es if e.get('plattform') == a.plattform]
    if a.status:
        es = [e for e in es if e.get('status') == a.status]
    if a.min_views:
        es = [e for e in es if (e.get('views') or 0) >= a.min_views]
    if a.faktor:
        es = [e for e in es if (e.get('faktor') or 0) >= a.faktor]
    es = sorted(es, key=lambda e: -((e.get('faktor') or 0) if a.nach == 'faktor' else (e.get('views') or 0)))
    if a.json:
        print(json.dumps(es[:a.n], ensure_ascii=False, indent=1))
        return
    if reg.get('mediane'):
        print('Mediane (nur Videos >= 3 Tage):', ', '.join(f'{k} {_zahl(v)}' for k, v in sorted(reg['mediane'].items())))
    _liste_drucken(reg, es, a.n)
    print(f'{len(es)} von {len(reg["eintraege"])} Einträgen. Register: {reg_pfad()}')


def cmd_zeige(a):
    reg = lesen()
    e = finden(reg, a.id)
    if not e:
        raise SystemExit(f'FEHLER: {a.id} nicht im Register (ms vorlagen liste).')
    print(json.dumps({k: v for k, v in e.items() if k not in ('video_url', 'audio_url', 'cover_url')}, ensure_ascii=False, indent=1))
    t = abs_pfad(e.get('transkript'))
    if t and t.with_suffix('.txt').exists():
        print('\nTranskript (Anfang):\n' + t.with_suffix('.txt').read_text(encoding='utf-8')[:800])


def cmd_set(a):
    if a.status is None and a.views is None and a.notiz is None and not a.views_unbekannt:
        raise SystemExit('FEHLER: Nichts zu setzen. Beispiele: ms vorlagen set <id> zerlegt | --views 250000 | --views-unbekannt')
    if a.status is not None and a.status not in STATI:
        raise SystemExit(f'FEHLER: Status "{a.status}" unbekannt. Erlaubt: {", ".join(STATI)}')
    if a.views is not None and a.views < 0:
        raise SystemExit('FEHLER: --views muss 0 oder mehr sein.')
    reg = lesen()
    e = finden(reg, a.id)
    if not e:
        raise SystemExit(f'FEHLER: {a.id} nicht im Register (ms vorlagen liste).')
    teile = []
    if a.status is not None:
        e['status'] = a.status
        teile.append(a.status)
    if a.views is not None:
        e['views'] = a.views
        e.pop('views_unbekannt', None)
        teile.append(f'{a.views} Views')
    elif a.views_unbekannt:
        e['views'] = None
        e['views_unbekannt'] = True
        teile.append('Views unbekannt (vermerkt)')
    if a.notiz is not None:
        e['notiz'] = a.notiz
        teile.append(f'Notiz „{a.notiz}“')
    e['aktualisiert'] = _ms.jetzt()
    schreiben(reg)
    print(f'OK {a.id}: ' + ', '.join(teile) + (f' (Faktor {e["faktor"]:.1f}x)' if e.get('faktor') else ''))


def status_setzen(vid: str, status: str, **felder):
    """Für andere Werkzeuge (laden, zerlegen): Status nur vorwärts setzen, nie zurück."""
    reg = lesen()
    e = finden(reg, vid)
    if not e:
        return None
    if status in STATI and STATI.index(status) > STATI.index(e.get('status') or 'neu') and e.get('status') != 'uebersprungen':
        e['status'] = status
    e.update({k: v for k, v in felder.items() if v is not None})
    e['aktualisiert'] = _ms.jetzt()
    schreiben(reg)
    return e


def main():
    ap = argparse.ArgumentParser(prog='ms vorlagen', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('add', help='einen Link ins Register')
    p.add_argument('url')
    p.add_argument('--views', type=int)
    p.add_argument('--creator')
    p.add_argument('--titel')
    p.add_argument('--datum', help='JJJJ-MM-TT')
    p.add_argument('--notiz')
    p.add_argument('--ohne-info', action='store_true', help='keine Metadaten per yt-dlp holen')
    p = sub.add_parser('yt', help='YouTube-Kanal (Shorts-Tab) gratis lesen')
    p.add_argument('quelle')
    p.add_argument('--max', type=int, default=60)
    p.add_argument('--tab', choices=['shorts', 'videos'], default='shorts')
    p.add_argument('--genau', action='store_true', help='jedes Video einzeln lesen (Datum, Dauer, Likes), langsamer')
    p = sub.add_parser('tiktok', help='TikTok-Profil per yt-dlp (kann ohne Login scheitern)')
    p.add_argument('handle')
    p.add_argument('--max', type=int, default=30)
    p = sub.add_parser('apify', help='Instagram über Apify (kostet, erst Schätzung, mit --ja ausführen)')
    p.add_argument('handle')
    p.add_argument('--anzahl', type=int, default=30)
    p.add_argument('--seit', help='nur Posts ab JJJJ-MM-TT')
    p.add_argument('--art', choices=['reels', 'posts'], default='reels')
    p.add_argument('--ja', action='store_true', help='wirklich ausführen (nur nach Ja des Nutzers)')
    p = sub.add_parser('import', help='Apify-JSON ins Register')
    p.add_argument('datei')
    p = sub.add_parser('liste', help='Register filtern und sortieren')
    p.add_argument('--min-views', type=int)
    p.add_argument('--faktor', type=float)
    p.add_argument('--creator')
    p.add_argument('--status', choices=STATI)
    p.add_argument('--plattform', choices=['youtube', 'instagram', 'tiktok', 'web', 'datei'])
    p.add_argument('--nach', choices=['views', 'faktor'], default='views')
    p.add_argument('--n', type=int, default=40)
    p.add_argument('--json', action='store_true')
    p = sub.add_parser('zeige', help='einen Eintrag zeigen')
    p.add_argument('id')
    p = sub.add_parser('set', help='Status, Views oder Notiz eines Eintrags setzen')
    p.add_argument('id')
    p.add_argument('status', nargs='?')
    p.add_argument('--notiz')
    p.add_argument('--views', type=int, help='Views von Hand (z. B. nach ms laden datei, Zahl steht unter dem Video)')
    p.add_argument('--views-unbekannt', action='store_true', help='vermerken, dass die Views nicht zu bekommen sind')
    a = ap.parse_args()
    {'add': cmd_add, 'yt': cmd_yt, 'tiktok': cmd_tiktok, 'apify': cmd_apify, 'import': cmd_import, 'liste': cmd_liste,
     'zeige': cmd_zeige, 'set': cmd_set}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
