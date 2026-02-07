/* TeleSticker v2 — API Client */

const API = {
    async _fetch(url, options = {}) {
        try {
            const res = await fetch(url, options);
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
            return data;
        } catch (err) {
            throw err;
        }
    },

    async upload(files) {
        const formData = new FormData();
        for (const file of files) {
            formData.append('files', file);
        }
        return this._fetch('/api/upload', { method: 'POST', body: formData });
    },

    async process(fileConfigs, sid) {
        return this._fetch('/api/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: fileConfigs, sid }),
        });
    },

    async deleteSticker(fileId) {
        return this._fetch(`/api/sticker/${fileId}`, { method: 'DELETE' });
    },

    async removeBg(fileId, settings = {}) {
        return this._fetch('/api/editor/remove-bg', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_id: fileId, ...settings }),
        });
    },

    async removeBgPreview(fileId, settings = {}) {
        return this._fetch('/api/editor/remove-bg/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_id: fileId, ...settings }),
        });
    },

    async bgStatus() {
        return this._fetch('/api/editor/bg-status');
    },

    // Pack API
    async listPacks() {
        return this._fetch('/api/pack');
    },

    async createPack(name, title) {
        return this._fetch('/api/pack', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, title }),
        });
    },

    async updatePack(packId, data) {
        return this._fetch(`/api/pack/${packId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
    },

    async deletePack(packId) {
        return this._fetch(`/api/pack/${packId}`, { method: 'DELETE' });
    },

    // Telegram API
    async validateToken(token) {
        return this._fetch('/api/telegram/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token }),
        });
    },

    async createStickerSet(token, userId, name, title, stickers) {
        return this._fetch('/api/telegram/create-set', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token, user_id: userId, name, title, stickers }),
        });
    },

    async addStickerToSet(token, userId, name, fileId, emoji) {
        return this._fetch('/api/telegram/add-sticker', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token, user_id: userId, name, file_id: fileId, emoji }),
        });
    },
};
