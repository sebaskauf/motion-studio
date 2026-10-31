# OS-Details für das Setup

Alle Paket-IDs und Befehle geprüft am 20.10.2026 (Homebrew-Formeln per `brew info`, winget-IDs im Repo microsoft/winget-pkgs,
Claude Code laut code.claude.com/docs/en/setup). `ms setup programme` nutzt genau diese Befehle.

## Mac

| Programm | Befehl | Hinweis |
|---|---|---|
| Homebrew | `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"` | fragt nach dem Mac-Passwort, nur im eigenen Terminal. Am Ende die zwei angezeigten `echo`-Zeilen ausführen, sonst fehlt `brew` im PATH |
| ffmpeg, ffprobe | `brew install ffmpeg` | |
| Python | `brew install python@3.12` | Systempython 3.9 reicht auch. Pakete nur ins venv (`ms setup venv`) |
| Node.js | `brew install node` | HyperFrames braucht 22 oder neuer |
| yt-dlp | `brew install yt-dlp` | regelmäßig `brew upgrade yt-dlp`, alte Versionen scheitern an YouTube |
| whisper-cli | `brew install whisper-cpp` | nutzt auf Apple Silicon die Grafikeinheit (Metal). Modell: `ms setup whisper-modell turbo --ja` |
| tmux | `brew install tmux` | für Agent-Sitzungen aus dem Dashboard |
| tesseract | `brew install tesseract` | optional, Texterkennung |
| git | `xcode-select --install` | meist schon da |
| Blender | `brew install --cask blender` | optional, rund 0,9 GB, liegt dann unter /Applications/Blender.app |
| Claude Code | `curl -fsSL https://claude.ai/install.sh \| bash` oder `brew install --cask claude-code` | |

Apple Silicon (M1 bis M5): alles läuft nativ. Intel-Macs gehen auch, Whisper und Blender sind deutlich langsamer (Whisper `small` nehmen).

## Windows (10/11)

Zuerst **Git for Windows** (`winget install -e --id Git.Git`): Für Motion-Studio Pflicht, weil `install.sh` und `ms` Bash-Skripte sind und im Bash-Werkzeug (Git Bash) laufen müssen. Claude Code selbst geht laut Doku auch ohne Git (dann nur mit PowerShell), Motion-Studio nicht.
winget kommt mit dem „App Installer“ aus dem Microsoft Store. Im Werkzeug laufen die Befehle mit `--accept-source-agreements --accept-package-agreements`.

| Programm | winget-ID | Hinweis |
|---|---|---|
| Git | `Git.Git` | Pflicht |
| ffmpeg | `Gyan.FFmpeg` | |
| Python | `Python.Python.3.12` | danach heißt der Befehl oft `python`, nicht `python3`. `ms` findet beides |
| Node.js | `OpenJS.NodeJS.LTS` | |
| yt-dlp | `yt-dlp.yt-dlp` | |
| tesseract | `UB-Mannheim.TesseractOCR` | optional |
| Blender | `BlenderFoundation.Blender` | optional, landet in `C:\Program Files\Blender Foundation\Blender <Version>\blender.exe`, `ms check` findet es dort |
| Claude Code | `Anthropic.ClaudeCode` | oder in PowerShell `irm https://claude.ai/install.ps1 \| iex` |

- **Nach jeder winget-Installation Claude Code schließen und neu starten.** Neue Programme stehen erst in einem neuen Terminal im PATH.
- **Transkription:** whisper.cpp gibt es nicht über winget. Einfachster Weg: `ms setup venv --whisper` (faster-whisper, läuft auf der CPU, mit NVIDIA-Karte schneller). Alternative: `whisper-bin-x64.zip` von den GitHub-Releases von whisper.cpp entpacken und den Ordner in den PATH legen.
- **tmux gibt es unter Windows nicht.** Das Dashboard startet Agenten dann in einem neuen Terminalfenster.
- Pfade: Agenten und Werkzeuge schreiben `C:/Users/<name>/…` mit Schrägstrichen. Das verstehen Git Bash, Python und Claude Code.
- Lange Pfade: liegt der Arbeitsordner tief verschachtelt, können manche Programme scheitern. Arbeitsordner kurz halten (Standard `C:/Users/<name>/MotionStudio`).
- Nicht getestet auf echtem Windows. Fehlermeldungen genau zeigen und ins Lernlog schreiben.

## Linux (Debian, Ubuntu)

`sudo` fragt nach dem Passwort, deshalb zeigt `ms setup programme` die Befehle nur an. Der Nutzer führt sie selbst aus.

| Programm | Befehl |
|---|---|
| ffmpeg | `sudo apt install -y ffmpeg` |
| Python | `sudo apt install -y python3 python3-venv python3-pip` |
| Node.js 22 | `curl -fsSL https://deb.nodesource.com/setup_22.x -o nodesource_setup.sh && sudo -E bash nodesource_setup.sh && sudo apt install -y nodejs` (die apt-Version ist meist zu alt) |
| yt-dlp | `sudo apt install -y pipx && pipx install yt-dlp` (apt-Version veraltet) |
| tmux, tesseract, git | `sudo apt install -y tmux tesseract-ocr git` |
| Blender | `sudo snap install blender --classic` |
| Transkription | `ms setup venv --whisper` |
| Claude Code | `curl -fsSL https://claude.ai/install.sh \| bash` |

## Für alle Systeme

| Teil | Befehl | Größe |
|---|---|---|
| HyperFrames | `npx --yes hyperframes --version` (lädt in den npx-Speicher) | rund 130 MB (gemessen, Mac) |
| Chrome für HyperFrames | `npx --yes hyperframes browser ensure` | rund 190 MB (gemessen, Mac) |
| HyperFrames-Skills | `ms setup hyperframes-skills --ja` (= `npx hyperframes skills`) | klein |
| Python-Pakete | `ms setup venv` | 165 MB (gemessen, Mac, inkl. scipy), 45 s |
| Whisper-Modell | `ms setup whisper-modell small|turbo|turbo-q5 --ja` | 0,49 / 1,62 / 0,57 GB |
| KI-Pakete | `ms setup venv --ki --ja` | Mac rund 1 GB, mit CUDA 3 GB und mehr |

Wo was liegt: Werkzeuge in `__HEIM__`, Arbeit in `__ARBEIT__`, Whisper-Modelle in `__HEIM__/modelle`, Python-Umgebung in `__HEIM__/.venv`.
Ein Update mit `./install.sh` lässt `config.json`, `.venv` und `modelle` stehen.
