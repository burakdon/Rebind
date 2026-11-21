// Lightbox study: the novel as a tunnel book. One cut-paper leaf per chapter, lit from behind.
// A study of the look first; the drawing rules below are simple enough to explain later.
//
//   ground  rises where the chapter is set; taller for more tension
//   sky     hangs lower over the same place the colder the chapter is
//   house   is cut on the leaf where the story arrives at a place
//   figures stand for the named people the reader verified in that chapter
//   paper   is tinted warm or cool by the chapter's warmth

import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

const W = 36, H = 24, GAP = 0.7, BORDER = 1.1, BASE = 1.7, TOP = 1.0, STEP = 0.03;
const Q = new URLSearchParams(location.search);
const num = (k, d) => (Q.has(k) ? parseFloat(Q.get(k)) : d);

// Everything drawn here comes from book.json, the style-neutral record of the reading (rebind tokenize).
const B = await (await fetch('../data/pride-and-prejudice/book.json')).json();
const K = B.chapters.length, DEPTH = (K - 1) * GAP;

// ---- data per chapter ------------------------------------------------------------------------
const places = B.places.map(b => b.name);
const weights = B.places.map(b => Math.sqrt(b.passages));
const total = weights.reduce((a, b) => a + b, 0);
const X0 = -W / 2 + BORDER + 1.6, X1 = W / 2 - BORDER - 1.6;
const anchor = {}, spread = {};
{ let acc = 0;
  places.forEach((p, i) => {
    anchor[p] = X0 + (X1 - X0) * (acc + weights[i] / 2) / total;
    spread[p] = (X1 - X0) * weights[i] / total;
    acc += weights[i];
  }); }

const WALKERS = 12;  // the most-mentioned people get a figure
const chapters = B.chapters.map((c, k) => ({ k, n: c.n, label: c.label, at: {}, people: {} }));
for (const p of B.passages) {
  const c = chapters[p.chapter - 1], place = p.at.place;
  if (!(place in anchor)) continue;
  const g = c.at[place] ??= { place, tension: 0, warm: 0, n: 0 };
  g.tension = Math.max(g.tension, p.tension ?? 0); g.warm += p.warmth ?? 5; g.n++;
  for (const who of p.people) {
    const i = B.people.findIndex(q => q.id === who.id);
    if (i < 0 || i >= WALKERS) continue;
    const t = B.people[i].title;
    (c.people[place] ??= new Map()).set(who.id, t === 'female' ? 'gown' : t === 'male' ? 'hat' : 'plain');
  }
}
for (const c of chapters) {
  let w = 0, n = 0;
  for (const g of Object.values(c.at)) { w += g.warm; n += g.n; g.warm /= g.n; }
  c.warm = n ? w / n : 5;
}

// ---- houses, as height profiles (paper is everything under the profile) ------------------------
const R = (x0, x1, h) => ({ t: 'r', x0, x1, h });
const G = (x0, x1, h0, h1) => ({ t: 'g', x0, x1, h0, h1 });
const D = (c, r, h0) => ({ t: 'd', x0: c - r, x1: c + r, c, r, h0 });
function grid(x0, x1, ys, cols, w, h) {
  const out = [];
  for (const y of ys) for (let i = 0; i < cols; i++) out.push([x0 + (x1 - x0) * (cols === 1 ? 0.5 : i / (cols - 1)) - w / 2, y, w, h]);
  return out;
}
const town = [R(-2, -1, 3.0), R(-1, 0, 3.35), R(0, 1, 2.9), R(1, 2, 3.2), R(-1.8, -1.6, 3.3), R(-0.5, -0.3, 3.7), R(0.5, 0.7, 3.2), R(1.55, 1.75, 3.55)];
const townWin = [...grid(-1.7, -1.3, [0.5, 1.2, 1.9, 2.5], 2, 0.2, 0.36), ...grid(-0.7, -0.3, [0.5, 1.2, 1.9, 2.6], 2, 0.2, 0.36),
  ...grid(0.3, 0.7, [0.5, 1.2, 1.9], 2, 0.2, 0.36), ...grid(1.3, 1.7, [0.5, 1.2, 1.9, 2.6], 2, 0.2, 0.36)];
