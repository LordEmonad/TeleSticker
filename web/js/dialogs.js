// Dialogs: the bot and account, publishing, packs, export, installing AI.
import { api, media } from './api.js';
import { state, load, pack, stickersInOrder, onEvent, notify, select } from './store.js';
import { h, icon, toast, closeOnOutside, plural, copyText, fmtBytes } from './util.js';
import { openEmojiPicker } from './emoji.js';

const host = () => document.getElementById('dialogs');

export function dialog({ title, body, foot, wide, onClose }) {
  const box = h('div', { class: `dialog${wide ? ' wide' : ''}`, role: 'dialog', 'aria-modal': 'true' });
  const scrim = h('div', { class: 'scrim' }, box);
  const close = () => { scrim.remove(); onClose && onClose(); };
  box.append(h('div', { class: 'dlg-head' }, h('h2', { text: title }), h('button', { class: 'btn icon ghost small', title: 'Close', onClick: close }, icon('x'))));
  const b = h('div', { class: 'dlg-body' }); box.append(b);
  if (typeof body === 'function') body(b, close); else b.append(...[].concat(body));
  if (foot) { const f = h('div', { class: 'dlg-foot' }); box.append(f); if (typeof foot === 'function') foot(f, close); else f.append(...[].concat(foot)); }
  scrim.addEventListener('pointerdown', (e) => { if (e.target === scrim) close(); });
  const key = (e) => { if (e.key === 'Escape') { close(); document.removeEventListener('keydown', key); } };
  document.addEventListener('keydown', key);
  host().append(scrim);
  return { close, box, body: b };
}

// ---- Telegram setup ----
export function openSettings(step) {
  const d = dialog({ title: 'Telegram and settings', wide: false, body: (b) => renderSettings(b, step) });
  return d;
}

