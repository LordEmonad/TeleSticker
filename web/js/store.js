// One observable store. The server is the source of truth; SSE keeps this copy current.
import { api } from './api.js';

const listeners = new Set();
export const state = {
  loaded: false,
  version: '',
  stickers: {},
  packs: {},
  currentPack: null,
  bot: { has_token: false },
  tools: {},
  tg: {},
  targets: {},
  selected: new Set(),   // ids ticked
  active: null,          // the id in the inspector
  busy: 0,
  lookClipboard: null,
};

export function subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); }
let scheduled = false;
export function notify(what = 'all') {
  if (scheduled) return;
  scheduled = true;
  requestAnimationFrame(() => { scheduled = false; for (const fn of listeners) fn(what); });
}

export async function load() {
  const s = await api.state();
  state.loaded = true;
  state.version = s.version;
  state.stickers = s.stickers;
  state.packs = s.packs;
  state.currentPack = s.current_pack;
  state.bot = s.bot;
  state.tools = s.tools;
  state.tg = s.tg;
  state.targets = s.targets;
  state.busy = s.busy;
  // forget selections that no longer exist
  for (const id of [...state.selected]) if (!state.stickers[id]) state.selected.delete(id);
  if (state.active && !state.stickers[state.active]) state.active = null;
  notify('all');
  return s;
}

export function pack() { return state.packs[state.currentPack] || Object.values(state.packs)[0]; }
export function order() { const p = pack(); return p ? p.stickers.filter((id) => state.stickers[id]) : []; }
export function stickersInOrder() { return order().map((id) => state.stickers[id]); }

export function setActive(id) {
  if (state.active === id) return;
  state.active = id;
  notify('active');
}

export function select(ids, mode = 'set') {
  if (mode === 'set') state.selected = new Set(ids);
  else if (mode === 'add') ids.forEach((i) => state.selected.add(i));
  else if (mode === 'toggle') ids.forEach((i) => state.selected.has(i) ? state.selected.delete(i) : state.selected.add(i));
  else if (mode === 'clear') state.selected.clear();
  notify('selection');
}

// ---- SSE ----
export function applyEvent(name, data) {
  if (name === 'sticker') {
    if (data.record) state.stickers[data.id] = data.record;
    else if (state.stickers[data.id] && data.out) state.stickers[data.id].out = data.out;
    if (data.record && !order().includes(data.id)) {
      const p = pack();
      if (p && !p.stickers.includes(data.id)) p.stickers.push(data.id);
    }
    notify('sticker:' + data.id);
  } else if (name === 'removed') {
    delete state.stickers[data.id];
    state.selected.delete(data.id);
    for (const p of Object.values(state.packs)) p.stickers = p.stickers.filter((x) => x !== data.id);
    if (state.active === data.id) state.active = null;
    notify('all');
  } else if (name === 'pack') {
    state.packs[data.id] = data;
    notify('pack');
  } else if (name === 'error') {
    notify('error');
  }
}

export function connect() {
  let es;
  let backoff = 1000;
  const open = () => {
    es = new EventSource('/api/events');
    for (const ev of ['sticker', 'removed', 'pack', 'publish', 'install', 'export', 'error']) {
      es.addEventListener(ev, (e) => {
        let data = {};
        try { data = JSON.parse(e.data); } catch { /* ignore */ }
        applyEvent(ev, data);
        for (const fn of eventFns) fn(ev, data);
      });
    }
    es.onopen = () => { backoff = 1000; if (state.loaded) load().catch(() => {}); };
    es.onerror = () => { es.close(); setTimeout(open, backoff); backoff = Math.min(15000, backoff * 1.6); };
  };
  open();
}
const eventFns = new Set();
export function onEvent(fn) { eventFns.add(fn); return () => eventFns.delete(fn); }
