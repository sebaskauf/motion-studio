"""Einstellungen von Tagesbau, Modellen und Posten (<Arbeitsordner>/autopilot.json) und die Startoptionen jeder Sitzung.
Gemeinsam für ms autopilot, ms starten, ms modelle und das Studio.

Modelle (Sebastian 30.10.2026): Pro und Max laufen wie bei Sebastian überwiegend auf Sonnet, geplant wird mit Opus.
  modell_regie    Regie in Sitzungen, die das Studio startet: "opusplan" = Opus nur im Plan-Modus, sonst Sonnet
                  (geprüft im Binary von Claude Code 2.1.289: Anzeige „Opus Plan Mode: Use Opus in plan mode, Sonnet otherwise“)
  modell_planung  Tagesbau Stufe A (Idee, Skript, Stimme, Storyboard): Opus. Eine eigene Sitzung, weil opusplan ohne Plan-Modus
                  (unbeaufsichtigt) nur Sonnet wäre.
  modell (Bau)    Tagesbau Stufe B (Szenen, Ton, Render, Prüfung) und das Posten: Sonnet
  modell_helfer   Bauer, Prüfer, Analyse: Sonnet (steht als model: im Agenten, die Regie gibt es beim Agent-Tool mit)
Sonnet spart keine Token: gemessen am 22.10.2026 braucht es je Videosekunde rund 20 % MEHR Token als Opus. Ob es weniger aufs
Wochenlimit zählt, ist nicht gemessen (/usage vorher und nachher). Sonnet ist Standard, weil die Qualität in Sebastians
Testbauten gleich war und Opus für die Planung bleibt.
MCP: Bau-Sitzungen laden nur die MCP-Server, die sie brauchen (--strict-mcp-config). "mcp_stimme" = ["voicestudio"], wenn die
Stimme über Voice Studio entsteht, "alle", wenn sie einen Connector braucht (z. B. Higgsfield), sonst []. Posten bekommt nur
Claude in Chrome (--chrome)."""
from __future__ import annotations

import json
from pathlib import Path

import _ms

STANDARD = {
    'an': False, 'kanal': '', 'abo': '', 'pro_tag': 1, 'parallel': 1, 'fenster': ['08:00', '22:00'], 'puffer': 5,
    'modell': 'sonnet', 'modell_planung': 'opus', 'modell_regie': 'opusplan', 'modell_helfer': 'sonnet',
    'staffel': True, 'denkstufe': 'high', 'ohne_gedaechtnis': True, 'max_stunden': 6,
    'wochen_bremse': 60, 'limit_m_pro_prozent': None, 'woche_reset': '', 'sonnet_faktor': None,
    'mcp_stimme': [], 'posten': False, 'post_zeit': '18:00', 'posts_pro_tag': 1,
}
# Vorschlag je Abo. Grundlage: TOKEN-ABGLEICH 30.10.2026 (eigene Folge geschätzt 20 bis 40 M gewichtete Token; Woche Max 20x
# gemessen 920 bis 1.040 M, Max 5x und Pro abgeleitet). Die Wochenbremse hält den Tagesbau an, bevor das Limit erreicht ist.
ABO = {
    'pro': {'pro_tag': 1, 'parallel': 1, 'wochen_bremse': 60,
            'text': 'Pro: realistisch 1 bis 2 eigene Folgen pro Woche, wenn du Claude sonst wenig nutzt. Der Tagesbau steht auf 1 am Tag, '
                    'die Wochenbremse hält ihn bei 60 % deines Wochenlimits an. Kanal lernen allein braucht schon 70 bis 150 % einer Pro-Woche.'},
    'max5': {'pro_tag': 1, 'parallel': 1, 'wochen_bremse': 60,
             'text': 'Max 5x: 1 Folge am Tag ist machbar (geschätzt 6 bis 12 pro Woche). Nach einer Woche ohne Bremse geht auch 2 am Tag.'},
    'max20': {'pro_tag': 3, 'parallel': 2, 'wochen_bremse': 70,
              'text': 'Max 20x: 3 Folgen am Tag als Start (möglich bis 5), höchstens 2 gleichzeitig, Bremse bei 70 % der Woche.'},
}
MODELLE = {'sonnet': 'sonnet', 'opus': 'opus', 'opusplan': 'opusplan', 'fable': 'fable',
           'claude-sonnet-5-5': 'sonnet', 'claude-opus-5-5': 'opus', 'claude-fable-5-1': 'fable'}