function renderSettings(b, focusStep) {
  b.innerHTML = '';
  const bot = state.bot;
  // step 1: bot
  const tokenInput = h('input', { class: 'text', type: 'password', placeholder: '123456789:ABCdef…', autocomplete: 'off', spellcheck: 'false' });
  const connect = h('button', { class: 'btn primary small', text: bot.has_token ? 'Change bot' : 'Connect' });
  const s1 = h('div', { class: `step ${bot.has_token ? 'done' : ''}` }, h('div', { class: 'n' }, bot.has_token ? icon('check') : '1'),
    h('div', {}, h('h3', { text: bot.has_token ? `Bot: @${bot.username}` : 'Your bot' }),
      h('p', { html: 'Telegram publishes sticker sets through a bot you own. Make one in a minute: open <a href="https://t.me/BotFather" target="_blank" rel="noopener">@BotFather</a>, send <code>/newbot</code>, and paste the token it gives you here. The token stays on this computer.' }),
      h('div', { class: 'row' }, tokenInput, connect),
      bot.has_token ? h('div', { class: 'row', style: { marginTop: '6px' } }, h('button', { class: 'btn small ghost', text: 'Forget this bot', onClick: async () => { await api.tgToken(''); await load(); renderSettings(b); } })) : null));
  connect.addEventListener('click', async () => {
    const t = tokenInput.value.trim();
    if (!t) { tokenInput.focus(); return; }
    connect.disabled = true;
    try { const r = await api.tgToken(t); toast(`Connected @${r.bot.username}`, 'ok'); await load(); renderSettings(b, 2); }
    catch (e) { toast(e.message, 'bad', 6000); } finally { connect.disabled = false; }
  });
  tokenInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') connect.click(); });
  b.append(s1);
  // step 2: who you are
  const uidInput = h('input', { class: 'text', inputmode: 'numeric', placeholder: 'or type your user id', value: bot.user_id || '' });
  const startLink = bot.username ? `https://t.me/${bot.username}?start=emosticker` : '#';
  const detect = h('button', { class: 'btn primary small', text: 'I pressed Start' });
  const s2 = h('div', { class: `step ${bot.user_id ? 'done' : ''}` }, h('div', { class: 'n' }, bot.user_id ? icon('check') : '2'),
    h('div', {}, h('h3', { text: bot.user_id ? `Owner: ${bot.user_name || bot.user_id}` : 'Who owns the sets' }),
      h('p', { html: bot.has_token
        ? `Sets belong to a Telegram account, not to the bot. <a href="${startLink}" target="_blank" rel="noopener">Open @${bot.username}</a> in Telegram, press <b>Start</b>, then come back and press the button: your account is picked up from that message.`
        : 'Connect a bot first.' }),
      h('div', { class: 'row' }, detect, uidInput, h('button', { class: 'btn small ghost', text: 'Save', onClick: async () => { try { await api.tgUser(uidInput.value.trim()); await load(); renderSettings(b); } catch (e) { toast(e.message, 'bad'); } } }))));
  detect.disabled = !bot.has_token;
  detect.addEventListener('click', async () => {
    detect.disabled = true;
    try {
      const r = await api.tgFindUser();
      if (r.found) { toast(`Hello, ${r.user_name}`, 'ok'); await load(); renderSettings(b); }
      else toast('No Start message yet. Open the bot in Telegram and press Start, then try again.', 'warn', 6000);
    } catch (e) { toast(e.message, 'bad', 7000); } finally { detect.disabled = false; }
  });
  b.append(s2);
  // tools
  const t = state.tools;
  const tools = h('div', { class: 'step' }, h('div', { class: 'n' }, icon('gear')), h('div', {},
    h('h3', { text: 'Tools' }),
    h('div', { class: 'kv' },
      h('dt', { text: 'ffmpeg' }), h('dd', {}, t.ffmpeg ? h('span', { class: 'pill ok', text: 'found' }) : h('span', { class: 'pill bad', text: 'missing: videos and GIFs need it (brew install ffmpeg)' })),
      h('dt', { text: 'AI cut-out' }), h('dd', {}, t.rembg ? h('span', { class: 'pill ok', text: 'rembg installed' }) : h('span', {}, h('span', { class: 'pill', text: 'not installed' }), ' ', h('button', { class: 'btn small ghost', text: 'Install (~300 MB)', onClick: () => openInstallAi() }))),
      h('dt', { text: 'Version' }), h('dd', { text: `EmoSticker ${state.version}` }),
    ),
    h('div', { class: 'row', style: { marginTop: '10px' } }, h('button', { class: 'btn small ghost', onClick: () => api.openFolder().catch((e) => toast(e.message, 'bad')) }, icon('folder'), 'Open the data folder'),
      h('span', { class: 'note', text: 'Your stickers, packs and settings live there.' })),
  ));
  b.append(tools);
  if (focusStep === 2) uidInput.scrollIntoView({ block: 'center' });
  if (!bot.has_token) setTimeout(() => tokenInput.focus(), 50);
}

export function openInstallAi() {
  const log = h('div', { class: 'log' });
  const d = dialog({ title: 'Install AI background removal', body: [
    h('p', { class: 'note', text: 'Installs rembg and onnxruntime into EmoSticker\'s own Python environment. The first cut-out then downloads a model (~170 MB). Everything runs on this computer.' }), log],
    foot: (f, close) => {
      const go = h('button', { class: 'btn primary', text: 'Install', onClick: async () => { go.disabled = true; try { await api.installAi(); } catch (e) { toast(e.message, 'bad'); go.disabled = false; } } });
      f.append(h('button', { class: 'btn ghost', text: 'Close', onClick: close }), go);
    } });
  const off = onEvent((ev, data) => {
    if (ev !== 'install') return;
    if (data.line) { log.append(h('div', { text: data.line })); log.scrollTop = log.scrollHeight; }
    if (data.done) { log.append(h('div', { class: data.ok ? 'done' : 'error', text: data.ok ? 'Installed. AI cut-out is ready.' : 'The install did not finish; see the lines above.' })); load(); if (data.ok) toast('AI cut-out installed', 'ok'); off(); }
  });
  return d;
}

