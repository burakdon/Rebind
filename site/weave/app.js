// The book as a weave. Everything drawn comes from book.json (rebind tokenize); this file only
// decides how to weave it, by the rules in RULES, which are also what the page shows as its legend.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const RULES = {
  W1: 'The cloth is woven top to bottom in book order. Every sentence is one pass of the weft, and a pale pass marks the start of each chapter. The cloth is cut into equal lengths where a chapter ends.',
  W2: 'Every person the reader verified is a band of warp threads running the whole length of the book. The most-mentioned person is in the middle and the others alternate outwards; a band is wider the more often its person is mentioned.',
  W3: 'Where a sentence names a person, their threads are lifted over the weft for that pass and show at full colour. Everywhere else the weft covers them and they show only faintly.',
  W4: 'The weft takes the reader\'s tone for that passage: bluer when colder, redder when warmer, darker when more tense. Speech is woven in a lighter, glossier yarn than narration.',
  W5: 'The edge threads are dyed by the place where the passage is set, and each place has its own ground weave.',
  W6: 'Where the reader found people meeting, a pale gold thread is laid between their bands on the sentences it cited. A quarrel is laid in silver and a proposal in white.',
  W7: 'The loose ends at the foot of each length are the same warp threads, unwoven, with the names of the most-mentioned people.',
};

const Q = new URLSearchParams(location.search);
const num = (k, d) => (Q.has(k) ? parseFloat(Q.get(k)) : d);
const DATA = '../data/pride-and-prejudice/';
const [B, TXT] = await Promise.all([fetch(DATA + 'book.json').then(r => r.json()), fetch(DATA + 'text.json').then(r => r.json())]);
await Promise.all([document.fonts.load('32px "IM Fell English SC"'), document.fonts.load('italic 32px "IM Fell English"')]).catch(() => {});
const S = B.sentences, P = B.passages, N = S.start.length;

// ---- the thread plan (W2, W5) --------------------------------------------------------------------
const hex = h => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
const DYES = ['#ff5a45', '#ffd45e', '#4f9dff', '#f48fb1', '#45c486', '#ff8f3c', '#b57bee', '#35c5c0', '#c3d24a', '#ee5fa7', '#8fd3ff',
  '#d9a066', '#ffab91', '#9ccc65', '#ce93d8', '#80cbc4'].map(hex);
const PLAIN = ['#b9ad98', '#9fb0a8', '#b89fa6', '#a3a9bd'].map(hex);
const PLACE = ['#c8b27a', '#8fb39b', '#b5838d', '#7d9bb8', '#d4a373', '#9a8fbf', '#a3b18a', '#c97b63', '#6d9dc5', '#e0c36a', '#7fb7b0', '#b98bb0'].map(hex);
const BINDER = [34, 29, 25], CHAPTER_PICK = [226, 214, 190];
const BROCADE = { gold: [226, 182, 92], quarrel: [190, 204, 222], proposal: [255, 255, 255] };
const SEL = 7, FRINGE = Math.round(num('fringe', 64));

const people = B.people.map((p, i) => ({ ...p, i, dye: i < DYES.length ? DYES[i] : PLAIN[i % PLAIN.length],
  ends: Math.round(2 + 12 * Math.sqrt(p.mentions / B.people[0].mentions)) }));
const across = [...people].sort((a, b) => (Math.ceil(a.i / 2) * (a.i % 2 ? 1 : -1)) - (Math.ceil(b.i / 2) * (b.i % 2 ? 1 : -1)));
const cols = [];
for (let i = 0; i < SEL; i++) cols.push({ type: 'edge' });
cols.push({ type: 'bind' }, { type: 'bind' });
for (const p of across) {
  p.c0 = cols.length;
  for (let i = 0; i < p.ends; i++) cols.push({ type: 'person', who: p.i });
  p.c1 = cols.length - 1;
  cols.push({ type: 'bind' });
}
cols.push({ type: 'bind' });
for (let i = 0; i < SEL; i++) cols.push({ type: 'edge' });
const E = cols.length;
const placeIndex = Object.fromEntries(B.places.map((p, i) => [p.name, i]));

