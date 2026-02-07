/* TeleSticker v2 — Editor Tool Implementations */

const EditorTools = {
    // === Drawing ===
    draw(editor, x, y) {
        const ctx = editor.getCtx();
        const size = parseInt(document.getElementById('brushSize')?.value || 4);
        const color = document.getElementById('brushColor')?.value || '#ffffff';
        ctx.strokeStyle = color;
        ctx.lineWidth = size;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.globalCompositeOperation = 'source-over';
        ctx.lineTo(x, y);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(x, y);
    },

    erase(editor, x, y) {
        const ctx = editor.getCtx();
        const size = parseInt(document.getElementById('brushSize')?.value || 10);
        ctx.globalCompositeOperation = 'destination-out';
        ctx.lineWidth = size;
        ctx.lineCap = 'round';
        ctx.lineTo(x, y);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.globalCompositeOperation = 'source-over';
    },

    // === Rotate ===
    rotateLeft(editor) {
        this._rotate(editor, -90);
    },

    rotateRight(editor) {
        this._rotate(editor, 90);
    },

    _rotate(editor, degrees) {
        const canvas = editor.getCanvas();
        const ctx = editor.getCtx();
        const w = canvas.width;
        const h = canvas.height;

        // Save current image
        const imgData = ctx.getImageData(0, 0, w, h);
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = w;
        tempCanvas.height = h;
        tempCanvas.getContext('2d').putImageData(imgData, 0, 0);

        // Swap dimensions for 90/-90
        canvas.width = h;
        canvas.height = w;

        ctx.save();
        ctx.translate(canvas.width / 2, canvas.height / 2);
        ctx.rotate((degrees * Math.PI) / 180);
        ctx.drawImage(tempCanvas, -w / 2, -h / 2);
        ctx.restore();

        editor._saveHistory();
    },

    // === Flip ===
    flipH(editor) {
        const canvas = editor.getCanvas();
        const ctx = editor.getCtx();
        const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = canvas.width;
        tempCanvas.height = canvas.height;
        tempCanvas.getContext('2d').putImageData(imgData, 0, 0);

        ctx.save();
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.scale(-1, 1);
        ctx.drawImage(tempCanvas, -canvas.width, 0);
        ctx.restore();
        editor._saveHistory();
    },

    flipV(editor) {
        const canvas = editor.getCanvas();
        const ctx = editor.getCtx();
        const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = canvas.width;
        tempCanvas.height = canvas.height;
        tempCanvas.getContext('2d').putImageData(imgData, 0, 0);

        ctx.save();
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.scale(1, -1);
        ctx.drawImage(tempCanvas, 0, -canvas.height);
        ctx.restore();
        editor._saveHistory();
    },

    // === Text ===
    placeText(editor, x, y) {
        const text = document.getElementById('textInput')?.value;
        if (!text) {
            Utils.showToast('Enter text first', 'warning');
            return;
        }

        const ctx = editor.getCtx();
        const size = parseInt(document.getElementById('textSize')?.value || 32);
        const color = document.getElementById('textColor')?.value || '#ffffff';
        const bold = document.getElementById('textBold')?.classList.contains('active') ? 'bold ' : '';
        const italic = document.getElementById('textItalic')?.classList.contains('active') ? 'italic ' : '';

        ctx.font = `${italic}${bold}${size}px Inter, sans-serif`;
        ctx.fillStyle = color;
        ctx.textBaseline = 'top';
        ctx.fillText(text, x, y);
        editor._saveHistory();
    },

    // === Crop ===
    _cropStart: null,
    _cropEnd: null,
    _cropOverlay: null,

    startCrop(editor, x, y) {
        this._cropStart = { x, y };
        this._cropEnd = { x, y };
    },

    updateCrop(editor, x, y) {
        if (!this._cropStart) return;
        this._cropEnd = { x, y };
        // Draw crop preview
        const canvas = editor.getCanvas();
        const ctx = editor.getCtx();

        // Redraw from last history state
        if (editor._history.length > 0) {
            ctx.putImageData(editor._history[editor._historyIndex], 0, 0);
        }

        // Draw overlay
        const sx = Math.min(this._cropStart.x, this._cropEnd.x);
        const sy = Math.min(this._cropStart.y, this._cropEnd.y);
        const sw = Math.abs(this._cropEnd.x - this._cropStart.x);
        const sh = Math.abs(this._cropEnd.y - this._cropStart.y);

        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        // Clear the crop area to show the image
        ctx.clearRect(sx, sy, sw, sh);
        if (editor._history.length > 0) {
            // Redraw only the crop area
            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = canvas.width;
            tempCanvas.height = canvas.height;
            const tempCtx = tempCanvas.getContext('2d');
            tempCtx.putImageData(editor._history[editor._historyIndex], 0, 0);
            ctx.drawImage(tempCanvas, sx, sy, sw, sh, sx, sy, sw, sh);
        }

        // Crop border
        ctx.strokeStyle = '#7c5bf5';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        ctx.strokeRect(sx, sy, sw, sh);
        ctx.setLineDash([]);
    },

    finishCrop(editor) {
        if (!this._cropStart || !this._cropEnd) return;

        const sx = Math.min(this._cropStart.x, this._cropEnd.x);
        const sy = Math.min(this._cropStart.y, this._cropEnd.y);
        const sw = Math.abs(this._cropEnd.x - this._cropStart.x);
        const sh = Math.abs(this._cropEnd.y - this._cropStart.y);

        if (sw < 5 || sh < 5) {
            // Too small, just redraw
            if (editor._history.length > 0) {
                editor.getCtx().putImageData(editor._history[editor._historyIndex], 0, 0);
            }
            this._cropStart = null;
            return;
        }

        // Get the cropped region from the pre-crop state
        const ctx = editor.getCtx();
        const canvas = editor.getCanvas();
        if (editor._history.length > 0) {
            ctx.putImageData(editor._history[editor._historyIndex], 0, 0);
        }
        const cropped = ctx.getImageData(sx, sy, sw, sh);

        canvas.width = sw;
        canvas.height = sh;
        ctx.putImageData(cropped, 0, 0);
        editor._saveHistory();

        this._cropStart = null;
        this._cropEnd = null;
    },
};

// Bold/Italic toggle
document.getElementById('textBold')?.addEventListener('click', function () { this.classList.toggle('active'); });
document.getElementById('textItalic')?.addEventListener('click', function () { this.classList.toggle('active'); });
