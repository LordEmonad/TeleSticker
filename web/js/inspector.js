// The inspector: one sticker as it will look in a chat, and every control that shapes it.
import { api, media } from './api.js';
import { state, subscribe, setActive, pack, notify, order } from './store.js';
import { h, icon, fmtBytes, fmtSecs, debounce, clamp, rgbHex, hexRgb, toast, canWebm, copyText } from './util.js';
import { openEmojiPicker, QUICK, isEmoji } from './emoji.js';
import { deleteIds, statusClass, statusText } from './grid.js';
import { mountTrim } from './trim.js';
import { mountFrameEditor } from './frame.js';

const root = () => document.getElementById('insp');
let cur = null;        // id shown
let tab = 'look';
let previewBg = localStorage.getItem('emosticker.previewBg') || 'light';
let actual = false;
let pickMode = false;
let pending = {};      // edit fields sent as quick, awaiting the final render
let frameEditor = null;

export function initInspector() {
  subscribe((what) => {
    if (what === 'active' || what === 'all') { if (state.active !== cur) { cur = state.active; pending = {}; build(); } else if (what === 'all') build(); }
    else if (cur && what === `sticker:${cur}`) refresh();
    else if (what === 'pack') refresh();
  });
  document.getElementById('inspector').addEventListener('click', (e) => { if (e.target.closest('.insp-close')) { document.getElementById('inspector').classList.remove('open'); } });
}

const s = () => state.stickers[cur];
const edit = () => s()?.edit || {};

// ---- edits ----
const flushFinal = debounce(async () => { if (!cur) return; try { await api.render(cur); } catch { /* the next event says */ } }, 1400);

async function send(partial, { quick = false } = {}) {
  if (!cur) return;
  const st = s();
  // optimistic local merge so controls do not snap back
  st.edit = { ...st.edit };
  for (const [k, v] of Object.entries(partial)) { if (v === null) delete st.edit[k]; else st.edit[k] = v; }
  st.out = { ...(st.out || {}), status: 'queued' };
  notify(`sticker:${cur}`);
  try {
    await api.patch(cur, { edit: partial, quick });
    if (quick) flushFinal(); else flushFinal.cancel();
  } catch (e) { toast(e.message, 'bad'); }
}
const sendQuick = debounce((p) => send(p, { quick: true }), 180);
let quickBuf = {};
function live(partial) { Object.assign(quickBuf, partial); const b = quickBuf; sendQuick(b); quickBuf = {}; Object.assign(quickBuf, b); }
function commit(partial) { sendQuick.cancel(); quickBuf = {}; send(partial); }

async function patchMeta(body) {
  const st = s();
  Object.assign(st, body);
  notify(`sticker:${cur}`);
  try { await api.patch(cur, body); } catch (e) { toast(e.message, 'bad'); }
}

