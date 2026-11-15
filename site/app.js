// Rebind viewer. It draws layout.json and nothing else: every height, line and mark
// below is computed from the facts and rules in that file, and the same formula is
// used to explain any point of ground the reader clicks.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { Line2 } from "three/addons/lines/Line2.js";
import { LineMaterial } from "three/addons/lines/LineMaterial.js";
import { LineGeometry } from "three/addons/lines/LineGeometry.js";

const SLUG = new URLSearchParams(location.search).get("book") || "pride-and-prejudice";
const ZS = 0.14;            // map units of height per point of tension
const GRID = [900, 600];    // terrain resolution (columns, rows)

await Promise.all(['96px "IM Fell English SC"', 'italic 96px "IM Fell English"'].map(f => document.fonts.load(f)));
const [L, TEXT] = await Promise.all([
  fetch(`data/${SLUG}/layout.json`).then(r => r.json()),
  fetch(`data/${SLUG}/text.json`).then(r => r.json()),
]);
const W = L.sheet.w, H = L.sheet.h;
const P = L.passages;
const bandOf = Object.fromEntries(L.bands.map(b => [b.name, b]));
const byId = Object.fromEntries(P.map((p, i) => [p.id, { ...p, i }]));
const sx = L.terrain.sigma_x, floor = L.terrain.floor;

// ---------- the terrain formula (rule L4) ----------
const smooth = (a, b, v) => { const t = Math.min(1, Math.max(0, (v - a) / (b - a))); return t * t * (3 - 2 * t); };
const envelope = (x, y) =>
  smooth(L.sheet.x0 - 0.9, L.sheet.x0 + 0.2, x) * smooth(L.sheet.x1 + 0.9, L.sheet.x1 - 0.2, x) *
  smooth(L.sheet.top - 0.8, L.sheet.top + 0.1, y) * smooth(L.sheet.bottom + 0.8, L.sheet.bottom - 0.1, y);
const near = x => {
  const i = Math.round((x - L.sheet.x0) / L.sheet.dx), r = Math.ceil(4 * sx / L.sheet.dx), out = [];
  for (let k = Math.max(0, i - r); k <= Math.min(P.length - 1, i + r); k++) out.push(P[k]);
  return out;
};
// Each passage's share of the height at (x, y). They sum to the height exactly.
function contributions(x, y) {
  const ps = near(x).filter(p => p.tension !== null);
  let gsum = 0;
  const parts = ps.map(p => {
    const g = Math.exp(-((x - p.x) ** 2) / (2 * sx * sx));
    const b = bandOf[p.band];
    const gy = Math.exp(-((y - b.y) ** 2) / (2 * L.terrain.sigma_y ** 2));
    gsum += g;
    return { p, g, gy, v: g * p.tension * (floor + (1 - floor) * gy) };
  });
  const env = envelope(x, y);
  parts.forEach(c => { c.v = gsum ? c.v / gsum * env : 0; });
  return parts;
}
const heightAt = (x, y) => contributions(x, y).reduce((s, c) => s + c.v, 0);
function warmthAt(x) {
  let s = 0, g = 0;
  for (const p of near(x)) if (p.warmth !== null) {
    const w = Math.exp(-((x - p.x) ** 2) / (2 * sx * sx)); s += w * p.warmth; g += w;
  }
  return g ? s / g : 5;
}

// ---------- scene ----------
const stage = document.getElementById("stage");
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(2, devicePixelRatio));
renderer.setSize(innerWidth, innerHeight);
renderer.setClearColor(0xefe5cf);
stage.appendChild(renderer.domElement);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(34, innerWidth / innerHeight, 0.1, 400);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.47;
controls.minDistance = 2;
controls.maxDistance = 90;
const toWorld = (x, y, h = 0) => new THREE.Vector3(x - W / 2, h, y - H / 2);

