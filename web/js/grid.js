// The pack as a grid of tiles: select, open, reorder by drag, drop files, paste.
import { api, media } from './api.js';
import { state, subscribe, order, pack, setActive, select, notify } from './store.js';
import { h, icon, fmtBytes, fmtSecs, toast, canWebm, isTouch, plural } from './util.js';

const grid = () => document.getElementById('grid');
const board = () => document.getElementById('board');
let lastClicked = null;
let playAll = false;

export function initGrid() {
  subscribe((what) => {
    if (what === 'all' || what === 'pack' || what === 'selection' || what === 'active' || what.startsWith('sticker:')) render(what);
  });
  const g = grid();
  g.addEventListener('click', onClick);
  g.addEventListener('dblclick', (e) => { const t = e.target.closest('.tile'); if (t) openInspector(); });
  g.addEventListener('keydown', onKey);
  document.getElementById('selectAll').addEventListener('change', (e) => select(e.target.checked ? order() : [], 'set'));
  document.getElementById('playAll').addEventListener('click', () => { playAll = !playAll; document.getElementById('playAll').textContent = playAll ? 'Pause all' : 'Play all'; render('all'); });
  setupDrag(g);
  setupFileDrop();
}

function openInspector() { document.getElementById('inspector').classList.add('open'); }

function onClick(e) {
  const t = e.target.closest('.tile');
  if (!t) { if (!e.target.closest('.board-head')) { select([], 'clear'); } return; }
  const id = t.dataset.id;
  const ids = order();
  if (e.target.closest('.tile-check')) {
    select([id], 'toggle');
    lastClicked = id;
    return;
  }
  if (e.shiftKey && lastClicked) {
    const a = ids.indexOf(lastClicked), b = ids.indexOf(id);
    const range = ids.slice(Math.min(a, b), Math.max(a, b) + 1);
    select(range, 'add');
  } else if (e.metaKey || e.ctrlKey) {
    select([id], 'toggle');
  } else {
    if (state.selected.size) select([], 'clear');
    setActive(id);
    if (isTouch || innerWidth <= 760) openInspector();
  }
  lastClicked = id;
}

function onKey(e) {
  const ids = order();
  if (!ids.length) return;
  const cur = state.active ? ids.indexOf(state.active) : -1;
  const cols = Math.max(1, Math.round(grid().clientWidth / (grid().querySelector('.tile')?.offsetWidth + 14 || 164)));
  const go = (i) => { const id = ids[Math.max(0, Math.min(ids.length - 1, i))]; setActive(id); grid().querySelector(`[data-id="${id}"]`)?.focus(); e.preventDefault(); };
  if (e.key === 'ArrowRight') go(cur + 1);
  else if (e.key === 'ArrowLeft') go(cur - 1);
  else if (e.key === 'ArrowDown') go(cur + cols);
  else if (e.key === 'ArrowUp') go(cur - cols);
  else if (e.key === ' ') { e.preventDefault(); const t = grid().querySelector('.tile.active'); t?.classList.toggle('playing'); syncVideo(t); }
}

export async function deleteIds(ids) {
  if (!ids.length) return;
  if (ids.length > 1 && !confirm(`Remove ${plural(ids.length, 'sticker')} from EmoSticker? The files are deleted from your computer.`)) return;
  for (const id of ids) {
    try { await api.remove(id); } catch (e) { toast(e.message, 'bad'); }
    delete state.stickers[id];
    state.selected.delete(id);
    if (state.active === id) state.active = null;
  }
  for (const p of Object.values(state.packs)) p.stickers = p.stickers.filter((x) => !ids.includes(x));
  notify('all');
}

// ---- rendering ----
const tiles = new Map();

