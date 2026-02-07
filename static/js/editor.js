/* TeleSticker v2 — Canvas-based Image Editor */

const Editor = {
    _canvas: null,
    _ctx: null,
    _image: null,
    _fileId: null,
    _history: [],
    _historyIndex: -1,
    _maxHistory: 30,
    _tool: 'select',
    _drawing: false,
    _lastX: 0,
    _lastY: 0,

    // Adjustments
    _brightness: 100,
    _contrast: 100,
    _saturation: 100,

    init() {
        this._canvas = document.getElementById('editorCanvas');
        this._ctx = this._canvas.getContext('2d');

        this._setupToolbar();
        this._setupSliders();
        this._setupCanvasEvents();
        this._setupActions();
    },

    _setupToolbar() {
        document.querySelectorAll('#editorToolbar .tool-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const tool = btn.dataset.tool;
                if (!tool) return;

                // Instant actions
                if (tool === 'rotate-left') { EditorTools.rotateLeft(this); return; }
                if (tool === 'rotate-right') { EditorTools.rotateRight(this); return; }
                if (tool === 'flip-h') { EditorTools.flipH(this); return; }
                if (tool === 'flip-v') { EditorTools.flipV(this); return; }

                this._setTool(tool, btn);
            });
        });
    },

    _setTool(tool, btn) {
        this._tool = tool;
        document.querySelectorAll('#editorToolbar .tool-btn').forEach(b => b.classList.remove('active'));
        if (btn) btn.classList.add('active');

        // Show/hide panel sections
        document.getElementById('adjustSection').style.display = (tool === 'select' || tool === 'crop') ? '' : 'none';
        document.getElementById('drawSection').style.display = (tool === 'draw' || tool === 'eraser') ? '' : 'none';
        document.getElementById('textSection').style.display = tool === 'text' ? '' : 'none';

        // Cursor
        if (tool === 'draw' || tool === 'eraser') this._canvas.style.cursor = 'crosshair';
        else if (tool === 'text') this._canvas.style.cursor = 'text';
        else if (tool === 'crop') this._canvas.style.cursor = 'crosshair';
        else this._canvas.style.cursor = 'default';
    },

    _setupSliders() {
        const sliders = [
            { id: 'brightness', prop: '_brightness', label: 'brightnessVal' },
            { id: 'contrast', prop: '_contrast', label: 'contrastVal' },
            { id: 'saturation', prop: '_saturation', label: 'saturationVal' },
        ];
        sliders.forEach(({ id, prop, label }) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('input', Utils.debounce(() => {
                this[prop] = parseInt(el.value);
                document.getElementById(label).textContent = el.value + '%';
                this._applyFiltersAndRedraw();
            }, 50));
        });

        // Brush size
        const brushSize = document.getElementById('brushSize');
        if (brushSize) {
            brushSize.addEventListener('input', () => {
                document.getElementById('brushSizeVal').textContent = brushSize.value;
            });
        }

        // Text size
        const textSize = document.getElementById('textSize');
        if (textSize) {
            textSize.addEventListener('input', () => {
                document.getElementById('textSizeVal').textContent = textSize.value;
            });
        }
    },

    _setupCanvasEvents() {
        const canvas = this._canvas;
        canvas.addEventListener('mousedown', (e) => this._onPointerDown(e));
        canvas.addEventListener('mousemove', (e) => this._onPointerMove(e));
        canvas.addEventListener('mouseup', (e) => this._onPointerUp(e));
        canvas.addEventListener('mouseleave', () => { this._drawing = false; });

        // Touch support
        canvas.addEventListener('touchstart', (e) => { e.preventDefault(); this._onPointerDown(this._touchToMouse(e)); });
        canvas.addEventListener('touchmove', (e) => { e.preventDefault(); this._onPointerMove(this._touchToMouse(e)); });
        canvas.addEventListener('touchend', (e) => { e.preventDefault(); this._onPointerUp(this._touchToMouse(e)); });
    },

    _touchToMouse(e) {
        const touch = e.touches[0] || e.changedTouches[0];
        const rect = this._canvas.getBoundingClientRect();
        return { offsetX: touch.clientX - rect.left, offsetY: touch.clientY - rect.top };
    },

    _onPointerDown(e) {
        if (!this._image) return;
        const { offsetX, offsetY } = e;
        const scaleX = this._canvas.width / this._canvas.offsetWidth;
        const scaleY = this._canvas.height / this._canvas.offsetHeight;
        const x = offsetX * scaleX;
        const y = offsetY * scaleY;

        if (this._tool === 'draw' || this._tool === 'eraser') {
            this._drawing = true;
            this._lastX = x;
            this._lastY = y;
            this._ctx.beginPath();
            this._ctx.moveTo(x, y);
        } else if (this._tool === 'text') {
            EditorTools.placeText(this, x, y);
        } else if (this._tool === 'crop') {
            EditorTools.startCrop(this, x, y);
        }
    },

    _onPointerMove(e) {
        if (!this._drawing) return;
        const { offsetX, offsetY } = e;
        const scaleX = this._canvas.width / this._canvas.offsetWidth;
        const scaleY = this._canvas.height / this._canvas.offsetHeight;
        const x = offsetX * scaleX;
        const y = offsetY * scaleY;

        if (this._tool === 'draw') {
            EditorTools.draw(this, x, y);
        } else if (this._tool === 'eraser') {
            EditorTools.erase(this, x, y);
        } else if (this._tool === 'crop') {
            EditorTools.updateCrop(this, x, y);
        }

        this._lastX = x;
        this._lastY = y;
    },

    _onPointerUp() {
        if (this._drawing) {
            this._drawing = false;
            if (this._tool === 'crop') {
                EditorTools.finishCrop(this);
            } else {
                this._saveHistory();
            }
        }
    },

    _setupActions() {
        document.getElementById('editorUndo')?.addEventListener('click', () => this.undo());
        document.getElementById('editorRedo')?.addEventListener('click', () => this.redo());
        document.getElementById('editorSave')?.addEventListener('click', () => this.save());
    },

    loadSticker(fileId) {
        const sticker = AppState.get('stickers')[fileId];
        if (!sticker) return;

        this._fileId = fileId;
        document.getElementById('editorEmpty').style.display = 'none';
        document.getElementById('editorWrapper').style.display = '';

        // Reset adjustments
        this._brightness = this._contrast = this._saturation = 100;
        ['brightness', 'contrast', 'saturation'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = 100;
            const label = document.getElementById(id + 'Val');
            if (label) label.textContent = '100%';
        });
        this._history = [];
        this._historyIndex = -1;

        // Load image
        const src = sticker.thumbnail_url || sticker._clientThumb;
        if (src && sticker.file_type === 'image') {
            const img = new Image();
            img.crossOrigin = 'anonymous';
            img.onload = () => {
                this._image = img;
                this._canvas.width = Math.min(img.width, 512);
                this._canvas.height = Math.min(img.height, 512);
                // Fit image
                const scale = Math.min(512 / img.width, 512 / img.height, 1);
                this._canvas.width = Math.round(img.width * scale);
                this._canvas.height = Math.round(img.height * scale);
                this._redraw();
                this._saveHistory();
            };
            img.src = src;
        } else {
            this._image = null;
            this._ctx.clearRect(0, 0, this._canvas.width, this._canvas.height);
            this._ctx.fillStyle = 'var(--text-muted)';
            this._ctx.font = '16px Inter, sans-serif';
            this._ctx.textAlign = 'center';
            this._ctx.fillText('Video editing not supported', this._canvas.width / 2, this._canvas.height / 2);
        }
    },

    _redraw() {
        if (!this._image) return;
        this._ctx.clearRect(0, 0, this._canvas.width, this._canvas.height);
        this._ctx.drawImage(this._image, 0, 0, this._canvas.width, this._canvas.height);
    },

    _applyFiltersAndRedraw() {
        if (!this._image) return;
        this._ctx.filter = `brightness(${this._brightness}%) contrast(${this._contrast}%) saturate(${this._saturation}%)`;
        this._ctx.clearRect(0, 0, this._canvas.width, this._canvas.height);
        this._ctx.drawImage(this._image, 0, 0, this._canvas.width, this._canvas.height);
        this._ctx.filter = 'none';
    },

    _saveHistory() {
        const data = this._ctx.getImageData(0, 0, this._canvas.width, this._canvas.height);
        // Remove future states if we're in the middle of history
        this._history = this._history.slice(0, this._historyIndex + 1);
        this._history.push(data);
        if (this._history.length > this._maxHistory) this._history.shift();
        this._historyIndex = this._history.length - 1;
    },

    undo() {
        if (this._historyIndex > 0) {
            this._historyIndex--;
            this._ctx.putImageData(this._history[this._historyIndex], 0, 0);
        }
    },

    redo() {
        if (this._historyIndex < this._history.length - 1) {
            this._historyIndex++;
            this._ctx.putImageData(this._history[this._historyIndex], 0, 0);
        }
    },

    save() {
        if (!this._fileId) return;
        // Export canvas as blob and update the sticker's thumbnail
        this._canvas.toBlob((blob) => {
            if (!blob) return;
            const url = URL.createObjectURL(blob);
            const sticker = AppState.get('stickers')[this._fileId];
            if (sticker) {
                sticker._clientThumb = url;
                sticker.thumbnail_url = null; // prefer client thumb
                sticker._editedBlob = blob;
                AppState.addSticker(sticker);
                Utils.showToast('Saved to sticker', 'success');
            }
        }, 'image/png');
    },

    getCanvas() { return this._canvas; },
    getCtx() { return this._ctx; },
};
