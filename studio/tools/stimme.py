"""Stimme einer Folge: Aufnahme übernehmen oder per ElevenLabs erzeugen, Tempo anpassen, auf −14 LUFS bringen.
  ms stimme <folge> --datei <aufnahme.wav|mp3|m4a>        eigene Aufnahme (oder Higgsfield-Download) als Roh-Take übernehmen
  ms stimme <folge> --elevenlabs --stimme <voice_id>       nur Zeichen zählen und Kosten schätzen (kein Aufruf)
  ms stimme <folge> --elevenlabs --stimme <voice_id> --ja  erzeugen (gleicher Text wird nicht doppelt bezahlt)
        [--modell eleven_multilingual_v2] [--stabilitaet 0.4] [--aehnlichkeit 0.75]
  ms stimme <folge> --probe "Schreibweise A" "Schreibweise B" --elevenlabs --stimme <id> [--ja]
                                                           Aussprache-Test: kurze Proben, Whisper sagt, was es hört
  ms stimme <folge> --text                                 Skript prüfen: Wörter, Zeichen, geschätzte Dauer, Abstand zur Vorlage (kostet nichts)
  ms stimme <folge> --higgsfield                           Text + Anleitung für Higgsfield-Stimmen (laufen über den MCP im Agenten)
  ms stimme <folge> --pruefen                              Whisper-Gegenprobe des Roh-Takes (läuft nach --datei/--elevenlabs automatisch)
  ms stimme <folge> --tempo [--wps 4.2 | --faktor 1.3] [--pause 0.06] [--pausen-lassen]
                                                           Pausen kürzen, Tempo anpassen, −14 LUFS → voice/stimme.wav
  ms stimme <pilot> --original [<video|register-id>] [--von 0] [--bis 10]
                                                           nur Pilot: Originalton im Zeitfenster als voice/stimme.wav
                                                           (kein Tempo, keine Pausen-Kürzung, nur Pegel auf −14 LUFS),
                                                           dazu vorbild/ausschnitt.mp4 (Original, gleiche Zeitachse wie der
                                                           Pilot) und, falls sie fehlt, voice/script.json aus dem Transkript.
                                                           Ohne Angabe: Vorlage aus STATUS.json. Danach: ms woerter <pilot>
Ausgangspunkt: voice/script.json {"tts": ["Satz …"], "display": "Anzeigetext", "sprache": "de" (optional)}.
Aussprache: kanaele/<kanal>/AUSSPRACHE.json {"Nginx": "Engine-X", …} wird vor jeder Erzeugung auf tts angewendet.
Ziel-Tempo ohne --wps: Tempo der Vorlage (STATUS vorlage/transkript), sonst kit/ton-rezept.json "wps", sonst nur Pausen + Lautheit.
Ausgabe: voice/roh.wav, voice/roh_check.txt, voice/stimme.wav, voice/stimme.json, voice/jobs.json (bezahlte Aufträge).
Pilot (STATUS art "pilot"): --tempo bricht ab, die Zeitachse des Originals bleibt unverändert (sonst passt der Vergleich nicht)."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import _ms
import _ton

ELEVEN_URL = 'https://api.elevenlabs.io/v1/text-to-speech/{stimme}?output_format=mp3_44100_128'
# Credits pro Zeichen (elevenlabs.io/pricing, Stand Oktober 2026): Multilingual v2 / v3 = 1, Flash/Turbo = 0,5.
CREDITS_PRO_ZEICHEN = {'flash': 0.5, 'turbo': 0.5}
# Preis pro 1.000 Credits in USD je Plan (Starter 6 $ / 30.000, Creator 22 $ / 121.000, Pro 99 $ / 600.000).
PLAENE = [('Starter', 6 / 30), ('Creator', 22 / 121), ('Pro', 99 / 600)]


# ---------------------------------------------------------------- Grundlagen

def folge_und_skript(ziel):
    ordner = _ms.ziel_pfad(ziel)
    st = _ms.status_lesen(ordner)
    if not st or st.get('art') == 'kanal':
        raise SystemExit(f'FEHLER: {ziel} ist keine Folge (STATUS.json fehlt oder ist ein Kanal).')
    pfad = ordner / 'voice' / 'script.json'
    s = _ms.json_lesen(pfad)
    if not s or not isinstance(s.get('tts'), list) or not s.get('tts'):
        raise SystemExit(f'FEHLER: {pfad} fehlt oder hat kein "tts" (Liste von Sätzen). Erst das Skript schreiben (Skill motion-skript).')
    if not str(s.get('display', '')).strip():
        raise SystemExit(f'FEHLER: {pfad} hat kein "display" (Anzeigetext für die Captions).')
    return ordner, st, s


def tts_text(s) -> str:
    return ' '.join(str(x).strip() for x in s['tts'] if str(x).strip())


def aussprache_anwenden(ordner, st, s) -> dict:
    """Wendet kanaele/<k>/AUSSPRACHE.json auf tts an und schreibt geänderte Sätze zurück."""
    kanal = st.get('kanal')
    regeln = _ms.json_lesen(_ms.arbeit() / 'kanaele' / kanal / 'AUSSPRACHE.json', {}) if kanal else {}
    if not regeln:
        return s
    neu = []
    for satz in s['tts']:
        for wort, sprich in regeln.items():
            if wort.startswith('_'):
                continue
            ersatz = sprich.get('tts') if isinstance(sprich, dict) else sprich
            if ersatz and wort.lower() != str(ersatz).lower():
                satz = re.sub(r'(?<!\w)' + re.escape(wort) + r'(?!\w)', str(ersatz), satz, flags=re.IGNORECASE)
        neu.append(satz)
    if neu != s['tts']:
        for alt, n in zip(s['tts'], neu):
            if alt != n:
                print(f'Aussprache (AUSSPRACHE.json): {alt}  →  {n}')
        s['tts'] = neu
        _ms.json_schreiben(ordner / 'voice' / 'script.json', s)
    return s


def ueberholt(pfad: Path) -> None:
    """Ersetztes nie löschen: nach voice/_ueberholt/ verschieben."""
    if pfad.exists():
        ziel = pfad.parent / '_ueberholt'
        ziel.mkdir(exist_ok=True)
        stempel = _ms.jetzt()[:19].replace(':', '').replace('-', '').replace('T', '-')
        shutil.move(str(pfad), str(ziel / f'{pfad.stem}-{stempel}{pfad.suffix}'))


def dauer_von(pfad) -> float:
    r = _ms.befehl(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(pfad)])
    return float(r.stdout.strip() or 0)


def als_roh(quelle, ziel: Path) -> None:
    ziel.parent.mkdir(parents=True, exist_ok=True)
    tmp = ziel.with_name('.roh-neu.wav')
    _ms.befehl(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(quelle), '-vn', '-ac', '1', '-ar', str(_ton.SR),
                '-c:a', 'pcm_s16le', str(tmp)])
    ueberholt(ziel)
    tmp.replace(ziel)


# ---------------------------------------------------------------- Gegenprobe (Whisper)

def vergleich(soll: str, gehoert: list[str]):
    a = [_ton.norm_wort(w) for w in soll.split() if _ton.norm_wort(w)]
    b = [_ton.norm_wort(w) for w in gehoert if _ton.norm_wort(w)]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    quote = sum(m.size for m in sm.get_matching_blocks()) / max(1, len(a))
    abw = [f'{" ".join(a[i1:i2]) or "(nichts)"}  →  {" ".join(b[j1:j2]) or "(nichts)"}' for t, i1, i2, j1, j2 in sm.get_opcodes() if t != 'equal']
    return quote, abw


def gegenprobe(ordner, s, audio=None, still=False) -> float:
    audio = audio or ordner / 'voice' / 'roh.wav'
    if not Path(audio).exists():
        raise SystemExit(f'FEHLER: {audio} fehlt. Erst --datei oder --elevenlabs.')
    t = _ms.transkribiere(audio, s.get('sprache') or 'auto')
    gehoert = [w['w'] for w in t['woerter']]
    q_tts, abw_tts = vergleich(tts_text(s), gehoert)
    q_disp, abw_disp = vergleich(str(s['display']), gehoert)
    quote, abw, basis = (q_tts, abw_tts, 'tts') if q_tts >= q_disp else (q_disp, abw_disp, 'display')
    bericht = (f'Erkannt: {quote * 100:.1f} % der Wörter (Vergleich mit {basis}, Sprache {t.get("sprache")})\n'
               f'Abweichungen (Zahlen als Ziffern und Getrenntschreibung sind meist harmlos):\n' + '\n'.join(abw) +
               f'\n\nWhisper hat gehört:\n{t["text"]}\n')
    (ordner / 'voice' / ('roh_check.txt' if audio == ordner / 'voice' / 'roh.wav' else 'check.txt')).write_text(bericht, encoding='utf-8')
    if not still:
        print(f'Gegenprobe: {quote * 100:.1f} % erkannt (Ziel ≥ 95 %).')
        for z in abw[:12]:
            print('  ', z)
        if quote < 0.95:
            print('WARNUNG: unter 95 %. Betroffene Stellen umformulieren oder Aussprache-Schreibweise ändern (Skill motion-stimme).')
    return quote


# ---------------------------------------------------------------- ElevenLabs

def credits_fuer(text: str, modell: str) -> float:
    faktor = next((v for k, v in CREDITS_PRO_ZEICHEN.items() if k in modell), 1.0)
    return len(text) * faktor


def schaetzung(text: str, modell: str, was='Stimme') -> float:
    cr = credits_fuer(text, modell)
    preise = ', '.join(f'{n} ca. {cr / 1000 * p:.2f} USD' for n, p in PLAENE)
    print(f'{was}: {len(text)} Zeichen mit {modell} = ca. {cr:.0f} ElevenLabs-Credits ({preise}).')
    print('Preise Stand Oktober 2026, prüfen: https://elevenlabs.io/pricing. Kommerzielle Nutzung erst ab Starter.')
    return cr


def eleven_auftrag(ordner, text, stimme, modell, einstellungen, ziel: Path, ja: bool, was='Stimme'):
    """Erzeugt eine Datei über die ElevenLabs-API. Gleicher Auftrag (Text, Stimme, Modell, Einstellungen) wird aus
    voice/jobs.json wiederverwendet und nicht neu bezahlt. Ohne ja: nur Schätzung. Gibt (Pfad oder None, Credits) zurück."""
    jobs_pfad = ordner / 'voice' / 'jobs.json'
    jobs = _ms.json_lesen(jobs_pfad, {}) or {}
    schluessel = hashlib.sha256(json.dumps([text, stimme, modell, einstellungen], ensure_ascii=False).encode()).hexdigest()[:16]
    alt = jobs.get(schluessel)
    if alt and (ordner / alt['datei']).exists():
        print(f'{was}: genau dieser Auftrag wurde schon bezahlt, nehme {alt["datei"]} (keine neuen Kosten).')
        return ordner / alt['datei'], 0.0
    cr = schaetzung(text, modell, was)
    if not ja:
        print('Nichts ausgeführt. Mit --ja erzeugen (erst nach Ja des Nutzers).')
        return None, cr
    if len(text) > 9500:
        raise SystemExit('FEHLER: Text über 9.500 Zeichen. ElevenLabs nimmt pro Auftrag höchstens 10.000. Skript teilen.')
    schluessel_api = _ms.env('ELEVENLABS_API_KEY')
    if not schluessel_api:
        raise SystemExit('FEHLER: ELEVENLABS_API_KEY fehlt. In <Arbeitsordner>/.env eintragen (Skill motion-setup), nie in den Chat.')
    body = {'text': text, 'model_id': modell, 'voice_settings': einstellungen}
    req = urllib.request.Request(ELEVEN_URL.format(stimme=stimme), data=json.dumps(body).encode('utf-8'), method='POST',
                                 headers={'xi-api-key': schluessel_api, 'Content-Type': 'application/json', 'Accept': 'audio/mpeg'})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            daten = r.read()
    except urllib.error.HTTPError as e:
        info = e.read().decode('utf-8', errors='replace')[:300]
        hinweis = {401: 'Schlüssel ungültig', 402: 'Guthaben/Plan reicht nicht', 404: 'Stimmen-ID unbekannt',
                   422: 'Eingabe ungültig (Modell? Einstellungen?)', 429: 'zu viele Aufträge, kurz warten'}.get(e.code, '')
        raise SystemExit(f'FEHLER: ElevenLabs antwortet {e.code} {hinweis}. Keine Datei erzeugt.\n{info}')
    except urllib.error.URLError as e:
        raise SystemExit(f'FEHLER: ElevenLabs nicht erreichbar ({e.reason}). Internet prüfen und erneut starten.')
    if len(daten) < 1000:
        raise SystemExit('FEHLER: ElevenLabs hat keine Audiodatei geliefert. Erneut versuchen.')
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(daten)
    jobs[schluessel] = {'datei': str(ziel.relative_to(ordner)), 'zeichen': len(text), 'credits': cr, 'modell': modell,
                        'stimme': stimme, 'zeit': _ms.jetzt(), 'was': was}
    _ms.json_schreiben(jobs_pfad, jobs)
    st = _ms.status_lesen(ordner)
    _ms.status_setzen(ordner, kosten=(st.get('kosten') or []) + [
        {'zeit': _ms.jetzt(), 'betrag': round(cr, 1), 'einheit': 'Credits', 'was': f'ElevenLabs {was} ({len(text)} Zeichen)'}])
    _ms.log(f'ElevenLabs {was}: {len(text)} Zeichen, ca. {cr:.0f} Credits', ziel=_ms.ziel_name(ordner), art='kosten')
    return ziel, cr


def einstellungen_aus(a) -> dict:
    return {'stability': a.stabilitaet, 'similarity_boost': a.aehnlichkeit}


# ---------------------------------------------------------------- Tempo

def ziel_wps(ordner, st, a):
    if a.wps:
        return float(a.wps), '--wps'
    v = st.get('vorlage') or {}
    kandidaten = []
    if v.get('transkript'):
        p = Path(str(v['transkript'])).expanduser()
        kandidaten.append(p if p.is_absolute() else _ms.arbeit() / p)
    if v.get('id'):
        kandidaten.append(_ms.arbeit() / 'vorlagen' / 'transkripte' / f'{v["id"]}.json')
    for p in kandidaten:
        d = _ms.json_lesen(p) if p.exists() else None
        if not d:
            continue
        stats = d.get('stats') or {}
        for quelle_d, k in ((stats, 'woerter_pro_s'), (d, 'woerter_pro_s'), (d, 'wps'), (d, 'woerter_pro_sekunde')):
            if isinstance(quelle_d.get(k), (int, float)) and quelle_d[k] > 0:
                return float(quelle_d[k]), f'Vorlage {p.name}'
        w = d.get('woerter') or []
        if len(w) >= 10 and w[-1]['e'] > w[0]['s']:
            return len(w) / (w[-1]['e'] - w[0]['s']), f'Vorlage {p.name}, {len(w)} Wörter gezählt'
    if st.get('kanal'):
        r = _ms.json_lesen(_ms.arbeit() / 'kanaele' / st['kanal'] / 'kit' / 'ton-rezept.json', {}) or {}
        for k in ('wps', 'woerter_pro_sekunde'):
            if isinstance(r.get(k), (int, float)) and r[k] > 0:
                return float(r[k]), 'kit/ton-rezept.json'
    return None, None


def pausen_kuerzen(x, roh: Path, pause: float, min_pause: float):
    """Pausen ab min_pause auf pause kürzen. Kürzere Grenzen beschädigen Plosive (t, k, p am Wortende)."""
    np = _ton.np_()
    sr = _ton.SR
    e = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-i', str(roh), '-af',
                        f'silencedetect=noise=-38dB:d={min_pause}', '-f', 'null', '-'], capture_output=True, text=True).stderr
    starts = [float(v) for v in re.findall(r'silence_start: (-?[\d.]+)', e)]
    enden = [float(v) for v in re.findall(r'silence_end: ([\d.]+)', e)]
    rand = pause / 2
    teile, pos, n = [], 0.0, 0
    dauer = len(x) / sr
    for i, s0 in enumerate(starts):
        s0 = max(0.0, s0)
        if i < len(enden):
            s1 = enden[i]
            if s0 <= 0.001:          # Stille am Anfang: 50 ms Vorlauf lassen
                pos = max(0.0, s1 - 0.05)
                n += 1
                continue
            teile.append(x[int(pos * sr):int((s0 + rand) * sr)])
            pos = s1 - rand
            n += 1
        else:                         # Stille am Ende: 150 ms Ausklang
            teile.append(x[int(pos * sr):int(min(dauer, s0 + 0.15) * sr)])
            pos = dauer
            n += 1
    if pos < dauer:
        teile.append(x[int(pos * sr):])
    f = int(0.004 * sr)               # 4 ms Blende an jeder Naht gegen Knackser
    for t in teile:
        if len(t) > 2 * f:
            t[:f] *= np.linspace(0, 1, f, dtype=np.float32)
            t[-f:] *= np.linspace(1, 0, f, dtype=np.float32)
    return (np.concatenate(teile) if teile else x), n


def hat_rubberband() -> bool:
    r = subprocess.run(['ffmpeg', '-hide_banner', '-filters'], capture_output=True, text=True)
    return bool(re.search(r'\brubberband\b', r.stdout))


def tempo(ordner, st, s, a):
    v = ordner / 'voice'
    roh = v / 'roh.wav'
    if not roh.exists():
        raise SystemExit('FEHLER: voice/roh.wav fehlt. Erst "ms stimme <folge> --datei …" oder "--elevenlabs … --ja".')
    x = _ton.dekodiere(roh)
    roh_dauer = len(x) / _ton.SR
    if a.pausen_lassen:
        y, n_pausen = x, 0
    else:
        y, n_pausen = pausen_kuerzen(x, roh, a.pause, a.min_pause)
    ohne = len(y) / _ton.SR
    woerter = len(tts_text(s).split())
    wps, quelle = ziel_wps(ordner, st, a)
    if a.faktor:
        faktor = float(a.faktor)          # von Hand; wps/quelle bleiben nur zum Vergleich in der Meldung
    elif wps:
        faktor = ohne / (woerter / wps)
    else:
        faktor = 1.0
        print('Kein Ziel-Tempo gefunden (kein --wps, Vorlage ohne Transkript, kein ton-rezept): nur Pausen gekürzt und Lautheit angepasst.')
    if faktor > 2.0 and not a.faktor:
        raise SystemExit(f'FEHLER: Tempo-Faktor {faktor:.2f} (über 2,0). Die Stimme würde unverständlich. Skript kürzen '
                         f'({woerter} Wörter, Ziel bei {wps:.2f} W/s: {woerter / wps:.1f} s) oder mit --faktor bewusst setzen.')
    tmp = v / '.ohne_pausen.wav'
    _ton.schreibe_wav(tmp, y)
    gedehnt = v / '.tempo.wav'
    verfahren = 'keins'
    if abs(faktor - 1.0) >= 0.005:
        if hat_rubberband():
            filt, verfahren = f'rubberband=tempo={faktor:.4f}:pitchq=quality:formant=preserved', 'rubberband'
        else:
            kette, rest = [], faktor
            while rest > 2.0:
                kette.append('atempo=2.0')
                rest /= 2.0
            while rest < 0.5:
                kette.append('atempo=0.5')
                rest /= 0.5
            kette.append(f'atempo={rest:.4f}')
            filt, verfahren = ','.join(kette), 'atempo (ffmpeg ohne rubberband, klingt etwas rauer)'
        _ms.befehl(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(tmp), '-af', filt, '-ar', str(_ton.SR), str(gedehnt)])
    else:
        shutil.copy2(tmp, gedehnt)
    ziel = v / 'stimme.wav'
    neu = v / '.stimme-neu.wav'
    lufs = _ton.auf_lufs(gedehnt, neu, -14.0, -1.5)
    ueberholt(ziel)
    neu.replace(ziel)
    for p in (tmp, gedehnt):
        p.unlink(missing_ok=True)
    dauer = dauer_von(ziel)
    info = {'quelle': (_ms.json_lesen(v / 'stimme.json', {}) or {}).get('quelle'), 'roh_dauer': round(roh_dauer, 2),
            'pausen_gekuerzt': n_pausen, 'ohne_pausen': round(ohne, 2), 'woerter': woerter, 'wps_ziel': round(wps, 2) if wps else None,
            'wps_quelle': quelle, 'faktor': round(faktor, 3), 'faktor_quelle': '--faktor' if a.faktor else ('wps' if wps else None), 'verfahren': verfahren, 'dauer': round(dauer, 2),
            'wps_ist': round(woerter / dauer, 2) if dauer else None, 'lufs': round(lufs, 1), 'zeit': _ms.jetzt()}
    _ms.json_schreiben(v / 'stimme.json', info)
    print(f'{woerter} Wörter | Roh {roh_dauer:.2f} s | {n_pausen} Pausen gekürzt → {ohne:.2f} s | Tempo ×{faktor:.3f} ({verfahren}) '
          f'| Ergebnis {dauer:.2f} s = {woerter / dauer:.2f} W/s | {lufs:.1f} LUFS')
    if a.faktor:
        print(f'Tempo-Faktor ×{faktor:g} von Hand gesetzt (--faktor).' + (
            f' Zum Vergleich: das Ziel-Tempo wäre {wps:.2f} Wörter/s gewesen (Quelle: {quelle}), daraus hätte sich ×{ohne / (woerter / wps):.3f} '
            f'ergeben. Nicht benutzt.' if wps else ''))
    elif wps:
        print(f'Ziel-Tempo {wps:.2f} Wörter/s (Quelle: {quelle}; --wps setzt es von Hand). Erreicht: {woerter / dauer:.2f} Wörter/s.')
    if faktor > 1.6:
        print('WARNUNG: Tempo-Faktor über 1,6, das klingt hörbar gequetscht. Besser das Skript kürzen (Füllwörter, nicht Aussagen).')
    elif faktor < 0.85:
        print('WARNUNG: Tempo-Faktor unter 0,85, die Stimme wird gedehnt und klingt zäh. Skript verlängern oder --pausen-lassen.')
    if abs(lufs + 14) > 0.5:
        print(f'WARNUNG: Lautheit {lufs:.1f} LUFS weicht über 0,5 vom Ziel −14 ab.')
    _ms.log(f'Stimme fertig: {dauer:.1f} s, ×{faktor:.2f}, {lufs:.1f} LUFS', ziel=_ms.ziel_name(ordner))
    print(ziel)
    print('Nächster Schritt: ms woerter', _ms.ziel_name(ordner).split('/')[-1])


def text_pruefen(ordner, st, s, a):
    """Gate fürs Skript: Länge gegen die Vorlage (±15 %), geschätzte Dauer, Satzlängen, Wortgrenzen tts ↔ display."""
    text = tts_text(s)
    n_tts, n_disp = len(text.split()), len(str(s['display']).split())
    wps, quelle = ziel_wps(ordner, st, a)
    print(f'Sprechtext: {len(s["tts"])} Sätze, {n_tts} Wörter, {len(text)} Zeichen | Anzeigetext: {n_disp} Wörter')
    if wps:
        print(f'Geschätzte Dauer bei {wps:.2f} W/s ({quelle}): {n_tts / wps:.1f} s')
    v = st.get('vorlage') or {}
    pfade = []
    if v.get('transkript'):
        p = Path(str(v['transkript'])).expanduser()
        pfade.append(p if p.is_absolute() else _ms.arbeit() / p)
    if v.get('id'):
        pfade.append(_ms.arbeit() / 'vorlagen' / 'transkripte' / f'{v["id"]}.json')
    vorlage = next((_ms.json_lesen(p) for p in pfade if p.exists()), None)
    if vorlage and vorlage.get('woerter'):
        n_v = len(vorlage['woerter'])
        abw = (n_tts - n_v) / n_v * 100
        print(f'Vorlage: {n_v} Wörter → {abw:+.0f} % ' + ('(im Rahmen ±15 %)' if abs(abw) <= 15 else '(AUSSERHALB ±15 %: kürzen oder ergänzen)'))
    lang = [x for x in s['tts'] if len(x.split()) > 25]
    if lang:
        print(f'Hinweis: {len(lang)} Sätze über 25 Wörter (gesprochen schwer). Erster: "{lang[0][:80]}…"')
    if abs(n_tts - n_disp) > max(2, 0.05 * n_tts):
        print(f'WARNUNG: tts hat {n_tts}, display {n_disp} Wörter. Wortgrenzen sollen passen (sonst sinkt die Zuordnung in "ms woerter").')
    zeichen = re.findall(r'[()\[\]{}<>#*_/\\]|[\U0001F300-\U0001FAFF]', text)
    if zeichen:
        print(f'WARNUNG: Sonderzeichen im Sprechtext ({" ".join(sorted(set(zeichen)))}). Ausschreiben oder streichen.')
    if re.search(r'\d', text):
        print('Hinweis: Ziffern im Sprechtext. Zahlen für die Stimme ausschreiben ("zwölf", "dreihunderttausend").')


# ---------------------------------------------------------------- Pilot: Originalton

SATZENDE = ('.', '?', '!', '…')


def _register_eintrag(vid: str):
    reg = _ms.json_lesen(_ms.arbeit() / 'vorlagen' / 'register.json', {}) or {}
    return next((e for e in reg.get('eintraege', []) if e.get('id') == vid), None)


def _arbeit_pfad(wert) -> Path | None:
    if not wert:
        return None
    p = Path(str(wert)).expanduser()
    return p if p.is_absolute() else _ms.arbeit() / p


def original_finden(st, wert: str):
    """Original-Video und Register-Eintrag: Pfad, Register-id oder (leer) die Vorlage aus STATUS.json."""
    vorlage = st.get('vorlage') or {}
    if wert:
        p = Path(wert).expanduser()
        if p.exists():
            p = p.resolve()
            reg = _ms.json_lesen(_ms.arbeit() / 'vorlagen' / 'register.json', {}) or {}
            e = next((x for x in reg.get('eintraege', []) if x.get('video') and _arbeit_pfad(x['video']).exists()
                      and _arbeit_pfad(x['video']).resolve() == p), None)
            return p, e
    vid = wert or vorlage.get('id')
    if not vid:
        raise SystemExit('FEHLER: Welches Original? --original <video.mp4|register-id> angeben '
                         '(oder die Folge mit "ms neu folge … --vorlage <id>" anlegen).')
    e = _register_eintrag(vid) or (vorlage if vorlage.get('id') == vid else None)
    kandidaten = [_arbeit_pfad((e or {}).get('video')), _ms.arbeit() / 'vorlagen' / 'videos' / f'{vid}.mp4']
    video = next((k for k in kandidaten if k and k.exists()), None)
    if not video:
        raise SystemExit(f'FEHLER: Video zu "{vid}" nicht gefunden. Erst laden: ms laden {vid} --kanal <kanal>')
    return video.resolve(), e


def transkript_im_fenster(video: Path, e, wav_fenster: Path, von: float, bis: float, sprache: str):
    """Wörter des Originals im Zeitfenster, Zeiten relativ zum Fensterbeginn. Quelle: Transkript aus dem Register
    (vorlagen/transkripte/<id>.json), sonst Whisper auf dem geschnittenen Ton."""
    kandidaten = []
    if e:
        kandidaten += [_arbeit_pfad(e.get('transkript')), _ms.arbeit() / 'vorlagen' / 'transkripte' / f'{e.get("id")}.json']
    for p in kandidaten:
        d = _ms.json_lesen(p) if p and p.exists() else None
        if d and d.get('woerter'):
            ws = [w for w in d['woerter'] if von - 0.02 <= (float(w['s']) + float(w['e'])) / 2 <= bis + 0.02]
            aus = [{'w': str(w['w']).strip(), 's': round(max(0.0, float(w['s']) - von), 3), 'e': round(float(w['e']) - von, 3)}
                   for w in ws if str(w['w']).strip()]
            return aus, d.get('sprache'), f'Transkript {p.name}'
    t = _ms.transkribiere(wav_fenster, sprache)
    return [w for w in t['woerter'] if str(w['w']).strip()], t.get('sprache'), 'Whisper auf dem Ausschnitt'


def ausschnitt_video(video: Path, ziel: Path, von: float, bis: float, ganz: bool) -> None:
    """Bild und Ton des Originals im Fenster, damit Pilot und Original dieselbe Zeitachse haben (snap --gegen, vergleich)."""
    ziel.parent.mkdir(parents=True, exist_ok=True)
    tmp = ziel.with_name('.ausschnitt-neu.mp4')
    if ganz:
        shutil.copy2(video, tmp)
    else:
        _ms.befehl(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{von:.3f}', '-i', str(video), '-t', f'{bis - von:.3f}',
                    '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                    '-movflags', '+faststart', str(tmp)])
    ueberholt(ziel)
    tmp.replace(ziel)


def pilot_ton(a) -> None:
    ordner = _ms.ziel_pfad(a.folge)
    st = _ms.status_lesen(ordner)
    if st.get('art') != 'pilot':
        raise SystemExit('FEHLER: --original nur beim Pilot (STATUS art "pilot"). Fremder Ton kommt nie in eine eigene Folge.')
    video, e = original_finden(st, a.original)
    info = _ms.probe(video)
    if not info['ton']:
        raise SystemExit(f'FEHLER: {video.name} hat keine Tonspur. Ton nachladen (ms laden <id> --neu) oder Pilot ohne Stimme bauen.')
    von = max(0.0, float(a.von or 0.0))
    bis = min(info['dauer'], float(a.bis)) if a.bis is not None else info['dauer']
    if bis - von < 1.0:
        raise SystemExit(f'FEHLER: Zeitfenster {von:.2f} bis {bis:.2f} s ist zu kurz (Original {info["dauer"]:.2f} s).')
    ganz = von <= 0.001 and bis >= info['dauer'] - 0.001
    v = ordner / 'voice'
    v.mkdir(parents=True, exist_ok=True)
    roh = v / '.original-fenster.wav'
    _ms.befehl(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{von:.3f}', '-i', str(video), '-t', f'{bis - von:.3f}',
                '-vn', '-ac', '1', '-ar', str(_ton.SR), '-c:a', 'pcm_s16le', str(roh)])
    neu = v / '.stimme-neu.wav'
    lufs = _ton.auf_lufs(roh, neu, -14.0, -1.5)
    ziel = v / 'stimme.wav'
    ueberholt(ziel)
    neu.replace(ziel)
    ausschnitt = ordner / 'vorbild' / 'ausschnitt.mp4'
    ausschnitt_video(video, ausschnitt, von, bis, ganz)
    dauer = dauer_von(ziel)
    try:
        rel = video.relative_to(_ms.arbeit().resolve()).as_posix()
    except ValueError:
        rel = str(video)
    info_json = {'quelle': f'Original {(e or {}).get("id") or video.name} (Pilot)', 'original': rel,
                 'original_id': (e or {}).get('id'), 'original_von': round(von, 3), 'original_bis': round(bis, 3),
                 'ausschnitt': 'vorbild/ausschnitt.mp4', 'faktor': 1.0, 'verfahren': 'Originalton, Tempo und Pausen unverändert',
                 'dauer': round(dauer, 2), 'lufs': round(lufs, 1), 'zeit': _ms.jetzt()}
    _ms.json_schreiben(v / 'stimme.json', info_json)
    print(f'Originalton {von:.2f} bis {bis:.2f} s aus {video.name}: {dauer:.2f} s, {lufs:.1f} LUFS (nur Pegel, Zeitachse unverändert)')
    print(f'Original-Ausschnitt mit gleicher Zeitachse: {ausschnitt}')

    skript = v / 'script.json'
    if skript.exists():
        print(f'{skript} gibt es schon und bleibt. Prüfen, ob display zum Zeitfenster passt.')
    else:
        ws, sprache, quelle = transkript_im_fenster(video, e, roh, von, bis, a.sprache or 'auto')
        if not ws:
            print('WARNUNG: Im Zeitfenster wurde nichts gesprochen. voice/script.json nicht angelegt, Captions aus '
                  '(ms szenen <pilot> --ohne-captions) oder anderes Fenster wählen.')
        else:
            saetze, satz = [], []
            for w in ws:
                satz.append(w['w'])
                if w['w'].endswith(SATZENDE):
                    saetze.append(' '.join(satz))
                    satz = []
            if satz:
                saetze.append(' '.join(satz))
            daten = {'tts': saetze, 'display': ' '.join(w['w'] for w in ws), 'sprache': sprache or 'auto',
                     '_quelle': f'Pilot: gesprochener Text des Originals {von:.2f} bis {bis:.2f} s ({quelle}), tts = display'}
            _ms.json_schreiben(skript, daten)
            print(f'voice/script.json aus {quelle}: {len(ws)} Wörter, {len(saetze)} Sätze (tts = display = gesprochener Text).')
    roh.unlink(missing_ok=True)
    _ms.log(f'Pilot-Ton: Original {von:.1f} bis {bis:.1f} s, {dauer:.1f} s, {lufs:.1f} LUFS', ziel=_ms.ziel_name(ordner))
    print(ziel)
    print('Nächster Schritt: ms woerter', ordner.name)


# ---------------------------------------------------------------- Hauptprogramm

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folge')
    ap.add_argument('--datei', help='eigene Aufnahme oder heruntergeladene Stimme übernehmen')
    ap.add_argument('--elevenlabs', action='store_true')
    ap.add_argument('--stimme', help='ElevenLabs voice_id')
    ap.add_argument('--modell', default='eleven_multilingual_v2')
    ap.add_argument('--stabilitaet', type=float, default=0.4)
    ap.add_argument('--aehnlichkeit', type=float, default=0.75)
    ap.add_argument('--probe', nargs='+', metavar='TEXT', help='Aussprache-Test: kurze Proben erzeugen und gegenhören')
    ap.add_argument('--higgsfield', action='store_true', help='Anleitung für Higgsfield-Stimmen')
    ap.add_argument('--text', action='store_true', help='Skript prüfen: Wörter, Zeichen, Dauer, Vergleich mit der Vorlage')
    ap.add_argument('--pruefen', action='store_true', help='Whisper-Gegenprobe des Roh-Takes')
    ap.add_argument('--tempo', action='store_true')
    ap.add_argument('--wps', type=float, help='Ziel-Wörter pro Sekunde')
    ap.add_argument('--faktor', type=float, help='Tempo-Faktor direkt (1,3 = 30 %% schneller)')
    ap.add_argument('--pause', type=float, default=0.06, help='Länge gekürzter Pausen in s (Standard 0,06)')
    ap.add_argument('--min-pause', type=float, default=0.12, help='ab dieser Länge wird eine Pause gekürzt')
    ap.add_argument('--pausen-lassen', action='store_true')
    ap.add_argument('--ja', action='store_true', help='Kosten bestätigt: bezahlten Auftrag ausführen')
    ap.add_argument('--original', nargs='?', const='', metavar='VIDEO|ID',
                    help='nur Pilot: Originalton als Stimme (ohne Angabe: Vorlage aus STATUS.json)')
    ap.add_argument('--von', type=float, help='mit --original: Fensterbeginn im Original in s (Standard 0)')
    ap.add_argument('--bis', type=float, help='mit --original: Fensterende im Original in s (Standard Videoende)')
    ap.add_argument('--sprache', help='mit --original: Sprache fürs Transkript, falls keins im Register liegt')
    a = ap.parse_args()

    if a.original is not None:
        pilot_ton(a)
        return
    if a.von is not None or a.bis is not None:
        raise SystemExit('FEHLER: --von/--bis gehen nur zusammen mit --original (Pilot).')
    if a.tempo and (_ms.status_lesen(_ms.ziel_pfad(a.folge)).get('art') == 'pilot'):
        raise SystemExit('WARNUNG: Pilot-Folge. Der Pilot behält Tempo und Pausen des Originals, sonst passen Szenen und '
                         'Vergleich nicht mehr. Kein --tempo beim Pilot: ms stimme <pilot> --original [--von --bis].')

    ordner, st, s = folge_und_skript(a.folge)
    v = ordner / 'voice'

    if a.datei:
        q = Path(a.datei).expanduser()
        if not q.exists():
            raise SystemExit(f'FEHLER: {q} gibt es nicht.')
        als_roh(q, v / 'roh.wav')
        _ms.json_schreiben(v / 'stimme.json', {'quelle': f'Datei {q.name}', 'zeit': _ms.jetzt()})
        print(f'Roh-Take übernommen: {dauer_von(v / "roh.wav"):.2f} s')
        gegenprobe(ordner, s)
        print('Nächster Schritt: ms stimme', a.folge, '--tempo')
        return

    if a.text:
        text_pruefen(ordner, st, s, a)
        return

    if a.higgsfield:
        s = aussprache_anwenden(ordner, st, s)
        text = tts_text(s)
        print('Higgsfield-Stimmen laufen über den Higgsfield-MCP im Agenten (Werkzeug generate_audio, Modell z. B. ElevenLabs v4),')
        print('nicht über dieses Werkzeug. Ablauf: Kosten mit dem Nutzer klären, erzeugen, Datei herunterladen, dann:')
        print(f'  ms stimme {a.folge} --datei <heruntergeladene.mp3>')
        print(f'\nText ({len(text)} Zeichen), genau so übergeben:\n{text}')
        return

    if a.probe:
        if not (a.elevenlabs and a.stimme):
            raise SystemExit('FEHLER: Aussprache-Test braucht --elevenlabs --stimme <voice_id>. Bei Higgsfield: Proben im Agenten '
                             'erzeugen und den Nutzer anhören lassen, nicht mit --datei prüfen (das ersetzt den Roh-Take).')
        gesamt = sum(credits_fuer(t, a.modell) for t in a.probe)
        print(f'Aussprache-Test: {len(a.probe)} Proben, zusammen ca. {gesamt:.0f} Credits.')
        for i, t in enumerate(a.probe, 1):
            ziel = v / 'proben' / f'probe-{i}-{_ton.slug(t)[:30]}.mp3'
            pfad, _ = eleven_auftrag(ordner, t, a.stimme, a.modell, einstellungen_aus(a), ziel, a.ja, f'Probe {i}')
            if pfad:
                gehoert = _ms.transkribiere(pfad, s.get('sprache') or 'auto')['text']
                print(f'  Probe {i}: "{t}"  →  Whisper hört: "{gehoert}"   ({pfad.name})')
        return

    if a.elevenlabs:
        if not a.stimme:
            raise SystemExit('FEHLER: --stimme <voice_id> fehlt (steht in PROFIL.md oder in der ElevenLabs-Stimmenliste).')
        s = aussprache_anwenden(ordner, st, s)
        text = tts_text(s)
        pfad, _ = eleven_auftrag(ordner, text, a.stimme, a.modell, einstellungen_aus(a), v / 'elevenlabs.mp3', a.ja, 'Stimme')
        if not pfad:
            return
        als_roh(pfad, v / 'roh.wav')
        _ms.json_schreiben(v / 'stimme.json', {'quelle': f'ElevenLabs {a.modell} {a.stimme}', 'zeit': _ms.jetzt()})
        print(f'Roh-Take: {dauer_von(v / "roh.wav"):.2f} s')
        gegenprobe(ordner, s)
        print('Nächster Schritt: ms stimme', a.folge, '--tempo')
        return

    if a.pruefen:
        gegenprobe(ordner, s)
        return

    if a.tempo:
        tempo(ordner, st, s, a)
        return

    ap.print_help()


if __name__ == '__main__':
    sys.exit(main())