function render(what) {
  const g = grid();
  const ids = order();
  board().classList.toggle('has-stickers', ids.length > 0);
  board().classList.toggle('selecting', state.selected.size > 0);
  // reconcile tiles
  const seen = new Set();
  let prev = null;
  for (const id of ids) {
    let t = tiles.get(id);
    const s = state.stickers[id];
    if (!t) { t = makeTile(s); tiles.set(id, t); }
    if (what === 'all' || what === 'pack' || what === `sticker:${id}`) updateTile(t, s);
    t.classList.toggle('active', state.active === id);
    t.classList.toggle('selected', state.selected.has(id));
    t.setAttribute('aria-selected', state.active === id ? 'true' : 'false');
    if (prev ? prev.nextSibling !== t : g.firstChild !== t) g.insertBefore(t, prev ? prev.nextSibling : g.firstChild);
    prev = t;
    seen.add(id);
  }
  for (const [id, t] of tiles) if (!seen.has(id)) { t.remove(); tiles.delete(id); }
  // header bits
  const n = ids.length, sel = state.selected.size;
  const all = document.getElementById('selectAll');
  all.checked = n > 0 && sel === n; all.indeterminate = sel > 0 && sel < n;
  document.getElementById('selInfo').textContent = sel ? `${sel} selected` : '';
  document.getElementById('selActions').hidden = !sel;
  document.getElementById('pasteLook').disabled = !state.lookClipboard;
  const stickers = ids.map((i) => state.stickers[i]);
  const ready = stickers.filter((s) => s.out?.ready).length;
  const busy = stickers.filter((s) => ['rendering', 'queued'].includes(s.out?.status)).length;
  const bad = stickers.filter((s) => s.out?.status === 'error' || (s.out?.status === 'done' && !s.out?.ready)).length;
  const sum = document.getElementById('summary');
  sum.innerHTML = '';
  if (n) {
    sum.append(h('b', { text: `${ready}/${n}` }), ' ready');
    if (busy) sum.append(' · ', h('span', { text: `${busy} rendering` }));
    if (bad) sum.append(' · ', h('span', { class: 'warn-txt', text: `${bad} need a look` }));
  }
  const p = pack();
  document.getElementById('packPickTitle').textContent = p?.title || 'My stickers';
  document.getElementById('packCount').textContent = n ? plural(n, 'sticker') + (p?.type === 'custom_emoji' ? ' · emoji set' : '') : '';
  document.getElementById('playAll').hidden = !stickers.some((s) => s.source.kind === 'video');
}

function makeTile(s) {
  const t = h('div', { class: 'tile', role: 'option', tabindex: 0, dataset: { id: s.id }, draggable: 'true' });
  t.append(
    h('div', { class: 'tile-pic' }, h('img', { alt: '', draggable: 'false' }), h('video', { muted: true, loop: true, playsinline: true, draggable: 'false' })),
    h('div', { class: 'tile-check' }, icon('check')),
    h('div', { class: 'tile-status' }),
    h('div', { class: 'tile-video-badge' }),
    h('div', { class: 'tile-foot' }, h('span', { class: 'tile-emoji' }), h('span', { class: 'tile-meta' })),
    h('div', { class: 'spin', hidden: true }, h('div', { class: 'spinner' })),
  );
  t.addEventListener('mouseenter', () => { if (s.source.kind === 'video' && !isTouch) { t.classList.add('playing'); syncVideo(t); } });
  t.addEventListener('mouseleave', () => { if (!playAll) { t.classList.remove('playing'); syncVideo(t); } });
  return t;
}

