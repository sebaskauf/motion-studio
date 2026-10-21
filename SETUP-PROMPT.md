# Setup-Prompt

Kopier den ganzen Block unter der Linie und füg ihn in Claude Code ein.
Rechne mit 20 bis 60 Minuten, je nachdem, wie viel auf deinem Rechner schon installiert ist.
Das Setup selbst kostet nichts. Bezahlte Dienste verbindest du nur, wenn du willst.

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

SCHRITT 3: ABSCHLUSS
1. Zeig mir als Beleg `"<Installationsordner>/ms" check --stufe alle` und eine kurze Übersicht: Basis ok, Profil fertig, Sound-Bibliothek ja/nein, Blender ja/nein, KI-Pakete ja/nein, verbundene Dienste.
2. Schreib mir zum Schluss eine kurze Rückmeldung zum Weiterleiten an Sebastian: mein System, welche Stufen ok sind, und alles, was gehakt hat (Befehl, genaue Fehlermeldung, wie es gelöst wurde). Höchstens 10 Zeilen, ohne Schlüssel oder Passwörter.
3. Sag mir, dass ich Claude Code einmal neu starten soll, und zwar im Arbeitsordner mit der Regie als Hauptsitzung: `cd <Arbeitsordner> && claude --agent motion-regie`. So gelten die erlaubten Befehle, und die Regie kann Analyse, Bauer und Prüfer starten. Genau so starte ich ab jetzt immer. Danach sage ich einfach, was ich will, zum Beispiel:
   - "Lern den Kanal @<vorbild>"
   - "Bau mir dieses Video nach: <Link>"
   - "Bau die nächste Folge"
   - "Was ist offen?"
   - "Zeig mir das Dashboard"
