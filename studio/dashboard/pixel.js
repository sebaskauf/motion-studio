// Pixel-Crew für STUDIO (Sebastian 22.10.2026: „welcher Agent gerade was macht, mit pixeligen Animationen“).
// Jede Figur ist ein kleiner Clawd (32 × 28 Pixel) mit Rollen-Zubehör. Die Tätigkeit bestimmt Requisite und Bewegung.
// Ein gemeinsamer Takt (8 Bilder/s) zeichnet nur sichtbare Figuren neu, pausiert bei verdecktem Tab,
// und bei „weniger Bewegung“ bleibt jede Figur ein Standbild (DESIGN.md, Abschnitt Pixel-Crew).
'use strict';
(() => {
  const W = 32, H = 28;
  const RUHIG = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const P = {
    k: '#d97757', kl: '#ec9a77', kd: '#b45a3c', auge: '#20150f', schatten: 'rgba(0,0,0,.28)',
    papier: '#f4efe4', papier2: '#d9d1c1', holz: '#8b5a2b', metall: '#a3abb5', metall2: '#6b7380', dunkel: '#23201c',
    akzent: '#ff6b1a', gruen: '#4ade80', blau: '#60a5fa', gelb: '#f2c14e', gelb2: '#c9932a', rot: '#d64545', lila: '#a78bfa',
  };
  // Zubehör je Figur (immer sichtbar) und Lieblings-Requisite bei „arbeitet“
  const FIGUR = {
    regie: { hut: 'barett', farbe: '#2d2a32', prop: 'klappe', name: 'Regie' },
    zwei_d: { hut: 'malerkappe', farbe: P.rot, prop: 'pinsel', name: '2D' },
    bauer: { hut: 'helm', farbe: P.gelb, prop: 'hammer', name: 'Bauer' },
    pruefer: { hut: 'brille', farbe: '#e8e2d6', prop: 'lupe', name: 'Prüfer' },
    analyse: { hut: 'muetze', farbe: '#1e3a5f', prop: 'diagramm', name: 'Analyse', brille: true },
    guide: { hut: 'entdecker', farbe: '#2f7d4f', prop: 'buch', name: 'Guide' },
    ceo: { hut: 'krawatte', farbe: '#b91c1c', prop: 'tasse', name: 'CEO' },
    autopilot: { hut: 'antenne', farbe: P.gruen, prop: 'zahnrad', name: 'Autopilot' },
    stimme: { hut: 'kopfhoerer', farbe: '#3b4252', prop: 'mikro', name: 'Stimme' },
    ton: { hut: 'kopfhoerer', farbe: '#4b3b5c', prop: 'eq', name: 'Ton' },
  };
  // Tätigkeit → Requisite (null = Lieblings-Requisite der Figur)
  const REQUISITE = {
    arbeitet: null, schreibt: 'stift', plant: 'stift', lernt: 'buch', liest: 'buch', sucht: 'lupe', recherchiert: 'lupe',
    rendert: 'filmrolle', stimme: 'mikro', ton: 'eq', hoert: 'eq', werkzeug: 'laptop', delegiert: 'megafon',
  };

  const r = (c, x, y, w, h, f) => { c.fillStyle = f; c.fillRect(x, y, w, h); };
  const welle = (t, n) => Math.floor(t / n) % 2;

  function koerper(c, dy, augen, armHoch, blick) {
    r(c, 8, 25, 16, 1, P.schatten);
    for (const x of [10, 13, 17, 20]) r(c, x, 22 + dy, 2, 3 - dy, P.kd);
    r(c, 8, 13 + dy, 16, 9, P.k);
    r(c, 8, 13 + dy, 16, 1, P.kl);
    r(c, 8, 21 + dy, 16, 1, P.kd);
    r(c, 23, 14 + dy, 1, 7, P.kd);
    r(c, 6, 16 + dy, 2, 2, P.k);
    if (armHoch) { r(c, 24, 9 + dy, 2, 7, P.k); r(c, 24, 9 + dy, 2, 1, P.kl); } else r(c, 24, 16 + dy, 2, 2, P.k);
    const bx = blick || 0;
    for (const ex of [12 + bx, 18 + bx]) {
      if (augen === 'zu') r(c, ex, 17 + dy, 2, 1, P.auge);
      else if (augen === 'froh') { r(c, ex, 15 + dy, 2, 1, P.auge); r(c, ex - 1, 16 + dy, 1, 1, P.auge); r(c, ex + 2, 16 + dy, 1, 1, P.auge); }
      else if (augen === 'x') { r(c, ex - 1, 15 + dy, 1, 1, P.auge); r(c, ex + 1, 15 + dy, 1, 1, P.auge); r(c, ex, 16 + dy, 1, 1, P.auge); r(c, ex - 1, 17 + dy, 1, 1, P.auge); r(c, ex + 1, 17 + dy, 1, 1, P.auge); }
      else r(c, ex, 15 + dy, 2, 3, P.auge);
    }
  }

  function zubehoer(c, f, dy, an) {
    const z = FIGUR[f] || FIGUR.regie;
    const g = z.farbe;
    if (z.hut === 'barett') { r(c, 9, 11 + dy, 11, 2, g); r(c, 17, 10 + dy, 4, 1, g); r(c, 13, 10 + dy, 1, 1, g); }
    else if (z.hut === 'malerkappe') { r(c, 8, 11 + dy, 12, 2, g); r(c, 18, 10 + dy, 4, 2, g); r(c, 10, 11 + dy, 3, 1, '#ef7a7a'); }
    else if (z.hut === 'helm') { r(c, 9, 10 + dy, 14, 3, g); r(c, 7, 12 + dy, 18, 1, P.gelb2); r(c, 11, 10 + dy, 4, 1, '#f8d77a'); r(c, 15, 9 + dy, 2, 1, g); }
    else if (z.hut === 'muetze') { r(c, 9, 10 + dy, 14, 3, g); r(c, 9, 12 + dy, 14, 1, '#2c5282'); r(c, 15, 9 + dy, 2, 1, '#9ab6d8'); }
    else if (z.hut === 'entdecker') { r(c, 10, 10 + dy, 12, 2, g); r(c, 7, 12 + dy, 18, 1, '#245f3c'); r(c, 10, 11 + dy, 12, 1, '#c9a86a'); }
    else if (z.hut === 'krawatte') { r(c, 15, 18 + dy, 2, 1, g); r(c, 15, 19 + dy, 2, 2, '#991b1b'); r(c, 15, 21 + dy, 2, 1, '#7f1515'); r(c, 9, 12 + dy, 14, 1, '#2a1f1a'); }
    else if (z.hut === 'antenne') { r(c, 15, 9 + dy, 1, 4, P.metall); r(c, 14, 7 + dy, 3, 2, an === false ? '#8b877f' : g); }
    else if (z.hut === 'kopfhoerer') { r(c, 9, 11 + dy, 14, 1, g); r(c, 8, 12 + dy, 1, 2, g); r(c, 23, 12 + dy, 1, 2, g); r(c, 6, 14 + dy, 2, 4, g); r(c, 24, 14 + dy, 2, 4, g); }
    if (z.hut === 'brille' || z.brille) {
      const fr = z.hut === 'brille' ? g : '#e8e2d6';
      for (const ex of [12, 18]) { r(c, ex - 1, 14 + dy, 4, 1, fr); r(c, ex - 1, 18 + dy, 4, 1, fr); r(c, ex - 1, 14 + dy, 1, 5, fr); r(c, ex + 2, 14 + dy, 1, 5, fr); }
      r(c, 15, 15 + dy, 2, 1, fr);
    }
  }

  // Requisiten rechts neben der Figur (x 24–31), t = Bildnummer
  function requisite(c, art, t, dy) {
    if (art === 'klappe') {
      r(c, 25, 18, 6, 5, P.dunkel); r(c, 26, 19, 1, 3, P.papier); r(c, 28, 19, 1, 3, P.papier); r(c, 30, 19, 1, 3, P.papier);
      if (welle(t, 2)) { r(c, 25, 16, 6, 1, P.papier); r(c, 25, 17, 6, 1, P.dunkel); } else { r(c, 25, 14, 2, 1, P.papier); r(c, 27, 15, 2, 1, P.papier); r(c, 29, 16, 2, 1, P.papier); }
    } else if (art === 'hammer') {
      r(c, 27, 22, 4, 3, '#7a6a58'); r(c, 27, 22, 4, 1, '#9b8a76');
      if (welle(t, 2)) { r(c, 26, 12, 1, 6, P.holz); r(c, 25, 10, 3, 2, P.metall2); }
      else { r(c, 26, 17, 4, 1, P.holz); r(c, 29, 19, 2, 3, P.metall2); r(c, 31, 20, 1, 1, P.gelb); r(c, 26, 21, 1, 1, P.gelb); }
    } else if (art === 'pinsel') {
      r(c, 26, 11, 6, 9, P.papier); r(c, 26, 20, 1, 4, P.holz); r(c, 31, 20, 1, 4, P.holz);
      const farben = [P.rot, P.blau, P.gelb, P.gruen];
      for (let i = 0; i <= t % 8; i++) r(c, 27 + (i % 4), 12 + Math.floor(i / 4) * 3, 1, 2, farben[i % 4]);
      r(c, 25 - (t % 2), 14, 1, 4, P.holz); r(c, 25 - (t % 2), 13, 1, 1, farben[t % 4]);
    } else if (art === 'lupe') {
      const pos = [[19, 13], [21, 12], [19, 11], [17, 12]][t % 4];
      const [x, y] = pos;
      r(c, x, y, 5, 1, P.metall); r(c, x, y + 4, 5, 1, P.metall); r(c, x, y, 1, 5, P.metall); r(c, x + 4, y, 1, 5, P.metall);
      c.fillStyle = 'rgba(191,227,255,.45)'; c.fillRect(x + 1, y + 1, 3, 3);
      r(c, x + 1, y + 1, 1, 1, '#ffffff'); r(c, x + 5, y + 5, 1, 1, P.holz); r(c, x + 6, y + 6, 1, 1, P.holz);
    } else if (art === 'diagramm') {
      r(c, 25, 12, 7, 11, P.papier); r(c, 25, 22, 7, 1, P.papier2);
      const hoehe = [3 + (t % 3), 5 + ((t + 1) % 4), 7 + ((t + 2) % 3)];
      [P.blau, P.gelb, P.gruen].forEach((f, i) => r(c, 26 + i * 2, 22 - hoehe[i], 1, hoehe[i], f));
    } else if (art === 'buch') {
      r(c, 10, 19 + dy, 12, 5, P.papier); r(c, 15, 19 + dy, 2, 5, P.papier2); r(c, 9, 23 + dy, 14, 1, '#2f6fdb');
      for (let i = 0; i < 3; i++) { r(c, 11, 20 + dy + i, 3, 1, P.papier2); r(c, 18, 20 + dy + i, 3, 1, P.papier2); }
      const s = t % 4; if (s < 2) r(c, 15 + (s ? 2 : -2), 18 + dy, 2, 5, '#fffaf0');
    } else if (art === 'tasse') {
      r(c, 26, 17, 4, 4, P.papier); r(c, 30, 18, 1, 2, P.papier); r(c, 26, 17, 4, 1, '#6b3e26');
      const s = t % 4; c.fillStyle = '#a39e96';
      c.fillRect(27 + (s % 2), 14 - (s >> 1), 1, 2); c.fillRect(28 - (s % 2), 12 - (s >> 1), 1, 2);
    } else if (art === 'zahnrad') {
      const x = 26, y = 15, f = t % 2;
      r(c, x + 1, y + 1, 4, 4, P.metall); r(c, x + 2, y + 2, 2, 2, P.metall2);
      if (f) { r(c, x + 2, y, 2, 1, P.metall); r(c, x + 2, y + 5, 2, 1, P.metall); r(c, x, y + 2, 1, 2, P.metall); r(c, x + 5, y + 2, 1, 2, P.metall); }
      else { r(c, x, y, 1, 1, P.metall); r(c, x + 5, y, 1, 1, P.metall); r(c, x, y + 5, 1, 1, P.metall); r(c, x + 5, y + 5, 1, 1, P.metall); }
    } else if (art === 'mikro') {
      r(c, 27, 13, 2, 3, P.metall); r(c, 27, 13, 2, 1, '#ffffff'); r(c, 28, 16, 1, 7, P.metall2); r(c, 26, 23, 4, 1, P.metall2);
      const n = t % 4; c.fillStyle = 'rgba(255,107,26,.85)';
      for (let i = 0; i < n; i++) { c.fillRect(30 + i, 13 - i, 1, 1); c.fillRect(30 + i, 15 + i, 1, 1); c.fillRect(31 + i, 14, 1, 1); }
    } else if (art === 'eq') {
      const hoehe = [2 + (t * 3) % 5, 4 + (t * 5) % 4, 1 + (t * 7) % 6, 3 + (t * 2) % 5];
      hoehe.forEach((h, i) => r(c, 25 + i * 2, 23 - h, 1, h, i % 2 ? P.akzent : P.gelb));
    } else if (art === 'stift') {
      r(c, 25, 17, 6, 7, P.papier);
      for (let i = 0; i < Math.min(3, (t % 6) + 1); i++) r(c, 26, 18 + i * 2, 1 + ((t + i) % 4), 1, P.papier2);
      const x = 26 + (t % 4); r(c, x, 13, 1, 4, P.gelb); r(c, x, 17, 1, 1, P.dunkel);
    } else if (art === 'filmrolle') {
      const x = 25, y = 13;
      r(c, x + 1, y, 5, 7, P.metall2); r(c, x, y + 1, 7, 5, P.metall2); r(c, x + 2, y + 2, 3, 3, P.dunkel);
      const loch = [[x + 1, y + 1], [x + 5, y + 1], [x + 5, y + 5], [x + 1, y + 5]][t % 4];
      r(c, loch[0], loch[1], 1, 1, P.dunkel); r(c, x + 3, y + 3, 1, 1, P.metall);
      r(c, x + 3, y + 7, 1, 3, P.dunkel); r(c, x + 1, y + 10, 6, 2, P.dunkel); r(c, x + 2 + (t % 2) * 2, y + 10, 1, 1, P.papier);
    } else if (art === 'laptop') {
      r(c, 9, 17 + dy, 14, 6, '#1f2937'); r(c, 8, 23 + dy, 16, 1, P.metall2);
      for (let i = 0; i < 3; i++) r(c, 10, 18 + dy + i * 2, 2 + ((t + i * 3) % 9), 1, i === 1 ? P.gruen : '#93c5fd');
    } else if (art === 'megafon') {
      r(c, 25, 15, 2, 3, P.papier2); r(c, 27, 14, 2, 5, P.papier); r(c, 29, 13, 1, 7, P.papier);
      const n = 1 + (t % 3); c.fillStyle = 'rgba(255,107,26,.85)';
      for (let i = 0; i < n; i++) c.fillRect(30 + i, 15 + (i % 2 ? -1 : 1) * 0, 1, 3);
    }
  }

  // Sprechblase mit dunklem Rand: auf hellem und dunklem Grund lesbar
  function kasten(c, x, y, w, h) { r(c, x - 1, y, w + 2, h, '#3a332d'); r(c, x, y - 1, w, h + 2, '#3a332d'); r(c, x, y, w, h, '#f4efe4'); }
  function blase(c, t, art) {
    if (art === 'fragt') {
      const dy = welle(t, 3) ? 1 : 2;
      kasten(c, 24, dy, 7, 8); r(c, 25, 8 + dy, 2, 1, '#3a332d');
      r(c, 26, 1 + dy, 3, 1, P.akzent); r(c, 29, 2 + dy, 1, 2, P.akzent); r(c, 28, 4 + dy, 1, 1, P.akzent); r(c, 27, 5 + dy, 1, 1, P.akzent); r(c, 27, 7 + dy, 1, 1, P.akzent);
    } else if (art === 'denkt') {
      r(c, 22, 10, 1, 1, '#8b877f'); r(c, 23, 8, 2, 1, '#8b877f'); kasten(c, 24, 1, 7, 5);
      const n = t % 4;
      for (let i = 0; i < 3; i++) r(c, 25 + i * 2, 3, 1, 1, i < n ? P.dunkel : '#cfc6b4');
    } else if (art === 'fehler') {
      const s = t % 4; c.fillStyle = 'rgba(160,155,148,.8)';
      c.fillRect(12 + s, 8 - s, 3, 2); c.fillRect(17 - s, 6 - (s >> 1), 2, 2); c.fillRect(14, 4 - (s % 2), 2, 1);
      r(c, 7, 13, 1, 2, P.blau);
    } else if (art === 'schlaeft') {
      const s = t % 6; c.fillStyle = '#8b877f';
      const z = (x, y, k) => { c.fillRect(x, y, k, 1); c.fillRect(x + k - 2, y + 1, 1, 1); c.fillRect(x, y + 2, k, 1); };
      z(24 + (s >> 1), 8 - s, 3); if (s > 2) z(27, 3 - (s - 3), 4);
    } else if (art === 'fertig') {
      kasten(c, 25, 2, 6, 6); r(c, 26, 5, 1, 1, '#1a7f5a'); r(c, 27, 6, 1, 1, '#1a7f5a'); r(c, 28, 5, 1, 1, '#1a7f5a'); r(c, 29, 4, 1, 1, '#1a7f5a'); r(c, 30, 3, 1, 1, '#1a7f5a');
    }
  }

  // Ein Bild der Figur: figur (FIGUR-Schlüssel), art (Tätigkeit), t (Bildnummer)
  function bild(c, figur, art, t, an) {
    c.clearRect(0, 0, W, H);
    const langsam = art === 'schlaeft' || art === 'wartet' || art === 'beendet';
    const dy = RUHIG ? 0 : (langsam ? (Math.floor(t / 6) % 2 ? -1 : 0) : (welle(t, 2) ? -1 : 0));
    const blinzeln = !RUHIG && t % 29 === 0;
    const augen = art === 'schlaeft' || art === 'beendet' || blinzeln ? 'zu' : art === 'fehler' ? 'x' : art === 'fertig' ? 'froh' : 'offen';
    const blick = art === 'wartet' && !RUHIG ? [0, 0, 0, -1, -1, 0, 0, 1, 1, 0][Math.floor(t / 4) % 10] : 0;
    koerper(c, dy, augen, art === 'fragt', blick);
    zubehoer(c, figur, dy, an);
    if (art in REQUISITE) requisite(c, REQUISITE[art] || (FIGUR[figur] || FIGUR.regie).prop, t, dy);
    blase(c, t, art);
  }

  // ---------------------------------------------------------------- Takt für alle Figuren
  const FIGUREN = new Set();
  let takt = 0;
  function zeichneAlle() {
    for (const cv of FIGUREN) {
      if (!cv.isConnected) { FIGUREN.delete(cv); continue; }
      if (!cv.offsetParent) continue;
      const o = cv._px;
      bild(cv._ctx, o.figur, o.art, takt + o.versatz, o.an);
    }
  }
  if (!RUHIG) setInterval(() => { if (!document.hidden) { takt++; zeichneAlle(); } }, 125);

  function figur(cv, opts) {
    if (!cv._ctx) {
      cv.width = W; cv.height = H;
      cv._ctx = cv.getContext('2d');
      cv._ctx.imageSmoothingEnabled = false;
      cv.setAttribute('role', 'img');
      FIGUREN.add(cv);
    }
    const alt = cv._px || {};
    cv._px = { figur: opts.figur || 'regie', art: opts.art || 'wartet', an: opts.an,
               versatz: alt.versatz ?? Math.floor(Math.random() * 40) };
    if (opts.label) cv.setAttribute('aria-label', opts.label);
    if (alt.figur !== cv._px.figur || alt.art !== cv._px.art || RUHIG) bild(cv._ctx, cv._px.figur, cv._px.art, takt + cv._px.versatz, cv._px.an);
  }

  // ---------------------------------------------------------------- Ruhige Szene für die Info-Karte (Hover)
  // Figur schwebt langsam auf einem Kissen, Staubkörnchen steigen auf, die Requisite läuft gemächlich.
  function szene(cv, opts) {
    const SW = 64, SH = 40;
    cv.width = SW; cv.height = SH;
    const c = cv.getContext('2d');
    c.imageSmoothingEnabled = false;
    const puffer = document.createElement('canvas');
    puffer.width = W; puffer.height = H;
    const pc = puffer.getContext('2d');
    const css = getComputedStyle(document.documentElement);
    const grund = css.getPropertyValue('--panel-2').trim() || '#181614';
    const linie = css.getPropertyValue('--line-2').trim() || '#302c28';
    const farbe = (FIGUR[opts.figur] || FIGUR.regie).farbe;
    const koerner = Array.from({ length: 9 }, (_, i) => ({ x: (i * 7 + 5) % SW, y: (i * 13) % SH, v: 0.12 + (i % 3) * 0.05, p: i }));
    let t = 0, lauf = true, letzt = 0;
    function schritt(zeit) {
      if (!lauf) return;
      if (zeit - letzt > 80 || RUHIG) {
        letzt = zeit; t++;
        c.fillStyle = grund; c.fillRect(0, 0, SW, SH);
        c.fillStyle = linie; c.fillRect(6, 35, SW - 12, 1);
        for (const k of koerner) {
          if (!RUHIG) { k.y -= k.v; if (k.y < 0) { k.y = SH; k.x = (k.x + 23) % SW; } }
          c.globalAlpha = 0.25 + 0.35 * Math.abs(Math.sin((t + k.p * 9) / 14));
          c.fillStyle = k.p % 3 ? farbe : '#f4efe4';
          c.fillRect(Math.round(k.x + Math.sin((t + k.p * 5) / 18) * 1.5), Math.round(k.y), 1, 1);
        }
        c.globalAlpha = 1;
        const schweben = RUHIG ? 0 : Math.round(Math.sin(t / 16) * 1.5);
        c.fillStyle = 'rgba(0,0,0,.22)'; c.fillRect(22 - (schweben < 0 ? 1 : 0), 35, 20 + (schweben < 0 ? 2 : 0), 1);
        c.fillStyle = '#3a332d'; c.fillRect(21, 33, 22, 2); c.fillStyle = farbe; c.fillRect(22, 32, 20, 1);
        bild(pc, opts.figur, opts.art || 'arbeitet', Math.floor(t / 2), opts.an);
        c.drawImage(puffer, 16, 6 + schweben);
      }
      if (!RUHIG) requestAnimationFrame(schritt);
    }
    requestAnimationFrame(schritt);
    return () => { lauf = false; };
  }

  window.PixelCrew = { figur, szene, FIGUR, ARTEN: Object.keys(REQUISITE).concat(['denkt', 'fragt', 'wartet', 'fehler', 'schlaeft', 'fertig', 'beendet']) };
})();
