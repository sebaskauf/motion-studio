"""HyperFrames-Projekt einer Folge zusammenbauen (index.html, Captions, Ton) und Szenen-Abdeckung prüfen.
  ms szenen <folge>                    schreibt build/index.html + build/compositions/captions.html, prüft danach
  ms szenen <folge> --plan             dasselbe vor dem Start der Bauer: Platzhalter zählen noch nicht als Fehler
  ms szenen <folge> --check            nur prüfen, schreibt nichts (Code 1 bei Fehler-Befund, Platzhalter = noch nicht gebaut)
  ms szenen <folge> --check --plan     nur den Zeitplan prüfen (Storyboard-Gate, Kompositionen dürfen noch fehlen)
  ms szenen <folge> --check --lint --nur s2,s4   Selbstprüfung eines Bauers: nur seine Szenen + hyperframes lint
  ms szenen <folge> --lint             zusätzlich hyperframes lint im build-Ordner (Fehler = Befund)
  ms szenen <folge> --ohne-captions    ohne Untertitel bauen
  ms szenen <folge> --auslauf 0.6      Sekunden Bild nach dem Stimm-Ende. Standard: wie beim letzten Bau (steht als
                                       <!-- ms-auslauf X --> in index.html, ms render und --check übernehmen ihn), sonst 0,47.
                                       Exakter Ausschnitt (Pilot, Stimme genau 10,0 s): --auslauf 0 ergibt 10,00 s.
Beispiel: ms szenen 2026-10-20-probe && ms snap 2026-10-20-probe --raster 0.5

Was geschrieben wird
  build/index.html                 Wurzel: Ton-Spur (Track 20), jede Szene als Sub-Komposition, Captions (Track 10)
  build/compositions/captions.html Untertitel im Kanal-Stil (kanaele/<k>/kit/captions.json, sonst Standard)
  build/hyperframes.json           nur falls es fehlt
  build/compositions/<id>.html     nur falls sie fehlt: neutraler Platzhalter (richtige Dauer, data-platzhalter="1"),
                                   damit index.html, lint und ms snap schon vor dem Bau laufen. Vorhandene Kompositionen
                                   werden nie überschrieben. Der Bauer ersetzt den Platzhalter komplett (Read, dann Write).
  Ton: build/assets/audio/mix.wav, wenn da (Teil Ton), sonst die Stimme (kopiert nach build/assets/audio/stimme.<ext>)
  Klassische Bibliotheken (erste Zeile enthält "ms-global", z. B. assets/lib/ms2d.js) bindet index.html im Kopf ein.
  three.js: Import-Map "three" → assets/lib/three/three.module.js, falls vorhanden, sonst jsDelivr three@0.181.2.

Prüfungen (auch ohne --check nach jedem Schreiben)
  Lücke: weniger als 0,02 s Überlappung zur vorigen Abdeckung = Schwarzbild (Soll: Start = Ende − 0,06)
  Erste Szene startet bei 0, letzte endet frühestens bei der Gesamtdauer (= Stimm-Ende + Auslauf)
  compositions/<id>.html vorhanden und kein Platzhalter mehr (sonst „noch nicht gebaut“, außer mit --plan),
  data-duration am Wurzel-Element = scenes.json-Dauer (±0,005), Timeline registriert
  Captions: Wortzeiten vorhanden. Gruppen enden spätestens am Videoende (werden gekappt, kein Fehler). Wörter, die
    erst nach dem Ende beginnen, fallen weg (Fehler, wenn deutlich nach dem Ende: Wortzeiten zur falschen Stimme?)

Captions abschalten
  ganz: kit/captions.json "an": false oder --ohne-captions
  je Szene: in scenes.json "captions": false. Wörter, die in dieser Szene beginnen, erscheinen nicht, eine laufende
    Gruppe endet beim Szenenstart (Pilot: Titelkarte oder Shot ohne Untertitel im Original). Zählt die Szene, die zu
    dem Zeitpunkt oben liegt (späterer Start, bei Gleichstand höherer track).

Formate (Vertrag zwischen Storyboard, Stimme, Bauern)
  build/scenes.json  [{"id": "s1", "start": 0.0, "dur": 4.2, "track": 1, "art": "2d|3d-web|blender", "inhalt": "…"}, …]
      Szenen überlappen 0,06 s. track: höhere Zahl liegt oben. Üblich 3D abwechselnd 1/2, 2D 3 (Captions 10, Ton 20 fest).
      Optional "captions": false (siehe oben).
  voice/woerter.json [{"w": "Wort", "s": 1.23, "e": 1.51}, …]   (auch {"woerter": [...]} wie aus _ms.transkribiere)
      w = Anzeigeschreibweise (so steht es in der Caption), s/e = Sekunden ab Folgenbeginn, aufsteigend.
  build/captions.json (optional, schreibt ms woerter; sonst gruppiert dieses Werkzeug selbst nach max_woerter/max_zeichen/Pausen)
      [{"text": "DAS IST NEU", "s": 0.10, "e": 0.92, "woerter": [{"w": "DAS", "s": 0.10, "e": 0.30}, …]}, …]
      Von Hand (Pilot: Gruppen wie im Original): je Gruppe zusätzlich "hand": true, dann überschreibt ms woerter die Datei nicht.
  Stimme: voice/stimme.wav (sonst stimme_fit.wav / neueste .wav|.mp3 in voice/)
  Caption-Stil kanaele/<k>/kit/captions.json, Felder: an schrift schrift_datei gewicht groesse versalien farbe kontur
      kontur_breite schatten hintergrund hintergrund_radius innenabstand hervorhebung{farbe,hintergrund,skala} y seitenrand
      zeilenabstand wortabstand max_woerter max_zeichen pause_bruch erscheinen(wort|gruppe) animation(pop|auf|keine)
      satzzeichen_weg"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path

import _bau
import _ms

THREE_CDN = 'https://cdn.jsdelivr.net/npm/three@0.181.2/'
GSAP = 'https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js'
HF_JSON = {
    '$schema': 'https://hyperframes.heygen.com/schema/hyperframes.json',
    'paths': {'blocks': 'compositions', 'components': 'compositions/components', 'assets': 'assets'},
    'media': {'autoProxy': True},
}


# ---------------------------------------------------------------- Wortzeiten und Caption-Gruppen

def woerter_lesen(fo: Path) -> list[dict]:
    d = _ms.json_lesen(fo / 'voice' / 'woerter.json')
    if d is None:
        return []
    if isinstance(d, dict):
        d = d.get('woerter') or d.get('words') or []
    aus = []
    for w in d:
        text = str(w.get('w', w.get('word', ''))).strip()
        if text:
            aus.append({'w': text, 's': float(w['s']), 'e': float(w['e'])})
    return aus


def gruppieren(woerter: list[dict], stil: dict) -> list[dict]:
    gruppen, akt = [], []

    def schliessen():
        if akt:
            gruppen.append({'text': ' '.join(w['w'] for w in akt), 's': akt[0]['s'], 'e': akt[-1]['e'],
                            'woerter': list(akt)})
            akt.clear()

    for w in woerter:
        if akt:
            zeichen = sum(len(x['w']) + 1 for x in akt) + len(w['w'])
            vorher = akt[-1]
            if (len(akt) >= stil['max_woerter'] or zeichen > stil['max_zeichen']
                    or w['s'] - vorher['e'] > stil['pause_bruch'] or re.search(r'[.!?:;]$', vorher['w'])
                    or (re.search(r',$', vorher['w']) and len(akt) >= 2)):
                schliessen()
        akt.append(w)
    schliessen()
    # Gruppenende: kurz nachstehen lassen, aber nie in die nächste Gruppe hinein
    for i, g in enumerate(gruppen):
        nxt = gruppen[i + 1]['s'] if i + 1 < len(gruppen) else g['e'] + 0.6
        g['e'] = round(min(nxt, g['e'] + 0.25), 3)
    return gruppen


def captions_zuschneiden(gruppen: list[dict], szenen: list[dict], dauer: float) -> tuple[list[dict], dict]:
    """Captions an die Folge anpassen: Wörter in Szenen mit "captions": false fallen weg, eine Gruppe endet vor so
    einer Szene und spätestens am Videoende (gekappt statt Fehler). Wörter ab dem Videoende fallen weg und werden
    gezählt. Rückgabe (gruppen, info) mit info: aus {szene: n}, nach_ende [zeiten], gekappt_ende (Anzahl Gruppen)."""
    def ohne(t):
        k = [s for s in szenen if s['start'] - 1e-6 <= t < s['start'] + s['dur']]
        oben = max(k, key=lambda s: (s['start'], s['track'])) if k else None
        return oben['id'] if oben and oben.get('captions') is False else None

    aus_starts = sorted(s['start'] for s in szenen if s.get('captions') is False)
    info = {'aus': {}, 'nach_ende': [], 'gekappt_ende': 0}
    neu = []
    for g in gruppen:
        stuecke, akt = [], []
        for w in g['woerter']:
            sid = ohne(w['s'])
            if w['s'] >= dauer - 0.02:
                info['nach_ende'].append(w['s'])
            elif sid:
                info['aus'][sid] = info['aus'].get(sid, 0) + 1
            else:
                akt.append(w)
                continue
            if akt:
                stuecke.append(akt)
                akt = []
        if akt:
            stuecke.append(akt)
        for ws in stuecke:
            s = g['s'] if ws[0] is g['woerter'][0] else ws[0]['s']
            e = g['e']
            grenze = [t for t in aus_starts if t > s + 1e-6]
            if grenze:
                e = min(e, grenze[0])
            if e > dauer:
                e = dauer
                info['gekappt_ende'] += 1
            neu.append({'text': ' '.join(w['w'] for w in ws), 's': round(s, 3), 'e': round(min(dauer, max(e, s + 0.04)), 3),
                        'woerter': ws})
    return neu, info


def anzeige(wort: str, stil: dict) -> str:
    w = wort.rstrip(stil.get('satzzeichen_weg') or '') or wort
    return w.upper() if stil.get('versalien') else w


def captions_html(gruppen: list[dict], stil: dict, dauer: float) -> str:
    hv = stil.get('hervorhebung') or {}
    font_face = ''
    familie = f"'{stil['schrift']}'"
    if stil.get('schrift_datei'):
        font_face = (f"@font-face {{ font-family: 'MSCaption'; src: url('assets/{stil['schrift_datei']}'); "
                     f"font-weight: 100 900; }}")
        familie = "'MSCaption'"
    kasten = (f"background: {stil['hintergrund']}; border-radius: {stil['hintergrund_radius']}px; "
              f"padding: {stil['innenabstand']};") if stil.get('hintergrund') else ''
    kontur = ''
    if stil.get('kontur'):
        # Kontur außen: Strich doppelt so breit, Füllung darüber (paint-order), kein Hilfselement nötig
        kontur = (f"-webkit-text-stroke: {2 * float(stil['kontur_breite']):g}px {stil['kontur']}; paint-order: stroke fill;")
    hv_kasten = f"background: {hv['hintergrund']};" if hv.get('hintergrund') else ''
    daten = [{'s': round(g['s'], 3), 'e': round(g['e'], 3),
              'w': [[anzeige(w['w'], stil), round(w['s'], 3)] for w in g['woerter']]} for g in gruppen]
    return f'''<!doctype html>
<html><head><meta charset="UTF-8" /></head><body><template>
<style>
  {font_face}
  #captions-root {{ position: absolute; inset: 0; pointer-events: none; }}
  .msc-g {{ position: absolute; left: {stil['seitenrand']}px; right: {stil['seitenrand']}px; top: {stil['y']}px;
    display: flex; flex-wrap: wrap; justify-content: center; gap: 10px {stil['wortabstand']}px; visibility: hidden; }}
  .msc-w {{ position: relative; display: inline-block; font-family: {familie}; font-weight: {stil['gewicht']};
    font-size: {stil['groesse']}px; line-height: {stil['zeilenabstand']}; color: {stil['farbe']}; text-shadow: {stil.get('schatten') or 'none'};
    transform-origin: 50% 70%; opacity: 0; {kontur} {kasten} }}
  .msc-w.an {{ color: {hv.get('farbe') or stil['farbe']}; {hv_kasten} }}
</style>
<div id="captions-root" data-composition-id="captions" data-width="1080" data-height="1920" data-duration="{dauer:.2f}"></div>
<script>
(function () {{
  // Erzeugt von "ms szenen": Gruppen [{{s, e, w: [[wort, start], …]}}]. Nicht von Hand ändern, neu erzeugen.
  const G = {json.dumps(daten, ensure_ascii=False)};
  const MODUS = {json.dumps(stil.get('erscheinen', 'wort'))}, ANIM = {json.dumps(stil.get('animation', 'pop'))};
  const SK = {float(hv.get('skala') or 1.0)};
  const root = document.getElementById("captions-root");
  const tl = gsap.timeline({{ paused: true }});
  tl.set({{}}, {{}}, {dauer:.2f});
  G.forEach((g) => {{
    const el = document.createElement("div"); el.className = "msc-g"; root.appendChild(el);
    tl.set(el, {{ visibility: "visible" }}, g.s); tl.set(el, {{ visibility: "hidden" }}, g.e);
    const ws = g.w.map(([w, t]) => {{
      const s = document.createElement("span"); s.className = "msc-w"; s.textContent = w; el.appendChild(s);
      const auf = MODUS === "gruppe" ? g.s : t;
      if (ANIM === "pop") tl.fromTo(s, {{ opacity: 0, scale: 0.6, y: 22 }}, {{ opacity: 1, scale: SK, y: -4, duration: 0.12, ease: "back.out(2.4)" }}, auf);
      else if (ANIM === "auf") tl.fromTo(s, {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.14, ease: "power2.out" }}, auf);
      else tl.set(s, {{ opacity: 1 }}, auf);
      tl.set(s, {{ className: "msc-w an" }}, t);
      return {{ s, t }};
    }});
    ws.forEach((o, k) => {{
      const naechst = k + 1 < ws.length ? ws[k + 1].t : g.e;
      if (naechst > o.t + 0.13) {{
        if (ANIM === "pop") tl.to(o.s, {{ scale: 1, y: 0, duration: 0.1, ease: "power2.out" }}, naechst);
        tl.set(o.s, {{ className: "msc-w" }}, naechst);
      }}
    }});
  }});
  window.__timelines["captions"] = tl;
}})();
</script>
</template></body></html>
'''


# ---------------------------------------------------------------- Platzhalter für noch nicht gebaute Szenen

PLATZHALTER = 'data-platzhalter="1"'


def platzhalter_html(sid: str, dur: float) -> str:
    """Neutrale Komposition mit der richtigen Dauer. Grau, mit Szenen-id, damit sie in Snapshots auffällt."""
    return f'''<!doctype html>
<!-- Platzhalter von "ms szenen": compositions/{sid}.html fehlte. Der Bauer ersetzt diese Datei komplett
     (erst mit Read öffnen, dann mit Write neu schreiben, ohne data-platzhalter). -->
<html><head><meta charset="UTF-8" /></head><body><template>
<style>
  #{sid}-root {{ position: absolute; inset: 0; overflow: hidden; background: #2b2b30; }}
  #{sid}-hinweis {{ position: absolute; left: 0; right: 0; top: 880px; text-align: center; color: #8d8d96;
    font-family: "Montserrat"; font-weight: 700; font-size: 56px; }}
</style>
<div id="{sid}-root" data-composition-id="{sid}" {PLATZHALTER} data-width="1080" data-height="1920" data-duration="{dur:.3f}">
  <div id="{sid}-hinweis">{sid} · noch nicht gebaut</div>
</div>
<script>
(function () {{
  const tl = gsap.timeline({{ paused: true }});
  tl.set({{}}, {{}}, {dur:.3f});
  window.__timelines["{sid}"] = tl;
}})();
</script>
</template></body></html>
'''


def ist_platzhalter(text: str) -> bool:
    return PLATZHALTER in text


def platzhalter_anlegen(build: Path, szenen: list[dict]) -> tuple[list[str], list[str]]:
    """Legt fehlende Kompositionen als Platzhalter an. Ein eigener, unveränderter Platzhalter bekommt bei geänderter
    Dauer die neue Dauer. Alles andere wird nie angefasst. Gibt (angelegt, angepasst) als Listen von ids zurück."""
    angelegt, angepasst = [], []
    for s in szenen:
        f = build / 'compositions' / f"{s['id']}.html"
        if not f.exists():
            f.write_text(platzhalter_html(s['id'], s['dur']), encoding='utf-8')
            angelegt.append(s['id'])
            continue
        text = f.read_text(encoding='utf-8', errors='replace')
        if not ist_platzhalter(text):
            continue
        alt = wurzel_dauer(text, s['id'])
        if alt is not None and abs(alt - s['dur']) > 0.0005 and text == platzhalter_html(s['id'], alt):
            f.write_text(platzhalter_html(s['id'], s['dur']), encoding='utf-8')
            angepasst.append(s['id'])
    return angelegt, angepasst


# ---------------------------------------------------------------- index.html

def globale_libs(build: Path) -> list[str]:
    aus = []
    for p in sorted((build / 'assets' / 'lib').glob('*.js')):
        try:
            kopf = p.read_text(encoding='utf-8', errors='replace')[:300]
        except OSError:
            continue
        if 'ms-global' in kopf:
            aus.append(f'assets/lib/{p.name}')
    return aus


def importmap(build: Path) -> str:
    lokal = build / 'assets' / 'lib' / 'three' / 'three.module.js'
    if lokal.exists():
        imp = {'three': 'assets/lib/three/three.module.js', 'three/addons/': 'assets/lib/three/addons/'}
    else:
        imp = {'three': THREE_CDN + 'build/three.module.js', 'three/addons/': THREE_CDN + 'examples/jsm/'}
    return json.dumps({'imports': imp})


def index_html(szenen: list[dict], dauer: float, ton_rel: str | None, libs: list[str], imap: str,
               captions: bool, auslauf: float = _bau.AUSLAUF) -> str:
    kopf_libs = '\n'.join(f'    <script src="{l}"></script>' for l in libs)
    zeilen = []
    if ton_rel:
        zeilen.append(f'      <audio id="ms-ton" src="{ton_rel}" data-start="0" data-duration="{dauer:.2f}" '
                      f'data-track-index="20"></audio>')
    for s in szenen:
        zeilen.append(
            f'      <div id="{s["id"]}" data-composition-id="{s["id"]}" data-composition-src="compositions/{s["id"]}.html" '
            f'data-start="{s["start"]:.3f}" data-duration="{s["dur"]:.3f}" data-track-index="{int(s["track"])}" '
            f'data-width="1080" data-height="1920" style="position:absolute;inset:0;z-index:{int(s["track"])}"></div>')
    if captions:
        zeilen.append(
            f'      <div id="captions" data-track-kind="captions" data-composition-id="captions" '
            f'data-composition-src="compositions/captions.html" data-start="0" data-duration="{dauer:.2f}" '
            f'data-track-index="10" data-width="1080" data-height="1920" style="position:absolute;inset:0;z-index:10"></div>')
    inhalt = '\n'.join(zeilen)
    return f'''<!doctype html>
<html lang="de">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <!-- Erzeugt von "ms szenen" aus build/scenes.json. Nicht von Hand ändern: Änderungen in scenes.json, dann neu erzeugen. -->
    <!-- {_bau.AUSLAUF_MARKE} {auslauf:.3f} -->
    <script type="importmap">{imap}</script>
    <script src="{GSAP}"></script>
{kopf_libs}
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ margin: 0; width: 1080px; height: 1920px; overflow: hidden; background: #000; }}
      #root {{ position: relative; width: 100%; height: 100%; overflow: hidden; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{dauer:.2f}" data-fps="30" data-width="1080" data-height="1920">
{inhalt}
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
'''


# ---------------------------------------------------------------- Prüfung

def wurzel_dauer(text: str, sid: str):
    """data-duration des Elements mit data-composition-id="<sid>" (Reihenfolge der Attribute egal)."""
    for tag in re.findall(r'<[a-zA-Z][^>]*data-composition-id="%s"[^>]*>' % re.escape(sid), text):
        m = re.search(r'data-duration="([\d.]+)"', tag)
        if m:
            return float(m.group(1))
    return None


def pruefen(fo: Path, szenen: list[dict], dauer: float, captions: bool, gruppen: list | None,
            nur_check: bool, plan: bool = False, nur: set | None = None) -> list[tuple[str, str]]:
    """Liefert Befunde als (schwere, text) mit schwere 'FEHLER' oder 'HINWEIS'.
    plan: vor dem Bau. Mit nur_check werden Kompositionen gar nicht geprüft, beim Schreiben sind Platzhalter nur Hinweis.
    nur: Kompositionen nur dieser ids prüfen (Selbstprüfung eines Bauers)."""
    b = []
    build = fo / 'build'
    if abs(szenen[0]['start']) > 1e-6:
        b.append(('FEHLER', f"erste Szene {szenen[0]['id']} startet bei {szenen[0]['start']:.3f} statt 0 (Schwarzbild am Anfang)"))
    gedeckt, vorige = szenen[0]['start'] + szenen[0]['dur'], szenen[0]
    for s in szenen[1:]:
        ueber = gedeckt - s['start']
        if ueber < _bau.LUECKE_GRENZE:
            b.append(('FEHLER', f"LÜCKE: bis {gedeckt:.3f} gedeckt ({vorige['id']}), {s['id']} startet {s['start']:.3f} "
                                f"(Überlappung {ueber:+.3f} s, Soll {_bau.UEBERLAPP:.2f}: Start = Ende − 0,06)"))
        elif ueber > 0.5 and s['track'] <= vorige['track']:
            b.append(('HINWEIS', f"{s['id']} überlappt {ueber:.2f} s mit {vorige['id']} und liegt nicht darüber "
                                 f"(track {s['track']} ≤ {vorige['track']}): gewollt?"))
        if s['start'] + s['dur'] > gedeckt:
            gedeckt, vorige = s['start'] + s['dur'], s
    if gedeckt < dauer - 0.01:
        b.append(('FEHLER', f'Szenen enden bei {gedeckt:.2f} s, Gesamtdauer ist {dauer:.2f} s (Schwarzbild am Ende). '
                            f'Letzte Szene verlängern.'))
    elif gedeckt > dauer + 0.5:
        b.append(('HINWEIS', f'Szenen laufen bis {gedeckt:.2f} s, das Video endet bei {dauer:.2f} s (Rest wird abgeschnitten).'))
    for s in ([] if (plan and nur_check) else szenen):
        if nur and s['id'] not in nur:
            continue
        f = build / 'compositions' / f"{s['id']}.html"
        if not f.exists():
            b.append(('FEHLER', f"fehlt: compositions/{s['id']}.html ({s.get('art', '?')}, {s.get('inhalt', '')[:50]})"))
            continue
        text = f.read_text(encoding='utf-8', errors='replace')
        if ist_platzhalter(text):
            b.append(('HINWEIS' if plan else 'FEHLER',
                      f"{s['id']} noch nicht gebaut (Platzhalter von ms szenen; {s.get('art', '?')}, {s.get('inhalt', '')[:50]})"))
            continue
        d = wurzel_dauer(text, s['id'])
        if d is None:
            b.append(('FEHLER', f"{s['id']}.html: kein Element mit data-composition-id=\"{s['id']}\" und data-duration"))
        elif abs(d - s['dur']) > 0.005:
            b.append(('FEHLER', f"{s['id']}.html: data-duration {d:g} ≠ scenes.json {s['dur']:g}"))
        hat_tl = re.search(r'__timelines\s*\[\s*["\']%s["\']\s*\]' % re.escape(s['id']), text) or (
            '__timelines[' in text and re.search(r'["\']%s["\']' % re.escape(s['id']), text))
        if not hat_tl and 'ms3dSzene(' not in text:
            b.append(('HINWEIS', f"{s['id']}.html: keine Timeline window.__timelines[\"{s['id']}\"] gefunden"))
        if s.get('art') == 'blender':
            for src in re.findall(r'<video[^>]*src="([^"]+)"', text):
                if not (build / src).exists():
                    b.append(('FEHLER', f"{s['id']}.html: Video {src} fehlt (Blender-Render noch nicht da?)"))
    if not _bau.stimme_finden(fo):
        b.append(('HINWEIS', 'keine Stimme in voice/: Gesamtdauer = Ende der letzten Szene, Video ohne Ton'))
    if captions:
        if not gruppen:
            b.append(('FEHLER', 'Captions an, aber voice/woerter.json fehlt oder ist leer (oder --ohne-captions)'))
        else:
            letzt = max(g['e'] for g in gruppen)
            if letzt > dauer + 0.01:
                b.append(('FEHLER', f'Captions laufen bis {letzt:.2f} s, Video endet {dauer:.2f} s (Wortzeiten zur falschen Stimme?)'))
    idx = build / 'index.html'
    if nur_check and not plan:
        if not idx.exists():
            b.append(('FEHLER', 'build/index.html fehlt: ms szenen <folge> (ohne --check) ausführen'))
        else:
            t = idx.read_text(encoding='utf-8', errors='replace')
            d = wurzel_dauer(t, 'main')
            if d is None or abs(d - dauer) > 0.011:
                b.append(('FEHLER', f'index.html ist veraltet (Dauer {d} statt {dauer:.2f}): ms szenen <folge> neu ausführen'))
            for s in szenen:
                m = re.search(r'id="%s"[^>]*data-start="([\d.]+)"[^>]*data-duration="([\d.]+)"' % re.escape(s['id']), t)
                if not m or abs(float(m.group(1)) - s['start']) > 0.002 or abs(float(m.group(2)) - s['dur']) > 0.002:
                    b.append(('FEHLER', f"index.html passt nicht zu scenes.json bei {s['id']}: ms szenen <folge> neu ausführen"))
                    break
    return b


# ---------------------------------------------------------------- Hauptteil

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folge')
    ap.add_argument('--check', action='store_true', help='nur prüfen, nichts schreiben')
    ap.add_argument('--ohne-captions', action='store_true')
    ap.add_argument('--plan', action='store_true',
                    help='vor dem Bau: mit --check nur den Zeitplan prüfen, beim Schreiben zählen Platzhalter nicht als Fehler')
    ap.add_argument('--lint', action='store_true', help='zusätzlich hyperframes lint im build-Ordner')
    ap.add_argument('--nur', action='append', metavar='IDS', help='Kompositionen nur dieser Szenen prüfen, z. B. --nur s2,s4')
    ap.add_argument('--auslauf', type=float,
                    help='Sekunden Bild nach dem Stimm-Ende (Standard: wie beim letzten Bau laut index.html, sonst 0,47)')
    a = ap.parse_args()

    fo = _bau.folge(a.folge)
    build = fo / 'build'
    szenen = _bau.szenen_lesen(fo)
    if a.auslauf is not None and a.auslauf < 0:
        raise SystemExit('FEHLER: --auslauf darf nicht negativ sein (0 = Video endet genau mit der Stimme).')
    auslauf = a.auslauf if a.auslauf is not None else _bau.index_auslauf(build)
    auslauf = _bau.AUSLAUF if auslauf is None else auslauf
    dauer, quelle = _bau.gesamtdauer(fo, auslauf, szenen)
    stil = _bau.caption_stil(fo)
    captions = bool(stil.get('an', True)) and not a.ohne_captions
    gruppen, cap_info = None, None
    if captions:
        eigene = _ms.json_lesen(build / 'captions.json')
        if eigene:
            gruppen = [{'text': g.get('text', ''), 's': float(g['s']), 'e': float(g['e']),
                        'woerter': [{'w': w['w'], 's': float(w['s']), 'e': float(w['e'])} for w in g['woerter']]}
                       for g in eigene]
        else:
            w = woerter_lesen(fo)
            gruppen = gruppieren(w, stil) if w else []
        if gruppen:
            gruppen, cap_info = captions_zuschneiden(gruppen, szenen, dauer)

    if not a.check:
        (build / 'compositions').mkdir(parents=True, exist_ok=True)
        audio = build / 'assets' / 'audio'
        audio.mkdir(parents=True, exist_ok=True)
        ton_rel = None
        if (audio / 'mix.wav').exists():
            ton_rel = 'assets/audio/mix.wav'
        else:
            st = _bau.stimme_finden(fo)
            if st:
                ziel = audio / f'stimme{st.suffix.lower()}'
                if not ziel.exists() or ziel.stat().st_mtime < st.stat().st_mtime or ziel.stat().st_size != st.stat().st_size:
                    shutil.copy2(st, ziel)
                ton_rel = f'assets/audio/{ziel.name}'
        if not (build / 'hyperframes.json').exists():
            _ms.json_schreiben(build / 'hyperframes.json', HF_JSON)
        angelegt, angepasst = platzhalter_anlegen(build, szenen)
        if angelegt:
            print(f'Platzhalter angelegt (noch nicht gebaut): {", ".join(angelegt)}')
        if angepasst:
            print(f'Platzhalter an neue Dauer angepasst: {", ".join(angepasst)}')
        (build / 'index.html').write_text(index_html(szenen, dauer, ton_rel, globale_libs(build), importmap(build),
                                                     bool(captions and gruppen), auslauf), encoding='utf-8')
        if captions and gruppen:
            (build / 'compositions' / 'captions.html').write_text(captions_html(gruppen, stil, dauer), encoding='utf-8')
            _ms.json_schreiben(build / 'captions_gruppen.json', gruppen)
        print(f'index.html geschrieben: {len(szenen)} Szenen, Gesamtdauer {dauer:.2f} s ({quelle}), '
              f'Ton {ton_rel or "keiner"}, Captions {len(gruppen) if (captions and gruppen) else 0} Gruppen')
    if cap_info:
        teile = [f'{n} Wörter in {sid} ausgeblendet ("captions": false)' for sid, n in cap_info['aus'].items()]
        if cap_info['gekappt_ende']:
            teile.append(f'{cap_info["gekappt_ende"]} Gruppe(n) am Videoende auf {dauer:.2f} s gekappt')
        if teile:
            print('Captions: ' + ', '.join(teile))

    nur = {x.strip() for teil in (a.nur or []) for x in teil.split(',') if x.strip()} or None
    if nur:
        unbekannt = nur - {s['id'] for s in szenen}
        if unbekannt:
            raise SystemExit(f'FEHLER: --nur {", ".join(sorted(unbekannt))} steht nicht in scenes.json.')
    befunde = pruefen(fo, szenen, dauer, captions, gruppen, a.check, a.plan, nur)
    if cap_info and cap_info['nach_ende']:
        spaet = cap_info['nach_ende']
        deutlich = [t for t in spaet if t > dauer + 1.0]     # über 1 s nach dem Ende: kein Satzrest mehr, sondern falsche Zeiten
        befunde.append(('FEHLER' if deutlich else 'HINWEIS',
                        f'{len(spaet)} Caption-Wörter beginnen erst ab {min(spaet):.2f} s, das Video endet {dauer:.2f} s, '
                        + ('bis zu {:.1f} s danach: Wortzeiten zur falschen Stimme? (ms woerter neu)'.format(max(spaet) - dauer)
                           if deutlich else 'sie fallen weg (Ausschnitt endet mitten im Satz? Sonst --auslauf größer)')))
    if a.lint:
        if not (build / 'index.html').exists():
            befunde.append(('FEHLER', 'lint nicht möglich: build/index.html fehlt (die Regie führt ms szenen <folge> aus)'))
        else:
            n_fehler, n_warn, text = _bau.lint(build)
            if n_fehler:
                zeilen = [z.strip() for z in text.splitlines() if '✗' in z or 'error' in z.lower()][:12]
                befunde.append(('FEHLER', f'hyperframes lint: {n_fehler} Fehler, {n_warn} Warnungen\n      ' + '\n      '.join(zeilen)))
            else:
                print(f'hyperframes lint: 0 Fehler, {n_warn} Warnungen')
    fehler = [t for s, t in befunde if s == 'FEHLER']
    print('Prüfung:', 'OK' if not fehler else f'{len(fehler)} Fehler', f'({len(befunde) - len(fehler)} Hinweise)' if len(befunde) > len(fehler) else '')
    for s, t in befunde:
        print(f'  {s}: {t}')
    if a.check:
        print(f'Gesamtdauer {dauer:.2f} s ({quelle}). Nur geprüft, nichts geschrieben.')
    else:
        print(build / 'index.html')
    return 1 if (fehler and a.check) else 0


if __name__ == '__main__':
    sys.exit(main())
