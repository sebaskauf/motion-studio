"""Ton zerlegen: Lautheit, Sprechtempo, Musik ja/nein, Effekt-Momente (Onsets außerhalb der Sprache), optional AST-Klassen.
  ms ton-zerlegen <video|register-id> [--kanal <slug>] [--out <ordner>] [--ton <audiodatei>] [--ohne-ast] [--sprache auto]
Beispiele:
  ms ton-zerlegen yt-abc123xyz00 --kanal mein-kanal       -> kanaele/mein-kanal/analyse/yt-abc123xyz00/ton.json + TON.md + ton.png
  ms ton-zerlegen reel.mp4 --ton reel.m4a             Video ohne Tonspur, Ton liegt daneben
Ergebnis: ton.json, TON.md, ton.png (Pegel, Sprache, Effekt-Momente, Schnitte) und ein Abschnitt in ANALYSE.md, falls vorhanden.
Effekt-Momente sind Kandidaten, keine bewiesenen Soundeffekte: Einsätze in Sprechpausen und breitbandige Einsätze
werden bevorzugt, Silben der Stimme fallen weg. Immer anhören. AST-Klassen (AudioSet) nur, wenn torch + transformers
installiert sind (Modell MIT/ast-finetuned-audioset-10-10-0.4593, beim ersten Mal ca. 350 MB Download).
Musik: Heuristik aus Pegel und Klang in den Sprechpausen, mit AST zusätzlich die Klasse "Music"."""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

import _ms
import transkript as T
import zerlegen as Z

RATE = 16000
N_FFT = 1024
HOP = 256
BAENDER = [60, 150, 300, 600, 1200, 2400, 4000, 6000, 8000]  # Hz, 8 Bänder
AST_MODELL = 'MIT/ast-finetuned-audioset-10-10-0.4593'
# AudioSet-Klassen, die typische Schnitt- und Animationseffekte beschreiben
EFFEKT_KLASSEN = {'Whoosh, swoosh, swish', 'Thump, thud', 'Bang', 'Slap, smack', 'Smash, crash', 'Whip', 'Beep, bleep', 'Ding',
                  'Clang', 'Clicking', 'Sound effect', 'Explosion', 'Burst, pop', 'Boom', 'Shatter', 'Cash register', 'Camera',
                  'Chime', 'Bell', 'Knock', 'Tick', 'Zipper (clothing)', 'Squeak', 'Clapping', 'Rattle', 'Ding-dong',
                  'White noise', 'Pink noise', 'Glass', 'Coin (dropping)', 'Typing', 'Computer keyboard', 'Mouse click'}


def _np():
    import numpy as np
    return np


def tonquelle(video: Path, extra: str | None) -> Path | None:
    """Tonspur des Videos oder eine Audiodatei daneben (Instagram/Apify liefern Ton oft getrennt)."""
    if extra:
        p = Path(extra).expanduser()
        if not p.exists():
            raise SystemExit(f'FEHLER: {p} gibt es nicht.')
        return p
    if _ms.probe(video)['ton']:
        return video
    for k in (video.with_suffix('.m4a'), video.with_suffix('.mp3'), video.with_suffix('.wav'), video.parent / 'audio.m4a'):
        if k.exists():
            return k
    return None


