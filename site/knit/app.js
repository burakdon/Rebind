// The knitting pattern (pattern.json, written by `rebind knit`) worked on screen, stitch by stitch.
// This file decides nothing about the book: it draws the rows the pattern gives and explains them.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { chosen, dye, loadPalettes, picker } from '../palette.js';

const Q = new URLSearchParams(location.search);
const num = (k, d) => (Q.has(k) ? parseFloat(Q.get(k)) : d);
const BOOK = Q.get('book') || 'pride-and-prejudice', DATA = `../data/${BOOK}/`;
const [K, B, TXT] = await Promise.all(['pattern.json', 'book.json', 'text.json'].map(f => fetch(DATA + f).then(r => r.json())));
const PALETTES = await loadPalettes('../data/'), OWN_DYE = K.palette?.name;
dye(K, PALETTES, chosen());   // the visitor's choice of colours; the book's own unless they picked another
const CHECKS = await fetch(DATA + 'checks.json').then(r => r.ok ? r.json() : null).catch(() => null);
await Promise.all([document.fonts.load('32px "IM Fell English SC"'), document.fonts.load('italic 32px "IM Fell English"')]).catch(() => {});
const passage = Object.fromEntries(B.passages.map(p => [p.id, p]));
const person = Object.fromEntries(B.people.map(p => [p.id, p]));
const yarn = Object.fromEntries(K.yarns.map(y => [y.key, y]));
const hex = h => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];

// ---- the fabric: one texel per stitch ----------------------------------------------------------------
// Two rows per passage. Seen from the right side: the right-side row is knit stitches (V) with eyelets;
// the row back shows as V again where it was purled (smooth) and as bumps where it was knitted (ridged).
const W = K.cast_on, R = K.rows.length * 2, TABLE = [14, 11, 9];
const V = 0, BUMP = 1, HOLE = 2, LEAN = 3;
const shown = new Uint8Array(W * R * 4), stitch = new Uint8Array(W * R * 4), rowH = new Float32Array(R);
K.rows.forEach((row, n) => {
  const col = hex(yarn[row.yarn].hex), ridged = row.texture === 'ridged', h = ridged ? 0.5 : 0.75;
  for (let half = 0; half < 2; half++) {
    const r = n * 2 + half; rowH[r] = h;
    for (let c = 0; c < W; c++) {
      const sym = row.rs[c], edge = c < K.edge || c >= W - K.edge;
      const kind = half === 0 ? (sym === 'o' ? HOLE : sym === '/' ? LEAN : V) : (ridged || edge ? BUMP : V);
      const o = (r * W + c) * 4, dim = kind === HOLE ? 0 : kind === BUMP ? 0.8 : 1;
      for (let k = 0; k < 3; k++) { shown[o + k] = kind === HOLE ? TABLE[k] : col[k] * dim; stitch[o + k] = col[k]; }
      shown[o + 3] = 255; stitch[o + 3] = kind * 32 + (ridged ? 128 : 0);
    }
  }
});
const along = new Float32Array(R + 1);
for (let r = 0; r < R; r++) along[r + 1] = along[r] + rowH[r];
const LEN = along[R];

// ---- the scarf laid in a hairpin, or flat if the book is short ----------------------------------------
const TURN = num('turn', 40), FLAT = Q.has('flat') ? Q.get('flat') !== '0' : LEN < 2.5 * Math.PI * TURN;
const RUN = (LEN - Math.PI * TURN) / 2, X0 = FLAT ? LEN / 2 : RUN / 2, Y0 = FLAT ? 0 : TURN;
function centre(s) {  // -> [x, y, tx, ty]
  if (FLAT) return [-X0 + s, 0, 1, 0];
  if (s < RUN) return [-X0 + s, TURN, 1, 0];
  if (s < RUN + Math.PI * TURN) { const a = Math.PI / 2 - (s - RUN) / TURN; return [X0 + TURN * Math.cos(a), TURN * Math.sin(a), Math.sin(a), -Math.cos(a)]; }
  return [X0 - (s - RUN - Math.PI * TURN), -TURN, -1, 0];
}
function ribbon(extra = 0, z = 0) {
  const ACROSS = 14, pos = [], uv = [], idx = [];
  for (let r = 0; r <= R; r++) {
    const [x, y, tx, ty] = centre(along[r]);
    for (let a = 0; a <= ACROSS; a++) {
      const u = a / ACROSS, t = (u - 0.5) * (W + extra);
      const wave = extra ? 0 : 0.45 * Math.sin(along[r] * 0.09 + u * 2.6) + 0.35 * Math.sin(along[r] * 0.031 + 1.7) + 0.5 * Math.pow(Math.abs(u - 0.5) * 2, 6);
      pos.push(x - ty * t, y + tx * t, z + wave); uv.push(u, r / R);
    }
  }
  for (let r = 0; r < R; r++) for (let a = 0; a < ACROSS; a++) {
    const i = r * (ACROSS + 1) + a, j = i + ACROSS + 1;
    idx.push(i, i + 1, j, i + 1, j + 1, j);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx); g.computeVertexNormals();
  return g;
}

