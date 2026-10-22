"""Claude-Code-Terminal lesen (Text aus `tmux capture-pane -p -J`), ohne Netz und ohne Zustand.
  frage(zeilen)       offene Frage: Auswahl-Menü (AskUserQuestion oder Freigabe-Abfrage) oder letzte Nachricht des Agenten
  taetigkeit(zeilen)  was der Agent gerade tut (denkt, liest, schreibt, rendert, gibt an einen Subagenten ab …)
  gespraech(zeilen)   Verlauf als Gespräch: deine Eingaben, Antworten des Agenten, Werkzeuge mit Ergebnis
Formate geprüft an echten Bildschirmen (Claude Code 2.1, 22.10.2026):
  Auswahl:  „☐ Kopf“ · Frage · „❯ 1. Option“ + eingerückte Erklärung · „4. Type something.“ · „Enter to select …“
            Ziffer setzt nur den Cursor, Enter wählt. Bei „Type something“: Ziffer, Text tippen, Enter.
  Freigabe: Werkzeug-Kasten · „Do you want to proceed?“ · „❯ 1. Yes“ … · „Esc to cancel“. Ziffer wählt sofort, ohne Enter.
  Nachricht: „⏺ Text“ (Folgezeilen 2 Leerzeichen eingerückt), Werkzeug: „⏺ Bash(befehl)“ + „  ⎿  Ergebnis“.
python3 terminal_lesen.py --test   prüft die Beispiele unten."""
from __future__ import annotations

import re
import sys

OPTION_RE = re.compile(r'^\s*[│|]?\s*(❯\s*)?(\d{1,2})\.\s+(.*?)\s*[│|]?\s*$')
TRENN_RE = re.compile(r'^\s*[─━═╌┄┈\-]{8,}\s*$')
KOPF_RE = re.compile(r'^\s*[☐☒✔✓□■]\s+(.+?)\s*$')
FUSS_AUSWAHL_RE = re.compile(r'Enter to (select|submit|confirm)', re.I)
FUSS_FREIGABE_RE = re.compile(r'Esc to cancel', re.I)
FREIGABE_RE = re.compile(r'Do you want|Möchtest du|Would you like', re.I)
FREI_RE = re.compile(r'^(Type something|Something else|Other|Etwas anderes|Eigene Antwort)', re.I)
CHAT_RE = re.compile(r'^Chat about this', re.I)
BLASE_RE = re.compile(r'^\s*[⏺●]\s?(.*)$')
WERKZEUG_RE = re.compile(r'^\s*[⏺●]\s+([A-Za-z][\w.:-]*)\((.*?)\)?\s*$')
ERGEBNIS_RE = re.compile(r'^\s*⎿\s?(.*)$')
EINGABE_RE = re.compile(r'^\s*[❯>]\s(.+)$')
SPINNER_RE = re.compile(r'^\s*[✻✶✳✢✽·*]\s+\S.*(…|\.\.\.|esc to interrupt|done\b|for \d+s)', re.I)
LAEUFT_RE = re.compile(r'esc to interrupt', re.I)
STATUS_RE = re.compile(r'bypass permissions|shift\+tab|manual mode|auto-accept|\? for shortcuts|⏸|⏵⏵|/gsd:|░|█|'
                       r'│\s*(Opus|Sonnet|Haiku|Fable)\b|^\s*\(ctrl\+', re.I)
EINGERUECKT_RE = re.compile(r'^\s{2,}\S')
LEER_PROMPT_RE = re.compile(r'^\s*[❯>]\s*$')

