"""Ton-Mix einer Folge: Stimme + Effekte aus der Sound-Bibliothek (+ optional Musikbett) auf −14 LUFS.
  ms mix <folge> [--musik <datei>|aus] [--musik-abstand 20] [--dauer 31.5]
  ms mix <folge> --vorschlaege        Vorschläge der Bauer (build/sfx_*.json) mit passenden Sounds als Entwurf (mischt nicht).
                                      Beschreibung → Familie über _ton.FAMILIE_WOERTER (pop/appear → @plopp, click/tick → @klick,
                                      thud/land/drop → @landen, whoosh/swoosh/swipe → @whoosh, paper/page → @papier), margin_db
                                      aus dem Vorschlag (sonst 8)
Eingaben:
  voice/stimme.wav                     (ms stimme --tempo)
  build/assets/audio/ereignisse.json   [[zeit, "sound-id" | "@familie", margin_db, halbtoene?], …]
    zeit       Moment des sichtbaren Treffers in s. Der Anschlag des Sounds wird genau darauf gelegt.
    margin_db  dB unter der Stimme in der Umgebung (kleiner = lauter): Hook 0 bis 2, Haupttreffer 4 bis 6, Begleitung 7 bis 9, Kleinkram 10 bis 12.
    halbtoene  optional. Reihe = gleicher Eintrag innerhalb 0,45 s MIT Halbton-Angabe (+2, +4, +5 …): bleibt derselbe Sound.
  Musik: --musik <datei>, sonst kanaele/<k>/kit/ton-rezept.json "musik" (Pfad relativ zum Kanal), "musik_abstand_db".
  Dauer: build/index.html (Hauptkomposition), sonst Stimme + 0,47 s.
Regeln: jeder Sound gehörgerecht (K-gewichtet) gepegelt plus seine Korrektur trim_db aus dem Katalog (ohne Urteil geschätzt);
"@familie" wechselt reihum die Variante, nie zweimal dieselbe hintereinander; ein fester Allzweck-Sound wird bei Wiederholung
leicht in der Tonhöhe verschoben. Sicherheitsnetz: Effekte bleiben ≥ 10 dB unter der Stimme, solange sie spricht (Hook bis 0,6 s: 4 dB).
Gesperrte oder aussortierte Sounds brechen ab.
Ausgabe (build/assets/audio/): mix.wav (−14 LUFS ±0,5), _sfx_bus.wav (nur Effekte, für "ms sound gegenprobe"), mix_bericht.json
(Lautheit, Effekte vs. Stimme Median/Max, Hook-Abstand, Nutzung je Sound, Warnungen). Ziel: Median ≤ −12 dB, Max ≤ −10 dB."""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

import _ms
import _ton

SR = _ton.SR
MARGIN_VERSATZ = 1.5      # dB: margin 0 liegt so knapp unter der lokalen Stimme (aus Hörtests kalibriert)
BUS_UNTER_STIMME = 10.0   # dB: Effekt-Bus bleibt so weit unter der Stimme, solange sie spricht (8 war an dichten Stellen zu laut)
HOOK_UNTER_STIMME = 4.0   # dB: Ausnahme Hook (bis 0,6 s), damit der erste Treffer knallt
BUS_UNTER_PAUSE = 3.0     # dB unter der mittleren Stimme in Sprechpausen
HOOK_ENDE = 0.6
REIHE_S = 0.45
TONHOEHEN_RUNDE = [0, 1, -1, 2, -2, 1, -1]   # Halbtöne je weiterem Auftritt desselben festen Allzweck-Sounds
AUSLAUF = 0.47


# ---------------------------------------------------------------- Eingaben

def dauer_bestimmen(ordner: Path, a, stimme_dauer: float) -> tuple[float, str]:
    if a.dauer:
        return float(a.dauer), '--dauer'
    idx = ordner / 'build' / 'index.html'
    if idx.exists():
        t = idx.read_text(encoding='utf-8', errors='replace')
        for tag in re.findall(r'<[^>]*data-composition-id="main"[^>]*>', t):
            m = re.search(r'data-duration="([\d.]+)"', tag)
            if m:
                return float(m.group(1)), 'build/index.html'
    return round(stimme_dauer + AUSLAUF, 2), f'Stimme + {AUSLAUF} s'