ANZEIGE = {'sonnet': 'Sonnet', 'opus': 'Opus', 'opusplan': 'Opus-Plan (Opus plant, Sonnet arbeitet)', 'fable': 'Fable'}
HELFER = ('sonnet', 'opus', 'haiku', 'fable', 'inherit')
# Welche Aufträge eine schlanke Sitzung bekommen (nur nötige MCP-Server). Beim Einrichten bleiben alle MCPs da (Voice Studio prüfen).
SCHLANK = ('autobau', 'autobau-b', 'folge', 'weiter', 'pruefen', 'kanal-lernen', 'vorlagen', 'posten', 'posten-einrichten')
STIMME_AUFTRAEGE = ('autobau', 'folge', 'weiter')   # hier kann die Stimme entstehen


def datei() -> Path:
    return _ms.arbeit() / 'autopilot.json'


def konfig() -> dict:
    d = _ms.json_lesen(datei(), {}) or {}
    cfg = {**STANDARD, **{k: v for k, v in d.items() if k in STANDARD}}
    for k in ('modell', 'modell_planung', 'modell_regie'):
        cfg[k] = MODELLE.get(str(cfg[k]), str(cfg[k]))
    return cfg


def konfig_schreiben(cfg: dict) -> None:
    _ms.json_schreiben(datei(), {k: cfg[k] for k in STANDARD})


def abo_setzen(cfg: dict, abo: str) -> dict:
    if abo not in ABO:
        raise SystemExit(f'FEHLER: Abo "{abo}" unbekannt. Erlaubt: pro, max5, max20.')
    cfg['abo'] = abo
    for k in ('pro_tag', 'parallel', 'wochen_bremse'):
        cfg[k] = ABO[abo][k]
    return cfg


def anzeige(modell: str) -> str:
    return ANZEIGE.get(MODELLE.get(str(modell), str(modell)), str(modell))


# ---------------------------------------------------------------- MCP-Server für schlanke Sitzungen

def _claude_jsons() -> list[Path]:
    import _setup
    kand = [_setup.claude_ordner() / '.claude.json', Path.home() / '.claude.json']
    return [p for i, p in enumerate(kand) if p.is_file() and p not in kand[:i]]


def mcp_server(namen: list[str]) -> tuple[dict, list[str]]:
    """Definitionen der genannten MCP-Server aus der Claude-Konfiguration (Nutzer, Projekt Arbeitsordner, .mcp.json).
    Server mit Zugangsdaten in der Definition (env, headers) werden nicht übernommen: Sie würden sonst im Startbefehl stehen.
    Rückgabe (mcpServers, fehlend)."""
    gefunden, fehlend = {}, []
    quellen = []
    arbeit = str(_ms.arbeit())
    for p in _claude_jsons():
        try:
            d = json.loads(p.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        quellen.append(d.get('mcpServers') or {})
        quellen.append(((d.get('projects') or {}).get(arbeit) or {}).get('mcpServers') or {})
    projekt = _ms.json_lesen(_ms.arbeit() / '.mcp.json', {}) or {}
    quellen.append(projekt.get('mcpServers') or {})
    for n in namen:
        e = next((q[n] for q in quellen if isinstance(q.get(n), dict)), None)
        if e is None and n == 'voicestudio':   # Pack 3 Prompt 3: claude mcp add --transport http voicestudio http://localhost:3900/mcp/
            e = {'type': 'http', 'url': 'http://localhost:3900/mcp/'}
        if e is None or e.get('env') or e.get('headers'):
            fehlend.append(n)
            continue
        gefunden[n] = e
    return gefunden, fehlend


def sitzung_optionen(art: str, cfg: dict | None = None) -> dict:
    """Startoptionen für claude (starten.claude_befehl) je Auftrag: Modell, Denkstufe, Gedächtnis, MCP, Chrome."""
    cfg = cfg or konfig()
    o = {'ohne_gedaechtnis': True, 'mcp': None, 'chrome': False}
    if art == 'autobau':
        o.update(modell=cfg['modell_planung'] if cfg['staffel'] else cfg['modell'], denkstufe=cfg['denkstufe'], bypass=True)
    elif art in ('autobau-b', 'posten'):
        o.update(modell=cfg['modell'], denkstufe=cfg['denkstufe'], bypass=True)
    else:
        o.update(modell=cfg['modell_regie'])
    if art in SCHLANK:
        stimme = cfg.get('mcp_stimme')
        if art in STIMME_AUFTRAEGE and stimme == 'alle':
            o['mcp'] = None
        else:
            namen = list(stimme) if (art in STIMME_AUFTRAEGE and isinstance(stimme, list)) else []
            o['mcp'] = namen
    if art in ('posten', 'posten-einrichten'):
        o['chrome'] = True
    return o
