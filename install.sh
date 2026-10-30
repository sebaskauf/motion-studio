#!/usr/bin/env bash
# Installiert Motion-Studio (4 Agenten, Skills, Werkzeuge) für Claude Code.
#
#   ./install.sh                    installieren oder aktualisieren
#   ./install.sh --arbeit <pfad>    Arbeitsordner festlegen (Standard: der bisherige, sonst ~/MotionStudio)
#   ./install.sh --force            fremde Dateien mit gleichem Namen ersetzen (vorher gesichert)
#   ./install.sh --help             diese Hilfe
#
# Wohin (CFG = $CLAUDE_CONFIG_DIR, sonst ~/.claude):
#   agents/motion-*.md   -> CFG/agents/
#   skills/motion-*/     -> CFG/skills/
#   studio/              -> CFG/motion-studio/  (HEIM; config.json, .venv/ und modelle/ bleiben bei Updates stehen)
#   Arbeitsordner        PROFIL.md, LERNLOG.md, .env, .claude/settings.json werden nur angelegt, wenn sie fehlen
# Exit 0 = fertig, 1 = Fehler, 2 = Namenskollision mit fremden Dateien (dann wurde nichts verändert).
# Läuft mit bash 3.2 (macOS) und Git Bash (Windows).
set -euo pipefail

fehler() { echo "FEHLER: $*" >&2; exit 1; }

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CFG="${CFG%/}"
case "$CFG" in /*|[A-Za-z]:*) ;; *) CFG="$PWD/$CFG" ;; esac
HEIM="$CFG/motion-studio"
ARBEIT=""
FORCE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --arbeit)   ARBEIT="${2:-}"; [ -n "$ARBEIT" ] || fehler "--arbeit braucht einen Pfad."; shift 2 ;;
    --arbeit=*) ARBEIT="${1#--arbeit=}"; shift ;;
    --force)    FORCE=1; shift ;;
    -h|--help)  sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)          fehler "unbekannte Option '$1' (Hilfe: ./install.sh --help)" ;;
  esac
done

[ -d "$REPO/studio/tools" ] || fehler "$REPO/studio/tools fehlt. install.sh im Motion-Studio-Repo ausführen."
[ -f "$REPO/studio/ms" ]    || fehler "$REPO/studio/ms fehlt. Repo unvollständig, neu klonen."

# ---------------------------------------------------------------- System und Pfadformen
WIN=0
case "$(uname -s 2>/dev/null)" in MINGW*|MSYS*|CYGWIN*) WIN=1 ;; esac
# aussen: so sehen Claude Code und Python den Pfad (Windows: C:/Users/…), posix: so sieht ihn bash (/c/Users/…)
aussen() { if [ "$WIN" = 1 ] && command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi; }
posix()  { if [ "$WIN" = 1 ] && command -v cygpath >/dev/null 2>&1; then cygpath -u "$1"; else printf '%s' "$1"; fi; }
sed_esc()  { printf '%s' "$1" | sed -e 's/[\\&#]/\\&/g'; }
json_esc() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }
ZEIT="$(date +%Y%m%d-%H%M%S)"

# Python finden (für config.json; ohne Python klappt die Installation trotzdem)
PY=""
for k in python3 python; do
  if command -v "$k" >/dev/null 2>&1 && "$k" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
    PY="$k"; break
  fi
done

# ---------------------------------------------------------------- Arbeitsordner bestimmen
if [ -z "$ARBEIT" ] && [ -f "$HEIM/config.json" ]; then
  ARBEIT="$(sed -n 's/.*"arbeitsordner"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$HEIM/config.json" | head -1)"
fi
[ -n "$ARBEIT" ] || ARBEIT="$HOME/MotionStudio"
case "$ARBEIT" in "~") ARBEIT="$HOME" ;; "~/"*) ARBEIT="$HOME/${ARBEIT#\~/}" ;; esac
ARBEIT="$(posix "$ARBEIT")"
case "$ARBEIT" in /*) ;; *) ARBEIT="$PWD/$ARBEIT" ;; esac
ARBEIT="${ARBEIT%/}"

# ---------------------------------------------------------------- Was gehört uns?
LISTE="$HEIM/.installiert"   # alle von uns installierten Dateien, relativ zu CFG
unser_datei() {  # $1 = Pfad, $2 = Eintrag relativ zu CFG
  [ -f "$LISTE" ] && grep -Fxq "$2" "$LISTE" && return 0
  grep -qi 'motion-studio' "$1" 2>/dev/null
}

KOLL=""
for f in "$REPO"/agents/*.md; do
  [ -e "$f" ] || continue
  n="$(basename "$f")"; z="$CFG/agents/$n"
  if [ -e "$z" ] && ! unser_datei "$z" "agents/$n"; then KOLL="$KOLL $z"; fi
done
for d in "$REPO"/skills/motion-*/; do
  [ -d "$d" ] || continue
  n="$(basename "$d")"; z="$CFG/skills/$n"
  if [ -e "$z" ] && ! unser_datei "$z/SKILL.md" "skills/$n/SKILL.md"; then KOLL="$KOLL $z"; fi