function updateTile(t, s) {
  const out = s.out || {};
  const img = t.querySelector('img');
  const vid = t.querySelector('video');
  const isVideo = s.source.kind === 'video';
  const pic = out.status === 'done' ? (isVideo ? media(s.id, 'poster.png', out.gen) : media(s.id, out.file, out.gen)) : media(s.id, 'thumb.png');
  if (img.dataset.src !== pic) { img.dataset.src = pic; img.src = pic; }
  if (isVideo && out.status === 'done') {
    const src = (!canWebm && out.preview_mp4) ? media(s.id, out.preview_mp4, out.gen) : media(s.id, out.file, out.gen);
    if (vid.dataset.src !== src) { vid.dataset.src = src; vid.src = src; }
  }
  t.classList.toggle('playing', playAll && isVideo && out.status === 'done');
  syncVideo(t);
  const st = t.querySelector('.tile-status');
  st.className = 'tile-status ' + statusClass(out);
  st.title = statusText(out);
  t.querySelector('.spin').hidden = !['rendering', 'queued'].includes(out.status);
  t.querySelector('.tile-emoji').textContent = (s.emoji || [])[0] || '';
  const meta = t.querySelector('.tile-meta');
  meta.innerHTML = '';
  if (isVideo) meta.append(h('span', { text: out.duration ? fmtSecs(out.duration) : 'video' }));
  if (out.bytes) meta.append(h('span', { class: out.bytes > out.limit ? 'over' : '', text: fmtBytes(out.bytes) }));
  t.querySelector('.tile-video-badge').hidden = true;
  t.title = s.name;
}

function syncVideo(t) {
  if (!t) return;
  const v = t.querySelector('video');
  if (!v) return;
  if (t.classList.contains('playing') && v.src) v.play().catch(() => {});
  else { v.pause(); }
}

export function statusClass(out) {
  if (!out || out.status === 'queued' || out.status === 'rendering') return 'busy';
  if (out.status === 'error') return 'bad';
  if (out.ready) return 'ready';
  if (out.status === 'done' && !out.final) return 'busy';
  return 'warn';
}
export function statusText(out) {
  if (!out || out.status === 'queued') return 'Waiting to render';
  if (out.status === 'rendering') return 'Rendering';
  if (out.status === 'error') return 'Could not render: ' + (out.error || '');
  if (out.ready) return 'Ready for Telegram';
  if (out.status === 'done' && !out.final) return 'Preview; the final file is on its way';
  return 'Not ready: ' + (out.reasons || []).join(', ');
}

// ---- drag to reorder ----
function setupDrag(g) {
  let dragId = null;
  g.addEventListener('dragstart', (e) => {
    const t = e.target.closest('.tile');
    if (!t) return;
    dragId = t.dataset.id;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/x-emosticker', dragId);
    t.classList.add('dragging');
  });
  g.addEventListener('dragend', () => { g.querySelectorAll('.dragging, .drop-before, .drop-after').forEach((x) => x.classList.remove('dragging', 'drop-before', 'drop-after')); dragId = null; });
  g.addEventListener('dragover', (e) => {
    if (!dragId) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const t = e.target.closest('.tile');
    g.querySelectorAll('.drop-before, .drop-after').forEach((x) => x.classList.remove('drop-before', 'drop-after'));
    if (!t || t.dataset.id === dragId) return;
    const r = t.getBoundingClientRect();
    t.classList.add(e.clientX < r.left + r.width / 2 ? 'drop-before' : 'drop-after');
  });
  g.addEventListener('drop', async (e) => {
    if (!dragId) return;
    e.preventDefault();
    const t = e.target.closest('.tile');
    const ids = order();
    const moving = state.selected.has(dragId) ? ids.filter((i) => state.selected.has(i)) : [dragId];
    let rest = ids.filter((i) => !moving.includes(i));
    let at = rest.length;
    if (t && !moving.includes(t.dataset.id)) {
      const r = t.getBoundingClientRect();
      at = rest.indexOf(t.dataset.id) + (e.clientX < r.left + r.width / 2 ? 0 : 1);
    }
    const next = [...rest.slice(0, at), ...moving, ...rest.slice(at)];
    const p = pack();
    p.stickers = next;
    notify('pack');
    try { await api.patchPack(p.id, { stickers: next }); } catch (err) { toast(err.message, 'bad'); }
  });
}