// ---- publish ----
export function openPublish() {
  const p = pack();
  const bot = state.bot;
  if (!bot.has_token || !bot.user_id) { openSettings(bot.has_token ? 2 : 1); return; }
  const list = stickersInOrder();
  const ready = list.filter((s) => s.out?.ready);
  const notReady = list.length - ready.length;
  const pub = p.published;
  const slugInput = h('input', { class: 'text', placeholder: 'short name, e.g. emonad_pack', value: pub?.name ? pub.name.replace(new RegExp(`_by_${bot.username}$`, 'i'), '') : slugify(p.title), spellcheck: 'false' });
  const titleInput = h('input', { class: 'text', maxlength: 64, value: p.title });
  const nameLine = h('div', { class: 'note' });
  const typeSeg = h('div', { class: 'seg grow' });
  for (const [v, label] of [['regular', 'Stickers'], ['custom_emoji', 'Custom emoji (100×100)']]) {
    const btn = h('button', { type: 'button', class: (p.type || 'regular') === v ? 'on' : '', text: label });
    btn.addEventListener('click', async () => {
      if (pub) { toast('A published set keeps its type. Make a new pack for the other kind.', 'warn'); return; }
      typeSeg.querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === btn));
      await api.patchPack(p.id, { type: v }); await load(); toast(v === 'custom_emoji' ? 'Rendering everything at 100×100' : 'Rendering everything at 512', 'info');
    });
    typeSeg.append(btn);
  }
  const check = async () => {
    try {
      const r = await api.tgCheckName(slugInput.value);
      nameLine.innerHTML = '';
      nameLine.append(h('span', { text: `t.me/addstickers/${r.name}` }));
      if (r.taken) nameLine.append(' · ', h('span', { class: pub?.name === r.name ? 'pill ok' : 'pill warn', text: pub?.name === r.name ? `your set (${r.taken.count} up)` : `exists: "${r.taken.title}" (${r.taken.count}); publishing adds to it` }));
      else nameLine.append(' · ', h('span', { class: 'pill ok', text: 'free' }));
    } catch (e) { nameLine.textContent = e.message; }
  };
  let t;
  slugInput.addEventListener('input', () => { clearTimeout(t); t = setTimeout(check, 400); });
  check();
  const log = h('div', { class: 'log', hidden: true });
  const d = dialog({ title: pub ? 'Update the Telegram set' : 'Publish to Telegram', body: [
    h('div', { class: 'kv' }, h('dt', { text: 'Bot' }), h('dd', { text: `@${bot.username}` }), h('dt', { text: 'Owner' }), h('dd', { text: bot.user_name || bot.user_id })),
    h('div', { class: 'field' }, h('div', { class: 'lbl', text: 'Title (what people see)' }), titleInput),
    h('div', { class: 'field' }, h('div', { class: 'lbl', text: 'Short name (the link)' }), slugInput, nameLine, h('div', { class: 'note', text: `Letters, digits and underscores. Telegram adds _by_${bot.username} to every set a bot makes.` })),
    h('div', { class: 'field' }, h('div', { class: 'lbl', text: 'Kind' }), typeSeg),
    h('div', { class: 'note', html: `<b>${ready.length}</b> ready${notReady ? `, <span style="color:var(--warn)">${notReady} not ready and will be left out</span>` : ''}. ${pub ? 'New stickers are added, re-edited ones replaced, the order synced, and anything you removed here stays in Telegram unless you remove it in Manage set.' : `Telegram takes up to ${p.type === 'custom_emoji' ? 200 : 120} per set.`}` }),
    log,
  ], foot: (f, close) => {
    const go = h('button', { class: 'btn primary' }, icon('send'), pub ? 'Update set' : 'Publish');
    go.disabled = !ready.length;
    go.addEventListener('click', async () => {
      go.disabled = true; log.hidden = false; log.innerHTML = '';
      try {
        await api.patchPack(p.id, { title: titleInput.value.trim() || p.title });
        await api.tgPublish({ pack: p.id, slug: slugInput.value, title: titleInput.value.trim() || p.title });
      } catch (e) { log.append(h('div', { class: 'error', text: e.message })); go.disabled = false; }
    });
    const manage = pub ? h('button', { class: 'btn ghost left', text: 'Manage set', onClick: () => { close(); openRemote(); } }) : null;
    f.append(manage, h('button', { class: 'btn ghost', text: 'Close', onClick: close }), go);
    const off = onEvent((ev, data) => {
      if (ev !== 'publish') return;
      if (data.kind === 'end') { go.disabled = false; load(); off(); return; }
      const line = h('div', { class: data.kind, text: data.text });
      if (data.link) line.append(' ', h('a', { href: data.link, target: '_blank', rel: 'noopener', text: data.link }), ' ', h('button', { class: 'btn small ghost', text: 'Copy link', onClick: () => copyText(data.link).then(() => toast('Link copied', 'ok', 1500)) }));
      log.append(line); log.scrollTop = log.scrollHeight;
      if (data.kind === 'done') toast(data.text, 'ok', 6000);
      if (data.kind === 'error') toast(data.text, 'bad', 8000);
    });
  } });
  return d;
}