done
heim_fremd() {  # HEIM gehört uns, wenn ms, config.json, tools/_ms.py da sind oder er leer ist (bis auf Reste eines Abbruchs)
  [ -d "$HEIM" ] || return 0
  { [ -f "$HEIM/ms" ] || [ -f "$HEIM/config.json" ] || [ -f "$HEIM/tools/_ms.py" ]; } && return 1
  [ -z "$(ls -A "$HEIM" 2>/dev/null | grep -v '^\.installiert')" ] && return 1
  return 0
}
if [ -e "$HEIM" ] && heim_fremd; then
  KOLL="$KOLL $HEIM"
fi
[ "$(cd "$REPO/studio" && pwd -P)" != "$( [ -d "$HEIM" ] && cd "$HEIM" && pwd -P)" ] \
  || fehler "Das Repo liegt im Installationsordner $HEIM. Repo woanders hin klonen (z. B. ~/Documents/motion-studio)."

if [ -n "$KOLL" ]; then
  if [ "$FORCE" -eq 0 ]; then
    echo "Unter diesen Namen liegt schon etwas, das nicht von Motion-Studio stammt:"
    for z in $KOLL; do
      echo
      echo "  $z"
      if [ -f "$z" ]; then sed -n '1,5p' "$z" | cut -c1-140 | sed 's/^/    | /'
      elif [ -f "$z/SKILL.md" ]; then sed -n '1,5p' "$z/SKILL.md" | cut -c1-140 | sed 's/^/    | /'
      else echo "    (Ordner)"; fi
    done
    echo
    echo "Das wird NICHT überschrieben. Möglichkeiten:"
    echo "  ./install.sh --force   ersetzen, vorher wird alles nach $CFG/motion-studio-sicherungen/$ZEIT/ verschoben"
    echo "  oder die fremden Dateien selbst umbenennen und install.sh noch einmal starten"
    echo
    echo "Es wurde nichts verändert."
    exit 2
  fi
  SICHER="$CFG/motion-studio-sicherungen/$ZEIT"
  for z in $KOLL; do
    teil="${z#$CFG/}"
    mkdir -p "$SICHER/$(dirname "$teil")"
    mv "$z" "$SICHER/$teil"
    echo "Gesichert: $z -> $SICHER/$teil"
  done
fi

