"""Wortzeiten der fertigen Stimme auf den Anzeigetext legen und Caption-Gruppen bauen.
  ms woerter <folge> [--max 3] [--sprache de]
Liest voice/stimme.wav (aus "ms stimme --tempo") und voice/script.json "display" (so, wie es in den Captions steht:
Ziffern statt Zahlwörter, richtige Schreibweise der Namen). Whisper hört die Stimme wortgenau, jedes Anzeigewort bekommt
Start und Ende: direkt (gleiches Wort), über die Schreibung (z. B. "10-mal" ↔ "10 mal") oder geschätzt (dazwischen verteilt).
Ausgabe:
  voice/woerter.json    [{"w": "Anzeigewort", "s": 1.23, "e": 1.51}, …]
  voice/timing.txt      jede Satzzeile als wort@sekunde (Grundlage fürs Storyboard)
  build/captions.json   [{"text": "…", "s": 0.0, "e": 1.2, "woerter": [{"w", "s", "e"}, …]}, …]
                        Bleibt unberührt, wenn eine Gruppe "hand": true trägt (von Hand übernommene Gruppen des Originals).
                        --captions-neu überschreibt sie trotzdem (die alte Datei wandert nach build/_ueberholt/).
  voice/woerter_check.txt  Zuordnung und Abweichungen
Gesamtdauer des Videos (wie ms szenen und ms render): Länge von voice/stimme.wav + Auslauf (Standard 0,47 s,
ms szenen --auslauf). Gruppen, die darüber hinausragen, kappt ms szenen am Ende.
"w" behält die Satzzeichen des Anzeigetexts (der Caption-Stil entscheidet, was angezeigt wird: "satzzeichen_weg").
Pilot (voice/stimme.json aus "ms stimme --original"): die Wortzeiten kommen aus dem Transkript des ganzen Originals,
verschoben um den Fensterbeginn (Whisper setzt Wörter am Schnittrand eines Ausschnitts oft 0,3 bis 1 s daneben).
--whisper hört stattdessen voice/stimme.wav neu.
Gruppen nach kanaele/<k>/kit/captions.json (max_woerter 3, max_zeichen 18, pause_bruch 0,35 s, wie "ms szenen"):
Bruch an Satzende, Komma und Sprechpausen, Reste ausgeglichen (4 Wörter → 2 + 2, nicht 3 + 1). Ziel: ≥ 85 % zugeordnet."""
from __future__ import annotations

import argparse
import difflib
import math
import sys

import _bau
import _ms
import _ton

SATZENDE = ('.', '?', '!', ':', '…')
WEICH = (',', ';', '\u2013', '\u2014')   # Komma, Semikolon, Gedankenstriche im Anzeigetext


def ohne_satzzeichen(w: str) -> str:
    w = w.strip()
    while len(w) > 1 and w[-1] in ',.;:':
        w = w[:-1]
    return w


