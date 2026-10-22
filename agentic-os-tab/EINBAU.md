# STUDIO-Tab ins Agentic OS einbauen

Diese Anleitung ist für Claude, nicht für den Nutzer. Sie baut den Tab STUDIO in ein bestehendes Agentic OS ein. Der Tab zeigt das Motion-Studio-Dashboard des Nutzers:
- Pixel-Crew der Agenten
- Fragen der Agenten mit Antwortfeld
- Steuerung des Tagesbaus
- Sendeplan
- Zahlen

Er läuft auf macOS, Windows und Linux und braucht keine CSS-Änderung, weil er die Klassen des CUTTER-Tabs nutzt.

Alles Feste erledigt `einbauen.py` (nur Python-Standardbibliothek). Du entscheidest nur, wo der Nutzer gefragt werden muss.

## Ablauf

1. **Prüfen, ändert nichts:**
   ```
   python3 <repo>/agentic-os-tab/einbauen.py --pruefen
   ```
   - Unter Windows heißt der Aufruf `py -3` bzw. `python` statt `python3`.
   - Das Skript zeigt Vault, Plugin-Version, vorhandene Tabs, Motion-Studio, git, node und npm sowie Tabs, die im Quellcode fehlen.
   - Fehlt Node: Der Nutzer installiert Node LTS von nodejs.org (Windows: `winget install -e --id OpenJS.NodeJS.LTS`). Danach neu prüfen.
2. **Vor dem Einbau dem Nutzer sagen:**
   - Obsidian muss danach einmal neu laden.
   - Dabei schließen sich alle offenen Agentic-OS-Terminals.
   - Läuft diese Sitzung selbst in so einem Terminal, stirbt sie beim Neuladen. Das ist in Ordnung, es ist der letzte Schritt.
   - Erst nach seinem Ja weiter.
3. **Einbauen:**
   ```
   python3 <repo>/agentic-os-tab/einbauen.py [--vault <pfad>]
   ```
   Die Exit-Codes:

   | Code | Bedeutung | Was du tust |
   |---|---|---|
   | 0 | Fertig, oder der Tab war schon drin | Weiter mit Schritt 4 |
   | 2 | Der Nutzer muss entscheiden | Text vorlesen, fragen, dann noch einmal aufrufen |
   | 1 | Fehler | Genaue Meldung zeigen, nichts selbst „reparieren“ am Vault |

   Fälle bei Code 2:
   - **Mehrere Vaults:** fragen welcher, dann mit `--vault`.
   - **Fremde Tabs fehlen im Quellcode:**
     - Das Plugin im Vault hat Tabs (z. B. CAROUSEL, BRIEFING), die im Quellordner `~/Documents/Projects/agentic-os` nicht eingebaut sind. Ein Build würde sie löschen.
     - Erst deren EINBAU.md im selben Quellordner nachholen (z. B. `carousel-producer-plugin/agentic-os-tab/EINBAU.md`), dabei nur Schritte 2 bis 4 ausführen. Bauen und Kopieren übernimmt `einbauen.py`.
     - Dann noch einmal aufrufen.
   - **Version:** Das Plugin im Vault ist neuer als der Quellcode. Nicht bauen. Dem Nutzer sagen, dass er die neueste Agentic-OS-Fassung braucht, bzw. den Quellordner aktualisieren.
   - **Ein anderer STUDIO-Tab ist schon da** (z. B. Sebastians eigener): nicht überschreiben.
4. **Neu laden lassen:**
   - Der Nutzer lädt Obsidian neu. Mac: Cmd+R, Windows: Strg+R, oder in der Befehlspalette „Reload app without saving“.
   - Danach steht oben der Tab STUDIO. Er startet das Dashboard selbst, Port 8777, sonst `dashboard_port` aus `<HEIM>/config.json`.
5. **Zurück, falls etwas nicht stimmt:**
   - Im Plugin-Ordner liegt `main.js.bak-vor-studio-<zeit>`. Wieder in `main.js` umbenennen und neu laden.
   - Ein kaputtes Cockpit ist schlimmer als ein fehlender Tab.

## Was das Skript ändert

- **Im Quellordner (`~/Documents/Projects/agentic-os`, bei Bedarf geklont):**
  - neu: `src/StudioView.tsx`, `src/loadStudio.ts`
  - `src/App.tsx` an vier Stellen: Import, `TabId`, `TABS`, Render-Zweig neben CUTTER. Die Sicherung liegt als `App.tsx.vor-studio` daneben.
  - Gebaut wird mit `npm install --ignore-scripts`, `tsc` und `esbuild`. node-pty bleibt extern, die Binaries im Vault bleiben.
- **Im Vault:** nur `main.js`, vorher gesichert. `styles.css` und `manifest.json` bleiben.
- **Zeigerdatei `~/.motion-studio-heim`:** Darin steht, wo Motion-Studio liegt. Daraus startet der Tab `dashboard/server.py`, mit dem Python aus `<HEIM>/.venv`, sonst python3 bzw. `py -3`.