# ---------------------------------------------------------------- Kopieren
mkdir -p "$CFG/agents" "$CFG/skills" "$HEIM" "$ARBEIT"
ARBEIT="$(cd "$ARBEIT" && pwd)"
ohne_leer() {  # Leerzeichen im Pfad zerlegen Befehle in Agenten. Windows: 8.3-Kurzform (C:/Users/MAXMUS~1/…)
  case "$1" in
    *" "*) if [ "$WIN" = 1 ]; then cygpath -m -s "$1" 2>/dev/null || printf '%s' "$1"; else printf '%s' "$1"; fi ;;
    *) printf '%s' "$1" ;;
  esac
}
H_AUSSEN="$(ohne_leer "$(aussen "$HEIM")")"
A_AUSSEN="$(ohne_leer "$(aussen "$ARBEIT")")"
case "$H_AUSSEN$A_AUSSEN" in
  *" "*) echo "WARNUNG: Ein Pfad enthält Leerzeichen ($H_AUSSEN, $A_AUSSEN). Befehle in den Agenten können daran scheitern."
         echo "         Besser: --arbeit mit einem Pfad ohne Leerzeichen, CLAUDE_CONFIG_DIR ebenso." ;;
esac
H_SED="$(sed_esc "$H_AUSSEN")"
A_SED="$(sed_esc "$A_AUSSEN")"

kopiere_baum() {  # $1 Quelle, $2 Ziel: Inhalt kopieren, ohne Caches und Nutzerdaten
  mkdir -p "$2"
  (cd "$1" && tar -cf - --exclude='__pycache__' --exclude='.DS_Store' --exclude='./.venv' --exclude='./modelle' \
     --exclude='./config.json' --exclude='./.installiert' .) | (cd "$2" && tar -xf -)
}
ersetze() {  # Platzhalter in einer Datei ersetzen
  grep -q -e '__HEIM__' -e '__ARBEIT__' "$1" 2>/dev/null || return 0
  sed -e "s#__HEIM__#$H_SED#g" -e "s#__ARBEIT__#$A_SED#g" "$1" > "$1.tmp.$$" && mv "$1.tmp.$$" "$1"
}

NEU="$HEIM/.installiert.neu.$$"
trap 'rm -f "$NEU" 2>/dev/null || true' EXIT
: > "$NEU"
AGENTEN=""
for f in "$REPO"/agents/*.md; do
  [ -e "$f" ] || continue
  n="$(basename "$f")"
  cp "$f" "$CFG/agents/$n"
  ersetze "$CFG/agents/$n"
  echo "agents/$n" >> "$NEU"
  AGENTEN="$AGENTEN ${n%.md}"
done
SKILLS=""
for d in "$REPO"/skills/motion-*/; do
  [ -d "$d" ] || continue
  n="$(basename "$d")"
  kopiere_baum "$d" "$CFG/skills/$n"
  (cd "$d" && find . -type f ! -name '.DS_Store' ! -path '*/__pycache__/*') | sed "s#^\./#skills/$n/#" >> "$NEU"
  SKILLS="$SKILLS $n"
done
kopiere_baum "$REPO/studio" "$HEIM"
(cd "$REPO/studio" && find . -type f ! -name '.DS_Store' ! -path '*/__pycache__/*' ! -path './.venv/*' ! -path './modelle/*' \
   ! -name 'config.json') | sed "s#^\./#motion-studio/#" >> "$NEU"
chmod +x "$HEIM/ms" 2>/dev/null || true

