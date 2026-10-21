/* ms-global  ms3d-start.js: verbindet eine Three.js-Szene mit HyperFrames. Globale Funktion ms3dSzene(o).
   "ms szenen" bindet diese Datei automatisch im Kopf von index.html ein (Markierung ms-global in Zeile 1).
   Macht synchron, was HyperFrames sofort braucht: pausierte Timeline registrieren, buildReady-Versprechen, hf-seek-Hörer.
   Dann lädt es ms3d.js (ES-Modul) und baut die Szene. Für ms3d.js braucht die Szene kein eigenes import(). Weitere Module
   (three/addons, Kanal-Kit assets/lib/<kanal>3d.js) nur im aufbau mit await import(…) laden, nie statisch oben im Skript
   (doppelte Namen = Syntaxfehler, der die GANZE Seite leer rendert) und nie in zustand/kamera/post (pro Bild, seek-sicher).

   const tl = ms3dSzene({
     id: "s2", dauer: 2.5,                       // = data-composition-id und data-duration der Szene
     canvas: "s2-canvas",                        // id des <canvas width="1080" height="1920">
     hintergrund: "#14181f", fov: 40, toon: true, // toon: alle Standard-Materialien als Cel-Shading
     schriften: ["900 100px Montserrat"],         // vor dem Aufbau laden (für Text-Texturen)
     aufbau: async (M, m) => { ... return welt; },   // einmal: Set, Licht, Requisiten. M = ms3d-Modul, m = motor
     zustand: (t, welt, M, m) => { ... },         // pro Bild: alles als reine Funktion der lokalen Zeit t
     kamera: (t, welt, M, m) => ({ pos: [0, 1.6, 5], ziel: [0, 1, 0], fov: 40 }),
     post: (t, welt, M, m) => ({ bloom: 0.35 }),  // optional, Werte siehe M.POST
   });
   Rückgabe tl: die GSAP-Timeline der Szene. Darauf dürfen 2D-Ebenen (Titel, Wisch-Übergang) über dem Canvas animiert werden.
   Der globale Start der Szene wird aus index.html gelesen (data-start des Szenen-Elements), o.start nur zum Testen. */
(function () {
  window.ms3dSzene = function (o) {
    const ID = o.id, D = o.dauer;
    const tl = gsap.timeline({ paused: true });
    tl.set({}, {}, D);
    window.__timelines[ID] = tl;
    window.__hf = window.__hf || {};
    window.__hf.buildReady = window.__hf.buildReady || {};
    const start = () => {
      if (typeof o.start === 'number') return o.start;
      const host = document.querySelector(`[data-composition-id="${ID}"][data-start]`);
      return host ? parseFloat(host.getAttribute('data-start')) || 0 : 0;
    };
    let render = null;
    const lib = new URL(o.lib || 'assets/lib/ms3d.js', document.baseURI).href;
    const bereit = import(lib).then((M) => M.szeneBauen(o, start)).then((r) => {
      render = r;
      render(typeof window.__hfThreeTime === 'number' ? window.__hfThreeTime : start());
    }).catch((e) => { console.error(`ms3d Szene ${ID}:`, e); throw e; });
    window.__hf.buildReady[ID] = bereit;
    window.addEventListener('hf-seek', (e) => {
      const t = e.detail.time, s = start();
      if (t < s - 0.05 || t > s + D + 0.05) return;
      if (render) render(t); else e.detail.waitUntil(bereit.then(() => render(t)));
    });
    return tl;
  };
})();