// ground weaves, one per place (W5): true where the warp shows through the weft
const WEAVES = [
  (c, r) => (c + r) % 4 === 0, (c, r) => (c - r % 4 + 4) % 4 === 0, (c, r) => (c * 3 + r) % 8 === 0,
  (c, r) => (c + [0, 1, 3, 2][r % 4]) % 4 === 0, (c, r) => (c * 2 + r) % 5 === 0, (c, r) => (c + r) % 3 === 0,
  (c, r) => (c - r % 3 + 3) % 3 === 0, (c, r) => ((Math.floor(c / 8) % 2 ? c + r : c - r % 4 + 4)) % 4 === 0,
  (c, r) => (Math.abs((c % 8) - 4) + Math.abs((r % 8) - 4)) % 4 === 0, (c, r) => (c * 2 + r) % 6 === 0,
  (c, r) => (Math.floor(c / 2) + Math.floor(r / 2)) % 4 === 0, (c, r) => (c + 2 * r) % 4 === 0,
];
const WEAVE_NAMES = ['twill to the right', 'twill to the left', 'eight-end satin', 'broken twill', 'five-end satin', 'steep twill to the right',
  'steep twill to the left', 'herringbone', 'diamond', 'six-end satin', 'basket', 'shallow twill'];

// ---- the weft (W4) and the gold threads (W6) -----------------------------------------------------
const mix = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
const COOL = [26, 44, 92], NEUTRAL = [70, 58, 44], WARM = [122, 34, 34];
function weft(tension, warmth, speech) {
  const u = Math.max(-1, Math.min(1, ((warmth ?? 5) - 5) / 4));
  const base = mix(NEUTRAL, u > 0 ? WARM : COOL, Math.pow(Math.abs(u), 0.9));
  const k = (1.18 - 0.85 * (tension ?? 5) / 10) * (speech ? 1.18 : 1);
  return base.map(v => Math.min(255, v * k));
}
const sentenceAt = new Map(S.start.map((s, i) => [s, i]));
const gold = new Map();  // sentence -> [{c0, c1, colour, meeting, passage}]
for (const p of P) for (const m of p.meetings) {
  const who = m.who.map(id => people.find(q => q.id === id)).filter(Boolean);
  if (who.length < 2) continue;
  const c0 = Math.min(...who.map(q => q.c0)), c1 = Math.max(...who.map(q => q.c1));
  const colour = BROCADE[m.kind] || BROCADE.gold;
  for (const [a] of m.spans) {
    const i = sentenceAt.get(a);
    if (i !== undefined) (gold.get(i) || gold.set(i, []).get(i)).push({ c0, c1, colour, who: who.map(q => q.i), meeting: m, passage: p });
  }
}

// ---- cut into lengths (W1) and weave each one -------------------------------------------------------
const chapterRange = B.chapters.map(c => {
  const first = P[c.passages[0]], last = P[c.passages[0] + c.passages[1] - 1];
  return [first.sentences[0], last.sentences[0] + last.sentences[1]];
});
const LENGTHS = Math.round(num('lengths', innerWidth > innerHeight * 1.15 ? 5 : 3));
const cuts = [0];
for (let j = 1; j < LENGTHS; j++) {
  let best = 0;
  chapterRange.forEach(([a], k) => { if (Math.abs(a - N * j / LENGTHS) < Math.abs(chapterRange[best][0] - N * j / LENGTHS)) best = k; });
  cuts.push(best);
}
cuts.push(B.chapters.length);