const HOUSES = {
  'Longbourn': { parts: [R(-2, 2, 1.7), G(-2.15, 2.15, 1.7, 2.45), R(-1.5, -1.2, 2.85), R(1.2, 1.5, 2.85), R(2, 3.1, 1.05), G(2, 3.1, 1.05, 1.55)],
    win: [...grid(-1.6, 1.6, [0.4, 1.05], 5, 0.3, 0.42), [2.4, 0.4, 0.3, 0.4]] },
  'Netherfield': { parts: [R(-2.8, 2.8, 2.35), R(-2.9, 2.9, 2.45), G(-1.1, 1.1, 2.45, 3.0), R(-2.4, -2.1, 2.95), R(2.1, 2.4, 2.95), R(-1.6, -1.35, 2.85), R(1.35, 1.6, 2.85)],
    win: grid(-2.4, 2.4, [0.35, 1.0, 1.65], 7, 0.3, 0.44) },
  'Meryton': { parts: [G(-3, -1.8, 0.9, 1.5), G(-1.8, -0.7, 1.1, 1.8), R(-0.5, 0.3, 2.2), G(-0.5, 0.3, 2.2, 4.3), G(0.5, 1.7, 1.0, 1.6), G(1.7, 3, 0.8, 1.4)],
    win: [[-2.55, 0.3, 0.26, 0.34], [-1.4, 0.4, 0.26, 0.4], [-0.23, 1.3, 0.26, 0.5], [0.95, 0.35, 0.26, 0.36], [2.2, 0.3, 0.26, 0.3]] },
  'Lucas Lodge': { parts: [R(-1.4, 1.4, 1.3), G(-1.55, 1.55, 1.3, 2.15), R(0.7, 0.95, 2.45)], win: grid(-1, 1, [0.35, 0.85], 3, 0.28, 0.34) },
  'Hunsford': { parts: [R(-2.4, -0.4, 1.1), G(-2.55, -0.25, 1.1, 1.9), R(-2.1, -1.85, 2.2), R(0.5, 1.4, 2.6), G(0.5, 1.4, 2.6, 4.1), R(1.4, 2.7, 1.2), G(1.4, 2.7, 1.2, 1.8)],
    win: [...grid(-2, -0.8, [0.4], 3, 0.26, 0.4), [0.82, 1.6, 0.26, 0.6], [1.9, 0.45, 0.3, 0.5]] },
  'Rosings': { parts: [R(-3.4, 3.4, 2.4), R(-3.4, -2.4, 3.6), R(2.4, 3.4, 3.6), R(-3.4, -3.2, 3.85), R(-3.0, -2.8, 3.85), R(-2.6, -2.4, 3.85),
      R(2.4, 2.6, 3.85), R(2.8, 3.0, 3.85), R(3.2, 3.4, 3.85), G(-1, 1, 2.4, 3.2), R(-1.9, -1.65, 2.9), R(1.65, 1.9, 2.9)],
    win: [...grid(-2.9, 2.9, [0.35, 1.0, 1.65], 9, 0.28, 0.44), [-3.04, 2.6, 0.28, 0.5], [2.76, 2.6, 0.28, 0.5]] },
  'Pemberley': { parts: [R(-4.6, 4.6, 1.9), R(-4.6, -3.4, 2.3), R(3.4, 4.6, 2.3), R(-2.2, 2.2, 2.6), G(-1.7, 1.7, 2.6, 3.4), D(0, 0.62, 3.25),
      R(-3.0, -2.75, 2.5), R(2.75, 3.0, 2.5)],
    win: [...grid(-4.15, 4.15, [0.35, 1.0], 13, 0.26, 0.42), ...grid(-1.7, 1.7, [1.7], 5, 0.26, 0.5)] },
  'Grosvenor Street': { parts: town, win: townWin },
  'Gracechurch Street': { parts: town.map(p => ({ ...p, h: p.h * 0.86 })), win: townWin.filter(w => w[1] < 2.2) },
  'London': { parts: [...town.map(p => ({ ...p, x0: p.x0 - 1.4, x1: p.x1 - 1.4 })), R(1, 3, 2.2), D(2, 1.0, 2.2), R(1.92, 2.08, 3.75)],
    win: townWin.map(w => [w[0] - 1.4, w[1], w[2], w[3]]) },
  'Lambton': { parts: [R(-1.6, 1.6, 1.2), G(-1.75, 1.75, 1.2, 2.05), R(-1.1, -0.85, 2.35), G(1.6, 2.9, 0.8, 1.3)], win: grid(-1.2, 1.2, [0.35, 0.85], 4, 0.26, 0.32) },
  'Ramsgate': { parts: [R(-0.36, 0.36, 3.2), R(-0.52, 0.52, 3.3), R(-0.28, 0.28, 3.75), G(-0.34, 0.34, 3.75, 4.15), G(0.9, 2.3, 0.8, 1.4)],
    win: [[-0.13, 3.38, 0.26, 0.3], [-0.1, 1.2, 0.2, 0.3], [-0.1, 2.2, 0.2, 0.3], [1.45, 0.3, 0.26, 0.32]] },
};
function profile(parts, dx) {
  let m = 0;
  for (const p of parts) {
    if (dx < p.x0 || dx > p.x1) continue;
    if (p.t === 'r') m = Math.max(m, p.h);
    else if (p.t === 'g') { const c = (p.x0 + p.x1) / 2; m = Math.max(m, p.h0 + (p.h1 - p.h0) * (1 - Math.abs(dx - c) / ((p.x1 - p.x0) / 2))); }
    else m = Math.max(m, p.h0 + Math.sqrt(Math.max(0, p.r * p.r - (dx - p.c) * (dx - p.c))));
  }
  return m;
}
const FIG = num('fig', 1.5);
const jit = (a, b) => { const v = Math.sin(a * 127.1 + b * 311.7) * 43758.5453; return v - Math.floor(v); };
function figure(kind, dx) {
  dx /= FIG; const a = Math.abs(dx); let h = 0;
  if (kind === 'gown') { if (a < 0.27) h = 0.66 * Math.pow(1 - a / 0.27, 0.55); if (a < 0.115) h = Math.max(h, 0.76 + Math.sqrt(0.115 * 0.115 - a * a)); }
  else if (kind === 'hat') { if (a < 0.13) h = 0.68; if (a < 0.1) h = Math.max(h, 0.78 + Math.sqrt(0.01 - a * a)); if (a < 0.16) h = Math.max(h, 0.93); if (a < 0.095) h = 1.12; }
  else { if (a < 0.15) h = 0.64 * Math.pow(1 - a / 0.2, 0.3); if (a < 0.105) h = Math.max(h, 0.74 + Math.sqrt(0.105 * 0.105 - a * a)); }
  return h * FIG;
}