AKTIV_WERKZEUG = {
    'Read': ('liest', 'liest'), 'Write': ('schreibt', 'schreibt'), 'Edit': ('schreibt', 'ändert'), 'MultiEdit': ('schreibt', 'ändert'),
    'NotebookEdit': ('schreibt', 'ändert'), 'Update': ('schreibt', 'ändert'), 'Create': ('schreibt', 'legt an'),
    'Grep': ('sucht', 'sucht'), 'Glob': ('sucht', 'sucht Dateien'), 'Search': ('sucht', 'sucht'), 'LS': ('liest', 'schaut in'),
    'WebFetch': ('recherchiert', 'liest Webseite'), 'WebSearch': ('recherchiert', 'sucht im Web'),
    'Skill': ('lernt', 'lädt Skill'), 'TodoWrite': ('plant', 'plant die Schritte'), 'Task': ('delegiert', 'gibt Arbeit ab'),
    'Agent': ('delegiert', 'gibt Arbeit ab'), 'AskUserQuestion': ('fragt', 'fragt dich'),
}
# Befehle im Terminal → Tätigkeit (erste passende Zeile gewinnt)
BEFEHL = [
    (re.compile(r'hyperframes|render\.sh|render\.py|blender|remotion|\bms render\b|snap\.sh', re.I), 'rendert', 'rendert'),
    (re.compile(r'gen_voice|stimme|tts|higgsfield.*audio|elevenlabs', re.I), 'stimme', 'spricht ein'),
    (re.compile(r'\bmix(\.py)?\b|loudnorm|lufs|sfx', re.I), 'ton', 'mischt den Ton'),
    (re.compile(r'whisper|transkri', re.I), 'hoert', 'hört nach'),
    (re.compile(r'ffmpeg|ffprobe|qa_sheets|qa_overlay|blackscan', re.I), 'rendert', 'prüft das Video'),
    (re.compile(r'\b(curl|wget)\b', re.I), 'recherchiert', 'holt Daten'),
    (re.compile(r'\bgit\b|\bwrangler\b|\bdeploy', re.I), 'werkzeug', 'veröffentlicht'),
]


def _rein(z: str) -> str:
    return z.rstrip().rstrip('│|').rstrip()


def _stumm(z: str) -> bool:
    s = z.strip()
    return not s or TRENN_RE.match(z) is not None or STATUS_RE.search(z) is not None


def frage(zeilen: list[str]) -> dict | None:
    """Offenes Auswahl-Menü unten auf dem Bildschirm, sonst None (Freitext-Fragen liefert nachricht())."""
    z = [_rein(x) for x in zeilen]
    fuss = None
    for i in range(len(z) - 1, max(-1, len(z) - 12), -1):
        if FUSS_AUSWAHL_RE.search(z[i]) or FUSS_FREIGABE_RE.search(z[i]):
            fuss = i
            break
    if fuss is None:
        return None
    # Optionen nach oben einsammeln (Erklärzeilen hängen an der Option davor)
    optionen, start, i = [], None, fuss - 1
    block = []
    while i >= 0 and fuss - i < 60:
        m = OPTION_RE.match(z[i])
        if m:
            block.append((i, m))
            start = i
        elif block and (KOPF_RE.match(z[i]) or FREIGABE_RE.search(z[i]) or (z[i].strip() and not EINGERUECKT_RE.match(z[i]) and not TRENN_RE.match(z[i]))):
            break
        i -= 1
    if not block:
        return None
    block.reverse()
    cursor = None
    for n, (idx, m) in enumerate(block):
        ende = block[n + 1][0] if n + 1 < len(block) else fuss
        info = [x.strip() for x in z[idx + 1:ende] if x.strip() and not TRENN_RE.match(x) and not OPTION_RE.match(x)]
        label = m.group(3)
        if m.group(1):
            cursor = int(m.group(2))
        optionen.append({'nr': int(m.group(2)), 'label': label, 'info': ' '.join(info)[:300]})
    freigabe = bool(FUSS_FREIGABE_RE.search(z[fuss])) and not FUSS_AUSWAHL_RE.search(z[fuss])
    # Frage und Kopf über den Optionen
    titel, text, details = '', [], []
    j = start - 1
    while j >= 0 and start - j < 40:
        s = z[j].strip()
        if KOPF_RE.match(z[j]):
            titel = KOPF_RE.match(z[j]).group(1)
            break
        if EINGABE_RE.match(z[j]) or (BLASE_RE.match(z[j]) and not freigabe):
            break
        if s and not TRENN_RE.match(z[j]) and not STATUS_RE.search(z[j]):
            text.insert(0, s)
        elif freigabe and TRENN_RE.match(z[j]) and text:
            # Freigabe: darüber steht der Werkzeug-Kasten (Art, Beschreibung ╌ Befehl ╌), oben begrenzt von einer ─-Linie
            k = j - 1
            while k >= 0 and j - k < 14:
                if '─' in z[k] and TRENN_RE.match(z[k]) or ERGEBNIS_RE.match(z[k]) or BLASE_RE.match(z[k]):
                    break
                if z[k].strip() and not TRENN_RE.match(z[k]):
                    details.insert(0, z[k].strip())
                k -= 1
            j = k
            break
        j -= 1
    beginn = max(0, j) if titel or freigabe else max(0, j + 1)
    frage_text = ' '.join(text) if freigabe else '\n'.join(text)
    frei = next((o['nr'] for o in optionen if FREI_RE.match(o['label'])), None)
    for o in optionen:
        o['frei'] = o['nr'] == frei
        o['chat'] = bool(CHAT_RE.match(o['label']))
    return {'art': 'freigabe' if freigabe else 'auswahl', 'titel': titel, 'text': frage_text.strip(), 'details': details[:6],
            'optionen': optionen, 'frei_nr': frei, 'enter': not freigabe, 'cursor': cursor, 'beginn': beginn}


