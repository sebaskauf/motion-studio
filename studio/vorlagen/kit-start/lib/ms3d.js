/* ms3d.js: Start-Bibliothek für 3D-Szenen (Three.js in HyperFrames), ES-Modul.
   Laden NICHT selbst: die Szene ruft ms3dSzene({...}) aus ms3d-start.js auf, das lädt dieses Modul und reicht es als M weiter.
   "three" kommt über die Import-Map in index.html (ms szenen schreibt sie: lokale Kopie oder jsDelivr three@0.181.2).

   Welt: y oben, Boden y = 0, Meter. Kamera hochkant 1080 × 1920, fov 40 (vertikal).
   KAMERA-MATHE: sichtbare halbe Breite ≈ 0,205 × Abstand (fov 40 hochkant), halbe Höhe ≈ 0,364 × Abstand.
     Bei 5 m Abstand sind also nur ±1,0 m in der Breite sichtbar. Alles Wichtige in dieses Fenster legen.
     M.halbeBreite(abstand, fov), M.abstandFuerBreite(halbeBreite, fov) rechnen das genau.
   SEEK-SICHER: zustand(t) und kamera(t) sind reine Funktionen der lokalen Zeit t. Kein Math.random, keine Uhr,
     keine Zustände zwischen Bildern. Zufall nur über M.rng(seed) im aufbau.

   Inhalt
     THREE, FPS, rng, clamp, lerp, smooth, win, ease.*         Mathe und Kurven
     halbeBreite, halbeHoehe, abstandFuerBreite                Kamera-Mathe
     motor({canvas, fov, hintergrund})                         Renderer 1080×1920 + Post (DOF, Bloom, AO, AgX, Korn, Bewegungsunschärfe)
     POST                                                      Standard-Post-Werte (pro Bild überschreibbar)
     licht(scene, preset, o)                                   Licht-Presets: studio | abend | buehne | tag
     materialPBR(farbe, o) / materialToon(farbe, o) / toonAlle(scene) / leuchtend(farbe, staerke)
     kiste(eltern, b, h, t, material, x, y, z, o)              (abgerundete) Box mit Schatten
     leinwand(b, h, zeichne, o) / textTextur(text, o)          Canvas-Texturen, Text per measureText eingepasst
     kamerafahrt({sek: {pos, ziel, fov}}) -> fn(t)             weiche Kamerafahrt (Catmull-Rom) als Funktion der Zeit
     orbit(o) -> fn(t)                                         Kreisfahrt um ein Ziel
     schuettel(t, t0, staerke, abkling)                        Kamerastoß-Offset nach einem Treffer
     blitz(o) / blitzZeigen(mesh, t, T, o)                     Treffer-Blitz (Stern, additiv) zur Kamera gedreht
     funkenWolke(scene, o) -> {add(pos, t0, opt), update(t)}   Funken + Rauchwolke (deterministisch)
     konfetti(scene, o) -> {add(pos, t0, opt), update(t)}      Konfetti-Explosion mit Schwerkraft
     portalFahrt(flaeche, von, t0, t1, o) -> fn(t)             Übergang: Kamera fährt in eine Fläche, bis sie das Bild füllt
     fuellAbstand(breite, hoehe, fov)                          Abstand, bei dem eine Fläche das Hochkant-Bild füllt
     szeneBauen(o, startFn)                                    (intern, benutzt von ms3d-start.js) */
import * as THREE from 'three';
export { THREE };

/* ------------------------------------------------------------------ Mathe */
export const FPS = 30;
export function rng(seed) {
  let a = (seed >>> 0) || 1;
  return function () {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
export const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const smooth = (t) => { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); };
/* Fortschritt 0..1 zwischen den Zeiten a und b (vorher 0, danach 1). */
export const win = (t, a, b) => clamp((t - a) / (b - a), 0, 1);
export const ease = {
  linear: (t) => t,
  inQuad: (t) => t * t,
  outQuad: (t) => 1 - (1 - t) * (1 - t),
  inOutQuad: (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2),
  inCubic: (t) => t * t * t,
  outCubic: (t) => 1 - Math.pow(1 - clamp(t, 0, 1), 3),
  inOutCubic: (t) => { t = clamp(t, 0, 1); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; },
  outBack: (t, s = 1.70158) => { t = clamp(t, 0, 1); return 1 + (s + 1) * Math.pow(t - 1, 3) + s * Math.pow(t - 1, 2); },
  outExpo: (t) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t)),
  inOutSine: (t) => -(Math.cos(Math.PI * clamp(t, 0, 1)) - 1) / 2,
};
export function frameOf(t) { return Math.floor(t * FPS + 0.02); }

/* ------------------------------------------------------------------ Kamera-Mathe (hochkant 1080 × 1920) */
const ASPEKT = 1080 / 1920;
/* Sichtbare halbe Breite in Metern bei diesem Abstand (fov vertikal in Grad). fov 40: ≈ 0,205 × Abstand. */
export function halbeBreite(abstand, fov = 40, aspekt = ASPEKT) { return abstand * Math.tan((fov * Math.PI) / 360) * aspekt; }
export function halbeHoehe(abstand, fov = 40) { return abstand * Math.tan((fov * Math.PI) / 360); }
/* Abstand, bei dem genau ±halbeB Meter in die Breite passen. */
export function abstandFuerBreite(halbeB, fov = 40, aspekt = ASPEKT) { return halbeB / (Math.tan((fov * Math.PI) / 360) * aspekt); }
/* Abstand, bei dem eine Fläche b × h das Bild komplett füllt (kein Rand sichtbar). */
export function fuellAbstand(b, h, fov = 40, aspekt = ASPEKT) { return Math.min(abstandFuerBreite(b / 2, fov, aspekt), (h / 2) / Math.tan((fov * Math.PI) / 360)); }

/* ------------------------------------------------------------------ Texturen */
const TEXCACHE = new Map();
/* Canvas-Textur: zeichne(ctx, b, h). o: { key (Cache), srgb = true, klemmen, wiederholen: [x, y] } */
export function leinwand(b, h, zeichne, o = {}) {
  if (o.key && TEXCACHE.has(o.key)) return TEXCACHE.get(o.key);
  const c = document.createElement('canvas'); c.width = b; c.height = h;
  zeichne(c.getContext('2d'), b, h);
  const t = new THREE.CanvasTexture(c);
  if (o.srgb !== false) t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  t.wrapS = t.wrapT = o.klemmen ? THREE.ClampToEdgeWrapping : THREE.RepeatWrapping;
  if (o.wiederholen) t.repeat.set(o.wiederholen[0], o.wiederholen[1]);
  t.needsUpdate = true;
  if (o.key) TEXCACHE.set(o.key, t);
  return t;
}
/* Text als Textur, per measureText in die Breite eingepasst (nie über den Rand).
   o: { b = 1024, h = 256, schrift = 'Montserrat', gewicht = 900, groesse = 160, farbe = '#111', hg = null, rand = 40 }
   Schrift vorher laden: await document.fonts.load('900 100px Montserrat') im aufbau. */