// ---- the cut line of one leaf -------------------------------------------------------------------
const AMP = num('amp', 9.5), CLOUD = num('cloud', 7), HOUSE = num('house', 1.0);
function leaf(c) {
  const k = c.k, groups = Object.values(c.at), prev = k ? chapters[k - 1].at : {};
  const hill = x => {
    let y = BASE + 0.14 * Math.sin(x * 1.7 + k * 2.1) + 0.08 * Math.sin(x * 4.3 + k * 0.7) + 0.25 * Math.sin(x * 0.35 + k * 0.9);
    for (const g of groups) {
      const s = spread[g.place] * 0.42 + 0.35 * g.n, a = 0.8 + Math.pow(g.tension / 10, 1.25) * AMP;
      y += a * Math.exp(-((x - anchor[g.place]) ** 2) / (2 * s * s));
    }
    return y;
  };
  const cloud = x => {
    let d = TOP + 0.1 * Math.sin(x * 1.3 + k * 1.3);
    for (const g of groups) {
      const s = spread[g.place] * 0.6 + 0.5 * g.n, a = Math.pow(Math.max(0, 10 - g.warm) / 10, 1.3) * CLOUD;
      d += a * Math.exp(-((x - anchor[g.place]) ** 2) / (2 * s * s)) * (0.7 + 0.3 * Math.pow(Math.abs(Math.sin(x * 0.95 + k * 1.7)), 0.6));
    }
    return d;
  };
  // houses on arrival, figures beside them
  const houses = [], figs = [];
  for (const g of groups) {
    const ax = anchor[g.place], arrived = !(g.place in prev), def = HOUSES[g.place];
    let half = 0.3;
    if (arrived && def) {
      const base = hill(ax) - 0.25;
      houses.push({ def, ax, base, place: g.place });
      half = Math.max(...def.parts.map(p => Math.max(Math.abs(p.x0), Math.abs(p.x1)))) * HOUSE + 0.45;
    }
    const who = [...(c.people[g.place] || new Map()).values()];
    let off = [half, half];
    who.forEach((kind, j) => { const side = j % 2; off[side] += FIG * (0.5 + 0.9 * jit(k, j + 7 * side)); figs.push({ kind, x: ax + (side ? -1 : 1) * off[side] }); });
  }
  const xl = -W / 2 + BORDER, xr = W / 2 - BORDER, lo = [], hi = [];
  let best = { gap: -1, x: 0, y: 0 };
  for (let x = xl; x <= xr + 1e-6; x += STEP) {
    let y = hill(x);
    for (const f of figs) if (Math.abs(x - f.x) < 0.3 * FIG) y = Math.max(y, hill(f.x) - 0.05 + figure(f.kind, x - f.x));
    for (const h of houses) { const p = profile(h.def.parts, (x - h.ax) / HOUSE) * HOUSE; if (p > 0) y = Math.max(y, h.base + p); }
    let top = H - cloud(x);
    if (top < y + 2.6) top = y + 2.6;
    lo.push(new THREE.Vector2(x, y - H / 2)); hi.push(new THREE.Vector2(x, Math.min(top, H - 0.5) - H / 2));
    const gap = top - y - Math.abs(x) * 0.22;
    if (gap > best.gap) best = { gap, x, y: (top + y) / 2 - H / 2 };
  }
  const cut = [...lo, ...hi.reverse()];
  const windows = houses.flatMap(h => h.def.win.map(([x, y, w, hh]) => [h.ax + x * HOUSE, h.base + y * HOUSE - H / 2, w * HOUSE, hh * HOUSE]));
  return { cut, windows, centre: best, houses };
}