// ---- build ----
function build() {
  const r = root();
  const empty = document.getElementById('inspEmpty');
  if (!cur || !s()) { r.hidden = true; empty.hidden = false; r.innerHTML = ''; return; }
  empty.hidden = true; r.hidden = false;
  r.innerHTML = '';
  const st = s();
  const isVideo = st.source.kind === 'video';
  const name = h('input', { class: 'insp-name', value: st.name, spellcheck: 'false', title: 'Rename', onChange: (e) => patchMeta({ name: e.target.value.trim() || st.name }) });
  name.addEventListener('keydown', (e) => { if (e.key === 'Enter') e.target.blur(); e.stopPropagation(); });
  const menuBtn = h('button', { class: 'btn icon ghost small', title: 'More', onClick: (e) => moreMenu(e.currentTarget) }, icon('grip'));
  const close = h('button', { class: 'insp-close', title: 'Close' }, icon('x'));
  r.append(h('div', { class: 'insp-head' }, name, menuBtn, close));
  r.append(h('div', { class: 'insp-sub', id: 'inspSub' }));
  // preview
  const pv = h('div', { class: `preview ${previewBg}${actual ? ' actual' : ''}`, id: 'preview' },
    h('div', { class: 'stage' }, isVideo ? h('video', { muted: true, loop: true, autoplay: true, playsinline: true }) : h('img', { alt: '' })),
    h('div', { class: 'bubble-time', text: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }),
  );
  pv.addEventListener('click', onPreviewClick);
  const bar = h('div', { class: 'preview-bar' },
    seg([['light', icon('sun'), 'Light chat'], ['dark', icon('moon'), 'Dark chat'], ['check', null, 'Grid']], previewBg, (v) => { previewBg = v; localStorage.setItem('emosticker.previewBg', v); pv.className = `preview ${v}${actual ? ' actual' : ''}`; }),
    h('span', { class: 'spacer' }),
    seg([['chat', null, 'Chat size'], ['actual', null, '1:1']], actual ? 'actual' : 'chat', (v) => { actual = v === 'actual'; pv.classList.toggle('actual', actual); }),
  );
  r.append(h('div', { class: 'preview-wrap' }, pv, bar));
  r.append(h('div', { class: 'status', id: 'status' }));
  // tabs
  const tabs = [['look', 'Look'], ['bg', 'Background'], ...(isVideo ? [['motion', 'Motion']] : []), ['tags', 'Emoji & tags']];
  if (!tabs.some(([k]) => k === tab)) tab = 'look';
  const tabBar = h('div', { class: 'tabs' }, tabs.map(([k, label]) => h('button', { class: k === tab ? 'on' : '', dataset: { tab: k }, text: label, onClick: () => { tab = k; r.querySelectorAll('.tabs button').forEach((b) => b.classList.toggle('on', b.dataset.tab === k)); r.querySelectorAll('.panel').forEach((p) => p.classList.toggle('on', p.dataset.panel === k)); if (k === 'look') frameEditor?.refresh(); } })));
  r.append(tabBar);
  r.append(panelLook(), panelBg(), ...(isVideo ? [panelMotion()] : []), panelTags());
  refresh();
}

function seg(items, value, onChange) {
  const el = h('div', { class: 'seg' });
  for (const [v, ic, label] of items) {
    const b = h('button', { type: 'button', class: v === value ? 'on' : '', title: label, dataset: { v } }, ic || null, ic ? null : label);
    b.addEventListener('click', () => { el.querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b)); onChange(v); });
    el.append(b);
  }
  return el;
}

function refresh() {
  const st = s();
  if (!st || !root().children.length) return;
  const out = st.out || {};
  const isVideo = st.source.kind === 'video';
  const src = st.source;
  document.getElementById('inspSub').textContent = `${isVideo ? 'video' : 'image'} · ${src.width}×${src.height}${isVideo ? ` · ${fmtSecs(src.duration)} · ${Math.round(src.fps)} fps` : ''}${src.alpha ? ' · alpha' : ''} · ${fmtBytes(src.bytes)}`;
  // preview media
  const pv = document.getElementById('preview');
  const stage = pv.querySelector('.stage');
  pv.querySelector('.veil')?.remove();
  pv.querySelector('.err')?.remove();
  if (out.status === 'done') {
    if (isVideo) {
      const v = stage.querySelector('video');
      const url = (!canWebm && out.preview_mp4) ? media(cur, out.preview_mp4, out.gen) : media(cur, out.file, out.gen);
      if (v.dataset.src !== url) { v.dataset.src = url; v.src = url; v.play().catch(() => {}); }
    } else {
      const img = stage.querySelector('img');
      const url = media(cur, out.file, out.gen);
      if (img.dataset.src !== url) { img.dataset.src = url; img.src = url; }
    }
  } else if (out.status === 'error') {
    pv.append(h('div', { class: 'err', text: out.error || 'Could not render' }));
  } else {
    const img = stage.querySelector('img');
    if (img && !img.src) img.src = media(cur, 'thumb.png');
    pv.append(h('div', { class: 'veil' }, h('div', { class: 'spinner' })));
  }
  // status
  const box = document.getElementById('status');
  box.className = 'status ' + statusClass(out);
  box.innerHTML = '';
  box.append(h('div', { class: 'status-line' }, h('span', { class: 'dot' }), h('b', { text: statusText(out).split(':')[0] })));
  if (out.status === 'done') {
    const facts = [`${out.width}×${out.height}`, fmtBytes(out.bytes) + (out.limit ? ` / ${fmtBytes(out.limit)}` : '')];
    if (isVideo) { facts.push(fmtSecs(out.duration), `${Math.round(out.fps)} fps`, `crf ${out.crf}`); if (out.speed && out.speed > 1.01) facts.push(`${out.speed}× faster`); if (out.seam != null) facts.push(`loop seam ${out.seam}`); }
    else facts.push(out.lossless ? 'lossless' : `quality ${out.quality}`);
    facts.push(out.alpha ? 'transparent' : 'no transparency');
    box.append(h('div', { class: 'status-facts' }, facts.map((f) => h('span', { text: f }))));
    const frac = out.limit ? out.bytes / out.limit : 0;
    box.append(h('div', { class: `budget ${frac > 1 ? 'bad' : frac > .9 ? 'warn' : ''}` }, h('i', { style: { width: `${Math.min(100, frac * 100)}%` } })));
    if (out.reasons?.length) box.append(h('div', { class: 'reasons', text: 'Not accepted: ' + out.reasons.join(', ') }));
    if (!out.alpha && !isVideo && !(edit().bg?.mode)) box.append(h('div', { class: 'note', style: { marginTop: '6px' }, text: 'No transparent area: it will show as a square. Background tab removes one.' }));
  } else if (out.status === 'error') box.append(h('div', { class: 'err-text', text: out.error }));
  // panels that mirror state
  root().querySelectorAll('[data-sync]').forEach((el) => el._sync && el._sync());
}