def ereignisse_lesen(pfad: Path) -> list:
    roh = _ms.json_lesen(pfad)
    if roh is None:
        return []
    if not isinstance(roh, list):
        raise SystemExit(f'FEHLER: {pfad} muss eine Liste sein: [[zeit, "sound-id" | "@familie", margin_db, halbtoene?], …]')
    aus = []
    for i, e in enumerate(roh):
        try:
            if isinstance(e, dict):
                t = e.get('t', e.get('zeit'))
                sid = e.get('sound', e.get('id'))
                m = e.get('margin_db', e.get('margin', 8))
                ht = e.get('halbtoene')
                eintrag = [float(t), str(sid), float(m)] + ([float(ht)] if ht is not None else [])
            else:
                eintrag = [float(e[0]), str(e[1]), float(e[2])] + ([float(e[3])] if len(e) > 3 and e[3] is not None else [])
        except (TypeError, ValueError, IndexError, KeyError):
            raise SystemExit(f'FEHLER: {pfad.name} Eintrag {i + 1} ({e}) hat nicht das Format [zeit, "sound-id", margin_db, halbtoene?].')
        aus.append(eintrag)
    return sorted(aus, key=lambda e: e[0])


def pruefen_und_variieren(EV, k):
    """Löst Familien auf, prüft IDs und Sperren, verteilt Tonhöhen. Gibt [t, id, margin, halbtoene, eintrag] zurück."""
    idx = _ton.index(k)
    fam = k['familien']
    nutzbar = lambda sid: sid in idx and not idx[sid].get('gesperrt') and idx[sid].get('urteil') != 'raus'
    fehler = []
    for t, tok, *_ in EV:
        if tok.startswith('@'):
            name = tok[1:]
            if name not in fam:
                fehler.append(f'Familie {tok} gibt es nicht (vorhanden: {", ".join("@" + f for f in sorted(fam)) or "keine"}). ms sound familie')
            elif not [m for m in fam[name]['mitglieder'] if nutzbar(m)]:
                fehler.append(f'Familie {tok} hat keine nutzbare Variante (alle gesperrt oder raus).')
        elif tok not in idx:
            nah = difflib.get_close_matches(tok, list(idx), n=3, cutoff=0.5)
            fehler.append(f'Sound "{tok}" bei {t:.2f} s gibt es nicht' + (f' (meintest du {", ".join(nah)}?)' if nah else '') + '. ms sound suche')
        elif idx[tok].get('gesperrt'):
            fehler.append(f'Sound "{tok}" bei {t:.2f} s ist GESPERRT' + (f' ({idx[tok]["sperr_grund"]})' if idx[tok].get('sperr_grund') else '')
                          + '. Anderen Sound oder eine Familie nehmen.')
        elif idx[tok].get('urteil') == 'raus':
            fehler.append(f'Sound "{tok}" bei {t:.2f} s wurde beim Abhören aussortiert (urteil raus). Anderen Sound nehmen.')
    if fehler:
        raise SystemExit('FEHLER: Mix abgebrochen.\n  ' + '\n  '.join(sorted(set(fehler))))
    aus, zuletzt_t, reihe, fam_pos, fam_letzt, zaehler = [], {}, {}, {}, {}, {}
    for ev in EV:
        t, tok, margin = ev[:3]
        ht = ev[3] if len(ev) > 3 else 0
        in_reihe = len(ev) > 3 and tok in zuletzt_t and t - zuletzt_t[tok] <= REIHE_S
        zuletzt_t[tok] = t
        if in_reihe:
            sid, basis = reihe[tok]
        else:
            if tok.startswith('@'):
                mit = [m for m in fam[tok[1:]]['mitglieder'] if nutzbar(m)]
                i = fam_pos.get(tok, 0)
                if len(mit) > 1 and mit[i % len(mit)] == fam_letzt.get(tok):
                    i += 1
                sid = mit[i % len(mit)]
                fam_pos[tok] = i + 1
                fam_letzt[tok] = sid
            else:
                sid = tok
            n = zaehler.get(sid, 0)
            zaehler[sid] = n + 1
            basis = TONHOEHEN_RUNDE[n % len(TONHOEHEN_RUNDE)] if (idx[sid].get('art') or 'allzweck') == 'allzweck' else 0
            reihe[tok] = (sid, basis)
        aus.append([t, sid, margin, max(-5.0, min(7.0, ht + basis)), tok])
    return aus


