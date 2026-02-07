/* TeleSticker v2 — Background Removal UI */

const BgRemoval = {
    _fileId: null,
    _modal: null,

    init() {
        this._modal = document.getElementById('bgRemoveModal');

        // Slider value labels
        document.getElementById('bgFgThreshold')?.addEventListener('input', (e) => {
            document.getElementById('bgFgVal').textContent = e.target.value;
        });
        document.getElementById('bgBgThreshold')?.addEventListener('input', (e) => {
            document.getElementById('bgBgVal').textContent = e.target.value;
        });
        document.getElementById('bgErodeSize')?.addEventListener('input', (e) => {
            document.getElementById('bgErodeVal').textContent = e.target.value;
        });

        // Buttons
        document.getElementById('bgPreviewBtn')?.addEventListener('click', () => this._preview());
        document.getElementById('bgApplyBtn')?.addEventListener('click', () => this._apply());
        document.getElementById('closeBgModal')?.addEventListener('click', () => this.close());
        this._modal?.addEventListener('click', (e) => {
            if (e.target === this._modal) this.close();
        });
    },

    _getSettings() {
        return {
            model: document.getElementById('bgModel')?.value || 'isnet-general-use',
            alpha_matting: document.getElementById('bgAlphaMatting')?.checked ?? true,
            fg_threshold: parseInt(document.getElementById('bgFgThreshold')?.value || 270),
            bg_threshold: parseInt(document.getElementById('bgBgThreshold')?.value || 20),
            erode_size: parseInt(document.getElementById('bgErodeSize')?.value || 15),
        };
    },

    open(fileId) {
        this._fileId = fileId;

        // Reset preview
        document.getElementById('bgPreviewImg').style.display = 'none';
        document.getElementById('bgPreviewPlaceholder').style.display = '';
        document.getElementById('bgPreviewSpinner').style.display = 'none';

        this._modal.classList.add('active');
    },

    close() {
        this._modal.classList.remove('active');
        this._fileId = null;
    },

    async _preview() {
        if (!this._fileId) return;

        const previewImg = document.getElementById('bgPreviewImg');
        const spinner = document.getElementById('bgPreviewSpinner');
        const placeholder = document.getElementById('bgPreviewPlaceholder');

        placeholder.style.display = 'none';
        previewImg.style.display = 'none';
        spinner.style.display = '';

        try {
            const settings = this._getSettings();
            const result = await API.removeBgPreview(this._fileId, settings);
            if (result.ok && result.data_url) {
                previewImg.src = result.data_url;
                previewImg.style.display = '';
            } else {
                placeholder.textContent = 'Preview failed';
                placeholder.style.display = '';
            }
        } catch (err) {
            placeholder.textContent = `Error: ${err.message}`;
            placeholder.style.display = '';
            Utils.showToast(`Preview failed: ${err.message}`, 'error');
        } finally {
            spinner.style.display = 'none';
        }
    },

    async _apply() {
        if (!this._fileId) return;

        const btn = document.getElementById('bgApplyBtn');
        btn.disabled = true;
        btn.innerHTML = '<div class="spinner"></div> Applying...';

        try {
            const settings = this._getSettings();
            const result = await API.removeBg(this._fileId, settings);
            if (result.ok) {
                const sticker = AppState.get('stickers')[this._fileId];
                if (sticker) {
                    sticker.bg_removed_path = true;
                    sticker.use_bg_removed = true;
                    sticker.thumbnail_url = result.preview_url;
                    sticker.has_transparency = true;
                    AppState.addSticker(sticker);
                }
                Utils.showToast('Background removed!', 'success');
                this.close();
            }
        } catch (err) {
            Utils.showToast(`Background removal failed: ${err.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-check"></i> Apply';
        }
    },
};