# Platzhalter: Agenten und alle .md der Skills; im HEIM nur __HEIM__ (Vorlagen behalten __ARBEIT__ für später)
while IFS= read -r eintrag; do
  case "$eintrag" in
    agents/*.md|skills/*.md) ersetze "$CFG/$eintrag" ;;   # * passt in case auch über / hinweg
    motion-studio/vorlagen/*) ;;
    motion-studio/*.md)
      f="$CFG/$eintrag"
      if grep -q '__HEIM__' "$f" 2>/dev/null; then sed -e "s#__HEIM__#$H_SED#g" "$f" > "$f.tmp.$$" && mv "$f.tmp.$$" "$f"; fi ;;
  esac
done < "$NEU"

# Dateien, die in einer früheren Version installiert waren und jetzt wegfallen, entfernen (nur unsere eigenen)
if [ -f "$LISTE" ]; then
  grep -Fxv -f "$NEU" "$LISTE" | while IFS= read -r alt; do
    case "$alt" in agents/motion-*|skills/motion-*|motion-studio/*) [ -f "$CFG/$alt" ] && rm -f "$CFG/$alt" && echo "Entfernt (nicht mehr im Paket): $alt" ;; esac
  done || true
fi
mv "$NEU" "$LISTE"

REST="$(for e in $(grep -e '^agents/' -e '^skills/' "$LISTE" | grep '\.md$'); do grep -l -e '__HEIM__' -e '__ARBEIT__' "$CFG/$e" 2>/dev/null || true; done)"
[ -z "$REST" ] || { echo "WARNUNG: Platzhalter nicht ersetzt in:"; echo "$REST" | sed 's/^/  /'; }

# ---------------------------------------------------------------- Arbeitsordner (gehört dem Nutzer)
mkdir -p "$ARBEIT/kanaele" "$ARBEIT/folgen" "$ARBEIT/vorlagen/videos" "$ARBEIT/vorlagen/transkripte" \
         "$ARBEIT/sounds/files" "$ARBEIT/live" "$ARBEIT/.claude"
NEU_ANGELEGT=""
vorlage_kopieren() {  # $1 Vorlage, $2 Ziel
  [ -f "$2" ] && return 0
  sed -e "s#__ARBEIT__#$A_SED#g" -e "s#__HEIM__#$H_SED#g" "$1" > "$2"
  NEU_ANGELEGT="$NEU_ANGELEGT $(basename "$2")"
}
vorlage_kopieren "$REPO/studio/vorlagen/PROFIL-START.md"  "$ARBEIT/PROFIL.md"
vorlage_kopieren "$REPO/studio/vorlagen/LERNLOG-START.md" "$ARBEIT/LERNLOG.md"

if [ ! -f "$ARBEIT/.env" ]; then
  cat > "$ARBEIT/.env" <<'ENVEOF'
# Motion-Studio: Schlüssel für bezahlte oder angemeldete Dienste.
# Nur hier eintragen, nie in andere Dateien. Claude liest diese Datei nicht (gesperrt in .claude/settings.json),
# die Werkzeuge lesen sie selbst. Eintragen: NAME=wert (ohne Leerzeichen um das =).
# Alles ist optional. "ms check" zeigt nur gesetzt/fehlt.
#
# APIFY_TOKEN=            Vorlagen von Instagram/TikTok laden (kostet pro Lauf, immer erst nach Ja)
# ELEVENLABS_API_KEY=     Stimme und Sound-Effekte (kostet je nach Plan)
# FREESOUND_API_KEY=      Sound-Suche auf freesound.org (gratis, Key: freesound.org/apiv2/apply)
# TRIPO_API_KEY=          3D-Figuren aus Text oder Bild (kostet pro Figur)
ENVEOF
  chmod 600 "$ARBEIT/.env" 2>/dev/null || true
  NEU_ANGELEGT="$NEU_ANGELEGT .env"
fi

if [ ! -f "$ARBEIT/.claude/settings.json" ]; then
  HJ="$(json_esc "$H_AUSSEN")"
  # Read/Edit-Regeln brauchen //absoluter/pfad (Windows: //c/Users/…). Skills: alle unter CFG/skills lesbar,
  # weil die Bauer neben motion-* auch die HyperFrames-Skills (hyperframes-core, hyperframes-animation …) lesen.
  AR="/$(json_esc "$(posix "$ARBEIT")")"
  HR="/$(json_esc "$(posix "$HEIM")")"
  CR="/$(json_esc "$(posix "$CFG")")"
  EXTRA=""
  [ "$WIN" = 1 ] && EXTRA="
      \"Bash($(json_esc "$(posix "$HEIM")")/ms *)\","
  cat > "$ARBEIT/.claude/settings.json" <<JSONEOF
{
  "autoMemoryEnabled": false,
  "permissions": {
    "allow": [
      "Bash($HJ/ms *)",$EXTRA
      "Bash(ffmpeg *)",
      "Bash(ffprobe *)",
      "Bash(npx hyperframes *)",
      "Bash(yt-dlp *)",
      "Bash(whisper-cli *)",
      "Bash(tmux *)",
      "Read($AR/**)",
      "Edit($AR/**)",
      "Read($HR/**)",
      "Read($CR/skills/**)"
    ],
    "deny": [
      "Read($AR/.env)",
      "Edit($AR/.env)"
    ]
  }
}
JSONEOF
  NEU_ANGELEGT="$NEU_ANGELEGT .claude/settings.json"
fi

# Token-Diät (30.10.2026): Sitzungen im Arbeitsordner ohne Auto-Gedächtnis, auch Dashboard- und manuelle Starts
# (Claude Code 2.1.289 liest "autoMemoryEnabled" aus den Projekt-Einstellungen). Vorhandene Datei: nur diesen einen Schlüssel
# ergänzen, wenn er fehlt, alles andere bleibt, wie es ist (vorher Sicherung settings.json.vor-v4).
if [ -n "$PY" ] && [ -f "$ARBEIT/.claude/settings.json" ]; then
  MS_S="$ARBEIT/.claude/settings.json" "$PY" - <<'PYEOF' || echo "HINWEIS: autoMemoryEnabled nicht ergänzt (settings.json nicht lesbar), Token-Diät greift dann nur bei Starts aus dem Studio."
import json, os, shutil
p = os.environ['MS_S']
with open(p, encoding='utf-8') as f:
    d = json.load(f)
if 'autoMemoryEnabled' not in d:
    shutil.copyfile(p, p + '.vor-v4')
    d['autoMemoryEnabled'] = False
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print('  .claude/settings.json: autoMemoryEnabled false ergänzt (Sicherung settings.json.vor-v4)')
PYEOF
fi

# ---------------------------------------------------------------- config.json im HEIM (Rest bleibt erhalten)
C_ARBEIT="$A_AUSSEN"; C_CFG="$(aussen "$CFG")"; C_REPO="$(aussen "$REPO")"
VER="$(git -C "$REPO" log -1 --format='%h vom %cs' 2>/dev/null)"   # zeigt das Studio im Menü „⋯“
if [ -n "$PY" ]; then
  MS_C="$HEIM/config.json" MS_A="$C_ARBEIT" MS_K="$C_CFG" MS_R="$C_REPO" MS_V="$VER" "$PY" - <<'PYEOF'
import json, os
p = os.environ['MS_C']
try:
    with open(p, encoding='utf-8') as f:
        d = json.load(f)
except (OSError, ValueError):
    d = {}
d.update({'arbeitsordner': os.environ['MS_A'], 'claude_ordner': os.environ['MS_K'], 'repo': os.environ['MS_R']})
if os.environ.get('MS_V'):
    d['version'] = os.environ['MS_V']
with open(p, 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=1)
    f.write('\n')
PYEOF
else
  setze() {  # $1 Schlüssel, $2 Wert (ohne Python, einfache JSON-Datei mit einem Schlüssel pro Zeile)
    local w; w="$(json_esc "$2")"
    if grep -q "\"$1\"" "$HEIM/config.json"; then
      sed -e "s#\"$1\"[[:space:]]*:[[:space:]]*\"[^\"]*\"#\"$1\": \"$(sed_esc "$w")\"#" "$HEIM/config.json" > "$HEIM/config.json.tmp" \
        && mv "$HEIM/config.json.tmp" "$HEIM/config.json"
    else
      sed -e "1s#^{#{\\
 \"$1\": \"$(sed_esc "$w")\",#" "$HEIM/config.json" > "$HEIM/config.json.tmp" && mv "$HEIM/config.json.tmp" "$HEIM/config.json"
    fi
  }
  [ -f "$HEIM/config.json" ] || printf '{\n "installiert": "%s"\n}\n' "$ZEIT" > "$HEIM/config.json"
  setze arbeitsordner "$C_ARBEIT"; setze claude_ordner "$C_CFG"; setze repo "$C_REPO"
  [ -n "$VER" ] && setze version "$VER"
fi

# ---------------------------------------------------------------- Laufendes Studio auf die neue Version bringen
# Ein Dashboard-Server aus der alten Installation liefert sonst die neue Seite mit altem Code aus (z. B. ohne Pixel-Crew).
# Neustart über die Seite selbst (/api/neustart mit Sitzungs-Token, wie der Menüpunkt „Server neu starten“).
PORT="$(sed -n 's/.*"dashboard_port"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p' "$HEIM/config.json" 2>/dev/null | head -1)"
PORT="${PORT:-8777}"
if command -v curl >/dev/null 2>&1 && curl -s -m 2 -o /dev/null "http://127.0.0.1:$PORT/api/stand"; then
  TOK="$(curl -s -m 3 "http://127.0.0.1:$PORT/" | sed -n 's/.*name="ms-token" content="\([^"]*\)".*/\1/p' | head -1)"
  if [ -n "$TOK" ] && curl -s -m 5 -o /dev/null -X POST -H "X-MS-Token: $TOK" -H "Origin: http://127.0.0.1:$PORT" \
       -H "Content-Type: application/json" -d '{}' "http://127.0.0.1:$PORT/api/neustart"; then
    STUDIO_NEU="Studio auf Port $PORT neu gestartet, es läuft jetzt die neue Version."
  fi
