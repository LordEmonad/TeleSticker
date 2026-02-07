/* TeleSticker v2 — Pack Management */

const Pack = {
    _grid: null,
    _empty: null,
    _currentPackId: null,

    init() {
        this._grid = document.getElementById('packGrid');
        this._empty = document.getElementById('packEmpty');

        document.getElementById('savePackBtn')?.addEventListener('click', () => this.savePack());
        document.getElementById('loadPackBtn')?.addEventListener('click', () => this.openLoadModal());
        document.getElementById('closePackLoadBtn')?.addEventListener('click', () => {
            document.getElementById('packLoadModal').classList.remove('active');
        });

        AppState.subscribe('pack', () => this.render());
    },

    render() {
        const stickerIds = AppState.get('pack.sticker_ids') || [];
        const allStickers = AppState.get('stickers') || {};

        if (stickerIds.length === 0) {
            this._empty.style.display = '';
            this._grid.style.display = 'none';
            return;
        }

        this._empty.style.display = 'none';
        this._grid.style.display = '';
        this._grid.innerHTML = '';

        stickerIds.forEach((fileId, index) => {
            const sticker = allStickers[fileId];
            if (!sticker) return;

            const card = Utils.el('div', { class: 'sticker-card', draggable: 'true' });
            card.dataset.fileId = fileId;
            card.dataset.index = index;

            const thumbSrc = sticker.thumbnail_url || sticker._clientThumb || '';
            const emoji = sticker.emoji || '🎨';

            card.innerHTML = `
                <div class="thumb-container">
                    ${thumbSrc ? `<img src="${thumbSrc}" alt="">` : `<i class="fas fa-image" style="font-size:2rem; color:var(--text-muted)"></i>`}
                </div>
                <div class="card-actions">
                    <button class="btn-icon" data-action="remove" title="Remove from pack"><i class="fas fa-times"></i></button>
                </div>
                <div class="card-info">
                    <div class="filename">${sticker.original_filename}</div>
                    <div class="meta">
                        <span class="emoji-tag" data-action="emoji" title="Change emoji">${emoji}</span>
                        <span>#${index + 1}</span>
                    </div>
                </div>
            `;

            // Remove from pack
            card.querySelector('[data-action="remove"]').addEventListener('click', () => {
                const ids = AppState.get('pack.sticker_ids');
                const i = ids.indexOf(fileId);
                if (i !== -1) ids.splice(i, 1);
                AppState.set('pack.sticker_ids', [...ids]);
            });

            // Emoji picker
            card.querySelector('[data-action="emoji"]').addEventListener('click', () => {
                EmojiPicker.open((selectedEmoji) => {
                    sticker.emoji = selectedEmoji;
                    AppState.addSticker(sticker);
                    this.render();
                });
            });

            // Drag and drop reorder
            card.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('text/plain', index);
                card.classList.add('dragging');
            });
            card.addEventListener('dragend', () => card.classList.remove('dragging'));
            card.addEventListener('dragover', (e) => {
                e.preventDefault();
                card.classList.add('drag-over');
            });
            card.addEventListener('dragleave', () => card.classList.remove('drag-over'));
            card.addEventListener('drop', (e) => {
                e.preventDefault();
                card.classList.remove('drag-over');
                const fromIndex = parseInt(e.dataTransfer.getData('text/plain'));
                const toIndex = index;
                if (fromIndex !== toIndex) {
                    const ids = AppState.get('pack.sticker_ids');
                    const [removed] = ids.splice(fromIndex, 1);
                    ids.splice(toIndex, 0, removed);
                    AppState.set('pack.sticker_ids', [...ids]);
                }
            });

            this._grid.appendChild(card);
        });
    },

    async savePack() {
        const name = document.getElementById('packName')?.value.trim();
        const title = document.getElementById('packTitle')?.value.trim();

        if (!name || !title) {
            Utils.showToast('Pack name and title are required', 'warning');
            return;
        }

        try {
            const stickerIds = AppState.get('pack.sticker_ids') || [];

            if (this._currentPackId) {
                await API.updatePack(this._currentPackId, { name, title, sticker_ids: stickerIds });
                Utils.showToast('Pack updated', 'success');
            } else {
                const pack = await API.createPack(name, title);
                this._currentPackId = pack.pack_id;
                AppState.set('pack.pack_id', pack.pack_id);
                await API.updatePack(pack.pack_id, { sticker_ids: stickerIds });
                Utils.showToast('Pack saved', 'success');
            }
        } catch (err) {
            Utils.showToast(`Save failed: ${err.message}`, 'error');
        }
    },

    async openLoadModal() {
        try {
            const data = await API.listPacks();
            const list = document.getElementById('packList');
            list.innerHTML = '';

            if (!data.packs || data.packs.length === 0) {
                list.innerHTML = '<p style="color:var(--text-muted); text-align:center; padding:20px">No saved packs</p>';
            } else {
                data.packs.forEach(pack => {
                    const item = Utils.el('div', {
                        class: 'card',
                        style: { padding: '12px', marginBottom: '8px', cursor: 'pointer' },
                        onClick: () => this.loadPack(pack),
                    });
                    item.innerHTML = `
                        <div style="display:flex; justify-content:space-between; align-items:center">
                            <div>
                                <div style="font-weight:600">${pack.title}</div>
                                <div style="font-size:0.8rem; color:var(--text-muted)">${pack.name} &middot; ${pack.sticker_ids?.length || 0} stickers</div>
                            </div>
                            <button class="btn btn-ghost btn-sm" data-delete title="Delete"><i class="fas fa-trash"></i></button>
                        </div>
                    `;
                    item.querySelector('[data-delete]').addEventListener('click', async (e) => {
                        e.stopPropagation();
                        await API.deletePack(pack.pack_id);
                        item.remove();
                        Utils.showToast('Pack deleted', 'info');
                    });
                    list.appendChild(item);
                });
            }

            document.getElementById('packLoadModal').classList.add('active');
        } catch (err) {
            Utils.showToast(`Failed to load packs: ${err.message}`, 'error');
        }
    },

    loadPack(pack) {
        this._currentPackId = pack.pack_id;
        AppState.set('pack.pack_id', pack.pack_id);
        AppState.set('pack.name', pack.name);
        AppState.set('pack.title', pack.title);
        AppState.set('pack.sticker_ids', pack.sticker_ids || []);

        document.getElementById('packName').value = pack.name;
        document.getElementById('packTitle').value = pack.title;

        document.getElementById('packLoadModal').classList.remove('active');
        Utils.showToast(`Loaded: ${pack.title}`, 'success');
    },
};
