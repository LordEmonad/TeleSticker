/* TeleSticker v2 — Sticker Preview Grid */

const Preview = {
    init() {
        this._card = document.getElementById('previewCard');
        this._grid = document.getElementById('previewGrid');
    },

    showResults(files) {
        this._card.style.display = '';
        this._grid.innerHTML = '';

        files.forEach(f => {
            const card = Utils.el('div', { class: 'sticker-card' });
            const ext = f.processed.split('.').pop().toLowerCase();
            const isVideo = ext === 'webm';

            card.innerHTML = `
                <div class="thumb-container checkerboard">
                    ${isVideo
                        ? `<video src="/api/preview/${f.processed}" autoplay loop muted playsinline style="max-width:100%;max-height:100%"></video>`
                        : `<img src="/api/preview/${f.processed}" alt="${f.processed}">`}
                </div>
                <div class="card-info">
                    <div class="filename">${f.processed}</div>
                    <div class="meta">
                        <span>${isVideo ? 'VIDEO' : 'IMAGE'}</span>
                        <span>${Utils.formatSize(f.size)}</span>
                    </div>
                </div>
                <div class="card-actions">
                    <button class="btn-icon" data-action="add-to-pack" title="Add to Pack"><i class="fas fa-plus"></i></button>
                </div>
            `;

            const addBtn = card.querySelector('[data-action="add-to-pack"]');
            addBtn.addEventListener('click', () => {
                const packIds = AppState.get('pack.sticker_ids');
                if (!packIds.includes(f.file_id)) {
                    packIds.push(f.file_id);
                    AppState.set('pack.sticker_ids', [...packIds]);
                    Utils.showToast('Added to pack', 'success');
                    if (typeof Pack !== 'undefined') Pack.render();
                }
            });

            this._grid.appendChild(card);
        });
    },
};
