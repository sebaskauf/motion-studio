"""Folge rendern und automatisch prüfen: Render, Ton-Mux, Schwarzbild-Scan, Kontaktbögen pro Szene, Bildzahl, LUFS, Vorschau.
  ms render <folge> <name>                       Entwurf (schnell, für die eigene Prüfung)
  ms render <folge> <name> --qualitaet final     Abgabe-Qualität
  ms render <folge> <name> --nur-qa              kein Render, nur die Prüfungen auf vorhandenem out/<name>.mp4
  --workers 2   parallele Chrome-Prozesse (Standard 1: RAM schonen, andere Agenten laufen mit)
  --trotzdem    auch rendern, wenn ms szenen --check Fehler meldet
  --dicht       Szenenbögen mit 10 statt 5 Bildern pro Sekunde (nur bei Verdacht, kostet doppelt so viele Bild-Token)
  --auslauf 0   wie bei ms szenen. Ohne Angabe gilt der Auslauf, mit dem ms szenen index.html gebaut hat
                (Dauer = Stimme + Auslauf = data-duration in index.html). Weicht die Angabe ab: Abbruch mit Hinweis.
Beispiel: ms render 2026-10-20-probe probe-v1
Exakter Ausschnitt (z. B. Pilot genau 10,0 s): ms szenen <pilot> --auslauf 0, dann ms render <pilot> pilot-v1
LANGE RENDERS IM HINTERGRUND STARTEN: Ein Render dauert 1 bis 10 min (unter Last länger). In Claude Code Bash mit
  run_in_background und Ausgabe umleiten: ms render <folge> <name> > <folge>/out/render_<name>.log 2>&1
  Fertig erst, wenn out/<name>.mp4 existiert UND das Log mit "fertig:" endet.

Ablauf
  1. ms szenen --check (Lücken, Dauern) und hyperframes lint, bei Fehlern Abbruch
  2. alte Fassung gleichen Namens (mp4, jpg, qa_<name>/) nach out/_ueberholt/ (nie löschen)
  3. hyperframes render -> out/<name>_roh.mp4, dann Ton darunter: build/assets/audio/mix.wav, sonst die Stimme
  4. Prüfungen: Bildzahl gegen Soll (Dauer × 30, ±1 Bild erlaubt), Schwarzbild-Scan (blackdetect + Dunkel-Sprünge, Treffer außerhalb
     von Szenenschnitten = Fehler, am Schnitt = Hinweis zum Ansehen), Lautheit (Soll −14 LUFS: das Gate ±0,5 gilt beim Mix,
     außerhalb ±1 ist es im Render ein Ausschlussfehler), Kontaktbögen out/qa_<name>/<szene>.jpg (5 Bilder/s, --dicht 10),
     Übersicht out/qa_<name>/uebersicht.jpg (1 Bild/s über die ganze Folge)
  5. out/<name>.jpg Vorschau, out/qa_<name>/RENDER.json + RENDER.md, Status "render" mit Video und Vorschau
Danach (Skill motion-qa, Token-Diät 30.10.2026): Die Regie liest RENDER.md und sieht die Übersicht an, der Prüfer jeden
Szenenbogen. Ein Bogen kostet rund 5 k Token, deshalb jeden Bogen nur einmal und nur bei Verdacht dichter (--dicht)."""
from __future__ import annotations

import argparse
import math
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import _bau
import _ms
import szenen as szenen_werkzeug

QUALI = {'entwurf': 'draft', 'final': 'delivery'}
LUFS_ZIEL = -14.0


def verschieben(out: Path, name: str):
    alt = out / '_ueberholt'
    stempel = datetime.now().strftime('%m%d_%H%M%S')
    for p in [out / f'{name}.mp4', out / f'{name}_roh.mp4', out / f'{name}.jpg', out / f'qa_{name}']:
        if p.exists():
            alt.mkdir(parents=True, exist_ok=True)
            ziel = alt / (f'{p.stem}_{stempel}{p.suffix}' if p.is_file() else f'{p.name}_{stempel}')
            shutil.move(str(p), str(ziel))


def muxen(roh: Path, ton: Path | None, ziel: Path, dauer: float):
    if ton is None:
        _ms.befehl(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', roh, '-map', '0:v', '-c:v', 'copy', ziel])
        return
    _ms.befehl(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', roh, '-i', ton, '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
                '-af', 'apad', '-c:a', 'aac', '-b:a', '256k', '-t', f'{dauer:.3f}', ziel])


