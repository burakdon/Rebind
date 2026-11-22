// The dye is the one thing about a scarf a visitor may change. Every page reads the choice here, the
// same way: ?palette=<key> in the address wins, then the choice remembered in this browser, then the
// book's own palette. Changing the dye changes no label, no rule and no stitch: only yarn names and colours.
// The palettes are written by `rebind knit` into data/palettes.json.

const STORE = 'rebind.palette';
export const OWN = 'own';

export function chosen() {
  const q = new URLSearchParams(location.search).get('palette');
  if (q) return q;
  try { return localStorage.getItem(STORE) || OWN; } catch { return OWN; }
}

function remember(key) {
  try { if (key === OWN) localStorage.removeItem(STORE); else localStorage.setItem(STORE, key); return true; } catch { return false; }
}

export const loadPalettes = base => fetch(base + 'palettes.json').then(r => (r.ok ? r.json() : null)).catch(() => null);

// Give pattern K the yarns of palette `key`. 'own', or a key that does not exist, leaves the book's own.
export function dye(K, P, key) {
  const pal = key !== OWN && P?.palettes.find(p => p.key === key);
  if (!pal || pal.key === K.palette?.key) return K;
  const by = Object.fromEntries(pal.yarns.map(y => [y.key, y]));
  for (const y of K.yarns) if (by[y.key]) { y.name = by[y.key].name; y.hex = by[y.key].hex; }
  K.palette = { ...K.palette, key: pal.key, name: pal.name, from: pal.from, borrowed: true };
  return K;
}

// Fill a <select> with the choices. Picking one reloads the page in that dye.
export function picker(select, P, ownLabel) {
  if (!select || !P) { if (select) select.closest('label')?.remove(); return; }
  const now = chosen(), has = P.palettes.some(p => p.key === now);
  select.innerHTML = `<option value="${OWN}">${ownLabel}</option>` + P.palettes.map(p => `<option value="${p.key}">${p.name}</option>`).join('');
  select.value = has ? now : OWN;
  select.onchange = () => {
    const kept = remember(select.value), u = new URL(location.href);
    u.searchParams.delete('palette');
    if (!kept && select.value !== OWN) u.searchParams.set('palette', select.value);   // no storage: carry it in the address
    location.href = u.href;
  };
}

// A row of swatches from cold to warm, then the undyed yarn.
export const swatches = K => 'ABCDEU'.split('').map(k => { const y = K.yarns.find(v => v.key === k); return `<i style="background:${y.hex}" title="yarn ${k}, ${y.name}"></i>`; });