// Terrain mesh with tension (aH) and warmth (aW) carried per vertex for the shader.
function buildTerrain() {
  const [nx, ny] = GRID;
  const pos = new Float32Array((nx + 1) * (ny + 1) * 3), aH = new Float32Array((nx + 1) * (ny + 1)),
    aW = new Float32Array((nx + 1) * (ny + 1));
  for (let i = 0; i <= nx; i++) {
    const x = (i / nx) * W, warm = warmthAt(x);
    for (let j = 0; j <= ny; j++) {
      const y = (j / ny) * H, k = j * (nx + 1) + i, h = heightAt(x, y);
      pos.set([x - W / 2, h * ZS, y - H / 2], k * 3);
      aH[k] = h; aW[k] = warm;
    }
  }
  const idx = new Uint32Array(nx * ny * 6);
  let n = 0;
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    const a = j * (nx + 1) + i, b = a + 1, c = a + nx + 1, d = c + 1;
    idx.set([a, c, b, b, c, d], n); n += 6;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  g.setAttribute("aH", new THREE.BufferAttribute(aH, 1));
  g.setAttribute("aW", new THREE.BufferAttribute(aW, 1));
  g.setIndex(new THREE.BufferAttribute(idx, 1));
  g.computeVertexNormals();
  const m = new THREE.ShaderMaterial({
    vertexShader: `
      attribute float aH; attribute float aW;
      varying float vH; varying float vW; varying vec3 vN; varying vec2 vXZ;
      void main() { vH = aH; vW = aW; vN = normal; vXZ = position.xz;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `
      varying float vH; varying float vW; varying vec3 vN; varying vec2 vXZ;
      float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      void main() {
        vec3 paper = vec3(0.937, 0.898, 0.812);
        vec3 warm = vec3(0.905, 0.760, 0.560), cold = vec3(0.735, 0.800, 0.835);
        float wash = smoothstep(1.2, 3.5, vH);
        vec3 col = mix(paper, mix(cold, warm, smoothstep(2.5, 7.5, vW)), 0.55 * wash);
        vec3 L = normalize(vec3(-0.55, 0.75, -0.45));
        col *= 0.86 + 0.16 * dot(normalize(vN), L);
        float f = abs(fract(vH - 0.5) - 0.5) / fwidth(vH);
        float minor = 1.0 - min(f / 0.9, 1.0);
        float f5 = abs(fract(vH / 5.0 - 0.5) - 0.5) / fwidth(vH / 5.0);
        float major = 1.0 - min(f5 / 1.6, 1.0);
        float on = step(0.4, vH);
        vec3 inkc = vec3(0.42, 0.30, 0.19);
        col = mix(col, inkc, on * max(minor * 0.5, major * 0.85));
        col *= 0.97 + 0.05 * hash(floor(vXZ * 220.0));
        gl_FragColor = vec4(col, 1.0);
      }`,
    extensions: { derivatives: true },
  });
  return new THREE.Mesh(g, m);
}
const terrain = buildTerrain();
scene.add(terrain);

// A coarse copy of the ground, used only to find where the pointer is.
const pick = (() => {
  const g = new THREE.PlaneGeometry(W, H, 180, 120);
  g.rotateX(-Math.PI / 2);
  const p = g.attributes.position;
  for (let k = 0; k < p.count; k++) p.setY(k, heightAt(p.getX(k) + W / 2, p.getZ(k) + H / 2) * ZS);
  g.computeBoundingSphere();
  return new THREE.Mesh(g, new THREE.MeshBasicMaterial({ visible: false }));
})();
scene.add(pick);

// ---------- lines draped on the ground ----------
const lineMats = [];
function drape(pts2, { color = "#2b2620", width = 1.5, dashed = false, dash = 0.08, gap = 0.08, lift = 0.012, opacity = 1 } = {}) {
  const flat = [];
  for (const [x, y] of pts2) { const v = toWorld(x, y, heightAt(x, y) * ZS + lift); flat.push(v.x, v.y, v.z); }
  const g = new LineGeometry(); g.setPositions(flat);
  const m = new LineMaterial({ color, linewidth: width, dashed, dashSize: dash, gapSize: gap, transparent: opacity < 1, opacity });
  m.resolution.set(innerWidth, innerHeight);
  lineMats.push(m);
  const line = new Line2(g, m);
  if (dashed) line.computeLineDistances();
  scene.add(line);
  return line;
}
function curve(a, b, steps) {  // eased path from a to b, the storyline way
  const out = [];
  for (let s = 0; s <= steps; s++) {
    const t = s / steps, e = t * t * (3 - 2 * t);
    out.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * e]);
  }
  return out;
}

// Band boundaries, like county lines.
L.bands.forEach((b, k) => {
  if (k === 0) return;
  const y = b.y - b.h / 2;
  const pts = []; for (let x = L.sheet.x0 - 0.3; x <= L.sheet.x1 + 0.3; x += 0.05) pts.push([x, y]);
  drape(pts, { color: "#8a7556", width: 1, dashed: true, dash: 0.22, gap: 0.1, opacity: 0.7 });
});

// Neatline and chapter graticule (rule L1).
{
  const x0 = L.sheet.x0 - 0.6, x1 = L.sheet.x1 + 0.6, y0 = L.sheet.top - 0.9, y1 = L.sheet.bottom + 0.9;
  for (const off of [0, 0.12]) drape([[x0 - off, y0 - off], [x1 + off, y0 - off], [x1 + off, y1 + off], [x0 - off, y1 + off], [x0 - off, y0 - off]], { width: off ? 2.2 : 1, lift: 0.001 });
  for (const c of L.chapters) {
    for (const [ya, yb] of [[y0, y0 + 0.18], [y1 - 0.18, y1]]) drape([[c.x0, ya], [c.x0, yb]], { width: 1, lift: 0.001 });
  }
}

// ---------- sprites: lettering and symbols ----------
function textSprite(text, { size = 0.5, font = "IM Fell English SC", italic = false, color = "#2b2620", spacing = 0.12, halo = true } = {}) {
  const px = 96, c = document.createElement("canvas"), ctx = c.getContext("2d");
  const f = `${italic ? "italic " : ""}${px}px "${font}"`;
  ctx.font = f;
  const chars = [...text], gapPx = spacing * px;
  const w = chars.reduce((s, ch) => s + ctx.measureText(ch).width, 0) + gapPx * (chars.length - 1);
  c.width = Math.ceil(w + 40); c.height = Math.ceil(px * 1.5);
  ctx.font = f; ctx.textBaseline = "middle";
  let x = 20;
  for (const ch of chars) {
    if (halo) { ctx.lineWidth = px * 0.16; ctx.strokeStyle = "rgba(239,229,207,0.85)"; ctx.strokeText(ch, x, c.height / 2); }
    ctx.fillStyle = color; ctx.fillText(ch, x, c.height / 2);
    x += ctx.measureText(ch).width + gapPx;
  }
  const t = new THREE.CanvasTexture(c); t.anisotropy = 8; t.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, depthWrite: false, transparent: true }));
  s.scale.set(size * c.width / c.height, size, 1);
  return s;
}
function symbolSprite(kind, ink = "#2b2620") {
  const c = document.createElement("canvas"); c.width = c.height = 64;
  const g = c.getContext("2d"); g.strokeStyle = ink; g.fillStyle = "#efe5cf"; g.lineWidth = 4;
  if (kind === "letter") { g.fillRect(10, 18, 44, 28); g.strokeRect(10, 18, 44, 28); g.beginPath(); g.moveTo(10, 18); g.lineTo(32, 36); g.lineTo(54, 18); g.stroke(); }
  else if (kind === "carriage") { g.beginPath(); g.arc(22, 42, 9, 0, 7); g.fill(); g.stroke(); g.beginPath(); g.arc(44, 42, 9, 0, 7); g.fill(); g.stroke(); g.strokeRect(14, 16, 38, 18); }
  else if (kind === "end") { g.fillStyle = "#efe5cf"; g.strokeStyle = ink; g.lineWidth = 9; g.beginPath(); g.arc(32, 32, 20, 0, 7); g.fill(); g.stroke(); }
  else if (kind === "knot") { g.fillStyle = ink; g.beginPath(); g.arc(32, 32, 11, 0, 7); g.fill(); g.strokeStyle = "#efe5cf"; g.lineWidth = 3; g.beginPath(); g.arc(32, 32, 5, 0, 7); g.stroke(); }
  else { g.beginPath(); g.moveTo(32, 14); g.lineTo(50, 32); g.lineTo(32, 50); g.lineTo(14, 32); g.closePath(); g.fill(); g.stroke(); }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  return new THREE.Sprite(new THREE.SpriteMaterial({ map: t, depthWrite: false, transparent: true }));
}
const place = (s, x, y, lift) => { s.position.copy(toWorld(x, y, heightAt(x, y) * ZS + lift)); scene.add(s); return s; };

// ---------- paths (rule L6) ----------
for (const path of L.paths) {
  const pts = path.points;
  if (!pts.length) continue;
  let solid = [[pts[0].x, pts[0].y]];
  const flush = () => { if (solid.length > 1) drape(solid, { color: path.ink, width: 2.6, lift: 0.02 }); };
  const end = pt => { const s = symbolSprite("end", path.ink); s.scale.setScalar(0.07); place(s, pt.x, pt.y, 0.04); };
  end(pts[0]);
  for (let k = 1; k < pts.length; k++) {
    const a = pts[k - 1], b = pts[k], gap = b.i - a.i;
    const moved = byId[a.passage].band !== byId[b.passage].band;
    if (gap === 1 && !moved) { solid.push([b.x, b.y]); continue; }
    flush(); solid = [[b.x, b.y]];
    if (gap > L.gap_max || moved) { end(a); end(b); continue; }
    drape(curve([a.x, a.y], [b.x, b.y], 24), { color: path.ink, width: 1.2, dashed: true, dash: 0.04, gap: 0.07, lift: 0.02, opacity: 0.8 });
  }
  flush();
  end(pts[pts.length - 1]);
  // Name at the first and last point of the path.
  for (const pt of [pts[0], pts[pts.length - 1]]) {
    const s = textSprite(path.name, { size: 0.2, font: "IM Fell English", italic: true, color: path.ink, spacing: 0.02 });
    s.center.set(pt === pts[0] ? 1.05 : -0.05, 0.5);
    place(s, pt.x, pt.y, 0.08);
  }
}

// ---------- roads (rule L10) ----------
for (const r of L.roads) {
  const pts = [];
  for (let s = 0; s <= 40; s++) { const t = s / 40, e = t * t * (3 - 2 * t); pts.push([r.x0 + (r.x1 - r.x0) * t, r.y0 + (r.y1 - r.y0) * e]); }
  drape(pts, { color: "#5a4e40", width: 1.1, dashed: true, dash: 0.07, gap: 0.05, lift: 0.015, opacity: 0.85 });
}

// ---------- meetings (rule L7) and objects (rule L8) ----------
for (const m of L.meetings) {
  drape([[m.x, m.y0], [m.x, m.y1]], { width: 1.4, lift: 0.025 });
  const s = symbolSprite("knot"); s.scale.setScalar(0.11);
  place(s, m.x, (m.y0 + m.y1) / 2, 0.05);
}
for (const o of L.objects) {
  const s = symbolSprite(o.kind); s.scale.setScalar(o.kind === "object" ? 0.1 : 0.17);
  place(s, o.x, o.y, 0.08);
}

// ---------- lettering: places (rule L9), bands, chapters ----------
for (const lb of L.labels) {
  const size = Math.min(0.55, Math.max(0.24, lb.width / (lb.text.length * 0.9)));
  place(textSprite(lb.text.toUpperCase(), { size, spacing: 0.22 }), lb.x, lb.y - 0.05, 0.35);
}
for (const b of L.bands) {
  const s = textSprite(b.name, { size: 0.22, font: "IM Fell English", italic: true, spacing: 0.02 });
  s.center.set(1, 0.5);
  place(s, L.sheet.x0 - 0.75, b.y, 0.02);
}
for (const c of L.chapters) {
  const s = textSprite(c.label, { size: 0.17, spacing: 0.02, halo: false });
  place(s, (c.x0 + c.x1) / 2, L.sheet.bottom + 0.6, 0.02);
}
{
  const s = textSprite("Chapters  →", { size: 0.2, font: "IM Fell English", italic: true, spacing: 0.02, halo: false });
  s.center.set(1, 0.5); place(s, L.sheet.x0 - 0.75, L.sheet.bottom + 0.6, 0.02);
}

// ---------- views ----------
let fly = null;
function view(name) {
  const t = new THREE.Vector3(0, 0, name === "plan" ? 0 : 1.5);
  let p;
  if (name === "plan") {
    const fov = THREE.MathUtils.degToRad(camera.fov / 2);
    const d = Math.max((H + 1) / 2 / Math.tan(fov), (W + 2) / 2 / Math.tan(fov) / camera.aspect);
    p = new THREE.Vector3(0, d, 0.01);
  } else p = new THREE.Vector3(-4, 17, 24);
  fly = { p0: camera.position.clone(), t0: controls.target.clone(), p, t, k: 0 };
  document.querySelectorAll("[data-view]").forEach(b => b.classList.toggle("on", b.dataset.view === name));
}
document.querySelectorAll("[data-view]").forEach(b => b.onclick = () => view(b.dataset.view));
camera.position.set(-4, 17, 24); controls.target.set(0, 0, 1.5);

addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  lineMats.forEach(m => m.resolution.set(innerWidth, innerHeight));
});
renderer.setAnimationLoop(() => {
  if (fly) {
    fly.k = Math.min(1, fly.k + 0.035);
    const e = fly.k * fly.k * (3 - 2 * fly.k);
    camera.position.lerpVectors(fly.p0, fly.p, e); controls.target.lerpVectors(fly.t0, fly.t, e);
    if (fly.k >= 1) fly = null;
  }
  controls.update();
  renderer.render(scene, camera);
});

// ---------- picking: what is under the pointer, in map coordinates ----------
const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
function mapPoint(ev) {
  ndc.set((ev.clientX / innerWidth) * 2 - 1, -(ev.clientY / innerHeight) * 2 + 1);
  ray.setFromCamera(ndc, camera);
  const hit = ray.intersectObject(pick)[0];
  return hit ? { x: hit.point.x + W / 2, y: hit.point.z + H / 2, dist: hit.distance } : null;
}
function nearest({ x, y, dist }) {
  const r = Math.max(0.06, dist * 0.006);
  let best = null, bd = Infinity;
  const consider = (d, item) => { if (d < r && d < bd) { bd = d; best = item; } };
  for (const o of L.objects) consider(Math.hypot(o.x - x, o.y - y) * 0.8, { type: "object", o });
  for (const m of L.meetings) if (Math.abs(m.x - x) < r) {
    const dy = y < m.y0 ? m.y0 - y : y > m.y1 ? y - m.y1 : 0;
    consider(Math.hypot(m.x - x, dy) * 0.9, { type: "meeting", m });
  }
  for (const path of L.paths) for (const pt of path.points) consider(Math.hypot(pt.x - x, pt.y - y), { type: "path", path, pt });
  if (best) return best;
  for (const r of L.roads) if (x >= r.x0 - 0.02 && x <= r.x1 + 0.02 && Math.min(r.y0, r.y1) - 0.1 <= y && y <= Math.max(r.y0, r.y1) + 0.1) return { type: "road", r };
  for (const lb of L.labels) if (Math.abs(x - lb.x) < Math.max(0.6, lb.width / 2) && Math.abs(y - lb.y) < 0.3) return { type: "label", lb };
  return { type: "ground", x, y };
}
const tip = document.getElementById("tip");
const describe = it => ({
  object: () => `${it.o.name} · ${chap(it.o.passage)}`,
  meeting: () => `${it.m.kind}: ${it.m.who.map(nameOf).join(" & ")} · ${chap(it.m.passage)}`,
  path: () => `${it.path.name} · ${chap(it.pt.passage)}`,
  label: () => it.lb.text,
  road: () => `${it.r.from} → ${it.r.to} · ${chap(it.r.passages[1])}`,
  ground: () => `tension ${heightAt(it.x, it.y).toFixed(1)} · click to see why`,
})[it.type]();
const nameOf = id => L.paths.find(p => p.entity === id)?.name || id;
const chap = pid => `ch. ${byId[pid].chapter}`;
let downAt = null;
renderer.domElement.addEventListener("pointerdown", e => { downAt = [e.clientX, e.clientY]; });
renderer.domElement.addEventListener("pointermove", e => {
  if (e.buttons) { tip.hidden = true; return; }
  const mp = mapPoint(e);
  if (!mp) { tip.hidden = true; return; }
  tip.textContent = describe(nearest(mp)); tip.hidden = false;
  tip.style.left = e.clientX + "px"; tip.style.top = e.clientY + "px";
});
renderer.domElement.addEventListener("pointerup", e => {
  if (!downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 5) return;
  const mp = mapPoint(e);
  if (mp) explain(nearest(mp));
});

// ---------- the explanation panel ----------
const panel = document.getElementById("panel"), body = document.getElementById("panel-body");
document.getElementById("close").onclick = () => { panel.hidden = true; };
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const rule = id => `<div class="rule"><b>Rule ${id}.</b> ${esc(L.rules[id])}</div>`;
const fid = ids => `<p class="fact">fact ${ids.map(esc).join(", ")} · run ${esc(L.run.id)}</p>`;
const uniq = spans => [...new Map(spans.map(s => [s.join(":"), s])).values()].sort((a, b) => a[0] - b[0]);
const prose = s => s.replace(/\r\n\r\n/g, "\n\n").replace(/\r\n/g, " ").replace(/_/g, "");
function quote(spans) {  // the cited sentences, exactly as in the source file
  return spans.map(([a, b]) => {
    const p = P.find(q => q.start <= a && b <= q.end);
    return p ? `<blockquote>${esc(prose(TEXT.passages[p.id].slice(a - p.start, b - p.start)))}</blockquote>` : "";
  }).join("");
}
const readLink = (pid, spans = []) => `<p><span class="link-a" data-read="${pid}" data-spans='${JSON.stringify(spans)}'>Read passage ${pid} with these sentences marked</span></p>`;
function show(html) {
  body.innerHTML = html; panel.hidden = false; panel.scrollTop = 0;
  body.querySelectorAll("[data-read]").forEach(a => a.onclick = () => readPassage(a.dataset.read, JSON.parse(a.dataset.spans)));
}
function settingNote(pid) {
  const p = byId[pid], s = p.setting;
  const how = p.placed === "carried" ? `The reader judged the setting “${esc(s.setting)}”, so it stays on the band of the passage before (rule L2).` :
    `Set at <b>${esc(s.setting)}</b>: ${esc(s.basis)}${s.rationale ? ` — “${esc(s.rationale.replace(/\.$/, ""))}”` : ""}.`;
  return `<p>${how}</p>${(s.flags || []).map(f => `<p class="flag">Flag: ${esc(f)}</p>`).join("")}`;
}
function explain(it) {
  if (it.type === "path") {
    const { path, pt } = it, p = byId[pt.passage];
    show(`<h2>${esc(path.name)}</h2>
      <p class="kicker">Chapter ${p.chapter}, passage ${p.id} · on the ${esc(p.band)} band</p>
      <p>Here the passage calls them <b>${pt.called.map(esc).join("”, “").replace(/^/, "“")}”</b>. Code accepted this because the cited sentences contain those exact words:</p>
      ${quote(uniq(pt.spans).slice(0, 3))}${uniq(pt.spans).length > 3 ? `<p class="kicker">and ${uniq(pt.spans).length - 3} more cited sentences, marked in the passage</p>` : ""}${fid(pt.facts)}
      ${rule("L6")}
      <h3>Who this path is</h3>
      <p>${path.mentions} verified mentions under the names ${path.aliases.map(n => `“${esc(n)}”`).join(", ")}, merged by the entity pass (each merge is logged with its rule or model call).</p>
      ${readLink(p.id, pt.spans)}`);
  } else if (it.type === "meeting") {
    const m = it.m, p = byId[m.passage];
    show(`<h2>${esc(m.kind[0].toUpperCase() + m.kind.slice(1))}</h2>
      <p class="kicker">${m.who.map(nameOf).map(esc).join(" and ")} · chapter ${p.chapter}</p>
      <p>${esc(m.summary)}</p>${quote(m.spans)}${fid(m.facts)}${rule("L7")}
      <p class="flag">The summary is the reader model's own words. Code checked that the cited sentences exist, not that the summary is right.</p>
      ${readLink(p.id, m.spans)}`);
  } else if (it.type === "object") {
    const o = it.o, p = byId[o.passage];
    show(`<h2>${esc(o.name)}</h2><p class="kicker">Chapter ${p.chapter} · ${esc(o.kind)}</p>
      ${o.description ? `<p>${esc(o.description)}</p>` : ""}${quote(o.spans)}${fid(o.facts)}${rule("L8")}${readLink(p.id, o.spans)}`);
  } else if (it.type === "road") {
    const r = it.r, [a, b] = r.passages;
    show(`<h2>${esc(r.from)} → ${esc(r.to)}</h2>
      <p class="kicker">Between passage ${a} and ${b} (chapter ${byId[b].chapter})</p>${rule("L10")}
      <h3>Where ${a} was set</h3>${settingNote(a)}${readLink(a, byId[a].setting.spans || [])}
      <h3>Where ${b} is set</h3>${settingNote(b)}${readLink(b, byId[b].setting.spans || [])}`);
  } else if (it.type === "label") {
    const lb = it.lb, ps = lb.passages.map(id => byId[id]);
    show(`<h2>${esc(lb.text)}</h2>
      <p class="kicker">Chapters ${ps[0].chapter}–${ps.at(-1).chapter} · ${ps.length} passages set here</p>
      ${rule("L9")}${rule("L2")}
      <h3>How each passage was placed here</h3>
      <table>${ps.map(p => `<tr><td>${p.id}</td><td>${p.placed === "carried" ? `<i>carried over (${esc(p.setting.setting)})</i>` : esc(p.setting.basis)}${(p.setting.flags || []).length ? ' <span class="flag">flagged</span>' : ""}</td><td><span class="link-a" data-read="${p.id}" data-spans='${JSON.stringify(p.setting.spans || [])}'>read</span></td></tr>`).join("")}</table>`);
  } else {
    const parts = contributions(it.x, it.y).filter(c => c.v > 0.001).sort((a, b) => b.v - a.v);
    const h = parts.reduce((s, c) => s + c.v, 0);
    const band = L.bands.find(b => Math.abs(it.y - b.y) <= b.h / 2);
    const top = parts.slice(0, 6);
    show(`<h2>This ground</h2>
      <p class="kicker">${band ? `In the ${esc(band.name)} band` : "In the margin"} · near chapter ${byId[near(it.x)[Math.floor(near(it.x).length / 2)].id].chapter}</p>
      <p>Height here is <b>${h.toFixed(2)}</b> points of tension (${Math.floor(h)} contour lines). It is the sum of these passages' shares, computed with the formula in rule L4:</p>
      <table>${top.map(c => `<tr><td class="n">${(100 * c.v / (h || 1)).toFixed(0)}%<div class="bar" style="width:${(100 * c.v / (h || 1)).toFixed(0)}%"></div></td>
        <td><b>${c.p.id}</b>, tension ${c.p.tension}, set at ${esc(c.p.band)}${c.gy < 0.3 ? " (far from here, so it counts for less)" : ""}<br>
        <i>“${esc(c.p.tone?.reason || "")}”</i> <span class="link-a" data-read="${c.p.id}" data-spans='${JSON.stringify(c.p.tone?.spans || [])}'>read</span></td></tr>`).join("")}
        ${parts.length > top.length ? `<tr><td class="n">${(100 * parts.slice(6).reduce((s, c) => s + c.v, 0) / (h || 1)).toFixed(0)}%</td><td>${parts.length - 6} more distant passages</td></tr>` : ""}</table>
      ${rule("L4")}${rule("L5")}
      <p class="flag">Tension is the reader model's 0–10 judgment of each passage, with its stated reason. Code checked the cited sentences exist; the number itself is the model's opinion.</p>`);
  }
}
function readPassage(pid, spans) {
  const p = byId[pid], text = TEXT.passages[pid];
  const marks = (spans || []).map(([a, b]) => [a - p.start, b - p.start]).filter(([a, b]) => a >= 0 && b <= text.length).sort((u, v) => u[0] - v[0]);
  let html = "", at = 0;
  for (const [a, b] of marks) { if (a < at) continue; html += esc(prose(text.slice(at, a))) + "<mark>" + esc(prose(text.slice(a, b))) + "</mark>"; at = b; }
  html += esc(prose(text.slice(at)));
  show(`<h2>Passage ${pid}</h2>
    <p class="kicker">Chapter ${p.chapter} · characters ${p.start.toLocaleString()}–${p.end.toLocaleString()} of ${esc(TEXT.file)}</p>
    ${settingNote(pid)}
    <p>Tension ${p.tension ?? "–"}, warmth ${p.warmth ?? "–"}${p.tone ? `: <i>“${esc(p.tone.reason)}”</i>` : ""}</p>
    <h3>What happens (reader's summary)</h3><ol>${p.events.map(e => `<li>${esc(e.summary)}</li>`).join("")}</ol>
    <h3>The text</h3><div class="passage">${html}</div>
    <p class="fact">source sha256 ${esc(TEXT.sha256.slice(0, 16))}…</p>`);
}

// ---------- cartouche and legend ----------
document.getElementById("title").textContent = L.book.title;
document.getElementById("meta").textContent =
  `${L.book.author} · read by ${L.run.model} · ${P.length} passages, ${L.paths.length} paths, ${L.meetings.length} meetings`;
document.getElementById("legend-model").textContent = L.run.model;
document.getElementById("rules").innerHTML = Object.entries(L.rules).map(([k, v]) => `<li value="${k.slice(1)}"><b>${k}</b> ${esc(v)}</li>`).join("");
const legend = document.getElementById("legend");
document.getElementById("legend-btn").onclick = () => { legend.hidden = !legend.hidden; };
legend.querySelector(".close-legend").onclick = () => { legend.hidden = true; };

// For poking at the map from the browser console.
window.rebind = { layout: L, explain, heightAt, contributions };
