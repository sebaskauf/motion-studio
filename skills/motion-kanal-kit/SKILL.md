---
name: motion-kanal-kit
description: "Baukasten eines Kanals aus dem Pilot machen und nach jeder Folge pflegen: wiederverwendbare Bausteine nach kanaele/<k>/kit/ (lib, fonts, tex, beispiele), KATALOG.md erzeugen, nichts darf verschwinden, REGELN.md aus Fehlern, Caption-Stil messen (captions.json), Ton-Rezept, Verweis auf den Skript-Baukasten. Laden bei \"Kit\", \"Baukasten\", \"KATALOG\", \"Bausteine übernehmen\", \"Regeln aus dem Pilot\", \"Kanal fertig machen\"."
---

# motion-kanal-kit

Ziel: Jede neue Folge startet mit allem, was der Pilot gelernt hat. Das Kit liegt in `__ARBEIT__/kanaele/<k>/kit/` und wird bei `ms neu folge` nach `build/assets/` kopiert (lib, fonts, tex).
Start: Beim Anlegen des Kanals (`ms neu kanal`) liegen schon die Start-Bausteine im Kit (`lib/ms2d.js`, `lib/ms3d.js`, `lib/ms3d-start.js`, `beispiele/beispiel-2d.html` Collage, `beispiel-2d-vektor.html` flacher Vektorstil, `beispiel-3d.html`, `captions.json`) und `KATALOG.md` ist schon erzeugt.

## 1. Bausteine aus dem Pilot übernehmen
- Was zweimal vorkommt oder den Stil ausmacht, wird ein Baustein: Hintergrund-Look, Titel-Element, Karten/Rahmen, Übergang, Wow-Effekt, Set mit Licht, Kamera-Muster, Figur/Objekt.
- Form: Funktion in einer Kit-Datei mit Kommentar direkt darüber (eine Zeile Zweck, dann Optionen mit Standardwerten). 2D in `lib/<kanal>2d.js` mit `/* ms-global */` in Zeile 1 und eigenem Objekt (z. B. `window.KANAL2D`), 3D als ES-Modul `lib/<kanal>3d.js` (`import * as THREE from 'three'`). In Szenen nur im `aufbau`-Teil laden: `await import(new URL("assets/lib/<kanal>3d.js", document.baseURI).href)`, nie in zustand oder kamera (Regel in motion-szene-3d-web).
- Pro Baustein eine Beispiel-Szene in `beispiele/` (eine fertige Pilot-Szene, ids auf `beispiel…` umbenannt). Sie ist die Vorlage für die Bauer.
- Schriften nach `kit/fonts/`, Texturen nach `kit/tex/` (Lizenz prüfen: nur frei nutzbare Dateien).
- **Nur additiv.** Vor jedem Kopieren:
```
__HEIM__/ms kit <k> pruefen --kandidat __ARBEIT__/folgen/<folge>/build/assets/lib
```
  OK → jede Datei mit Read lesen und mit Write nach `kanaele/<k>/kit/lib/` schreiben (kein `cp`). Meldet es „würde verschwinden“: fehlende Funktionen zurückholen, dann erneut prüfen.
- Danach `__HEIM__/ms kit <k> katalog` und `__HEIM__/ms kit <k> pruefen` (Syntax jeder Datei, nichts verschwunden).
**Gate:** `pruefen` OK, KATALOG.md listet jeden Baustein mit Kommentar, jede Datei hat ein Beispiel.

## 2. KATALOG.md
- Oberer Teil wird erzeugt (Funktionen, Kommentare, Beispiele). Nie von Hand ändern, sondern die Kommentare im Code.
- Unterer Teil ab der Zeile `---` ist von Hand: **Rezepte** (bewährte Kombinationen mit Szene und Datum, ein Satz Wirkung, Schnipsel). Bleibt beim Neu-Erzeugen erhalten.

## 3. REGELN.md (was den Stil ausmacht, prüfbar)
- Mindestens 8 Regeln, jede prüfbar am Bild oder in Zahlen: „Hintergrund immer #f3ead9 mit Raster 0,08“, „Titel oben bei y 260, Montserrat 900, max. 900 px breit“, „pro Szene ein Stempel-Treffer mit Kamera-Punch 1,1“, „Schnitt alle 2 bis 3 s“.
- Jeder Fehler aus Pilot und Folgen wird eine Regel mit Datum: was passiert ist, woran man es erkennt, wie man es verhindert. Neueste Aussage des Nutzers schlägt ältere, Widerspruch mit Auflösung notieren.
- motion-pruefer liest REGELN.md bei jeder Abnahme.

## 4. Caption-Stil (kit/captions.json)
Am Original messen (Einzelbild mit Caption in voller Größe): Schrift, Größe in px, Farben (Text, Kontur, Hervorhebung, Kasten), Oberkante y, Wörter pro Gruppe, Erscheinen (Wort für Wort oder Gruppe). Prüfen: `__HEIM__/ms szenen <folge>` und `__HEIM__/ms snap <folge> <zeiten> --gegen <original>` (Paar-Bogen `kontaktbogen_paar.jpg`).
Alle Felder (fehlt eins, gilt der Standard; Felder, die mit `_` beginnen, sind Kommentare und werden ignoriert):