// ---- scene ----------------------------------------------------------------------------------
const stage = document.getElementById('stage');
const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
const EXPOSURE = num('exp', 1.0);
renderer.toneMappingExposure = EXPOSURE;
stage.appendChild(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x060708);
const camera = new THREE.PerspectiveCamera(num('fov', 30), 1, 0.05, 400);

// gallery wall and the lamp behind the leaves
const wall = new THREE.Mesh(new THREE.PlaneGeometry(400, 240), new THREE.ShaderMaterial({
  uniforms: {}, vertexShader: 'varying vec2 p; void main(){ p = position.xy; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); }',
  fragmentShader: `varying vec2 p; void main(){ float d = length(p/vec2(${(W * 0.9).toFixed(1)}, ${(H * 1.1).toFixed(1)}));
    vec3 c = mix(vec3(0.085,0.062,0.04), vec3(0.012,0.013,0.015), smoothstep(0.55, 1.9, d)); gl_FragColor = vec4(c,1.); }` }));
wall.position.z = -DEPTH - 2.2; scene.add(wall);

const lamp = new THREE.Mesh(new THREE.PlaneGeometry(W, H), new THREE.ShaderMaterial({
  uniforms: { gain: { value: num('lamp', 0.8) } },
  vertexShader: 'varying vec2 u; void main(){ u = uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); }',
  fragmentShader: `uniform float gain; varying vec2 u; void main(){
    float v = u.y; vec2 q = (u - vec2(0.5, 0.36)) * vec2(1.5, 1.0); float d = length(q);
    vec3 c = mix(vec3(2.3, 1.55, 0.8), vec3(1.5, 0.72, 0.42), smoothstep(0.3, 0.55, v));
    c = mix(c, vec3(0.62, 0.36, 0.5), smoothstep(0.5, 0.75, v));
    c = mix(c, vec3(0.13, 0.2, 0.42), smoothstep(0.7, 1.0, v));
    c += vec3(2.4, 1.9, 1.2) * exp(-d * d / 0.03) + vec3(3.0, 2.6, 2.0) * smoothstep(0.062, 0.055, d);
    c *= mix(0.55, 1.0, smoothstep(0.0, 0.3, v));
    gl_FragColor = vec4(c * gain, 1.); }` }));
