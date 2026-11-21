// The poster, drawn from the same files as the site: pattern.json, book.json, text.json, checks.json.
// Nothing here decides anything about a book. ?book=<slug> picks the lead scarf, ?row=<n> the worked example.

const SITE = 'https://burakdon.github.io/Rebind/';
const AUTHOR = 'Burak Donbekci · AIPI 590, Duke University';
const Q = new URLSearchParams(location.search);
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const get = f => fetch(f).then(r => (r.ok ? r.json() : null)).catch(() => null);

const books = await get('../data/books.json');
const LEAD = Q.get('book') || books[0].slug;
const all = await Promise.all(books.map(async b => ({ b, K: await get(`../data/${b.slug}/pattern.json`), C: await get(`../data/${b.slug}/checks.json`) })));
const lead = all.find(x => x.b.slug === LEAD), K = lead.K;
const [B, TXT] = await Promise.all([get(`../data/${LEAD}/book.json`), get(`../data/${LEAD}/text.json`)]);
await document.fonts.ready;

const hexOf = Object.fromEntries(K.yarns.map(y => [y.key, y.hex]));
const shade = (h, f) => '#' + [1, 3, 5].map(i => Math.round(Math.min(255, parseInt(h.slice(i, i + 2), 16) * f)).toString(16).padStart(2, '0')).join('');
const f2 = v => v.toFixed(2);

// ---- a scarf lying flat, cast-on edge at the left, one stitch at a time ---------------------------------
// Units are stitch widths. A smooth row is 0.75 tall and a ridged one 0.5, as in the gauge.
function scarf(P, unit, detail) {
  const W = P.cast_on, rowH = r => (r.texture === 'ridged' ? 0.5 : 0.75);
  const along = [0];
  for (const r of P.rows) { along.push(along.at(-1) + rowH(r)); along.push(along.at(-1) + rowH(r)); }
  const LEN = along.at(-1), hex = Object.fromEntries(P.yarns.map(y => [y.key, y.hex]));
  let s = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${f2(LEN)} ${W}" width="${f2(LEN * unit)}in" height="${f2(W * unit)}in" shape-rendering="geometricPrecision">`;
  P.rows.forEach((r, n) => {
    const col = hex[r.yarn], ridged = r.texture === 'ridged', h = rowH(r);
    for (let half = 0; half < 2; half++) {
      const x = along[n * 2 + half];
      s += `<rect x="${f2(x)}" y="0" width="${f2(h + 0.02)}" height="${W}" fill="${shade(col, detail ? 0.66 : (ridged ? 0.84 : 1))}"/>`;
      let vs = '', bumps = '', holes = '';
      for (let c = 0; c < W; c++) {
        const y = W - 1 - c, sym = r.rs[c], edge = c < P.edge || c >= W - P.edge;
        if (half === 0 && sym === 'o') { holes += `<ellipse cx="${f2(x + h / 2)}" cy="${y + 0.5}" rx="${f2(h * 0.4)}" ry="0.34"/>`; continue; }
        if (!detail) continue;
        if (half === 1 && (ridged || edge)) bumps += `M${f2(x + h * 0.5)} ${y + 0.14}V${y + 0.86}`;
        else vs += `M${f2(x + h * 1.12)} ${y + 0.1}L${f2(x + h * 0.1)} ${y + 0.5}L${f2(x + h * 1.12)} ${y + 0.9}`;
      }
      if (vs) s += `<path d="${vs}" fill="none" stroke="${col}" stroke-width="0.3" stroke-linecap="round" stroke-linejoin="round"/>`;
      if (bumps) s += `<path d="${bumps}" fill="none" stroke="${shade(col, 1.06)}" stroke-width="${f2(h * 0.62)}" stroke-linecap="round"/>`;
      if (holes) s += `<g fill="#2e261d">${holes}</g>`;
    }
  });
  return { svg: s + '</svg>', along, LEN, W };
}

// ---- header ----------------------------------------------------------------------------------------------
const qr = qrcode(0, 'M'); qr.addData(SITE); qr.make();
$('qr').innerHTML = qr.createSvgTag({ cellSize: 4, margin: 0, scalable: true });
$('url').textContent = SITE.replace('https://', '');
$('by').textContent = AUTHOR;