function weave(k0, k1) {
  const rows = [];
  for (let k = k0; k < k1; k++) { rows.push({ chapter: k }); for (let i = chapterRange[k][0]; i < chapterRange[k][1]; i++) rows.push({ s: i }); }
  const R = rows.length + FRINGE, rgba = new Uint8Array(E * R * 4), aux = new Uint8Array(E * R * 4);
  const put = (c, r, col, up, sheen, fringe) => {
    const o = (r * E + c) * 4;
    rgba[o] = col[0]; rgba[o + 1] = col[1]; rgba[o + 2] = col[2]; rgba[o + 3] = up ? 255 : 0;
    aux[o] = sheen * 255; aux[o + 1] = fringe ? 255 : 0; aux[o + 3] = 255;
  };
  let place = 0;
  rows.forEach((row, r) => {
    if (row.chapter !== undefined) {
      for (let c = 0; c < E; c++) { const up = c % 6 === r % 6; put(c, r, up ? BINDER : CHAPTER_PICK, up, 0.25); }
      return;
    }
    const i = row.s, p = P[S.passage[i]];
    place = placeIndex[p.at.place] ?? place;
    const w = weft(p.tension, p.warmth, S.speech[i]), named = S.people[i], ties = gold.get(i), ground = WEAVES[place % WEAVES.length];
    for (let c = 0; c < E; c++) {
      const col = cols[c];
      if (col.type === 'edge') { const up = (c + r) % 4 !== 0; put(c, r, up ? PLACE[place % PLACE.length] : w, up, 0.3); continue; }
      const lifted = col.type === 'person' && named.includes(col.who);
      const tie = !lifted && col.type !== 'bind' && (c + r) % 3 !== 0 && ties && ties.find(t => c >= t.c0 && c <= t.c1 && !t.who.includes(col.who));
      if (tie) { put(c, r, tie.colour, false, 1); continue; }
      if (lifted) { put(c, r, people[col.who].dye, true, 0.9); continue; }
      const up = ground(c, r);
      put(c, r, up ? (col.type === 'bind' ? BINDER : people[col.who].dye.map(v => v * 0.7)) : w, up, up ? 0.45 : (S.speech[i] ? 0.5 : 0.2));
    }
  });
  for (let r = rows.length; r < R; r++) for (let c = 0; c < E; c++) {
    const col = cols[c];
    put(c, r, col.type === 'person' ? people[col.who].dye : col.type === 'edge' ? PLACE[place % PLACE.length] : BINDER, true, 0.7, true);
  }
  return { rows, R, rgba, aux, k0, k1 };
}

// ---- scene ---------------------------------------------------------------------------------------
const CELL = 0.1, GAP = 5.5, PW = E * CELL;
const stage = document.getElementById('stage');
const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
stage.appendChild(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0d0c0b);
const camera = new THREE.PerspectiveCamera(28, 1, 0.5, 4000);

const vert = `varying vec2 vUv; varying vec3 vP; varying vec3 vN;
  void main(){ vUv = uv; vec4 w = modelMatrix * vec4(position, 1.); vP = w.xyz; vN = normalize(mat3(modelMatrix) * normal);
    gl_Position = projectionMatrix * viewMatrix * w; }`;
