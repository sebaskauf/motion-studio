"""Einzelbilder einer Folge an Zeitpunkten rendern (schnell, ohne Vollrender) plus Kontaktbogen zum Ansehen.
  ms snap <folge> 0.0 1.25 3.4                 globale Zeiten (auch "0,1.25,3.4")
  ms snap <folge> --szene s2                   Raster 0,25 s über die Szene s2 (erstes und letztes Bild immer dabei)
  ms snap <folge> --szene s2 --raster 0.1      dichteres Raster
  ms snap <folge> --szene s2 --lokal 0.4 1.1   Zeiten LOKAL zur Szene (= Wortzeit − Szenenstart)
  ms snap <folge> --raster 0.5                 Raster über die ganze Folge
  ms snap <folge> 2.4 3.1 --gegen <folge>/vorbild/ausschnitt.mp4   zusätzlich das Original an denselben Zeiten
                                                (Pilot; der Ausschnitt aus "ms stimme --original" hat die Zeitachse des Pilots).
                                                Ergebnis dann auch kontaktbogen_paar*.jpg: je Zeitpunkt Original | Nachbau
                                                nebeneinander, beschriftet (ein Bogen statt vieler pair-*.jpg)
  --name kern_s2     Ordnername unter snapshots/ (Standard: Szene bzw. "snap"). Gleicher Name: hyperframes ersetzt die
                     Bilder, der vorige Kontaktbogen wandert vorher nach <name>/_ueberholt/ (Vorher-Nachher-Vergleich)
Ergebnis: <folge>/snapshots/<name>/frame-*.png (volle Auflösung) + kontaktbogen*.jpg (Zeiten global und lokal beschriftet).
Vorher läuft hyperframes lint: ein Skriptfehler in EINER Szene rendert die ganze Seite leer, deshalb Abbruch bei lint-Fehlern.
Dauer: etwa 1,5 s pro Bild (3D-Szenen länger). Kontaktbogen danach mit dem Read-Tool ansehen."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import _bau
import _ms

PRO_BOGEN = 36


def zeiten_parsen(liste) -> list[float]:
    aus = []
    for x in liste or []:
        for teil in str(x).replace(';', ',').split(','):
            teil = teil.strip()
            if teil:
                try:
                    aus.append(float(teil))
                except ValueError:
                    raise SystemExit(f'FEHLER: "{teil}" ist keine Zeit in Sekunden.')
    return aus


def raster(von: float, bis: float, schritt: float) -> list[float]:
    n = int((bis - von) / schritt + 1e-6)
    zs = [von + i * schritt for i in range(n + 1)]
    if bis - zs[-1] > schritt * 0.3:
        zs.append(bis)
    return zs


def szene_von(szenen, t):
    """Oberste Szene, die zur globalen Zeit t sichtbar ist (für die lokale Beschriftung)."""
    kand = [s for s in szenen if s['start'] - 1e-6 <= t < s['start'] + s['dur']]
    return max(kand, key=lambda s: s['track']) if kand else None


def bogen(bilder: list[tuple[float, Path]], ziel: Path, szenen, titel: str, spalten=6, breite=270) -> Path:
    from PIL import Image, ImageDraw
    hoehe = round(breite * 1920 / 1080)
    zeilen = (len(bilder) + spalten - 1) // spalten
    kopf = 34
    b = Image.new('RGB', (spalten * breite, kopf + zeilen * (hoehe + 40)), (20, 20, 20))
    z = ImageDraw.Draw(b)
    klein, gross = _ms._schrift(15), _ms._schrift(20)
    z.text((8, 7), titel, fill=(255, 255, 255), font=gross)
    for i, (t, p) in enumerate(bilder):
        x, y = (i % spalten) * breite, kopf + (i // spalten) * (hoehe + 40)
        try:
            im = Image.open(p).convert('RGB').resize((breite, hoehe), Image.LANCZOS)
        except OSError:
            im = Image.new('RGB', (breite, hoehe), (80, 0, 0))
        b.paste(im, (x, y + 40))
        s = szene_von(szenen, t)
        z.text((x + 6, y + 2), f'{t:.2f}s', fill=(255, 220, 90), font=klein)
        if s:
            z.text((x + 6, y + 20), f"{s['id']} lokal {t - s['start']:.2f}", fill=(150, 210, 255), font=klein)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    b.save(ziel, quality=88)
    return ziel


PRO_PAARBOGEN = 18


def paarbogen(paare: list[tuple[float, Path | None, Path]], ziel: Path, szenen, titel: str, spalten=3, breite=240) -> Path:
    """paare = [(t, original_png | None, nachbau_png)] -> je Kachel Original links | Nachbau rechts, Zeit global und lokal."""
    from PIL import Image, ImageDraw
    hoehe = round(breite * 1920 / 1080)
    kw, kopf_k = 2 * breite + 4, 40
    zeilen = (len(paare) + spalten - 1) // spalten
    kopf = 34
    b = Image.new('RGB', (spalten * (kw + 10), kopf + zeilen * (hoehe + kopf_k + 10)), (20, 20, 20))
    z = ImageDraw.Draw(b)
    klein, gross = _ms._schrift(15), _ms._schrift(20)
    z.text((8, 7), titel + '   (je Paar: links Original | rechts Nachbau)', fill=(255, 255, 255), font=gross)

    def laden(p):
        try:
            return Image.open(p).convert('RGB').resize((breite, hoehe), Image.LANCZOS) if p else None
        except OSError:
            return None
    for i, (t, ref, nach) in enumerate(paare):
        x, y = (i % spalten) * (kw + 10), kopf + (i // spalten) * (hoehe + kopf_k + 10)
        for k, (bild, name) in enumerate(((laden(ref), 'Original'), (laden(nach), 'Nachbau'))):
            if bild is None:
                bild = Image.new('RGB', (breite, hoehe), (80, 0, 0))
                ImageDraw.Draw(bild).text((10, hoehe // 2), f'kein {name}', fill=(255, 255, 255), font=klein)
            b.paste(bild, (x + k * (breite + 4), y + kopf_k))
            z.text((x + k * (breite + 4) + 6, y + 21), name, fill=(200, 200, 200), font=klein)
        s = szene_von(szenen, t)
        z.text((x + 6, y + 2), f'{t:.2f}s' + (f"   {s['id']} lokal {t - s['start']:.2f}" if s else ''),
               fill=(255, 220, 90), font=klein)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    b.save(ziel, quality=88)
    return ziel


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folge')
    ap.add_argument('zeiten', nargs='*', help='globale Sekunden (oder lokal mit --lokal)')
    ap.add_argument('--szene')
    ap.add_argument('--raster', type=float)
    ap.add_argument('--lokal', action='store_true', help='Zeiten sind lokal zur --szene')
    ap.add_argument('--name')
    ap.add_argument('--gegen', help='Vorbild-Video für Paar-Bilder (hyperframes --against)')
    ap.add_argument('--ohne-lint', action='store_true')
    a = ap.parse_args()

    fo = _bau.folge(a.folge)
    build = fo / 'build'
    if not (build / 'index.html').exists():
        raise SystemExit('FEHLER: build/index.html fehlt. Erst "ms szenen <folge>".')
    szenen = _bau.szenen_lesen(fo)
    dauer = _bau.index_dauer(build) or max(s['start'] + s['dur'] for s in szenen)
    sz = None
    if a.szene:
        sz = next((s for s in szenen if s['id'] == a.szene), None)
        if not sz:
            raise SystemExit(f'FEHLER: Szene {a.szene} nicht in scenes.json ({", ".join(s["id"] for s in szenen)}).')
    zeiten = zeiten_parsen(a.zeiten)
    if a.lokal:
        if not sz:
            raise SystemExit('FEHLER: --lokal braucht --szene.')
        zeiten = [sz['start'] + t for t in zeiten]
    if a.raster or (sz and not zeiten):
        schritt = a.raster or 0.25
        if sz:
            von, bis = sz['start'] + 1 / 30, min(sz['start'] + sz['dur'], dauer) - 1 / 30
        else:
            von, bis = 0.0, dauer - 1 / 30
        zeiten += raster(von, bis, schritt)
    if not zeiten:
        raise SystemExit('FEHLER: keine Zeiten. Beispiele: ms snap <folge> 1.2 3.4 | --szene s2 | --raster 0.5')
    zeiten = sorted({round(min(max(0.0, t), dauer - 1 / 30), 3) for t in zeiten})

    if not a.ohne_lint:
        fehler, warn, text = _bau.lint(build)
        if fehler:
            zeilen = [z for z in text.splitlines() if '✗' in z or 'error' in z.lower()][:12]
            raise SystemExit('ABBRUCH: hyperframes lint meldet Fehler (ein Skriptfehler in EINER Szene legt die ganze Seite lahm):\n  '
                             + '\n  '.join(zeilen))
    name = a.name or (f'{sz["id"]}' if sz else 'snap')
    ordner = fo / 'snapshots' / name
    ordner.mkdir(parents=True, exist_ok=True)
    # hyperframes snapshot entfernt vor dem Schreiben alle .png/.jpg im Zielordner. Den vorigen Kontaktbogen deshalb
    # vorher nach _ueberholt/ legen (überschreibt dort nur den vorvorigen), damit nichts ungefragt verschwindet.
    alte = sorted(ordner.glob('kontaktbogen*.jpg'))
    if alte:
        ablage = ordner / '_ueberholt'
        ablage.mkdir(exist_ok=True)
        for p in alte:
            p.replace(ablage / p.name)
    args = ['snapshot', '--at', ','.join(f'{t:g}' for t in zeiten), '--no-end', '--describe', 'false',
            '--timeout', '120000', '-o', str(ordner)]
    if a.gegen:
        args += ['--against', str(Path(a.gegen).resolve())]
    args.append('.')
    print(f'Rendere {len(zeiten)} Bilder nach {ordner} …', flush=True)
    r = _bau.hf(args, build, nett=True)
    if r.returncode != 0:
        raise SystemExit(f'FEHLER: hyperframes snapshot (Code {r.returncode})\n{_bau.ANSI.sub("", (r.stdout or "") + (r.stderr or ""))[-1500:]}')
    def von_diesem_lauf(p: Path):
        """Zeit aus dem Dateinamen (…-at-1.25s.png), nur wenn sie zu diesem Lauf gehört. Ältere Bilder im selben
        Ordner (andere Zeiten) bleiben liegen, kommen aber nicht in den Bogen."""
        m = re.search(r'-at-([\d.]+)s\.(?:png|jpg)$', p.name)
        if m and any(abs(float(m.group(1)) - z) < 0.002 for z in zeiten):
            return float(m.group(1))
        return None

    bilder = sorted((von_diesem_lauf(p), p) for p in ordner.glob('frame-*-at-*s.png') if von_diesem_lauf(p) is not None)
    if not bilder:
        raise SystemExit(f'FEHLER: hyperframes hat keine Bilder geschrieben. Ausgabe:\n{_bau.ANSI.sub("", r.stdout or "")[-1200:]}')
    boegen = []
    for k in range(0, len(bilder), PRO_BOGEN):
        teil = bilder[k:k + PRO_BOGEN]
        nr = f'_{k // PRO_BOGEN + 1}' if len(bilder) > PRO_BOGEN else ''
        titel = f'{fo.name}  {name}  {teil[0][0]:.2f} bis {teil[-1][0]:.2f} s  ({len(teil)} Bilder)'
        boegen.append(bogen(teil, ordner / f'kontaktbogen{nr}.jpg', szenen, titel))
    paar = [p for p in sorted(ordner.glob('*pair*.jpg')) + sorted(ordner.glob('*against*.jpg')) if von_diesem_lauf(p) is not None]
    paar_boegen = []
    if a.gegen:
        refs = {}
        for p in ordner.glob('ref-*-at-*s.png'):
            t = von_diesem_lauf(p)
            if t is not None:
                refs[round(t, 3)] = p
        paare = [(t, refs.get(round(t, 3)), p) for t, p in bilder]
        for k in range(0, len(paare), PRO_PAARBOGEN):
            teil = paare[k:k + PRO_PAARBOGEN]
            nr = f'_{k // PRO_PAARBOGEN + 1}' if len(paare) > PRO_PAARBOGEN else ''
            titel = f'{fo.name}  {name}  {teil[0][0]:.2f} bis {teil[-1][0]:.2f} s  ({len(teil)} Paare)'
            paar_boegen.append(paarbogen(teil, ordner / f'kontaktbogen_paar{nr}.jpg', szenen, titel))
        if not refs:
            print('HINWEIS: hyperframes hat keine Originalbilder (ref-*.png) geschrieben, im Paar-Bogen fehlt die linke Seite.')
    _ms.log(f'Snapshots {name}: {len(bilder)} Bilder', ziel=_ms.ziel_name(fo))
    print(f'{len(bilder)} Bilder. Kontaktbogen ansehen' + (' (Paar-Bogen zuerst):' if paar_boegen else ':'))
    for b in paar_boegen + boegen:
        print(b)
    if paar:
        print(f'Einzelpaare von hyperframes: {len(paar)} × pair-*.jpg in {ordner}')
    if alte:
        print(f'Voriger Bogen zum Vergleich: {ordner / "_ueberholt" / alte[0].name}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
