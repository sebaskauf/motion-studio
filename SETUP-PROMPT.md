# Setup-Prompt

Kopier den ganzen Block unter der Linie und füg ihn in Claude Code ein.
Rechne mit 20 bis 60 Minuten, je nachdem, wie viel auf deinem Rechner schon installiert ist.
Das Setup selbst kostet nichts. Bezahlte Dienste verbindest du nur, wenn du willst.
Voraussetzung: Claude Code läuft. Hast du das Agentic OS, baut das Setup am Ende den Tab STUDIO hinein (Mac und Windows).
Starte den Prompt am besten in einem normalen Terminal, nicht in einem Agentic-OS-Terminal: Beim letzten Schritt lädt Obsidian neu.

---

Installiere mir Motion-Studio aus diesem Repo und richte es auf MICH ein: https://github.com/sebaskauf/motion-studio

Arbeite die Schritte der Reihe nach ab. Du KANNST das alles über das Terminal. Sag nicht "das geht nicht", führ die Befehle wirklich aus. Schlägt etwas fehl, zeig mir die genaue Fehlermeldung und was du brauchst, statt den Schritt als erledigt zu melden oder ihn zu überspringen.

SCHRITT 1: INSTALLIEREN
1. `git clone https://github.com/sebaskauf/motion-studio.git ~/Documents/motion-studio` (existiert der Ordner schon: dort `git pull`). Fehlt git, sag mir, wie ich es installiere (Mac: `xcode-select --install`, Windows: `winget install -e --id Git.Git`), und warte. Fragt git nach einem Login (privates Repo), gib mir die Zeile `gh auth login` für mein eigenes Terminal (fehlt gh: Mac `brew install gh`, Windows `winget install -e --id GitHub.cli`) und warte, bis ich "fertig" sage.
2. Frag mich EINE Sache: Wo soll mein Arbeitsordner liegen? Vorschlag: `~/MotionStudio`. Dort landen meine Kanäle, Folgen und Sounds.
3. Führ im Repo `./install.sh --arbeit <mein Arbeitsordner>` aus.
   - Läuft es durch: gut.
   - **Endet es mit Code 2**, liegt bei mir schon etwas mit gleichem Namen, das nicht von Motion-Studio stammt. Lies mir vor, was da liegt, und frag MICH, ob du mit `./install.sh --force` ersetzen sollst (vorher wird gesichert). Entscheide das nicht selbst.
4. Sag mir in einem Satz, was installiert ist. Ich muss Claude Code jetzt NICHT neu starten.

SCHRITT 2: SETUP
Lies die installierte Skill-Datei komplett (`~/.claude/skills/motion-setup/SKILL.md`, dazu `OS-DETAILS.md` im selben Ordner) und geh sie jetzt mit mir durch:
- Zuerst `"<Installationsordner>/ms" check --stufe alle` (der Pfad steht am Ende der Ausgabe von install.sh) und mir das Ergebnis als kurze Tabelle zeigen.
- Stufe für Stufe: prüfen, mir sagen, was fehlt und was die Installation macht, nach meinem Ja installieren, wieder prüfen.
- Eine Frage nach der anderen.
- Braucht ein Befehl mein Passwort (Homebrew, sudo), gib mir die Zeile für mein eigenes Terminal und warte, bis ich "fertig" sage.
- Danach das Interview für mein Profil.
- Schlüssel (Apify, ElevenLabs …) zeigst du nie an. Ich trage sie selbst in die `.env` im Arbeitsordner ein.

SCHRITT 3: TAGESBAU (automatisch jeden Tag neue Folgen, token-sparsam)
Lies `"<Installationsordner>/tools/autopilot.py" --help` und erklär mir den Tagesbau in drei Sätzen:
- Was er macht: Jeden Tag im Bau-Fenster startet er selbst neue Folgen für meinen Kanal, höchstens 2 gleichzeitig. Gepostet wird nichts, fertige Folgen landen im Studio.
- Wie er Tokens spart:
  - Bau-Sitzungen mit Sonnet und ohne Auto-Gedächtnis
  - feste Effizienz-Regeln
  - Pause, wenn mein Claude-Limit erreicht ist