def spektrum(audio: Path, tmp: Path) -> dict:
    """Kurzzeit-Merkmale in Blöcken (Audio liegt als memmap auf der Platte, nie komplett im RAM)."""
    np = _np()
    roh = tmp / 'a.f32'
    _ms.befehl(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(audio), '-vn', '-ac', '1', '-ar', str(RATE),
                '-f', 'f32le', str(roh)])
    x = np.memmap(roh, dtype=np.float32, mode='r')
    n_frames = max(0, (len(x) - N_FFT) // HOP + 1)
    if n_frames < 10:
        raise SystemExit('FEHLER: Tonspur zu kurz oder leer.')
    fenster = np.hanning(N_FFT).astype(np.float32)
    freq = np.fft.rfftfreq(N_FFT, 1 / RATE)
    bands = [(freq >= a) & (freq < b) for a, b in zip(BAENDER, BAENDER[1:])]
    sprach = (freq >= 100) & (freq < 6000)
    stimmband = (freq >= 300) & (freq < 3400)
    rms, flux, flach, stimme = (np.zeros(n_frames, np.float32) for _ in range(4))
    bandflux = np.zeros((n_frames, len(bands)), np.float32)
    vorher = None
    block = 4096
    for s in range(0, n_frames, block):
        e = min(n_frames, s + block)
        stueck = np.asarray(x[s * HOP:(e - 1) * HOP + N_FFT], dtype=np.float32)
        rahmen = np.lib.stride_tricks.sliding_window_view(stueck, N_FFT)[::HOP][:e - s]
        rms[s:e] = 20 * np.log10(np.sqrt((rahmen ** 2).mean(1)) + 1e-7)
        mag = np.abs(np.fft.rfft(rahmen * fenster, axis=1)).astype(np.float32)
        L = np.log1p(10 * mag)
        davor = np.vstack([vorher[None] if vorher is not None else L[:1], L[:-1]])
        pos = np.maximum(0, L - davor)
        flux[s:e] = pos.mean(1)
        for j, b in enumerate(bands):
            bandflux[s:e, j] = pos[:, b].mean(1)
        p = mag[:, sprach] ** 2 + 1e-10
        flach[s:e] = np.exp(np.log(p).mean(1)) / p.mean(1)
        stimme[s:e] = 10 * np.log10((mag[:, stimmband] ** 2).mean(1) + 1e-10)
        vorher = L[-1]
    t = (np.arange(n_frames) * HOP + N_FFT / 2) / RATE
    return {'t': t, 'rms': rms, 'flux': flux, 'bandflux': bandflux, 'flach': flach, 'stimme': stimme, 'dauer': len(x) / RATE,
            'roh': roh, 'n': len(x)}


def sprach_abschnitte(t: dict | None) -> list:
    """Sprechzeiten aus den Wortzeiten (Lücken < 0,15 s überbrückt, 30 ms Rand)."""
    if not t or not t.get('woerter'):
        return []
    ab = []
    for w in t['woerter']:
        s, e = w['s'] - 0.03, w['e'] + 0.03
        if ab and s - ab[-1][1] < 0.15:
            ab[-1][1] = max(ab[-1][1], e)
        else:
            ab.append([s, e])
    return ab


def pausen_aus_audio(sp: dict, sprache: list) -> list:
    """Sprechpausen aus dem Sprachband-Pegel (whisper setzt Wortgrenzen lückenlos, daher nicht aus dem Transkript).
    Pause = Pegel im Band 300-3400 Hz deutlich unter dem Sprechpegel, mindestens 80 ms. Außerhalb der Sprechzeit immer Pause."""
    np = _np()
    st = np.convolve(sp['stimme'], np.ones(3) / 3, mode='same')
    lo, hi = np.percentile(st, 20), np.percentile(st, 95)
    leise = st < lo + 0.35 * (hi - lo)
    t = sp['t']
    if sprache:
        leise |= (t < sprache[0][0]) | (t > sprache[-1][1])
    else:
        leise[:] = True
    aus, i, mind = [], 0, int(0.08 * RATE / HOP)
    while i < len(leise):
        if leise[i]:
            e = i
            while e + 1 < len(leise) and leise[e + 1]:
                e += 1
            if e - i + 1 >= mind:
                aus.append((float(t[i]), float(t[e])))
            i = e + 1
        else:
            i += 1
    return aus


def onsets(sp: dict, pausen: list) -> list:
    """Einsätze per Spektralfluss, bewertet nach Sprechpause und Breitband-Charakter."""
    np = _np()
    n = sp['flux']
    fps = RATE / HOP
    r = int(0.25 * fps)
    med = np.array([np.median(n[max(0, i - r):i + r + 1]) for i in range(len(n))])
    mad = float(np.median(np.abs(n - med))) + 1e-6
    schwelle = med + 3 * mad + 0.002
    p90 = np.percentile(sp['bandflux'], 90, axis=0) + 1e-6
    flach_typisch = float(np.median(sp['flach'])) + 1e-6
    vor = int(0.1 * fps)
    abst = int(0.08 * fps)
    kandidaten, letzte = [], -10 ** 9
    for i in range(3, len(n) - 3):
        if n[i] <= schwelle[i] or n[i] < n[i - 3:i + 4].max() or i - letzte < abst:
            continue
        letzte = i
        t = float(sp['t'][i])
        staerke = float(n[i] / schwelle[i])
        breit = float((sp['bandflux'][i] >= p90).mean())
        in_pause = bool(any(a <= t - 0.02 <= b for a, b in pausen))  # Einsatz kommt aus einer Sprechpause
        rauschig = bool(float(np.median(sp['flach'][i:i + vor])) / flach_typisch >= 2.0)
        if staerke >= 1.3 and ((in_pause and breit >= 0.5) or breit >= 0.75):
            punkte = staerke * (1.5 if in_pause else 1.0) * (1 + breit) * (1.3 if rauschig else 1.0)
            kandidaten.append({'t': round(t, 3), 'staerke': round(staerke, 2), 'breitband': round(breit, 2),
                               'in_pause': in_pause, 'rauschig': rauschig,
                               'sicher': bool(in_pause and breit >= 0.75), '_punkte': punkte})
    kandidaten.sort(key=lambda k: -k['_punkte'])
    aus = sorted(kandidaten[:40], key=lambda k: k['t'])
    for k in aus:
        k.pop('_punkte')
    return aus


def demucs_trennen(audio: Path, tmp: Path):
    """Stimme und Rest trennen (nur wenn demucs installiert ist). Gibt (stimme.wav, rest.wav) oder None zurück."""
    import shutil
    import subprocess
    cmd = ['demucs'] if shutil.which('demucs') else None
    if not cmd:
        try:
            import demucs  # noqa: F401
            cmd = [sys.executable, '-m', 'demucs']
        except ImportError:
            return None
    wav = tmp / 'mix.wav'
    _ms.befehl(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(audio), '-vn', '-ac', '2', '-ar', '44100', str(wav)])
    print('Trenne Stimme und Rest mit demucs (dauert etwa so lange wie das Video) …', flush=True)
    # -d cpu: auf Apple Silicon bricht demucs auf MPS ab ("Output channels > 65536 not supported")
    r = subprocess.run(cmd + ['--two-stems=vocals', '-n', 'htdemucs', '-d', 'cpu', '-o', str(tmp / 'sep'), str(wav)],
                       capture_output=True, text=True)
    stimme = next((tmp / 'sep').rglob('vocals.wav'), None) if (tmp / 'sep').exists() else None
    rest = next((tmp / 'sep').rglob('no_vocals.wav'), None) if (tmp / 'sep').exists() else None
    if r.returncode != 0 or not stimme or not rest:
        print('Hinweis: demucs ist fehlgeschlagen, weiter ohne Trennung.')
        return None
    return stimme, rest