export function textTextur(text, o = {}) {
  const b = o.b || 1024, h = o.h || 256, rand = o.rand ?? 40;
  return leinwand(b, h, (ctx) => {
    if (o.hg) { ctx.fillStyle = o.hg; ctx.fillRect(0, 0, b, h); }
    let fs = o.groesse || 160;
    const font = (s) => `${o.gewicht || 900} ${s}px ${JSON.stringify(o.schrift || 'Montserrat')}`;
    ctx.font = font(fs);
    const w = ctx.measureText(text).width;
    if (w > b - 2 * rand) { fs = Math.floor((fs * (b - 2 * rand)) / w); ctx.font = font(fs); }
    ctx.fillStyle = o.farbe || '#111111'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(text, b / 2, h / 2 + fs * 0.04);
  }, { key: o.key || `txt_${text}_${b}_${h}_${o.farbe}_${o.hg}_${o.schrift}`, klemmen: true });
}

/* ------------------------------------------------------------------ Materialien */
/* PBR (physikalisch): o: { rau = 0.6, metall = 0, map, emissiv, ei = 1, transparent, deckkraft, flach, seite } */
export function materialPBR(farbe, o = {}) {
  const m = new THREE.MeshStandardMaterial({ color: new THREE.Color(farbe), roughness: o.rau ?? 0.6, metalness: o.metall ?? 0,
    map: o.map || null, transparent: !!o.transparent, opacity: o.deckkraft ?? 1, flatShading: !!o.flach, side: o.seite ?? THREE.FrontSide });
  if (o.emissiv) { m.emissive = new THREE.Color(o.emissiv); m.emissiveIntensity = o.ei ?? 1; }
  return m;
}
/* Leuchtendes Material (für Bloom): ignoriert Licht, Farbe × staerke > 1 überstrahlt. */
export function leuchtend(farbe, staerke = 2.5, o = {}) {
  const m = new THREE.MeshBasicMaterial({ color: new THREE.Color(farbe).multiplyScalar(staerke), transparent: !!o.transparent,
    opacity: o.deckkraft ?? 1, depthWrite: o.depthWrite ?? true, blending: o.additiv ? THREE.AdditiveBlending : THREE.NormalBlending });
  m.userData.keinToon = true;
  return m;
}
/* Toon (Cel-Shading): direktes Licht in drei Stufen, Glanz hart. Auf einem MeshStandardMaterial, damit Schatten,
   Emissive und Farbanimationen weiter greifen. o wie materialPBR (Standard rau 0.85). Böden rau ≥ 0,8, sonst harter Glanzfleck. */
export function materialToon(farbe, o = {}) { return toonify(materialPBR(farbe, Object.assign({ rau: 0.85 }, o))); }
function toonify(mt) {
  if (!mt.isMeshStandardMaterial || mt.transparent || mt.userData.keinToon || mt.userData.toon) return mt;
  if (mt.emissive && mt.emissiveIntensity > 0 && (mt.emissive.r + mt.emissive.g + mt.emissive.b) > 0.05) return mt;
  mt.onBeforeCompile = (sh) => {
    sh.fragmentShader = sh.fragmentShader.replace('#include <lights_fragment_end>', `#include <lights_fragment_end>
    {
      float dl = dot(reflectedLight.directDiffuse, vec3(0.2126, 0.7152, 0.0722));
      float bl = max(dot(diffuseColor.rgb, vec3(0.2126, 0.7152, 0.0722)), 1e-3);
      float irr = dl / bl * 3.14159;
      float q = mix(0.0, 0.62, smoothstep(0.16, 0.2, irr)); q = mix(q, 1.3, smoothstep(0.92, 1.0, irr));
      reflectedLight.directDiffuse *= q / max(irr, 1e-3);
      float sl = dot(reflectedLight.directSpecular, vec3(0.333));
      reflectedLight.directSpecular *= smoothstep(0.32, 0.36, sl) * 0.7 / max(sl, 1e-3) * 0.6;
    }`);
  };
  mt.customProgramCacheKey = () => 'ms-toon1';
  mt.userData.toon = true;
  mt.needsUpdate = true;
  return mt;
}
/* Alle Standard-Materialien einer Szene auf Toon umstellen (leuchtende und transparente bleiben weich). */
export function toonAlle(scene) {
  const gesehen = new Set();
  scene.traverse((m) => { if (!m.isMesh) return; (Array.isArray(m.material) ? m.material : [m.material]).forEach((mt) => { if (mt && !gesehen.has(mt)) { gesehen.add(mt); toonify(mt); } }); });
}

/* ------------------------------------------------------------------ Geometrie */
const GEOCACHE = new Map();
function rundBoxGeo(w, h, d, r = 0.02, seg = 2) {
  const key = `rb${w.toFixed(4)}_${h.toFixed(4)}_${d.toFixed(4)}_${r}_${seg}`;
  if (GEOCACHE.has(key)) return GEOCACHE.get(key);
  r = Math.min(r, w / 2 - 1e-4, h / 2 - 1e-4, d / 2 - 1e-4);
  const S = 2 * seg + 1, g = new THREE.BoxGeometry(1, 1, 1, S, S, S);
  const pos = g.attributes.position, nor = g.attributes.normal, inner = [w / 2 - r, h / 2 - r, d / 2 - r];
  const remap = (u, ax) => {
    const i = Math.round((u + 0.5) * S);
    if (i <= seg) return -inner[ax] - r * (1 - i / seg);
    if (i >= S - seg) return inner[ax] + r * ((i - (S - seg)) / seg);
    return -inner[ax] + ((i - seg) / (S - 2 * seg)) * 2 * inner[ax];
  };
  const v = new THREE.Vector3(), c = new THREE.Vector3(), n = new THREE.Vector3();
  for (let k = 0; k < pos.count; k++) {
    v.set(remap(pos.getX(k), 0), remap(pos.getY(k), 1), remap(pos.getZ(k), 2));
    c.set(clamp(v.x, -inner[0], inner[0]), clamp(v.y, -inner[1], inner[1]), clamp(v.z, -inner[2], inner[2]));
    n.subVectors(v, c); const L = n.length();
    if (L > 1e-6) { n.divideScalar(L); v.copy(c).addScaledVector(n, r); } else n.set(nor.getX(k), nor.getY(k), nor.getZ(k));
    pos.setXYZ(k, v.x, v.y, v.z); nor.setXYZ(k, n.x, n.y, n.z);
  }
  pos.needsUpdate = true; nor.needsUpdate = true; g.computeBoundingBox(); g.computeBoundingSphere();
  GEOCACHE.set(key, g);
  return g;
}
/* Box mit Schatten, Ursprung = Mitte. o: { r (Rundung, z. B. 0.03), rot: [x, y, z], schatten = true } */
export function kiste(eltern, b, h, t, material, x = 0, y = 0, z = 0, o = {}) {
  const m = new THREE.Mesh(o.r ? rundBoxGeo(b, h, t, o.r, o.seg || 2) : new THREE.BoxGeometry(b, h, t), material);
  m.position.set(x, y, z);
  if (o.rot) m.rotation.set(o.rot[0], o.rot[1], o.rot[2]);
  m.castShadow = o.schatten ?? true; m.receiveShadow = true;
  if (eltern) eltern.add(m);
  return m;
}