| Feld | Standard | Erlaubt / Bedeutung |
|---|---|---|
| `an` | `true` | `false` = Kanal ohne Untertitel (einzelne Szenen abschalten: `"captions": false` in scenes.json) |
| `schrift` | `"Montserrat"` | eingebaut und offline: Montserrat, Oswald, League Gothic (nur 400), Archivo Black (nur 400), Space Mono, IBM Plex Mono, JetBrains Mono |
| `schrift_datei` | `null` | eigene Schrift: `"fonts/<datei>.ttf"` (Datei in `kit/fonts/`, landet in `build/assets/fonts/`), ersetzt dann `schrift` |
| `gewicht` | `900` | 100 bis 900 (die Schrift muss das Gewicht haben) |
| `groesse` | `74` | Schriftgröße in px bei 1080 Breite |
| `versalien` | `true` | `true` = alles groß, `false` = wie geschrieben |
| `farbe` | `"#ffffff"` | Textfarbe (CSS-Farbe) |
| `kontur` | `"#000000"` | Konturfarbe außen, `null` = ohne |
| `kontur_breite` | `12` | px, liegt hinter der Schrift |
| `schatten` | `"0 8px 0 rgba(0,0,0,0.35)"` | CSS `text-shadow`, `null` = ohne |
| `hintergrund` | `null` | Kasten hinter jedem Wort, z. B. `"#0f5a46"` |
| `hintergrund_radius` | `14` | px Eckenradius des Kastens |
| `innenabstand` | `"8px 20px 10px"` | CSS `padding` des Kastens |
| `hervorhebung` | `{"farbe": "#ffd23f", "hintergrund": null, "skala": 1.08}` | aktuelles Wort: Farbe, eigener Kasten, Größe (1 = gleich groß) |
| `y` | `1470` | Oberkante der Caption-Zeile in px (Bild 1920 hoch). Wichtiges im Bild bleibt oberhalb von y − 125 |
| `seitenrand` | `70` | px links und rechts |
| `zeilenabstand` | `1.08` | CSS `line-height` |
| `wortabstand` | `18` | px zwischen den Wörtern |
| `max_woerter` | `3` | Wörter pro Gruppe (gilt auch für `ms woerter`) |
| `max_zeichen` | `18` | Zeichen pro Gruppe |
| `pause_bruch` | `0.35` | s Sprechpause, ab der eine neue Gruppe beginnt |
| `erscheinen` | `"wort"` | `"wort"`: Wörter erscheinen nacheinander auf ihrem gesprochenen Wort. `"gruppe"`: ganze Gruppe steht ab Gruppenstart, das aktuelle Wort leuchtet |
| `animation` | `"pop"` | `"pop"`: ploppt mit Überschwinger auf (0,12 s). `"auf"`: gleitet 30 px hoch (0,14 s). `"keine"`: erscheint hart. Andere Werte wirken wie `"keine"` |
| `satzzeichen_weg` | `".,;:"` | diese Zeichen am Wortende werden nicht angezeigt (`""` = alle zeigen) |

Gruppen wie im Original (Pilot) gehören nicht hierher, sondern von Hand nach `build/captions.json` der Folge (Skill motion-kanal-lernen, Schritt 4).

## 5. Ton-Rezept und Skript-Baukasten
- `kit/ton-rezept.json`: Musik ja/nein, Musik-Abstand, Sprechtempo (wps), typische Effekt-Familien je Aktion. Format und Werkzeug: Skill motion-ton-mix.
- `SKRIPT-BAUKASTEN.md` (Hook-Formeln, Aufbau, Länge) entsteht in Skill motion-skript-zerlegen. Hier nur prüfen, dass er existiert und im KATALOG unter „Dazu“ verlinkt ist.

## 6. Nach jeder Folge pflegen
1. Neue Bausteine der Folge prüfen und additiv übernehmen (Schritt 1).
2. Neue Fehler als Regel in REGELN.md, gute Kombinationen als Rezept in KATALOG.md.
3. `__HEIM__/ms kit <k> katalog`. Status nur beim Pilot setzen: `__HEIM__/ms status kanal:<k> kit --notiz "<n> Bausteine, <m> Regeln"`.

## Fallen
- Ein Syntaxfehler in einer Kit-Datei rendert JEDE Szene leer: `ms kit <k> pruefen` vor jedem Kopieren.
- Doppelte Funktionsnamen in zwei Dateien desselben globalen Objekts überschreiben sich still. Ein Objekt pro Datei.
- Beispiel-Szenen mit festen Pfaden außerhalb von `assets/` laufen beim nächsten Nutzer nicht.