def nachricht(zeilen: list[str]) -> str:
    """Letzte Textnachricht des Agenten (ohne Werkzeuge), z. B. eine Rückfrage im Klartext."""
    z = [_rein(x) for x in zeilen]
    for i in range(len(z) - 1, -1, -1):
        m = BLASE_RE.match(z[i])
        if not m or WERKZEUG_RE.match(z[i]):
            continue
        teile = [m.group(1).strip()]
        for x in z[i + 1:]:
            if not EINGERUECKT_RE.match(x) or ERGEBNIS_RE.match(x) or SPINNER_RE.match(x) or STATUS_RE.search(x):
                break
            teile.append(x.strip())
        return '\n'.join(t for t in teile if t)
    return ''


def taetigkeit(zeilen: list[str], zustand: str = 'arbeitet') -> dict:
    """{art, text, werkzeug, agent}. art: denkt | liest | schreibt | sucht | recherchiert | rendert | stimme | ton | hoert |
    lernt | plant | delegiert | werkzeug | fragt | wartet | fehler | beendet."""
    if zustand == 'beendet':
        return {'art': 'beendet', 'text': 'Sitzung beendet'}
    if zustand == 'fehler':
        return {'art': 'fehler', 'text': 'steht wegen eines Fehlers'}
    f = frage(zeilen)
    if f:
        return {'art': 'fragt', 'text': 'wartet auf deine Freigabe' if f['art'] == 'freigabe' else 'fragt dich etwas'}
    z = [_rein(x) for x in zeilen]
    w_idx, w = -1, None
    t_idx = -1
    for i in range(len(z) - 1, -1, -1):
        m = WERKZEUG_RE.match(z[i])
        if m and w is None:
            w_idx, w = i, m
        elif BLASE_RE.match(z[i]) and not m and t_idx < 0:
            t_idx = i
        if w is not None and t_idx >= 0:
            break
    if zustand == 'wartet':
        n = nachricht(zeilen)
        return {'art': 'fragt' if n.rstrip().endswith('?') else 'wartet',
                'text': 'fragt dich etwas' if n.rstrip().endswith('?') else 'wartet auf den nächsten Auftrag'}
    if w is None or t_idx > w_idx:
        return {'art': 'denkt', 'text': 'denkt nach'}
    name, arg = w.group(1), w.group(2).strip()
    kurz = re.sub(r'\s+', ' ', arg)[:70]
    if name in ('Bash', 'Shell', 'PowerShell'):
        for rx, art, text in BEFEHL:
            if rx.search(arg):
                return {'art': art, 'text': text, 'werkzeug': kurz}
        return {'art': 'werkzeug', 'text': 'führt einen Befehl aus', 'werkzeug': kurz}
    if name in AKTIV_WERKZEUG:
        art, text = AKTIV_WERKZEUG[name]
        datei = re.split(r'[/\\]', arg.split(',')[0].strip('"\' '))[-1][:48] if art in ('liest', 'schreibt') else ''
        return {'art': art, 'text': f'{text} {datei}'.strip(), 'werkzeug': kurz}
    if '-' in name or name.islower():          # Subagent erscheint mit seinem Namen, z. B. reel-pruefer(…)
        return {'art': 'delegiert', 'text': f'{name} arbeitet', 'agent': name, 'werkzeug': kurz}
    if name.startswith('mcp__'):
        return {'art': 'recherchiert', 'text': 'nutzt ein Zusatzwerkzeug', 'werkzeug': name.split('__')[-1]}
    return {'art': 'werkzeug', 'text': f'nutzt {name}', 'werkzeug': kurz}