/* ------------------------------------------------------------------ Licht-Presets */
/* preset: 'studio' (neutral, weiches Key + Fill + Kante) | 'abend' (warm/kühl, Kontrast) | 'buehne' (dunkel, harter Spot von oben)
   | 'tag' (hell, Himmel). Gibt {haupt, fuell, kante, himmel, amb, spot?} zurück: im zustand(t) dimmen für Licht-Dramatik.
   Ohne Fill/Himmel werden Rückseiten schwarz (flache Scherenschnitte): nie nur ein Licht. */
export function licht(scene, preset = 'studio', o = {}) {
  const P = {
    studio: { sky: '#dfe8ff', ground: '#6b5a4a', hemi: 1.1, key: '#fff1de', keyI: 2.4, keyPos: [-3.5, 8, 6], fill: '#9fb4ff', fillI: 0.6, rim: '#e6efff', rimI: 1.0, amb: 0.15 },
    abend: { sky: '#8aa0d8', ground: '#4a2e22', hemi: 0.8, key: '#ffc88a', keyI: 2.8, keyPos: [5, 5, 5], fill: '#6a7dff', fillI: 0.5, rim: '#ffd9a8', rimI: 1.4, amb: 0.08 },
    buehne: { sky: '#3a4466', ground: '#1a1410', hemi: 0.35, key: '#fff4e0', keyI: 1.2, keyPos: [0, 9, 3], fill: '#5a6aa8', fillI: 0.25, rim: '#bcd0ff', rimI: 1.2, amb: 0.05, spot: true },
    tag: { sky: '#cfe6ff', ground: '#8f8a7a', hemi: 1.5, key: '#fffaf0', keyI: 2.6, keyPos: [4, 10, 6], fill: '#cfe0ff', fillI: 0.7, rim: '#ffffff', rimI: 0.6, amb: 0.2 },
  }[preset] || {};
  const c = Object.assign({}, P, o), L = {};
  L.himmel = new THREE.HemisphereLight(c.sky, c.ground, c.hemi); scene.add(L.himmel);
  L.haupt = new THREE.DirectionalLight(c.key, c.keyI); L.haupt.position.set(...c.keyPos); L.haupt.target.position.set(...(c.ziel || [0, 1, 0]));
  scene.add(L.haupt, L.haupt.target);
  L.haupt.castShadow = true; L.haupt.shadow.mapSize.set(2048, 2048);
  const s = c.schattenGroesse || 7, sc = L.haupt.shadow.camera;
  sc.left = -s; sc.right = s; sc.top = s; sc.bottom = -s; sc.near = 0.5; sc.far = 40;
  L.haupt.shadow.bias = -0.0004; L.haupt.shadow.normalBias = 0.02; L.haupt.shadow.radius = 4;
  L.fuell = new THREE.DirectionalLight(c.fill, c.fillI); L.fuell.position.set(5, 4, 3); scene.add(L.fuell);
  L.kante = new THREE.DirectionalLight(c.rim, c.rimI); L.kante.position.set(1, 6, -9); scene.add(L.kante);
  L.amb = new THREE.AmbientLight('#ffffff', c.amb); scene.add(L.amb);
  if (c.spot) {
    L.spot = new THREE.SpotLight('#fff1d6', 60, 18, 0.32, 0.55, 1.6);
    L.spot.position.set(0, 6, 2); L.spot.target.position.set(0, 0.8, 0); L.spot.castShadow = true; L.spot.shadow.mapSize.set(1024, 1024);
    scene.add(L.spot, L.spot.target);
  }
  return L;
}

/* ------------------------------------------------------------------ Post (DOF, AO, Bloom, AgX, Grading, Korn, Bewegungsunschärfe) */
/* Standardwerte. Pro Bild über post(t) überschreibbar, z. B. { bloom: t > T_HIT ? 0.8 : 0.35, schaerfe: 4.5, blende: 2 }.
   belichtung, agx (Filmkurve an), saettigung, kontrast, bloom (Stärke), bloomSchwelle, bloomRadius, schaerfe (Fokus-Abstand m),
   blende (0 = alles scharf), maxUnschaerfe (px), ao (0..1 Kontaktschatten), vignette, korn, farbsaum, mb (Unterbilder für
   Bewegungsunschärfe, 1 = aus, 5 = an), verschluss (0..1)
   Text-Tafeln lesbar halten: Tafelfarbe ≤ 0,85 Helligkeit (sonst Bloom-Schleier über der Schrift), farbsaum klein. */