# ---------------------------------------------------------------- Signal

def hochregal(x, f0=6000.0, gain_db=-3.0):
    """Höhenregal (RBJ-Kochbuch) auf ein Stereo-Signal."""
    import math
    from scipy.signal import lfilter
    A = 10 ** (gain_db / 40)
    w0 = 2 * math.pi * f0 / SR
    alpha = math.sin(w0) / 2 * math.sqrt(2)
    cw = math.cos(w0)
    b = [A * ((A + 1) + (A - 1) * cw + 2 * math.sqrt(A) * alpha), -2 * A * ((A - 1) + (A + 1) * cw),
         A * ((A + 1) + (A - 1) * cw - 2 * math.sqrt(A) * alpha)]
    a = [(A + 1) - (A - 1) * cw + 2 * math.sqrt(A) * alpha, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - 2 * math.sqrt(A) * alpha]
    return lfilter([v / a[0] for v in b], [v / a[0] for v in a], x, axis=0).astype('float32')


def sound_laden(s, halbtoene):
    np = _ton.np_()
    filt = f'asetrate={SR}*{2 ** (halbtoene / 12):.5f},aresample={SR}' if halbtoene else None
    sig = _ton.dekodiere(_ton.sound_datei(s), kanaele=2, von=s.get('von'), bis=s.get('bis'),
                         max_s=None if s.get('bis') is not None else 20, filt=filt)
    if not len(sig):
        raise SystemExit(f'FEHLER: {s["id"]} ist leer (Fenster von/bis prüfen: ms sound info {s["id"]}).')
    sig = sig[:max(1, _ton.ende_hoerbar(sig))].copy()
    sig *= 0.89 / (np.abs(sig).max() + 1e-9)
    fi, fo = min(len(sig), 48), min(len(sig), int(0.15 * SR) if s.get('bis') is not None else 576)
    sig[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)[:, None]
    sig[-fo:] *= np.linspace(1, 0, fo, dtype=np.float32)[:, None]
    return sig


def musik_laden(pfad: Path, gesamt: int):
    np = _ton.np_()
    r = _ms.befehl(['ffmpeg', '-nostdin', '-v', 'error', '-stream_loop', '-1', '-i', str(pfad), '-t', f'{gesamt / SR:.3f}',
                    '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-'], still=False, capture_output=True)
    m = np.frombuffer(r.stdout, dtype=np.float32).reshape(-1, 2).copy()
    return np.pad(m, ((0, max(0, gesamt - len(m))), (0, 0)))[:gesamt]


# ---------------------------------------------------------------- Mix