const frag = `uniform sampler2D map, aux; uniform vec2 grid; uniform vec3 light; uniform vec4 pick; uniform float fringeRows;
  varying vec2 vUv; varying vec3 vP; varying vec3 vN;
  float hash(float n){ return fract(sin(n * 127.1) * 43758.5453); }
  vec3 lit(vec3 base, float sheen, vec3 N, vec3 Td, vec3 V, vec3 L){
    float d = max(0., (dot(N, L) + 0.5) / 1.5);
    vec3 H = normalize(L + V); float th = dot(Td, H);
    float s = pow(max(0., 1. - th * th), 28.) * smoothstep(-0.2, 0.4, dot(N, L));
    return base * (0.26 + 0.95 * d) + mix(vec3(1.), base, 0.55) * s * sheen * 0.85;
  }
  void main(){
    vec2 t = vec2(vUv.x, 1. - vUv.y), g = t * grid, c = floor(g), f = fract(g), fw = fwidth(g);
    float detail = 1. - smoothstep(0.1, 0.34, max(fw.x, fw.y));
    vec3 N = normalize(vN); if (!gl_FrontFacing) N = -N;
    vec3 Tu = normalize(cross(vec3(0., 1., 0.), N)), Tv = normalize(cross(N, Tu));
    vec3 V = normalize(cameraPosition - vP), L = normalize(light);
    vec4 far = texture2D(map, t), fa = texture2D(aux, t);
    vec3 col = mix(lit(far.rgb, fa.r, N, Tu, V, L), lit(far.rgb, fa.r, N, Tv, V, L), far.a);
    float inFringe = step(grid.y - fringeRows, g.y);
    float len = fringeRows * (0.55 + 0.45 * hash(c.x));
    if (inFringe > 0.5 && g.y > grid.y - fringeRows + len) discard;
    col *= mix(1., 0.62, inFringe);
    if (detail > 0.) {
      vec4 me = textureLod(map, (c + .5) / grid, 0.), ma = textureLod(aux, (c + .5) / grid, 0.);
      bool U = me.a > .5, fr = ma.g > .5;
      float across = U ? f.x : f.y, along = U ? f.y : f.x;
      vec2 st = U ? vec2(0., 1.) : vec2(1., 0.);
      bool pS = (textureLod(map, (c - st + .5) / grid, 0.).a > .5) == U, nS = (textureLod(map, (c + st + .5) / grid, 0.).a > .5) == U;
      float a = across * 2. - 1.;
      float s0 = pS ? 0. : 1. - smoothstep(0., .5, along), s1 = nS ? 0. : smoothstep(.5, 1., along);
      float crown = fr ? 1. : (1. - s0) * (1. - s1);
      // a thread is round, narrows where it dives under its neighbour, and is plied with a visible twist
      float wd = fr ? 0.58 : 0.98 * (0.62 + 0.38 * crown);
      float round_ = max(0., 1. - (a * a) / (wd * wd));
      if (fr && round_ < 0.03 && detail > 0.5) discard;
      float run = along + (U ? c.y : c.x);
      float ply = 0.5 + 0.5 * sin((run * 2.5 + a * 0.55) * 6.2832);
      float fibre = hash(floor(a * 7. + run * 3.) + c.x * 17. + c.y * 31.);
      vec3 base = me.rgb * (0.7 + 0.24 * ply + 0.1 * fibre) * (0.16 + 0.84 * pow(round_, 0.75)) * mix(.42, 1., crown);
      vec3 Tp = U ? Tu : Tv, Td = U ? Tv : Tu;
      vec3 Nm = normalize(N + Tp * (a * 1.25) + Td * ((U ? 1. : -1.) * (s0 - s1) * 0.9));
      col = mix(col, lit(base, ma.r, Nm, Td, V, L), detail);
    }
    if (pick.w > .5) {
      if (c.y == pick.x) col = col * 1.35 + 0.1;
      else if (c.x >= pick.y && c.x <= pick.z) col = col * 1.18 + 0.03;
    }
    gl_FragColor = vec4(col, 1.);
    #include <colorspace_fragment>
  }`;

function label(text, size, colour = '#cdbf9f', font = '"IM Fell English SC"', style = '') {
  const cv = document.createElement('canvas'), x = cv.getContext('2d'), px = 64;
  x.font = `${style} ${px}px ${font}`;
  const w = Math.ceil(x.measureText(text).width) + 16;
  cv.width = w; cv.height = px * 1.4;
  x.font = `${style} ${px}px ${font}`; x.fillStyle = colour; x.textBaseline = 'middle'; x.fillText(text, 8, cv.height / 2);
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
  const m = new THREE.Mesh(new THREE.PlaneGeometry(size * w / cv.height, size), new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false }));
  m.userData.w = size * w / cv.height;
  return m;
}