export const POST = {
  belichtung: 1.0, agx: true, saettigung: 1.1, kontrast: 1.04, bloom: 0.35, bloomSchwelle: 1.0, bloomKnie: 0.45, bloomRadius: 0.8,
  schaerfe: 5, blende: 0, maxUnschaerfe: 8, ao: 0.4, aoRadius: 0.3, vignette: 0.22, vignetteWeich: 0.6, korn: 0.016,
  farbsaum: 0.0012, mb: 1, verschluss: 1.0, lift: [0, 0, 0], gain: [1, 1, 1],
};
const VS = 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }';
function vollbild() {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute([-1, -1, 0, 3, -1, 0, -1, 3, 0], 3));
  geo.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, 2, 0, 0, 2], 2));
  const mesh = new THREE.Mesh(geo, null); mesh.frustumCulled = false;
  const scene = new THREE.Scene(); scene.add(mesh);
  const cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  return { run(r, material, ziel) { mesh.material = material; r.setRenderTarget(ziel || null); r.render(scene, cam); } };
}
function rt(w, h, o = {}) {
  const t = new THREE.WebGLRenderTarget(w, h, { type: o.type ?? THREE.HalfFloatType, format: THREE.RGBAFormat, minFilter: THREE.LinearFilter,
    magFilter: THREE.LinearFilter, depthBuffer: !!o.depth, samples: o.samples || 0 });
  if (o.depthTexture) { t.depthTexture = new THREE.DepthTexture(w, h); t.depthTexture.type = THREE.FloatType; }
  t.texture.colorSpace = THREE.LinearSRGBColorSpace;
  return t;
}
const AO_FS = `precision highp float; varying vec2 vUv;
uniform sampler2D tDepth; uniform mat4 uProj, uProjInv; uniform vec2 uRes; uniform float uRadius, uBias;
vec3 vpos(vec2 uv){ float d = texture2D(tDepth, uv).r; vec4 p = uProjInv * vec4(uv*2.0-1.0, d*2.0-1.0, 1.0); return p.xyz/p.w; }
void main(){
  float d0 = texture2D(tDepth, vUv).r; if (d0 >= 0.99999) { gl_FragColor = vec4(1.0); return; }
  vec2 px = 1.0/uRes; vec3 P = vpos(vUv);
  vec3 a = vpos(vUv + vec2(px.x, 0.0)) - P, b = P - vpos(vUv - vec2(px.x, 0.0)), c = vpos(vUv + vec2(0.0, px.y)) - P, e = P - vpos(vUv - vec2(0.0, px.y));
  vec3 dx = dot(a,a) < dot(b,b) ? a : b; vec3 dy = dot(c,c) < dot(e,e) ? c : e;
  vec3 N = normalize(cross(dx, dy)); if (N.z < 0.0) N = -N;
  vec2 cell = mod(floor(gl_FragCoord.xy), 4.0); float ang = (cell.x * 4.0 + cell.y) / 16.0 * 6.2831853 + 0.37;
  vec3 rv = vec3(cos(ang), sin(ang), 0.0); vec3 T = normalize(rv - N * dot(rv, N)); vec3 B = cross(N, T); mat3 TBN = mat3(T, B, N);
  float occ = 0.0;
  for (int i = 0; i < 16; i++) {
    float fi = float(i); float r = (fi + 0.5) / 16.0; float th = fi * 2.3999632;
    vec3 k = vec3(cos(th) * sqrt(r), sin(th) * sqrt(r), sqrt(1.0 - r));
    vec3 S = P + TBN * k * uRadius * mix(0.15, 1.0, r * r);
    vec4 o = uProj * vec4(S, 1.0); vec2 suv = o.xy / o.w * 0.5 + 0.5;
    if (suv.x < 0.0 || suv.y < 0.0 || suv.x > 1.0 || suv.y > 1.0) continue;
    float sz = vpos(suv).z;
    occ += (sz >= S.z + uBias ? 1.0 : 0.0) * smoothstep(0.0, 1.0, uRadius / max(abs(P.z - sz), 1e-4));
  }
  gl_FragColor = vec4(vec3(1.0 - occ / 16.0), 1.0);
}`;
const AOBLUR_FS = `precision highp float; varying vec2 vUv; uniform sampler2D tAO; uniform vec2 uPx;
void main(){ float s = 0.0; for (int x = -2; x < 2; x++) for (int y = -2; y < 2; y++) s += texture2D(tAO, vUv + (vec2(float(x), float(y)) + 0.5) * uPx).r; gl_FragColor = vec4(vec3(s / 16.0), 1.0); }`;
const AOAPPLY_FS = `precision highp float; varying vec2 vUv; uniform sampler2D tColor; uniform sampler2D tAO; uniform float uAO;
void main(){ vec3 c = texture2D(tColor, vUv).rgb; gl_FragColor = vec4(c * mix(1.0, texture2D(tAO, vUv).r, uAO), 1.0); }`;
const DOF_FS = `precision highp float; varying vec2 vUv;
uniform sampler2D tColor; uniform sampler2D tDepth; uniform vec2 uPx; uniform float uNear, uFar, uFocus, uAperture, uMaxBlur;
float lin(float d){ float z = d*2.0-1.0; return 2.0*uNear*uFar/(uFar+uNear - z*(uFar-uNear)); }
float coc(float z){ return clamp(abs((1.0/uFocus - 1.0/z) * uAperture), 0.0, uMaxBlur); }
void main(){
  vec3 col = texture2D(tColor, vUv).rgb;
  if (uMaxBlur < 0.5 || uAperture <= 0.0) { gl_FragColor = vec4(col, 1.0); return; }
  float cz = lin(texture2D(tDepth, vUv).r); float cs = coc(cz); float tot = 1.0; float radius = 0.65; float ang = 0.0;
  for (int i = 0; i < 900; i++) {
    if (radius >= uMaxBlur) break;
    vec2 tc = vUv + vec2(cos(ang), sin(ang)) * uPx * radius;
    vec3 sc = texture2D(tColor, tc).rgb; float sz = lin(texture2D(tDepth, tc).r); float ss = coc(sz);
    if (sz > cz) ss = clamp(ss, 0.0, cs * 2.0);
    col += mix(col / tot, sc, smoothstep(radius - 0.5, radius + 0.5, ss)); tot += 1.0;
    ang += 2.39996323; radius += 0.65 / radius;
  }
  gl_FragColor = vec4(col / tot, 1.0);
}`;
const BRIGHT_FS = `precision highp float; varying vec2 vUv; uniform sampler2D tColor; uniform float uThr, uKnee;
void main(){ vec3 c = texture2D(tColor, vUv).rgb; float br = max(c.r, max(c.g, c.b));
  float soft = clamp(br - uThr + uKnee, 0.0, 2.0*uKnee); soft = soft*soft/(4.0*uKnee + 1e-4);
  gl_FragColor = vec4(c * (max(soft, br - uThr) / max(br, 1e-4)), 1.0); }`;
const DOWN_FS = `precision highp float; varying vec2 vUv; uniform sampler2D tSrc; uniform vec2 uPx;
void main(){ vec3 a = texture2D(tSrc, vUv + uPx*vec2(-1.0,-1.0)).rgb + texture2D(tSrc, vUv + uPx*vec2(1.0,-1.0)).rgb + texture2D(tSrc, vUv + uPx*vec2(-1.0,1.0)).rgb + texture2D(tSrc, vUv + uPx*vec2(1.0,1.0)).rgb;
 vec3 b = texture2D(tSrc, vUv).rgb*4.0 + texture2D(tSrc, vUv + uPx*vec2(2.0,0.0)).rgb + texture2D(tSrc, vUv - uPx*vec2(2.0,0.0)).rgb + texture2D(tSrc, vUv + uPx*vec2(0.0,2.0)).rgb + texture2D(tSrc, vUv - uPx*vec2(0.0,2.0)).rgb;
 gl_FragColor = vec4(a*0.125 + b*0.0625, 1.0); }`;
const UP_FS = `precision highp float; varying vec2 vUv; uniform sampler2D tSrc; uniform sampler2D tPrev; uniform vec2 uPx; uniform float uR;
void main(){ vec2 o = uPx * uR; vec3 s = texture2D(tSrc, vUv).rgb*4.0
 + (texture2D(tSrc, vUv+vec2(o.x,0.0)).rgb + texture2D(tSrc, vUv-vec2(o.x,0.0)).rgb + texture2D(tSrc, vUv+vec2(0.0,o.y)).rgb + texture2D(tSrc, vUv-vec2(0.0,o.y)).rgb)*2.0
 + texture2D(tSrc, vUv+o).rgb + texture2D(tSrc, vUv-o).rgb + texture2D(tSrc, vUv+vec2(o.x,-o.y)).rgb + texture2D(tSrc, vUv+vec2(-o.x,o.y)).rgb;
 gl_FragColor = vec4(s/16.0 + texture2D(tPrev, vUv).rgb, 1.0); }`;