// ---- Look ----
function panelLook() {
  const st = s();
  const e = edit();
  const p = h('div', { class: `panel ${tab === 'look' ? 'on' : ''}`, dataset: { panel: 'look' } });
  const square = pack()?.type === 'custom_emoji';
  const fitRow = h('div', { class: 'field' }, h('div', { class: 'lbl', text: 'Frame' }));
  const fitSeg = seg([['fit', null, 'Fit'], ['square', null, 'Square'], ['fill', null, 'Fill']], square && e.fit !== 'fill' ? 'square' : (e.fit || 'fit'), (v) => { commit({ fit: v }); frameEditor?.setMode(v); });
  fitSeg.classList.add('grow');
  fitRow.append(fitSeg, h('div', { class: 'note', text: square ? 'Custom emoji are always 100×100. Fill crops to a square; Square pads it.' : 'Fit keeps the whole picture (one side 512). Square pads to 512×512. Fill crops to a square about the focus point.' }));
  p.append(fitRow);
  // the frame editor: crop + focus
  const fe = h('div', { class: 'field' }, h('div', { class: 'lbl' }, 'Crop', h('span', { class: 'val' }, h('button', { class: 'btn small ghost', text: 'Reset', onClick: () => { commit({ crop: null, focus: null }); frameEditor?.set({ crop: null, focus: null }); } }))));
  frameEditor = mountFrameEditor(fe, {
    id: cur, mode: square && e.fit !== 'fill' ? 'square' : (e.fit || 'fit'), crop: e.crop || null, focus: e.focus || [0.5, 0.5], rotate: e.rotate || 0,
    onChange: (v, final) => (final ? commit : live)(v),
  });
  p.append(fe);
  const margin = sliderField('Breathing room', e.margin || 0, 0, 0.3, 0.01, (v) => `${Math.round(v * 100)}%`, (v, final) => (final ? commit : live)({ margin: v || null }));
  p.append(margin);
  // these read edit() when pressed: the `e` captured at build time goes stale after the first press
  const turn = (partial) => { commit(partial); setTimeout(() => frameEditor?.refresh(), 150); };
  const flipH = h('button', { title: 'Flip horizontally', class: e.flip_h ? 'on' : '', onClick: () => { const on = !edit().flip_h; flipH.classList.toggle('on', on); turn({ flip_h: on || null }); } }, icon('fliph'));
  const flipV = h('button', { title: 'Flip vertically', class: e.flip_v ? 'on' : '', onClick: () => { const on = !edit().flip_v; flipV.classList.toggle('on', on); turn({ flip_v: on || null }); } }, icon('flipv'));
  p.append(h('div', { class: 'row' }, h('label', { text: 'Turn' }), h('div', { class: 'iconbar' },
    h('button', { title: 'Rotate left', onClick: () => turn({ rotate: (((edit().rotate || 0) + 270) % 360) || null }) }, icon('rotl')),
    h('button', { title: 'Rotate right', onClick: () => turn({ rotate: (((edit().rotate || 0) + 90) % 360) || null }) }, icon('rotr')),
    flipH, flipV,
  )));
  // outline
  const ol = e.outline || {};
  const olOn = toggleRow('Outline', !!ol.width, (on) => commit({ outline: on ? { width: ol.width || 10, color: ol.color || [255, 255, 255], opacity: 1 } : null }));
  const olSub = h('div', { class: 'sub', hidden: !ol.width },
    sliderField('Width', ol.width || 10, 2, 40, 1, (v) => `${v}px`, (v, final) => (final ? commit : live)({ outline: { ...(edit().outline || {}), width: v, color: (edit().outline || {}).color || [255, 255, 255], opacity: 1 } })),
    h('div', { class: 'row' }, h('label', { text: 'Colour' }), swatch(ol.color || [255, 255, 255], (c) => commit({ outline: { ...(edit().outline || {}), width: (edit().outline || {}).width || 10, color: c, opacity: 1 } })),
      h('button', { class: 'btn small ghost', text: 'White', onClick: () => commit({ outline: { ...(edit().outline || {}), width: (edit().outline || {}).width || 10, color: [255, 255, 255], opacity: 1 } }) }),
      h('button', { class: 'btn small ghost', text: 'Black', onClick: () => commit({ outline: { ...(edit().outline || {}), width: (edit().outline || {}).width || 10, color: [0, 0, 0], opacity: 1 } }) })),
  );
  p.append(olOn, olSub);
  const sh = e.shadow || {};
  const shOn = toggleRow('Shadow', !!sh.opacity, (on) => commit({ shadow: on ? { blur: 6, offset: [0, 4], opacity: 0.45 } : null }));
  const shSub = h('div', { class: 'sub', hidden: !sh.opacity }, sliderField('Strength', sh.opacity || .45, .1, 1, .05, (v) => `${Math.round(v * 100)}%`, (v, final) => (final ? commit : live)({ shadow: { blur: 6, offset: [0, 4], opacity: v } })));
  p.append(shOn, shSub);
  if (st.source.kind !== 'video') {
    p.append(h('div', { class: 'row' }, h('label', { text: 'File' }), seg([['webp', null, 'WebP'], ['png', null, 'PNG']], e.format || 'webp', (v) => commit({ format: v })), h('span', { class: 'note', text: 'WebP is lossless when it fits.' })));
  }
  p.append(h('div', { class: 'row' }, h('label', { text: 'Bars' }), h('label', { class: 'toggle' }, h('input', { type: 'checkbox', checked: e.bars !== false, onChange: (ev) => commit({ bars: ev.target.checked ? null : false }) }), h('span', { class: 'sw' }), h('span', { text: 'Cut black bars off automatically' }))));
  return p;
}