// ---- the lead scarf ----------------------------------------------------------------------------------------
const CW = (K.book.chapter_word || 'Chapter'), S = K.size;
$('lead-title').textContent = K.book.title;
$('lead-facts').textContent = `${K.book.author}. ${S.pairs} passages, ${S.rows} rows, cast on ${K.cast_on}: about ${Math.round(S.width_in)} × ${S.length_in} inches in worsted yarn. First page at the left, last page at the right.`;
const box = $('lead-scarf'), NAMES = 1.75, AVAIL = 34 - NAMES - 0.95;
const pre = scarf(K, 1, false), unit = Math.min(AVAIL / pre.LEN, 6.9 / pre.W);
const big = scarf(K, unit, true), top = 0.05;
const holder = document.createElement('div'); holder.className = 'scarf'; holder.style.cssText = `left:${NAMES}in;top:${top}in`; holder.innerHTML = big.svg; box.appendChild(holder);
const tag = (cls, html, css) => { const d = document.createElement('div'); d.className = 'tag ' + cls; d.innerHTML = html; d.style.cssText = css; box.appendChild(d); return d; };
for (const c of K.columns) {
  const y = top + (big.W - (c.stitches[0] + 0.5)) * unit;
  tag('', esc(c.name), `right:${34 - NAMES + 0.12}in;top:${y - 0.09}in;font-size:15.5pt`);
}
K.rows.forEach((r, n) => {
  if (!r.starts_chapter) return;
  tag('num', `${CW} ${esc(r.chapter_label)}`, `left:${NAMES + big.along[n * 2] * unit}in;top:${top + big.W * unit + 0.12}in;font-size:17pt;border-left:1pt solid #2b2620;padding:0.02in 0 0.05in 0.07in`);
});
$('key').innerHTML = `<li class="ramp"><b>Yarn</b> &nbsp;cold ${'ABCDE'.split('').map(k => `<i style="background:${hexOf[k]}"></i>`).join('')} warm</li>
  <li><i style="background:${hexOf.U}"></i>undyed: the two readings were too far apart to say</li>
  <li><b>Ridge</b> (raised bars): at least half the passage is tense</li>
  <li><b>Hole</b>: that person is in the passage</li>`;

// ---- the other books ---------------------------------------------------------------------------------------
$('others').innerHTML = all.filter(x => x.b.slug !== LEAD).map(({ b, K: P }) => {
  const u = 1.62 / P.cast_on, t = scarf(P, u, false);
  return `<div class="book"><h3>${esc(b.title)}</h3><p class="small">${esc(b.author || '')}. ${b.pairs} passages, ${b.rows} rows, about ${Math.round(b.width_in)} × ${b.length_in} inches. ${b.undyed} passages undyed.</p><div class="strip">${t.svg}</div></div>`;
}).join('');

// ---- the rules, from the numbers the pattern was made with -------------------------------------------------
const [a, b, c, d] = K.yarn_cuts, m = v => String(v).replace('-', '−');
$('rules').innerHTML = [
  ['K1', `One passage of the book is one pair of rows, first page to last.`],
  ['K2', `Yarn: warm labels minus cold labels, over both readings, divided by the number of labels. A at ${m(a)} or less, B below ${m(b)}, C below ${c}, D below ${d}, E above.`],
  ['K3', `Ridge: at least ${Math.round(K.ridged_share * 100)} in 100 of the labels are tense. Otherwise smooth.`],
  ['K4', `The ${K.columns.length} most-mentioned people each own a column, the most-mentioned in the middle.`],
  ['K5', `Eyelet: a checked fact puts that person in the passage.`],
  ['K6', `An eyelet in the edge marks where a ${CW.toLowerCase()} begins.`],
  ['K7', `Undyed: counted apart, the two readings pick yarns ${K.unsure_gap} or more apart.`],
].map(([k, v]) => `<li><b>${k}</b>${v}</li>`).join('');