const ACC_FS = 'precision highp float; varying vec2 vUv; uniform sampler2D tSrc; uniform float uW; void main(){ gl_FragColor = vec4(texture2D(tSrc, vUv).rgb * uW, 1.0); }';
const FINAL_FS = `precision highp float; varying vec2 vUv;
uniform sampler2D tColor; uniform sampler2D tBloom; uniform vec2 uRes;
uniform float uExposure, uBloom, uCA, uVig, uVigSoft, uGrain, uSeed, uSat, uContrast, uAgx; uniform vec3 uLift, uGain;
float hash12(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
vec3 toSRGB(vec3 c){ c = max(c, 0.0); return mix(c * 12.92, 1.055 * pow(c, vec3(1.0/2.4)) - 0.055, step(0.0031308, c)); }
vec3 agxContrast(vec3 x){ vec3 x2 = x * x; vec3 x4 = x2 * x2; return 15.5 * x4 * x2 - 40.14 * x4 * x + 31.96 * x4 - 6.868 * x2 * x + 0.4298 * x2 + 0.1191 * x - 0.00232; }
vec3 agxTone(vec3 color){
  const mat3 toRec2020 = mat3(vec3(0.6274, 0.0691, 0.0164), vec3(0.3293, 0.9195, 0.0880), vec3(0.0433, 0.0113, 0.8956));
  const mat3 fromRec2020 = mat3(vec3(1.6605, -0.1246, -0.0182), vec3(-0.5876, 1.1329, -0.1006), vec3(-0.0728, -0.0083, 1.1187));
  const mat3 inset = mat3(vec3(0.856627153315983, 0.137318972929847, 0.11189821299995), vec3(0.0951212405381588, 0.761241990602591, 0.0767994186031903), vec3(0.0482516061458583, 0.101439036467562, 0.811302368396859));
  const mat3 outset = mat3(vec3(1.1271005818144368, -0.1413297634984383, -0.14132976349843826), vec3(-0.11060664309660323, 1.157823702216272, -0.11060664309660294), vec3(-0.016493938717834573, -0.016493938717834257, 1.2519364065950405));
  color = toRec2020 * color; color = inset * color; color = max(color, 1e-10); color = log2(color);
  color = (color + 12.47393) / (4.026069 + 12.47393); color = clamp(color, 0.0, 1.0); color = agxContrast(color);
  color = outset * color; color = pow(max(vec3(0.0), color), vec3(2.2)); color = fromRec2020 * color; return clamp(color, 0.0, 1.0);
}
void main(){
  vec2 d = vUv - 0.5; vec2 da = d * vec2(1.0, uRes.y / uRes.x); float r2 = dot(da, da);
  vec2 off = d * uCA * (0.35 + 2.4 * r2);
  vec3 c;
  c.r = texture2D(tColor, vUv + off).r + texture2D(tBloom, vUv + off).r * uBloom;
  c.g = texture2D(tColor, vUv).g + texture2D(tBloom, vUv).g * uBloom;
  c.b = texture2D(tColor, vUv - off).b + texture2D(tBloom, vUv - off).b * uBloom;
  c *= uExposure;
  c = (uAgx > 0.5) ? agxTone(c) : c / (1.0 + 0.06 * c);
  vec3 s = toSRGB(c);
  s = (s - 0.5) * uContrast + 0.5;
  s = max(s * uGain + uLift * (1.0 - s), 0.0);
  float l = dot(s, vec3(0.2126, 0.7152, 0.0722)); s = mix(vec3(l), s, uSat);
  float vig = smoothstep(0.85, 0.85 - uVigSoft, length(d * vec2(1.0, 1.15)) * 1.414); s *= mix(1.0 - uVig, 1.0, vig);
  s += (hash12(vUv * uRes + vec2(uSeed * 37.13, uSeed * 91.71)) + hash12(vUv * uRes * 0.5 + uSeed * 13.7) - 1.0) * uGrain;
  gl_FragColor = vec4(clamp(s, 0.0, 1.0), 1.0);
}`;
class Post {
  constructor(r, w, h) {
    this.r = r; this.w = w; this.h = h; this.q = vollbild();
    this.sceneRT = rt(w, h, { depth: true, depthTexture: true }); this.msRT = rt(w, h, { depth: true, samples: 4 });
    this.dofRT = rt(w, h); this.aoRT = rt(w, h); this.aoBlurRT = rt(w, h); this.aoColRT = rt(w, h); this.accRT = rt(w, h);
    this.bright = rt(w >> 1, h >> 1); this.mips = []; let mw = w >> 1, mh = h >> 1;
    for (let i = 0; i < 6; i++) { mw = Math.max(1, mw >> 1); mh = Math.max(1, mh >> 1); this.mips.push({ down: rt(mw, mh), up: rt(mw, mh) }); }
    this.bloomOut = rt(w >> 1, h >> 1); this.black = rt(4, 4);
    const sm = (fs, u) => new THREE.ShaderMaterial({ vertexShader: VS, fragmentShader: fs, uniforms: u, depthTest: false, depthWrite: false });
    const V2 = (x, y) => ({ value: new THREE.Vector2(x, y) });
    this.mDof = sm(DOF_FS, { tColor: { value: null }, tDepth: { value: null }, uPx: V2(1 / w, 1 / h), uNear: { value: 0.05 }, uFar: { value: 200 }, uFocus: { value: 3 }, uAperture: { value: 0 }, uMaxBlur: { value: 8 } });
    this.mAO = sm(AO_FS, { tDepth: { value: null }, uProj: { value: new THREE.Matrix4() }, uProjInv: { value: new THREE.Matrix4() }, uRes: V2(w, h), uRadius: { value: 0.3 }, uBias: { value: 0.02 } });
    this.mAOBlur = sm(AOBLUR_FS, { tAO: { value: null }, uPx: V2(1 / w, 1 / h) });
    this.mAOApply = sm(AOAPPLY_FS, { tColor: { value: null }, tAO: { value: null }, uAO: { value: 0 } });
    this.mBright = sm(BRIGHT_FS, { tColor: { value: null }, uThr: { value: 1 }, uKnee: { value: 0.5 } });
    this.mDown = sm(DOWN_FS, { tSrc: { value: null }, uPx: V2(0, 0) });
    this.mUp = sm(UP_FS, { tSrc: { value: null }, tPrev: { value: null }, uPx: V2(0, 0), uR: { value: 1 } });
    this.mAcc = sm(ACC_FS, { tSrc: { value: null }, uW: { value: 1 } });
    this.mAcc.blending = THREE.CustomBlending; this.mAcc.blendEquation = THREE.AddEquation; this.mAcc.blendSrc = THREE.OneFactor; this.mAcc.blendDst = THREE.OneFactor; this.mAcc.transparent = true;
    this.mFinal = sm(FINAL_FS, { tColor: { value: null }, tBloom: { value: null }, uRes: V2(w, h), uExposure: { value: 1 }, uBloom: { value: 0.3 }, uCA: { value: 0 },
      uVig: { value: 0.3 }, uVigSoft: { value: 0.5 }, uGrain: { value: 0.02 }, uSeed: { value: 1 }, uSat: { value: 1 }, uContrast: { value: 1 }, uAgx: { value: 1 },
      uLift: { value: new THREE.Vector3() }, uGain: { value: new THREE.Vector3(1, 1, 1) } });
  }
  ebene(scene, camera, p) {
    const r = this.r;
    r.setRenderTarget(this.msRT); r.clear(); r.render(scene, camera);
    r.setRenderTarget(this.sceneRT); r.clear(); r.render(scene, camera);
    let col = this.msRT.texture;
    if (p.ao > 0) {
      const a = this.mAO.uniforms; a.tDepth.value = this.sceneRT.depthTexture; a.uProj.value.copy(camera.projectionMatrix); a.uProjInv.value.copy(camera.projectionMatrixInverse);
      a.uRadius.value = p.aoRadius; this.q.run(r, this.mAO, this.aoRT);
      this.mAOBlur.uniforms.tAO.value = this.aoRT.texture; this.q.run(r, this.mAOBlur, this.aoBlurRT);
      const ap = this.mAOApply.uniforms; ap.tColor.value = col; ap.tAO.value = this.aoBlurRT.texture; ap.uAO.value = p.ao; this.q.run(r, this.mAOApply, this.aoColRT);
      col = this.aoColRT.texture;
    }
    const u = this.mDof.uniforms;
    u.tColor.value = col; u.tDepth.value = this.sceneRT.depthTexture; u.uNear.value = camera.near; u.uFar.value = camera.far;
    u.uFocus.value = p.schaerfe; u.uAperture.value = p.blende; u.uMaxBlur.value = p.maxUnschaerfe;
    this.q.run(r, this.mDof, this.dofRT);
    return this.dofRT.texture;
  }
  bloom(src, p) {
    const r = this.r;
    this.mBright.uniforms.tColor.value = src; this.mBright.uniforms.uThr.value = p.bloomSchwelle; this.mBright.uniforms.uKnee.value = p.bloomKnie;
    this.q.run(r, this.mBright, this.bright);
    let s = this.bright;
    for (const m of this.mips) { this.mDown.uniforms.tSrc.value = s.texture; this.mDown.uniforms.uPx.value.set(1 / s.width, 1 / s.height); this.q.run(r, this.mDown, m.down); s = m.down; }
    for (let i = this.mips.length - 1; i >= 0; i--) {
      const m = this.mips[i];
      this.mUp.uniforms.tSrc.value = m.down.texture; this.mUp.uniforms.tPrev.value = (i === this.mips.length - 1 ? this.black : this.mips[i + 1].up).texture;
      this.mUp.uniforms.uPx.value.set(1 / m.down.width, 1 / m.down.height); this.mUp.uniforms.uR.value = p.bloomRadius;
      this.q.run(r, this.mUp, m.up);
    }
    this.mUp.uniforms.tSrc.value = this.bright.texture; this.mUp.uniforms.tPrev.value = this.mips[0].up.texture; this.mUp.uniforms.uPx.value.set(2 / this.w, 2 / this.h);
    this.q.run(r, this.mUp, this.bloomOut);
    return this.bloomOut.texture;
  }
  render(scene, camera, params, zustandBei) {
    const p = Object.assign({}, POST, params || {}), r = this.r, n = Math.max(1, p.mb | 0);
    let tex;
    if (n === 1 || !zustandBei) { if (zustandBei) zustandBei(0); tex = this.ebene(scene, camera, p); }
    else {
      r.setRenderTarget(this.accRT); r.setClearColor(0x000000, 1); r.clear();
      for (let i = 0; i < n; i++) {
        zustandBei(((i + 0.5) / n - 0.5) * p.verschluss);
        const t = this.ebene(scene, camera, p);
        this.mAcc.uniforms.tSrc.value = t; this.mAcc.uniforms.uW.value = 1 / n; this.q.run(r, this.mAcc, this.accRT);
      }
      tex = this.accRT.texture;
    }
    const b = this.bloom(tex, p), u = this.mFinal.uniforms;
    u.tColor.value = tex; u.tBloom.value = b; u.uExposure.value = p.belichtung; u.uBloom.value = p.bloom; u.uCA.value = p.farbsaum;
    u.uVig.value = p.vignette; u.uVigSoft.value = p.vignetteWeich; u.uGrain.value = p.korn; u.uSeed.value = p.kornSeed ?? 1;
    u.uSat.value = p.saettigung; u.uContrast.value = p.kontrast; u.uAgx.value = p.agx ? 1 : 0; u.uLift.value.set(...p.lift); u.uGain.value.set(...p.gain);
    this.q.run(r, this.mFinal, null);
    r.setRenderTarget(null);
  }
}