const stage = document.getElementById('stage');
const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
stage.appendChild(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0d0c0b);
const camera = new THREE.PerspectiveCamera(28, 1, 0.5, 4000);
// On a tall screen the view is turned a quarter, so the scarf hangs down it with the cast-on edge at the top.
const TALL = Q.has('tall') ? Q.get('tall') !== '0' : innerWidth / innerHeight < 0.8;
if (TALL) camera.up.set(-1, 0, 0);

const map = new THREE.DataTexture(shown, W, R, THREE.RGBAFormat);
map.colorSpace = THREE.SRGBColorSpace; map.generateMipmaps = true; map.minFilter = THREE.LinearMipmapLinearFilter; map.magFilter = THREE.LinearFilter;
map.anisotropy = renderer.capabilities.getMaxAnisotropy(); map.needsUpdate = true;
const kinds = new THREE.DataTexture(stitch, W, R, THREE.RGBAFormat);
kinds.colorSpace = THREE.SRGBColorSpace; kinds.minFilter = kinds.magFilter = THREE.NearestFilter; kinds.needsUpdate = true;

const vert = `varying vec2 vUv; varying vec3 vP; varying vec3 vN;
  void main(){ vUv = uv; vec4 w = modelMatrix * vec4(position, 1.); vP = w.xyz; vN = normalize(mat3(modelMatrix) * normal);
    gl_Position = projectionMatrix * viewMatrix * w; }`;
