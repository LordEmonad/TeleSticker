/* TeleSticker v2 — Observable State Manager */

const AppState = {
    _state: {
        stickers: {},       // file_id -> sticker data
        currentEditor: null, // file_id being edited
        pack: {
            pack_id: null,
            name: '',
            title: '',
            sticker_ids: [],
        },
        processing: {
            jobId: null,
            active: false,
            progress: 0,
        },
        telegram: {
            token: '',
            botInfo: null,
            userId: '',
            validated: false,
        },
        settings: {
            format: 'webp',
            emojiMode: false,
            autoProcess: false,
        },
        sid: null,
    },
    _listeners: {},

    get(path) {
        return path.split('.').reduce((o, k) => o && o[k], this._state);
    },

    set(path, value) {
        const keys = path.split('.');
        const last = keys.pop();
        const target = keys.reduce((o, k) => o[k], this._state);
        target[last] = value;
        this._notify(path, value);
    },

    subscribe(path, callback) {
        if (!this._listeners[path]) this._listeners[path] = [];
        this._listeners[path].push(callback);
        return () => {
            this._listeners[path] = this._listeners[path].filter(cb => cb !== callback);
        };
    },

    _notify(path, value) {
        // Notify exact and parent paths
        for (const [p, cbs] of Object.entries(this._listeners)) {
            if (path.startsWith(p) || p.startsWith(path)) {
                cbs.forEach(cb => cb(value, path));
            }
        }
    },

    addSticker(data) {
        this._state.stickers[data.file_id] = data;
        this._notify('stickers', this._state.stickers);
    },

    removeSticker(fileId) {
        delete this._state.stickers[fileId];
        // Also remove from pack if present
        const ids = this._state.pack.sticker_ids;
        const idx = ids.indexOf(fileId);
        if (idx !== -1) ids.splice(idx, 1);
        this._notify('stickers', this._state.stickers);
    },

    getStickers() {
        return Object.values(this._state.stickers);
    },

    getStickerCount() {
        return Object.keys(this._state.stickers).length;
    },

    clearStickers() {
        this._state.stickers = {};
        this._notify('stickers', {});
    },
};