/* Renderer + Szene + Kamera für 1080 × 1920 mit Post. o: { canvas, breite, hoehe, fov = 40, nah, fern, hintergrund, nebel: [farbe, nah, fern] }
   -> { renderer, scene, camera, setzeKamera({pos, ziel, fov, roll}), render(post, zustandBei), projiziere(v) -> [px, py] } */
export function motor(o = {}) {
  const W = o.breite || 1080, H = o.hoehe || 1920;
  const renderer = new THREE.WebGLRenderer({ canvas: o.canvas, antialias: false, preserveDrawingBuffer: true, alpha: false, powerPreference: 'high-performance' });
  renderer.setPixelRatio(1); renderer.setSize(W, H, false);
  renderer.outputColorSpace = THREE.LinearSRGBColorSpace; renderer.toneMapping = THREE.NoToneMapping;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.setClearColor(0x000000, 1); renderer.autoClear = false;
  const scene = new THREE.Scene(); scene.background = new THREE.Color(o.hintergrund || '#14181f');
  if (o.nebel) scene.fog = new THREE.Fog(o.nebel[0], o.nebel[1], o.nebel[2]);
  const camera = new THREE.PerspectiveCamera(o.fov || 40, W / H, o.nah || 0.05, o.fern || 200);
  const post = new Post(renderer, W, H), v = new THREE.Vector3();
  const m = {
    renderer, scene, camera, post, W, H,
    setzeKamera(k) {
      if (k.fov) { camera.fov = k.fov; camera.updateProjectionMatrix(); }
      camera.position.set(k.pos[0], k.pos[1], k.pos[2]);
      camera.up.set(0, 1, 0); camera.lookAt(k.ziel[0], k.ziel[1], k.ziel[2]);
      if (k.roll) camera.rotateZ(k.roll);
      camera.updateMatrixWorld(true);
    },
    projiziere(p) { camera.updateMatrixWorld(true); v.set(p.x ?? p[0], p.y ?? p[1], p.z ?? p[2]).project(camera); return [(v.x + 1) * 0.5 * W, (1 - v.y) * 0.5 * H]; },
    render(params, zustandBei) { post.render(scene, camera, params, zustandBei); },
  };
  return m;
}

/* ------------------------------------------------------------------ Kamera als Funktion der Zeit */
/* Kamerafahrt aus Schlüsseln in lokalen Sekunden: { 0: {pos:[x,y,z], ziel:[x,y,z], fov: 40}, 1.2: {...} } -> fn(t).
   Weich (Catmull-Rom), vor dem ersten und nach dem letzten Schlüssel steht die Kamera. Keys nie durch Objekte legen. */
export function kamerafahrt(keys) {
  const ks = Object.keys(keys).map(Number).sort((a, b) => a - b);
  const get = (i) => keys[ks[clamp(i, 0, ks.length - 1)]];
  return (t) => {
    if (t <= ks[0]) return keys[ks[0]];
    if (t >= ks[ks.length - 1]) return keys[ks[ks.length - 1]];
    let i = 0; while (ks[i + 1] < t) i++;
    const u = (t - ks[i]) / (ks[i + 1] - ks[i]);
    const a = get(i - 1), b = get(i), c = get(i + 1), d = get(i + 2);
    const cr = (p0, p1, p2, p3) => { const u2 = u * u, u3 = u2 * u; return 0.5 * (2 * p1 + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u2 + (-p0 + 3 * p1 - 3 * p2 + p3) * u3); };
    const out = { pos: b.pos.map((_, j) => cr(a.pos[j], b.pos[j], c.pos[j], d.pos[j])), ziel: b.ziel.map((_, j) => cr(a.ziel[j], b.ziel[j], c.ziel[j], d.ziel[j])) };
    out.fov = cr(a.fov || 40, b.fov || 40, c.fov || 40, d.fov || 40);
    if (b.roll !== undefined || c.roll !== undefined) out.roll = lerp(b.roll || 0, c.roll || 0, u);
    return out;
  };
}
/* Kreisfahrt um ein Ziel. o: { ziel: [x,y,z], radius, hoehe, von (Grad), bis (Grad), t0, t1, fov = 40, kurve = ease.inOutSine }.
   Winkel 0 = Kamera auf +z vor dem Ziel. */