function toggleRow(label, on, onChange) {
  const input = h('input', { type: 'checkbox', checked: on, onChange: (e) => { onChange(e.target.checked); const sub = row.nextElementSibling; if (sub?.classList.contains('sub')) sub.hidden = !e.target.checked; } });
  const row = h('div', { class: 'row' }, h('label', { text: label }), h('label', { class: 'toggle' }, input, h('span', { class: 'sw' })));
  return row;
}

function sliderField(label, value, min, max, step, fmt, onChange, opts = {}) {
  const val = h('span', { class: 'val', text: fmt(value) });
  const input = h('input', { type: 'range', min, max, step, value, disabled: opts.disabled || false });
  input.addEventListener('input', () => { const v = parseFloat(input.value); val.textContent = fmt(v); onChange(v, false); });
  input.addEventListener('change', () => onChange(parseFloat(input.value), true));
  const f = h('div', { class: 'field' }, h('div', { class: 'lbl' }, label, val), input);
  f._input = input;
  f._set = (v) => { input.value = v; val.textContent = fmt(v); };
  return f;
}

function swatch(rgb, onChange) {
  const fill = h('i', { style: { background: rgbHex(rgb) } });
  const input = h('input', { type: 'color', value: rgbHex(rgb) });
  input.addEventListener('input', () => { fill.style.background = input.value; });
  input.addEventListener('change', () => onChange(hexRgb(input.value)));
  const sw = h('button', { class: 'swatch', type: 'button', title: 'Pick a colour' }, fill, input);
  sw.addEventListener('click', (e) => { if (e.target !== input) input.click(); });
  sw._set = (c) => { fill.style.background = rgbHex(c); input.value = rgbHex(c); };
  return sw;
}