# Zahlwörter → Ziffern, damit "2" im Anzeigetext und "zwei" bei Whisper (oder umgekehrt) direkt zusammenpassen
ZAHLEN = {}
for _i, (_de, _en) in enumerate(zip(
        'null eins zwei drei vier fünf sechs sieben acht neun zehn elf zwölf dreizehn vierzehn fünfzehn sechzehn siebzehn achtzehn neunzehn zwanzig'.split(),
        'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split())):
    ZAHLEN[_de] = ZAHLEN[_en] = str(_i)
ZAHLEN.update({'dreißig': '30', 'vierzig': '40', 'fünfzig': '50', 'sechzig': '60', 'siebzig': '70',
               'achtzig': '80', 'neunzig': '90', 'hundert': '100', 'tausend': '1000', 'thirty': '30', 'forty': '40', 'fifty': '50',
               'hundred': '100', 'thousand': '1000', 'zweimal': '2mal', 'dreimal': '3mal', 'zehnmal': '10mal'})


def norm(w: str) -> str:
    n = _ton.norm_wort(w)
    return ZAHLEN.get(n, n)


def zuordnen(gehoert, anzeige):
    """gehoert: [{"w", "s", "e"}] aus Whisper. anzeige: Liste der Anzeigewörter (mit Satzzeichen).
    Gibt Liste [s, e, art] je Anzeigewort zurück, art = direkt | schreibung | geschaetzt."""
    A = [norm(w['w']) for w in gehoert]
    keep = [i for i, a in enumerate(A) if a]
    G = [gehoert[i] for i in keep]
    A = [A[i] for i in keep]
    B = [norm(w) for w in anzeige]
    erg = [None] * len(anzeige)
    sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                erg[j1 + k] = [G[i1 + k]['s'], G[i1 + k]['e'], 'direkt']
        elif tag == 'replace':
            # Zeichenweise innerhalb des Blocks: fängt Getrennt-/Zusammenschreibung, Bindestriche, Ziffern-Varianten
            a_str, a_ix, a_pos = '', [], []
            for i in range(i1, i2):
                for p, ch in enumerate(A[i]):
                    a_str += ch
                    a_ix.append(i)
                    a_pos.append((p, len(A[i])))
            b_grenzen, b_str = [], ''
            for j in range(j1, j2):
                b_grenzen.append((len(b_str), len(b_str) + len(B[j])))
                b_str += B[j]
            m = difflib.SequenceMatcher(None, a_str, b_str, autojunk=False)
            b_zu_a = {}
            for blk in m.get_matching_blocks():
                for q in range(blk.size):
                    b_zu_a[blk.b + q] = blk.a + q

            def zeit(ai, ende=False):
                i = a_ix[ai]
                p, n = a_pos[ai]
                s, e = G[i]['s'], G[i]['e']
                return s + (e - s) * ((p + (1 if ende else 0)) / max(1, n))

            for jj, (b0, b1) in enumerate(b_grenzen):
                if b1 <= b0:
                    continue
                treffer = [b_zu_a[c] for c in range(b0, b1) if c in b_zu_a]
                if len(treffer) >= max(1, math.ceil(0.6 * (b1 - b0))):
                    erg[j1 + jj] = [zeit(treffer[0]), zeit(treffer[-1], True), 'schreibung']
    # Lücken schätzen: zwischen bekannten Nachbarn gleichmäßig verteilen
    n = len(erg)
    ende_ges = G[-1]['e'] if G else 0.5
    i = 0
    while i < n:
        if erg[i] is not None:
            i += 1
            continue
        j = i
        while j < n and erg[j] is None:
            j += 1
        t0 = erg[i - 1][1] if i > 0 else (G[0]['s'] if G else 0.0)
        t1 = erg[j][0] if j < n else max(t0 + 0.3 * (j - i), ende_ges)
        schritt = (t1 - t0) / (j - i) if j > i else 0
        for k in range(i, j):
            erg[k] = [t0 + schritt * (k - i), t0 + schritt * (k - i + 1), 'geschaetzt']
        i = j
    # Ordnung erzwingen: Starts steigen, kein Wort endet nach dem Start des nächsten, Mindestlänge 40 ms
    for k in range(n):
        if k > 0 and erg[k][0] < erg[k - 1][0]:
            erg[k][0] = erg[k - 1][0]
        erg[k][1] = max(erg[k][1], erg[k][0] + 0.04)
    for k in range(n - 1):
        if erg[k][1] > erg[k + 1][0] >= erg[k][0] + 0.04:
            erg[k][1] = erg[k + 1][0]
    return erg


def stil_lesen(st, a) -> dict:
    """Gruppierungs-Regeln aus kanaele/<k>/kit/captions.json (gleiche Felder wie "ms szenen"), sonst Standard."""
    stil = {'max_woerter': 3, 'max_zeichen': 18, 'pause_bruch': 0.35}
    if st.get('kanal'):
        k = _ms.json_lesen(_ms.arbeit() / 'kanaele' / st['kanal'] / 'kit' / 'captions.json', {}) or {}
        for key in stil:
            if isinstance(k.get(key), (int, float)) and k[key] > 0:
                stil[key] = k[key]
    if a.max:
        stil['max_woerter'] = a.max
    return stil


def passt(ws, stil) -> bool:
    return len(ws) <= stil['max_woerter'] and sum(len(ohne_satzzeichen(w['w'])) + 1 for w in ws) - 1 <= stil['max_zeichen']


def teilen(ws, stil):
    """Eine Phrase in Gruppen teilen: so wenige wie möglich, gleichmäßig (4 Wörter → 2 + 2, nicht 3 + 1)."""
    for teile in range(math.ceil(len(ws) / stil['max_woerter']), len(ws) + 1):
        basis, rest = divmod(len(ws), teile)
        aus, pos = [], 0
        for t in range(teile):
            g = basis + (1 if t < rest else 0)
            aus.append(ws[pos:pos + g])
            pos += g
        if all(passt(g, stil) or len(g) == 1 for g in aus):
            return aus
    return [[w] for w in ws]


def gruppen(woerter, stil):
    """Caption-Gruppen: harte Brüche an Satzende und Sprechpausen, weiche an Komma, jede Phrase ausgeglichen geteilt."""
    phrasen, cur = [], []
    for i, w in enumerate(woerter):
        cur.append(w)
        pause = woerter[i + 1]['s'] - w['e'] if i + 1 < len(woerter) else 0
        hart = w['w'].endswith(SATZENDE) or pause >= stil['pause_bruch']
        if hart or w['w'].endswith(WEICH):
            phrasen.append((cur, hart))
            cur = []
    if cur:
        phrasen.append((cur, True))
    # Ein Wort vor einem Komma („Ja, …“) mit der nächsten Phrase verbinden, wenn es passt
    zusammen, k = [], 0
    while k < len(phrasen):
        ws, hart = phrasen[k]
        if not hart and len(ws) == 1 and k + 1 < len(phrasen) and passt(ws + phrasen[k + 1][0], stil):
            ws = ws + phrasen[k + 1][0]
            k += 1
        zusammen.append(ws)
        k += 1
    gruppen_ws = [g for ws in zusammen for g in teilen(ws, stil)]
    aus = []
    for gi, ws in enumerate(gruppen_ws):
        nxt = gruppen_ws[gi + 1][0]['s'] if gi + 1 < len(gruppen_ws) else ws[-1]['e'] + 0.6
        aus.append({'text': ' '.join(w['w'] for w in ws), 's': ws[0]['s'], 'e': round(min(nxt, ws[-1]['e'] + 0.25), 2),
                    'woerter': ws})
    return aus


def pilot_transkript(v):
    """Beim Pilot: Wörter des Original-Transkripts im Fenster aus voice/stimme.json, Zeiten ab Fensterbeginn. Sonst None."""
    info = _ms.json_lesen(v / 'stimme.json', {}) or {}
    if info.get('original_von') is None or not info.get('original_id'):
        return None
    p = _ms.arbeit() / 'vorlagen' / 'transkripte' / f"{info['original_id']}.json"
    d = _ms.json_lesen(p) if p.exists() else None
    if not d or not d.get('woerter'):
        return None
    von, bis = float(info['original_von']), float(info.get('original_bis') or 1e9)
    ws = [{'w': str(w['w']).strip(), 's': round(max(0.0, float(w['s']) - von), 3), 'e': round(min(float(w['e']), bis) - von, 3)}
          for w in d['woerter'] if str(w['w']).strip() and von - 0.02 <= (float(w['s']) + float(w['e'])) / 2 <= bis + 0.02]
    if not ws:
        return None
    return {'text': ' '.join(w['w'] for w in ws), 'woerter': ws, 'quelle': p.name, 'von': von}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folge')
    ap.add_argument('--max', type=int, help='höchstens so viele Wörter pro Caption-Gruppe')
    ap.add_argument('--sprache', help='Sprache für Whisper (Standard: script.json "sprache" oder automatisch)')
    ap.add_argument('--whisper', action='store_true', help='Pilot: stimme.wav neu hören statt das Original-Transkript zu nehmen')
    ap.add_argument('--captions-neu', action='store_true', help='build/captions.json auch dann neu schreiben, wenn sie von Hand ist')
    a = ap.parse_args()

    ordner = _ms.ziel_pfad(a.folge)
    st = _ms.status_lesen(ordner)
    v = ordner / 'voice'
    s = _ms.json_lesen(v / 'script.json')
    if not s or not str(s.get('display', '')).strip():
        raise SystemExit(f'FEHLER: {v}/script.json fehlt oder hat kein "display".')
    stimme = v / 'stimme.wav'
    if not stimme.exists():
        raise SystemExit('FEHLER: voice/stimme.wav fehlt. Erst "ms stimme <folge> --tempo".')
    roh = str(s['display']).split()
    t = None if a.whisper else pilot_transkript(v)
    if t:
        print(f'Pilot: Wortzeiten aus {t["quelle"]} (Fenster ab {t["von"]:.2f} s), nicht neu gehört.')
    else:
        t = _ms.transkribiere(stimme, a.sprache or s.get('sprache') or 'auto')
    if not t['woerter']:
        raise SystemExit('FEHLER: Whisper hat in voice/stimme.wav nichts gehört. Datei anhören.')
    zeiten = zuordnen(t['woerter'], roh)
    woerter = [{'w': w, 's': round(z[0], 2), 'e': round(z[1], 2)} for w, z in zip(roh, zeiten)]
    n = len(woerter)
    direkt = sum(1 for z in zeiten if z[2] == 'direkt')
    schreib = sum(1 for z in zeiten if z[2] == 'schreibung')
    quote = (direkt + schreib) / max(1, n)

    _ms.json_schreiben(v / 'woerter.json', woerter)
    caps = gruppen(woerter, stil_lesen(st, a))
    cap_datei = ordner / 'build' / 'captions.json'
    alt = _ms.json_lesen(cap_datei)
    von_hand = isinstance(alt, list) and any(isinstance(g, dict) and g.get('hand') for g in alt)
    if von_hand and not a.captions_neu:
        print(f'build/captions.json ist von Hand ("hand": true) und bleibt. Neu gruppieren: --captions-neu.')
    else:
        if von_hand:
            ablage = ordner / 'build' / '_ueberholt'
            ablage.mkdir(parents=True, exist_ok=True)
            cap_datei.replace(ablage / f'captions_hand_{_ms.jetzt()[:19].replace(":", "")}.json')
        _ms.json_schreiben(cap_datei, caps)
    ende = t['woerter'][-1]['e']
    auslauf = _bau.index_auslauf(ordner / 'build')
    auslauf = _bau.AUSLAUF if auslauf is None else auslauf
    wav_dauer = _bau.dauer(stimme)
    zeilen, satz = [], []
    for w, r in zip(woerter, roh):
        satz.append(f"{ohne_satzzeichen(w['w'])}@{w['s']:.2f}")
        if r.endswith(SATZENDE):
            zeilen.append(' '.join(satz))
            satz = []
    if satz:
        zeilen.append(' '.join(satz))
    (v / 'timing.txt').write_text('\n'.join(zeilen) + f'\n\nStimme endet bei {ende:.2f} s\n', encoding='utf-8')
    unsicher = [f"{w['w']}@{w['s']:.2f} ({z[2]})" for w, z in zip(woerter, zeiten) if z[2] != 'direkt']
    (v / 'woerter_check.txt').write_text(
        f'{n} Anzeigewörter: {direkt} direkt, {schreib} über die Schreibung, {n - direkt - schreib} geschätzt.\n'
        f'Zugeordnet: {quote * 100:.1f} % (Ziel ≥ 85 %)\n\nNicht direkt zugeordnet:\n' + '\n'.join(unsicher) +
        f'\n\nWhisper hat gehört:\n{t["text"]}\n', encoding='utf-8')

    print(f'{n} Wörter: {direkt} direkt, {schreib} über die Schreibung, {n - direkt - schreib} geschätzt → {quote * 100:.0f} % zugeordnet '
          f'| {len(caps)} Caption-Gruppen | Stimme endet bei {ende:.2f} s')
    print(f'Gesamtdauer des Videos: stimme.wav {wav_dauer:.2f} s + Auslauf {auslauf:.2f} s = {wav_dauer + auslauf:.2f} s '
          f'(anderer Auslauf: ms szenen <folge> --auslauf <s>, ms render übernimmt ihn)')
    if quote < 0.85:
        print('WARNUNG: unter 85 % zugeordnet. display gegen voice/woerter_check.txt prüfen (meist abweichende Schreibung oder '
              'ein Satz, der in tts und display verschieden ist).')
    print('\n'.join(zeilen))
    _ms.log(f'Wortzeiten: {n} Wörter, {quote * 100:.0f} % zugeordnet, {len(caps)} Caption-Gruppen', ziel=_ms.ziel_name(ordner))
    for p in (v / 'woerter.json', v / 'timing.txt', ordner / 'build' / 'captions.json'):
        print(p)


if __name__ == '__main__':
    sys.exit(main())
