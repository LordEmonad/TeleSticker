// A trim range over a filmstrip: two handles, a draggable window, keyboard nudges.
import { h, clamp } from './util.js';

export function mountTrim(parent, { strip, duration, start, end, onChange }) {
  const el = h('div', { class: 'trim', tabindex: 0, role: 'group', 'aria-label': 'Trim' });
  const img = h('img', { src: strip, alt: '', draggable: 'false' });
  const shadeL = h('div', { class: 'shade l' }), shadeR = h('div', { class: 'shade r' });
  const win = h('div', { class: 'win' });
  const hl = h('div', { class: 'handle l' }), hr = h('div', { class: 'handle r' });
  el.append(img, shadeL, shadeR, win, hl, hr);
  parent.append(el);
  let a = start, b = end;
  const dur = Math.max(0.01, duration);
  const minLen = Math.min(0.2, dur);

  function draw() {
    const pa = (a / dur) * 100, pb = (b / dur) * 100;
    shadeL.style.width = `${pa}%`;
    shadeR.style.width = `${100 - pb}%`;
    win.style.left = `${pa}%`; win.style.width = `${pb - pa}%`;
    hl.style.left = `${pa}%`; hr.style.left = `${pb}%`;
  }
  draw();

  function drag(target, mode) {
    target.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      target.setPointerCapture(e.pointerId);
      const rect = el.getBoundingClientRect();
      const x0 = e.clientX, a0 = a, b0 = b;
      const move = (ev) => {
        const dt = ((ev.clientX - x0) / rect.width) * dur;
        if (mode === 'l') a = clamp(a0 + dt, 0, b - minLen);
        else if (mode === 'r') b = clamp(b0 + dt, a + minLen, dur);
        else { const len = b0 - a0; a = clamp(a0 + dt, 0, dur - len); b = a + len; }
        draw(); onChange(a, b, false);
      };
      const up = () => { target.removeEventListener('pointermove', move); target.removeEventListener('pointerup', up); onChange(a, b, true); };
      target.addEventListener('pointermove', move);
      target.addEventListener('pointerup', up);
    });
  }
  drag(hl, 'l'); drag(hr, 'r'); drag(win, 'm');
  el.addEventListener('keydown', (e) => {
    const step = e.shiftKey ? 0.5 : 1 / 24;
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      const d = e.key === 'ArrowLeft' ? -step : step;
      if (e.altKey) b = clamp(b + d, a + minLen, dur); else a = clamp(a + d, 0, b - minLen);
      draw(); onChange(a, b, true); e.preventDefault();
    }
  });
  return {
    el,
    set(na, nb) { a = clamp(na, 0, dur); b = clamp(nb, a + minLen, dur); draw(); },
  };
}