lamp.position.z = -DEPTH - GAP; scene.add(lamp);

// the box and its frame
const wood = new THREE.MeshStandardMaterial({ color: 0x24160d, roughness: 0.55, metalness: 0.05 });
const inner = new THREE.MeshBasicMaterial({ color: 0x050403 });
const zc = (1.0 + (-DEPTH - GAP - 0.3)) / 2, zd = 1.0 - (-DEPTH - GAP - 0.3), TH = 0.9;
for (const [sx, sy, px, py] of [[TH, H + 2 * TH, -(W + TH) / 2, 0], [TH, H + 2 * TH, (W + TH) / 2, 0], [W, TH, 0, (H + TH) / 2], [W, TH, 0, -(H + TH) / 2]]) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, zd), [wood, wood, wood, wood, wood, wood]);
  m.position.set(px, py, zc); scene.add(m);
  const lining = new THREE.Mesh(new THREE.PlaneGeometry(sx === TH ? zd : W, sx === TH ? H : zd), inner);
  if (sx === TH) { lining.rotation.y = px < 0 ? Math.PI / 2 : -Math.PI / 2; lining.position.set(px < 0 ? -W / 2 + 0.01 : W / 2 - 0.01, 0, zc); }
  else { lining.rotation.x = py < 0 ? -Math.PI / 2 : Math.PI / 2; lining.position.set(0, py < 0 ? -H / 2 + 0.01 : H / 2 - 0.01, zc); }
  scene.add(lining);
}
const FR = 2.2;
for (const [sx, sy, px, py] of [[FR, H + 2 * FR - 0.6, -(W + FR) / 2 + 0.3, 0], [FR, H + 2 * FR - 0.6, (W + FR) / 2 - 0.3, 0], [W + 2 * FR - 0.6, FR, 0, (H + FR) / 2 - 0.3], [W + 2 * FR - 0.6, FR, 0, -(H + FR) / 2 + 0.3]]) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, 1.0), wood); m.position.set(px, py, 1.2); scene.add(m);
}
scene.add(new THREE.AmbientLight(0xfff0dd, 0.35));
const key = new THREE.DirectionalLight(0xffe2c0, 1.6); key.position.set(-30, 40, 60); scene.add(key);

// the leaves. Paper is lit from behind: it glows along every cut and falls dark away from it,
// deeper leaves sit nearer the lamp and are brighter, and each leaf lets a little of what is behind it through.
const RIM = num('rim', 0.22), CANDLE = num('candle', 1.0), ALPHA = num('alpha', 0.92), HALO = num('halo', 0.5);
const warmHalo = new THREE.Color(1.0, 0.44, 0.12), coolHalo = new THREE.Color(0.3, 0.56, 1.0), plainHalo = new THREE.Color(0.95, 0.7, 0.42);
const paperVert = 'varying vec2 p; void main(){ p = position.xy; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); }';
const paperFrag = `uniform sampler2D prof; uniform float xl, xr, alpha; uniform vec3 base, halo; varying vec2 p;
  void main(){
    float d = 1e3;
    for (int i = -5; i <= 5; i++) {
      float x = clamp(p.x + float(i) * 0.1, xl, xr), dx = x - p.x;
      vec2 s = texture2D(prof, vec2((x - xl) / (xr - xl), 0.5)).rg;
      float v = max(0.0, max(s.r - p.y, p.y - s.g));
      d = min(d, sqrt(dx * dx + v * v));
    }
    float g = 1.1 * exp(-d / 0.16) + 0.5 * exp(-d / 0.9) + 0.22 * exp(-d / 3.5);
    float grain = fract(sin(dot(floor(p * 40.0), vec2(12.9898, 78.233))) * 43758.5453);
    gl_FragColor = vec4((base + halo * g) * (0.94 + 0.12 * grain), alpha);
  }`;
