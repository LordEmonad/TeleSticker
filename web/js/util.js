// Small helpers shared by every module.

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'html') el.innerHTML = v;
    else if (k === 'text') el.textContent = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === 'dataset') Object.assign(el.dataset, v);
    else if (v === true) el.setAttribute(k, '');
    else el.setAttribute(k, v);
  }
  for (const c of children.flat(Infinity)) {
    if (c == null || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return el;
}

export function icon(name, cls = 'i') {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', cls);
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', `/web/icons.svg#${name}`);
  svg.append(use);
  return svg;
}

export function fmtBytes(n) {
  if (n == null) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n < 10240 ? 1 : 0)} KB`;
  return `${(n / 1048576).toFixed(1)} MB`;
}

export function fmtSecs(s) {
  if (s == null) return '';
  return `${Number(s).toFixed(s < 10 ? 2 : 1)}s`;
}

export function debounce(fn, ms) {
  let t;
  const d = (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
  d.cancel = () => clearTimeout(t);
  d.flush = (...a) => { clearTimeout(t); fn(...a); };
  return d;
}

export function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

export function rgbHex([r, g, b]) {
  return '#' + [r, g, b].map((x) => Math.round(x).toString(16).padStart(2, '0')).join('');
}
export function hexRgb(hex) {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || '');
  return m ? [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)] : [255, 255, 255];
}

const toasts = () => document.getElementById('toasts');
export function toast(text, kind = 'info', ms = 3600) {
  const names = { ok: 'check', bad: 'warn', warn: 'warn', info: 'info' };
  const el = h('div', { class: `toast ${kind}`, role: 'status' }, icon(names[kind] || 'info'), h('span', { text }));
  const close = h('button', { title: 'Dismiss', onClick: () => el.remove() }, icon('x', 'i'));
  el.append(close);
  toasts().append(el);
  if (ms) setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; setTimeout(() => el.remove(), 320); }, ms);
  return el;
}

export function closeOnOutside(el, onClose) {
  const down = (e) => { if (!el.contains(e.target)) { cleanup(); onClose(); } };
  const key = (e) => { if (e.key === 'Escape') { cleanup(); onClose(); } };
  const cleanup = () => { document.removeEventListener('pointerdown', down, true); document.removeEventListener('keydown', key, true); };
  setTimeout(() => { document.addEventListener('pointerdown', down, true); document.addEventListener('keydown', key, true); }, 0);
  return cleanup;
}

export const isMac = /Mac|iPhone|iPad/.test(navigator.platform);
export const canWebm = (() => { const v = document.createElement('video'); return !!v.canPlayType && v.canPlayType('video/webm; codecs="vp9"') !== ''; })();
export const isTouch = matchMedia('(pointer: coarse)').matches;

export function copyText(text) {
  if (navigator.clipboard) return navigator.clipboard.writeText(text).catch(() => fallback());
  return Promise.resolve(fallback());
  function fallback() {
    const ta = h('textarea', { style: { position: 'fixed', opacity: 0 } }, text);
    document.body.append(ta); ta.select(); document.execCommand('copy'); ta.remove();
  }
}

export function plural(n, one, many) { return `${n} ${n === 1 ? one : (many || one + 's')}`; }