def bpm_schaetzen(sp: dict):
    np = _np()
    n = sp['flux'] - sp['flux'].mean()
    fps = RATE / HOP
    lo, hi = int(0.33 * fps), int(1.0 * fps)  # 60 bis 180 BPM
    if len(n) < hi * 4:
        return None, 0.0
    ac = np.correlate(n, n, mode='full')[len(n) - 1:]
    ac = ac / (ac[0] + 1e-9)
    lag = lo + int(np.argmax(ac[lo:hi]))
    return round(60 * fps / lag), round(float(ac[lag]), 2)


def musik_heuristik(sp: dict, sprache: list) -> dict:
    np = _np()
    t, rms, fl = sp['t'], sp['rms'], sp['flach']
    rand = (t > 0.2) & (t < sp['dauer'] - 0.2)
    in_sprache = np.zeros(len(t), bool)
    for a, b in sprache:
        in_sprache |= (t >= a) & (t <= b)
    pause = rand & ~in_sprache
    pause_s = float(pause.sum() * HOP / RATE)
    grund = float(np.percentile(rms[rand], 10)) if rand.any() else -90.0
    laut = float(np.percentile(rms[rand], 90)) if rand.any() else -90.0
    werte = {'grundpegel_db': round(grund, 1), 'sprachpegel_db': round(laut, 1), 'abstand_db': round(laut - grund, 1),
             'pausen_s': round(pause_s, 2)}
    if pause_s >= 0.5:
        werte['pause_pegel_db'] = round(float(np.median(rms[pause])), 1)
        werte['pause_aktiv'] = round(float((rms[pause] > -50).mean()), 2)
        werte['pause_tonal'] = round(float(np.median(fl[pause])), 3)
    bpm, puls = bpm_schaetzen(sp)
    werte['bpm_schaetzung'], werte['puls'] = bpm, puls
    # Urteil: durchgehendes Bett (hoher Grundpegel nahe der Stimme) oder aktive, klingende Pausen
    bett = grund > -42 and (laut - grund) < 26
    pausen_klingen = werte.get('pause_aktiv', 0) > 0.7 and werte.get('pause_pegel_db', -99) > -45 and werte.get('pause_tonal', 1) < 0.3
    still = grund < -55 or (werte.get('pause_pegel_db', -99) < -55 and pause_s >= 0.5)
    if bett or pausen_klingen:
        urteil = 'ja (durchgehendes Bett unter der Stimme)' if bett else 'ja (Pausen klingen tonal weiter)'
    elif still:
        urteil = 'nein (Pausen sind still)'
    else:
        urteil = 'unklar'
    werte['urteil'] = urteil
    return werte