def mischen(ordner: Path, a):
    np = _ton.np_()
    audio = ordner / 'build' / 'assets' / 'audio'
    stimme_p = ordner / 'voice' / 'stimme.wav'
    if not stimme_p.exists():
        raise SystemExit('FEHLER: voice/stimme.wav fehlt. Erst "ms stimme <folge> --tempo".')
    k = _ton.katalog_lesen()
    idx = _ton.index(k)
    EV = ereignisse_lesen(audio / 'ereignisse.json')
    warnungen = []
    if not EV:
        warnungen.append('Keine Ereignisse (build/assets/audio/ereignisse.json fehlt oder ist leer): nur Stimme und Musik.')
    EV = pruefen_und_variieren(EV, k)

    stimme = _ton.dekodiere(stimme_p, kanaele=2)
    DUR, dauer_quelle = dauer_bestimmen(ordner, a, len(stimme) / SR)
    gesamt = int(round(DUR * SR))
    stimme = np.pad(stimme, ((0, max(0, gesamt - len(stimme))), (0, 0)))[:gesamt]
    vk = _ton.k_filter(stimme.mean(axis=1))
    aktiv = np.abs(stimme.mean(axis=1)) > 1e-3
    vk_alle = float(-0.691 + 10 * np.log10(np.mean(vk[aktiv] ** 2) + 1e-12)) if aktiv.any() else -30.0

    def vk_lokal(anker):
        seg = vk[max(0, anker - int(0.2 * SR)):min(gesamt, anker + int(0.5 * SR))]
        v = float(-0.691 + 10 * np.log10(np.mean(seg ** 2) + 1e-12)) if len(seg) else vk_alle
        return max(v, vk_alle - 3)

    bus = np.zeros((gesamt, 2), dtype=np.float32)
    bus_ref = np.zeros_like(bus)       # ohne unter_stimme_db: Grundlage fürs Sicherheitsnetz
    protokoll, ausserhalb = [], []
    for t, sid, margin, ht, tok in EV:
        if t >= DUR or t < -0.5:
            ausserhalb.append(f'{t:.2f} s {tok}')
            continue
        s = idx[sid]
        sig = sound_laden(s, ht)
        ans = _ton.anschlag(sig)
        anker = int(round(t * SR))
        beginn = anker - int(round(ans * SR))
        kopf = max(0, -beginn)                      # Sound vor 0 s: Anfang abschneiden
        beginn = max(0, beginn)
        ende = min(gesamt, beginn + len(sig) - kopf)
        if s.get('trim_db') is not None and s.get('urteil'):
            trim, trim_quelle = float(s['trim_db']), 'Urteil'
        elif s.get('trim_db') is not None:
            trim, trim_quelle = float(s['trim_db']), 'gesetzt'
        else:
            trim, trim_quelle = _ton.trim_geschaetzt(len(sig) / SR, s.get('hell', 0)), 'geschätzt'
        g_k = vk_lokal(anker) - (margin + MARGIN_VERSATZ) - _ton.k_laut(sig)
        seg = vk[beginn:max(beginn + 1, ende)]
        spricht_anteil = float(np.mean(_ton.gleitend(seg, int(0.05 * SR), int(0.4 * SR))[1] > vk_alle - 12)) if len(seg) > int(0.4 * SR) \
            else float(-0.691 + 10 * np.log10(np.mean(seg ** 2) + 1e-12) > vk_alle - 10)
        us = float(s.get('unter_stimme_db') or 0.0) if spricht_anteil > 0.5 else 0.0
        gain = min(g_k + trim, -1.0 - 20 * np.log10(np.abs(sig).max() + 1e-9), 14.0)
        if ende > beginn:
            stueck = sig[kopf:kopf + ende - beginn]
            bus_ref[beginn:ende] += stueck * 10 ** (gain / 20)
            bus[beginn:ende] += stueck * 10 ** ((gain + us) / 20)
        protokoll.append({'t': round(t, 3), 'eintrag': tok, 'sound': sid, 'margin_db': margin, 'halbtoene': ht,
                          'gain_db': round(float(gain + us), 1), 'trim_db': trim, 'trim_quelle': trim_quelle,
                          'unter_stimme_db': us, 'dauer': round(len(sig) / SR, 3), 'spricht': round(spricht_anteil, 2),
                          'tief': s.get('tief', 0), 'hell': s.get('hell', 0)})

    # Sicherheitsnetz: Effekt-Bus nie zu nah an die Stimme (rechnet mit bus_ref, damit unter_stimme_db danach noch wirkt)
    HOP, WIN = int(0.05 * SR), int(0.4 * SR)
    ib, lb = _ton.gleitend(_ton.k_filter(bus_ref.mean(axis=1)), HOP, WIN)
    del bus_ref
    _, lv = _ton.gleitend(vk, HOP, WIN)
    spricht = lv > vk_alle - 12
    erlaubt = np.where(spricht, lv - BUS_UNTER_STIMME, vk_alle - BUS_UNTER_PAUSE)
    erlaubt = np.where(ib < int(HOOK_ENDE * SR), np.maximum(erlaubt, lv - HOOK_UNTER_STIMME), erlaubt)
    schnitt = np.minimum(0.0, erlaubt - lb)
    g = 10 ** (schnitt / 20)
    huelle = np.ones(gesamt)
    for i0, gi in zip(ib[g < 1], g[g < 1]):
        huelle[i0:i0 + WIN] = np.minimum(huelle[i0:i0 + WIN], gi)
    rel = np.exp(-1 / (0.25 * SR))
    glatt = np.empty_like(huelle)
    y = 1.0
    for i in range(0, gesamt, 240):           # 5-ms-Blöcke: sofort runter, langsam (250 ms) wieder hoch
        blk = huelle[i:i + 240].min()
        y = blk if blk < y else y + (blk - y) * (1 - rel ** 240)
        glatt[i:i + 240] = y
    bus *= glatt[:, None].astype(np.float32)
    bus = hochregal(bus)
    netz_anteil = float(np.mean(schnitt[spricht] < -0.5)) if spricht.any() else 0.0

    # Musikbett (optional)
    musik_info = None
    musik_pfad = None
    rezept = {}
    st = _ms.status_lesen(ordner)
    if st.get('kanal'):
        rezept = _ms.json_lesen(_ms.arbeit() / 'kanaele' / st['kanal'] / 'kit' / 'ton-rezept.json', {}) or {}
    if a.musik and a.musik != 'aus':
        musik_pfad = Path(a.musik).expanduser()
    elif a.musik != 'aus' and rezept.get('musik'):
        mp = Path(str(rezept['musik'])).expanduser()
        musik_pfad = mp if mp.is_absolute() else _ms.arbeit() / 'kanaele' / st['kanal'] / mp
    gemisch = stimme + bus
    if musik_pfad:
        if not musik_pfad.exists():
            raise SystemExit(f'FEHLER: Musik {musik_pfad} fehlt.')
        abstand = float(a.musik_abstand if a.musik_abstand is not None else rezept.get('musik_abstand_db', 20))
        duck = float(rezept.get('musik_ducking_db', 4))
        mus = musik_laden(musik_pfad, gesamt)
        _, lm = _ton.gleitend(_ton.k_filter(mus.mean(axis=1)), HOP, WIN)
        n = min(len(lm), len(lv))
        if spricht[:n].any() and (lm[:n] > -70).any():
            gain_m = float(np.median((lv[:n] - lm[:n])[spricht[:n]])) - abstand + duck
        else:
            gain_m = -abstand
        # Ducking: während die Stimme spricht duck dB leiser (Angriff 50 ms, Freigabe 400 ms)
        ziel = np.ones(gesamt)
        for i0, sp in zip(ib[:n], spricht[:n]):
            if sp:
                ziel[i0:i0 + HOP] = 10 ** (-duck / 20)
        hk = np.empty_like(ziel)
        y = 1.0
        an, ab = np.exp(-1 / (0.05 * SR)), np.exp(-1 / (0.4 * SR))
        for i in range(0, gesamt, 240):
            blk = ziel[i:i + 240].min()
            y = y + (blk - y) * (1 - (an if blk < y else ab) ** 240)
            hk[i:i + 240] = y
        rampe = np.minimum(1, np.arange(gesamt) / (0.3 * SR)) * np.minimum(1, (gesamt - np.arange(gesamt)) / (1.0 * SR))
        mus *= (10 ** (gain_m / 20) * hk * rampe)[:, None].astype(np.float32)
        gemisch = gemisch + mus
        musik_info = {'datei': musik_pfad.name, 'abstand_db': abstand, 'ducking_db': duck, 'gain_db': round(gain_m, 1)}

    roh = audio / '_mix_roh.wav'
    _ton.schreibe_wav(roh, gemisch, gleitkomma=True)
    _ton.schreibe_wav(audio / '_sfx_bus.wav', bus)
    lufs = _ton.auf_lufs(roh, audio / 'mix.wav', -14.0, -1.5)
    roh.unlink(missing_ok=True)

    # Bericht
    _, lb2 = _ton.gleitend(_ton.k_filter(bus.mean(axis=1)), HOP, WIN)
    nach_hook = ib >= int(HOOK_ENDE * SR)
    rel_db = (lb2 - lv)[spricht & (lb2 > -70) & nach_hook]
    rel_hook = (lb2 - lv)[spricht & (lb2 > -70) & ~nach_hook]
    evs = {'median': round(float(np.median(rel_db)), 1) if len(rel_db) else None,
           'p90': round(float(np.percentile(rel_db, 90)), 1) if len(rel_db) else None,
           'max': round(float(rel_db.max()), 1) if len(rel_db) else None,
           'hook_max': round(float(rel_hook.max()), 1) if len(rel_hook) else None}
    hook_ev = [p for p in protokoll if p['t'] < 0.25]
    # Hook-Abstand: hörbarer Teil des Effekt-Busses in den ersten 0,6 s gegen die typische Stimme (gleiches Maß wie margin)
    hook_bus = _ton.k_laut(bus[:int(HOOK_ENDE * SR)])
    hook_abstand = round(vk_alle - hook_bus, 1) if hook_bus > -100 else None

    nutzung, auftritte = {}, {}
    for t, sid, margin, ht, tok in EV:
        nutzung[sid] = nutzung.get(sid, 0) + 1
    letzt = {}
    for t, sid, margin, ht, tok in EV:          # Reihen (≤ 0,45 s) zählen als ein Auftritt
        if sid not in letzt or t - letzt[sid] > REIHE_S:
            auftritte.setdefault(sid, []).append((t, tok))
        letzt[sid] = t
    fest_viel = {sid: len(v) for sid, v in auftritte.items()
                 if (idx[sid].get('art') or 'allzweck') == 'allzweck' and sum(1 for _, tok in v if not tok.startswith('@')) > 3}
    nische = {sid: len(v) for sid, v in auftritte.items() if idx[sid].get('art') == 'nische' and len(v) > 1}
    zeiten = sorted(p['t'] for p in protokoll)
    teppich = sorted({round(t0, 2) for t0 in zeiten if sum(1 for t in zeiten if t0 <= t < t0 + 0.5) > 6})
    ohne_urteil = sorted({p['sound'] for p in protokoll if p['trim_quelle'] == 'geschätzt'})
    sub_allein = [p for p in protokoll if (p['tief'] or 0) > 0.9 and not any(
        abs(q['t'] - p['t']) <= 0.06 and (q['tief'] or 0) < 0.5 for q in protokoll if q is not p)]
    lang_unter_rede = [p for p in protokoll if p['dauer'] > 1.0 and p['spricht'] > 0.5 and p['margin_db'] < 10]

    if ausserhalb:
        warnungen.append(f'{len(ausserhalb)} Ereignisse außerhalb der Dauer {DUR:.2f} s übersprungen: {", ".join(ausserhalb[:5])}')
    if EV and not hook_ev:
        warnungen.append('Kein Hook-Sound auf Bild 1 (kein Ereignis vor 0,25 s). Der erste Treffer soll sofort hörbar sein.')
    elif hook_abstand is not None and hook_ev and hook_abstand > 4:
        warnungen.append(f'Hook-Sound zu leise: {hook_abstand:.1f} dB unter der Stimme (Soll ≤ 4). margin des ersten Treffers auf 0 bis 2.')
    if evs['median'] is not None and evs['median'] > -12:
        warnungen.append(f'Effekte im Schnitt zu laut: Median {evs["median"]} dB unter der Stimme (Soll ≤ −12). margins erhöhen.')
    if netz_anteil > 0.25:
        warnungen.append(f'Sicherheitsnetz griff in {netz_anteil * 100:.0f} % der Sprechfenster: margins insgesamt zu klein gewählt.')
    if teppich:
        warnungen.append(f'Teppich-Gefahr: mehr als 6 Sounds in 0,5 s ab {", ".join(f"{t:.2f}" for t in teppich[:6])} s.')
    if fest_viel:
        warnungen.append(f'Zu wenig Abwechslung: fester Allzweck-Sound öfter als 3× (Reihen einmal gezählt): {fest_viel}. Familie "@…" nehmen.')
    if nische:
        warnungen.append(f'Nischen-Sound mehrfach (nur ok, wenn es dieselbe Sache ist): {nische}.')
    if ohne_urteil:
        warnungen.append(f'{len(ohne_urteil)} Sounds ohne Urteil (Korrektur geschätzt), auf die Abhörseite: {", ".join(ohne_urteil[:8])}'
                         + (' …' if len(ohne_urteil) > 8 else ''))
    if sub_allein:
        warnungen.append('Sub-Boom ohne Mitten-Impact (Handylautsprecher geben unter 150 Hz kaum etwas wieder): '
                         + ', '.join(f'{p["t"]:.2f} s {p["sound"]}' for p in sub_allein[:5]))
    if lang_unter_rede:
        warnungen.append('Lange Sounds unter laufender Rede (besser in Sprechpausen legen oder margin 10 bis 12): '
                         + ', '.join(f'{p["t"]:.2f} s {p["sound"]}' for p in lang_unter_rede[:5]))
    if abs(lufs + 14) > 0.5:
        warnungen.append(f'Gesamtlautheit {lufs:.1f} LUFS außerhalb −14 ±0,5.')

    bericht = {'zeit': _ms.jetzt(), 'dauer': DUR, 'dauer_quelle': dauer_quelle, 'lufs': round(lufs, 2),
               'effekte_vs_stimme_db': evs, 'hook_abstand_db': hook_abstand, 'netz_anteil': round(netz_anteil, 3),
               'ereignisse_anzahl': len(protokoll), 'verschiedene_sounds': len(nutzung),
               'ueber_familien': sum(1 for e in EV if e[4].startswith('@')), 'nutzung': dict(sorted(nutzung.items(), key=lambda kv: -kv[1])),
               'musik': musik_info, 'warnungen': warnungen, 'ereignisse': protokoll,
               'grenzen': {'bus_unter_stimme_db': BUS_UNTER_STIMME, 'hook_unter_stimme_db': HOOK_UNTER_STIMME, 'ziel_lufs': -14}}
    _ms.json_schreiben(audio / 'mix_bericht.json', bericht)

    print(f'Mix: {len(protokoll)} Ereignisse, {len(nutzung)} verschiedene Sounds ({bericht["ueber_familien"]} über Familien), '
          f'Dauer {DUR:.2f} s ({dauer_quelle})' + (f', Musik {musik_info["datei"]} {musik_info["abstand_db"]:.0f} dB unter der Stimme' if musik_info else ''))
    print(f'Gesamt {lufs:.2f} LUFS (Soll −14 ±0,5) | Effekte vs. Stimme, solange sie spricht: Median {evs["median"]} dB, '
          f'90 % {evs["p90"]} dB, Max {evs["max"]} dB (Grenze −{BUS_UNTER_STIMME:.0f}) | Hook-Max {evs["hook_max"]} dB '
          f'| Hook-Abstand {hook_abstand} dB (Soll ≤ 4) | Netz griff in {netz_anteil * 100:.0f} % der Sprechfenster')
    print('Nutzung:', ', '.join(f'{k_}×{v}' for k_, v in list(bericht['nutzung'].items())[:12]))
    for w in warnungen:
        print('PRÜFEN:', w)
    _ms.log(f'Mix: {lufs:.1f} LUFS, Effekte Median {evs["median"]} dB unter der Stimme, {len(warnungen)} Hinweise',
            ziel=_ms.ziel_name(ordner), art='warnung' if warnungen else 'info')
    for p in (audio / 'mix.wav', audio / '_sfx_bus.wav', audio / 'mix_bericht.json'):
        print(p)