// ---- how far to trust it --------------------------------------------------------------------------------------
const per = v => (v == null ? '–' : Math.round(100 * v));
$('checks').innerHTML = `<tr><th>Book</th><th class="n">Question<br>reworded</th><th class="n">Every name<br>swapped</th><th class="n">A second<br>model</th><th class="n">Rows left<br>undyed</th></tr>`
  + all.map(({ b, C }) => {
    const o = C && Object.values(C.other || {})[0], sw = C?.memory && C.readings['a-swapped'] >= C.readings.a ? C.memory : null;
    const cell = x => (x ? `${per(x.feeling.same)} · ${per(x.pace.same)}` : 'not run');
    return `<tr><td>${esc(b.title)}</td><td class="n">${cell(C?.stability)}</td><td class="n">${cell(sw)}</td><td class="n">${o ? cell(o) + (o.passages < o.of ? '*' : '') : 'not run'}</td><td class="n">${b.undyed} of ${b.pairs}</td></tr>`;
  }).join('') + `<tr><td colspan="5" style="border:0;font-size:14pt;color:#5f5343">Each cell: warm/cold/neither label · tense/calm label. A person: not checked for any book.${all.some(x => Object.values(x.C?.other || {}).some(o => o.passages < o.of)) ? ' *On a sample of passages.' : ''}</td></tr>`;
const fragile = K.rows.filter(r => r.margin === 1).length, st = lead.C?.stability, me = lead.C?.memory;
$('limits').innerHTML = [
  st && me ? `<b>Wording moves it more than names do.</b> Rewording the question changes about ${Math.round(100 * (1 - st.feeling.same))} in 100 feeling labels in ${esc(K.book.title)}; swapping every name changes about ${Math.round(100 * (1 - me.feeling.same))}. So there is no sign the model leans on recognising the book, though it may still know the text.` : '',
  `<b>No person has checked the labels.</b> The figures say how steady the model is, not whether it is right. The site lets anyone label a sample blind.`,
  `<b>Thin margins.</b> In ${fragile} of ${K.rows.length} rows of the lead scarf, one changed label would change the yarn. Every row states its own margin.`,
  `<b>The cut points are choices.</b> ${m(a)}, ${m(b)}, ${c} and ${d} were set by hand. Moving them changes the scarf, not the labels.`,
  `<b>Not yet knitted.</b> Sizes come from a typical gauge, not a swatch. “He” and “she” leave no eyelet, because code cannot check who is meant.`,
].filter(Boolean).map(x => `<li>${x}</li>`).join('');

// ---- one row, unravelled ----------------------------------------------------------------------------------------
const pick = Q.has('row') ? +Q.get('row') : (K.rows.filter(r => !r.unsure && r.gap === 0 && r.eyelets.length >= 2 && r.tally.a.n <= 9).at(-1) || K.rows.at(-1)).n;
const r = K.rows[pick - 1], p = B.passages.find(x => x.id === r.passage), t = r.tally, y = K.yarns.find(v => v.key === r.yarn);
const sw = k => `<span class="sw" style="background:${hexOf[k]}"></span>`;
const sum = (x, unit) => `${x.n} ${unit}: ${x.warm} warm, ${x.cold} cold, ${x.neither} neither. (${x.warm} − ${x.cold}) ÷ ${x.n} = ${m(f2((x.warm - x.cold) / x.n))}: yarn ${x.yarn}.`;
const FEEL = ['neither', 'warm', 'cold'], PACE = ['calm', 'tense'], CHIP = [hexOf.C, hexOf.D, hexOf.A];
const SS = B.sentences, [s0, sn] = p.sentences, text = TXT.passages[p.id];
const cut = (s, n) => (s.length > n ? s.slice(0, s.lastIndexOf(' ', n)) + ' …' : s);
let sents = '';
for (let i = s0; i < s0 + sn; i++) {
  const s = text.slice(SS.start[i] - p.start, SS.end[i] - p.start).replace(/\s*\r?\n\s*/g, ' ');
  const differs = SS.feeling_b[i] >= 0 && (SS.feeling_b[i] !== SS.feeling[i] || SS.pace_b[i] !== SS.pace[i]);
  sents += `<div class="sent" style="border-color:${CHIP[SS.feeling[i]]}">${esc(cut(s, 150))} <span>${FEEL[SS.feeling[i]]}, ${PACE[SS.pace[i]]}${differs ? ` · asked again: ${FEEL[SS.feeling_b[i]]}, ${PACE[SS.pace_b[i]]}` : ''}</span></div>`;
}
const verdict = r.unsure ? `Counted apart the readings pick ${t.a.yarn} and ${t.b.yarn}, too far apart, so the row is left undyed.`
  : r.gap === 0 ? `Counted apart, both readings pick ${t.a.yarn} too. The row is knitted in yarn ${r.yarn}, ${esc(y.name)}.`
  : `Counted apart the readings pick neighbours, ${t.a.yarn} and ${t.b.yarn}. The row takes the yarn of both together: ${r.yarn}, ${esc(y.name)}.`;
