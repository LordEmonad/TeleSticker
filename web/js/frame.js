// The frame editor: a crop box with eight handles over the source frame, or a focus point for Fill.
import { h, clamp } from './util.js';

export function mountFrameEditor(parent, { id, mode, crop, focus, rotate, onChange }) {
  const el = h('div', { class: 'frame-ed' });
  const img = h('img', { alt: '', draggable: 'false' });
  el.append(img);
  parent.append(el);
  let state = { mode, crop: crop ? [...crop] : null, focus: [...(focus || [0.5, 0.5])] };
  let box = null, focusEl = null, fillBox = null;
  let ready = false;

  function load() {
    img.src = `/api/sticker/${id}/frame?r=${Date.now()}`;
  }
  img.addEventListener('load', () => { ready = true; render(); });
  load();

  function rect() { return { w: img.clientWidth, h: img.clientHeight, left: img.offsetLeft, top: img.offsetTop }; }

  function render() {
    if (!ready) return;
    box?.remove(); focusEl?.remove(); fillBox?.remove();
    box = focusEl = fillBox = null;
    const r = rect();
    if (state.mode === 'fill') {
      // the square that Fill keeps, about the focus point
      const side = Math.min(r.w, r.h);
      const fx = clamp(state.focus[0], 0, 1), fy = clamp(state.focus[1], 0, 1);
      const x = r.left + (r.w - side) * fx, y = r.top + (r.h - side) * fy;
      fillBox = h('div', { class: 'fillbox', style: { left: `${x}px`, top: `${y}px`, width: `${side}px`, height: `${side}px` } });
      focusEl = h('div', { class: 'focus', title: 'Drag to choose what stays in the square', style: { left: `${r.left + r.w * fx}px`, top: `${r.top + r.h * fy}px` } });
      el.append(fillBox, focusEl);
      dragFocus(focusEl);
    } else {
      const c = state.crop || [0, 0, 1, 1];
      box = h('div', { class: 'cropbox', style: { left: `${r.left + c[0] * r.w}px`, top: `${r.top + c[1] * r.h}px`, width: `${c[2] * r.w}px`, height: `${c[3] * r.h}px` } });
      for (const k of ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w']) box.append(h('div', { class: `h ${k}`, dataset: { k } }));
      el.append(box);
      dragCrop(box);
    }
  }

  function dragFocus(target) {
    target.addEventListener('pointerdown', (e) => {
      e.preventDefault(); target.setPointerCapture(e.pointerId);
      const r = rect();
      const move = (ev) => {
        const b = img.getBoundingClientRect();
        state.focus = [clamp((ev.clientX - b.left) / b.width, 0, 1), clamp((ev.clientY - b.top) / b.height, 0, 1)];
        render(); onChange({ focus: state.focus.map((v) => +v.toFixed(3)) }, false);
      };
      const up = () => { target.removeEventListener('pointermove', move); onChange({ focus: state.focus.map((v) => +v.toFixed(3)) }, true); };
      target.addEventListener('pointermove', move);
      target.addEventListener('pointerup', up, { once: true });
      void r;
    });
  }

  function dragCrop(target) {
    target.addEventListener('pointerdown', (e) => {
      e.preventDefault(); target.setPointerCapture(e.pointerId);
      const k = e.target.dataset.k || 'move';
      const r = rect();
      const c0 = [...(state.crop || [0, 0, 1, 1])];
      const x0 = e.clientX, y0 = e.clientY;
      const min = 0.05;
      const move = (ev) => {
        const dx = (ev.clientX - x0) / r.w, dy = (ev.clientY - y0) / r.h;
        let [x, y, w, hh] = c0;
        if (k === 'move') { x = clamp(x + dx, 0, 1 - w); y = clamp(y + dy, 0, 1 - hh); }
        else {
          let x1 = x + w, y1 = y + hh;
          if (k.includes('w')) x = clamp(x + dx, 0, x1 - min);
          if (k.includes('e')) x1 = clamp(x1 + dx, x + min, 1);
          if (k.includes('n')) y = clamp(y + dy, 0, y1 - min);
          if (k.includes('s')) y1 = clamp(y1 + dy, y + min, 1);
          w = x1 - x; hh = y1 - y;
        }
        state.crop = [x, y, w, hh];
        render(); onChange({ crop: state.crop.map((v) => +v.toFixed(4)) }, false);
      };
      const up = () => {
        target.removeEventListener('pointermove', move);
        const c = state.crop;
        const full = c && c[0] < 0.002 && c[1] < 0.002 && c[2] > 0.996 && c[3] > 0.996;
        if (full) state.crop = null;
        onChange({ crop: state.crop ? state.crop.map((v) => +v.toFixed(4)) : null }, true);
      };
      target.addEventListener('pointermove', move);
      target.addEventListener('pointerup', up, { once: true });
    });
  }

  const ro = new ResizeObserver(() => render());
  ro.observe(img);
  return {
    el,
    setMode(m) { state.mode = m; render(); },
    set(v) { if ('crop' in v) state.crop = v.crop ? [...v.crop] : null; if ('focus' in v) state.focus = v.focus ? [...v.focus] : [0.5, 0.5]; render(); },
    refresh() { load(); },
  };
}
