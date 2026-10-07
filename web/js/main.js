// Boot: load the state, connect the event stream, wire the header, keyboard shortcuts.
import { api } from './api.js';
import { state, load, connect, subscribe, order, select, setActive, pack, onEvent } from './store.js';
import { initGrid, deleteIds } from './grid.js';
import { initInspector } from './inspector.js';
import { openSettings, openPublish, openPackMenu, openMoveMenu, bulkEmoji, pasteLook, openExportMenu, openInstallAi } from './dialogs.js';
import { toast, isMac } from './util.js';

async function boot() {
  initGrid();
  initInspector();
  try { await load(); } catch (e) { toast(e.message, 'bad', 0); return; }
  connect();
  subscribe((what) => { if (what === 'all' || what === 'pack') renderHeader(); });
  renderHeader();
  wireHeader();
  wireKeys();
  onEvent((ev, data) => {
    if (ev === 'error' && data.message) toast(data.message, 'bad', 6000);
    if (ev === 'export' && data.n) { /* the download link shows the browser's own progress */ }
  });
  document.addEventListener('emosticker:install-ai', () => openInstallAi());
  if (!state.tools.ffmpeg && Object.keys(state.stickers).length === 0) {
    toast('ffmpeg was not found: pictures work, videos and GIFs need it (brew install ffmpeg)', 'warn', 9000);
  }
}

function renderHeader() {
  const bot = state.bot;
  const chip = document.getElementById('botChip');
  chip.classList.toggle('on', !!(bot.has_token && bot.user_id));
  document.getElementById('botChipText').textContent = bot.has_token ? (bot.user_id ? `@${bot.username}` : `@${bot.username} · press Start`) : 'Connect a bot';
  const p = pack();
  document.getElementById('publishBtn').querySelector('span').textContent = p?.published ? 'Update set' : 'Publish';
}

function wireHeader() {
  document.getElementById('botChip').addEventListener('click', () => openSettings());
  document.getElementById('settingsBtn').addEventListener('click', () => openSettings());
  document.getElementById('publishBtn').addEventListener('click', () => {
    if (!order().length) { toast('Add some stickers first', 'warn'); return; }
    openPublish();
  });
  document.getElementById('packPick').addEventListener('click', (e) => openPackMenu(e.currentTarget));
  const exportBtn = document.getElementById('exportBtn'), exportMenu = document.getElementById('exportMenu');
  exportBtn.addEventListener('click', () => { if (!order().length) { toast('Nothing to export yet', 'warn'); return; } exportMenu.hidden ? openExportMenu(exportBtn, exportMenu) : (exportMenu.hidden = true); });
  document.getElementById('selActions').addEventListener('click', (e) => {
    const b = e.target.closest('[data-bulk]');
    if (!b) return;
    const ids = order().filter((id) => state.selected.has(id));
    if (!ids.length) return;
    const k = b.dataset.bulk;
    if (k === 'delete') deleteIds(ids);
    else if (k === 'emoji') bulkEmoji(b, ids);
    else if (k === 'move') openMoveMenu(ids);
    else if (k === 'copy-look') { const s = state.stickers[state.active || ids[0]]; state.lookClipboard = { ...(s.edit || {}) }; delete state.lookClipboard.crop; delete state.lookClipboard.start; delete state.lookClipboard.end; toast(`Look copied from ${s.name}`, 'ok'); document.getElementById('pasteLook').disabled = false; }
    else if (k === 'paste-look') pasteLook(ids);
  });
}

function wireKeys() {
  document.addEventListener('keydown', (e) => {
    const inField = e.target.closest('input, textarea, select, [contenteditable]');
    const mod = isMac ? e.metaKey : e.ctrlKey;
    if (inField) return;
    if (mod && e.key.toLowerCase() === 'a') { e.preventDefault(); select(order(), 'set'); }
    else if (e.key === 'Delete' || e.key === 'Backspace') {
      const ids = state.selected.size ? order().filter((id) => state.selected.has(id)) : (state.active ? [state.active] : []);
      if (ids.length) { e.preventDefault(); deleteIds(ids); }
    } else if (e.key === 'Escape') { select([], 'clear'); document.getElementById('inspector').classList.remove('open'); }
    else if (mod && e.key === 'Enter') { e.preventDefault(); document.getElementById('publishBtn').click(); }
    else if (mod && e.key.toLowerCase() === 'o') { e.preventDefault(); document.getElementById('fileInput').click(); }
    else if (e.key === 'Enter' && state.active) { document.getElementById('inspector').classList.add('open'); }
    else if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key) && !document.activeElement.closest('.grid')) {
      const ids = order(); if (!ids.length) return;
      const i = ids.indexOf(state.active);
      const d = e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 1;
      setActive(ids[Math.max(0, Math.min(ids.length - 1, i + d))]);
      e.preventDefault();
    }
  });
}

boot();
export { api };
