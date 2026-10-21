/* ms-global  ms2d.js: Start-Bibliothek für 2D-Szenen (HyperFrames + GSAP). Globales Objekt `MS2D`.
   "ms szenen" bindet Dateien mit "ms-global" in der ersten Zeile automatisch im Kopf von index.html ein.
   Alles ist seek-sicher: keine Uhr, kein Math.random, alle Bewegung liegt auf der pausierten GSAP-Timeline der Szene.
   Koordinaten: Bild 1080 × 1920 px. Zeiten: lokale Sekunden der Szene (0 = Szenenstart).

   Inhalt (Kurzfassung, Details an jeder Funktion)
     rng(seed)                         seek-sicherer Zufall (mulberry32), Zahlen 0..1
     div(eltern, css, html)            absolut positioniertes div
     bake(tl, el, fn, t0, t1, schritt) berechnete Bewegung Bild für Bild auf die Timeline legen
     schriftenLaden(liste)             Promise, vor dem Messen von Text abwarten
     textEinpassen(el, text, o)        Schriftgröße per measureText so wählen, dass der Text in die Breite passt
     wischFilter / wisch               horizontaler Wisch mit Bewegungsunschärfe (Szenen-Übergang)
     kameraLeben / kameraPunch         langsamer Push-in über die Szene / kurzer Zoom-Stoß auf einem Treffer
     wackeln                           abklingendes Kamerawackeln nach einem Aufprall
     staub / funken / sternSVG / konfetti   Partikel-Effekte (deterministisch)
     stempel / schlag                  Stempel-Element und Stempelschlag mit Nachfedern
     glanz                             Glanz-Wisch über ein Element (Wow auf Text/Karten)
     zaehler                           Zahl zählt hoch (Zählwerk)
     tippen                            Schreibmaschinen-Text
     linieZeichnen                     SVG-Pfad zeichnet sich
     papierFilter / konturFilter / rauFilter   SVG-Filter: ausgeschnittenes Papier, Kontur, raue Kante
     papierHintergrund                 Grundfarbe + optionale Textur + feines Druckraster
   Fallen: tl.set(el, …, 0) greift im allerersten Bild nicht sicher. Startzustände (opacity:0) ins CSS schreiben.
   Nach tl.set(el, {opacity: 1}) folgende fromTo mit immediateRender: false. */