$('example').innerHTML = `<h2>One row, unravelled</h2>
  <p class="kicker">Rows ${r.n * 2 - 1} and ${r.n * 2} of ${S.rows}: ${CW.toLowerCase()} ${esc(r.chapter_label)}, passage ${r.n} of ${S.pairs}. On the site, every row opens like this.</p>
  <div class="rows">Yarn ${r.yarn} (${esc(y.name)}). Row ${r.n * 2 - 1} (right side): ${esc(r.rs_text)}.<br>Row ${r.n * 2} (wrong side): ${esc(r.ws_text)}.</div>
  <div class="two"><div>
    <h3>Why this yarn</h3>
    <p class="sum">${sw(t.a.yarn)}<b>First reading.</b> ${sum(t.a, 'sentences')}</p>
    ${t.b ? `<p class="sum">${sw(t.b.yarn)}<b>Asked again in other words.</b> ${sum(t.b, 'sentences')}</p>
    <p class="sum">${sw(t.both.yarn)}<b>Both together.</b> ${sum(t.both, 'labels')}</p>` : ''}
    <p class="sum">${verdict} ${r.margin ? `It would take ${r.margin === 1 ? 'one changed label' : r.margin + ' changed labels'} of ${t.both.n} to pick another yarn.` : ''}</p>
    <h3 style="margin-top:0.1in">Why it is ${r.texture}</h3>
    <p class="sum">${t.both.tense} of ${t.both.n} labels are tense, ${Math.round(100 * t.both.tense / t.both.n)} in 100. A ridge needs ${Math.round(K.ridged_share * 100)}.</p>
    <h3 style="margin-top:0.1in">The holes</h3>
    ${r.eyelets.map(e => { const col = K.columns.find(q => q.person === e.person); const [x0, x1] = e.spans[0]; return `<p class="sum"><b>${esc(col.name)}</b>, stitches ${col.stitches.join('–')}: named in “${esc(cut(text.slice(x0 - p.start, x1 - p.start).replace(/\s*\r?\n\s*/g, ' '), 70))}”</p>`; }).join('')}
  </div><div>
    <h3>Its ${sn} sentences, each with its label</h3>${sents}
  </div></div>`;

$('foot').innerHTML = `<span>Reader: ${esc(K.run.model.split(':')[0])} (open weights), run on a MacBook with Ollama. No text leaves the laptop, and every prompt and answer is kept in the repository.</span><span>Texts: Project Gutenberg. Code: github.com/burakdon/Rebind</span>`;

// ---- mark the example row on the scarf and lead a line down to it ----------------------------------------------
const P = $('poster'), scale0 = P.getBoundingClientRect().width / (36 * 96);
const inches = el => { const q = el.getBoundingClientRect(), o = P.getBoundingClientRect(); return { x: (q.left - o.left) / 96 / scale0, y: (q.top - o.top) / 96 / scale0, w: q.width / 96 / scale0, h: q.height / 96 / scale0 }; };
const sb = inches(holder), ex = inches($('example'));
const x0 = sb.x + big.along[(r.n - 1) * 2] * unit, x1 = sb.x + big.along[r.n * 2] * unit;
const mark = document.createElement('div');
mark.style.cssText = `position:absolute;left:${x0 - 0.03}in;top:${sb.y - 0.06}in;width:${x1 - x0 + 0.06}in;height:${sb.h + 0.12}in;border:2pt solid #2b2620`;
P.appendChild(mark);
const line = $('lead-line'), lx = Math.min(Math.max((x0 + x1) / 2, ex.x + 0.3), ex.x + ex.w - 0.3);
line.style.cssText = `left:${lx}in;top:${sb.y + sb.h + 0.06}in;height:${ex.y - sb.y - sb.h - 0.06}in`;

// ---- on screen, fit the window ------------------------------------------------------------------------------------
function fit() {
  const k = Math.min(innerWidth / (36 * 96), 1);
  P.style.transform = `scale(${k})`; $('frame').style.width = 36 * 96 * k + 'px'; $('frame').style.height = 24 * 96 * k + 'px';
}
if (!Q.has('print')) { fit(); addEventListener('resize', fit); }
document.body.dataset.ready = '1';
