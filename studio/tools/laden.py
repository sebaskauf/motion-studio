"""Vorlage-Video laden (yt-dlp ohne Login oder Apify-Link), Tonspur sichern, transkribieren.
  ms laden <register-id|url> [--kanal <slug>] [--ohne-transkript] [--sprache auto] [--neu]
  ms laden datei <pfad> [--id <id>] [--url <quelle>] [--creator name] [--views N] [--kanal <slug>]
Beispiele:
  ms laden yt-abc123xyz00 --kanal mein-kanal          YouTube-Short laden, im Kanal als Vorbild verlinken
  ms laden https://www.youtube.com/shorts/<id>     Link geht auch, landet dabei im Register
  ms laden datei ~/Downloads/reel.mp4 --url https://www.instagram.com/reel/<code>/ --views 250000
Ergebnis: <arbeit>/vorlagen/videos/<id>.mp4, Transkript <arbeit>/vorlagen/transkripte/<id>.json + .txt, Register 'geladen'.
Mit --kanal zusätzlich kanaele/<slug>/vorbild/<id>.mp4 (Verweis) + <id>.json.
Instagram: yt-dlp lädt öffentliche Reels oft auch ohne Login (dann ohne Views). Scheitert es: Apify-Import
(ms vorlagen apify, kostet ein paar Cent) oder das Video selbst speichern und mit "ms laden datei" übernehmen.
Nie Browser-Cookies verwenden. yt-dlp aktuell halten: alte Versionen brechen bei YouTube mit 403 ab."""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

import _ms
import transkript as T
import vorlagen as V


def videos_ordner() -> Path:
    d = _ms.arbeit() / 'vorlagen' / 'videos'
    d.mkdir(parents=True, exist_ok=True)
    return d


def http_laden(url: str, ziel: Path, was='Video'):
    """Lädt eine Datei in Blöcken (nie alles im RAM)."""
    req = urllib.request.Request(url, headers=V.UA)
    try:
        with urllib.request.urlopen(req, timeout=120) as r, open(ziel, 'wb') as f:
            shutil.copyfileobj(r, f, 1 << 20)
    except urllib.error.HTTPError as ex:
        if ex.code in (403, 410):
            raise SystemExit(f'FEHLER: {was}-Link abgelaufen ({ex.code}). Apify-Links gelten nur wenige Tage: '
                             f'Daten neu holen (ms vorlagen apify …, kostet) oder Video selbst laden + "ms laden datei".')
        raise SystemExit(f'FEHLER: {was} nicht ladbar ({ex.code}).')
    except (urllib.error.URLError, TimeoutError, OSError) as ex:
        raise SystemExit(f'FEHLER: {was} nicht ladbar ({ex}). Internet prüfen.')


def ytdlp_laden(url: str, tmp: Path) -> tuple[Path, dict]:
    """Bestes Video bis 1080p (h264 bevorzugt, läuft überall) plus Ton, als mp4. Ohne Cookies."""
    vorlage = str(tmp / 'v.%(ext)s')
    r = _ms.befehl(['yt-dlp', '--no-warnings', '--no-update', '--no-playlist', '-f', 'bv*+ba/b',
                    '-S', 'res:1080,vcodec:h264,acodec:m4a', '--merge-output-format', 'mp4', '--write-info-json',
                    '-o', vorlage, url], pruefen=False, stdin=subprocess.DEVNULL)
    dateien = [p for p in tmp.glob('v.*') if p.suffix not in ('.json', '.part', '.ytdl')]
    if r.returncode != 0 or not dateien:
        zeilen = (r.stderr or '').strip().splitlines()
        raise RuntimeError(next((z for z in reversed(zeilen) if 'ERROR' in z), zeilen[-1] if zeilen else 'unbekannt'))
    info = _ms.json_lesen(tmp / 'v.info.json', {}) or {}
    return dateien[0], info


def als_mp4(quelle: Path, ziel: Path):
    """Übernimmt eine Videodatei als mp4 (umverpacken, sonst neu kodieren)."""
    if quelle.suffix.lower() == '.mp4':
        shutil.copy2(quelle, ziel)
        return
    r = _ms.befehl(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(quelle), '-c', 'copy', '-movflags', '+faststart',
                    str(ziel)], pruefen=False)
    if r.returncode != 0:
        _ms.befehl(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(quelle), '-c:v', 'libx264', '-crf', '17',
                    '-preset', 'fast', '-c:a', 'aac', '-b:a', '192k', str(ziel)])