const light = new THREE.Vector3(-0.45, 0.55, 0.7);
const lengths = [], meshes = [];
const totalW = LENGTHS * PW + (LENGTHS - 1) * GAP;
let maxH = 0;
for (let j = 0; j < LENGTHS; j++) {
  const w = weave(cuts[j], cuts[j + 1]), PH = w.R * CELL;
  maxH = Math.max(maxH, PH);
  const tex = new THREE.DataTexture(w.rgba, E, w.R, THREE.RGBAFormat);
  tex.colorSpace = THREE.SRGBColorSpace;
  const ax = new THREE.DataTexture(w.aux, E, w.R, THREE.RGBAFormat);
  for (const t of [tex, ax]) { t.generateMipmaps = true; t.minFilter = THREE.LinearMipmapLinearFilter; t.magFilter = THREE.LinearFilter;
    t.anisotropy = renderer.capabilities.getMaxAnisotropy(); t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping; t.needsUpdate = true; }
  const geo = new THREE.PlaneGeometry(PW, PH, 60, 200), pos = geo.attributes.position, DR = num('drape', 1.0);
  for (let v = 0; v < pos.count; v++) {
    const x = pos.getX(v), y = pos.getY(v), d = Math.max(0, 0.5 - y / PH);  // 0 at the rod, 1 at the foot
    pos.setZ(v, DR * (0.12 + 1.15 * Math.pow(d, 1.2)) * Math.sin(x / PW * Math.PI * 5 + j * 1.9 + 0.9 * Math.sin(d * 4 + j)) + DR * 0.5 * Math.sin(d * 5 + j * 2.3));
  }
  geo.computeVertexNormals();
  const mat = new THREE.ShaderMaterial({ vertexShader: vert, fragmentShader: frag, side: THREE.DoubleSide,
    uniforms: { map: { value: tex }, aux: { value: ax }, grid: { value: new THREE.Vector2(E, w.R) }, light: { value: light },
      pick: { value: new THREE.Vector4(0, 0, 0, 0) }, fringeRows: { value: FRINGE } } });
  const mesh = new THREE.Mesh(geo, mat);
  const x0 = -totalW / 2 + j * (PW + GAP) + PW / 2;
  mesh.position.set(x0, -PH / 2, 0);
  mesh.userData = { w, j }; scene.add(mesh); meshes.push(mesh); lengths.push({ w, mesh, x0, PH });

  // rod, shadow on the wall, heading, chapter numerals, names on the loose ends (W7)
  const rod = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.42, PW + 3, 20), new THREE.MeshBasicMaterial({ color: 0x2c1d12 }));
  rod.rotation.z = Math.PI / 2; rod.position.set(x0, 0.2, -0.1); scene.add(rod);
  const shadow = new THREE.Mesh(new THREE.PlaneGeometry(PW * 1.25, PH * 1.06), new THREE.ShaderMaterial({ transparent: true, depthWrite: false,
    vertexShader: 'varying vec2 u; void main(){ u = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }',
    fragmentShader: 'varying vec2 u; void main(){ vec2 d = smoothstep(vec2(0.), vec2(0.16, 0.05), u) * smoothstep(vec2(0.), vec2(0.16, 0.05), 1. - u); gl_FragColor = vec4(0., 0., 0., 0.62 * d.x * d.y); }' }));
  shadow.position.set(x0 + 2.2, -PH / 2 - 1.6, -3.6); scene.add(shadow);
  const head = label(`Chapters ${B.chapters[w.k0].label} – ${B.chapters[w.k1 - 1].label}`, 1.5);
  head.position.set(x0, 2.6, 0); scene.add(head);
  w.rows.forEach((row, r) => {
    if (row.chapter === undefined) return;
    const m = label(B.chapters[row.chapter].label, 0.62, '#9d917c');
    m.position.set(x0 - PW / 2 - 0.35 - m.userData.w / 2, -(r + 0.5) * CELL, 0.3); scene.add(m);
  });
  for (const p of people.slice(0, 16)) {
    const m = label(p.name, 0.95, '#' + p.dye.map(v => Math.round(v).toString(16).padStart(2, '0')).join(''), '"IM Fell English"', 'italic');
    m.rotation.z = -Math.PI / 2;
    m.position.set(x0 - PW / 2 + (p.c0 + p.c1 + 1) / 2 * CELL, -PH - 0.6 - m.userData.w / 2, 0.6); scene.add(m);
  }
}
const wall = new THREE.Mesh(new THREE.PlaneGeometry(3000, 2000), new THREE.ShaderMaterial({
  uniforms: { c: { value: new THREE.Vector2(0, -maxH * 0.42) }, s: { value: new THREE.Vector2(totalW * 0.75, maxH * 0.85) } },
  vertexShader: 'varying vec2 p; void main(){ p = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }',
  fragmentShader: `uniform vec2 c, s; varying vec2 p; void main(){ float d = length((p - c) / s);
    vec3 col = mix(vec3(0.022, 0.019, 0.016), vec3(0.003, 0.003, 0.003), smoothstep(0.3, 1.7, d));
    gl_FragColor = vec4(col, 1.);
    #include <colorspace_fragment>
  }` }));
