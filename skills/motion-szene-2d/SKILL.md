---
name: motion-szene-2d
description: "2D-Szene für Motion-Studio bauen und prüfen: HyperFrames-Komposition mit GSAP (Typo, Collage, UI, Diagramme, Lottie), Bibliothek MS2D aus dem Kanal-Kit, seek-sicher, Text eingepasst, Aktionen auf den Wortzeiten, Wow-Moment, Prüfung per Snapshot-Raster. Laden bei \"2D-Szene\", \"Szene art 2d\", \"GSAP-Szene\", \"Typo-Animation\", \"Collage-Szene\", \"baue Szene s3 (2d)\"."
---

# motion-szene-2d

Grundlage: HyperFrames-Skills `hyperframes-core` (Vertrag einer Komposition) und `hyperframes-animation` (GSAP, Lottie: `adapters/gsap.md`, `adapters/lottie.md`). Bei Unklarheit dort nachlesen.
Bibliothek: `build/assets/lib/ms2d.js` (globales Objekt `MS2D`, in index.html automatisch geladen). Liste aller Bausteine: `kanaele/<k>/kit/KATALOG.md`.

## Gerüst
1. Vorlage übernehmen: `kanaele/<k>/kit/beispiele/beispiel-2d.html` (Collage, Papier, Stempel) oder `beispiel-2d-vektor.html` (flacher Vektorstil in SVG: wenige Flächen, eine Aktion auf dem Wort, Zoom-Punch) mit Read lesen. Gibt es im Kit eine Szene, die näher dran ist, die nehmen. In `build/compositions/<id>.html` liegt schon ein Platzhalter von `ms szenen`: mit Read öffnen, dann mit Write komplett durch die Vorlage ersetzen (`data-platzhalter` fällt dabei weg). Kein `cp`.
2. Alle `beispiel2d` bzw. `beispiel2dv` durch die Szenen-id ersetzen. `data-duration` und `DUR` = Dauer aus scenes.json (auf 0,005 s genau).
3. Ebenen von außen nach innen: `#<id>-root` (Hintergrund) > `-wisch` (Übergang) > `-kamera` (Push-in) > `-punch` (Zoom-Stoß) > `-wackel` (Shake) > Inhalt. Jede Bewegungsart auf einer eigenen Ebene, sonst überschreiben sich scale/x/y.
4. Alles im `<template>`: Style, Markup, Script. ids immer mit `<id>-` beginnen (eindeutig in der ganzen Seite).
5. Skript: `build()` nach `MS2D.schriftenLaden([...])`, darin eine `gsap.timeline({ paused: true })`, alles auf diese Timeline, am Ende `window.__timelines["<id>"] = tl`.

## Regeln
- **Zeiten lokal:** lokal = Wortzeit global − Szenenstart. Konstanten `T_…` oben im Skript, mit dem Wort im Kommentar.
- **Eine Aktion pro Aussage auf ihrem Wort**, 0,3 bis 0,4 s lesbar. **Ein Wow-Moment** (`MS2D.schlag` + `staub` + `kameraPunch` + `wackeln`, `funken`, `konfetti`, `glanz`, `zaehler`, `linieZeichnen`).
- **Lebt immer:** `MS2D.kameraLeben(tl, kamera, DUR)`. Über 1,5 s ohne neue Aktion: Detail einplanen (Glanz, Funkeln, Nachfedern).
  **Ausnahme Pilot:** 1:1 geht vor Stil. Steht die Kamera im Original still (Kamera-Spalte in ANALYSE.md „ruhig“, Paarbilder), dann kein `kameraLeben` und kein zusätzlicher Push-in. Hat das Original einen Punch oder schnellen Zoom (ANALYSE.md, „Kamera-Ereignisse in einer Szene“), genau den nachbauen: Zeit, Richtung, Stärke aus dem Szenenbogen messen.
- **Seek-sicher:** kein `Math.random`, kein `Date`, kein `setTimeout`, keine Zustände. Zufall `MS2D.rng(seed)`, berechnete Bewegung `MS2D.bake(tl, el, (t) => ({…}), t0, t1)`.
- **Text immer einpassen:** `MS2D.textEinpassen(el, text, { breite, groesse, familie })`. Nie Text über den Rand. Keine `<br>` in Fließtext.
- **Schriften:** in HyperFrames eingebaut (offline): Montserrat, Oswald, League Gothic, Archivo Black (nur 400), Space Mono, IBM Plex Mono, JetBrains Mono. Eigene Schrift: `@font-face` auf `assets/fonts/<datei>` im Template.
- Farben, Schrift, Motiv genau wie im Brief. Wichtiges oberhalb der Caption-Zone (Standard y 1345).
- Übergang rein: `MS2D.wisch` bei 0 (Standard) oder wie im Brief (Herauszoomen aus Bildschirm: `-kamera` scale 1,25 → 1 in 0,2 s, Hintergrundfarbe = Fläche der Szene davor).