const leaves = [];
for (const c of chapters) {
  const cutting = leaf(c), z = -c.k * GAP, order = (K - c.k) * 3, t = c.k / (K - 1);
  const shape = new THREE.Shape([new THREE.Vector2(-W / 2, -H / 2), new THREE.Vector2(W / 2, -H / 2), new THREE.Vector2(W / 2, H / 2), new THREE.Vector2(-W / 2, H / 2)]);
  shape.holes.push(new THREE.Path(cutting.cut));
  for (const [x, y, w, h] of cutting.windows) shape.holes.push(new THREE.Path([new THREE.Vector2(x, y), new THREE.Vector2(x + w, y), new THREE.Vector2(x + w, y + h), new THREE.Vector2(x, y + h)]));
  const n = cutting.cut.length / 2, data = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) { data[i * 4] = cutting.cut[i].y; data[i * 4 + 1] = cutting.cut[2 * n - 1 - i].y; }
  const prof = new THREE.DataTexture(data, n, 1, THREE.RGBAFormat, THREE.FloatType);
  prof.minFilter = prof.magFilter = THREE.LinearFilter; prof.needsUpdate = true;
  const u = THREE.MathUtils.clamp((c.warm - 5) / 3, -1, 1);
  const halo = plainHalo.clone().lerp(u > 0 ? warmHalo : coolHalo, Math.abs(u)).multiplyScalar(HALO * (0.3 + 0.95 * Math.pow(t, 1.3)));
  const base = new THREE.Color(0.016, 0.011, 0.008).lerp(new THREE.Color(0.3, 0.16, 0.07), Math.pow(t, 2.0));
  const paper = new THREE.Mesh(new THREE.ShapeGeometry(shape), new THREE.ShaderMaterial({
    uniforms: { prof: { value: prof }, xl: { value: cutting.cut[0].x }, xr: { value: cutting.cut[n - 1].x }, alpha: { value: ALPHA }, base: { value: base }, halo: { value: halo } },
    vertexShader: paperVert, fragmentShader: paperFrag, transparent: true, depthWrite: false }));
  paper.position.z = z; paper.renderOrder = order; scene.add(paper);
  // the cut edge catches the light
  const edge = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(cutting.cut),
    new THREE.LineBasicMaterial({ color: halo.clone().multiplyScalar(RIM / HALO), blending: THREE.AdditiveBlending, transparent: true, depthWrite: false, toneMapped: false }));
  edge.position.z = z; edge.renderOrder = order + 1; scene.add(edge);
  // candles in the windows
  if (cutting.windows.length) {
    const pos = [], idx = [];
    cutting.windows.forEach(([x, y, w, h], i) => { pos.push(x, y, 0, x + w, y, 0, x + w, y + h, 0, x, y + h, 0); idx.push(i * 4, i * 4 + 1, i * 4 + 2, i * 4, i * 4 + 2, i * 4 + 3); });
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx);
    const glow = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color: new THREE.Color(2.2, 1.25, 0.45).multiplyScalar(CANDLE), blending: THREE.AdditiveBlending, transparent: true, depthWrite: false, toneMapped: false }));
    glow.position.z = z; glow.renderOrder = order + 2; scene.add(glow);
  }
  leaves.push({ c, cutting, z });
}