wall.position.z = -4; scene.add(wall);

// ---- camera ----------------------------------------------------------------------------------------
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.dampingFactor = 0.08; controls.zoomToCursor = true; controls.screenSpacePanning = true;
controls.mouseButtons = { LEFT: THREE.MOUSE.PAN, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.ROTATE };
controls.touches = { ONE: THREE.TOUCH.PAN, TWO: THREE.TOUCH.DOLLY_ROTATE };
controls.minDistance = 3; controls.minAzimuthAngle = -1.1; controls.maxAzimuthAngle = 1.1; controls.minPolarAngle = 0.7; controls.maxPolarAngle = 2.3;
const centre = new THREE.Vector3(0, -maxH / 2 - 1.5, 0);
let homeDist = 400;
function home() {
  const t = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
  homeDist = Math.max((maxH / 2 + 9) / t, (totalW / 2 + 6) / (t * camera.aspect));
  controls.maxDistance = homeDist * 1.6;
  controls.target.copy(centre);
  camera.position.set(centre.x + homeDist * num('az', 0), centre.y, homeDist);
  if (Q.has('at')) {  // ?at=length,row,col,distance for looking closely
    const [j, r, c, d] = Q.get('at').split(',').map(Number), l = lengths[j];
    controls.target.set(l.x0 - PW / 2 + c * CELL, -r * CELL, 0);
    camera.position.set(controls.target.x + d * num('az', 0), controls.target.y, d);
  }
  controls.update();
}
function resize() {
  renderer.setSize(innerWidth, innerHeight);
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
}
addEventListener('resize', resize); resize(); home();
document.getElementById('home').onclick = () => { Q.delete('at'); home(); };

// ---- every stitch explains itself -------------------------------------------------------------------
const $ = id => document.getElementById(id), esc = s => String(s).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
$('meta').textContent = `${N.toLocaleString()} sentences, ${people.length} people, read by ${B.run.model}. Click any stitch.`;
$('legend-model').textContent = B.run.model;
$('rules').innerHTML = Object.entries(RULES).map(([k, v]) => `<li value="${k.slice(1)}">${esc(v)}</li>`).join('');
const legend = $('legend'), panel = $('panel'), tip = $('tip');
$('legend-btn').onclick = () => { legend.hidden = !legend.hidden; };
legend.querySelector('.close-legend').onclick = () => { legend.hidden = true; };
$('close').onclick = () => { panel.hidden = true; meshes.forEach(m => { m.material.uniforms.pick.value.w = 0; }); };