## Technik-Fallen (alle schon passiert)
- `tl.set(el, {opacity: 0}, 0)` greift im allerersten Bild nicht sicher. Startzustände ins CSS (`opacity: 0`).
- Nach `tl.set(el, {opacity: 1}, t)` folgende `fromTo` mit `immediateRender: false`, sonst springt das Element vorher.
- CSS-`transform` und GSAP auf derselben Eigenschaft streiten (lint `gsap_css_transform_conflict`): Startwert in `fromTo` setzen, zentrieren mit `left/top` statt `translate(-50%)`.
- GSAP liest zahlartige Texte als Zahl („1.000“ wird 1): Texte über `MS2D.zaehler`/`MS2D.tippen` setzen (die schützen das).
- Nie `visibility`/`display`/`autoAlpha` auf einem `.clip`-Element tweenen (lint). Kinder animieren.
- Ein Syntaxfehler in EINER Szene rendert die ganze Seite leer, auch Captions. Deshalb lint vor jedem Snapshot (`ms snap` macht das).
- Filter (`filter: url(#…)`) auf großen Ebenen kosten Renderzeit: nur während des Wischs setzen (macht `MS2D.wisch`).

### SVG-Fallen (Vektorstil; aus dem Kaltstart-Test und dem Bau des Beispiels, Lösung in `beispiel-2d-vektor.html`)
- **Ursprung beim Skalieren/Drehen:** `transformOrigin: "540px 760px"` bezieht sich bei SVG-Elementen auf deren eigene Box, nicht aufs Bild. Für einen Punkt im Bild `svgOrigin: "540 760"` nehmen (viewBox-Koordinaten, ohne px).
- **svgOrigin in from UND to:** `tl.fromTo(el, {scale: 0.5, svgOrigin: M}, {scale: 1, svgOrigin: M, …})`. Steht es nur in den Zielwerten, gleicht GSAP den Wechsel des Ursprungs aus und das Element landet versetzt oder zu groß (im Test: Strahlenkranz doppelt so groß, Schein 170 px verschoben).
- **Schrift im SVG:** Das Attribut `font-family="Montserrat"` am `<text>` allein lädt die Schrift nicht sicher (Ersatzschrift im Render). Immer eine CSS-Regel im Template, z. B. `#<id>-svg text { font-family: "Montserrat"; font-weight: 900; }`, eigene Schrift zusätzlich mit `@font-face`, und vor dem Bauen `MS2D.schriftenLaden([...])` abwarten.
- **Per Code erzeugte SVG-Elemente** (`createElementNS`, z. B. Strahlen, Punkte): `opacity="0"` direkt beim Anlegen setzen. Mit `fromTo(…, {immediateRender: false})` gilt der Startwert erst ab dem Startzeitpunkt, davor stünde das Element sichtbar im Bild. Dasselbe für Markup-Elemente, die später erscheinen (`opacity="0"` im Markup).

## Prüfen (Pflicht, bevor du fertig meldest)
1. `__HEIM__/ms szenen <folge> --check --lint --nur <id>` → kein Fehler zu deiner Szene (auch kein „noch nicht gebaut“), lint 0 Fehler. `ms snap` lintet zusätzlich vor jedem Bild.
2. `__HEIM__/ms snap <folge> --szene <id> --raster 0.25 --name <bauer>_<id>` und den Kontaktbogen mit dem Read-Tool ansehen.
3. Kernaktionen einzeln: `__HEIM__/ms snap <folge> --szene <id> --lokal <T_1> <T_1+0.1> <T_2> … --name <bauer>_<id>_kern`.
4. Prüfliste je Bogen: Jede Aktion auf ihrem Wort sichtbar? Text lesbar und im Rahmen? Wow-Moment da? Erstes Bild nicht leer? Nichts verdeckt Wichtiges oder liegt unter den Captions? Leere Flächen? Stillstand über 1,5 s?
5. Korrigieren, erneut prüfen. Unklare Stelle in voller Größe: die `frame-*.png` im Snapshot-Ordner öffnen.
**Gate:** lint 0 Fehler, Raster angesehen, Prüfliste ohne offenen Punkt.

## Pilot (Nachbau)
Referenzbild je Zeitpunkt: `__HEIM__/ms snap <folge> <zeiten> --gegen __ARBEIT__/folgen/<folge>/vorbild/ausschnitt.mp4 --name <bauer>_<id>_paar` legt das Original daneben (Ausschnitt mit gleicher Zeitachse wie der Pilot, aus `ms stimme --original`).
Ergebnis: `kontaktbogen_paar.jpg` (je Zeitpunkt Original links, Nachbau rechts, Zeit global und lokal) zuerst ansehen.
Lage und Größe in Pixeln am Original messen (Kontaktbogen, Einzelbild), nicht schätzen. Eine Variable pro Versuch (Skill motion-vergleich).
Kamera wie im Original: still, wenn sie dort still steht (kein `kameraLeben`), Punches und schnelle Zooms nur dort, wo ANALYSE.md sie meldet.