// ---- Background ----
function panelBg() {
  const e = edit();
  const bg = e.bg || { mode: 'none' };
  const p = h('div', { class: `panel ${tab === 'bg' ? 'on' : ''}`, dataset: { panel: 'bg' } });
  const ai = state.tools.rembg;
  const modeSeg = seg([['none', null, 'Keep'], ['key', null, 'Colour key'], ['ai', null, ai ? 'AI cut-out' : 'AI (install)']], bg.mode || 'none', (v) => {
    if (v === 'ai' && !ai) { modeSeg.querySelectorAll('button').forEach((b) => b.classList.toggle('on', b.dataset.v === (bg.mode || 'none'))); openInstallAi(); return; }
    commit({ bg: v === 'none' ? null : { ...bg, mode: v } });
    keySub.hidden = v !== 'key'; aiSub.hidden = v !== 'ai';
  });
  modeSeg.classList.add('grow');
  p.append(h('div', { class: 'field' }, h('div', { class: 'lbl', text: 'Remove the background' }), modeSeg,
    h('div', { class: 'note', text: 'Colour key takes out one colour and everything close to it: green screens, flat backgrounds, white cards. AI cut-out finds the subject in a photo.' })));
  // key controls
  const col = bg.color || s().out?.key_color || null;
  const sw = swatch(col || [0, 255, 0], (c) => commit({ bg: { ...bgNow(), mode: 'key', color: c } }));
  const pickBtn = h('button', { class: 'btn small ghost', onClick: () => startPick() }, icon('eyedrop'), 'Pick from picture');
  const autoBtn = h('button', { class: 'btn small ghost', text: 'Auto', title: 'The colour most of the border shares', onClick: () => commit({ bg: { ...bgNow(), mode: 'key', color: null } }) });
  const keySub = h('div', { class: 'sub', hidden: bg.mode !== 'key' },
    h('div', { class: 'row' }, h('label', { text: 'Colour' }), sw, pickBtn, autoBtn),
    h('div', { class: 'note', dataset: { sync: 1 }, text: '' }),
    sliderField('Tolerance', bg.tolerance ?? 0.18, 0.02, 0.6, 0.01, (v) => `${Math.round(v * 100)}`, (v, f) => (f ? commit : live)({ bg: { ...bgNow(), mode: 'key', tolerance: v } })),
    sliderField('Softness', bg.softness ?? 0.10, 0, 0.4, 0.01, (v) => `${Math.round(v * 100)}`, (v, f) => (f ? commit : live)({ bg: { ...bgNow(), mode: 'key', softness: v } })),
    sliderField('Shrink edge', bg.erode ?? 0, 0, 6, 1, (v) => `${v}px`, (v, f) => (f ? commit : live)({ bg: { ...bgNow(), mode: 'key', erode: v } })),
    sliderField('Feather', bg.feather ?? 0, 0, 6, 1, (v) => `${v}px`, (v, f) => (f ? commit : live)({ bg: { ...bgNow(), mode: 'key', feather: v } })),
    h('div', { class: 'row wrap' },
      h('label', { class: 'toggle' }, h('input', { type: 'checkbox', checked: bg.despill !== 0, onChange: (ev) => commit({ bg: { ...bgNow(), mode: 'key', despill: ev.target.checked ? 1 : 0 } }) }), h('span', { class: 'sw' }), h('span', { text: 'Despill edges' })),
      h('label', { class: 'toggle' }, h('input', { type: 'checkbox', checked: !!bg.keep_inside, onChange: (ev) => commit({ bg: { ...bgNow(), mode: 'key', keep_inside: ev.target.checked } }) }), h('span', { class: 'sw' }), h('span', { text: 'Keep enclosed holes' })),
    ),
  );
  const note = keySub.querySelector('[data-sync]');
  note._sync = () => { const c = (edit().bg || {}).color || s().out?.key_color; if (c) { sw._set(c); note.textContent = (edit().bg || {}).color ? '' : `Auto picked ${rgbHex(c)} from the border`; } };
  p.append(keySub);
  const models = state.tools.rembg_models || [];
  const aiSub = h('div', { class: 'sub', hidden: bg.mode !== 'ai' },
    h('div', { class: 'row' }, h('label', { text: 'Model' }), h('select', { class: 'text', onChange: (ev) => commit({ bg: { ...bgNow(), mode: 'ai', model: ev.target.value } }) }, models.map(([k, label]) => h('option', { value: k, selected: (bg.model || 'isnet-general-use') === k, text: label })))),
    h('label', { class: 'toggle' }, h('input', { type: 'checkbox', checked: bg.matting !== false, onChange: (ev) => commit({ bg: { ...bgNow(), mode: 'ai', matting: ev.target.checked } }) }), h('span', { class: 'sw' }), h('span', { text: 'Soft edges (alpha matting)' })),
    h('div', { class: 'note', text: s().source.kind === 'video' ? 'On a video the model runs on every frame: slow, and the edges can flicker. For green screens, Colour key is better.' : 'The first use downloads the model (about 170 MB).' }),
  );
  p.append(aiSub);
  p.append(h('div', { class: 'row' }, h('label', { text: 'Trim' }), h('label', { class: 'toggle' }, h('input', { type: 'checkbox', checked: e.trim_content !== false, onChange: (ev) => commit({ trim_content: ev.target.checked ? null : false }) }), h('span', { class: 'sw' }), h('span', { text: 'Crop empty space round the subject' }))));
  return p;
}
const bgNow = () => ({ ...(edit().bg || {}) });