// the way in: through the widest part of each leaf's opening
const way = leaves.map((l, i) => {
  let x = 0, y = 0, n = 0;
  for (let j = Math.max(0, i - 5); j <= Math.min(K - 1, i + 5); j++) { x += leaves[j].cutting.centre.x; y += leaves[j].cutting.centre.y; n++; }
  return new THREE.Vector3(x / n, y / n, l.z);
});
function wayAt(z) {
  const f = THREE.MathUtils.clamp(-z / GAP, 0, K - 1), i = Math.floor(f), j = Math.min(K - 1, i + 1);
  return way[i].clone().lerp(way[j], f - i).setZ(z);
}

// ---- camera -----------------------------------------------------------------------------------
const composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(2, 2, { type: THREE.HalfFloatType, samples: 4 }));
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(2, 2), num('bloom', 0.32), num('radius', 0.85), num('thresh', 0.72));
composer.addPass(bloom);
composer.addPass(new OutputPass());

let home = 62;
function resize() {
  const w = innerWidth, h = innerHeight;
  renderer.setSize(w, h); composer.setSize(w, h);
  camera.aspect = w / h; camera.updateProjectionMatrix();
  const t = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
  home = Math.max((H / 2 + 5.5) / t, (W / 2 + 5.5) / (t * camera.aspect));
}
addEventListener('resize', resize); resize();

const state = { p: num('p', 0), pt: num('p', 0), mx: num('mx', 0), my: num('my', 0), tx: num('mx', 0), ty: num('my', 0) };
addEventListener('pointermove', e => { state.tx = (e.clientX / innerWidth) * 2 - 1; state.ty = (e.clientY / innerHeight) * 2 - 1; });
addEventListener('wheel', e => { state.pt = THREE.MathUtils.clamp(state.pt + e.deltaY * 0.00045, 0, 1); e.preventDefault(); }, { passive: false });
addEventListener('keydown', e => {
  if (e.key === 'ArrowUp' || e.key === 'ArrowRight') state.pt = Math.min(1, state.pt + 1 / K);
  if (e.key === 'ArrowDown' || e.key === 'ArrowLeft') state.pt = Math.max(0, state.pt - 1 / K);
});
let touchY = null;
addEventListener('touchstart', e => { touchY = e.touches[0].clientY; }, { passive: true });
addEventListener('touchmove', e => { const y = e.touches[0].clientY; state.pt = THREE.MathUtils.clamp(state.pt + (touchY - y) * 0.0012, 0, 1); touchY = y; }, { passive: true });

const title = document.getElementById('cap-title'), sub = document.getElementById('cap-sub');
const intro = sub.textContent;
let shown = -2;
function caption(z) {
  const k = z > 0.5 ? -1 : Math.min(K - 1, Math.max(0, Math.round(-z / GAP)));
  if (k === shown) return; shown = k;
  if (k < 0) { title.textContent = B.book.title; sub.textContent = intro; return; }
  const c = chapters[k];
  title.textContent = 'Chapter ' + c.label;
  sub.textContent = Object.keys(c.at).join(' · ') || 'no place named';
}

function frame() {
  state.p += (state.pt - state.p) * 0.08; state.mx += (state.tx - state.mx) * 0.06; state.my += (state.ty - state.my) * 0.06;
  const z = THREE.MathUtils.lerp(home, -DEPTH + 1.2, state.p);
  const inside = THREE.MathUtils.smoothstep(-z, -12, 2);
  const out = new THREE.Vector3(state.mx * 13, -state.my * 7, z);
  const on = wayAt(Math.min(0, z)).add(new THREE.Vector3(state.mx * 1.2, -state.my * 0.8, 0));
  camera.position.copy(out.lerp(on, inside));
  const far = new THREE.Vector3(0, 0, -DEPTH * 0.45), ahead = wayAt(Math.min(0, z) - 9);
  camera.lookAt(far.lerp(ahead, inside));
  renderer.toneMappingExposure = EXPOSURE * (1 - 0.45 * inside * THREE.MathUtils.clamp(-z / DEPTH, 0, 1));
  caption(z);
  composer.render();
  requestAnimationFrame(frame);
}
frame();
window.box = { state, leaves, chapters, camera, bloom, lamp };