const frag = `uniform sampler2D map, kinds; uniform vec2 grid; uniform vec3 light; uniform vec2 pick;
  varying vec2 vUv; varying vec3 vP; varying vec3 vN;
  float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  // distance from p to segment ab, and how far along it
  vec2 seg(vec2 p, vec2 a, vec2 b){ vec2 pa = p - a, ba = b - a; float h = clamp(dot(pa, ba) / dot(ba, ba), 0., 1.); return vec2(length(pa - ba * h), h); }
  vec4 cell(vec2 c){ return texelFetch(kinds, ivec2(clamp(c, vec2(0.), grid - 1.)), 0); }
  float kindOf(vec4 t){ return floor(mod(floor(t.a * 255. + .5), 128.) / 32. + .5); }
  float heightOf(vec4 t){ return t.a > 0.5 ? 0.5 : 0.75; }
  // one strand of yarn: returns coverage in .x, roundness in .y
  void strand(vec2 p, vec2 a, vec2 b, float rad, vec3 yarn, float seed, inout vec4 best, inout vec2 tilt){
    vec2 d = seg(p, a, b);
    if (d.x < rad) {
      float round_ = sqrt(1. - (d.x / rad) * (d.x / rad));
      if (round_ > best.a) {
        vec2 ab = normalize(b - a), n = vec2(-ab.y, ab.x);
        float side = dot(p - a, n) / rad;
        float ply = 0.5 + 0.5 * sin((d.y * length(b - a) * 5.5 + side * 0.9 + seed) * 6.2832);
        best = vec4(yarn * (0.74 + 0.2 * ply + 0.1 * hash(floor(p * 23.) + seed)), round_);
        tilt = n * side;
      }
    }
  }
  void stitchAt(vec2 c, vec2 p, inout vec4 best, inout vec2 tilt){
    vec4 t = cell(c); float k = kindOf(t), h = heightOf(t), seed = hash(c);
    if (k < 0.5 || k > 2.5) {       // a knit stitch is a V; knit-two-together leans
      float lean = k > 2.5 ? 0.22 : 0.;
      strand(p, vec2(0.5, -0.3 * h), vec2(0.07 + lean, 1.08 * h), 0.215, t.rgb, seed, best, tilt);
      strand(p, vec2(0.5, -0.3 * h), vec2(0.93 + lean, 1.08 * h), 0.215, t.rgb, seed + 3., best, tilt);
    } else if (k < 1.5) {           // the back of a knitted row: bumps
      strand(p, vec2(0.12, 0.7 * h), vec2(0.88, 0.7 * h), 0.2, t.rgb, seed, best, tilt);
      strand(p, vec2(-0.38, 0.22 * h), vec2(0.38, 0.22 * h), 0.2, t.rgb, seed + 5., best, tilt);
      strand(p, vec2(0.62, 0.22 * h), vec2(1.38, 0.22 * h), 0.2, t.rgb, seed + 7., best, tilt);
    }
  }
  void main(){
    vec2 g = vUv * grid, c = floor(g), f = fract(g), fw = fwidth(g);
    float detail = 1. - smoothstep(0.07, 0.26, max(fw.x, fw.y));
    vec3 N = normalize(vN); if (!gl_FrontFacing) N = -N;
    vec3 dpx = dFdx(vP), dpy = dFdy(vP); vec2 dux = dFdx(vUv), duy = dFdy(vUv);
    vec3 Tu = normalize(dpx * duy.y - dpy * dux.y), Tv = normalize(dpy * dux.x - dpx * duy.x);
    vec3 V = normalize(cameraPosition - vP), L = normalize(light);
    vec3 far = texture2D(map, vUv).rgb;
    float d0 = max(0., (dot(N, L) + 0.55) / 1.55);
    vec3 col = far * (0.3 + 0.9 * d0);
    if (detail > 0.) {
      vec4 me = cell(c); float k = kindOf(me), h = heightOf(me);
      vec2 p = vec2(f.x, f.y * h);
      vec4 best = vec4(me.rgb * 0.2, 0.); vec2 tilt = vec2(0.);
      float hole = 0.;
      if (k > 1.5 && k < 2.5) {     // yarn over: a real hole, ringed by the strand that made it
        float e = length((p - vec2(0.5, 0.5 * h)) / vec2(0.36, 0.36 * h / 0.6));
        if (e < 1.) hole = 1.;
        else { best = vec4(me.rgb * (0.55 + 0.3 * smoothstep(1.5, 1., e)), 0.6 * smoothstep(1.6, 1., e)); tilt = normalize(p - vec2(0.5, 0.5 * h)) * 0.6; }
      } else stitchAt(c, p, best, tilt);
      // the row above overlaps the top of this one; the stitches either side reach in a little
      vec4 up = cell(c + vec2(0., 1.));
      if (c.y + 1. < grid.y) stitchAt(c + vec2(0., 1.), vec2(f.x, f.y * h - h), best, tilt);
      stitchAt(c + vec2(-1., 0.), vec2(f.x + 1., f.y * h), best, tilt);
      stitchAt(c + vec2(1., 0.), vec2(f.x - 1., f.y * h), best, tilt);
      if (hole > 0.5 && best.a < 0.05) { if (detail > 0.5) discard; best = vec4(${TABLE.map(v => (v / 255).toFixed(3)).join(', ')}, 0.); }
      vec3 Nm = normalize(N + (Tu * tilt.x + Tv * tilt.y) * 1.1);
      float d = max(0., (dot(Nm, L) + 0.55) / 1.55);
      float sp = pow(max(0., dot(Nm, normalize(L + V))), 14.) * 0.1;
      vec3 near = best.rgb * (0.2 + 0.8 * best.a) * (0.3 + 0.95 * d) + sp + best.rgb * 0.12 * pow(1. - best.a, 3.) * step(0.01, best.a);
      col = mix(col, near, detail);
    }
    if (pick.y > .5 && floor(c.y / 2.) == pick.x) col = col * 1.3 + 0.08;
    gl_FragColor = vec4(col, 1.);
    #include <colorspace_fragment>
  }`;
const light = new THREE.Vector3(-0.5, 0.6, 0.65);
const scarf = new THREE.Mesh(ribbon(), new THREE.ShaderMaterial({ vertexShader: vert, fragmentShader: frag, side: THREE.DoubleSide,
  uniforms: { map: { value: map }, kinds: { value: kinds }, grid: { value: new THREE.Vector2(W, R) }, light: { value: light }, pick: { value: new THREE.Vector2(0, 0) } } }));