def ast_klassen(sp: dict, effekte: list, ohne: bool) -> dict:
    """AudioSet-Klassen für Effekt-Momente und Musik-Wahrscheinlichkeit. Fällt still aus, wenn torch/transformers fehlen."""
    if ohne:
        return {'status': 'aus (--ohne-ast)'}
    try:
        import torch
        from transformers import ASTFeatureExtractor, ASTForAudioClassification
    except ImportError:
        return {'status': 'nicht installiert (torch + transformers fehlen, siehe ms check)'}
    np = _np()
    try:
        fe = ASTFeatureExtractor.from_pretrained(AST_MODELL)
        modell = ASTForAudioClassification.from_pretrained(AST_MODELL).eval()
    except Exception as ex:  # noqa: BLE001 (z. B. offline und Modell nicht im Cache)
        return {'status': f'Modell nicht ladbar ({str(ex)[:100]})'}
    x = np.memmap(sp.get('roh_rest', sp['roh']), dtype=np.float32, mode='r')
    labels = modell.config.id2label
    musik_id = next((int(i) for i, n in labels.items() if n == 'Music'), None)
    sprach_id = next((int(i) for i, n in labels.items() if n == 'Speech'), None)

    def stueck(a, b):
        s = np.array(x[max(0, int(a * RATE)):max(0, int(b * RATE))], dtype=np.float32)
        return np.pad(s, (0, max(0, RATE - len(s))))

    def vorhersage(segmente):
        aus = []
        for i in range(0, len(segmente), 8):
            with torch.inference_mode():
                ein = fe(segmente[i:i + 8], sampling_rate=RATE, return_tensors='pt')
                aus.append(torch.sigmoid(modell(**ein).logits).numpy())
        return np.concatenate(aus) if aus else np.zeros((0, len(labels)))
    wichtig = sorted(effekte, key=lambda e: -e['staerke'])[:40]
    p = vorhersage([stueck(e['t'] - 0.05, e['t'] + 0.55) for e in wichtig])
    effekt_ids = [int(i) for i, n in labels.items() if n in EFFEKT_KLASSEN]
    for e, pe in zip(wichtig, p):
        top = np.argsort(pe)[::-1][:3]
        e['klassen'] = [f"{labels[int(i)]} {pe[i]:.2f}" for i in top if pe[i] >= 0.08]
        beste = max(effekt_ids, key=lambda i: pe[i]) if effekt_ids else None
        if beste is not None:
            e['effekt_p'] = round(float(pe[beste]), 2)
            e['effekt_klasse'] = labels[beste]
            top1 = labels[int(top[0])]
            if pe[beste] >= 0.15:
                e['urteil'] = 'Effekt wahrscheinlich'
            elif top1 in ('Music', 'Speech', 'Male speech, man speaking', 'Female speech, woman speaking', 'Musical instrument') \
                    and pe[beste] < 0.05:
                e['urteil'] = 'eher ' + ('Musik' if 'Music' in top1 or 'instrument' in top1 else 'Sprache')
            else:
                e['urteil'] = 'unklar'
            e['sicher'] = bool(pe[beste] >= 0.15 or (e['sicher'] and e['urteil'] == 'unklar'))
    dauer = sp['dauer']
    mitten = [dauer * (i + 0.5) / 10 for i in range(10)] if dauer > 3 else [dauer / 2]
    pm = vorhersage([stueck(m - 1.0, m + 1.0) for m in mitten])
    erg = {'status': 'ok', 'modell': AST_MODELL}
    if musik_id is not None and len(pm):
        erg['musik_wahrscheinlichkeit'] = round(float(pm[:, musik_id].mean()), 2)
        erg['musik_anteil_fenster'] = round(float((pm[:, musik_id] >= 0.2).mean()), 2)
    if sprach_id is not None and len(pm):
        erg['sprache_wahrscheinlichkeit'] = round(float(pm[:, sprach_id].mean()), 2)
    return erg