const ray = new THREE.Raycaster(), mouse = new THREE.Vector2();
function stitchAt(e) {
  mouse.set((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1);
  ray.setFromCamera(mouse, camera);
  const hit = ray.intersectObjects(meshes)[0];
  if (!hit) return null;
  const { w, j } = hit.object.userData, c = Math.min(E - 1, Math.floor(hit.uv.x * E)), r = Math.min(w.R - 1, Math.floor((1 - hit.uv.y) * w.R));
  const row = r < w.rows.length ? w.rows[r] : { fringe: true };
  return { j, c, r, row, col: cols[c], mesh: hit.object };
}
const sentence = i => { const p = P[S.passage[i]]; return TXT.passages[p.id].slice(S.start[i] - p.start, S.end[i] - p.start).replace(/\s*\r?\n\s*/g, ' '); };
const quote = spans => p => spans.slice(0, 3).map(([a, b]) => `<blockquote>${esc(TXT.passages[p.id].slice(a - p.start, b - p.start).replace(/\s*\r?\n\s*/g, ' '))}</blockquote>`).join('');
const sw = c => `<span class="sw" style="background:rgb(${c.map(Math.round).join(',')})"></span>`;
const rule = k => `<div class="rule"><b>Rule ${k}.</b> ${esc(RULES[k])}</div>`;
const threadOf = col => col.type === 'person' ? people[col.who] : null;

function tipText(h) {
  if (h.row.fringe) return threadOf(h.col) ? `${threadOf(h.col).name}: loose ends` : 'loose ends';
  if (h.row.chapter !== undefined) return `Chapter ${B.chapters[h.row.chapter].label} begins`;
  const i = h.row.s, p = P[S.passage[i]], who = threadOf(h.col);
  const what = who ? `${who.name}${S.people[i].includes(who.i) ? ', named here' : ''}` : h.col.type === 'edge' ? p.at.place : '';
  return `Ch. ${B.chapters[p.chapter - 1].label}, sentence ${(i + 1).toLocaleString()}${what ? ' · ' + what : ''}`;
}

function explain(h) {
  const body = $('panel-body'), who = threadOf(h.col);
  meshes.forEach(m => { m.material.uniforms.pick.value.set(h.r, who ? who.c0 : h.c, who ? who.c1 : h.c, m === h.mesh && !h.row.fringe ? 1 : 0); });
  const thread = who ? `<h3>This thread</h3><p>${sw(who.dye)}<b>${esc(who.name)}</b>: ${who.ends} threads wide, from ${who.mentions} verified mentions. The reader verified these names for them: ${who.names.map(esc).join(', ')}.</p>` : '';
  if (h.row.fringe) { body.innerHTML = `<h2>Loose ends</h2>${thread || '<p>Binding and edge threads.</p>'}${rule('W7')}${rule('W2')}`; panel.hidden = false; return; }
  if (h.row.chapter !== undefined) { body.innerHTML = `<h2>Chapter ${B.chapters[h.row.chapter].label}</h2><p class="kicker">A pale pass of weft marks where the chapter begins.</p>${rule('W1')}`; panel.hidden = false; return; }
  const i = h.row.s, p = P[S.passage[i]], ch = B.chapters[p.chapter - 1], span = [S.start[i], S.end[i]];
  const named = S.people[i].map(k => people[k]);
  let html = `<h2>Chapter ${ch.label} · ${esc(p.at.place)}</h2>
    <p class="kicker">Sentence ${(i + 1).toLocaleString()} of ${N.toLocaleString()}, ${S.speech[i] ? 'speech' : 'narration'}, ${S.words[i]} words</p>
    <blockquote class="this">${esc(sentence(i))}</blockquote>`;
  if (who) html += thread + `<p>${S.people[i].includes(who.i) ? 'Lifted over the weft here, because this sentence names them.' : 'Covered by the weft here: this sentence does not name them.'}</p>${rule('W3')}`;
  if (named.length) html += `<h3>Named in this sentence</h3><p>${named.map(q => sw(q.dye) + esc(q.name)).join(' &nbsp; ')}</p>`;
  for (const t of gold.get(i) || []) html += `<h3>${t.meeting.kind === 'quarrel' ? 'Silver' : t.meeting.kind === 'proposal' ? 'White' : 'Gold'} thread: ${esc(t.meeting.kind)}</h3>
    <p>${esc(t.meeting.summary)}</p><p class="fact">${t.meeting.fact} · ${t.who.map(k => esc(people[k].name)).join(', ')}</p>${rule('W6')}`;
  html += `<h3>The colour of this pass</h3><p>${sw(weft(p.tension, p.warmth, S.speech[i]))}Tension ${p.tension}, warmth ${p.warmth} for this passage. ${p.tone ? esc(p.tone.reason) : ''}</p>
    ${p.tone ? `<p class="fact">${p.tone.fact} · the reader cited:</p>${quote(p.tone.spans)(p)}` : ''}${rule('W4')}`;
  const pl = placeIndex[p.at.place] ?? 0;
  html += `<h3>The edge and the ground weave</h3><p>${sw(PLACE[pl % PLACE.length])}<b>${esc(p.at.place)}</b>, woven in ${WEAVE_NAMES[pl % WEAVE_NAMES.length]}. ${p.at.how === 'carried' ? `The reader called this passage '${esc(p.place.setting)}', so it keeps the place before it. ` : ''}Basis: ${esc(p.place.basis || '')}. ${esc(p.place.rationale || '')}</p>
    ${(p.place.flags || []).map(f => `<p class="flag">Flagged: ${esc(f)}</p>`).join('')}${rule('W5')}`;
  const cites = [];
  const has = spans => spans.some(([a, b]) => a === span[0] && b === span[1]);
  for (const q of p.people) if (has(q.spans)) cites.push(`${esc(people.find(x => x.id === q.id)?.name || q.id)} is here, called ${q.called.map(esc).join(', ')} <span class="fact">${q.facts.join(' ')}</span>`);
  for (const e of p.events) if (has(e.spans)) cites.push(`${esc(e.summary)} <span class="fact">${e.fact}</span>`);
  for (const o of p.objects) if (has(o.spans)) cites.push(`Object: ${esc(o.name)} <span class="fact">${o.fact}</span>`);
  html += `<h3>What the reader took from this sentence</h3>${cites.length ? `<ul>${cites.map(c => `<li>${c}</li>`).join('')}</ul>` : '<p>No accepted fact cites this sentence.</p>'}
    <button class="link" id="read">Read the whole passage</button><div id="passage"></div>`;
  body.innerHTML = html; panel.hidden = false; panel.scrollTop = 0;
  $('read').onclick = () => {
    const t = TXT.passages[p.id], a = span[0] - p.start, b = span[1] - p.start;
    $('passage').innerHTML = `<p class="fact">${p.id}</p><div class="passage">${esc(t.slice(0, a))}<mark>${esc(t.slice(a, b))}</mark>${esc(t.slice(b))}</div>`;
    $('read').remove();
  };
}

let down = null;
renderer.domElement.addEventListener('pointerdown', e => { down = [e.clientX, e.clientY]; });
renderer.domElement.addEventListener('pointerup', e => {
  if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5 || e.button !== 0) return;
  const h = stitchAt(e); if (h) explain(h);
});
renderer.domElement.addEventListener('pointermove', e => {
  const h = e.buttons ? null : stitchAt(e);
  tip.hidden = !h;
  if (h) { tip.textContent = tipText(h); tip.style.left = e.clientX + 'px'; tip.style.top = e.clientY + 'px'; }
});
renderer.domElement.addEventListener('pointerleave', () => { tip.hidden = true; });
renderer.domElement.addEventListener('contextmenu', e => e.preventDefault());

const clock = new THREE.Clock();
(function frame() {
  const t = clock.getElapsedTime();
  light.set(-0.45 + 0.22 * Math.sin(t * 0.25), 0.55 + 0.08 * Math.sin(t * 0.17), 0.7);
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
})();
window.weave = { B, people, cols, lengths, explain, stitchAt, gold, camera, controls };