function slugify(t) { return (t || 'pack').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').replace(/^[^a-z]/, 'p$&').slice(0, 40) || 'pack'; }

// ---- remote set management ----
export async function openRemote() {
  const p = pack();
  const pub = p.published;
  if (!pub) { toast('This pack is not published yet', 'warn'); return; }
  const grid = h('div', { class: 'remote-grid' }, h('div', { class: 'note', text: 'Loading from Telegram…' }));
  const head = h('div', { class: 'kv' });
  const d = dialog({ title: `Manage ${pub.title || pub.name}`, wide: true, body: [head, grid,
    h('div', { class: 'note', text: 'This is the set as Telegram has it now. Removing here removes it from the set for everyone who added it; it stays in EmoSticker.' })],
    foot: (f, close) => {
      f.append(
        h('button', { class: 'btn ghost left danger', text: 'Delete the whole set', onClick: async () => { if (!confirm(`Delete ${pub.name} from Telegram for everyone? This cannot be undone.`)) return; try { await api.tgDeleteSet(pub.name, p.id); toast('Set deleted', 'ok'); await load(); close(); } catch (e) { toast(e.message, 'bad'); } } }),
        h('button', { class: 'btn ghost', text: 'Set icon…', onClick: () => pickIcon(p) }),
        h('a', { class: 'btn ghost', href: pub.link, target: '_blank', rel: 'noopener' }, icon('ext'), 'Open in Telegram'),
        h('button', { class: 'btn primary', text: 'Done', onClick: close }));
    } });
  try {
    const r = await api.tgRemote(pub.name);
    const set = r.set;
    head.append(h('dt', { text: 'Link' }), h('dd', {}, h('a', { href: pub.link, target: '_blank', rel: 'noopener', text: pub.link })), h('dt', { text: 'Stickers' }), h('dd', { text: `${set.stickers.length} on Telegram · kind ${set.type}` }));
    grid.innerHTML = '';
    const byFile = Object.fromEntries(Object.entries(pub.stickers || {}).map(([sid, fid]) => [fid, sid]));
    for (const tg of set.stickers) {
      const sid = byFile[tg.file_id];
      const local = sid && state.stickers[sid];
      const cell = h('div', { class: 'r', title: local ? local.name : 'not in this pack any more' });
      if (local) cell.append(h('img', { src: media(sid, local.out?.kind === 'video' ? 'poster.png' : local.out?.file, local.out?.gen), alt: '', style: { maxWidth: '80%', maxHeight: '80%' } }));
      else cell.append(h('span', { text: tg.emoji || '🩶' }));
      cell.append(h('small', { text: tg.video ? 'video' : 'still' }));
      cell.append(h('button', { title: 'Remove from the Telegram set', onClick: async () => { if (!confirm('Remove this sticker from the set on Telegram?')) return; try { await api.tgRemoteDelete(tg.file_id, p.id); cell.remove(); await load(); } catch (e) { toast(e.message, 'bad'); } } }, icon('x')));
      grid.append(cell);
    }
    if (!set.stickers.length) grid.append(h('div', { class: 'note', text: 'The set is empty.' }));
  } catch (e) { grid.innerHTML = ''; grid.append(h('div', { class: 'note warn', text: e.message })); }
  return d;
}

function pickIcon(p) {
  const list = stickersInOrder().filter((s) => s.out?.ready);
  const grid = h('div', { class: 'remote-grid' });
  const d = dialog({ title: 'Set icon', body: [h('p', { class: 'note', text: 'The small picture Telegram shows for the set (100×100, made from the sticker you pick). Without one, the first sticker is used.' }), grid] });
  for (const s of list) {
    const cell = h('div', { class: 'r', style: { cursor: 'pointer' }, title: s.name, onClick: async () => { cell.style.opacity = .5; try { await api.tgThumbnail(p.id, s.id); toast('Set icon updated', 'ok'); d.close(); } catch (e) { toast(e.message, 'bad', 7000); cell.style.opacity = 1; } } },
      h('img', { src: media(s.id, s.out.kind === 'video' ? 'poster.png' : s.out.file, s.out.gen), alt: '', style: { maxWidth: '80%', maxHeight: '80%' } }));
    grid.append(cell);
  }
}

// ---- packs ----
export function openPackMenu(anchor) {
  document.querySelector('.menu.floating')?.remove();
  const m = h('div', { class: 'menu floating left', style: { position: 'fixed', zIndex: 80, minWidth: '300px' } });
  m.append(h('div', { class: 'menu-title', text: 'Packs' }));
  const packs = Object.values(state.packs).sort((a, b) => (b.updated || b.created || 0) - (a.updated || a.created || 0));
  for (const p of packs) {
    const faces = h('span', { class: 'faces' }, p.stickers.slice(0, 3).map((id) => state.stickers[id]).filter(Boolean).map((s) => h('img', { src: media(s.id, 'thumb.png'), alt: '' })));
    m.append(h('button', { class: p.id === state.currentPack ? 'on' : '', onClick: async () => { m.remove(); await api.switchPack(p.id); state.active = null; select([], 'clear'); await load(); } },
      faces, h('span', { text: p.title, style: { flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' } }), h('small', { text: `${p.stickers.length}${p.published ? ' · live' : ''}` })));
  }
  m.append(h('hr'),
    h('button', { onClick: async () => { m.remove(); const t = prompt('Name the new pack', 'New pack'); if (t == null) return; await api.newPack(t.trim() || 'New pack'); state.active = null; select([], 'clear'); await load(); } }, icon('plus'), 'New pack'),
    h('button', { onClick: () => { m.remove(); renamePack(); } }, icon('copy'), 'Rename this pack'),
    pack()?.published ? h('button', { onClick: () => { m.remove(); openRemote(); } }, icon('telegram'), 'Manage the Telegram set') : null,
    packs.length > 1 ? h('button', { class: 'on', onClick: async () => { m.remove(); const p = pack(); const go = confirm(`Delete the pack "${p.title}" and its ${plural(p.stickers.length, 'sticker')}?\n\nThe sticker files are deleted from this computer. A set already published to Telegram stays there.`); if (!go) return; await api.deletePack(p.id, true); state.active = null; select([], 'clear'); await load(); } }, icon('trash'), 'Delete this pack') : null,
  );
  document.body.append(m);
  const r = anchor.getBoundingClientRect();
  m.style.top = `${r.bottom + 6}px`; m.style.left = `${r.left}px`;
  closeOnOutside(m, () => m.remove());
}

export async function renamePack() {
  const p = pack();
  const t = prompt('Pack title (what people see in Telegram)', p.title);
  if (t == null || !t.trim()) return;
  await api.patchPack(p.id, { title: t.trim().slice(0, 64) });
  await load();
}

export function openMoveMenu(ids) {
  const others = Object.values(state.packs).filter((p) => p.id !== state.currentPack);
  const d = dialog({ title: `Move ${plural(ids.length, 'sticker')} to…`, body: (b, close) => {
    const list = h('div', { class: 'pack-list' });
    for (const p of others) list.append(h('div', { class: 'pack-item', onClick: async () => { await api.move(state.currentPack, ids, p.id, true); select([], 'clear'); await load(); close(); toast(`Moved to ${p.title}`, 'ok'); } }, h('div', { class: 't' }, h('b', { text: p.title }), h('small', { text: plural(p.stickers.length, 'sticker') }))));
    list.append(h('div', { class: 'pack-item', onClick: async () => { const t = prompt('Name the new pack', 'New pack'); if (t == null) return; const np = await api.newPack(t.trim() || 'New pack'); await api.switchPack(state.currentPack); await api.move(state.currentPack, ids, np.id, true); select([], 'clear'); await load(); close(); toast(`Moved to ${np.title}`, 'ok'); } }, icon('plus'), h('div', { class: 't' }, h('b', { text: 'New pack' }))));
    b.append(list);
  } });
  return d;
}

export function bulkEmoji(anchor, ids) {
  openEmojiPicker(anchor, async (em) => {
    for (const id of ids) { const s = state.stickers[id]; if (!s) continue; s.emoji = [em, ...(s.emoji || []).filter((x) => x !== em)].slice(0, 20); try { await api.patch(id, { emoji: s.emoji }); } catch (e) { toast(e.message, 'bad'); } }
    notify('all');
    toast(`${em} set on ${plural(ids.length, 'sticker')}`, 'ok', 1500);
  });
}

export async function pasteLook(ids) {
  const look = state.lookClipboard;
  if (!look) return;
  for (const id of ids) {
    const s = state.stickers[id];
    if (!s) continue;
    const e = { ...look };
    if (s.source.kind !== 'video') for (const k of ['fit_time', 'boomerang', 'blend', 'fps', 'reverse']) delete e[k];
    // the look replaces the target's whole look, except its own crop and trim, which belong to its picture
    for (const k of ['crop', 'start', 'end', 'focus']) if (s.edit?.[k] != null) e[k] = s.edit[k];
    try { await api.patch(id, { edit: e, replace_edit: true }); } catch (err) { toast(err.message, 'bad'); }
  }
  toast(`Look applied to ${plural(ids.length, 'sticker')}`, 'ok', 1500);
}

// ---- export menu ----
export function openExportMenu(btn, menu) {
  menu.innerHTML = '';
  const p = pack();
  const n = p.stickers.length;
  menu.append(h('div', { class: 'menu-title', text: 'Download as a ZIP' }));
  const items = [['telegram', 'Telegram', 'the files as rendered'], ['whatsapp', 'WhatsApp', '512×512 WebP, 100 KB / 500 KB'], ['discord', 'Discord', '320×320 PNG / APNG'], ['signal', 'Signal', '512×512 WebP / APNG']];
  for (const [k, label, note] of items) {
    menu.append(h('a', { href: `/api/pack/${p.id}/export?target=${k}`, download: '', onClick: () => { menu.hidden = true; if (k !== 'telegram') toast(`Re-encoding ${plural(n, 'sticker')} for ${label}: the download starts when it is done`, 'info', 5000); } }, icon('download'), label, h('small', { text: note })));
  }
  menu.append(h('div', { class: 'sub-note', text: 'Other platforms are re-encoded to their own limits.' }));
  menu.hidden = false;
  closeOnOutside(menu, () => { menu.hidden = true; });
}