fi

# ---------------------------------------------------------------- Bericht
echo "Motion-Studio installiert."
echo "  Agenten:       $(echo $AGENTEN | wc -w | tr -d ' ') in $CFG/agents ($(echo $AGENTEN | sed 's/ /, /g'))"
echo "  Skills:        $(echo $SKILLS | wc -w | tr -d ' ') in $CFG/skills"
echo "  Werkzeuge:     $HEIM (Einstieg: $H_AUSSEN/ms)"
[ -n "${STUDIO_NEU:-}" ] && echo "  $STUDIO_NEU"
echo "  Arbeitsordner: $A_AUSSEN"
[ -n "$NEU_ANGELEGT" ] && echo "    neu angelegt:$NEU_ANGELEGT"
[ -f "$ARBEIT/PROFIL.md" ] && ! echo "$NEU_ANGELEGT" | grep -q PROFIL && echo "    dein PROFIL.md und LERNLOG.md sind geblieben"
[ -d "$HEIM/.venv" ] && echo "    Python-Umgebung (.venv) ist geblieben"
echo
[ -n "$PY" ]                         || echo "HINWEIS: Python 3.9+ fehlt noch. Der Skill motion-setup installiert es mit dir."
command -v ffmpeg >/dev/null 2>&1    || echo "HINWEIS: ffmpeg fehlt noch. Der Skill motion-setup installiert es mit dir."
command -v node   >/dev/null 2>&1    || echo "HINWEIS: Node.js fehlt noch. Der Skill motion-setup installiert es mit dir."
echo "Nächster Schritt, Stand prüfen:"
echo "  \"$H_AUSSEN/ms\" check"
echo "Claude Code danach im Arbeitsordner mit der Regie als Hauptsitzung starten (dort gelten die erlaubten Befehle,"
echo "und nur die Hauptsitzung kann Analyse, Bauer und Prüfer starten):"
echo "  cd \"$A_AUSSEN\" && claude --agent motion-regie --model opusplan"
echo "  (opusplan: Opus im Plan-Modus, sonst Sonnet. Weglassen, wenn du immer dein Standardmodell willst.)"