# ---------------------------------------------------------------- Vorschläge der Bauer

def vorschlaege(ordner: Path, n: int):
    """Liest build/sfx_*.json (Bauer schreiben dort, wo ein Sound hingehört) und sucht passende Sounds.
    Schreibt build/assets/audio/ereignisse_vorschlag.json + .md. ereignisse.json bleibt unberührt: die Regie kuratiert."""
    import sound as _sound
    dateien = sorted((ordner / 'build').glob('sfx_*.json'))
    if not dateien:
        raise SystemExit('Keine Vorschläge (build/sfx_*.json fehlt). Die Bauer schreiben sie beim Szenenbau.')
    k = _ton.katalog_lesen()
    idx = _ton.index(k)
    entwurf, md = [], ['# Sound-Vorschläge der Bauer', '', 'Entwurf, nicht gemischt. Die Regie wählt aus, ändert margins und schreibt',
                       '`build/assets/audio/ereignisse.json`. Nicht jede Mikrobewegung vertonen.', '']
    for d in dateien:
        roh = _ms.json_lesen(d, []) or []
        md += [f'## {d.name}', '']
        for e in roh:
            if isinstance(e, list) and len(e) >= 3:
                tok = str(e[1])
                ok = tok.startswith('@') and tok[1:] in k['familien'] or tok in idx
                entwurf.append([float(e[0]), tok, float(e[2])] + ([e[3]] if len(e) > 3 else []))
                md.append(f'- {float(e[0]):.2f} s `{tok}` margin {e[2]}' + ('' if ok else '  **(nicht im Katalog)**'))
                continue
            if not isinstance(e, dict):
                continue
            t = e.get('t', e.get('zeit'))
            text = str(e.get('sound') or e.get('beschreibung') or e.get('event') or '').strip()
            if t is None or not text:
                continue
            treffer = _sound.suche(text, n)[0] if k['sounds'] else []
            kand = [s['id'] for s in treffer]
            fam = _ton.familie_aus_text(text, k['familien'])
            wahl = f'@{fam}' if fam else (kand[0] if kand else None)
            if wahl:
                entwurf.append([round(float(t), 3), wahl, float(e.get('margin_db', e.get('margin', 8)))])
            if fam:
                ziel = f'`@{fam}` (Familie)' + (f', sonst {", ".join(f"`{c}`" for c in kand)}' if kand else '')
            else:
                ziel = ', '.join(f'`{c}`' for c in kand) or 'nichts gefunden (Lücke, Skill motion-sound-bibliothek)'
            md.append(f'- {float(t):.2f} s {e.get("scene", e.get("szene", ""))} {e.get("event", "")}: „{text}“ → {ziel}')
        md.append('')
    audio = ordner / 'build' / 'assets' / 'audio'
    _ms.json_schreiben(audio / 'ereignisse_vorschlag.json', sorted(entwurf, key=lambda x: x[0]))
    (audio / 'ereignisse_vorschlag.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(f'{len(entwurf)} {"Vorschlag" if len(entwurf) == 1 else "Vorschläge"} aus {len(dateien)} '
          f'{"Datei" if len(dateien) == 1 else "Dateien"}.')
    print(audio / 'ereignisse_vorschlag.json')
    print(audio / 'ereignisse_vorschlag.md')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folge')
    ap.add_argument('--musik', help='Musikdatei für das Bett oder "aus"')
    ap.add_argument('--musik-abstand', type=float, help='dB, die die Musik unter der Stimme liegt (Standard 20)')
    ap.add_argument('--dauer', type=float, help='Gesamtdauer in s (Standard: build/index.html, sonst Stimme + 0,47)')
    ap.add_argument('--vorschlaege', action='store_true', help='nur Vorschläge der Bauer mit passenden Sounds als Entwurf')
    ap.add_argument('--n', type=int, default=3, help='Kandidaten je Vorschlag')
    a = ap.parse_args()
    ordner = _ms.ziel_pfad(a.folge)
    if a.vorschlaege:
        vorschlaege(ordner, a.n)
    else:
        mischen(ordner, a)


if __name__ == '__main__':
    sys.exit(main())