- Kosten: Ohne Frage gibt er nur bis zur Grenze „Ohne Nachfrage frei bis“ aus meinem Profil aus. Was mehr kostet, wartet im Studio auf mein Ja.

Dann frag mich EINE Sache: Wie viele Folgen pro Tag? Vorschlag 5, möglich 5 bis 8, je nach meinem Claude-Abo.

Danach:
1. `"<Installationsordner>/ms" autopilot einstellen --pro-tag <Zahl> --fenster 08:00-22:00 --modell sonnet`
2. `"<Installationsordner>/ms" autopilot einrichten`. Das legt den Zeitplan an: Mac launchd, Windows Aufgabenplanung, Linux cron, alle 15 Minuten. Unter Windows statt des ms-Skripts: `py -3 "<Installationsordner>/tools/autopilot.py" einrichten`.
3. Zeig mir `ms autopilot` als Beleg.
4. Sag mir: Eingeschaltet wird der Tagesbau erst, wenn mein erster Kanal fertig gelernt ist. Das geht im Studio mit dem Schalter „Tagesbau“ oder mit `ms autopilot an --kanal <slug>`. Läuft er, sehe ich im Studio jeden Agenten als Pixel-Figur bei der Arbeit und kann seine Fragen dort beantworten.

SCHRITT 4: STUDIO IM AGENTIC OS (nur wenn ich das Agentic OS nutze)
Das Studio ist mein Dashboard: Pixel-Crew der Agenten, Fragen mit Antwortfeld, Tagesbau-Schalter, Sendeplan und Zahlen.
1. Prüfen, ändert nichts: `python3 ~/Documents/motion-studio/agentic-os-tab/einbauen.py --pruefen`. Unter Windows `py -3` statt `python3` und `%USERPROFILE%\Documents\motion-studio\…`.
   - Kein Agentic OS gefunden: Den Schritt überspringen. Das Studio geht auch im Browser: `ms dashboard --oeffnen`.
2. Lies `~/Documents/motion-studio/agentic-os-tab/EINBAU.md` komplett. Halte dich an die Exit-Codes dort.
3. Sag mir vorher, dass Obsidian danach neu laden muss und sich dabei offene Agentic-OS-Terminals schließen. Erst nach meinem Ja: `python3 ~/Documents/motion-studio/agentic-os-tab/einbauen.py` (bei mehreren Vaults mit `--vault <pfad>`).
4. Liefert das Skript eine ENTSCHEIDUNG (mehrere Vaults, fehlende Tabs, Version), frag mich genau das. Rate nicht und bau nichts am Vault von Hand.

SCHRITT 5: ABSCHLUSS
1. Zeig mir als Beleg `"<Installationsordner>/ms" check --stufe alle` und eine kurze Übersicht:
   - Basis ok
   - Profil fertig
   - Sound-Bibliothek ja/nein
   - Blender ja/nein
   - KI-Pakete ja/nein
   - verbundene Dienste
   - Tagesbau eingestellt (Zahl pro Tag, Zeitplan ja/nein)
   - Studio-Tab im Agentic OS ja/nein
2. Schreib mir zum Schluss eine kurze Rückmeldung zum Weiterleiten an Sebastian: mein System, welche Stufen ok sind, und alles, was gehakt hat (Befehl, genaue Fehlermeldung, wie es gelöst wurde). Höchstens 10 Zeilen, ohne Schlüssel oder Passwörter.
3. Hast du den Studio-Tab eingebaut: Ich lade Obsidian jetzt neu (Mac Cmd+R, Windows Strg+R), dann ist oben der Tab STUDIO da.
4. Sag mir, dass ich Claude Code einmal neu starten soll, und zwar im Arbeitsordner mit der Regie als Hauptsitzung:
   - Mac/Linux: `cd <Arbeitsordner> && claude --agent motion-regie`
   - Windows PowerShell: `cd <Arbeitsordner>; claude --agent motion-regie` So gelten die erlaubten Befehle, und die Regie kann Analyse, Bauer und Prüfer starten. Genau so starte ich ab jetzt immer. Danach sage ich einfach, was ich will, zum Beispiel:
   - "Lern den Kanal @<vorbild>"
   - "Bau mir dieses Video nach: <Link>"
   - "Bau die nächste Folge"
   - "Was ist offen?"
   - "Zeig mir das Dashboard"
