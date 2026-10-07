// The emoji picker: a popover anchored to a button, with search and recents.
import { EMOJI_GROUPS } from './emoji-data.js';
import { h, closeOnOutside } from './util.js';

const RECENT_KEY = 'emosticker.recentEmoji';
export const QUICK = ['😂', '❤️', '🔥', '😭', '😎', '🥀', '💀', '👀', '🤔', '👍', '🎉', '🙏', '😡', '🥹', '💅', '🚀'];

function recents() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]'); } catch { return []; }
}
export function remember(e) {
  const r = [e, ...recents().filter((x) => x !== e)].slice(0, 24);
  try { localStorage.setItem(RECENT_KEY, JSON.stringify(r)); } catch { /* private mode */ }
}

export function openEmojiPicker(anchor, onPick) {
  document.querySelector('.epick')?.remove();
  const pop = h('div', { class: 'epick', role: 'dialog', 'aria-label': 'Pick an emoji' });
  const search = h('input', { class: 'text', placeholder: 'Search emoji', autofocus: true });
  const cats = h('div', { class: 'cats' });
  const list = h('div', { class: 'list' });
  pop.append(h('div', { class: 'search' }, search), cats, list);

  const groups = [{ name: 'Recent', icon: '🕘', items: recents().map((e) => [e, '']) }, ...EMOJI_GROUPS];
  const render = (q) => {
    list.innerHTML = '';
    const ql = (q || '').trim().toLowerCase();
    for (const g of groups) {
      const items = ql ? g.items.filter(([e, n]) => n.includes(ql) || e === ql) : g.items;
      if (!items.length) continue;
      const sec = h('div', { dataset: { g: g.name } }, h('div', { class: 'gname', text: g.name }));
      const grid = h('div', { class: 'ems' });
      for (const [e, n] of items.slice(0, ql ? 120 : 600)) {
        grid.append(h('button', { type: 'button', title: n, onClick: () => { remember(e); done(); onPick(e); } }, e));
      }
      sec.append(grid);
      list.append(sec);
    }
    if (!list.children.length) list.append(h('div', { class: 'note', style: { padding: '12px' }, text: 'No emoji by that name' }));
  };
  for (const g of groups) {
    if (!g.items.length) continue;
    cats.append(h('button', { type: 'button', title: g.name, onClick: () => { const s = list.querySelector(`[data-g="${g.name}"]`); s && list.scrollTo({ top: s.offsetTop - list.offsetTop, behavior: 'smooth' }); } }, g.icon));
  }
  search.addEventListener('input', () => render(search.value));
  search.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const first = list.querySelector('.ems button');
      if (first) first.click();
      else if (isEmoji(search.value.trim())) { remember(search.value.trim()); done(); onPick(search.value.trim()); }
    }
  });
  render('');
  document.body.append(pop);
  place(pop, anchor);
  const cleanup = closeOnOutside(pop, () => pop.remove());
  const done = () => { cleanup(); pop.remove(); };
  search.focus();
  return done;
}

function place(pop, anchor) {
  const r = anchor.getBoundingClientRect();
  const w = pop.offsetWidth, hgt = pop.offsetHeight;
  let left = Math.min(r.left, innerWidth - w - 8);
  let top = r.bottom + 6;
  if (top + hgt > innerHeight - 8) top = Math.max(8, r.top - hgt - 6);
  pop.style.left = `${Math.max(8, left)}px`;
  pop.style.top = `${top}px`;
}

export function isEmoji(s) {
  if (!s) return false;
  try {
    const segs = [...new Intl.Segmenter(undefined, { granularity: 'grapheme' }).segment(s)];
    return segs.length === 1 && /\p{Extended_Pictographic}|\p{Regional_Indicator}/u.test(s);
  } catch { return /\p{Extended_Pictographic}/u.test(s); }
}
