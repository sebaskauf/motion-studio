# Motion-Studio

Ein Agenten-Team für Claude Code, das Motion-Design-Kurzvideos baut. Du zeigst ihm einen Kanal, den du gut findest.
Es zerlegt die Videos, baut eines fast 1:1 nach und misst, wie nah es dran ist. Daraus macht es einen Baukasten
und produziert dann laufend eigene Folgen in diesem Stil. Alles läuft lokal auf deinem Rechner.

## Was es kann

| Phase | Wie oft | Was passiert | Ergebnis |
|---|---|---|---|
| **A Einrichten** | einmal | prüft und installiert Programme Stufe für Stufe, Interview zu deinem Kanal, Sound-Bibliothek | alles installiert und geprüft, `PROFIL.md` |
| **B Kanal lernen** | einmal pro Vorbild | Top-Videos finden, zerlegen (Schnitte, Farben, Bewegung, Text, Ton, Skript), ein Video als Pilot nachbauen, Farbabstand und Formähnlichkeit pro Szene messen, unabhängig prüfen | `BIBEL.md` (Stil-Regeln), gemessener Pilot, Baukasten mit Bausteinen, Regeln und Skript-Formeln |
| **C Produzieren** | laufend | Vorlage wählen, eigenes Skript, Stimme, Storyboard, Szenen parallel bauen, Ton mischen, rendern, prüfen | fertiges Video mit Caption und Titelbild im Upload-Ordner |