export function orbit(o) {
  return (t) => {
    const u = (o.kurve || ease.inOutSine)(win(t, o.t0 ?? 0, o.t1 ?? 1));
    const a = ((o.von ?? 0) + ((o.bis ?? 30) - (o.von ?? 0)) * u) * Math.PI / 180;
    return { pos: [o.ziel[0] + Math.sin(a) * o.radius, o.hoehe ?? o.ziel[1] + 0.6, o.ziel[2] + Math.cos(a) * o.radius], ziel: o.ziel, fov: o.fov || 40 };
  };
}
/* Kamerastoß nach einem Treffer bei t0: [dx, dy] zum Addieren auf pos. staerke in Metern (0.03 spürbar), abkling 12 = kurz. */
export function schuettel(t, t0, staerke = 0.03, abkling = 12) {
  if (t < t0) return [0, 0];
  const k = Math.exp(-(t - t0) * abkling) * staerke, f = frameOf(t);
  return [Math.sin(f * 2.7) * k, Math.cos(f * 3.1) * k];
}
/* Übergang 3D -> 2D: Kamera fährt von "von" in die Fläche (Mesh mit PlaneGeometry), bis sie das Bild füllt.
   Die Fläche hat die Hintergrundfarbe der folgenden 2D-Szene. -> fn(t), für t außerhalb [t0, t1] gilt von bzw. das Ende.
   o: { fov (Ende, Standard wie von), ueberfuellen = 0.92 (Abstand-Faktor < 1 = sicher randlos) } */
export function portalFahrt(flaeche, von, t0, t1, o = {}) {
  flaeche.updateMatrixWorld(true);
  const g = flaeche.geometry.parameters || { width: 1, height: 1 }, s = new THREE.Vector3(); flaeche.getWorldScale(s);
  const mitte = new THREE.Vector3(); flaeche.getWorldPosition(mitte);
  const normal = new THREE.Vector3(0, 0, 1).applyQuaternion(flaeche.getWorldQuaternion(new THREE.Quaternion()));
  const fov = o.fov || von.fov || 40;
  const d = fuellAbstand(g.width * s.x, g.height * s.y, fov) * (o.ueberfuellen ?? 0.92);
  const ende = { pos: mitte.clone().addScaledVector(normal, d).toArray(), ziel: mitte.toArray(), fov };
  return (t) => {
    const u = ease.inOutCubic(win(t, t0, t1));
    return { pos: von.pos.map((x, j) => lerp(x, ende.pos[j], u)), ziel: von.ziel.map((x, j) => lerp(x, ende.ziel[j], u)), fov: lerp(von.fov || 40, fov, u) };
  };
}

/* ------------------------------------------------------------------ Effekte */
/* Treffer-Blitz: kamerabezogener Stern (additiv, leuchtet im Bloom). o: { groesse = 1.2, farbe = '#ffd25a', staerke = 1.4, zacken = 12, seed,
   ueberAllem = true }. ueberAllem: ohne Tiefentest, sonst schneidet die Blitz-Fläche Objekte am Treffer in Keile. */
export function blitz(o = {}) {
  const c = Object.assign({ groesse: 1.2, farbe: '#ffd25a', staerke: 1.4, zacken: 12, seed: 3, art: 'stern' }, o);
  const tex = leinwand(256, 256, (ctx, w, h) => {
    const r = rng(c.seed), cx = w / 2, cy = h / 2;
    const g2 = ctx.createRadialGradient(cx, cy, 0, cx, cy, w / 2);
    g2.addColorStop(0, 'rgba(255,255,255,1)'); g2.addColorStop(c.art === 'stern' ? 0.25 : 0.4, 'rgba(255,255,255,0.75)'); g2.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g2; ctx.fillRect(0, 0, w, h);
    if (c.art === 'stern') {
      ctx.fillStyle = 'rgba(255,255,255,0.95)';
      for (let i = 0; i < c.zacken; i++) {
        const a = (i / c.zacken) * Math.PI * 2 + (r() - 0.5) * 0.4, L = w * (0.3 + r() * 0.2), wd = 0.06 + r() * 0.05;
        ctx.beginPath(); ctx.moveTo(cx + Math.cos(a - wd) * w * 0.12, cy + Math.sin(a - wd) * w * 0.12);
        ctx.lineTo(cx + Math.cos(a) * L, cy + Math.sin(a) * L); ctx.lineTo(cx + Math.cos(a + wd) * w * 0.12, cy + Math.sin(a + wd) * w * 0.12); ctx.fill();
      }
    }
  }, { key: `blitz_${c.art}_${c.seed}_${c.zacken}`, klemmen: true });
  const m = new THREE.MeshBasicMaterial({ map: tex, color: new THREE.Color(c.farbe).multiplyScalar(c.staerke), transparent: true, depthWrite: false,
    depthTest: c.ueberAllem === false, blending: THREE.AdditiveBlending });
  m.userData.keinToon = true;
  const s = new THREE.Mesh(new THREE.PlaneGeometry(c.groesse, c.groesse), m); s.renderOrder = 12; s.visible = false;
  return s;
}
/* Blitz im zustand(t) zeigen: ab T für o.dauer (0.28 s) wachsen und ausblenden, zur Kamera gedreht. kameraPos = aktuelle Kameraposition. */
export function blitzZeigen(mesh, t, T, pos, kameraPos, o = {}) {
  const u = win(t, T, T + (o.dauer || 0.28));
  mesh.visible = u > 0 && u < 1;
  if (!mesh.visible) return;
  mesh.position.set(pos[0] ?? pos.x, pos[1] ?? pos.y, pos[2] ?? pos.z);
  mesh.lookAt(kameraPos[0] ?? kameraPos.x, kameraPos[1] ?? kameraPos.y, kameraPos[2] ?? kameraPos.z);
  mesh.scale.setScalar((o.von ?? 0.4) + (o.bis ?? 1.4) * ease.outCubic(u));
  mesh.material.opacity = 1 - u;
}

/* Funken + Rauchwolke. add(pos, t0, opt): opt { groesse = 1, n = 8, dauer = 0.55, farbe (Funken), staub (Wolkenfarbe),
   wolke: false = nur Funken (für Treffer: Wolken verdecken den Treffer), ring: true = Wolkenring um eine Figur (Erscheinen) }.
   Alles im aufbau anlegen, update(t) im zustand. */
