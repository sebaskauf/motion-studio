---
name: motion-szene-3d-web
description: "3D-Szene für Motion-Studio im Browser bauen und prüfen: Three.js in HyperFrames über ms3dSzene (Kit ms3d.js), Kamera-Mathe für Hochformat, Toon oder PBR, Licht-Presets, Kamerafahrten als Funktion der Zeit, Treffer-Blitz mit Bloom, Funken, Konfetti, Portal-Übergang, seek-sicher, Prüfung per Snapshots. Laden bei \"3D-Szene\", \"Three.js\", \"Szene art 3d-web\", \"3D im Browser\", \"baue Szene s2 (3d)\"."
---

# motion-szene-3d-web

Grundlage: HyperFrames-Skill `hyperframes-animation` → `adapters/three.md` (hf-seek, buildReady). Das Kit nimmt dir die Anbindung ab.
Bibliothek: `build/assets/lib/ms3d.js` (ES-Modul, kommt als `M`) und `ms3d-start.js` (globale Funktion `ms3dSzene`). Bausteine: `kanaele/<k>/kit/KATALOG.md`.

## Gerüst
1. Vorlage übernehmen: `kanaele/<k>/kit/beispiele/beispiel-3d.html` (oder eine nähere 3D-Szene aus dem Kit) mit Read lesen. In `build/compositions/<id>.html` liegt schon ein Platzhalter von `ms szenen`: mit Read öffnen, dann mit Write komplett durch die Vorlage ersetzen. Kein `cp`.
2. Alle `beispiel3d` durch die Szenen-id ersetzen, `data-duration` und `DUR` = Dauer aus scenes.json.
3. Die Zeile `<script type="module">import "three";</script>` bleibt drin (lädt three über die Import-Map vor, lint `missing_three_script`).
4. Aufbau:
```js
ms3dSzene({ id: "s2", dauer: DUR, canvas: "s2-canvas", hintergrund: "#1b2230", fov: 40, toon: true,
  schriften: ["900 100px Montserrat"],
  aufbau: async (M, m) => { /* Set, Licht, Requisiten, Effekte anlegen. return welt */ },
  zustand: (t, w, M, m) => { /* pro Bild: alles als reine Funktion von t */ },
  kamera: (t, w, M) => ({ pos: [x, y, z], ziel: [x, y, z], fov: 40 }),
  post: (t) => ({ bloom: t > T_HIT && t < T_HIT + 0.3 ? 0.8 : 0.35 }) });
```
**`import()` nur im `aufbau`-Teil** (läuft einmal, darf `await`): erlaubt sind `three/addons/…` (z. B. GLTFLoader) und das Kanal-Kit `assets/lib/<kanal>3d.js` über `await import(new URL("assets/lib/<kanal>3d.js", document.baseURI).href)`. Nie in `zustand`, `kamera` oder `post`: die laufen pro Bild, müssen synchron und seek-sicher sein. Keine weiteren statischen `import`-Zeilen außer der Vorlade-Zeile aus Schritt 3. Alles andere kommt über `M` (`M.THREE`, `M.kiste`, …). Rückgabe von `ms3dSzene` ist die GSAP-Timeline der Szene: Titel oder Wisch als DOM-Ebene über dem Canvas dürfen darauf animiert werden.
Der globale Start wird aus index.html gelesen. `t` in zustand/kamera ist lokal (0 = Szenenstart).

## Maße und Kamera (Zahlen statt Gefühl)
- Hochformat, fov 40 (vertikal): **sichtbare halbe Breite ≈ 0,205 × Abstand**, halbe Höhe ≈ 0,364 × Abstand. Bei 5 m Abstand nur ±1,0 m Breite. `M.halbeBreite(abstand)`, `M.abstandFuerBreite(m)` rechnen genau.
- Hauptobjekt ≥ 25 % Bildbreite, nie angeschnitten. Halbtotale: Kamera 4,5 bis 5,6 m vor dem Objekt, Höhe 1,6 bis 2,1 m.
- Kamera als Funktion der Zeit: `M.kamerafahrt({0: {pos, ziel, fov}, 1.2: {…}})`, `M.orbit({...})`, Stoß nach Treffer `M.schuettel(t, T_HIT, 0.035)`. Push-in auf einen Treffer 0,3 s vor dem Wort starten, auf dem Wort ankommen.
- Kamerapfad nie durch Objekte (Wände, Säulen). Keine Reißschwenks, keine Wackel-Kamera.
- Wichtiges oberhalb der Caption-Zone (Standard y 1345): `m.projiziere([x,y,z])` gibt Pixel.

## Look
- `toon: true` = Cel-Shading (drei Lichtstufen), sonst PBR (`M.materialPBR(farbe, {rau, metall})`). Leuchtendes für Bloom: `M.leuchtend(farbe, 2.5)`.
- Licht: `M.licht(scene, "studio" | "abend" | "buehne" | "tag")`. Nie nur ein Licht: ohne Fill/Himmel werden Rückseiten schwarz (flache Scherenschnitte).
- Post pro Bild über `post(t)`, Werte in `M.POST`: belichtung, bloom, bloomSchwelle, schaerfe + blende (Tiefenschärfe), ao, korn, vignette, mb (Bewegungsunschärfe 5 nur während schneller Fahrten).
- Text in 3D: `M.textTextur(text, {b, h, hg, farbe})` (per measureText eingepasst). Tafelfarbe ≤ 0,85 Helligkeit, sonst Bloom-Schleier über der Schrift.
- Modelle (GLTF): `const { GLTFLoader } = await import("three/addons/loaders/GLTFLoader.js")` im aufbau (Regel oben), Datei lokal in `build/assets/`, im aufbau laden (`await`), nie in zustand.