Vier Agenten: `motion-regie` (dein Ansprechpartner, führt durch alles), `motion-analyse` (zerlegt Vorbilder),
`motion-bauer` (baut Szenen in 2D, 3D im Browser oder Blender, läuft mehrfach parallel), `motion-pruefer` (prüft unabhängig).
Das Fachwissen steckt in Skills mit dem Präfix `motion-`. Gerendert wird mit [HyperFrames](https://github.com/heygen-com/hyperframes) (HTML zu Video).

## Was es nicht kann (ehrlich)

- **Figuren-Animation auf dem Niveau großer 3D-Kanäle ist nicht belegt.** Szene, Licht und Kamera klappen. Figuren mit Rig und echtem Schauspiel sind der Engpass. Das Studio sagt dir vorher, was bei deinem Vorbild realistisch ist.
- **Die Blender-Spur ist Beta.** Sie läuft headless (ohne Oberfläche) und ist langsam: gemessen mit EEVEE 1,5 bis 1,9 s pro Bild in 1080×1920 (Apple M3 Pro, Beispielszene), ein 20-s-Reel also 15 bis 19 Minuten. Three.js im Browser ist rund 6-mal schneller.
- **Gemessene Nähe aus unserem eigenen Nachbau:** 2D (Collage, Typo) ΔE 5,2 und SSIM 0,84, also sehr nah. 3D im Browser ΔE 16 bei Ziel 15, knapp verfehlt.
- **Kein Posten.** Fertige Folgen liegen als Upload-Paket bereit. Hochladen machst du.
- **Instagram-Vorbilder** lassen sich ohne Login kaum laden. Wege: Apify (kostet ein paar Cent) oder du speicherst die Videos selbst. YouTube und TikTok gehen gratis.
- Getestet auf dem Mac (Apple Silicon). **Unter Windows nicht auf echtem Windows getestet**, das Setup ist dafür vorbereitet (winget, Git Bash).

## Was es kostet

| Posten | Nötig? | Kosten |
|---|---|---|
| Claude-Plan mit Claude Code (Pro, Max, Team oder API) | ja | dein Abo. Phase B und parallele Bauer verbrauchen viel. Mit Pro rechne mit Pausen wegen Nutzungslimits, für laufende Produktion ist Max realistischer (Einschätzung, nicht gemessen) |
| Programme (ffmpeg, Node, Python, HyperFrames, Whisper, Blender) | ja, Blender optional | gratis |
| Sound-Bibliothek (Kenney, Mixkit, Sonniss) | ja | gratis, frei für kommerzielle Nutzung |
| Apify (Instagram-Vorbilder laden) | optional | pro Lauf, das Werkzeug nennt vorher die Schätzung |
| Stimme: ElevenLabs oder Higgsfield | optional | nach Plan. Gratis-Weg: eigene Aufnahme |
| Tripo (3D-Figuren aus Text oder Bild) | optional | pro Figur, Preis vor jeder Nutzung prüfen |

Jeder bezahlte Schritt wird vorher mit Betrag genannt und läuft erst nach deinem Ja. Budget und erlaubte Dienste stehen in deinem `PROFIL.md`.

## Voraussetzungen

- Claude Code ([Installation](https://code.claude.com/docs/en/setup)), angemeldet
- macOS 13+ oder Windows 10/11 (mit Git for Windows) oder Linux (Debian/Ubuntu)
- Platz: Programme und Python-Umgebung rund 0,5 GB, Whisper-Modell 0,5 bis 1,6 GB, Blender (optional) 0,9 GB, KI-Pakete (optional) ab 1 GB, dazu Sounds und deine Videos
- git. Alles andere installiert das Setup mit dir (Homebrew, winget oder apt)

## Schnellstart

Kopier den Block aus [SETUP-PROMPT.md](SETUP-PROMPT.md) in Claude Code. Er installiert, prüft und richtet alles mit dir ein.

Von Hand:
```
git clone https://github.com/sebaskauf/motion-studio.git ~/Documents/motion-studio
cd ~/Documents/motion-studio
./install.sh                          # oder: ./install.sh --arbeit ~/MeinOrdner
~/.claude/motion-studio/ms check      # was fehlt noch?
cd ~/MotionStudio && claude --agent motion-regie   # im Arbeitsordner, mit der Regie als Hauptsitzung
```
Starte immer mit `claude --agent motion-regie`: So ist die Regie die Hauptsitzung und kann Analyse, Bauer und Prüfer starten.
Die Knöpfe im Dashboard starten genauso.
Dann zum Beispiel: „Richte Motion-Studio mit mir ein“, „Lern den Kanal @vorbild“, „Bau die nächste Folge“, „Was ist offen?“.

Update: `git pull && ./install.sh`. Dein Profil, Lernlog, Arbeitsordner, Python-Umgebung und Modelle bleiben stehen.

## Dashboard

```
~/.claude/motion-studio/ms dashboard --oeffnen
```
Öffnet http://127.0.0.1:8777: alle Folgen als Karten von Vorlage bis Gepostet, was die Agenten gerade tun,
Knöpfe für feste Aufträge (Vorlagen finden, Kanal lernen, nächste Folge, weitermachen). Läuft nur auf deinem Rechner.

## Ordner

```
~/.claude/agents/motion-*.md          die 4 Agenten
~/.claude/skills/motion-*/            die Skills
~/.claude/motion-studio/              Werkzeuge (ms), Dashboard, Vorlagen, Python-Umgebung, Whisper-Modelle
~/MotionStudio/                       DEIN Arbeitsordner, wird bei Updates nie überschrieben
  PROFIL.md  LERNLOG.md               dein Profil und was das Studio gelernt hat
  .env                                deine Schlüssel (nur hier, nie anzeigen)
  kanaele/<name>/                     gelernte Kanäle: BIBEL.md, REGELN.md, Kit, Analyse, Pilot
  folgen/<datum>-<name>/              jede Folge: Skript, Stimme, Szenen, Renders, upload/
  vorlagen/                           Register der Vorbild-Videos
  sounds/                             Sound-Bibliothek mit Katalog
```
Statt `~/.claude` nimmt der Installer `$CLAUDE_CONFIG_DIR`, falls gesetzt.

## Sicherheit

- Schlüssel stehen nur in `~/MotionStudio/.env`. Claude darf die Datei nicht lesen (Sperre in `.claude/settings.json` des Arbeitsordners), die Werkzeuge lesen sie selbst und geben nie einen Wert aus.
- Im Arbeitsordner sind nur feste Befehle ohne Nachfrage erlaubt (`ms`, ffmpeg, ffprobe, HyperFrames, yt-dlp, whisper-cli, tmux). Alles andere fragt Claude Code vorher.
- Nichts wird gelöscht. Ersetztes wandert nach `_ueberholt/`.
- Keine Browser-Cookies, kein Login bei fremden Plattformen.
- Fremde Videos dienen nur der Analyse. Der Pilot-Nachbau ist eine Übung und wird nicht veröffentlicht. Gepostet wird nur deine eigene Folge.
- Das Dashboard hört nur auf 127.0.0.1 und startet nur feste Aufträge.
- Der Installer überschreibt keine fremden Agenten oder Skills. Bei gleichem Namen bricht er ab (Code 2). `--force` sichert vorher alles nach `~/.claude/motion-studio-sicherungen/`.

## Entfernen

Ordner selbst löschen: `~/.claude/agents/motion-*.md`, `~/.claude/skills/motion-*`, `~/.claude/motion-studio`.
Dein Arbeitsordner bleibt, bis du ihn selbst löschst. HyperFrames-Skills (`~/.claude/skills/hyperframes*`) gehören zu HyperFrames.

## Lizenz

MIT, siehe [LICENSE](LICENSE). HyperFrames und die Sound-Quellen haben eigene Lizenzen.