function startPick() {
  pickMode = true;
  const pv = document.getElementById('preview');
  pv.classList.add('pickmode');
  pv.append(h('div', { class: 'pick-hint', text: 'Tap the colour to remove (Esc to cancel)' }));
  // show the source frame so the colour is still there to tap
  const stage = pv.querySelector('.stage');
  const old = stage.firstElementChild;
  const img = h('img', { alt: '', src: `/api/sticker/${cur}/frame?t=${edit().start || 0}&r=${Date.now()}` });
  old.hidden = true;
  stage.append(img);
  const esc = (e) => { if (e.key === 'Escape') endPick(); };
  document.addEventListener('keydown', esc);
  pv._endPick = () => { document.removeEventListener('keydown', esc); img.remove(); old.hidden = false; pv.classList.remove('pickmode'); pv.querySelector('.pick-hint')?.remove(); pickMode = false; };
}
function endPick() { document.getElementById('preview')?._endPick?.(); }
async function onPreviewClick(e) {
  if (!pickMode) return;
  const img = e.currentTarget.querySelector('.stage img:not([hidden])');
  if (!img || e.target !== img) return;
  const r = img.getBoundingClientRect();
  const x = clamp((e.clientX - r.left) / r.width, 0, 1), y = clamp((e.clientY - r.top) / r.height, 0, 1);
  endPick();
  try {
    const res = await api.pick(cur, x, y);
    commit({ bg: { ...bgNow(), mode: 'key', color: res.color } });
    toast(`Keying ${rgbHex(res.color)}`, 'ok', 1500);
    root().querySelector('[data-panel="bg"] .seg button[data-v="key"]')?.click();
  } catch (err) { toast(err.message, 'bad'); }
}

