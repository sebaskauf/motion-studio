"""Token-Verbrauch aus den Sitzungsprotokollen von Claude Code (nur lesen, nichts wird verändert).

Grundlage: Jede Claude-Code-Sitzung schreibt <Claude-Ordner>/projects/<Ordnername>/<sitzung>.jsonl, Subagenten (Bauer, Prüfer,
Analyse) liegen in <sitzung>/subagents/agent-*.jsonl mit agent-*.meta.json (customAgentType, model).
Gewichtung wie im reel-studio gemessen (Eichung 18. bis 22.10.2026): input + 1,25 × Cache-Schreiben + 0,1 × Cache-Lesen
+ 5 × Output. Das bildet ab, wie stark ein Schritt aufs Nutzungslimit drückt, nicht den Dollarpreis.

  gewicht(usage) -> float                       gewichtete Token eines API-Schritts
  sitzung_summen(datei) -> dict                 Summe je Modell-Familie für eine .jsonl (Streaming-Doppel nur einmal)
  woche_start(cfg) -> datetime                  letzter Reset des Wochenlimits (cfg "woche_reset" wie "do 02:00", sonst 7 Tage zurück)
  wochen_anteil(cfg, cache) -> dict             geschätzter Anteil am Wochenlimit in %, mit Cache (Scan dauert Sekunden)
  folge_verbrauch(folge_id) -> dict             Verbrauch aller Sitzungen, in denen die Folge vorkommt, je Rolle
Schätzung: Das Wochenlimit je Abo ist nicht veröffentlicht. Max 20x ist gemessen (rund 920 bis 1.040 M gewichtet je Woche),
Max 5x und Pro sind daraus abgeleitet (ein Viertel bzw. ein Zwanzigstel). `ms verbrauch --eichen <prozent>` setzt den Wert
mit einem Ablesepunkt aus /usage genauer."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import _ms

# Millionen gewichtete Token je Prozent Wochenlimit (Opus-Gewichtung). max20 gemessen, max5 und pro angenommen.
ABO_LIMIT_M = {'pro': 0.5, 'max5': 2.4, 'max20': 9.8}
WOCHENTAGE = {'mo': 0, 'di': 1, 'mi': 2, 'do': 3, 'fr': 4, 'sa': 5, 'so': 6}
SCAN_ALTER_TAGE = 8


def gewicht(u: dict) -> float:
    return (float(u.get('input_tokens') or 0) + 1.25 * float(u.get('cache_creation_input_tokens') or 0)
            + 0.1 * float(u.get('cache_read_input_tokens') or 0) + 5 * float(u.get('output_tokens') or 0))


def familie(modell: str) -> str:
    m = str(modell or '').lower()
    return 'sonnet' if 'sonnet' in m else 'opus' if 'opus' in m else 'fable' if 'fable' in m else 'andere'


def claude_ordner() -> Path:
    import _setup
    return _setup.claude_ordner()


def projekte() -> Path:
    return claude_ordner() / 'projects'


def projekt_ordner(pfad) -> Path:
    """Ordner, in dem Claude Code die Sitzungen eines Arbeitsordners ablegt (jedes Zeichen außer A-Z a-z 0-9 wird zu -)."""
    return projekte() / re.sub(r'[^A-Za-z0-9]', '-', str(pfad))


def _schritte(datei: Path, ab: str | None = None, bis: str | None = None):
    """(zeit, usage, modell) je API-Antwort. Beim Streaming steht eine Antwort mehrfach im Protokoll: die letzte zählt."""
    gesehen = {}
    try:
        with open(datei, encoding='utf-8', errors='ignore') as f:
            for zeile in f:
                if '"usage"' not in zeile:
                    continue
                try:
                    e = json.loads(zeile)
                except ValueError:
                    continue
                m = e.get('message') or {}
                u, mid = m.get('usage'), m.get('id')
                if e.get('type') != 'assistant' or not u or not mid:
                    continue
                ts = str(e.get('timestamp') or '')
                if (ab and ts < ab) or (bis and ts > bis):
                    continue
                gesehen[mid] = (ts, u, m.get('model') or '')
    except OSError:
        return []
    return sorted(gesehen.values(), key=lambda x: x[0])


def sitzung_summen(datei: Path, ab: str | None = None, bis: str | None = None) -> dict:
    aus = {'opus': 0.0, 'sonnet': 0.0, 'fable': 0.0, 'andere': 0.0, 'schritte': 0, 'bilder': 0}
    for _, u, modell in _schritte(Path(datei), ab, bis):
        aus[familie(modell)] += gewicht(u)
        aus['schritte'] += 1
    aus['gesamt'] = aus['opus'] + aus['sonnet'] + aus['fable'] + aus['andere']
    return aus


def _utc_iso(t: datetime) -> str:
    """Zeitstempel im Format der Protokolle (UTC), damit der Vergleich als Text stimmt."""
    return t.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M')


def woche_start(cfg: dict | None = None, jetzt: datetime | None = None) -> datetime:
    """Letzter Reset des Wochenlimits. cfg["woche_reset"] = "do 02:00" (aus /usage: „Resets Oct 29 at 2am“ war ein Donnerstag),
    sonst gleitend 7 Tage zurück (vorsichtig: zählt eher zu viel als zu wenig)."""
    jetzt = (jetzt or datetime.now()).astimezone()
    roh = str((cfg or {}).get('woche_reset') or '').strip().lower()
    m = re.match(r'^(mo|di|mi|do|fr|sa|so)\w*\s+(\d{1,2}):(\d\d)$', roh)
    if not m:
        return jetzt - timedelta(days=7)
    tag, h, mi = WOCHENTAGE[m.group(1)], int(m.group(2)), int(m.group(3))
    r = (jetzt - timedelta(days=(jetzt.weekday() - tag) % 7)).replace(hour=h, minute=mi, second=0, microsecond=0)
    if r > jetzt:
        r -= timedelta(days=7)
    return r


def limit_m_pro_prozent(cfg: dict) -> float | None:
    if cfg.get('limit_m_pro_prozent'):
        try:
            return float(cfg['limit_m_pro_prozent'])
        except (TypeError, ValueError):
            pass
    return ABO_LIMIT_M.get(str(cfg.get('abo') or ''))


def wochen_summen(ab: datetime) -> dict:
    """Gewichtete Token aller Claude-Code-Sitzungen seit `ab` (alle Projekte, also auch die eigene Arbeit des Nutzers:
    das Limit gilt fürs ganze Konto)."""
    ab_iso = _utc_iso(ab)
    tot = {'opus': 0.0, 'sonnet': 0.0, 'fable': 0.0, 'andere': 0.0}
    basis = projekte()
    if not basis.is_dir():
        return {**tot, 'gesamt': 0.0, 'dateien': 0}
    grenze = time.time() - SCAN_ALTER_TAGE * 86400
    n = 0
    for f in basis.glob('**/*.jsonl'):
        try:
            if f.stat().st_mtime < grenze:
                continue
        except OSError:
            continue
        n += 1
        s = sitzung_summen(f, ab=ab_iso)
        for k in tot:
            tot[k] += s[k]
    return {**tot, 'gesamt': sum(tot.values()), 'dateien': n}


def wochen_anteil(cfg: dict, cache: dict | None = None, max_alter_min: int = 30) -> dict:
    """{'prozent', 'gewichtet_M', 'ab', 'zeit', 'geeicht'} oder {'prozent': None, 'grund'} ohne Abo/Eichung.
    `cache` ist ein dict (z. B. aus dem Autopilot-Zustand), das Ergebnis wird darin unter "woche" gemerkt."""
    if cache is not None:
        w = cache.get('woche') or {}
        if w.get('zeit') and time.time() - float(w['zeit']) < max_alter_min * 60 and w.get('abo') == cfg.get('abo'):
            return w
    proz_m = limit_m_pro_prozent(cfg)
    ab = woche_start(cfg)
    s = wochen_summen(ab)
    sonnet_faktor = float(cfg.get('sonnet_faktor') or 1.0)   # unbekannt, bis eine Eichung mit Sonnet-Anteil vorliegt
    gewichtet = s['opus'] + s['fable'] + s['andere'] + sonnet_faktor * s['sonnet']
    erg = {'zeit': time.time(), 'ab': ab.isoformat(timespec='minutes'), 'gewichtet_M': round(gewichtet / 1e6, 1),
           'sonnet_M': round(s['sonnet'] / 1e6, 1), 'abo': cfg.get('abo'), 'geeicht': bool(cfg.get('limit_m_pro_prozent')),
           'prozent': round(gewichtet / 1e6 / proz_m, 1) if proz_m else None}
    if not proz_m:
        erg['grund'] = 'Abo nicht eingestellt (ms autopilot abo pro|max5|max20)'
    if cache is not None:
        cache['woche'] = erg
    return erg


# ---------------------------------------------------------------- Verbrauch einer Folge

def _rolle(meta: dict, name: str) -> str:
    t = str(meta.get('customAgentType') or meta.get('agentType') or name)
    for r in ('bauer', 'pruefer', 'analyse', 'regie'):
        if r in t:
            return r
    return 'helfer'


def folge_verbrauch(folge_id: str, ordner: Path | None = None) -> dict:
    """Alle Sitzungen im Arbeitsordner, die hauptsächlich an dieser Folge gearbeitet haben (Regie und ihre Subagenten):
    Eine Sitzung gehört der Folge, deren ID in ihrem Protokoll am häufigsten vorkommt. Andere Folgen derselben Sitzung
    stehen unter "geteilt" (z. B. Pilot und Kopie in einem Nachbau-Lauf)."""
    ordner = ordner or projekt_ordner(_ms.arbeit())
    aus = {'folge': folge_id, 'ordner': str(ordner), 'sitzungen': [], 'rollen': {}, 'gesamt_M': 0.0, 'modelle': {}}
    if not ordner.is_dir():
        aus['grund'] = f'Keine Sitzungsprotokolle in {ordner}'
        return aus
    for haupt in sorted(ordner.glob('*.jsonl')):
        try:
            text = haupt.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        if folge_id not in text:
            continue
        zaehler: dict = {}
        for x in re.findall(r'(\d{4}-\d\d-\d\d-[A-Za-z0-9_-]*[A-Za-z0-9])', text):
            zaehler[x] = zaehler.get(x, 0) + 1
        haupt_id = max(zaehler, key=lambda k: zaehler[k]) if zaehler else folge_id
        if haupt_id != folge_id and zaehler.get(folge_id, 0) < zaehler.get(haupt_id, 0):
            continue
        folgen_ids = {k for k, n in zaehler.items() if n >= 3}
        teile = [('regie', haupt, {})]
        sub = haupt.with_suffix('') / 'subagents'
        for f in sorted(sub.glob('*.jsonl')) if sub.is_dir() else []:
            meta = _ms.json_lesen(f.with_suffix('.meta.json'), {}) or {}
            teile.append((_rolle(meta, f.stem), f, meta))
        summe = 0.0
        for rolle, f, meta in teile:
            s = sitzung_summen(f)
            summe += s['gesamt']
            aus['rollen'][rolle] = aus['rollen'].get(rolle, 0.0) + s['gesamt'] / 1e6
            for fam in ('opus', 'sonnet', 'fable', 'andere'):
                if s[fam]:
                    aus['modelle'][fam] = aus['modelle'].get(fam, 0.0) + s[fam] / 1e6
        aus['sitzungen'].append({'datei': haupt.name, 'gewichtet_M': round(summe / 1e6, 2),
                                 'geteilt': sorted(x for x in folgen_ids if x != folge_id)[:5]})
        aus['gesamt_M'] += summe / 1e6
    aus['gesamt_M'] = round(aus['gesamt_M'], 2)
    aus['rollen'] = {k: round(v, 2) for k, v in aus['rollen'].items()}
    aus['modelle'] = {k: round(v, 2) for k, v in aus['modelle'].items()}
    return aus