scene.add(scarf);
const shadow = new THREE.Mesh(ribbon(9, -1.4), new THREE.ShaderMaterial({ transparent: true, depthWrite: false,
  vertexShader: 'varying vec2 u; void main(){ u = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }',
  fragmentShader: 'varying vec2 u; void main(){ float d = smoothstep(0., 0.14, u.x) * smoothstep(0., 0.14, 1. - u.x) * smoothstep(0., 0.004, u.y) * smoothstep(0., 0.004, 1. - u.y); gl_FragColor = vec4(0., 0., 0., 0.7 * d); }' }));
shadow.position.set(1.6, -1.6, 0); scene.add(shadow);
const table = new THREE.Mesh(new THREE.PlaneGeometry(3000, 2000), new THREE.ShaderMaterial({
  uniforms: { s: { value: new THREE.Vector2(X0 + TURN * 1.6, FLAT ? TURN * 1.6 : TURN * 2.6) } },
  vertexShader: 'varying vec2 p; void main(){ p = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }',
  fragmentShader: `uniform vec2 s; varying vec2 p; void main(){ float d = length(p / s);
    vec3 col = mix(vec3(0.03, 0.024, 0.019), vec3(0.004, 0.004, 0.004), smoothstep(0.35, 1.6, d));
    gl_FragColor = vec4(col, 1.);
    #include <colorspace_fragment>
  }` }));
table.position.z = -1.6; scene.add(table);

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
// chapter numerals beside the edge that carries the chapter eyelets (K6); names at the cast-on end (K4)
K.rows.forEach((row, n) => {
  if (!row.starts_chapter) return;
  const [x, y, tx, ty] = centre((along[n * 2] + along[n * 2 + 2]) / 2), m = label(row.chapter_label, 1.7, '#9d917c'), off = W / 2 + 1.8;
  m.position.set(x + ty * off, y - tx * off, 0.2); m.rotation.z = TALL ? Math.PI / 2 : Math.atan2(ty, tx) + (tx < -0.01 ? Math.PI : 0);
  scene.add(m);
});
for (const c of K.columns) {
  const m = label(c.name, 2.1, '#cdbf9f', '"IM Fell English"', 'italic'), u = (c.stitches[0] + 0.5) / W;
  m.position.set(-X0 - 1.8 - m.userData.w / 2, Y0 + (u - 0.5) * W, 0.2); scene.add(m);
}
const cast = label('cast on', 1.8, '#8f8370'); cast.position.set(-X0 - 1.8 - cast.userData.w / 2, Y0 + W / 2 + 1.6, 0.2); scene.add(cast);
const bind = label('bind off', 1.8, '#8f8370'); bind.position.set(FLAT ? X0 + 1.8 + bind.userData.w / 2 : -X0 - 1.8 - bind.userData.w / 2, -Y0, 0.2); scene.add(bind);

// ---- camera ---------------------------------------------------------------------------------------------
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.dampingFactor = 0.08; controls.zoomToCursor = true; controls.screenSpacePanning = true;
controls.mouseButtons = { LEFT: THREE.MOUSE.PAN, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.ROTATE };
controls.touches = { ONE: THREE.TOUCH.PAN, TWO: THREE.TOUCH.DOLLY_ROTATE };
controls.minDistance = 6; controls.minAzimuthAngle = -1.1; controls.maxAzimuthAngle = 1.1; controls.minPolarAngle = 0.6; controls.maxPolarAngle = 2.4;
function home() {
  const t = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)), halfW = FLAT ? X0 + 20 : X0 + TURN + W / 2 + 16, halfH = FLAT ? W / 2 + 14 : TURN + W / 2 + 9;
  const cx = FLAT ? -5 : TURN / 2 - 6;
  // tall: the scarf's length runs down the screen, and the title and buttons take the top and bottom of it
  const dist = TALL ? Math.max(halfW * 1.38 / t, halfH / (t * camera.aspect)) : Math.max(halfH / t, halfW / (t * camera.aspect));
  controls.maxDistance = dist * 1.6;
  controls.target.set(cx, 0, 0);
  camera.position.set(cx + dist * num('az', 0), -dist * num('el', 0), dist);
  if (Q.has('at')) {  // ?at=pair,stitch,distance for looking closely
    const [n, c, d] = Q.get('at').split(',').map(Number), [x, y, tx, ty] = centre(along[n * 2]), tt = (c / W - 0.5) * W;
    controls.target.set(x - ty * tt, y + tx * tt, 0);
    camera.position.set(controls.target.x + d * num('az', 0), controls.target.y - d * num('el', 0), d);
  }
  controls.update();
}
function resize() { renderer.setSize(innerWidth, innerHeight); camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); }
addEventListener('resize', resize); resize(); home();
document.getElementById('home').onclick = () => { Q.delete('at'); home(); };

