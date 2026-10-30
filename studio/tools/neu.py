"""Neue Folge oder neuen Kanal im Arbeitsordner anlegen (Ordner, STATUS.json, Startdateien).
  ms neu kanal <slug> --vorbild "@handle oder URL" [--titel "…"]
  ms neu folge <slug> --kanal <slug> --idee "<Idee aus IDEEN.md>" [--vorlage <id>] [--titel "…"]   eigene Folge (Standard)
  ms neu folge <slug> --kanal <slug> --pilot --vorlage <id>           Pilot: 1:1-Nachbau zum Lernen (wird nie gepostet)
  ms neu folge <slug> --kanal <slug> --kopie --vorlage <id>           Kopie eines fremden Videos (motion-nachbau, wird nie
                                                                      automatisch gepostet)
  ms neu folge <slug> --kanal <slug> --stiltest --vorlage <id>        Stil-Test (motion-kanal-lernen Schritt 9): wie ein Pilot
                                                                      mit Originalton, ändert aber den Kanal-Status nicht
Ein Kanal bekommt die Start-Bausteine (kit/lib, kit/beispiele, kit/captions.json) und gleich kit/KATALOG.md (ms kit … katalog).
Eine Folge bekommt den Ordner folgen/<JJJJ-MM-TT>-<slug>/ mit voice/, build/ (HyperFrames-Projekt), out/.
Liegt im Kanal ein Kit (kanaele/<k>/kit/lib, fonts, tex), wird es nach build/assets/ kopiert.
--vorlage übernimmt Video- und Transkript-Pfad aus dem Register: die Vorlage vorher laden (ms laden <id> --kanal <k>).
  Bei einer eigenen Folge ist sie nur der Bauplan (Form, Länge, Tempo, Hook-Formel), der Inhalt kommt aus der Idee.
--idee macht die Folge zur eigenen Folge (STATUS quelle "eigen", nur solche postet Motion-Studio) und hakt die passende
  offene Idee in kanaele/<k>/IDEEN.md ab. Die Bau-Sitzung des Autopiloten steht in STATUS "sitzung" (Umgebung MS_SITZUNG).
--pilot trägt den Ordner im Kanal-Status ein (Feld pilot) und setzt dort die Phase pilot, solange der Kanal noch davor steht."""
import argparse
import os
import re
import shutil
import sys
from datetime import date

import _ms


def slug_ok(s):
    s = re.sub(r'[^a-z0-9-]+', '-', s.lower()).strip('-')
    if not s:
        raise SystemExit('FEHLER: Slug leer. Nur a-z, 0-9 und Bindestrich.')
    return s


def neu_kanal(a):
    slug = slug_ok(a.slug)
    d = _ms.arbeit() / 'kanaele' / slug
    if (d / 'STATUS.json').exists():
        raise SystemExit(f'Kanal {slug} gibt es schon: {d}')
    for teil in ('vorbild', 'analyse', 'kit/lib', 'kit/fonts', 'kit/tex', 'kit/beispiele'):
        (d / teil).mkdir(parents=True, exist_ok=True)
    start = _ms.HEIM / 'vorlagen' / 'kit-start'            # Start-Bausteine (2D/3D-Hilfen, Beispiele, Caption-Stil)
    if start.exists():
        for teil in ('lib', 'beispiele', 'fonts', 'tex'):
            if (start / teil).exists():
                shutil.copytree(start / teil, d / 'kit' / teil, dirs_exist_ok=True)
        if (start / 'captions.json').exists():
            shutil.copyfile(start / 'captions.json', d / 'kit' / 'captions.json')
    _ms.json_schreiben(d / 'STATUS.json', {
        'id': slug, 'art': 'kanal', 'titel': a.titel or slug, 'vorbild': a.vorbild or '', 'phase': None, 'phasen': {},
        'pilot': None, 'messwerte': {}, 'erstellt': _ms.jetzt(), 'aktualisiert': _ms.jetzt()})
    _ms.log(f'Kanal {slug} angelegt (Vorbild {a.vorbild or "?"})', ziel=f'kanaele/{slug}', art='info')
    import kit                                              # KATALOG.md der Start-Bausteine gleich mit anlegen
    kit.katalog(d)
    import ideen                                            # Ideenliste mit Schema-Abschnitt (Pack 4 Prompt 2)
    ideen.anlegen(slug)
    print(d)