def ton_nachladen(video: Path, audio_url: str):
    """Apify liefert bei Reels oft ein Video ohne Ton und den Ton als eigenen Link: beides zusammenführen."""
    with tempfile.TemporaryDirectory() as tmp:
        a = Path(tmp) / 'a.m4a'
        http_laden(audio_url, a, 'Ton')
        aus = Path(tmp) / 'mit_ton.mp4'
        _ms.befehl(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(video), '-i', str(a), '-map', '0:v:0',
                    '-map', '1:a:0', '-c', 'copy', '-shortest', str(aus)])
        shutil.move(str(aus), video)


def im_kanal_verlinken(kanal: str, e: dict, video: Path):
    k = _ms.arbeit() / 'kanaele' / kanal
    if not (k / 'STATUS.json').exists():
        raise SystemExit(f'FEHLER: Kanal {kanal} gibt es nicht. Erst "ms neu kanal {kanal} --vorbild …".')
    d = k / 'vorbild'
    d.mkdir(parents=True, exist_ok=True)
    ziel = d / f"{e['id']}{video.suffix}"
    if not ziel.exists():
        try:
            os.symlink(video, ziel)
        except OSError:
            try:
                os.link(video, ziel)
            except OSError:
                shutil.copy2(video, ziel)
    _ms.json_schreiben(d / f"{e['id']}.json", {k2: e.get(k2) for k2 in V.FELDER + ['aelter_als', 'kommentare']
                                                  if e.get(k2) is not None} | {'video_absolut': str(video)})
    return ziel


def laden(e: dict, neu=False) -> Path:
    ziel = videos_ordner() / f"{e['id']}.mp4"
    if ziel.exists() and not neu:
        print(f'Video liegt schon da: {ziel.name}')
        return ziel
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        if e.get('video_url'):
            print('Lade Video über den Apify-Link …', flush=True)
            roh = tmp / 'v.mp4'
            http_laden(e['video_url'], roh)
            als_mp4(roh, ziel)
        else:
            print(f"Lade {e['url']} per yt-dlp (ohne Login) …", flush=True)
            try:
                datei, info = ytdlp_laden(e['url'], tmp)
            except RuntimeError as ex:
                if e.get('plattform') == 'instagram':
                    raise SystemExit(
                        f'FEHLER: Instagram gibt dieses Video ohne Login nicht heraus ({str(ex)[:120]}).\n'
                        'Wege (Browser-Cookies verwenden wir nie):\n'
                        f'  1) Apify: ms vorlagen apify @{e.get("creator") or "<handle>"} --anzahl 30 (zeigt erst die Kosten, '
                        'dann mit --ja), danach ms laden ' + e['id'] + '\n'
                        f'  2) Video selbst speichern und übernehmen: ms laden datei <pfad> --id {e["id"]}')
                if '403' in str(ex):
                    raise SystemExit(f'FEHLER: YouTube bricht den Download ab ({ex}). Fast immer ist yt-dlp zu alt: '
                                     'ältere Versionen stoppen bei rund 10 MB mit 403. Aktualisieren (pip install -U yt-dlp '
                                     'bzw. brew upgrade yt-dlp, "ms check" zeigt die Version), dann nochmal.')
                raise SystemExit(f'FEHLER: Download fehlgeschlagen: {ex}\nyt-dlp aktuell? (pip install -U yt-dlp bzw. '
                                 'brew upgrade yt-dlp). Sonst Video selbst laden und "ms laden datei <pfad>".')
            als_mp4(datei, ziel)
            meta = {'views': info.get('view_count'), 'likes': info.get('like_count'),
                    'datum': V._datum(info.get('upload_date') or info.get('timestamp')),
                    'titel': (info.get('title') or '')[:160] or None,
                    'creator': V._creator(info.get('uploader_id') or info.get('channel') or info.get('uploader'))}
            for k, v in meta.items():
                if v and not e.get(k):
                    e[k] = v
    return ziel


