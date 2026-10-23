"""Sound-Bibliothek: laden, einlesen, suchen, abhören, Familien, Sperren (Arbeitsordner/sounds/katalog.json).
  ms sound laden kenney [--ja]                     die 7 CC0-Audio-Packs von kenney.nl: Größe ansagen, mit --ja laden + einlesen
  ms sound laden mixkit <id> [--name "…"] [--ja]   einen einzelnen Mixkit-Sound (Nummer aus der Mixkit-Seite), nie Massen
  ms sound einlesen <ordner|datei> --quelle <name> --lizenz "<text>" [--verlinken] [--ohne-ki]
                                                   kopieren (oder verlinken), messen: Dauer, Lautheit, Peak, Anschlag, Helligkeit
  ms sound ki [--neu]                              KI-Felder nachrüsten: AST-Klassen (maschinelles Anhören) + CLAP-Vektoren (Suche)
  ms sound suche "<begriff>" [--n 10] [--alle]     Textsuche in Namen/Tags (deutsch oder englisch), mit CLAP wenn installiert
  ms sound liste [--quelle q] [--familie f] [--urteil behalten|raus|offen] [--gesperrt] [--n 40] [--json]
  ms sound info <id>
  ms sound abhoeren [--neu] [--quelle q] [--familie f] [--ids a b …] [--server] [--port 8778]
                                                   Abhörseite: alle gleich laut abspielen, behalten/raus, Korrektur trim_db
  ms sound urteile <export.json>                   Urteile von der Abhörseite übernehmen (wenn ohne --server gearbeitet)
  ms sound familie                                 Familien zeigen
  ms sound familie <name> <ids|muster…> [--einsatz "…"] | --entfernen <ids…> | --aufloesen
  ms sound setzen <ids…> [--urteil behalten|raus|offen] [--trim -3] [--art allzweck|motiv|nische|hook]
                         [--von 0.1 --bis 0.8] [--unter-stimme -3] [--tags "a,b"] [--notiz "…"]
  ms sound sperren <ids…> [--grund "…"] [--weg]    gesperrte Sounds lassen jeden Mix abbrechen
  ms sound gegenprobe <folge|bus.wav> [t:Name …] [--fenster 0.45]   AST hört kurze Fenster im fertigen Effekt-Bus
IDs: <quelle>/<name>, z. B. kenney/impact-metal-heavy-001 (aus impactMetal_heavy_001.ogg: Wortgrenzen und _ werden -).
Muster mit * gehen bei familie/setzen/sperren. Bei familie wird ein Muster ohne Treffer mit Warnung übersprungen
(z. B. "mixkit/*whoosh*", solange nur Kenney geladen ist), die übrigen Muster zählen.
Ohne KI-Pakete (torch, transformers) läuft alles außer AST/CLAP, die Suche ist dann reine Textsuche."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import http.server
import json
import os
import re
import secrets
import shutil
import sys
import urllib.error
import urllib.request
import webbrowser
import zipfile
from pathlib import Path

import _ms
import _ton

KENNEY_PACKS = ['impact-sounds', 'interface-sounds', 'sci-fi-sounds', 'digital-audio', 'ui-audio', 'rpg-audio', 'casino-audio']
KENNEY_LIZENZ = 'CC0 1.0 (kenney.nl, kommerziell frei, ohne Namensnennung)'
MIXKIT_LIZENZ = 'Mixkit Sound Effects Free License (mixkit.co/license/#sfxFree), kommerziell frei, ohne Namensnennung'
UA = {'User-Agent': 'Mozilla/5.0 (Motion-Studio Sound-Bibliothek)'}
AST_ID = 'MIT/ast-finetuned-audioset-10-10-0.4593'
CLAP_ID = 'laion/clap-htsat-fused'
FUELL = {'audio', 'sounds', 'sound', 'sfx', 'files', 'kenney', 'mixkit', 'the', 'and', 'of', 'ogg', 'wav', 'mp3'}
# Deutsche Suchwörter → englische Wörter in Dateinamen und AST-Klassen
SYNONYME = {
    'klick': ['click', 'tap', 'switch'], 'klicken': ['click'], 'plopp': ['pop', 'plop', 'bubble', 'drop'], 'blubb': ['bubble'],
    'whoosh': ['whoosh', 'woosh', 'swoosh', 'swish', 'swipe'], 'wusch': ['whoosh', 'swoosh', 'swish'], 'zisch': ['swish', 'hiss'],
    'schlag': ['impact', 'hit', 'punch', 'thud'], 'aufprall': ['impact', 'thud'], 'landen': ['impact', 'thud', 'drop', 'land'],
    'glas': ['glass'], 'metall': ['metal'], 'holz': ['wood', 'wooden'], 'stein': ['stone', 'rock'], 'papier': ['paper'],
    'muenze': ['coin', 'coins', 'chips'], 'münze': ['coin', 'coins', 'chips'], 'geld': ['coin', 'cash', 'chips'],
    'karte': ['card'], 'karten': ['card', 'cards'], 'tuer': ['door'], 'tür': ['door'], 'schritt': ['footstep', 'step'],
    'schritte': ['footstep'], 'glocke': ['bell', 'chime'], 'ding': ['ding', 'bell', 'chime'], 'piep': ['beep', 'blip'],
    'fehler': ['error', 'fail', 'wrong', 'buzz'], 'erfolg': ['success', 'win', 'complete', 'confirm'], 'gewinn': ['win', 'jingle'],
    'tippen': ['typing', 'keyboard', 'key'], 'tastatur': ['keyboard', 'typing'], 'schalter': ['switch', 'toggle'],
    'laser': ['laser'], 'explosion': ['explosion'], 'knall': ['explosion', 'bang', 'impact'], 'zauber': ['magic', 'spell'],
    'schwert': ['sword', 'blade'], 'tropfen': ['drop', 'drip'], 'auf': ['open'], 'zu': ['close'], 'oeffnen': ['open'],
    'öffnen': ['open'], 'schliessen': ['close'], 'schließen': ['close'], 'aufladen': ['power', 'charge', 'up'],
    'runter': ['down'], 'hoch': ['up', 'rise'], 'bass': ['low', 'bass', 'boom'], 'boom': ['boom', 'explosion', 'low'],
    'kette': ['chain'], 'schloss': ['lock'], 'computer': ['computer', 'digital'], 'roboter': ['robot', 'sci'],
    'raumschiff': ['spaceship', 'engine', 'sci'], 'motor': ['engine'], 'fluessigkeit': ['water'], 'wasser': ['water', 'splash'],
}


# ---------------------------------------------------------------- Hilfen

def lade_url(url, ziel: Path | None = None, kopf=False):
    req = urllib.request.Request(url, headers=UA, method='HEAD' if kopf else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            if kopf:
                return int(r.headers.get('Content-Length') or 0)
            if ziel is None:
                return r.read().decode('utf-8', errors='replace')
            ziel.parent.mkdir(parents=True, exist_ok=True)
            tmp = ziel.with_name('.' + ziel.name + '.tmp')
            with open(tmp, 'wb') as f:
                shutil.copyfileobj(r, f, 1 << 20)
            tmp.replace(ziel)
            return ziel
    except urllib.error.HTTPError as e:
        raise SystemExit(f'FEHLER: {url} antwortet {e.code}. Seite im Browser prüfen (Link geändert?).')
    except urllib.error.URLError as e:
        raise SystemExit(f'FEHLER: {url} nicht erreichbar ({e.reason}). Internet prüfen.')


def mb(n) -> str:
    return f'{n / 1e6:.1f} MB'


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def tags_aus(rel: Path, quelle: str) -> list[str]:
    teile = list(rel.parts[:-1]) + [rel.stem]
    woerter = []
    for t in teile:
        t = re.sub(r'([a-z])([A-Z])', r'\1 \2', t)
        t = re.sub(r'([A-Za-z])(\d)', r'\1 \2', t)
        for w in re.split(r'[^A-Za-z0-9äöüÄÖÜß]+', t):
            w = w.lower()
            if len(w) >= 2 and not w.isdigit() and w not in FUELL and w != quelle and w not in woerter:
                woerter.append(w)
    return woerter


def neue_id(quelle: str, rel: Path, belegt: set) -> str:
    kandidaten = [f'{quelle}/{_ton.slug(rel.stem)}']
    if len(rel.parts) > 1:
        eltern = [p for p in rel.parts[:-1] if p.lower() not in FUELL]
        if eltern:
            kandidaten.append(f'{quelle}/{_ton.slug(eltern[-1])}-{_ton.slug(rel.stem)}')
    for k in kandidaten:
        if k not in belegt:
            return k
    n = 2
    while f'{kandidaten[-1]}-{n}' in belegt:
        n += 1
    return f'{kandidaten[-1]}-{n}'


def ids_aufloesen(k, muster: list[str], streng=True) -> list[str]:
    alle = [s['id'] for s in k['sounds']]
    aus = []
    for m in muster:
        treffer = fnmatch.filter(alle, m) if any(c in m for c in '*?[') else ([m] if m in alle else [])
        if not treffer:
            vorschlag = ', '.join(__import__('difflib').get_close_matches(m, alle, n=3, cutoff=0.5))
            msg = f'"{m}" gibt es nicht im Katalog.' + (f' Meintest du: {vorschlag}?' if vorschlag else '')
            if streng:
                raise SystemExit('FEHLER: ' + msg)
            print('WARNUNG:', msg, 'Übersprungen.')
        aus += [t for t in treffer if t not in aus]
    return aus


def zeile(s) -> str:
    urteil = s.get('urteil') or 'offen'
    if s.get('gesperrt'):
        urteil = 'GESPERRT'
    trim = s.get('trim_db')
    trim_txt = f'{trim:+.1f}' if isinstance(trim, (int, float)) else f'~{_ton.trim_geschaetzt(s["dauer"], s.get("hell", 0)):+.1f}'
    fam = f'@{s["familie"]}' if s.get('familie') else ''
    return (f'{s["id"]:<44} {s["dauer"]:5.2f}s {s["lufs"]:6.1f} LUFS hell {s.get("hell", 0):.2f} trim {trim_txt:>5} '
            f'{urteil:<8} {fam:<10} {" ".join(s.get("tags", [])[:5])}')


# ---------------------------------------------------------------- Einlesen

def einlesen(quelle_pfad: Path, quelle: str, lizenz: str, verlinken=False, ki=True) -> list[str]:
    quelle_pfad = Path(quelle_pfad).expanduser().resolve()
    if not quelle_pfad.exists():
        raise SystemExit(f'FEHLER: {quelle_pfad} gibt es nicht.')
    quelle = _ton.slug(quelle)
    basis = _ton.sounds_ordner()
    files_root = (basis / 'files').resolve()
    if quelle_pfad.is_file():
        dateien, wurzel = [quelle_pfad], quelle_pfad.parent
    else:
        dateien = sorted(p for p in quelle_pfad.rglob('*') if p.is_file() and p.suffix.lower() in _ton.AUDIO_ENDUNGEN
                         and not p.name.startswith('.') and 'preview' not in p.name.lower())
        wurzel = quelle_pfad
    if not dateien:
        raise SystemExit(f'FEHLER: keine Audiodateien in {quelle_pfad} ({", ".join(sorted(_ton.AUDIO_ENDUNGEN))}).')
    drinnen = str(quelle_pfad).startswith(str(files_root) + os.sep) or quelle_pfad == files_root
    k = _ton.katalog_lesen()
    nach_sha = {s.get('sha256'): s for s in k['sounds']}
    belegt = {s['id'] for s in k['sounds']}
    neu, doppelt, kurz = [], 0, 0
    ziel_basis = basis / 'files' / quelle
    if not drinnen and quelle_pfad.is_dir():
        for lic in quelle_pfad.rglob('*'):
            if lic.is_file() and re.match(r'(?i)(licen[cs]e|lizenz|readme)', lic.name) and lic.suffix.lower() in ('.txt', '.md', ''):
                (ziel_basis).mkdir(parents=True, exist_ok=True)
                shutil.copy2(lic, ziel_basis / lic.name)
    print(f'Lese {len(dateien)} Dateien aus {quelle_pfad.name} ein …', flush=True)
    for nr, f in enumerate(dateien, 1):
        h = sha256(f)
        if h in nach_sha:
            doppelt += 1
            continue
        rel = f.relative_to(wurzel)
        if drinnen:
            ziel = f
        else:
            ziel = ziel_basis / rel
            ziel.parent.mkdir(parents=True, exist_ok=True)
            if not ziel.exists():
                if verlinken:
                    try:
                        os.symlink(f, ziel)
                    except OSError:
                        shutil.copy2(f, ziel)
                else:
                    shutil.copy2(f, ziel)
        x = _ton.dekodiere(ziel, max_s=30)
        if len(x) < int(0.01 * _ton.SR):
            kurz += 1
            continue
        m = _ton.messe(x)
        sid = neue_id(quelle, rel, belegt)
        belegt.add(sid)
        eintrag = {'id': sid, 'datei': str(Path(os.path.relpath(ziel, basis)).as_posix()), 'quelle': quelle, 'lizenz': lizenz,
                   **m, 'tags': tags_aus(rel, quelle), 'familie': None, 'urteil': None, 'trim_db': None, 'gesperrt': False,
                   'art': None, 'sha256': h, 'eingelesen': _ms.jetzt()}
        k['sounds'].append(eintrag)
        nach_sha[h] = eintrag
        neu.append(sid)
        if nr % 100 == 0:
            print(f'  {nr}/{len(dateien)}', flush=True)
    _ton.katalog_schreiben(k)
    dauer = sum(s['dauer'] for s in k['sounds'] if s['id'] in set(neu))
    print(f'Neu: {len(neu)} Sounds ({dauer / 60:.1f} Min), doppelt übersprungen: {doppelt}, zu kurz: {kurz}. '
          f'Bibliothek jetzt {len(k["sounds"])} Sounds.')
    _ms.log(f'Sound-Bibliothek: {len(neu)} Sounds aus {quelle} eingelesen', art='info')
    if neu and ki:
        if _ton.ki_verfuegbar():
            ki_nachruesten(set(neu))
        else:
            print('Hinweis: KI-Pakete fehlen (requirements-ki). Suche läuft als Textsuche. Später: ms sound ki')
    return neu


# ---------------------------------------------------------------- KI: AST (Anhören) und CLAP (Suche)

def clap_lesen():
    np = _ton.np_()
    p = _ton.sounds_ordner() / 'clap.npz'
    if not p.exists():
        return {}
    d = np.load(p, allow_pickle=False)
    return {str(i): (str(h), v) for i, h, v in zip(d['ids'], d['sha'], d['vektoren'])}


def clap_schreiben(vek: dict) -> None:
    np = _ton.np_()
    ids = sorted(vek)
    p = _ton.sounds_ordner() / 'clap.npz'
    tmp = p.with_name('.clap-neu.npz')
    np.savez_compressed(tmp, ids=np.array(ids), sha=np.array([vek[i][0] for i in ids]),
                        vektoren=np.stack([vek[i][1] for i in ids]).astype(np.float32) if ids else np.zeros((0, 512), np.float32))
    tmp.replace(p)


class Ki:
    def __init__(self, clap=True, ast=True):
        if not _ton.ki_verfuegbar():
            raise SystemExit('FEHLER: KI-Pakete fehlen (torch, transformers). Setup-Stufe KI installieren (Skill motion-setup).')
        import torch
        self.torch = torch
        self.dev = _ton.ki_geraet()
        if ast:
            from transformers import ASTFeatureExtractor, ASTForAudioClassification
            self.astf = _ton.hf_laden(ASTFeatureExtractor, AST_ID)
            self.astm = _ton.hf_laden(ASTForAudioClassification, AST_ID).eval().to(self.dev)
            self.labels = [self.astm.config.id2label[i] for i in range(self.astm.config.num_labels)]
        if clap:
            from transformers import ClapModel, ClapProcessor
            self.proc = _ton.hf_laden(ClapProcessor, CLAP_ID)
            self.clapm = _ton.hf_laden(ClapModel, CLAP_ID).eval().to(self.dev)

    def ast(self, x16, n=5):
        np = _ton.np_()
        seg = np.pad(x16[:16000 * 10], (0, max(0, 8000 - len(x16))))
        with self.torch.inference_mode():
            inp = self.astf(seg, sampling_rate=16000, return_tensors='pt')
            lo = self.astm(**{k: v.to(self.dev) for k, v in inp.items()}).logits[0].float().cpu().sigmoid().numpy()
        top = np.argsort(lo)[-n:][::-1]
        return [[self.labels[i], round(float(lo[i]), 3)] for i in top]

    def audio_vek(self, x48):
        np = _ton.np_()
        seg = np.pad(np.clip(x48[:48000 * 10], -1, 1), (0, max(0, 48000 - len(x48))))
        with self.torch.inference_mode():
            inp = self.proc.feature_extractor(seg, sampling_rate=48000, return_tensors='pt')
            v = self.clapm.get_audio_features(**{k: t.to(self.dev) for k, t in inp.items()})[0].float().cpu().numpy()
        return v / (np.linalg.norm(v) + 1e-9)

    def text_vek(self, q):
        np = _ton.np_()
        with self.torch.inference_mode():
            inp = self.proc.tokenizer([q], return_tensors='pt', padding=True)
            v = self.clapm.get_text_features(**{k: t.to(self.dev) for k, t in inp.items()})[0].float().cpu().numpy()
        return v / (np.linalg.norm(v) + 1e-9)


_KI_CACHE = {}


def ki_holen(clap=True, ast=True) -> Ki:
    """Modelle nur einmal pro Lauf laden."""
    for (c, a_), ki in _KI_CACHE.items():
        if (c or not clap) and (a_ or not ast):
            return ki
    ki = Ki(clap=clap, ast=ast)
    _KI_CACHE[(clap, ast)] = ki
    return ki


def ki_nachruesten(nur: set | None = None, neu_rechnen=False) -> None:
    k = _ton.katalog_lesen()
    vek = clap_lesen()
    offen = [s for s in k['sounds'] if (nur is None or s['id'] in nur) and
             (neu_rechnen or 'ast' not in s or vek.get(s['id'], ('',))[0] != s.get('sha256'))]
    if not offen:
        print('KI-Felder sind vollständig.')
        return
    print(f'KI: AST-Klassen und CLAP-Vektoren für {len(offen)} Sounds …', flush=True)
    ki = ki_holen()
    for nr, s in enumerate(offen, 1):
        datei = _ton.sound_datei(s)
        if neu_rechnen or 'ast' not in s:
            s['ast'] = ki.ast(_ton.dekodiere(datei, rate=16000, max_s=10))
        if neu_rechnen or vek.get(s['id'], ('',))[0] != s.get('sha256'):
            vek[s['id']] = (s.get('sha256', ''), ki.audio_vek(_ton.dekodiere(datei, rate=48000, max_s=10)))
        if nr % 50 == 0:
            print(f'  {nr}/{len(offen)}', flush=True)
            _ton.katalog_schreiben(k)
            clap_schreiben(vek)
    _ton.katalog_schreiben(k)
    clap_schreiben(vek)
    print(f'KI fertig: {len(offen)} Sounds ({ki.dev}).')


# ---------------------------------------------------------------- Suche

def suchwoerter(q: str) -> list[str]:
    aus = []
    for w in re.split(r'[^\wäöüß]+', q.lower()):
        if not w:
            continue
        for x in [w] + SYNONYME.get(w, []):
            if x not in aus:
                aus.append(x)
    return aus


def text_punkte(s, woerter) -> float:
    tags = set(s.get('tags', []))
    heu = ' '.join([s['id']] + s.get('tags', []) + [a[0].lower() for a in s.get('ast', [])[:3]] + [s.get('notiz') or '', s.get('einsatz') or '']).lower()
    p = 0.0
    for w in woerter:
        if w in tags:
            p += 2
        elif w in heu:
            p += 1
    return p


def suche(q: str, n=10, alle=False, ki_aus=False):
    k = _ton.katalog_lesen()
    if not k['sounds']:
        raise SystemExit('FEHLER: Bibliothek leer. Erst "ms sound laden kenney --ja" oder "ms sound einlesen …" (Skill motion-sound-bibliothek).')
    woerter = suchwoerter(q)
    kand = [s for s in k['sounds'] if alle or not (s.get('gesperrt') or s.get('urteil') == 'raus')]
    punkte = {s['id']: text_punkte(s, woerter) for s in kand}
    clap = {}
    if not ki_aus and _ton.ki_verfuegbar() and (_ton.sounds_ordner() / 'clap.npz').exists():
        np = _ton.np_()
        vek = clap_lesen()
        mit = [s for s in kand if s['id'] in vek]
        if mit:
            ki = ki_holen(ast=False)
            # Deutsche Wörter für CLAP ins Englische übersetzen (CLAP versteht vor allem Englisch)
            q_en = ' '.join(SYNONYME.get(w, [w])[0] for w in re.split(r'\s+', q.lower()) if w)
            t = ki.text_vek(q_en)
            sc = np.stack([vek[s['id']][1] for s in mit]) @ t
            clap = {s['id']: float(v) for s, v in zip(mit, sc)}
            fehlen = len(kand) - len(mit)
            if fehlen:
                print(f'Hinweis: {fehlen} Sounds ohne CLAP-Vektor (ms sound ki rechnet sie nach).')
    if clap:
        rang = sorted(kand, key=lambda s: -(clap.get(s['id'], -1) + 0.04 * min(punkte[s['id']], 4)))
        art = f'CLAP + Text ("{q}")'
    else:
        rang = sorted([s for s in kand if punkte[s['id']] > 0],
                      key=lambda s: (-punkte[s['id']], s.get('urteil') != 'behalten', s['dauer']))
        art = f'Textsuche nach {", ".join(woerter)}'
    fam = [f for f in k['familien'] if any(w in f for w in woerter)]
    return rang[:n], clap, punkte, art, fam, k


# ---------------------------------------------------------------- Abhörseite

def abhoeren_seite(k, auswahl, server_token=None) -> Path:
    daten = []
    for s in auswahl:
        daten.append({'id': s['id'], 'datei': s['datei'], 'tags': s.get('tags', [])[:6], 'dauer': s['dauer'], 'lufs': s['lufs'],
                      'hell': s.get('hell', 0), 'urteil': s.get('urteil'), 'trim': s.get('trim_db'),
                      'schaetz': _ton.trim_geschaetzt(s['dauer'], s.get('hell', 0)), 'familie': s.get('familie'),
                      'gesperrt': bool(s.get('gesperrt')), 'quelle': s.get('quelle'), 'notiz': s.get('notiz') or '',
                      'ast': (s.get('ast') or [[None]])[0][0]})
    html = (ABHOER_HTML.replace('__DATEN__', json.dumps(daten, ensure_ascii=False).replace('</', '<\\/'))
            .replace('__FAMILIEN__', json.dumps(sorted(k['familien']), ensure_ascii=False))
            .replace('__TOKEN__', server_token or ''))
    p = _ton.sounds_ordner() / 'abhoeren.html'
    p.write_text(html, encoding='utf-8')
    return p


def urteile_anwenden(daten: dict) -> int:
    k = _ton.katalog_lesen()
    idx = _ton.index(k)
    urteile = daten.get('urteile', daten)
    n = 0
    for sid, u in urteile.items():
        s = idx.get(sid)
        if not s or not isinstance(u, dict):
            continue
        if 'urteil' in u:
            s['urteil'] = u['urteil'] if u['urteil'] in ('behalten', 'raus') else None
        if 'trim_db' in u and u['trim_db'] is not None:
            s['trim_db'] = round(float(u['trim_db']), 1)
        if 'notiz' in u:
            s['notiz'] = str(u['notiz'] or '')[:300]
        if 'familie' in u:
            fam = _ton.slug(u['familie']).replace('-', '') if u['familie'] else None
            for f in k['familien'].values():
                if sid in f.get('mitglieder', []) and fam is None:
                    f['mitglieder'].remove(sid)
            if fam:
                for name, f in k['familien'].items():
                    if name != fam and sid in f.get('mitglieder', []):
                        f['mitglieder'].remove(sid)
                f = k['familien'].setdefault(fam, {'einsatz': '', 'mitglieder': []})
                if sid not in f['mitglieder']:
                    f['mitglieder'].append(sid)
        n += 1
    _ton.katalog_schreiben(k)
    return n


def server_starten(port: int, token: str, oeffnen=True):
    basis = _ton.sounds_ordner()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(basis), **kw)

        def log_message(self, *a):
            pass

        def do_GET(self):
            pfad = self.path.split('?')[0]
            if not (pfad in ('/', '/abhoeren.html') or pfad.startswith('/files/')):
                self.send_error(404)
                return
            if pfad == '/':
                self.path = '/abhoeren.html'
            super().do_GET()

        def do_POST(self):
            if self.path != '/speichern' or self.headers.get('X-Token') != token:
                self.send_error(403)
                return
            laenge = int(self.headers.get('Content-Length') or 0)
            if laenge > 5_000_000:
                self.send_error(413)
                return
            try:
                daten = json.loads(self.rfile.read(laenge).decode('utf-8'))
                n = urteile_anwenden(daten)
                antwort, code = {'ok': True, 'n': n}, 200
            except Exception as e:  # Seite soll eine lesbare Antwort bekommen
                antwort, code = {'ok': False, 'fehler': str(e)[:200]}, 400
            roh = json.dumps(antwort).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(roh)))
            self.end_headers()
            self.wfile.write(roh)

    srv = http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler)
    url = f'http://127.0.0.1:{port}/abhoeren.html#token={token}'
    print(f'Abhörseite läuft: {url}', flush=True)
    print('Urteile werden sofort im Katalog gespeichert. Beenden mit Strg+C.', flush=True)
    _ms.log('Abhörseite der Sound-Bibliothek gestartet', art='info')
    if oeffnen:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nAbhörseite beendet.')


# ---------------------------------------------------------------- Gegenprobe

def gegenprobe(ziel: str, spots: list[str], fenster: float, n: int):
    np = _ton.np_()
    p = Path(ziel).expanduser()
    bericht = None
    if not (p.exists() and p.is_file()):
        ordner = _ms.ziel_pfad(ziel)
        p = ordner / 'build' / 'assets' / 'audio' / '_sfx_bus.wav'
        bericht = _ms.json_lesen(ordner / 'build' / 'assets' / 'audio' / 'mix_bericht.json', {})
        if not p.exists():
            raise SystemExit('FEHLER: build/assets/audio/_sfx_bus.wav fehlt. Erst "ms mix <folge>".')
    punkte = []
    for a in spots:
        t, _, name = a.partition(':')
        punkte.append((float(t.replace(',', '.')), name))
    if not punkte and bericht:
        ev = sorted(bericht.get('ereignisse', []), key=lambda e: (e.get('margin_db', 9), e['t']))[:n]
        punkte = [(e['t'], e['sound']) for e in sorted(ev, key=lambda e: e['t'])]
    if not punkte:
        raise SystemExit('FEHLER: keine Zeitpunkte. Beispiel: ms sound gegenprobe <folge> 2.4:Glas 7.1:Klick')
    ki = ki_holen(clap=False)
    k = _ton.katalog_lesen()
    idx = _ton.index(k)
    x = _ton.dekodiere(p, rate=16000)
    print(f'AST-Gegenprobe ({fenster:.2f}-s-Fenster ab dem Zeitpunkt). Hört die Maschine etwas völlig anderes, Sound tauschen.')
    for t, name in punkte:
        seg = x[int(t * 16000):int((t + fenster) * 16000)]
        if not len(seg) or np.abs(seg).max() < 1e-4:
            print(f'{t:7.2f} {name[:30]:30s} | still')
            continue
        top = ki.ast(seg, 3)
        erwartet = ''
        if name in idx:
            erwartet = ' (Katalog: ' + ', '.join((idx[name].get('tags') or [])[:3]) + ')'
        print(f'{t:7.2f} {name[:30]:30s} | ' + ', '.join(f'{a[:24]} {b:.2f}' for a, b in top) + erwartet)


# ---------------------------------------------------------------- Befehle

def cmd_laden(a):
    if a.was == 'kenney':
        print('Kenney-Audio-Packs (CC0, kommerziell frei, ohne Namensnennung). Ermittle Download-Links …')
        packs = []
        for p in KENNEY_PACKS:
            html = lade_url(f'https://kenney.nl/assets/{p}')
            m = re.search(r"(https?://kenney\.nl)?(/media/pages/assets/" + re.escape(p) + r"/[^'\"\s]+\.zip)", html)
            if not m:
                raise SystemExit(f'FEHLER: Download-Link für {p} nicht gefunden. Seite https://kenney.nl/assets/{p} im Browser öffnen, '
                                 f'Zip von Hand laden und mit "ms sound einlesen <ordner> --quelle kenney --lizenz CC0" übernehmen.')
            url = 'https://kenney.nl' + m.group(2)
            groesse = lade_url(url, kopf=True)
            packs.append((p, url, groesse))
            print(f'  {p:<18} {mb(groesse):>8}  {url}')
        gesamt = sum(g for _, _, g in packs)
        print(f'Zusammen {mb(gesamt)} Download.')
        if not a.ja:
            print('Nichts geladen. Mit --ja laden, entpacken und einlesen.')
            return
        dl = _ton.sounds_ordner() / '_downloads'
        ziel = _ton.sounds_ordner() / 'files' / 'kenney'
        for p, url, groesse in packs:
            z = dl / f'kenney_{p}.zip'
            if not (z.exists() and z.stat().st_size == groesse):
                print(f'Lade {p} …', flush=True)
                lade_url(url, z)
            with zipfile.ZipFile(z) as zf:
                for info in zf.infolist():
                    name = Path(info.filename)
                    if info.is_dir() or '..' in name.parts or name.is_absolute():
                        continue
                    ist_audio = name.suffix.lower() in _ton.AUDIO_ENDUNGEN and 'preview' not in name.name.lower()
                    ist_lizenz = re.match(r'(?i)licen[cs]e', name.name) is not None
                    if not (ist_audio or ist_lizenz):
                        continue
                    teile = [t for t in name.parts if t.lower() != 'audio']
                    dest = ziel / p / Path(*teile)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as q, open(dest, 'wb') as f:
                        shutil.copyfileobj(q, f)
        einlesen(ziel, 'kenney', KENNEY_LIZENZ, ki=not a.ohne_ki)
        return
    if a.was == 'mixkit':
        if not a.id or not re.fullmatch(r'\d+', a.id):
            raise SystemExit('FEHLER: Mixkit-Nummer fehlt (z. B. 2568). Sie steht in der Adresse des Sounds auf mixkit.co.')
        url = f'https://assets.mixkit.co/active_storage/sfx/{a.id}/{a.id}.wav'
        groesse = lade_url(url, kopf=True)
        print(f'Mixkit {a.id}: {mb(groesse)} ({url}). Lizenz: {MIXKIT_LIZENZ}')
        print('Achtung: Auf Mixkit-Listenseiten gehört der Titel nicht immer zur Vorschau daneben. Nach dem Laden anhören.')
        if not a.ja:
            print('Nichts geladen. Mit --ja laden und einlesen. Nur einzelne Sounds, keine Massen-Downloads.')
            return
        dest = _ton.sounds_ordner() / 'files' / 'mixkit' / f'mixkit-{a.id}{"-" + _ton.slug(a.name) if a.name else ""}.wav'
        lade_url(url, dest)
        einlesen(dest, 'mixkit', MIXKIT_LIZENZ, ki=not a.ohne_ki)
        return
    raise SystemExit('FEHLER: unbekannte Quelle. Möglich: kenney, mixkit. Andere Quellen von Hand laden, dann "ms sound einlesen".')


def cmd_suche(a):
    treffer, clap, punkte, art, fam, k = suche(a.begriff, a.n, a.alle, a.ohne_ki)
    print(f'{art}: {len(treffer)} Treffer')
    for s in treffer:
        sc = f'{clap[s["id"]]:.3f}' if s['id'] in clap else f'{punkte[s["id"]]:>5.0f}'
        ast = f' | hört: {s["ast"][0][0]}' if s.get('ast') else ''
        print(f'{sc}  {zeile(s)}{ast}')
    for f in fam:
        print(f'Familie @{f}: {", ".join(k["familien"][f]["mitglieder"][:8])}')
    if not treffer:
        print('Nichts gefunden. Anderes Wort (englisch: click, pop, whoosh, impact …) oder Lücke füllen (Skill motion-sound-bibliothek).')


def filtern(k, a):
    aus = k['sounds']
    if getattr(a, 'quelle', None):
        aus = [s for s in aus if s.get('quelle') == a.quelle]
    if getattr(a, 'familie', None):
        f = a.familie.lstrip('@')
        aus = [s for s in aus if s.get('familie') == f]
    if getattr(a, 'urteil', None):
        aus = [s for s in aus if (s.get('urteil') or 'offen') == a.urteil]
    if getattr(a, 'gesperrt', False):
        aus = [s for s in aus if s.get('gesperrt')]
    if getattr(a, 'ids', None):
        wahl = set(ids_aufloesen(k, a.ids))
        aus = [s for s in aus if s['id'] in wahl]
    return aus


def cmd_liste(a):
    k = _ton.katalog_lesen()
    aus = filtern(k, a)
    if a.json:
        print(json.dumps(aus[:a.n], ensure_ascii=False, indent=1))
        return
    nach_q = {}
    for s in k['sounds']:
        nach_q[s.get('quelle')] = nach_q.get(s.get('quelle'), 0) + 1
    print(f'Bibliothek: {len(k["sounds"])} Sounds ({", ".join(f"{q} {n}" for q, n in nach_q.items())}), '
          f'{len(k["familien"])} Familien, Auswahl {len(aus)}')
    for s in aus[:a.n]:
        print(zeile(s))
    if len(aus) > a.n:
        print(f'… {len(aus) - a.n} weitere (--n erhöhen)')


def cmd_info(a):
    k = _ton.katalog_lesen()
    for sid in ids_aufloesen(k, [a.id]):
        s = _ton.index(k)[sid]
        print(json.dumps(s, ensure_ascii=False, indent=1))
        print('Datei:', _ton.sound_datei(s))


def cmd_abhoeren(a):
    k = _ton.katalog_lesen()
    if not k['sounds']:
        raise SystemExit('FEHLER: Bibliothek leer. Erst laden oder einlesen.')
    aus = filtern(k, a)
    if a.neu:
        aus = [s for s in aus if not s.get('urteil')]
    if not aus:
        raise SystemExit('Keine Sounds in dieser Auswahl.')
    token = secrets.token_urlsafe(16) if a.server else None
    p = abhoeren_seite(k, aus, token)
    print(f'Abhörseite mit {len(aus)} Sounds: {p}')
    if a.server:
        server_starten(a.port, token, not a.kein_browser)
    else:
        print('Im Browser öffnen (Chrome oder Firefox, Safari spielt .ogg nicht überall). Am Ende "Export" klicken, dann:')
        print('  ms sound urteile <heruntergeladene urteile-….json>')
        print('Bequemer: ms sound abhoeren --server (speichert sofort, nur auf diesem Rechner erreichbar).')


def cmd_urteile(a):
    p = Path(a.datei).expanduser()
    daten = _ms.json_lesen(p)
    if not daten:
        raise SystemExit(f'FEHLER: {p} fehlt oder ist leer.')
    n = urteile_anwenden(daten)
    k = _ton.katalog_lesen()
    beh = sum(1 for s in k['sounds'] if s.get('urteil') == 'behalten')
    raus = sum(1 for s in k['sounds'] if s.get('urteil') == 'raus')
    print(f'{n} Urteile übernommen. Bibliothek: {beh} behalten, {raus} raus, {len(k["sounds"]) - beh - raus} offen.')
    _ms.log(f'Sound-Urteile übernommen ({n})', art='info')


def cmd_familie(a):
    k = _ton.katalog_lesen()
    if not a.name:
        if not k['familien']:
            print('Noch keine Familien. Beispiel: ms sound familie whoosh "kenney/*whoosh*" --einsatz "Bewegung, Szenenwechsel"')
        for name, f in sorted(k['familien'].items()):
            print(f'@{name:<10} {len(f["mitglieder"]):>3} Varianten  {f.get("einsatz", "")}')
            print('            ' + ', '.join(f['mitglieder']))
        return
    name = _ton.slug(a.name.lstrip('@')).replace('-', '')
    if a.aufloesen:
        if name in k['familien']:
            del k['familien'][name]
            _ton.katalog_schreiben(k)
            print(f'Familie @{name} aufgelöst (die Sounds bleiben in der Bibliothek).')
        return
    # Muster ohne Treffer werden mit Warnung übersprungen (z. B. "mixkit/*whoosh*", solange nur Kenney geladen ist)
    ids = ids_aufloesen(k, a.ids, streng=False) if a.ids else []
    if a.ids and not ids and not a.entfernen and not k['familien'].get(name, {}).get('mitglieder'):
        raise SystemExit(f'FEHLER: Kein Muster hat einen Sound getroffen, @{name} bleibt leer und wird nicht angelegt. '
                         f'ms sound suche "<begriff>" zeigt passende IDs.')
    f = k['familien'].setdefault(name, {'einsatz': '', 'mitglieder': []})
    if a.einsatz:
        f['einsatz'] = a.einsatz
    idx = _ton.index(k)
    if a.entfernen:
        f['mitglieder'] = [m for m in f['mitglieder'] if m not in ids]
    else:
        for sid in ids:
            for n2, f2 in k['familien'].items():
                if n2 != name and sid in f2['mitglieder']:
                    f2['mitglieder'].remove(sid)
                    print(f'  {sid} wechselt von @{n2} nach @{name}')
            if sid not in f['mitglieder']:
                f['mitglieder'].append(sid)
            s = idx[sid]
            if s.get('gesperrt') or s.get('urteil') == 'raus':
                print(f'WARNUNG: {sid} ist {"gesperrt" if s.get("gesperrt") else "aussortiert"}, der Mix überspringt ihn.')
    _ton.katalog_schreiben(k)
    print(f'@{name}: {len(f["mitglieder"])} Varianten. Im Mix "@{name}" schreiben, dann wechselt die Variante reihum.')
    if len(f['mitglieder']) < 3:
        print('Hinweis: mindestens 3 Varianten, sonst hört man die Wiederholung.')


def cmd_setzen(a):
    k = _ton.katalog_lesen()
    ids = ids_aufloesen(k, a.ids)
    idx = _ton.index(k)
    for sid in ids:
        s = idx[sid]
        if a.urteil:
            s['urteil'] = None if a.urteil == 'offen' else a.urteil
            if a.urteil == 'behalten' and s.get('trim_db') is None and a.trim is None:
                s['trim_db'] = round(_ton.trim_geschaetzt(s['dauer'], s.get('hell', 0)), 1)   # wie die Abhörseite, nicht 0
        if a.trim is not None:
            s['trim_db'] = round(a.trim, 1)
        if a.art:
            s['art'] = a.art
        if a.von is not None:
            s['von'] = round(a.von, 3)
        if a.bis is not None:
            s['bis'] = round(a.bis, 3)
        if a.unter_stimme is not None:
            s['unter_stimme_db'] = round(a.unter_stimme, 1)
        if a.tags:
            s['tags'] = [t.strip().lower() for t in a.tags.split(',') if t.strip()]
        if a.notiz is not None:
            s['notiz'] = a.notiz
        if a.einsatz is not None:
            s['einsatz'] = a.einsatz
    _ton.katalog_schreiben(k)
    print(f'{len(ids)} Sounds geändert.')
    for sid in ids[:20]:
        print(zeile(idx[sid]))


def cmd_sperren(a):
    k = _ton.katalog_lesen()
    ids = ids_aufloesen(k, a.ids)
    idx = _ton.index(k)
    for sid in ids:
        idx[sid]['gesperrt'] = not a.weg
        if a.grund and not a.weg:
            idx[sid]['sperr_grund'] = a.grund
        if a.weg:
            idx[sid].pop('sperr_grund', None)
    _ton.katalog_schreiben(k)
    print(f'{len(ids)} Sounds {"entsperrt" if a.weg else "gesperrt (jeder Mix mit ihnen bricht ab)"}: {", ".join(ids[:10])}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='befehl')

    p = sub.add_parser('laden', help='kenney (7 CC0-Packs) oder einen Mixkit-Sound laden')
    p.add_argument('was', choices=['kenney', 'mixkit'])
    p.add_argument('id', nargs='?')
    p.add_argument('--name')
    p.add_argument('--ja', action='store_true')
    p.add_argument('--ohne-ki', action='store_true')

    p = sub.add_parser('einlesen', help='Ordner oder Datei in die Bibliothek übernehmen')
    p.add_argument('ordner')
    p.add_argument('--quelle', required=True)
    p.add_argument('--lizenz', required=True)
    p.add_argument('--verlinken', action='store_true', help='verlinken statt kopieren (spart Platz)')
    p.add_argument('--ohne-ki', action='store_true')

    p = sub.add_parser('ki', help='AST-Klassen und CLAP-Vektoren nachrüsten')
    p.add_argument('--neu', action='store_true', help='alles neu rechnen')

    p = sub.add_parser('suche')
    p.add_argument('begriff')
    p.add_argument('--n', type=int, default=10)
    p.add_argument('--alle', action='store_true', help='auch gesperrte und aussortierte')
    p.add_argument('--ohne-ki', action='store_true')

    p = sub.add_parser('liste')
    p.add_argument('--quelle')
    p.add_argument('--familie')
    p.add_argument('--urteil', choices=['behalten', 'raus', 'offen'])
    p.add_argument('--gesperrt', action='store_true')
    p.add_argument('--n', type=int, default=40)
    p.add_argument('--json', action='store_true')

    p = sub.add_parser('info')
    p.add_argument('id')

    p = sub.add_parser('abhoeren')
    p.add_argument('--neu', action='store_true', help='nur Sounds ohne Urteil')
    p.add_argument('--quelle')
    p.add_argument('--familie')
    p.add_argument('--ids', nargs='+')
    p.add_argument('--server', action='store_true', help='lokaler Server auf 127.0.0.1, speichert sofort')
    p.add_argument('--port', type=int, default=8778)
    p.add_argument('--kein-browser', action='store_true')

    p = sub.add_parser('urteile')
    p.add_argument('datei')

    p = sub.add_parser('familie')
    p.add_argument('name', nargs='?')
    p.add_argument('ids', nargs='*')
    p.add_argument('--einsatz')
    p.add_argument('--entfernen', action='store_true')
    p.add_argument('--aufloesen', action='store_true')

    p = sub.add_parser('setzen')
    p.add_argument('ids', nargs='+')
    p.add_argument('--urteil', choices=['behalten', 'raus', 'offen'])
    p.add_argument('--trim', type=float)
    p.add_argument('--art', choices=['allzweck', 'motiv', 'nische', 'hook'])
    p.add_argument('--von', type=float)
    p.add_argument('--bis', type=float)
    p.add_argument('--unter-stimme', type=float)
    p.add_argument('--tags')
    p.add_argument('--notiz')
    p.add_argument('--einsatz')

    p = sub.add_parser('sperren')
    p.add_argument('ids', nargs='+')
    p.add_argument('--grund')
    p.add_argument('--weg', action='store_true')

    p = sub.add_parser('gegenprobe')
    p.add_argument('ziel')
    p.add_argument('spots', nargs='*')
    p.add_argument('--fenster', type=float, default=0.45)
    p.add_argument('--n', type=int, default=10)

    a = ap.parse_args()
    if a.befehl == 'laden':
        cmd_laden(a)
    elif a.befehl == 'einlesen':
        einlesen(Path(a.ordner), a.quelle, a.lizenz, a.verlinken, not a.ohne_ki)
    elif a.befehl == 'ki':
        ki_nachruesten(None, a.neu)
    elif a.befehl == 'suche':
        cmd_suche(a)
    elif a.befehl == 'liste':
        cmd_liste(a)
    elif a.befehl == 'info':
        cmd_info(a)
    elif a.befehl == 'abhoeren':
        cmd_abhoeren(a)
    elif a.befehl == 'urteile':
        cmd_urteile(a)
    elif a.befehl == 'familie':
        cmd_familie(a)
    elif a.befehl == 'setzen':
        cmd_setzen(a)
    elif a.befehl == 'sperren':
        cmd_sperren(a)
    elif a.befehl == 'gegenprobe':
        gegenprobe(a.ziel, a.spots, a.fenster, a.n)
    else:
        ap.print_help()


ABHOER_HTML = r'''<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sounds abhören</title>
<link rel="icon" href="data:,">
<style>
:root{--bg:#f6f4ef;--fl:#fffdf8;--tx:#1c1b19;--mu:#6f6a60;--li:#e3ded3;--ak:#c2410c;--ok:#15803d;--no:#b91c1c;--sel:#fff1e6}
@media (prefers-color-scheme:dark){:root{--bg:#161513;--fl:#1f1e1b;--tx:#ece8df;--mu:#9b958a;--li:#34312c;--ak:#fb923c;--ok:#4ade80;--no:#f87171;--sel:#2b2118}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
header{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--li);padding:14px 16px}
h1{font-size:19px;margin:0 0 4px}
.hilfe{color:var(--mu);font-size:13px;margin:0 0 10px;max-width:980px}
.leiste{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
input[type=search],input[type=text]{background:var(--fl);color:var(--tx);border:1px solid var(--li);border-radius:8px;padding:7px 10px;font:inherit}
input[type=search]{flex:1 1 220px;min-width:0}
button{font:inherit;border:1px solid var(--li);background:var(--fl);color:var(--tx);border-radius:8px;padding:6px 11px;cursor:pointer}
button:hover{border-color:var(--mu)}
button.an.beh{background:var(--ok);border-color:var(--ok);color:#fff}
button.an.raus{background:var(--no);border-color:var(--no);color:#fff}
.status{color:var(--mu);font-size:13px;margin-left:auto}
main{padding:8px 16px 60px;max-width:1100px}
.zeile{display:grid;grid-template-columns:44px minmax(0,1fr) auto;gap:10px;align-items:center;background:var(--fl);border:1px solid var(--li);border-radius:10px;padding:9px 11px;margin:7px 0}
.zeile.sel{outline:2px solid var(--ak);background:var(--sel)}
.zeile.gesperrt{opacity:.55}
.play{width:40px;height:40px;border-radius:50%;padding:0;font-size:15px}
.name{font-weight:600;word-break:break-all}
.meta{color:var(--mu);font-size:12.5px}
.rechts{display:flex;flex-wrap:wrap;gap:6px;align-items:center;justify-content:flex-end}
.trim{display:flex;align-items:center;gap:6px;font-variant-numeric:tabular-nums;font-size:13px}
.trim input{width:120px;accent-color:var(--ak)}
.geschaetzt{color:var(--ak)}
.fam{width:96px}
kbd{border:1px solid var(--li);border-bottom-width:2px;border-radius:4px;padding:0 4px;font-size:12px}
@media (max-width:720px){.zeile{grid-template-columns:44px minmax(0,1fr)}.rechts{grid-column:1/-1;justify-content:flex-start}}
</style>
</head>
<body>
<header>
  <h1>Sounds abhören</h1>
  <p class="hilfe">Alle Sounds spielen gleich laut (gemessen). Wirkt einer trotzdem lauter (oft lange oder helle Sounds), den Regler nach links,
  bis er gleich laut wirkt. Orange = geschätzte Korrektur, noch nicht gehört. <b>Behalten</b> oder <b>Raus</b> je Sound.
  Tasten: <kbd>↑</kbd><kbd>↓</kbd> wählen, <kbd>Leertaste</kbd> abspielen, <kbd>A</kbd> Referenz und dann dieser Sound,
  <kbd>B</kbd> behalten, <kbd>R</kbd> raus, <kbd>←</kbd><kbd>→</kbd> Korrektur ±0,5 dB.</p>
  <div class="leiste">
    <input type="search" id="filter" placeholder="Filter: Name, Tag, Familie …">
    <label><input type="checkbox" id="nurOffen"> nur offene</label>
    <button id="ref">Referenz abspielen</button>
    <button id="export">Export</button>
    <span class="status" id="status"></span>
  </div>
</header>
<main id="liste"></main>
<audio id="player" preload="none"></audio>
<script>
const SOUNDS = __DATEN__;
const FAMILIEN = __FAMILIEN__;
const TOKEN_SERVER = "__TOKEN__";
const REF_LUFS = -24;
const SPEICHER = "ms-abhoeren-v1";
const token = (location.hash.match(/token=([\w-]+)/) || [])[1] || "";
const server = location.protocol.startsWith("http") && token && token === TOKEN_SERVER;
let geaendert = {};
try { geaendert = JSON.parse(localStorage.getItem(SPEICHER) || "{}"); } catch (e) { geaendert = {}; }
const player = document.getElementById("player");
let sel = 0, sichtbar = [], refId = null;

function wert(s, k) { const g = geaendert[s.id]; return g && k in g ? g[k] : s[k]; }
function trimVon(s) { const t = wert(s, "trim"); return t === null || t === undefined ? null : t; }
function lautstaerke(s) { const t = trimVon(s); const tr = t === null ? s.schaetz : t; return Math.min(1, Math.pow(10, (REF_LUFS - s.lufs + tr) / 20)); }
function spiele(s) { player.src = s.datei; player.volume = lautstaerke(s); player.currentTime = 0; player.play().catch(() => {}); }
function setze(s, k, v) {
  geaendert[s.id] = Object.assign(geaendert[s.id] || {}, {[k]: v});
  if (k === "urteil" && v === "behalten" && trimVon(s) === null) geaendert[s.id].trim = s.schaetz;
  try { localStorage.setItem(SPEICHER, JSON.stringify(geaendert)); } catch (e) {}
  speichern();
}
let timer = null;
function exportDaten() {
  const u = {};
  for (const [id, g] of Object.entries(geaendert)) {
    const e = {};
    if ("urteil" in g) e.urteil = g.urteil;
    if ("trim" in g && g.trim !== null) e.trim_db = g.trim;
    if ("familie" in g) e.familie = g.familie;
    if ("notiz" in g) e.notiz = g.notiz;
    u[id] = e;
  }
  return {art: "motion-studio-urteile", zeit: new Date().toISOString(), urteile: u};
}
function speichern() {
  const st = document.getElementById("status");
  if (!server) { st.textContent = Object.keys(geaendert).length + " geändert, nicht gespeichert: am Ende Export"; return; }
  clearTimeout(timer);
  timer = setTimeout(async () => {
    try {
      const r = await fetch("/speichern", {method: "POST", headers: {"Content-Type": "application/json", "X-Token": token}, body: JSON.stringify(exportDaten())});
      const d = await r.json();
      st.textContent = d.ok ? "gespeichert (" + d.n + ")" : "Fehler: " + d.fehler;
    } catch (e) { st.textContent = "Server nicht erreichbar: Export nutzen"; }
  }, 400);
}
function el(tag, attrs, kinder) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) { if (k === "text") e.textContent = v; else if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v); }
  for (const c of kinder || []) e.append(c);
  return e;
}
function zeichne() {
  const f = document.getElementById("filter").value.toLowerCase().trim();
  const nurOffen = document.getElementById("nurOffen").checked;
  const liste = document.getElementById("liste");
  liste.innerHTML = "";
  sichtbar = SOUNDS.filter(s => (!nurOffen || !wert(s, "urteil")) &&
    (!f || (s.id + " " + s.tags.join(" ") + " " + (wert(s, "familie") || "") + " " + (s.ast || "")).toLowerCase().includes(f)));
  if (sel >= sichtbar.length) sel = Math.max(0, sichtbar.length - 1);
  sichtbar.forEach((s, i) => {
    const t = trimVon(s), urteil = wert(s, "urteil");
    const zahl = el("span", {text: (t === null ? s.schaetz : t).toFixed(1) + " dB", class: t === null ? "geschaetzt" : ""});
    const regler = el("input", {type: "range", min: "-12", max: "6", step: "0.5", value: String(t === null ? s.schaetz : t), "aria-label": "Korrektur in dB",
      oninput: e => { setze(s, "trim", parseFloat(e.target.value)); zahl.textContent = parseFloat(e.target.value).toFixed(1) + " dB"; zahl.className = ""; },
      onchange: () => spiele(s)});
    const fam = el("input", {type: "text", class: "fam", list: "familien", placeholder: "Familie", value: wert(s, "familie") || "",
      onchange: e => setze(s, "familie", e.target.value.trim() || null)});
    const zeile = el("div", {class: "zeile" + (i === sel ? " sel" : "") + (s.gesperrt ? " gesperrt" : ""), onclick: () => { sel = i; markiere(); }}, [
      el("button", {class: "play", text: "▶", title: "abspielen", onclick: e => { e.stopPropagation(); sel = i; markiere(); spiele(s); }}),
      el("div", {}, [el("div", {class: "name", text: s.id + (s.gesperrt ? "  (gesperrt)" : "")}),
        el("div", {class: "meta", text: s.dauer.toFixed(2) + " s · " + s.lufs.toFixed(1) + " LUFS · hell " + Math.round(s.hell * 100) + " % · " + s.tags.join(" ") + (s.ast ? " · hört: " + s.ast : "")})]),
      el("div", {class: "rechts"}, [
        el("div", {class: "trim"}, [regler, zahl]), fam,
        el("button", {text: "Behalten", class: "beh" + (urteil === "behalten" ? " an" : ""), onclick: e => { e.stopPropagation(); setze(s, "urteil", urteil === "behalten" ? null : "behalten"); zeichne(); }}),
        el("button", {text: "Raus", class: "raus" + (urteil === "raus" ? " an" : ""), onclick: e => { e.stopPropagation(); setze(s, "urteil", urteil === "raus" ? null : "raus"); zeichne(); }}),
        el("button", {text: "Referenz", title: "als Vergleich festlegen", onclick: e => { e.stopPropagation(); refId = s.id; document.getElementById("status").textContent = "Referenz: " + s.id; }})
      ])]);
    liste.append(zeile);
  });
}
function markiere() { document.querySelectorAll(".zeile").forEach((z, i) => z.classList.toggle("sel", i === sel)); const z = document.querySelectorAll(".zeile")[sel]; if (z) z.scrollIntoView({block: "nearest"}); }
function referenz() { return SOUNDS.find(s => s.id === refId) || SOUNDS.find(s => wert(s, "urteil") === "behalten") || SOUNDS[0]; }
function abVergleich(s) { const r = referenz(); spiele(r); setTimeout(() => spiele(s), Math.min(1600, r.dauer * 1000 + 350)); }
document.getElementById("filter").addEventListener("input", () => { sel = 0; zeichne(); });
document.getElementById("nurOffen").addEventListener("change", () => { sel = 0; zeichne(); });
document.getElementById("ref").addEventListener("click", () => spiele(referenz()));
document.getElementById("export").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(exportDaten(), null, 1)], {type: "application/json"});
  const a = el("a", {href: URL.createObjectURL(blob), download: "urteile-" + new Date().toISOString().slice(0, 10) + ".json"});
  document.body.append(a); a.click(); a.remove();
  document.getElementById("status").textContent = "Export geladen: ms sound urteile <datei>";
});
document.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT" && e.target.type !== "range") return;
  const s = sichtbar[sel]; if (!s) return;
  if (e.key === "ArrowDown" || e.key === "j") { sel = Math.min(sichtbar.length - 1, sel + 1); markiere(); e.preventDefault(); }
  else if (e.key === "ArrowUp" || e.key === "k") { sel = Math.max(0, sel - 1); markiere(); e.preventDefault(); }
  else if (e.key === " " || e.key === "Enter") { spiele(s); e.preventDefault(); }
  else if (e.key === "a") abVergleich(s);
  else if (e.key === "b") { setze(s, "urteil", "behalten"); zeichne(); }
  else if (e.key === "r") { setze(s, "urteil", "raus"); zeichne(); }
  else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
    const t = trimVon(s); const neu = Math.max(-12, Math.min(6, (t === null ? s.schaetz : t) + (e.key === "ArrowLeft" ? -0.5 : 0.5)));
    setze(s, "trim", neu); zeichne(); spiele(s); e.preventDefault();
  }
});
const dl = el("datalist", {id: "familien"}, FAMILIEN.map(f => el("option", {value: f})));
document.body.append(dl);
zeichne();
if (server) document.getElementById("status").textContent = "speichert direkt in den Katalog";
else speichern();
</script>
</body>
</html>
'''

if __name__ == '__main__':
    sys.exit(main())