def neu_folge(a):
    slug = slug_ok(a.slug)
    if not a.kanal:
        raise SystemExit('FEHLER: --kanal fehlt (welcher gelernte Stil?).')
    if sum(bool(x) for x in (a.pilot, a.kopie, a.idee, a.stiltest)) != 1:
        raise SystemExit('FEHLER: Genau eins davon: --idee "<Idee>" (eigene Folge), --pilot (Nachbau zum Lernen), --kopie oder --stiltest.')
    kanal = _ms.arbeit() / 'kanaele' / a.kanal
    if not (kanal / 'STATUS.json').exists():
        raise SystemExit(f'FEHLER: Kanal {a.kanal} gibt es nicht. Erst "ms neu kanal {a.kanal}".')
    fid = f'{date.today().isoformat()}-{slug}'
    d = _ms.arbeit() / 'folgen' / fid
    if (d / 'STATUS.json').exists():
        raise SystemExit(f'Folge {fid} gibt es schon: {d}')
    for teil in ('voice', 'build/compositions', 'build/assets/audio', 'build/assets/lib', 'build/assets/fonts',
                 'build/assets/tex', 'build/assets/video', 'out', 'snapshots'):
        (d / teil).mkdir(parents=True, exist_ok=True)
    for teil in ('lib', 'fonts', 'tex'):
        quelle = kanal / 'kit' / teil
        if quelle.exists():
            shutil.copytree(quelle, d / 'build' / 'assets' / teil, dirs_exist_ok=True)
    vorlage = {}
    if a.vorlage:
        reg = _ms.json_lesen(_ms.arbeit() / 'vorlagen' / 'register.json', {}) or {}
        eintrag = next((e for e in reg.get('eintraege', []) if e.get('id') == a.vorlage), None)
        if not eintrag:
            raise SystemExit(f'FEHLER: Vorlage {a.vorlage} nicht im Register (ms vorlagen liste).')
        vorlage = {k: eintrag.get(k) for k in ('id', 'url', 'creator', 'views', 'datum', 'video', 'transkript')}
        if not vorlage.get('video') or not vorlage.get('transkript'):
            print(f'HINWEIS: Vorlage {a.vorlage} ist noch nicht geladen (Video oder Transkript fehlt im Register). '
                  f'Jetzt nachholen: ms laden {a.vorlage} --kanal {a.kanal} (Skript, Tempo und Pilot brauchen beides).')
    if vorlage and a.idee:
        vorlage['rolle'] = 'bauplan'
    st = {'id': fid, 'art': 'pilot' if (a.pilot or a.stiltest) else 'kopie' if a.kopie else 'folge', 'titel': a.titel or slug, 'kanal': a.kanal,
          'vorlage': vorlage, 'phase': None, 'phasen': {}, 'kosten': [], 'erstellt': _ms.jetzt(), 'aktualisiert': _ms.jetzt()}
    if a.idee:
        st.update(quelle='eigen', idee=' '.join(a.idee.split()))
    if a.stiltest:
        st['test'] = 'stil'
    if os.environ.get('MS_SITZUNG'):
        st['sitzung'] = os.environ['MS_SITZUNG']
    _ms.json_schreiben(d / 'STATUS.json', st)
    kopf = (f'Idee: {st["idee"]}\nBauplan (nur Form, Länge, Tempo, Hook-Formel): {vorlage.get("url", "-")}' if a.idee
            else f'Vorlage: {vorlage.get("url", "-")}')
    (d / 'SKRIPT.md').write_text(f'# {a.titel or slug}\n\n{kopf}\n\n', encoding='utf-8')
    if a.idee:
        import ideen
        try:
            ideen.nutzen(a.kanal, a.idee, fid)
        except SystemExit:
            pass   # Idee stand nicht in der Liste (z. B. direkt vom Nutzer genannt): Folge trotzdem anlegen
    if a.pilot:
        phase = _ms.status_lesen(kanal).get('phase')
        davor = phase not in _ms.KANAL_PHASEN or _ms.KANAL_PHASEN.index(phase) < _ms.KANAL_PHASEN.index('pilot')
        _ms.status_setzen(kanal, 'pilot' if davor else None, f'Pilot {fid} angelegt' if davor else None, pilot=f'folgen/{fid}')
    art = 'Pilot' if a.pilot else 'Stil-Test' if a.stiltest else 'Kopie' if a.kopie else 'eigene Folge'
    _ms.log(f'Folge {fid} angelegt ({art}, Kanal {a.kanal})', ziel=f'folgen/{fid}')
    print(d)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('was', choices=['kanal', 'folge'])
    ap.add_argument('slug')
    ap.add_argument('--vorbild')
    ap.add_argument('--kanal')
    ap.add_argument('--vorlage')
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--kopie', action='store_true')
    ap.add_argument('--stiltest', action='store_true')
    ap.add_argument('--idee')
    ap.add_argument('--titel')
    a = ap.parse_args()
    (neu_kanal if a.was == 'kanal' else neu_folge)(a)


if __name__ == '__main__':
    sys.exit(main())