def gespraech(zeilen: list[str], max_bloecke: int = 80) -> list[dict]:
    """Bildschirm → [{wer: du|agent|werkzeug|info, text, werkzeug?, ergebnis?}]. Menüs und Statuszeilen fallen weg."""
    z = [_rein(x) for x in zeilen]
    f = frage(z)
    if f:   # das offene Menü zeigt die Seite eigens, nicht im Verlauf
        z = z[:f['beginn']]
    aus: list[dict] = []
    akt = None
    for x in z:
        if not x.strip() or TRENN_RE.match(x) or STATUS_RE.search(x) or LEER_PROMPT_RE.match(x):
            akt = None if akt and akt['wer'] == 'du' else akt
            continue
        if SPINNER_RE.match(x):
            akt = None
            continue
        m = WERKZEUG_RE.match(x)
        if m:
            akt = {'wer': 'werkzeug', 'werkzeug': m.group(1), 'text': m.group(2).strip()[:400], 'ergebnis': []}
            aus.append(akt)
            continue
        m = BLASE_RE.match(x)
        if m:
            akt = {'wer': 'agent', 'text': m.group(1).strip()}
            aus.append(akt)
            continue
        m = ERGEBNIS_RE.match(x)
        if m and akt and akt['wer'] == 'werkzeug':
            akt['ergebnis'].append(m.group(1).strip())
            continue
        m = EINGABE_RE.match(x)
        if m and not OPTION_RE.match(x):
            akt = {'wer': 'du', 'text': m.group(1).strip()}
            aus.append(akt)
            continue
        if akt and EINGERUECKT_RE.match(x):
            if akt['wer'] == 'werkzeug':
                if len(akt['ergebnis']) < 12:
                    akt['ergebnis'].append(x.strip())
            else:
                akt['text'] += '\n' + x.strip()
            continue
        if x.strip() and not akt:
            aus.append({'wer': 'info', 'text': x.strip()})
    for b in aus:
        if b['wer'] == 'werkzeug':
            b['ergebnis'] = '\n'.join(b['ergebnis'][:12])
        b['text'] = b['text'][:4000]
    return [b for b in aus if b['text'] or b.get('ergebnis')][-max_bloecke:]


# ---------------------------------------------------------------- Beispiele (echte Bildschirme, gekürzt)

BEISPIEL_AUSWAHL = """\
❯ Nutze jetzt sofort das AskUserQuestion-Werkzeug und frag mich: Welche Farbe soll der Hook haben?
  auffällig), Blau (ruhig), Grün (frisch). Danach warte.
────────────────────────────────────────────────────────────────────────────────────
 ☐ Hook-Farbe

Welche Farbe soll der Hook haben?

❯ 1. Rot
     Warm, auffällig — zieht sofort die Aufmerksamkeit
  2. Blau
     Ruhig, vertrauenswürdig — wirkt seriös und stabil
  3. Grün
     Frisch, positiv — signalisiert Wachstum und Optimismus
  4. Type something.
────────────────────────────────────────────────────────────────────────────────────
  5. Chat about this

Enter to select · ↑/↓ to navigate · Esc to cancel"""