def nachbereiten(e: dict, video: Path, a) -> dict:
    info = _ms.probe(video)
    if not info['ton'] and e.get('audio_url'):
        print('Video ohne Tonspur, lade den Ton nach …', flush=True)
        ton_nachladen(video, e['audio_url'])
        info = _ms.probe(video)
    felder = {'video': V.rel(video), 'dauer': round(info['dauer'], 1),
              'format': f"{info['breite']}x{info['hoehe']} {info['fps']} fps"}
    for k in ('views', 'likes', 'datum', 'titel', 'creator'):
        if e.get(k):
            felder[k] = e[k]
    e = V.status_setzen(e['id'], 'geladen', **felder) or e
    groesse = video.stat().st_size / 1e6
    print(f"OK {e['id']}: {info['breite']}x{info['hoehe']}, {info['fps']} fps, {info['dauer']:.1f} s, "
          f"{'mit' if info['ton'] else 'OHNE'} Ton, {groesse:.1f} MB")
    ziel_log = None
    if a.kanal:
        link = im_kanal_verlinken(a.kanal, e, video)
        ziel_log = f'kanaele/{a.kanal}'
        print(f'Im Kanal verlinkt: {link}')
    _ms.log(f"Vorlage {e['id']} geladen ({info['dauer']:.0f} s)", wer='motion-analyse', ziel=ziel_log)
    if not a.ohne_transkript:
        if not info['ton']:
            print('Kein Ton, also kein Transkript.')
        else:
            tj = _ms.arbeit() / 'vorlagen' / 'transkripte' / f"{e['id']}.json"
            print('Transkribiere (lokal) …', flush=True)
            t = T.transkribieren(video, tj, a.sprache, neu=a.neu)
            V.status_setzen(e['id'], 'geladen', transkript=V.rel(tj))
            print('Transkript:', T.kurzbericht(t))
            print(tj.with_suffix('.txt'))
    print(video)
    return e


def cmd_datei(a):
    quelle = Path(a.pfad).expanduser().resolve()
    if not quelle.exists():
        raise SystemExit(f'FEHLER: {quelle} gibt es nicht.')
    if a.url:
        werte = V.id_aus_url(a.url)
    else:
        werte = {'plattform': 'datei', 'url': None}
    vid = a.id or werte.get('id') or 'datei-' + re.sub(r'[^a-z0-9-]+', '-', quelle.stem.lower()).strip('-')[:40]
    werte['id'] = vid
    for k in ('creator', 'views'):
        if getattr(a, k):
            werte[k] = V._creator(a.creator) if k == 'creator' else a.views
    reg = V.lesen()
    e, _ = V.einfuegen(reg, V.neuer_eintrag(**werte))
    V.schreiben(reg)
    ziel = videos_ordner() / f'{vid}.mp4'
    if ziel.exists() and not a.neu:
        print(f'Video liegt schon da: {ziel.name} (--neu überschreibt)')
    else:
        als_mp4(quelle, ziel)
    nachbereiten(dict(e), ziel, a)


def main():
    ap = argparse.ArgumentParser(prog='ms laden', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('ziel', help='Register-ID, Link oder "datei"')
    ap.add_argument('pfad', nargs='?', help='nur bei "datei": Pfad zur Videodatei')
    ap.add_argument('--kanal')
    ap.add_argument('--ohne-transkript', action='store_true')
    ap.add_argument('--sprache', default='auto')
    ap.add_argument('--neu', action='store_true', help='erneut laden bzw. transkribieren')
    ap.add_argument('--id')
    ap.add_argument('--url')
    ap.add_argument('--creator')
    ap.add_argument('--views', type=int)
    a = ap.parse_args()
    if a.ziel == 'datei':
        if not a.pfad:
            ap.error('Pfad fehlt: ms laden datei <pfad>')
        return cmd_datei(a)
    reg = V.lesen()
    if re.match(r'https?://', a.ziel):
        werte = V.id_aus_url(a.ziel)
        e = V.finden(reg, werte['id'])
        if not e:
            e, _ = V.einfuegen(reg, V.neuer_eintrag(**werte))
            V.schreiben(reg)
    else:
        e = V.finden(reg, a.ziel)
        if not e:
            raise SystemExit(f'FEHLER: {a.ziel} nicht im Register. "ms vorlagen liste" zeigt alle IDs, ein Link geht auch.')
    e = dict(e)
    video = laden(e, a.neu)
    nachbereiten(e, video, a)


if __name__ == '__main__':
    sys.exit(main())