// ---- Motion ----
function panelMotion() {
  const st = s();
  const e = edit();
  const src = st.source;
  const p = h('div', { class: `panel ${tab === 'motion' ? 'on' : ''}`, dataset: { panel: 'motion' } });
  const maxS = state.tg.video_seconds || 3;
  const trimVal = h('span', { class: 'val' });
  const trimField = h('div', { class: 'field' }, h('div', { class: 'lbl' }, 'Trim', trimVal));
  const updateTrimVal = (a, b) => { const d = b - a; trimVal.innerHTML = `<b>${fmtSecs(a)}</b> → <b>${fmtSecs(b)}</b> · ${d > maxS + 0.01 ? `<span class="too-long">${fmtSecs(d)}</span>` : fmtSecs(d)}`; };
  const trim = mountTrim(trimField, {
    strip: media(cur, 'strip.jpg'), duration: src.duration, start: e.start || 0, end: e.end || src.duration,
    onChange: (a, b, final) => { (final ? commit : live)({ start: a > 0.01 ? +a.toFixed(3) : null, end: b < src.duration - 0.01 ? +b.toFixed(3) : null }); updateTrimVal(a, b); },
  });
  updateTrimVal(e.start || 0, e.end || src.duration);
  p.append(trimField);
  const mode = e.fit_time || 'speed';
  const fitRow = h('div', { class: 'field' }, h('div', { class: 'lbl', text: `Longer than ${maxS}s?` }));
  const fitSeg = seg([['speed', null, 'Speed up'], ['cut', null, 'Cut'], ['loop', null, 'Find loop']], mode, (v) => commit({ fit_time: v === 'speed' ? null : v }));
  fitSeg.classList.add('grow');
  fitRow.append(fitSeg, h('div', { class: 'note', dataset: { sync: 1 } }));
  fitRow.querySelector('[data-sync]')._sync = () => {
    const o = s().out || {}; const m = edit().fit_time || 'speed'; const n = fitRow.querySelector('[data-sync]');
    if (m === 'loop') n.textContent = o.loop_window ? `Best loop found: ${fmtSecs(o.loop_window[0])} to ${fmtSecs(o.loop_window[1])} inside the trim (seam ${o.seam_found}). Lower is smoother; under 1.5 is good.` : 'Looks through the trimmed clip for the stretch that wraps round best.';
    else if (m === 'cut') n.textContent = `Keeps the first ${maxS} seconds of the trim.`;
    else n.textContent = o.speed > 1.01 ? `Playing ${o.speed}× faster to fit ${maxS}s. Trim it instead if that looks rushed.` : 'Plays the whole trim faster if it is too long.';
  };
  p.append(fitRow);
  const findBtn = h('button', { class: 'btn small ghost', onClick: async () => {
    findBtn.disabled = true;
    try { const r = await api.findLoop(cur); trim.set(r.start, r.end); commit({ start: r.start > 0.01 ? r.start : null, end: r.end < src.duration - 0.01 ? r.end : null, fit_time: null }); updateTrimVal(r.start, r.end); toast(`Trimmed to the best loop (seam ${r.seam})`, 'ok'); }
    catch (err) { toast(err.message, 'bad'); } finally { findBtn.disabled = false; }
  } }, icon('loop'), 'Trim to best loop');
  p.append(h('div', { class: 'row' }, findBtn, h('span', { class: 'note', text: 'Sets the trim handles to the stretch that loops best.' })));
  p.append(h('div', { class: 'row wrap' },
    h('label', { class: 'toggle' }, h('input', { type: 'checkbox', checked: !!e.boomerang, onChange: (ev) => commit({ boomerang: ev.target.checked || null }) }), h('span', { class: 'sw' }), h('span', { text: 'Boomerang (forward, then back)' })),
    h('label', { class: 'toggle' }, h('input', { type: 'checkbox', checked: !!e.reverse, onChange: (ev) => commit({ reverse: ev.target.checked || null }) }), h('span', { class: 'sw' }), h('span', { text: 'Reverse' })),
  ));
  p.append(sliderField('Blend the loop point', e.blend || 0, 0, 12, 1, (v) => (v ? `${v} frames` : 'off'), (v, f) => (f ? commit : live)({ blend: v || null })));
  p.append(h('div', { class: 'row' }, h('label', { text: 'Frame rate' }), seg([[30, null, '30'], [24, null, '24'], [20, null, '20'], [15, null, '15']], e.fps || 30, (v) => commit({ fps: v === 30 ? null : v })), h('span', { class: 'note', text: 'Fewer frames, more quality each.' })));
  return p;
}