BEISPIEL_FREIGABE = """\
❯ Führ jetzt mit dem Bash-Werkzeug aus: touch probe.txt && echo ok
⏺ Bash(touch probe.txt && echo ok)
  ⎿  Waiting…
────────────────────────────────────────────────────────────────────────────────────
 Bash command
 Create probe.txt file and echo confirmation
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 touch probe.txt && echo ok
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 Do you want to proceed?
 ❯ 1. Yes
   2. Yes, and always allow access to /private/tmp/fragetest from this project
   3. No
 Esc to cancel · Tab to amend"""

BEISPIEL_TEXT = """\
❯ Stell mir jetzt eine Rückfrage als normalen Text (kein Werkzeug): ob du die Szene 3 neu rendern sollst
  Begründung davor. Dann warte.
⏺ Szene 3 hatte in der letzten Prüfung einen Timing-Versatz von ca. 200 ms — das fällt bei 45 s Gesamtlänge stärker auf.
  Wenn wir den Hook-Schnitt jetzt verschärfen, passen die Cuts nicht mehr exakt zu den Szenenwechseln.
  Sollen wir Szene 3 neu rendern, um die neuen Timing-Vorgaben zu erfüllen?
✻ Worked for 3s · done 10:11 PM
────────────────────────────────────────────────────────────────────────────────────
❯
────────────────────────────────────────────────────────────────────────────────────
  ⬆ /gsd:update │ Haiku 4.5 │ fragetest ███░░░░░░░ 35%
  ⏸ manual mode on · ← 5 agents"""

BEISPIEL_ARBEIT = """\
⏺ Ich baue jetzt Szene 4.
⏺ Bash(cd episodes/2026-10-22-kontext && npx hyperframes render s04 --quality high)
  ⎿  Running…
✶ Rendering… (2m 10s · ↓ 4.1k tokens · esc to interrupt)"""


def _test() -> int:
    a = frage(BEISPIEL_AUSWAHL.splitlines())
    assert a and a['art'] == 'auswahl' and a['titel'] == 'Hook-Farbe', a
    assert a['text'] == 'Welche Farbe soll der Hook haben?', a['text']
    assert [o['nr'] for o in a['optionen']] == [1, 2, 3, 4, 5], a['optionen']
    assert a['optionen'][0]['label'] == 'Rot' and 'Warm' in a['optionen'][0]['info']
    assert a['frei_nr'] == 4 and a['enter'] is True and a['cursor'] == 1 and a['optionen'][4]['chat']
    f = frage(BEISPIEL_FREIGABE.splitlines())
    assert f and f['art'] == 'freigabe' and f['enter'] is False, f
    assert f['text'] == 'Do you want to proceed?', f['text']
    assert [o['label'] for o in f['optionen']][0] == 'Yes' and len(f['optionen']) == 3
    assert any('touch probe.txt' in d for d in f['details']) and any('Bash command' in d for d in f['details']), f['details']
    assert frage(BEISPIEL_TEXT.splitlines()) is None
    n = nachricht(BEISPIEL_TEXT.splitlines())
    assert n.startswith('Szene 3') and n.endswith('erfüllen?'), n
    t = taetigkeit(BEISPIEL_TEXT.splitlines(), 'wartet')
    assert t['art'] == 'fragt', t
    t = taetigkeit(BEISPIEL_ARBEIT.splitlines(), 'arbeitet')
    assert t['art'] == 'rendert' and 'hyperframes' in t['werkzeug'], t
    assert taetigkeit(BEISPIEL_AUSWAHL.splitlines(), 'wartet')['art'] == 'fragt'
    g = gespraech(BEISPIEL_ARBEIT.splitlines())
    assert [b['wer'] for b in g] == ['agent', 'werkzeug'] and g[1]['ergebnis'] == 'Running…', g
    g = gespraech(BEISPIEL_TEXT.splitlines())
    assert [b['wer'] for b in g] == ['du', 'agent'] and 'Begründung' in g[0]['text'], g
    g = gespraech(BEISPIEL_AUSWAHL.splitlines())
    assert all('Rot' not in b['text'] for b in g), g
    print('terminal_lesen: alle Beispiele ok')
    return 0


if __name__ == '__main__':
    sys.exit(_test() if '--test' in sys.argv else print(__doc__) or 0)