// ---- every row explains itself -----------------------------------------------------------------------------
const $ = id => document.getElementById(id), esc = s => String(s).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
const S = K.size, CW = K.book.chapter_word || 'Chapter';
document.title = `Rebind · ${K.book.title}, knitted`; $('title').textContent = K.book.title;
for (const a of document.querySelectorAll('#tools a')) a.href = `pattern.html?book=${BOOK}`;
$('meta').textContent = `${S.pairs} passages, ${S.rows} rows, about ${Math.round(S.width_in)} × ${S.length_in} inches. Click any row to unravel it.`;
$('key').innerHTML = `<span>cold</span>${'ABCDE'.split('').map(k => `<i style="background:${yarn[k].hex}" title="yarn ${k}, ${yarn[k].name}"></i>`).join('')}<span>warm</span>
  <span class="gap"><i style="background:${yarn.U.hex}"></i>the two readings too far apart</span><span class="gap">ridge: tense</span><span class="gap">hole: that person is there</span>`;
$('legend-model').textContent = K.run.model;
picker($('palette'), PALETTES, 'This book’s own');
if (K.palette) $('dye').textContent = `The colours here are “${K.palette.name}”${K.palette.borrowed ? `, borrowed from another book (this book’s own are “${OWN_DYE}”)` : `, after ${K.palette.from}`}. ${K.palette.note} You can change them at the top of the page; no stitch moves.`;
$('rules').innerHTML = Object.entries(K.rules).map(([k, v]) => `<li value="${k.slice(1)}">${esc(v)}</li>`).join('');
const legend = $('legend'), panel = $('panel'), tip = $('tip');
// How far to trust it: the counted checks, in plain words.
(function sure() {
  const c = CHECKS, per = v => Math.round(100 * v) + ' in 100', unsure = K.rows.filter(r => r.unsure).length;
  const near = K.rows.filter(r => !r.unsure && r.gap === 1).length, same = K.rows.filter(r => r.gap === 0).length;
  let h = `<h2>How sure is it</h2>` + (K.readings.twice
    ? `<p>Counted apart, the two readings pick the same yarn for ${same} of ${K.rows.length} passages and neighbouring yarns for ${near}; those are knitted in the yarn of both readings together. The other ${unsure} are two or more yarns apart and are knitted undyed.</p>`
    : `<p>The book has been read once so far, so nothing here checks whether the labels depend on how the question was put.</p>`);
  if (c?.stability) h += `<p><b>Asked twice in different words,</b> the reader gives a sentence the same feeling ${per(c.stability.feeling.same)} times and the same pace ${per(c.stability.pace.same)} times. A passage gets the same yarn ${per(c.stability.rows.yarn.same)} times and the same or a neighbouring yarn ${per(c.stability.rows.yarn_within_one)}.</p>`;
  if (c?.memory && c.readings['a-swapped'] >= c.readings.a) h += `<p><b>With every name swapped for a neutral one,</b> a sentence keeps its feeling ${per(c.memory.feeling.same)} times and its pace ${per(c.memory.pace.same)} times. ${c.stability && c.memory.feeling.same >= c.stability.feeling.same ? 'That is less movement than rewording the question causes, so there is no sign here that the reader leans on recognising the names. It cannot rule out that the reader knows the text itself.' : 'That is more movement than rewording the question causes, which suggests the reader leans on recognising the names.'}</p>`;
  for (const o of Object.values(c?.other || {})) h += `<p><b>Against a different model</b> (${esc(o.model)}, asked the same question${o.passages < o.of ? `, on ${o.passages} of ${o.of} passages so far` : ''}): the same feeling ${per(o.feeling.same)} times and the same pace ${per(o.pace.same)} times, and the same or a neighbouring yarn ${per(o.rows.yarn_within_one)}. Two models agreeing does not make either right, but this check does not depend on the main reader.</p>`;
  if (c?.hand) h += `<p><b>Against a person,</b> who labelled ${c.hand.sentences} sentences without seeing the reader's answers: the same feeling ${per(c.hand.a.feeling.same)} times and the same pace ${per(c.hand.a.pace.same)} times.</p>`;
  else h += `<p><b>Against a person:</b> not checked. No one has labelled a sample by hand, so these numbers say how steady the labels are, not whether they are right. <a href="check.html?book=${BOOK}">Anyone can label a sample here.</a></p>`;
  const d = document.createElement('div'); d.innerHTML = h; legend.insertBefore(d, legend.querySelector('.hint'));
})();
$('legend-btn').onclick = () => { legend.hidden = !legend.hidden; };
legend.querySelector('.close-legend').onclick = () => { legend.hidden = true; };
$('close').onclick = () => { panel.hidden = true; scarf.material.uniforms.pick.value.y = 0; };
const sw = h => `<span class="sw" style="background:${h}"></span>`;
const rule = k => `<div class="rule"><b>Rule ${k}.</b> ${esc(K.rules[k])}</div>`;
const quotes = (p, spans, n = 2) => spans.slice(0, n).map(([a, b]) => `<blockquote>${esc(TXT.passages[p.id].slice(a - p.start, b - p.start).replace(/\s*\r?\n\s*/g, ' '))}</blockquote>`).join('');

