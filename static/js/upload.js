/* TeleSticker v2 — Upload & Processing */

const Upload = {
    init() {
        this._zone = document.getElementById('uploadZone');
        this._fileInput = document.getElementById('fileInput');
        this._stickerList = document.getElementById('stickerList');
        this._globalOptions = document.getElementById('globalOptions');
        this._processSection = document.getElementById('processSection');
        this._progressCard = document.getElementById('progressCard');
        this._downloadCard = document.getElementById('downloadCard');
        this._previewCard = document.getElementById('previewCard');
        this._progressFill = document.getElementById('progressFill');
        this._progressPercent = document.getElementById('progressPercent');
        this._statusLog = document.getElementById('statusLog');
        this._uploadCount = document.getElementById('uploadCount');

        this._setupDragDrop();
        this._setupButtons();

        AppState.subscribe('stickers', () => this._renderStickers());
    },

    _setupDragDrop() {
        const zone = this._zone;
        zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('dragover'); });
        zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            this._handleFiles(e.dataTransfer.files);
        });
        this._fileInput.addEventListener('change', (e) => {
            this._handleFiles(e.target.files);
            e.target.value = '';
        });
    },

    _setupButtons() {
        document.getElementById('processBtn').addEventListener('click', () => this._startProcessing());
        document.getElementById('clearBtn').addEventListener('click', () => this._clearAll());
    },

    async _handleFiles(fileList) {
        if (!fileList || fileList.length === 0) return;

        try {
            const data = await API.upload(fileList);
            if (data.files) {
                for (const f of data.files) {
                    // Use server thumbnail or generate client-side
                    if (!f.thumbnail_url) {
                        const matchingFile = Array.from(fileList).find(
                            file => file.name === f.original_filename
                        );
                        if (matchingFile) {
                            f._clientThumb = await Utils.generateClientThumbnail(matchingFile);
                        }
                    }
                    AppState.addSticker(f);
                }
                Utils.showToast(`${data.files.length} file(s) uploaded`, 'success');
            }
        } catch (err) {
            Utils.showToast(`Upload failed: ${err.message}`, 'error');
        }
    },

    _renderStickers() {
        const stickers = AppState.getStickers();
        const count = stickers.length;

        // Update badge
        if (count > 0) {
            this._uploadCount.style.display = '';
            this._uploadCount.textContent = count;
            this._globalOptions.style.display = '';
            this._processSection.style.display = '';
        } else {
            this._uploadCount.style.display = 'none';
            this._globalOptions.style.display = 'none';
            this._processSection.style.display = 'none';
        }

        this._stickerList.innerHTML = '';
        stickers.forEach(s => {
            const card = this._createStickerCard(s);
            this._stickerList.appendChild(card);
        });
    },

    _createStickerCard(sticker) {
        const thumbSrc = sticker.thumbnail_url || sticker._clientThumb || '';
        const card = Utils.el('div', { class: 'sticker-card' });
        card.dataset.fileId = sticker.file_id;

        card.innerHTML = `
            <div class="thumb-container">
                ${thumbSrc ? `<img src="${thumbSrc}" alt="${sticker.original_filename}">` : `<i class="${Utils.getFileIcon(sticker.file_type)}" style="font-size:2rem; color:var(--text-muted)"></i>`}
            </div>
            <div class="card-actions">
                <button class="btn-icon" data-action="edit" title="Edit"><i class="fas fa-edit"></i></button>
                <button class="btn-icon" data-action="remove-bg" title="Remove Background"><i class="fas fa-magic"></i></button>
                <button class="btn-icon" data-action="delete" title="Remove"><i class="fas fa-times"></i></button>
            </div>
            <div class="card-info">
                <div class="filename">${sticker.original_filename}</div>
                <div class="meta">
                    ${Utils.getTypeBadge(sticker.file_type)}
                    <span>${Utils.formatSize(sticker.file_size)}</span>
                </div>
            </div>
        `;

        // Action buttons
        card.querySelector('[data-action="delete"]').addEventListener('click', (e) => {
            e.stopPropagation();
            this._deleteSticker(sticker.file_id);
        });
        card.querySelector('[data-action="edit"]').addEventListener('click', (e) => {
            e.stopPropagation();
            this._editSticker(sticker.file_id);
        });
        card.querySelector('[data-action="remove-bg"]').addEventListener('click', (e) => {
            e.stopPropagation();
            this._removeBg(sticker.file_id);
        });

        return card;
    },

    async _deleteSticker(fileId) {
        try {
            await API.deleteSticker(fileId);
            AppState.removeSticker(fileId);
        } catch (err) {
            Utils.showToast('Failed to delete', 'error');
        }
    },

    _editSticker(fileId) {
        AppState.set('currentEditor', fileId);
        // Switch to editor tab
        document.querySelector('[data-tab="editor"]').click();
        if (typeof Editor !== 'undefined') Editor.loadSticker(fileId);
    },

    _removeBg(fileId) {
        const sticker = AppState.get('stickers')[fileId];
        if (!sticker || sticker.file_type !== 'image') {
            Utils.showToast('Background removal only works on images', 'warning');
            return;
        }
        BgRemoval.open(fileId);
    },

    async _startProcessing() {
        const stickers = AppState.getStickers();
        if (stickers.length === 0) return;

        const format = document.querySelector('input[name="globalFormat"]:checked')?.value || 'webp';
        const emojiMode = AppState.get('settings.emojiMode');

        const fileConfigs = stickers.map(s => ({
            file_id: s.file_id,
            output_format: s.output_format || format,
            mode: emojiMode ? 'emoji' : (s.mode || 'sticker'),
        }));

        this._progressCard.style.display = '';
        this._downloadCard.style.display = 'none';
        this._previewCard.style.display = 'none';
        this._progressFill.style.width = '0%';
        this._progressPercent.textContent = '0%';
        this._statusLog.innerHTML = '';
        document.getElementById('processBtn').disabled = true;

        try {
            const sid = AppState.get('sid');
            const result = await API.process(fileConfigs, sid);
            AppState.set('processing.jobId', result.job_id);
            AppState.set('processing.active', true);
            this._addLog(`Processing ${stickers.length} files...`);
        } catch (err) {
            Utils.showToast(`Processing failed: ${err.message}`, 'error');
            document.getElementById('processBtn').disabled = false;
            this._progressCard.style.display = 'none';
        }
    },

    _clearAll() {
        const stickers = AppState.getStickers();
        stickers.forEach(s => {
            API.deleteSticker(s.file_id).catch(() => {});
        });
        AppState.clearStickers();
        this._downloadCard.style.display = 'none';
        this._progressCard.style.display = 'none';
        this._previewCard.style.display = 'none';
    },

    _addLog(msg) {
        const line = Utils.el('div', {
            text: `${new Date().toLocaleTimeString()}: ${msg}`,
            style: { padding: '2px 0' },
        });
        this._statusLog.appendChild(line);
        this._statusLog.scrollTop = this._statusLog.scrollHeight;
    },

    // Socket callbacks
    onProcessingUpdate(data) {
        this._progressFill.style.width = data.progress + '%';
        this._progressPercent.textContent = data.progress + '%';
        if (data.message) this._addLog(data.message);
    },

    onFileProcessed(data) {
        if (data.status === 'success') {
            this._addLog(`Processed: ${data.processed_name} (${Utils.formatSize(data.size)})`);
        } else {
            this._addLog(`Error: ${data.message || 'Failed'}`);
        }
    },

    onProcessingComplete(data) {
        document.getElementById('processBtn').disabled = false;
        this._progressFill.style.width = '100%';
        this._progressPercent.textContent = '100%';
        this._progressFill.classList.add('success');

        if (data.status === 'complete' && data.download_url) {
            this._downloadCard.style.display = '';
            document.getElementById('downloadBtn').href = data.download_url;
            document.getElementById('downloadMessage').textContent =
                `${data.files?.length || 0} sticker(s) ready for download.`;
            Utils.showToast('Processing complete!', 'success');

            // Show preview
            if (data.files && data.files.length > 0) {
                Preview.showResults(data.files);
            }
        } else {
            Utils.showToast(data.message || 'Processing failed', 'error');
        }

        this._addLog(data.message || 'Done');
    },
};