const PUFF_GEO = new THREE.IcosahedronGeometry(1, 1), FUNKE_GEO = new THREE.OctahedronGeometry(1, 0);
export function funkenWolke(scene, o = {}) {
  const liste = [], r = rng(o.seed || 99);
  const add = (pos, t0, opt = {}) => {
    const size = opt.groesse ?? 1, n = opt.n ?? 8, dur = opt.dauer ?? 0.55, ring = !!opt.ring, puffs = [];
    if (opt.wolke !== false) {
      const pm = materialPBR(opt.staub || '#f1e8d8', { rau: 0.95, flach: true }), np = ring ? 11 : Math.max(5, Math.round(n * 0.9));
      for (let i = 0; i < np; i++) {
        const m = new THREE.Mesh(PUFF_GEO, pm); m.castShadow = false; m.visible = false; scene.add(m);
        puffs.push({ m, a: (i / np) * Math.PI * 2 + r() * 0.5, r0: (ring ? 0.4 : 0.16) * size * (0.8 + r() * 0.5), y0: (ring ? 0.12 + r() * 0.55 : (r() - 0.35) * 0.3) * size, s: (ring ? 0.24 : 0.17) * size * (0.75 + r() * 0.6), d: r() * 0.07, rot: r() * 6 });
      }
    }
    const sm = materialPBR('#ffffff', { emissiv: opt.farbe || '#fff1c0', ei: 3.2, rau: 0.4 }); sm.userData.keinToon = true;
    const funken = [...Array(Math.max(3, Math.round(n * 0.8)))].map((_, i, arr) => {
      const m = new THREE.Mesh(FUNKE_GEO, sm); m.castShadow = false; m.visible = false; scene.add(m);
      const a = (i / arr.length) * Math.PI * 2 + r() * 0.6, el = 0.25 + r() * 0.9;
      return { m, v: new THREE.Vector3(Math.cos(a) * Math.cos(el), Math.sin(el) + 0.2, Math.sin(a) * Math.cos(el)).multiplyScalar((1.5 + r() * 1.3) * size), spin: 4 + r() * 8 };
    });
    liste.push({ pos: new THREE.Vector3(pos[0] ?? pos.x, pos[1] ?? pos.y, pos[2] ?? pos.z), t0, puffs, funken, size, dur, ring });
  };
  const update = (t) => liste.forEach((b) => {
    const PD = b.ring ? 0.62 : b.dur;
    b.puffs.forEach((p) => {
      const u = (t - b.t0 - p.d) / PD, an = u >= 0 && u < 1; p.m.visible = an; if (!an) return;
      const e = 1 - Math.pow(1 - u, 3), rr = p.r0 + 0.45 * b.size * e;
      p.m.position.set(b.pos.x + Math.cos(p.a) * rr, b.pos.y + p.y0 + 0.28 * b.size * e, b.pos.z + Math.sin(p.a) * rr * 0.85);
      p.m.scale.setScalar(Math.max(0.0001, p.s * Math.pow(Math.sin(Math.PI * Math.min(1, u * 1.15)), 0.6))); p.m.rotation.set(p.rot + u, p.rot * 0.5 + u * 2, 0);
    });
    b.funken.forEach((s) => {
      const u = (t - b.t0) / (b.dur * 0.85), an = u >= 0 && u < 1; s.m.visible = an; if (!an) return;
      const d = ((1 - Math.exp(-3.2 * u)) / 3.2) * 1.6;
      s.m.position.set(b.pos.x + s.v.x * d, b.pos.y + s.v.y * d - 0.7 * b.size * u * u, b.pos.z + s.v.z * d);
      s.m.scale.setScalar(Math.max(0.0001, 0.05 * b.size * (1 - u))); s.m.rotation.set(s.spin * u, s.spin * 0.6 * u, 0);
    });
  });
  return { add, update, liste };
}

/* Konfetti: farbige Schnipsel fliegen hoch, flattern, fallen. add(pos, t0, opt { n = 60, kraft = 3.2, dauer = 1.6, farben }), update(t). */
export function konfetti(scene, o = {}) {
  const liste = [], r = rng(o.seed || 5), geo = new THREE.PlaneGeometry(0.06, 0.035);
  const add = (pos, t0, opt = {}) => {
    const farben = opt.farben || ['#ffd25a', '#5aff9a', '#ff7ac8', '#7fd8ff', '#ffffff'], n = opt.n || 60;
    const mats = farben.map((f) => { const m = new THREE.MeshBasicMaterial({ color: f, side: THREE.DoubleSide }); m.userData.keinToon = true; return m; });
    for (let i = 0; i < n; i++) {
      const m = new THREE.Mesh(geo, mats[i % mats.length]); m.visible = false; scene.add(m);
      const a = r() * Math.PI * 2, el = 0.9 + r() * 0.6, v = (opt.kraft || 3.2) * (0.5 + r() * 0.7);
      liste.push({ m, t0, dur: opt.dauer || 1.6, p: new THREE.Vector3(pos[0] ?? pos.x, pos[1] ?? pos.y, pos[2] ?? pos.z),
        v: new THREE.Vector3(Math.cos(a) * Math.cos(el) * v, Math.sin(el) * v, Math.sin(a) * Math.cos(el) * v), spin: [r() * 14, r() * 14, r() * 6], flatter: 6 + r() * 8 });
    }
  };
  const update = (t) => liste.forEach((k) => {
    const u = t - k.t0, an = u >= 0 && u < k.dur; k.m.visible = an; if (!an) return;
    const zieh = 1 - Math.exp(-2.2 * u);
    k.m.position.set(k.p.x + k.v.x * zieh / 2.2 + Math.sin(u * k.flatter) * 0.05, k.p.y + k.v.y * zieh / 2.2 - 1.6 * u * u, k.p.z + k.v.z * zieh / 2.2);
    k.m.rotation.set(k.spin[0] * u, k.spin[1] * u, k.spin[2] * u);
    k.m.scale.setScalar(u > k.dur * 0.8 ? Math.max(0.001, 1 - (u - k.dur * 0.8) / (k.dur * 0.2)) : 1);
  });
  return { add, update, liste };
}

/* ------------------------------------------------------------------ HyperFrames-Anbindung (benutzt von ms3d-start.js) */
/* Baut die Szene und liefert render(globaleZeit). o siehe ms3d-start.js. startFn() liefert den globalen Start der Szene. */
export async function szeneBauen(o, startFn) {
  const M = await import(import.meta.url);
  const canvas = typeof o.canvas === 'string' ? document.getElementById(o.canvas) : o.canvas;
  if (!canvas) throw new Error(`ms3d: canvas ${o.canvas} nicht gefunden`);
  if (o.schriften) await Promise.all(o.schriften.map((f) => document.fonts.load(f).catch(() => null)));
  const m = motor({ canvas, fov: o.fov || 40, hintergrund: o.hintergrund, nebel: o.nebel });
  const welt = (await o.aufbau(M, m)) || {};
  if (o.toon) toonAlle(m.scene);
  const D = o.dauer;
  return (gt) => {
    const t = clamp(gt - startFn(), 0, D), f = frameOf(t);
    const p = Object.assign({}, o.post ? o.post(t, welt, M, m) : {}, { kornSeed: f + 1 });
    m.render(p, (u) => {
      const tt = t + u / FPS;
      m.setzeKamera(o.kamera(tt, welt, M, m));   // Kamera zuerst: zustand darf m.camera.position benutzen (Blitz zur Kamera drehen)
      o.zustand(tt, welt, M, m);
      m.scene.updateMatrixWorld(true);
    });
  };
}