## Effekte (Wow pro Szene, Rezepte im KATALOG)
- **Treffer:** `M.blitz()` + `M.blitzZeigen(w.blitz, t, T_HIT, pos, m.camera.position)` + Bloom-Spitze in `post` + `M.schuettel` + `M.funkenWolke` mit `wolke: false`. Rauchwolken nie auf den Treffer (verdecken ihn), nur beim Erscheinen (`ring: true`).
- **Erfolg:** `M.konfetti(scene).add(pos, T, {n: 70})`, Update im zustand.
- **Licht-Dramatik:** Licht-Preset `buehne` oder Intensitäten im zustand dimmen, Spot auf das Objekt.
- **Übergang 3D → 2D:** `M.portalFahrt(flaeche, kamera(T0), T0, DUR - 0.08)`: Fläche in der Hintergrundfarbe der nächsten 2D-Szene füllt am Ende das Bild. Im Brief der 2D-Szene: „startet als Herauszoomen, Hintergrund #…“.
- **Lebendig:** Nachfedern nach Aufprall (`Math.exp(-(t-T)*9) * Math.sin((t-T)*22)`), Squash beim Landen, leichte Drehung, Partikel im Licht.

## Seek-Sicherheit und Technik-Fallen (alle schon passiert)
- zustand(t) und kamera(t) sind reine Funktionen von t. Kein `Math.random`, keine Uhr, kein Hochzählen zwischen Bildern. Zufall: `M.rng(seed)` im aufbau.
- `obj.visible = 0` gilt in Three.js als sichtbar. Immer Boolean: `obj.visible = u > 0`.
- Glänzende Böden (rau < 0,6) bekommen im Toon-Look einen harten Glanzfleck: Böden rau ≥ 0,8.
- Additive Leucht-Lagen summieren sich schnell zu Weiß: wenige Lagen, Stärke ≤ 0,8, dunkler Hintergrund dahinter.
- NaN im Shader gibt schwarze Blöcke im Bloom: `pow`-Basen mit `clamp` absichern.
- Ein Objekt, das „erscheint“, ist ab Bild 1 da und verwandelt sich auf dem Wort, statt in ein leeres Bild zu ploppen.
- Kamera wird VOR zustand gesetzt: im zustand ist `m.camera.position` schon die aktuelle (für zur Kamera gedrehte Blitze).
- Schnitte innerhalb einer Szene: Zeit einmal als Konstante, im Kamera-Wähler und in jeder Sichtbarkeit dieselbe Konstante. Letztes Bild vor und erstes Bild nach dem Schnitt prüfen.
- Ein Skriptfehler in EINER Szene rendert die ganze Seite leer. lint vor jedem Snapshot.
- Langsame Szene (über 1 s pro Bild im Snapshot): Schattenkarten verkleinern, mb aus, weniger Partikel, ao 0.

## Prüfen (beim Bauen, nicht erst am Ende)
0. `__HEIM__/ms szenen <folge> --check --lint --nur <id>` → kein Fehler zu deiner Szene, lint 0 Fehler (`ms snap` lintet zusätzlich vor jedem Bild).
1. `__HEIM__/ms snap <folge> --szene <id> --lokal 0 <T_1> <T_1+0.1> <T_2> … --name <bauer>_<id>_kern`: erstes Bild und jede Kernaktion + 0,1 s. Ansehen: Ist die Aktion im Bild? Trifft, was treffen soll? Objekt ganz im Bild, nicht verdeckt? Text lesbar?
2. `__HEIM__/ms snap <folge> --szene <id> --raster 0.25 --name <bauer>_<id>`: Bewegung flüssig, kein Stillstand über 1,5 s, kein Durchdringen, kein Objekt an einer seltsamen Stelle (Objekt genau hinter einem anderen wirkt wie ein Teil davon).
3. Endpose rendern statt glauben: Greifen, Stapeln, Treffen immer im Bild prüfen.
**Gate:** lint 0 Fehler, Kern-Snapshots und Raster angesehen, alle Punkte erledigt. Höchstens zwei Raster-Runden je Szene, danach nur noch die geänderte Stelle (`--lokal … --detail`). Nie `frame-*.png` in voller Größe öffnen.
Gibt es den Stil-Skill `__ARBEIT__/.claude/skills/stil-<k>/SKILL.md`, gelten Szenentyp, Bausteine mit Aufruf, Kamera, Licht und Abnahme-Kriterien von dort.

## Pilot (Nachbau)
Kamera am Original messen: Fluchtpunkte, Objektgröße im Bild → Abstand per Kamera-Mathe, fov schätzen. `__HEIM__/ms snap <folge> <zeiten> --gegen __ARBEIT__/folgen/<folge>/vorbild/ausschnitt.mp4` für Paar-Bilder (Original mit gleicher Zeitachse wie der Pilot).
Realistische Grenze aus unserem Nachbau: 3D erreichte ΔE76 16 (ΔE2000 ≈ 12), Hauptfehler waren Proportionen der Figuren, nicht ihre Lage. Proportionen zuerst messen.