def bildzahl(video: Path) -> int:
    r = _ms.befehl(['ffprobe', '-v', 'error', '-count_packets', '-select_streams', 'v:0', '-show_entries',
                    'stream=nb_read_packets', '-of', 'csv=p=0', video])
    try:
        return int(r.stdout.strip().split(',')[0])
    except ValueError:
        return _ms.probe(video)['frames']


def schwarz_scan(video: Path, szenen: list[dict], fps: float) -> list[dict]:
    """Zwei Scans, beide streamend: ffmpeg blackdetect (≥ 90 % des Bildes dunkel) und Sprünge im Dunkelanteil (> 20 %).
    Treffer im Abstand ≤ 0,1 s zu einem Szenenschnitt gelten als erwartbar (Übergang), der Rest ist ein Befund."""
    schnitte = sorted({round(s['start'], 3) for s in szenen} | {round(s['start'] + s['dur'], 3) for s in szenen})

    def am_schnitt(t):
        return any(abs(t - c) <= 0.1 for c in schnitte)

    treffer = []
    r = _ms.befehl(['ffmpeg', '-nostdin', '-v', 'info', '-i', video, '-vf', 'blackdetect=d=0.02:pic_th=0.90:pix_th=0.10',
                    '-an', '-f', 'null', '-'], pruefen=False)
    for m in re.finditer(r'black_start:([\d.]+)\s+black_end:([\d.]+)\s+black_duration:([\d.]+)', r.stderr or ''):
        a, e, d = float(m.group(1)), float(m.group(2)), float(m.group(3))
        treffer.append({'art': 'schwarz', 'von': round(a, 3), 'bis': round(e, 3), 'dauer': round(d, 3),
                        'am_schnitt': am_schnitt(a) and d <= 0.2})
    vorher, i = None, 0
    for t, bild in _ms.frames(video, groesse=(54, 96), grau=True):
        dunkel = float((bild < 28).mean())
        if vorher is not None and abs(dunkel - vorher) > 0.20:
            treffer.append({'art': 'dunkel-sprung', 'von': round(t, 3), 'bis': round(t + 1 / fps, 3),
                            'dauer': round(1 / fps, 3), 'wert': f'{vorher:.2f}→{dunkel:.2f}', 'am_schnitt': am_schnitt(t)})
        vorher = dunkel
        i += 1
    return treffer


def uebersicht(video: Path, ziel: Path, dauer_video: float, spalten=8, breite=150) -> Path:
    """Ein Bild pro Sekunde über die ganze Folge: für den schnellen Blick der Regie (statt aller Szenenbögen)."""
    zeiten = [round(t + 0.5, 2) for t in range(int(max(1, dauer_video)))]
    return _ms.kontaktbogen(video, zeiten, ziel, spalten=spalten, breite=breite, titel=f'{video.name}: 1 Bild pro Sekunde')