// ---- adding files ----
export async function addFiles(files) {
  const list = [...files].filter((f) => f && (f.size > 0));
  if (!list.length) return;
  const t = toast(`Adding ${plural(list.length, 'file')}…`, 'info', 0);
  try {
    const res = await api.upload(list, (p) => { t.querySelector('span').textContent = `Uploading ${Math.round(p * 100)}%`; });
    t.remove();
    const bad = res.files.filter((f) => f.error);
    const ok = res.files.filter((f) => f.id);
    if (ok.length) toast(`${plural(ok.length, 'sticker')} added`, 'ok', 2000);
    for (const b of bad) toast(`${b.name}: ${b.error}`, 'bad', 6000);
    if (ok.length && !state.active) setActive(ok[0].id);
  } catch (e) { t.remove(); toast(e.message, 'bad'); }
}

export async function addLink(url) {
  if (!url) return;
  const t = toast('Fetching the link…', 'info', 0);
  try { const r = await api.fetchUrl(url); t.remove(); toast('Added', 'ok', 1500); setActive(r.id); }
  catch (e) { t.remove(); toast(e.message, 'bad', 6000); }
}

function setupFileDrop() {
  const veil = document.getElementById('dropVeil');
  let depth = 0;
  const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes('Files');
  document.addEventListener('dragenter', (e) => { if (hasFiles(e)) { depth++; veil.hidden = false; } });
  document.addEventListener('dragleave', () => { if (depth > 0 && --depth === 0) veil.hidden = true; });
  document.addEventListener('dragover', (e) => { if (hasFiles(e)) e.preventDefault(); });
  document.addEventListener('drop', async (e) => {
    depth = 0; veil.hidden = true;
    if (!hasFiles(e)) return;
    e.preventDefault();
    const files = await filesFromDrop(e.dataTransfer);
    if (files.length) addFiles(files);
    else {
      const url = e.dataTransfer.getData('text/uri-list') || e.dataTransfer.getData('text/plain');
      if (/^https?:\/\//.test(url || '')) addLink(url.trim());
    }
  });
  document.addEventListener('paste', (e) => {
    if (e.target.closest('input, textarea, [contenteditable]')) return;
    const items = [...(e.clipboardData?.items || [])];
    const files = items.filter((i) => i.kind === 'file').map((i) => i.getAsFile()).filter(Boolean);
    if (files.length) { e.preventDefault(); addFiles(files.map((f, i) => f.name ? f : new File([f], `pasted-${Date.now()}-${i}.png`, { type: f.type }))); return; }
    const text = e.clipboardData?.getData('text/plain')?.trim();
    if (text && /^https?:\/\/\S+$/.test(text)) { e.preventDefault(); addLink(text); }
  });
  const input = document.getElementById('fileInput');
  input.addEventListener('change', () => { addFiles(input.files); input.value = ''; });
  for (const id of ['addBtn', 'emptyAdd']) document.getElementById(id).addEventListener('click', () => input.click());
  document.getElementById('emptyLink').addEventListener('click', () => { const u = prompt('Paste a link to a picture or a video'); if (u) addLink(u.trim()); });
}

async function filesFromDrop(dt) {
  const out = [];
  const entries = [...(dt.items || [])].map((i) => i.webkitGetAsEntry?.()).filter(Boolean);
  if (!entries.length) return [...dt.files];
  const walk = async (entry, depth = 0) => {
    if (entry.isFile) {
      await new Promise((res) => entry.file((f) => { if (!f.name.startsWith('.')) out.push(f); res(); }, res));
    } else if (entry.isDirectory && depth < 4) {
      const reader = entry.createReader();
      let batch;
      do {
        batch = await new Promise((res) => reader.readEntries(res, () => res([])));
        for (const en of batch) await walk(en, depth + 1);
      } while (batch.length);
    }
  };
  for (const en of entries) await walk(en);
  return out.length ? out : [...dt.files];
}
