"""Stil-Skill eines Kanals: die Bauanleitung, mit der jede neue Sitzung Szenen genau in diesem Stil baut
  ms stil <kanal> anlegen [--neu]      <Arbeitsordner>/.claude/skills/stil-<kanal>/SKILL.md aus Pilot, Kit und Analyse anlegen:
                                       Messbares füllt das Werkzeug selbst (Zahlen, Palette, Captions, Bausteine, Pilot-Szenen),
                                       den Rest markiert es mit AUSFÜLLEN für die Regie. --neu: vorhandene Fassung nach _ueberholt/
  ms stil <kanal> pruefen [--json]     Gate: nichts mehr AUSFÜLLEN, genug Szenentypen, Bausteine mit Aufruf, Zahlen, Kriterien,
                                       Beispiele; und gegenüber der letzten Sicherung ist nichts verschwunden. Code 1 bei Mängeln
  ms stil <kanal> sichern              Sicherung vor einer Änderung (_ueberholt/SKILL-<zeit>.md), pruefen vergleicht damit
  ms stil <kanal> pfad                 Pfad des Skills ausgeben
Sebastian 30.10.2026: Nach dem Pilot entsteht je Kanal ein Skill, der „PERFEKT beschreibt, auch für alle neuen Sessions, wie man
so Animationen standardisiert BIS AUFS Detail baut“. Er liegt im Arbeitsordner unter .claude/skills/, damit Claude Code ihn in
jeder Sitzung dort als Projekt-Skill kennt; Regie und Bauer lesen ihn zusätzlich direkt über den Pfad."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics
import sys
from datetime import datetime
from pathlib import Path

import _ms

AUSFUELLEN = 'AUSFÜLLEN'
PFLICHT = ['Kurzfassung', 'Grundlagen in Zahlen', 'Farben und Schrift', 'Szenentypen', 'Bausteine', 'Bewegung',
           'Übergänge', 'Captions', 'Ton', 'Bewegungsliste', 'Abnahme', 'Beispiele aus dem Pilot', 'So baust du eine neue Szene',
           'Pflege']
MINDEST = {'szenentypen': 4, 'bausteine': 5, 'zahlen_bewegung': 6, 'abnahme': 8, 'beispiele': 3}


def kanal_ordner(kanal: str) -> Path:
    d = _ms.arbeit() / 'kanaele' / kanal
    if not (d / 'STATUS.json').is_file():
        raise SystemExit(f'FEHLER: Kanal {kanal} gibt es nicht (ms status --alle).')
    return d


def pfad(kanal: str) -> Path:
    return _ms.arbeit() / '.claude' / 'skills' / f'stil-{kanal}' / 'SKILL.md'


# ---------------------------------------------------------------- Messbares sammeln

def _pilot(kst: dict) -> Path | None:
    p = kst.get('pilot')
    d = _ms.arbeit() / p if p else None
    return d if d and (d / 'STATUS.json').is_file() else None


def _fmt(x: float) -> str:
    return f'{x:.2f}'.replace('.', ',')


def _szenen_zahlen(szenen: list[dict]) -> list[str]:
    dauern = [float(s['dur']) for s in szenen if s.get('id') != 'cap' and s.get('dur')]
    if not dauern:
        return [f'- Szenenlängen: {AUSFUELLEN} (kein scenes.json im Pilot)']
    gesamt = max(float(s['start']) + float(s['dur']) for s in szenen)
    arten = {}
    for s in szenen:
        if s.get('id') != 'cap':
            arten[s.get('art', '?')] = arten.get(s.get('art', '?'), 0) + float(s.get('dur') or 0)
    summe = sum(arten.values()) or 1
    return [f'- Pilot: {len(dauern)} Szenen in {_fmt(gesamt)} s, Szenenlänge min {_fmt(min(dauern))} s, Median {_fmt(statistics.median(dauern))} s, '
            f'max {_fmt(max(dauern))} s (Overlay-Szenen wie Captions nicht mitgezählt).',
            '- Spuren nach Szenendauer: ' + ', '.join(f'{k} {v / summe * 100:.0f} %' for k, v in sorted(arten.items(), key=lambda kv: -kv[1]))]


def _analyse_zahlen(kdir: Path, vorlage_id: str | None) -> tuple[list[str], list[str]]:
    """(Zahlen-Zeilen, Palette-Zeilen) aus analyse/<id>/analyse.json des Pilot-Videos (sonst des ersten)."""
    kand = sorted((kdir / 'analyse').glob('*/analyse.json'))
    datei = next((k for k in kand if vorlage_id and k.parent.name == vorlage_id), kand[0] if kand else None)
    if not datei:
        return [f'- Schnittrhythmus des Vorbilds: {AUSFUELLEN} (keine analyse.json)'], [f'| {AUSFUELLEN} | | |']
    a = _ms.json_lesen(datei, {}) or {}
    z = []
    r = a.get('rhythmus') or {}
    if r:
        z.append('- Vorbild (' + datei.parent.name + '): ' + ', '.join(f'{k} {v}' for k, v in r.items() if isinstance(v, (int, float, str)))[:400])
    pal = [p for p in (a.get('palette') or []) if isinstance(p, dict) and p.get('hex')]
    pz = [f'| `{p["hex"]}` | {p.get("anteil", 0) * 100:.0f} % der Fläche | {AUSFUELLEN}: Rolle (Hintergrund, Fläche, Akzent, Text, Linie) |' for p in pal[:8]]
    return z or [f'- Schnittrhythmus des Vorbilds: {AUSFUELLEN}'], pz or [f'| {AUSFUELLEN} | | |']


def _gsap_zahlen(pilot: Path | None) -> list[str]:
    if not pilot:
        return [f'- {AUSFUELLEN}: kein Pilot gefunden']
    eases, dauern, kamera = {}, [], []
    for f in sorted((pilot / 'build' / 'compositions').glob('*.html')):
        t = f.read_text(encoding='utf-8', errors='ignore')
        for e in re.findall(r'ease\s*:\s*["\']([^"\']+)["\']', t):
            eases[e] = eases.get(e, 0) + 1
        dauern += [float(x) for x in re.findall(r'duration\s*:\s*([0-9]*\.?[0-9]+)', t)]
        kamera += [f'{f.stem}: {m.strip()[:90]}' for m in re.findall(r'(MS2D\.(?:kameraPunch|kameraLeben|wackeln)\([^)]*\))', t)]
    z = []
    if eases:
        z.append('- Easing im Pilot (Anzahl): ' + ', '.join(f'`{e}` {n}' for e, n in sorted(eases.items(), key=lambda kv: -kv[1])[:8]))
    if dauern:
        z.append(f'- Tween-Dauern im Pilot: {len(dauern)} Stück, Median {_fmt(statistics.median(dauern))} s, '
                 f'kürzeste {_fmt(min(dauern))} s, längste {_fmt(max(dauern))} s')
    z += [f'- Kamera im Pilot: `{k}`' for k in kamera[:6]]
    return z or [f'- {AUSFUELLEN}: im Pilot keine Easing- oder Dauer-Angaben gefunden, aus den Kompositionen ablesen']


def _pilot_funktionen(pilot: Path | None) -> list[str]:
    """Eigene Funktionen in den Pilot-Kompositionen: genau die Bausteine, die den Stil tragen (Kit-Kandidaten)."""
    if not pilot:
        return []
    aus, gesehen = [], set()
    for f in sorted((pilot / 'build' / 'compositions').glob('*.html')):
        t = f.read_text(encoding='utf-8', errors='ignore')
        for n, args in re.findall(r'function\s+([A-Za-z_]\w*)\s*\(([^)]*)\)', t):
            if n in gesehen or n in ('build', 'aufbau', 'zustand', 'kamera'):
                continue
            gesehen.add(n)
            aus.append(f'| `{n}({args.strip()[:60]})` | Pilot `{f.name}` | eigene Funktion im Pilot | {AUSFUELLEN}: Zweck, Aufruf mit Werten aus dem Pilot, ins Kit übernehmen? |')
    return aus[:30]


def _bausteine(kdir: Path, pilot: Path | None = None) -> list[str]:
    """Funktionen aus kit/lib wie in KATALOG.md (ms kit … katalog), mit Aufruf. Was der Pilot benutzt, braucht eine Angabe,
    wie es im Stil eingesetzt wird; der Rest ist nur Liste."""
    text_pilot = ''
    if pilot:
        text_pilot = '\n'.join(f.read_text(encoding='utf-8', errors='ignore') for f in (pilot / 'build' / 'compositions').glob('*.html'))
    funktionen = []
    try:
        import kit
        for datei in sorted((kdir / 'kit' / 'lib').glob('*.js')):
            funktionen += [(datei.name, f['name'], f['sig'], f['doku']) for f in kit.funktionen(datei)]
    except Exception:  # Kit nicht lesbar: Liste aus KATALOG.md
        funktionen = []
    eigene = _pilot_funktionen(pilot)
    if not funktionen:
        kat = kdir / 'kit' / 'KATALOG.md'
        zeilen = [z for z in (kat.read_text(encoding='utf-8').splitlines() if kat.exists() else []) if z.startswith('| `')]
        return eigene + [z + f' {AUSFUELLEN}: wann einsetzen |' for z in zeilen[:40]] or [f'| {AUSFUELLEN} | | | |']
    def spalte(n):
        kurz = n.split('.')[-1]
        return f'im Pilot benutzt. {AUSFUELLEN}: wie (Werte aus dem Pilot)' if re.search(r'\b' + re.escape(kurz) + r'\s*\(', text_pilot) \
            else 'im Pilot nicht benutzt'
    return eigene + [f'| `{n}{sig}` | {datei} | {_erste_zeile(kom)} | {spalte(n)} |' for datei, n, sig, kom in funktionen[:60]]


def _erste_zeile(kom: str) -> str:
    z = [x.strip(' /*') for x in str(kom or '').splitlines() if x.strip(' /*')]
    return (z[0] if z else '').replace('|', '/')[:90]


def _captions(kdir: Path) -> list[str]:
    c = _ms.json_lesen(kdir / 'kit' / 'captions.json', {}) or {}
    if not c:
        return [f'- {AUSFUELLEN}: kit/captions.json fehlt']
    if c.get('an') is False:
        return ['- `kit/captions.json`: an = false. Captions laufen nicht über `ms szenen`, sondern als eigene Overlay-Komposition '
                f'(im Pilot z. B. `cap.html`). {AUSFUELLEN}: Schrift, Größe px, Farben, Lage y, Wörter je Gruppe, Erscheinen, aus dem Overlay.']
    felder = ['schrift', 'gewicht', 'groesse', 'versalien', 'farbe', 'kontur', 'kontur_breite', 'hintergrund', 'hervorhebung', 'y',
              'max_woerter', 'max_zeichen', 'erscheinen', 'animation']
    return [f'- `{k}`: {json.dumps(c.get(k), ensure_ascii=False)}' for k in felder if k in c]


def _ton(kdir: Path) -> list[str]:
    t = _ms.json_lesen(kdir / 'kit' / 'ton-rezept.json', {}) or {}
    if not t:
        return [f'- {AUSFUELLEN}: kit/ton-rezept.json fehlt (Skill motion-ton-mix)']
    return [f'- `{k}`: {json.dumps(v, ensure_ascii=False)[:200]}' for k, v in t.items() if not str(k).startswith('_')]


def _beispiele(pilot: Path | None, szenen: list[dict]) -> list[str]:
    if not pilot:
        return [f'| {AUSFUELLEN} | | | |']
    rel = _ms.ziel_name(pilot)
    qa = sorted((pilot / 'out').glob('qa_*'))
    qa_name = qa[-1].name if qa else 'qa_<name>'
    return [f'| {s["id"]} | {_fmt(float(s["start"]))} bis {_fmt(float(s["start"]) + float(s["dur"]))} s | `{rel}/build/compositions/{s["id"]}.html` '
            f'(Bogen `{rel}/out/{qa_name}/{s["id"]}.jpg`) | {AUSFUELLEN}: was die Szene zeigt und welcher Szenentyp |' for s in szenen]


def anlegen(kanal: str, neu: bool = False) -> Path:
    kdir = kanal_ordner(kanal)
    ziel = pfad(kanal)
    if ziel.exists() and not neu:
        raise SystemExit(f'FEHLER: {ziel} gibt es schon. Ändern statt neu anlegen (vorher ms stil {kanal} sichern), '
                         f'oder --neu (alte Fassung wandert nach _ueberholt/).')
    if ziel.exists():
        sichern(kanal)
    kst = _ms.status_lesen(kdir)
    pilot = _pilot(kst)
    pst = _ms.status_lesen(pilot) if pilot else {}
    szenen = _ms.json_lesen(pilot / 'build' / 'scenes.json', []) if pilot else []
    vorlage_id = (pst.get('vorlage') or {}).get('id')
    zahlen_a, palette = _analyse_zahlen(kdir, vorlage_id)
    mw = kst.get('messwerte') or {}
    a = _ms.arbeit()
    text = f'''---
name: stil-{kanal}
description: "Stil des Kanals {kanal} (Vorbild {kst.get('vorbild') or '?'}) bis ins Detail: Szenentypen, Bausteine mit Aufruf, Zeiten, Easing und Kamera in Zahlen, Farben und Schrift als Tokens, Übergänge, Captions, Ton, Abnahme-Kriterien mit Schwellen, Beispiele aus dem Pilot. Laden vor JEDER Folge, jedem Storyboard und jeder Szene für Kanal {kanal}, bei „Stil {kanal}“, „Szene im Stil“, „baue Szene“, „Brief an den Bauer“."
---

# Stil {kanal}

Diese Datei ist die Bauanleitung des Kanals. Eine frische Sitzung ohne weiteren Kontext soll damit eine Szene bauen können,
die neben dem Pilot nicht auffällt. Inhalt kommt aus der Idee der Folge, die FORM kommt von hier.
Kanal: `{_ms.ziel_name(kdir)}` · Pilot: `{_ms.ziel_name(pilot) if pilot else AUSFUELLEN}` · Messwerte Pilot: ΔE {mw.get('delta_e', '?')}, SSIM {mw.get('ssim', '?')}
Grundlage: `BIBEL.md`, `REGELN.md`, `kit/KATALOG.md`, `SKRIPT-BAUKASTEN.md` im Kanalordner. Bei Widerspruch gilt die neueste Regel in REGELN.md.

## Kurzfassung

{AUSFUELLEN}: Fünf Sätze, die den Stil so beschreiben, dass man ihn am ersten Bild erkennt (Bildwelt, Licht, Formensprache, Tempo, Ton).

## Grundlagen in Zahlen

- Format 1080 × 1920, 30 Bilder/s. Wichtiges oberhalb der Caption-Zone.
{chr(10).join(_szenen_zahlen(szenen))}
{chr(10).join(zahlen_a)}
- {AUSFUELLEN}: Sprechtempo in Wörtern/s und Länge einer Folge in s (aus SKRIPT-BAUKASTEN.md bzw. ton-rezept.json)

## Farben und Schrift

Tokens: Jede Szene nimmt Farben nur aus dieser Tabelle, mit genau diesem Hex-Wert.

| Token | Anteil im Vorbild | Rolle |
|---|---|---|
{chr(10).join(palette)}

- Schrift Überschriften: {AUSFUELLEN} (Familie, Gewicht, Größe px, Laufweite, Versalien ja/nein)
- Schrift im Bild (Labels, Zahlen): {AUSFUELLEN}

## Szenentypen

{AUSFUELLEN}: Mindestens vier Typen, die im Pilot vorkommen, je Typ ein Abschnitt `### <Name>` mit: wann (welche Aussage),
Ebenen von außen nach innen, Bausteine mit Aufruf, Zeiten (Auftauchen, Halten, Abgang in s), Kamera, Beispiel (Datei + Zeit).

## Bausteine

Aufrufe aus dem Kit (`kit/lib`, Liste in `kit/KATALOG.md`). Fehlt einer: in der Szene bauen und als Kit-Kandidat melden.

| Aufruf | Datei | Zweck | Im Stil |
|---|---|---|---|
{chr(10).join(_bausteine(kdir, pilot))}

## Bewegung

Zeiten, Easing und Kamera in Zahlen. Aus den Pilot-Kompositionen gemessen:
{chr(10).join(_gsap_zahlen(pilot))}

{AUSFUELLEN}: Regeln daraus, z. B. „Auftauchen 0,30 s power2.out aus 85 % Größe“, „Kamera driftet 2 % je 4 s“, „Punch 1,08 in 0,12 s auf dem Schlüsselwort“.

## Übergänge

{AUSFUELLEN}: Welche Übergänge der Kanal nutzt (harter Schnitt, Wisch, Zoom durch ein Objekt …), Dauer in s, Easing, wie oft je Folge.

## Captions

{chr(10).join(_captions(kdir))}

## Ton

{chr(10).join(_ton(kdir))}
- {AUSFUELLEN}: Musik ja/nein und Abstand zur Stimme in dB, Effekt-Familie je Aktion (Auftauchen, Treffer, Zahl, Übergang)

## Bewegungsliste

{AUSFUELLEN}: Muster aus der Bewegungsliste des Pilots (NACHBAU.md bzw. ANALYSE.md): wie Elemente auftauchen und verschwinden,
was sich dauerhaft bewegt, welche Details den Look tragen. Jede Zeile mit Pilot-Zeit.

## Abnahme

Prüfbare Kriterien mit Schwelle. Bauer prüfen ihre Szene dagegen, der Prüfer jede Folge.

| Kriterium | Schwelle | Wie prüfen |
|---|---|---|
| Farben nur aus den Tokens | jede Fläche ein Token-Hex | Kontaktbogen gegen Tabelle oben |
| Stillstand | höchstens 1,5 s ohne neue Bewegung | Szenenbogen (5 Bilder/s) |
| Aktion auf dem Wort | Abweichung höchstens 0,10 s | `ms snap --lokal` an der Wortzeit |
| Lautheit | −14 LUFS ±0,5 im Mix | `build/assets/audio/mix_bericht.json` |
| Captions | Lage und Stil wie oben, kein Wort falsch | Bogen, Captions-Zeile |
| {AUSFUELLEN} | | |
| {AUSFUELLEN} | | |
| {AUSFUELLEN} | | |

## Beispiele aus dem Pilot

| Szene | Zeit | Datei | Was sie zeigt |
|---|---|---|---|
{chr(10).join(_beispiele(pilot, szenen))}

## So baust du eine neue Szene

1. Brief und Storyboard-Zeile lesen: Aussage, Wortzeiten (lokal = global − Szenenstart), Szenentyp.
2. Den passenden Szenentyp oben wählen und die Beispieldatei aus dem Pilot mit Read öffnen.
3. Gerüst aus Skill motion-szene-2d bzw. motion-szene-3d-web, Ebenen wie im Szenentyp.
4. Farben nur aus den Tokens, Schrift wie oben, Bausteine aus der Tabelle mit genau diesem Aufruf.
5. Zeiten und Easing nach „Bewegung“, eine Aktion pro Aussage auf ihrem Wort, Übergang wie unter „Übergänge“.
6. `ms snap … --szene <id> --raster 0.25` und den Bogen gegen „Abnahme“ prüfen, höchstens zwei Runden.
7. Neue Lösungen, die wiederkommen werden, als Kit-Kandidat und hier unter „Pflege“ melden.

## Pflege

Nach jeder Folge ergänzt die Regie hier, was neu dazukam (Szenentyp, Baustein, Regel), mit Datum und Folge. Nichts löschen:
Überholtes durchstreichen und begründen. Vorher `ms stil {kanal} sichern`, danach `ms stil {kanal} pruefen`.

- {datetime.now():%d.%m.%Y}: angelegt aus Pilot `{_ms.ziel_name(pilot) if pilot else '?'}` (ms stil anlegen)
'''
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(text, encoding='utf-8')
    _ms.log(f'Stil-Skill stil-{kanal} angelegt, Lücken mit {AUSFUELLEN} markiert', ziel=f'kanal:{kanal}', art='info')
    return ziel



def sichern(kanal: str) -> Path | None:
    p = pfad(kanal)
    if not p.exists():
        return None
    ab = p.parent / '_ueberholt'
    ab.mkdir(exist_ok=True)
    ziel = ab / f'SKILL-{datetime.now():%Y%m%d-%H%M%S}.md'
    shutil.copyfile(p, ziel)
    return ziel


def _abschnitte(text: str) -> dict:
    teile, aktuell = {}, None
    for z in text.splitlines():
        if z.startswith('## '):
            aktuell = z[3:].strip()
            teile[aktuell] = []
        elif aktuell:
            teile[aktuell].append(z)
    return teile


def pruefen(kanal: str) -> dict:
    p = pfad(kanal)
    if not p.exists():
        return {'ok': False, 'maengel': [f'{p} fehlt: ms stil {kanal} anlegen'], 'pfad': str(p)}
    text = p.read_text(encoding='utf-8')
    ab = _abschnitte(text)
    maengel = []
    rest = text.count(AUSFUELLEN)
    if rest:
        maengel.append(f'{rest} Stellen noch {AUSFUELLEN}')
    for name in PFLICHT:
        if not any(k.startswith(name) for k in ab):
            maengel.append(f'Abschnitt „{name}“ fehlt')

    def teil(name):
        return next((v for k, v in ab.items() if k.startswith(name)), [])
    zahlen = {
        'szenentypen': sum(1 for z in teil('Szenentypen') if z.startswith('### ')),
        'bausteine': sum(1 for z in teil('Bausteine') if re.match(r'^\|\s*`[^`]*\(', z)),
        'zahlen_bewegung': len(re.findall(r'\d+[,.]?\d*\s*(s|%|px|°)', '\n'.join(teil('Bewegung')))),
        'abnahme': sum(1 for z in teil('Abnahme') if z.startswith('|') and not z.startswith('|---') and not z.startswith('| Kriterium')
                       and re.search(r'\d', z)),
        'beispiele': sum(1 for z in teil('Beispiele') if re.search(r'\.html', z) and re.search(r'\d+[,.]\d+', z)),
    }
    for k, n in zahlen.items():
        if n < MINDEST[k]:
            maengel.append(f'{k}: {n} statt mindestens {MINDEST[k]}')
    vorher = sorted((p.parent / '_ueberholt').glob('SKILL-*.md')) if (p.parent / '_ueberholt').is_dir() else []
    verloren = []
    if vorher:
        alt = vorher[-1].read_text(encoding='utf-8')
        neu_text = text
        for z in alt.splitlines():
            if (z.startswith('### ') or re.match(r'^\|\s*`', z) or z.startswith('## ')) and z.strip() not in neu_text:
                kern = z.split('|')[1].strip() if z.startswith('|') else z
                if kern not in neu_text:
                    verloren.append(z.strip()[:100])
        if verloren:
            maengel.append(f'{len(verloren)} Einträge aus der letzten Sicherung fehlen (nichts darf verschwinden): ' + '; '.join(verloren[:5]))
    return {'ok': not maengel, 'maengel': maengel, 'zahlen': zahlen, 'pfad': str(p), 'verglichen_mit': str(vorher[-1]) if vorher else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('kanal')
    ap.add_argument('was', nargs='?', default='pruefen', choices=['anlegen', 'pruefen', 'sichern', 'pfad'])
    ap.add_argument('--neu', action='store_true')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    if a.was == 'pfad':
        print(pfad(a.kanal))
        return 0
    if a.was == 'anlegen':
        p = anlegen(a.kanal, a.neu)
        e = pruefen(a.kanal)
        print(f'Angelegt: {p}\nNoch offen: {len(e["maengel"])} Punkte (zuerst alle {AUSFUELLEN} füllen, dann ms stil {a.kanal} pruefen).')
        return 0
    if a.was == 'sichern':
        z = sichern(a.kanal)
        print(f'Gesichert: {z}' if z else 'Noch kein Stil-Skill, nichts zu sichern.')
        return 0
    e = pruefen(a.kanal)
    if a.json:
        print(json.dumps(e, ensure_ascii=False, indent=1))
    else:
        print(('OK: ' if e['ok'] else 'NICHT FERTIG: ') + e['pfad'])
        if e.get('zahlen'):
            print('  ' + ', '.join(f'{k} {v}' for k, v in e['zahlen'].items()))
        for m in e['maengel']:
            print(f'  - {m}')
    return 0 if e['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