def bogen_szene(video: Path, s: dict, ziel: Path, dauer_video: float, spalten=10, breite=216, fps=5) -> Path:
    """Kontaktbogen einer Szene (5 Bilder/s, mit --dicht 10), Bilder gestreamt (nie das ganze Video im RAM)."""
    from PIL import Image, ImageDraw
    hoehe = round(breite * 1920 / 1080)
    von, bis = s['start'], min(s['start'] + s['dur'], dauer_video)
    bilder = [(t, Image.fromarray(b)) for t, b in _ms.frames(video, fps=fps, groesse=(breite, hoehe), start=von, ende=bis)]
    if not bilder:
        bilder = [(von, Image.new('RGB', (breite, hoehe), (80, 0, 0)))]
    zeilen = math.ceil(len(bilder) / spalten)
    kopf = 32
    b = Image.new('RGB', (spalten * breite, kopf + zeilen * (hoehe + 20)), (20, 20, 20))
    z = ImageDraw.Draw(b)
    z.text((8, 6), f"{s['id']}  {von:.2f} bis {bis:.2f} s  ({s.get('art', '?')})  {str(s.get('inhalt', ''))[:90]}",
           fill=(255, 255, 255), font=_ms._schrift(18))
    klein = _ms._schrift(14)
    for i, (t, im) in enumerate(bilder):
        x, y = (i % spalten) * breite, kopf + (i // spalten) * (hoehe + 20)
        b.paste(im, (x, y + 20))
        z.text((x + 4, y + 2), f'{t:.2f}  l{t - von:.2f}', fill=(255, 220, 90), font=klein)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    b.save(ziel, quality=86)
    return ziel


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folge')
    ap.add_argument('name')
    ap.add_argument('--qualitaet', choices=list(QUALI), default='entwurf')
    ap.add_argument('--workers', default=str(_ms.config().get('render_workers', 1)))
    ap.add_argument('--nur-qa', action='store_true')
    ap.add_argument('--trotzdem', action='store_true')
    ap.add_argument('--dicht', action='store_true', help='Szenenbögen mit 10 statt 5 Bildern pro Sekunde (nur bei Verdacht)')
    ap.add_argument('--auslauf', type=float, help='wie ms szenen (Standard: der Auslauf aus index.html)')
    a = ap.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', a.name):
        raise SystemExit('FEHLER: Name nur aus Buchstaben, Ziffern, Punkt, Bindestrich, Unterstrich (z. B. probe-v1).')

    fo = _bau.folge(a.folge)
    build, out = fo / 'build', fo / 'out'
    out.mkdir(exist_ok=True)
    ziel_name = _ms.ziel_name(fo)
    szenen = _bau.szenen_lesen(fo)
    dauer = _bau.index_dauer(build)
    if dauer is None:
        raise SystemExit('FEHLER: build/index.html fehlt oder ohne Dauer. Erst "ms szenen <folge>".')
    video = out / f'{a.name}.mp4'
    befunde, t0 = [], time.time()

    if not a.nur_qa:
        auslauf_index = _bau.index_auslauf(build)
        auslauf = a.auslauf if a.auslauf is not None else (auslauf_index if auslauf_index is not None else _bau.AUSLAUF)
        soll_dauer, _ = _bau.gesamtdauer(fo, auslauf, szenen)
        stil = _bau.caption_stil(fo)
        caps = bool(stil.get('an', True)) and (build / 'compositions' / 'captions.html').exists()
        gruppen = _ms.json_lesen(build / 'captions_gruppen.json') if caps else None
        pr = szenen_werkzeug.pruefen(fo, szenen, dauer, caps, gruppen, True)
        fehler = [t for s, t in pr if s == 'FEHLER']
        if abs(soll_dauer - dauer) > 0.011:
            fehler.append(f'index.html hat Dauer {dauer:.2f} (Auslauf {auslauf_index if auslauf_index is not None else "?"}), '
                          f'Stimme + Auslauf {auslauf:g} ergibt {soll_dauer:.2f}: ms szenen <folge> --auslauf {auslauf:g} neu ausführen')
        if fehler and not a.trotzdem:
            raise SystemExit('ABBRUCH: ms szenen --check meldet Fehler:\n  ' + '\n  '.join(fehler))
        f, w, text = _bau.lint(build)
        if f:
            zeilen = [z for z in text.splitlines() if '✗' in z][:12]
            raise SystemExit('ABBRUCH: hyperframes lint meldet Fehler:\n  ' + '\n  '.join(zeilen or [text[-800:]]))
        verschieben(out, a.name)
        roh = out / f'{a.name}_roh.mp4'
        _ms.log(f'Render {a.name} gestartet ({a.qualitaet}, {dauer:.1f} s)', ziel=ziel_name)
        print(f'Render {a.name} ({a.qualitaet}, {dauer:.2f} s, workers {a.workers}) …', flush=True)
        args = ['render', '-q', QUALI[a.qualitaet], '--workers', a.workers, '-o', str(roh), '.']
        r = _bau.hf(args, build, nett=True)
        log = _bau.ANSI.sub('', (r.stdout or '') + (r.stderr or ''))
        if r.returncode != 0 or not roh.exists():
            _ms.log(f'Render {a.name} fehlgeschlagen', ziel=ziel_name, art='fehler')
            raise SystemExit(f'FEHLER: hyperframes render (Code {r.returncode})\n{log[-2500:]}')
        (out / f'render_{a.name}_hyperframes.log').write_text(log, encoding='utf-8')
        ton = _bau.ton_finden(fo)
        muxen(roh, ton, video, dauer)
        print(f'Render fertig in {time.time() - t0:.0f} s, Ton: {ton.name if ton else "keiner"}', flush=True)
    elif not video.exists():
        raise SystemExit(f'FEHLER: {video} gibt es nicht (für --nur-qa muss es schon gerendert sein).')

    info = _ms.probe(video)
    fps = info['fps'] or 30
    n_ist, n_soll = bildzahl(video), round(dauer * 30)
    if abs(n_ist - n_soll) > 1:
        befunde.append(('FEHLER', f'Bildzahl {n_ist} statt {n_soll} (Dauer {dauer:.2f} s × 30, erlaubt ±1)'))
    treffer = schwarz_scan(video, szenen, fps)
    for h in treffer:
        if h['am_schnitt']:
            befunde.append(('HINWEIS', f"{h['art']} bei {h['von']:.2f} bis {h['bis']:.2f} s {h.get('wert', '')} am Szenenschnitt: "
                                       f"gewollter Übergang (dunkler Hintergrund)? Sonst lädt eine Szene zu spät. Bild ansehen"))
        else:
            befunde.append(('FEHLER', f"{h['art']} bei {h['von']:.2f} bis {h['bis']:.2f} s {h.get('wert', '')} "
                                      f"(nicht an einem Szenenschnitt): Bild ziehen und ansehen"))
    lautheit = None
    if info['ton']:
        lautheit = _ms.lufs(video)
        if abs(lautheit - LUFS_ZIEL) > 1.0:
            befunde.append(('HINWEIS' if a.qualitaet == 'entwurf' else 'FEHLER',
                            f'Lautheit {lautheit:.1f} LUFS außerhalb −14 ±1 (bei der Abgabe ein Ausschlussfehler; das Mix-Gate ist −14 ±0,5). '
                            f'Mix fehlt oder ist veraltet? Skill motion-ton-mix'))
    else:
        befunde.append(('HINWEIS', 'Video ohne Ton'))
    qa = out / f'qa_{a.name}'
    boegen = [bogen_szene(video, s, qa / f"{s['id']}.jpg", info['dauer'], fps=10 if a.dicht else 5) for s in szenen]
    ueber = uebersicht(video, qa / 'uebersicht.jpg', info['dauer'])
    from PIL import Image
    t_v = min(1.0, info['dauer'] / 2)
    Image.fromarray(_ms.frame_bei(video, t_v, (540, 960))).save(out / f'{a.name}.jpg', quality=88)

    ergebnis = {'video': f'out/{a.name}.mp4', 'qualitaet': a.qualitaet, 'dauer': info['dauer'], 'bilder': n_ist,
                'bilder_soll': n_soll, 'lufs': lautheit, 'schwarz_treffer': treffer,
                'befunde': [{'schwere': s, 'text': t} for s, t in befunde], 'boegen': [str(b.relative_to(fo)) for b in boegen],
                'renderzeit_s': round(time.time() - t0, 1), 'zeit': _ms.jetzt()}
    _ms.json_schreiben(qa / 'RENDER.json', ergebnis)
    md = [f'# Render {a.name}', '', f'- Video: out/{a.name}.mp4 ({info["dauer"]:.2f} s, {n_ist}/{n_soll} Bilder, {a.qualitaet})',
          f'- Lautheit: {lautheit:.1f} LUFS' if lautheit is not None else '- Lautheit: kein Ton',
          f'- Schwarzbild-Scan: {len(treffer)} Treffer, davon {sum(1 for h in treffer if not h["am_schnitt"])} außerhalb von Schnitten',
          '', '## Befunde', ''] + ([f'- **{s}** {t}' for s, t in befunde] or ['- keine']) + \
         ['', f'## Übersicht (Regie): {ueber.name}', '', '## Kontaktbögen je Szene (Prüfer: jeden einmal ansehen)', ''] + [f'- {b.name}' for b in boegen]
    (qa / 'RENDER.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    if not a.nur_qa:   # --nur-qa ändert den Status nicht (prüft evtl. eine ältere Fassung)
        _ms.status_setzen(fo, 'render', f'Render {a.name} ({a.qualitaet}): {len(befunde)} Befunde',
                          video=f'out/{a.name}.mp4', vorschau=f'out/{a.name}.jpg')

    print(f'Bilder {n_ist}/{n_soll} · Lautheit {lautheit if lautheit is None else round(lautheit, 1)} LUFS · '
          f'Schwarz-Treffer {len(treffer)} ({sum(1 for h in treffer if not h["am_schnitt"])} außerhalb von Schnitten)')
    print('Befunde:', 'keine' if not befunde else len(befunde))
    for s, t in befunde:
        print(f'  {s}: {t}')
    print(f'Übersicht (Regie): {ueber}')
    print('Kontaktbögen je Szene (der Prüfer sieht jeden an, die Regie nur bei Befund oder Verdacht):')
    for b in boegen:
        print(f'  {b}')
    print(f'fertig: {video} ({time.time() - t0:.0f} s)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