const FEEL = ['neither', 'warm', 'cold'], PACE = ['calm', 'tense'], CHIP = ['#9c978c', '#c8745f', '#35548c'];
const pct = (a, n) => Math.round(100 * a / n);
function sum(t, unit = 'sentences') {
  const d = t.warm - t.cold;
  return `${t.n} ${unit}: ${t.warm} warm, ${t.cold} cold, ${t.neither} neither. (${t.warm} − ${t.cold}) ÷ ${t.n} = ${(d / t.n).toFixed(2).replace('-', '−')}, which is yarn ${t.yarn}.`;
}
function why(r) {
  const a = r.tally.a, b = r.tally.b, t = r.tally.both, y = yarn[r.yarn];
  if (!t) return `<h3>Why this yarn</h3><p>${sw(y.hex)}The reader gave no usable labels for this passage, so it is undyed.</p>${rule('K7')}`;
  let h = `<h3>Why this yarn</h3>`;
  if (b) {
    h += `<p>${sw(yarn[a.yarn].hex)}<b>First reading.</b> ${sum(a)}</p><p>${sw(yarn[b.yarn].hex)}<b>Second reading.</b> ${sum(b)}</p>
      <p>${sw(yarn[t.yarn].hex)}<b>Both together.</b> ${sum(t, 'labels')}</p>
      <p>${sw(y.hex)}${r.unsure ? `Counted apart, the readings pick yarns ${a.yarn} and ${b.yarn}, which are ${r.gap} apart. That is too far, so the row is knitted undyed and the scarf makes no claim here.`
        : r.gap === 0 ? `Counted apart, both readings pick yarn ${a.yarn} too, so the row is knitted in yarn ${r.yarn} (${esc(y.name)}).`
        : `Counted apart, the readings pick neighbouring yarns, ${a.yarn} and ${b.yarn}, so the row is knitted in the yarn of both together, ${r.yarn} (${esc(y.name)}).`}</p>`;
  } else h += `<p>${sw(y.hex)}${sum(a)}</p>`;
  if (r.margin) h += `<p>Change ${r.margin === 1 ? 'one label' : r.margin + ' labels'} out of ${t.n} and the count would pick a different yarn.</p>`;
  h += `${rule('K2')}${rule('K7')}<h3>Why it is ${r.texture}</h3>
    <p>${t.tense} of ${t.n} ${b ? 'labels' : 'sentences'} are tense (${pct(t.tense, t.n)} in 100)${b ? `: ${a.tense} of ${a.n} in the first reading and ${b.tense} of ${b.n} in the second` : ''}. A ridge needs ${Math.round(K.ridged_share * 100)} in 100, so the row back is ${r.texture === 'ridged' ? 'knitted and leaves a ridge' : 'purled and the fabric is smooth'}.</p>${rule('K3')}`;
  return h;
}
function unravel(r, p) {
  const S = B.sentences, [s0, sn] = p.sentences;
  let h = '';
  for (let i = s0; i < s0 + sn; i++) {
    const f = S.feeling[i], pc = S.pace[i], fb = S.feeling_b[i], pb = S.pace_b[i];
    const text = TXT.passages[p.id].slice(S.start[i] - p.start, S.end[i] - p.start).replace(/\s*\r?\n\s*/g, ' ');
    const differs = fb >= 0 && (fb !== f || pb !== pc);
    h += `<blockquote style="border-left:5px solid ${f >= 0 ? CHIP[f] : '#efe6d0'}">${esc(text)}<br><span class="fact">${f >= 0 ? `${FEEL[f]}, ${PACE[pc]}` : 'no label'}${differs ? ` · second reading: ${FEEL[fb]}, ${PACE[pb]}` : ''}</span></blockquote>`;
  }
  return h;
}
const ray = new THREE.Raycaster(), mouse = new THREE.Vector2();
function rowAt(e) {
  mouse.set((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1);
  ray.setFromCamera(mouse, camera);
  const hit = ray.intersectObject(scarf)[0];
  if (!hit) return null;
  const n = Math.min(K.rows.length - 1, Math.floor(hit.uv.y * R / 2)), c = Math.min(W - 1, Math.floor(hit.uv.x * W));
  return { n, c, row: K.rows[n], column: K.columns.find(q => c + 1 >= q.stitches[0] - 1 && c + 1 <= q.stitches[1]) };
}
function tipText(h) {
  const r = h.row, who = r.eyelets.map(e => person[e.person].name);
  const col = h.column ? ` · ${h.column.name}${who.includes(h.column.name) ? ': eyelet' : ': plain'}` : '';
  return `Rows ${r.n * 2 - 1}–${r.n * 2} · ${CW} ${r.chapter_label} · yarn ${r.yarn}${r.unsure ? ' (unsure)' : ''}, ${r.texture}${col}`;
}
function explain(h) {
  const r = h.row, p = passage[r.passage], y = yarn[r.yarn];
  scarf.material.uniforms.pick.value.set(h.n, 1);
  let html = `<h2>${CW} ${r.chapter_label}${p.at?.place ? ' · ' + esc(p.at.place) : ''}</h2>
    <p class="kicker">Rows ${r.n * 2 - 1} and ${r.n * 2} of ${S.rows}: passage ${r.n} of ${S.pairs} <span class="fact">${r.passage}</span></p>
    <div class="rows">With yarn ${r.yarn} (${esc(y.name)}):<br>Row ${r.n * 2 - 1} (RS): ${esc(r.rs_text)}.<br>Row ${r.n * 2} (WS): ${esc(r.ws_text)}.</div>
    ${why(r)}
    <h3>The eyelets</h3>`;
  if (r.starts_chapter) html += `<p>Stitches 2–3: the chapter begins here.</p>${rule('K6')}`;
  if (!r.eyelets.length) html += `<p>None. The reader has no verified fact that names one of the ten people in this passage. A passage that only says "he" or "she" leaves no eyelet.</p>`;
  for (const e of r.eyelets) {
    const c = K.columns.find(q => q.person === e.person);
    html += `<p><b>${esc(c.name)}</b>, stitches ${c.stitches.join('–')}: called ${e.called.map(x => `“${esc(x)}”`).join(', ')} here. <span class="fact">${e.facts.join(' ')}</span></p>${quotes(p, e.spans, 1)}`;
  }
  html += `${rule('K5')}<h3>Unravel this row</h3><p>Every sentence of the passage, with the label the reader gave it. These are what the tallies above count.</p>${unravel(r, p)}`;
  $('panel-body').innerHTML = html; panel.hidden = false; panel.scrollTop = 0;
}
let down = null;
renderer.domElement.addEventListener('pointerdown', e => { down = [e.clientX, e.clientY]; });
renderer.domElement.addEventListener('pointerup', e => {
  if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5 || e.button !== 0) return;
  const h = rowAt(e); if (h) explain(h);
});
renderer.domElement.addEventListener('pointermove', e => {
  const h = e.buttons ? null : rowAt(e);
  tip.hidden = !h;
  if (h) { tip.textContent = tipText(h); tip.style.left = e.clientX + 'px'; tip.style.top = e.clientY + 'px'; }
});
renderer.domElement.addEventListener('pointerleave', () => { tip.hidden = true; });
renderer.domElement.addEventListener('contextmenu', e => e.preventDefault());

const clock = new THREE.Clock();
(function frame() {
  const t = clock.getElapsedTime();
  light.set(-0.5 + 0.2 * Math.sin(t * 0.25), 0.6 + 0.08 * Math.sin(t * 0.17), 0.65);
  controls.update(); renderer.render(scene, camera); requestAnimationFrame(frame);
})();
window.knit = { K, explain, rowAt, camera, controls, centre, along };