(function () {
  const NS = 'http://www.w3.org/2000/svg';
  const MS2D = {};

  /* Seek-sicherer Zufall (mulberry32). const r = MS2D.rng(7); r() -> 0..1, immer dieselbe Folge pro seed. */
  MS2D.rng = function (seed) {
    let a = (seed >>> 0) || 1;
    return function () {
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  };

  /* Absolut positioniertes div. MS2D.div(root, 'left:100px;top:200px;width:300px;height:80px;', 'Text') */
  MS2D.div = function (eltern, css, html) {
    const d = document.createElement('div');
    d.style.cssText = 'position:absolute;' + (css || '');
    if (html != null) d.innerHTML = html;
    if (eltern) eltern.appendChild(d);
    return d;
  };

  /* Berechnete Bewegung: fn(t) liefert GSAP-Werte für die lokale Zeit t, gesetzt in jedem Bild (30 fps) von t0 bis t1.
     schritt 2 = "on twos" (jedes zweite Bild, Trickfilm-Gefühl). Seek-sicher, weil jeder Wert fest auf der Timeline liegt.
     Beispiel Hüpfen: MS2D.bake(tl, figur, (t) => ({ y: -Math.abs(Math.sin(t * 9)) * 40 }), 0.5, 1.8) */
  MS2D.bake = function (tl, el, fn, t0, t1, schritt) {
    const dt = (schritt || 1) / 30, n = Math.max(0, Math.round((t1 - t0) / dt));
    for (let i = 0; i <= n; i++) { const t = t0 + i * dt; tl.set(el, fn(t), +t.toFixed(4)); }
  };

  /* Schriften laden, bevor gemessen wird: await MS2D.schriftenLaden(['900 80px Montserrat', '400 60px "Archivo Black"']) */
  MS2D.schriftenLaden = function (liste) {
    return Promise.all((liste || []).map((f) => document.fonts.load(f).catch(() => null)));
  };

  /* Text einpassen: setzt font-size so, dass text in o.breite passt (höchstens o.groesse, mindestens o.min).
     o: { breite, groesse = 96, min = 24, gewicht = 900, familie = 'Montserrat', zeilen = 1 }. Gibt die Größe zurück.
     Bei zeilen > 1 wird die längste Zeile (Trennung an \n) gemessen. Nie Text über den Rand. */
  MS2D.textEinpassen = function (el, text, o = {}) {
    const c = MS2D._mc || (MS2D._mc = document.createElement('canvas'));
    const ctx = c.getContext('2d');
    const gew = o.gewicht || 900, fam = o.familie || 'Montserrat', max = o.groesse || 96, min = o.min || 24;
    const zeilen = String(text).split('\n');
    ctx.font = `${gew} ${max}px ${JSON.stringify(fam)}`;
    const breiteste = Math.max(...zeilen.map((z) => ctx.measureText(z).width), 1);
    const fs = Math.max(min, Math.min(max, Math.floor((max * o.breite) / breiteste)));
    if (el) {
      el.style.fontFamily = JSON.stringify(fam); el.style.fontWeight = gew; el.style.fontSize = fs + 'px';
      el.style.whiteSpace = zeilen.length > 1 ? 'pre' : 'nowrap';
      el.textContent = text;
    }
    return fs;
  };

  /* Wisch-Übergang. Einmal pro Szene: const blur = MS2D.wischFilter(root, ID + '-mb'); Ebene bekommt style filter:url(#ID-mb).
     MS2D.wisch(tl, ebene, blur, ID + '-mb', 0, { richtung: 'rein', dx: -300, dauer: 0.12 })
     richtung 'raus' am Szenenende: x von 0 nach dx mit zunehmender Unschärfe. */
  MS2D.wischFilter = function (eltern, id) {
    const s = document.createElementNS(NS, 'svg');
    s.setAttribute('width', '0'); s.setAttribute('height', '0'); s.style.position = 'absolute';
    s.innerHTML = `<filter id="${id}" x="-60%" y="-5%" width="220%" height="110%" color-interpolation-filters="sRGB"><feGaussianBlur stdDeviation="0 0"/></filter>`;
    eltern.appendChild(s);
    return s.querySelector('feGaussianBlur');
  };
  MS2D.wisch = function (tl, el, blurKnoten, id, at, o = {}) {
    const d = o.dauer || 0.12, b = o.blur || 22, dx = o.dx ?? -300;
    if (o.richtung === 'raus') {
      tl.set(el, { filter: `url(#${id})` }, at);
      tl.fromTo(el, { x: 0 }, { x: dx, duration: d, ease: 'power2.in', immediateRender: false }, at);
      tl.fromTo(blurKnoten, { attr: { stdDeviation: '0 0' } }, { attr: { stdDeviation: `${b} 1` }, duration: d, ease: 'power2.in', immediateRender: false }, at);
    } else {
      tl.fromTo(el, { x: dx }, { x: 0, duration: d, ease: 'power3.out' }, at);
      tl.fromTo(blurKnoten, { attr: { stdDeviation: `${b} 1` } }, { attr: { stdDeviation: '0 0' }, duration: d, ease: 'power3.out' }, at);
      tl.set(el, { filter: 'none' }, at + d);
    }
  };

  /* Szene lebt immer leicht: langsamer Push-in über die ganze Dauer. kamera = Ebene mit transform-origin (z. B. 540px 760px). */
  MS2D.kameraLeben = function (tl, kamera, dauer, o = {}) {
    tl.fromTo(kamera, { scale: o.von || 1 }, { scale: o.bis || 1.035, duration: dauer, ease: 'sine.inOut' }, 0);
  };

  /* Kamera-Punch auf einem Treffer: Zoom-Stoß und zurück. Arbeitet auf einer EIGENEN Ebene (nicht der von kameraLeben),
     sonst überschreiben sich die scale-Werte. o: { staerke = 1.12, rein = 0.08, raus = 0.3 } */
  MS2D.kameraPunch = function (tl, ebene, at, o = {}) {
    const s = o.staerke || 1.12;
    tl.fromTo(ebene, { scale: 1 }, { scale: s, duration: o.rein || 0.08, ease: 'power2.out', immediateRender: false }, at);
    tl.to(ebene, { scale: 1, duration: o.raus || 0.3, ease: 'power3.out' }, at + (o.rein || 0.08));
  };

  /* Abklingendes Wackeln nach einem Aufprall (Ebene zwischen Kamera und Inhalt). o: { staerke = 18 px, dauer = 0.35, frequenz = 38 } */
  MS2D.wackeln = function (tl, ebene, at, o = {}) {
    const st = o.staerke || 18, d = o.dauer || 0.35, f = o.frequenz || 38;
    MS2D.bake(tl, ebene, (t) => {
      const u = t - at, k = Math.exp(-u * (5 / d)) * st;
      return { x: Math.sin(u * f) * k, y: Math.cos(u * f * 1.3) * k * 0.6 };
    }, at, at + d);
    tl.set(ebene, { x: 0, y: 0 }, at + d + 1 / 30);
  };

  /* Staub-/Papier-Burst an (x, y). o: { seed, n = 12, farben, dist = 150, groesse = 1, dauer = 0.3, wolken = 3, fall = 28, bogen = 360 } */
  MS2D.staub = function (tl, eltern, x, y, at, o = {}) {
    const r = MS2D.rng(o.seed || 7), n = o.n || 12, cols = o.farben || ['#f3ead9', '#e4d6bd', '#17150f'];
    for (let i = 0; i < n; i++) {
      const s = (o.groesse || 1) * (5 + r() * 10), a = ((o.bogenStart || 0) + r() * (o.bogen ?? 360)) * Math.PI / 180;
      const d = (o.dist || 150) * (0.45 + r() * 0.75);
      const dx = Math.cos(a) * d, dy = Math.sin(a) * d * 0.55;
      const p = MS2D.div(eltern, `left:${x + (r() - 0.5) * 80}px;top:${y + (r() - 0.5) * 14}px;width:${s.toFixed(1)}px;height:${(s * (0.45 + r() * 0.6)).toFixed(1)}px;background:${cols[i % cols.length]};opacity:0;border-radius:${r() < 0.45 ? '50%' : '1px'};`);
      const dur = (o.dauer || 0.3) + r() * 0.18;
      tl.set(p, { opacity: 1 }, at);
      tl.to(p, { x: dx, y: dy + (o.fall ?? 28), rotation: (r() - 0.5) * 300, scale: 0.35, duration: dur, ease: 'power3.out' }, at);
      tl.to(p, { opacity: 0, duration: dur * 0.45, ease: 'power1.in' }, at + dur * 0.55);
    }
    for (let i = 0; i < (o.wolken ?? 3); i++) {
      const s = 70 + r() * 50, px = x + (i - 1) * 56;
      const p = MS2D.div(eltern, `left:${px - s / 2}px;top:${y - s / 2}px;width:${s}px;height:${s}px;border-radius:50%;background:radial-gradient(circle, rgba(243,234,217,.75) 0%, rgba(243,234,217,0) 70%);opacity:0;`);
      tl.set(p, { opacity: 0.9 }, at);
      tl.fromTo(p, { scale: 0.4 }, { scale: 1.5, x: (i - 1) * 40, y: -10, duration: 0.4, ease: 'power2.out', immediateRender: false }, at);
      tl.to(p, { opacity: 0, duration: 0.25 }, at + 0.15);
    }
  };

  /* Vierzackiger Funkelstern als SVG-String (Mitte im Ursprung des Eltern-Elements). */
  MS2D.sternSVG = function (r, farbe) {
    const k = r * 0.12;
    return `<svg width="${2 * r}" height="${2 * r}" viewBox="${-r} ${-r} ${2 * r} ${2 * r}" style="position:absolute;left:${-r}px;top:${-r}px;overflow:visible"><path d="M0 ${-r} Q${k} ${-k} ${r} 0 Q${k} ${k} 0 ${r} Q${-k} ${k} ${-r} 0 Q${-k} ${-k} 0 ${-r}Z" fill="${farbe}"/></svg>`;
  };

  /* Funkeln: punkte = [[x, y, radius, verzoegerung], …]. Ploppt auf und dreht weg. */
  MS2D.funken = function (tl, eltern, punkte, at, farbe) {
    punkte.forEach(([x, y, r, dl], i) => {
      const s = MS2D.div(eltern, `left:${x}px;top:${y}px;width:0;height:0;opacity:0;`, MS2D.sternSVG(r, farbe || '#ffd23f'));
      const t = at + (dl || 0);
      tl.set(s, { opacity: 1 }, t);
      tl.fromTo(s, { scale: 0, rotation: -40 }, { scale: 1.15, rotation: 10, duration: 0.12, ease: 'back.out(3)', immediateRender: false }, t);
      tl.to(s, { scale: 0, rotation: 60, duration: 0.16, ease: 'power2.in' }, t + 0.16 + i * 0.01);
    });
  };

  /* Konfetti-Explosion von (x, y): Schnipsel fliegen hoch, drehen, fallen mit Schwerkraft. Seek-sicher über bake.
     o: { seed, n = 40, farben, kraft = 900, schwerkraft = 2400, dauer = 1.4, breite = 14 } */
  MS2D.konfetti = function (tl, eltern, x, y, at, o = {}) {
    const r = MS2D.rng(o.seed || 11), n = o.n || 40, cols = o.farben || ['#ffd23f', '#ff5a5f', '#3ddc97', '#4ea8ff', '#ffffff'];
    const g = o.schwerkraft || 2400, dauer = o.dauer || 1.4;
    for (let i = 0; i < n; i++) {
      const w = (o.breite || 14) * (0.6 + r() * 0.8), h = w * (0.4 + r() * 0.5);
      const p = MS2D.div(eltern, `left:${x}px;top:${y}px;width:${w.toFixed(1)}px;height:${h.toFixed(1)}px;background:${cols[i % cols.length]};opacity:0;`);
      const a = (-90 + (r() - 0.5) * 110) * Math.PI / 180, v = (o.kraft || 900) * (0.55 + r() * 0.6);
      const vx = Math.cos(a) * v, vy = Math.sin(a) * v, spin = (r() - 0.5) * 1400, flat = 6 + r() * 10;
      tl.set(p, { opacity: 1 }, at);
      MS2D.bake(tl, p, (t) => {
        const u = t - at;
        return { x: vx * u, y: vy * u + 0.5 * g * u * u, rotation: spin * u, scaleY: Math.cos(u * flat), opacity: u > dauer * 0.75 ? Math.max(0, 1 - (u - dauer * 0.75) / (dauer * 0.25)) : 1 };
      }, at, at + dauer, 1);
    }
  };

  /* Stempel-Element (unsichtbar, bis MS2D.schlag es zeigt). o: { x, y (Mitte), farbe, groesse = 96, rot = -12, familie } */
  MS2D.stempel = function (eltern, text, o = {}) {
    const w = MS2D.div(eltern, `left:${o.x}px;top:${o.y}px;width:0;height:0;opacity:0;`);
    const s = document.createElement('div');
    const f = o.farbe || '#c33b2b';
    s.textContent = text;
    s.style.cssText = `position:absolute;left:0;top:0;white-space:nowrap;color:${f};border:10px solid ${f};font:900 ${o.groesse || 96}px ${JSON.stringify(o.familie || 'Montserrat')};letter-spacing:4px;padding:8px 26px;border-radius:14px;transform:translate(-50%,-50%) rotate(${o.rot ?? -12}deg);mix-blend-mode:multiply;opacity:.92;`;
    if (o.rau !== false) { MS2D.rauFilter(); s.style.filter = 'url(#ms2d-rau)'; }
    s.setAttribute('data-layout-allow-overlap', '');
    w.appendChild(s);
    return w;
  };
  /* Stempelschlag: groß und gedreht -> knallt auf, federt nach. Gibt die Aufprallzeit zurück (dort Staub/Ton/Punch). */
  MS2D.schlag = function (tl, w, at, o = {}) {
    const hit = at + (o.dauer || 0.08);
    tl.set(w, { opacity: 1 }, at);
    tl.fromTo(w, { scale: o.von || 1.6, rotation: -5 }, { scale: 1, rotation: 0, duration: hit - at, ease: 'power3.in', immediateRender: false }, at);
    tl.to(w, { keyframes: [{ rotation: 2.4, scale: 0.97, duration: 0.04 }, { rotation: -1.3, scale: 1.012, duration: 0.05 }, { rotation: 0, scale: 1, duration: 0.07 }], ease: 'none' }, hit);
    return hit;
  };

  /* Glanz-Wisch über ein Element (Element braucht position und overflow:hidden). o: { dauer = 0.45, breite = 160, farbe } */
  MS2D.glanz = function (tl, el, at, o = {}) {
    const b = o.breite || 160;
    const g = MS2D.div(el, `left:0;top:-20%;width:${b}px;height:140%;background:linear-gradient(100deg, rgba(255,255,255,0) 0%, ${o.farbe || 'rgba(255,255,255,0.75)'} 50%, rgba(255,255,255,0) 100%);transform:skewX(-18deg);mix-blend-mode:screen;opacity:0;pointer-events:none;`);
    tl.set(g, { opacity: 1 }, at);
    tl.fromTo(g, { x: -b * 1.5 }, { x: (el.offsetWidth || o.weite || 900) + b, duration: o.dauer || 0.45, ease: 'power2.inOut', immediateRender: false }, at);
    tl.set(g, { opacity: 0 }, at + (o.dauer || 0.45));
    return g;
  };

  /* Text seek-sicher setzen. GSAP liest zahlartige Texte als Zahl ("1.000" wird 1, "1.50" wird 1.5),
     deshalb steht ein unsichtbares Zeichen (U+200B) davor. */
  const TXT = (s) => '\u200b' + s;

  /* Zählwerk: Zahl läuft von von bis bis zwischen t0 und t1. format(z) -> Text, Standard ganze Zahl mit Tausenderpunkt. */
  MS2D.zaehler = function (tl, el, von, bis, t0, t1, format) {
    const fmt = format || ((z) => Math.round(z).toLocaleString('de-DE'));
    MS2D.bake(tl, el, (t) => {
      const u = Math.min(1, Math.max(0, (t - t0) / (t1 - t0))), e = 1 - Math.pow(1 - u, 3);
      return { textContent: TXT(fmt(von + (bis - von) * e)) };
    }, t0, t1);
  };

  /* Schreibmaschine: text erscheint Zeichen für Zeichen ab t0 mit zps Zeichen pro Sekunde. */
  MS2D.tippen = function (tl, el, text, t0, zps) {
    const n = text.length, d = n / (zps || 24);
    MS2D.bake(tl, el, (t) => ({ textContent: TXT(text.slice(0, Math.max(0, Math.min(n, Math.round((t - t0) / d * n))))) }), t0, t0 + d);
  };

  /* SVG-Pfad zeichnet sich zwischen t0 und t1 (Pfeile, Unterstreichungen, Kurven). */
  MS2D.linieZeichnen = function (tl, pfad, t0, t1, ease) {
    const L = pfad.getTotalLength ? pfad.getTotalLength() : 1000;
    pfad.style.strokeDasharray = `${L}`;
    pfad.style.strokeDashoffset = `${L}`;
    tl.fromTo(pfad, { strokeDashoffset: L }, { strokeDashoffset: 0, duration: t1 - t0, ease: ease || 'power2.inOut', immediateRender: false }, t0);
  };

  function filterSvg(id, inhalt) {
    if (document.getElementById(id)) return;
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('width', '0'); svg.setAttribute('height', '0'); svg.style.position = 'absolute';
    svg.innerHTML = inhalt;
    document.body.appendChild(svg);
  }

  /* Papier-Look: heller, leicht unregelmäßiger Rand + weicher Schatten. Benutzen: style="filter:url(#ms2d-papier)".
     Varianten #ms2d-papier-s (klein) und #ms2d-papier-l (groß). o: { rand = '#fbf7ee', schatten = '#08261d' } */
  MS2D.papierFilter = function (o = {}) {
    const mk = (id, r, dy, blur, a, seed) => `<filter id="${id}" x="-30%" y="-30%" width="160%" height="175%" color-interpolation-filters="sRGB">` +
      `<feMorphology in="SourceAlpha" operator="dilate" radius="${r}" result="d"/>` +
      `<feTurbulence type="fractalNoise" baseFrequency="0.045" numOctaves="2" seed="${seed}" result="n"/>` +
      `<feDisplacementMap in="d" in2="n" scale="${(r * 0.9).toFixed(1)}" xChannelSelector="R" yChannelSelector="G" result="dd"/>` +
      `<feFlood flood-color="${o.rand || '#fbf7ee'}" result="w"/><feComposite in="w" in2="dd" operator="in" result="rim"/>` +
      `<feGaussianBlur in="dd" stdDeviation="${blur}" result="b"/><feOffset in="b" dx="0" dy="${dy}" result="bo"/>` +
      `<feFlood flood-color="${o.schatten || '#08261d'}" flood-opacity="${a}" result="sc"/><feComposite in="sc" in2="bo" operator="in" result="sh"/>` +
      `<feMerge><feMergeNode in="sh"/><feMergeNode in="rim"/><feMergeNode in="SourceGraphic"/></feMerge></filter>`;
    filterSvg('ms2d-papier', mk('ms2d-papier', 7, 10, 7, 0.45, 5) + mk('ms2d-papier-s', 4, 6, 4, 0.42, 9) + mk('ms2d-papier-l', 10, 16, 11, 0.45, 13));
  };

  /* Kontur um beliebige Formen (Sticker-Rand, Comic-Linie). style="filter:url(#ms2d-kontur)". o: { farbe = '#111', breite = 6 } */
  MS2D.konturFilter = function (o = {}) {
    filterSvg('ms2d-kontur', `<filter id="ms2d-kontur" x="-20%" y="-20%" width="140%" height="140%"><feMorphology in="SourceAlpha" operator="dilate" radius="${o.breite || 6}" result="d"/>` +
      `<feFlood flood-color="${o.farbe || '#111111'}" result="f"/><feComposite in="f" in2="d" operator="in" result="k"/><feMerge><feMergeNode in="k"/><feMergeNode in="SourceGraphic"/></feMerge></filter>`);
  };

  /* Raue Druck-/Stempelkante. style="filter:url(#ms2d-rau)". */
  MS2D.rauFilter = function () {
    filterSvg('ms2d-rau', '<filter id="ms2d-rau"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7"/><feDisplacementMap in="SourceGraphic" scale="6"/></filter>');
  };

  /* Hintergrund: Farbe + optionale Textur (o.textur = 'assets/tex/papier.png', multiply) + feines Druckraster (o.raster 0..0.3). */
  MS2D.papierHintergrund = function (el, farbe, o = {}) {
    el.style.background = farbe || '#f3ead9';
    if (o.textur) MS2D.div(el, `inset:0;background:url(${o.textur}) center/cover;mix-blend-mode:multiply;opacity:${o.texturStaerke ?? 0.55};pointer-events:none`);
    if ((o.raster ?? 0.1) > 0) MS2D.div(el, `inset:0;background-image:radial-gradient(rgba(23,21,15,${o.raster ?? 0.1}) 1.1px, transparent 1.4px);background-size:7px 7px;mix-blend-mode:multiply;pointer-events:none`);
  };

  window.MS2D = MS2D;
})();
