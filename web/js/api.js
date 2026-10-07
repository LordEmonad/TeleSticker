// The server, as functions. Every call returns parsed JSON or throws an Error with the server's message.

async function call(method, url, body, isForm = false) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    if (isForm) opts.body = body;
    else { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  }
  let res;
  try { res = await fetch(url, opts); } catch (e) { throw new Error('EmoSticker is not running (the terminal window may have closed)'); }
  let data = null;
  const text = await res.text();
  try { data = text ? JSON.parse(text) : {}; } catch { data = { error: text.slice(0, 200) }; }
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

export const api = {
  state: () => call('GET', '/api/state'),
  upload(files, onProgress) {
    // XHR for the progress bar
    return new Promise((resolve, reject) => {
      const fd = new FormData();
      for (const f of files) fd.append('files', f, f.name);
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/upload');
      xhr.upload.onprogress = (e) => onProgress && e.lengthComputable && onProgress(e.loaded / e.total);
      xhr.onload = () => {
        try { const d = JSON.parse(xhr.responseText); xhr.status < 300 ? resolve(d) : reject(new Error(d.error || `HTTP ${xhr.status}`)); }
        catch { reject(new Error('Upload failed')); }
      };
      xhr.onerror = () => reject(new Error('Upload failed'));
      xhr.send(fd);
    });
  },
  fetchUrl: (url) => call('POST', '/api/fetch', { url }),
  sticker: (id) => call('GET', `/api/sticker/${id}`),
  patch: (id, body) => call('PATCH', `/api/sticker/${id}`, body),
  render: (id) => call('POST', `/api/sticker/${id}/render`),
  remove: (id) => call('DELETE', `/api/sticker/${id}`),
  duplicate: (id) => call('POST', `/api/sticker/${id}/duplicate`),
  pick: (id, x, y) => call('POST', `/api/sticker/${id}/pick`, { x, y }),
  findLoop: (id) => call('POST', `/api/sticker/${id}/find-loop`),
  newPack: (title) => call('POST', '/api/pack', { title }),
  patchPack: (id, body) => call('PATCH', `/api/pack/${id}`, body),
  switchPack: (id) => call('POST', `/api/pack/${id}/switch`),
  deletePack: (id, withStickers) => call('DELETE', `/api/pack/${id}?stickers=${withStickers ? 1 : 0}`),
  move: (pid, ids, to, remove) => call('POST', `/api/pack/${pid}/move`, { ids, to, remove }),
  tgToken: (token) => call('POST', '/api/tg/token', { token }),
  tgFindUser: () => call('POST', '/api/tg/find-user'),
  tgUser: (user_id) => call('POST', '/api/tg/user', { user_id }),
  tgCheckName: (slug) => call('POST', '/api/tg/check-name', { slug }),
  tgPublish: (body) => call('POST', '/api/tg/publish', body),
  tgRemote: (name) => call('POST', '/api/tg/remote', { name }),
  tgRemoteDelete: (file_id, pack) => call('POST', '/api/tg/remote/delete', { file_id, pack }),
  tgDeleteSet: (name, pack) => call('POST', '/api/tg/remote/delete-set', { name, pack }),
  tgThumbnail: (pack, sticker) => call('POST', '/api/tg/thumbnail', { pack, sticker }),
  installAi: () => call('POST', '/api/tools/install-ai'),
  openFolder: () => call('POST', '/api/tools/open-folder'),
};

export const media = (id, file, gen) => `/api/media/${id}/${file}${gen ? `?g=${gen}` : ''}`;