// ---- Tags ----
function panelTags() {
  const st = s();
  const p = h('div', { class: `panel ${tab === 'tags' ? 'on' : ''}`, dataset: { panel: 'tags' } });
  const row = h('div', { class: 'emoji-row', dataset: { sync: 1 } });
  const renderEmoji = () => {
    row.innerHTML = '';
    for (const em of s().emoji || []) {
      row.append(h('span', { class: 'emoji-chip' }, em, h('button', { class: 'rm', title: 'Remove', onClick: () => patchMeta({ emoji: (s().emoji || []).filter((x) => x !== em) }) }, '✕')));
    }
    const add = h('button', { class: 'emoji-chip add', text: '+ add' });
    add.addEventListener('click', () => openEmojiPicker(add, (em) => { const list = s().emoji || []; if (!list.includes(em)) patchMeta({ emoji: [...list, em].slice(0, 20) }); }));
    row.append(add);
  };
  row._sync = renderEmoji;
  renderEmoji();
  p.append(h('div', { class: 'field' }, h('div', { class: 'lbl' }, 'Emoji', h('span', { class: 'val', text: 'first one shows in Telegram' })), row,
    h('div', { class: 'quick-emoji' }, QUICK.map((em) => h('button', { title: 'Set as the emoji', onClick: () => patchMeta({ emoji: [em, ...(s().emoji || []).filter((x) => x !== em)].slice(0, 20) }) }, em)))));
  const tags = h('div', { class: 'tags' });
  const input = h('input', { placeholder: 'keyword, Enter' });
  const renderTags = () => {
    tags.querySelectorAll('.tag').forEach((t) => t.remove());
    for (const k of s().keywords || []) tags.insertBefore(h('span', { class: 'tag' }, k, h('button', { onClick: () => patchMeta({ keywords: (s().keywords || []).filter((x) => x !== k) }) }, '✕')), input);
  };
  input.addEventListener('keydown', (ev) => {
    ev.stopPropagation();
    if ((ev.key === 'Enter' || ev.key === ',') && input.value.trim()) { ev.preventDefault(); const k = input.value.trim().replace(/,$/, ''); input.value = ''; if (!(s().keywords || []).includes(k)) patchMeta({ keywords: [...(s().keywords || []), k] }); }
    if (ev.key === 'Backspace' && !input.value && (s().keywords || []).length) patchMeta({ keywords: (s().keywords || []).slice(0, -1) });
  });
  tags.append(input);
  tags.addEventListener('click', () => input.focus());
  renderTags();
  tags.dataset.sync = 1; tags._sync = renderTags;
  p.append(h('div', { class: 'field' }, h('div', { class: 'lbl' }, 'Search keywords', h('span', { class: 'val', text: 'up to 64 letters in all' })), tags,
    h('div', { class: 'note', text: 'People find the sticker by typing these in Telegram.' })));
  return p;
}

// ---- more menu ----
function moreMenu(anchor) {
  document.querySelector('.menu.floating')?.remove();
  const st = s();
  const m = h('div', { class: 'menu floating', style: { position: 'fixed', zIndex: 80 } });
  const item = (label, ic, fn, cls) => h('button', { class: cls || '', onClick: () => { m.remove(); fn(); } }, ic ? icon(ic) : null, label);
  const ids = order();
  const at = ids.indexOf(cur);
  const moveBy = async (d) => {
    const next = [...ids]; const j = Math.max(0, Math.min(next.length - 1, at + d));
    next.splice(at, 1); next.splice(j, 0, cur);
    const p = pack(); p.stickers = next; notify('pack');
    try { await api.patchPack(p.id, { stickers: next }); } catch (e) { toast(e.message, 'bad'); }
  };
  m.append(
    item('Download this file', 'download', () => { location.href = `/api/sticker/${cur}/download`; }),
    item('Duplicate', 'copy', async () => { try { const r = await api.duplicate(cur); setActive(r.id); } catch (e) { toast(e.message, 'bad'); } }),
    at > 0 ? item('Move earlier in the pack', 'rotl', () => moveBy(-1)) : null,
    at < ids.length - 1 ? item('Move later in the pack', 'rotr', () => moveBy(1)) : null,
    item('Copy look', 'copy', () => { state.lookClipboard = { ...st.edit }; delete state.lookClipboard.crop; delete state.lookClipboard.start; delete state.lookClipboard.end; toast('Look copied: pick other stickers and Paste look', 'ok'); notify('selection'); }),
    item('Render again', 'loop', () => api.render(cur).catch((e) => toast(e.message, 'bad'))),
    item('Copy source path', 'link', () => copyText(st.source.path).then(() => toast('Path copied', 'ok', 1500))),
    h('hr'),
    item('Remove sticker', 'trash', () => deleteIds([cur]), 'on'),
  );
  document.body.append(m);
  const r = anchor.getBoundingClientRect();
  m.style.top = `${r.bottom + 6}px`; m.style.left = `${Math.min(r.left, innerWidth - m.offsetWidth - 8)}px`;
  const cleanup = () => m.remove();
  import('./util.js').then(({ closeOnOutside }) => closeOnOutside(m, cleanup));
}

export function openInstallAi() { document.dispatchEvent(new CustomEvent('emosticker:install-ai')); }