def schnitte_zuordnen(effekte: list, ordner: Path):
    an = _ms.json_lesen(ordner / 'analyse.json')
    if not an:
        return None
    grenzen = an.get('schnitte', [])
    for e in effekte:
        nah = min(grenzen, key=lambda g: abs(g['t'] - e['t']), default=None)
        if nah and abs(nah['t'] - e['t']) <= 0.1:
            e['am_schnitt'] = f"{nah['art']} {nah['t']:.2f} s"
    return [g['t'] for g in grenzen]


def bild(ziel: Path, sp: dict, sprache: list, effekte: list, schnitte, pausen=()):
    np = _np()
    from PIL import Image, ImageDraw
    W, H, L, O, U = 1600, 360, 44, 30, 30
    im = Image.new('RGB', (W, H), (250, 250, 247))
    z = ImageDraw.Draw(im)
    schrift = _ms._schrift(13)
    dauer = sp['dauer']

    def xp(t):
        return L + (W - L - 10) * t / max(dauer, 0.01)

    def yp(db):
        return H - U - (H - O - U) * (min(0, max(-60, db)) + 60) / 60
    for a, b in sprache:
        z.rectangle([xp(a), O, xp(b), H - U], fill=(222, 238, 222))
    for a, b in pausen:
        z.rectangle([xp(a), O, xp(b), H - U], fill=(250, 246, 225))
    schritt = max(1, len(sp['t']) // 3000)
    z.line([(xp(float(t)), yp(float(r))) for t, r in zip(sp['t'][::schritt], sp['rms'][::schritt])], fill=(60, 90, 160), width=1)
    for t in (schnitte or []):
        z.line([(xp(t), O), (xp(t), H - U)], fill=(170, 170, 170), width=1)
    for i, e in enumerate(effekte):
        f = (210, 40, 40) if e['in_pause'] else (240, 140, 20)
        z.line([(xp(e['t']), O + 10), (xp(e['t']), H - U)], fill=f, width=2 if e['sicher'] else 1)
        if e.get('urteil') == 'Effekt wahrscheinlich':
            z.text((xp(e['t']) + 2, O + 12 + (i % 4) * 13), e['effekt_klasse'][:18], fill=(20, 20, 20), font=schrift)
    for db in (0, -20, -40, -60):
        z.text((4, yp(db) - 7), f'{db}', fill=(90, 90, 90), font=schrift)
    for t in range(0, int(dauer) + 1, 5):
        z.text((xp(t) - 6, H - U + 7), f'{t}s', fill=(60, 60, 60), font=schrift)
    z.text((L, 6), 'Pegel dBFS (blau), Sprechzeit (grün), gemessene Pausen (gelb), Effekt-Kandidaten: rot = aus Pause, '
                   'orange = breitbandig, dick = sicher, beschriftet = AST hört einen Effekt. Schnitte grau',
           fill=(30, 30, 30), font=schrift)
    im.save(ziel)


def _komma(x, n=1):
    return f'{x:.{n}f}'.replace('.', ',')


def md_abschnitt(ton: dict) -> str:
    z = ['## Ton', '']
    if not ton.get('ton'):
        return '## Ton\n\nKeine Tonspur gefunden.\n'
    st = ton.get('sprache', {})
    z.append(f"- **Lautheit:** {_komma(ton['lufs'])} LUFS integriert" +
             (f", LRA {_komma(ton['lra'])} LU, True Peak {_komma(ton['true_peak'])} dBTP" if ton.get('lra') is not None else ''))
    if st.get('woerter'):
        z.append(f"- **Sprache:** {st['woerter']} Wörter in {_komma(st['sprechdauer'])} s = {_komma(st['woerter_pro_s'], 2)} Wörter/s "
                 f"({st['wpm']} wpm), {st['pausen_anzahl']} Pausen > 0,4 s, längste {_komma(st['laengste_pause'], 2)} s, "
                 f"erstes Wort bei {_komma(st['erstes_wort'], 2)} s")
    else:
        z.append('- **Sprache:** keine erkannt')
    m = ton['musik']
    z.append(f"- **Musik:** {m['urteil']} (Grundpegel {_komma(m['grundpegel_db'])} dB, Sprache {_komma(m['sprachpegel_db'])} dB, "
             f"Abstand {_komma(m['abstand_db'])} dB" +
             (f", Pausen {_komma(m['pause_pegel_db'])} dB, tonal {m['pause_tonal']}" if 'pause_pegel_db' in m else '') +
             (f", gleichmäßiger Puls ~{m['bpm_schaetzung']} BPM (Stärke {m['puls']})" if (m.get('puls') or 0) >= 0.2 else
              ', kein klarer Puls') + ')')
    if ton.get('trennung'):
        tr = ton['trennung']
        z.append(f"- **Trennung (demucs):** Stimme {_komma(tr['stimme_lufs'])} LUFS, Rest (Musik + Effekte) {_komma(tr['rest_lufs'])} LUFS, "
                 f"also {_komma(tr['rest_unter_stimme_db'])} dB unter der Stimme")
    a = ton.get('ast', {})
    if a.get('status') == 'ok':
        z.append(f"- **AST:** Musik-Wahrscheinlichkeit {a.get('musik_wahrscheinlichkeit')}, in {a.get('musik_anteil_fenster', 0):.0%} "
                 f"der 2-s-Fenster ≥ 0,2; Sprache {a.get('sprache_wahrscheinlichkeit')}")
    else:
        z.append(f"- **AST:** {a.get('status', 'aus')}")
    eff = ton['effekte']
    sicher = sum(1 for e in eff if e['sicher'])
    if not ton.get('trennung'):
        z.append('- Genauer wird es mit `--trennen` (demucs trennt Stimme und Rest, Effekte werden dann im Rest gesucht).')
    am = sum(1 for e in eff if e.get('am_schnitt'))
    z.append(f"- **Effekt-Kandidaten:** {len(eff)} (davon {sicher} in Sprechpause und breitbandig, {am} an einem Schnitt ±0,1 s). "
             'Kandidaten, keine Beweise: anhören.')
    if eff:
        z += ['', '| Zeit | Stärke | Breitband | Pause | rauschig | am Schnitt | Urteil | Effekt (AST) | Klassen (AST) |',
              '|---|---|---|---|---|---|---|---|---|']
        for e in eff[:40]:
            z.append(f"| {_komma(e['t'], 2)} | {e['staerke']} | {e['breitband']} | {'ja' if e['in_pause'] else '-'} | "
                     f"{'ja' if e.get('rauschig') else '-'} | {e.get('am_schnitt', '-')} | {e.get('urteil', '-')} | "
                     f"{(e['effekt_klasse'] + ' ' + str(e['effekt_p'])) if e.get('effekt_p') is not None else '-'} | "
                     f"{', '.join(e.get('klassen', [])) or '-'} |")
    z += ['', 'Bild: `ton.png` (Pegel, Sprache, Kandidaten, Schnitte).']
    return '\n'.join(z) + '\n'


def analyse_md_ergaenzen(ordner: Path, abschnitt: str):
    p = ordner / 'ANALYSE.md'
    if not p.exists():
        return False
    text = p.read_text(encoding='utf-8')
    block = '<!-- ton:start -->\n' + abschnitt.strip() + '\n<!-- ton:end -->'
    if '<!-- ton:start -->' in text:
        text = re.sub(r'<!-- ton:start -->.*?<!-- ton:end -->', lambda _: block, text, flags=re.S)
    else:
        text = text.rstrip() + '\n\n' + block + '\n'
    p.write_text(text, encoding='utf-8')
    return True


def lautheit(audio: Path) -> dict:
    aus = {'lufs': _ms.lufs(audio)}
    r = _ms.befehl(['ffmpeg', '-nostdin', '-v', 'info', '-i', str(audio), '-af', 'ebur128=peak=true:framelog=quiet',
                    '-f', 'null', '-'], pruefen=False)
    m = re.findall(r'LRA:\s+(-?[\d.]+) LU', r.stderr or '')
    p = re.findall(r'Peak:\s+(-?[\d.inf]+) dBFS', r.stderr or '')
    aus['lra'] = float(m[-1]) if m else None
    try:
        aus['true_peak'] = float(p[-1]) if p else None
    except ValueError:
        aus['true_peak'] = None
    return aus


def main():
    ap = argparse.ArgumentParser(prog='ms ton-zerlegen', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video')
    ap.add_argument('--kanal')
    ap.add_argument('--out')
    ap.add_argument('--ton', help='eigene Audiodatei, wenn das Video keine Tonspur hat')
    ap.add_argument('--ohne-ast', action='store_true')
    ap.add_argument('--trennen', action='store_true', help='Stimme und Rest mit demucs trennen (nur wenn installiert, genauer)')
    ap.add_argument('--sprache', default='auto')
    ap.add_argument('--neu', action='store_true', help='Transkript neu erstellen')
    a = ap.parse_args()
    try:
        import numpy  # noqa: F401
    except ImportError:
        raise SystemExit('FEHLER: numpy fehlt in der Studio-Umgebung. "ms check" zeigt, wie es installiert wird.')
    video, vid, ordner, eintrag = Z.ziel_aufloesen(a.video, a.kanal, a.out)
    ordner.mkdir(parents=True, exist_ok=True)
    ziel_log = f'kanaele/{a.kanal}' if a.kanal else None
    audio = tonquelle(video, a.ton)
    if audio is None:
        ton = {'id': vid, 'datei': str(video), 'ton': False, 'erstellt': _ms.jetzt()}
        _ms.json_schreiben(ordner / 'ton.json', ton)
        (ordner / 'TON.md').write_text(f'# Ton {vid}\n\n' + md_abschnitt(ton), encoding='utf-8')
        print('Keine Tonspur (auch keine Audiodatei daneben). Mit --ton <datei> angeben.')
        return
    print(f'Ton aus {audio.name} …', flush=True)
    # Transkript: aus dem Register, aus dem Ordner oder neu
    tj = None
    if eintrag and eintrag.get('transkript'):
        import vorlagen as V
        tj = V.abs_pfad(eintrag['transkript'])
    if not tj or not tj.exists():
        tj = ordner / 'transkript.json'
    t = T.transkribieren(audio, tj, a.sprache, neu=a.neu) if (a.neu or not tj.exists()) else _ms.json_lesen(tj)
    if t and 'stats' not in t:
        t = T.auswerten(t)
    sprache = sprach_abschnitte(t)
    trennung = None
    with tempfile.TemporaryDirectory() as tmp:
        sp = spektrum(audio, Path(tmp))
        pausen = pausen_aus_audio(sp, sprache)
        musik = musik_heuristik(sp, sprache)
        getrennt = demucs_trennen(audio, Path(tmp)) if a.trennen else None
        if getrennt:
            # Effekte im Rest ohne Stimme suchen: dort stört keine Silbe
            (Path(tmp) / 'rest').mkdir()
            sp_rest = spektrum(getrennt[1], Path(tmp) / 'rest')
            eff = onsets(sp_rest, [(0.0, sp_rest['dauer'])])
            for e in eff:
                e['in_pause'] = bool(any(x <= e['t'] - 0.02 <= y for x, y in pausen))
                e['sicher'] = e['breitband'] >= 0.75
                e['quelle'] = 'rest ohne Stimme'
            l_st, l_rest = _ms.lufs(getrennt[0]), _ms.lufs(getrennt[1])
            trennung = {'stimme_lufs': round(l_st, 1), 'rest_lufs': round(l_rest, 1), 'rest_unter_stimme_db': round(l_st - l_rest, 1)}
            sp['roh_rest'] = sp_rest['roh']
        else:
            eff = onsets(sp, pausen)
        ast = ast_klassen(sp, eff, a.ohne_ast)
        if ast.get('status') == 'ok' and ast.get('musik_wahrscheinlichkeit') is not None:
            mw = ast['musik_wahrscheinlichkeit']
            if mw >= 0.25 and not musik['urteil'].startswith('ja'):
                musik['urteil'] = f'ja (AST hört Musik, {mw})'
            elif mw < 0.05 and musik['urteil'] == 'unklar':
                musik['urteil'] = f'nein (AST hört keine Musik, {mw})'
        schnitte = schnitte_zuordnen(eff, ordner)
        bild(ordner / 'ton.png', sp, sprache, eff, schnitte, pausen)
        dauer = sp['dauer']
    ton = {'id': vid, 'datei': str(video), 'quelle_ton': str(audio), 'ton': True, 'erstellt': _ms.jetzt(),
           'dauer': round(dauer, 2), **lautheit(audio), 'transkript': str(tj), 'sprache': (t or {}).get('stats', {}),
           'sprache_erkannt': (t or {}).get('sprache'), 'musik': musik, 'ast': ast, 'effekte': eff,
           'trennung': trennung, 'pausen': [[round(x, 2), round(y, 2)] for x, y in pausen],
           'sprechabschnitte': [[round(x, 2), round(y, 2)] for x, y in sprache]}
    _ms.json_schreiben(ordner / 'ton.json', ton)
    abschnitt = md_abschnitt(ton)
    (ordner / 'TON.md').write_text(f'# Ton {vid}\n\n' + abschnitt, encoding='utf-8')
    ergaenzt = analyse_md_ergaenzen(ordner, abschnitt)
    st = ton['sprache']
    print(f"Lautheit {ton['lufs']:.1f} LUFS · Sprache " + (f"{st['woerter_pro_s']} Wörter/s" if st.get('woerter') else 'keine') +
          f" · Musik: {musik['urteil']} · {len(eff)} Effekt-Kandidaten ({sum(1 for e in eff if e['sicher'])} sicher) · "
          f"AST: {ast.get('status')}")
    _ms.log(f"Ton zerlegt {vid}: {ton['lufs']:.1f} LUFS, Musik {musik['urteil'].split(' ')[0]}", wer='motion-analyse', ziel=ziel_log)
    print(ordner / 'ton.json')
    print(ordner / 'TON.md' if not ergaenzt else ordner / 'ANALYSE.md')
    print(ordner / 'ton.png')


if __name__ == '__main__':
    sys.exit(main())
