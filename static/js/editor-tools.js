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
    rotateLeft(editor) { this._rotate(editor, -90); },
    rotateRight(editor) { this._rotate(editor, 90); },

    _rotate(editor, degrees) {
        const canvas = editor.getCanvas();
        const ctx = editor.getCtx();
        const w = canvas.width;
        const h = canvas.height;

        const imgData = ctx.getImageData(0, 0, w, h);
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = w;
        tempCanvas.height = h;
        tempCanvas.getContext('2d').putImageData(imgData, 0, 0);

        canvas.width = h;
        canvas.height = w;

        ctx.save();
        ctx.translate(canvas.width / 2, canvas.height / 2);
        ctx.rotate((degrees * Math.PI) / 180);
        ctx.drawImage(tempCanvas, -w / 2, -h / 2);
        ctx.restore();

        editor._saveHistory();
        editor._updateImageFromCanvas();
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
        editor._updateImageFromCanvas();
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
        editor._updateImageFromCanvas();
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
        const strokeOn = document.getElementById('textStroke')?.checked;
        const strokeColor = document.getElementById('textStrokeColor')?.value || '#000000';
        const bold = document.getElementById('textBold')?.classList.contains('active') ? 'bold ' : '';
        const italic = document.getElementById('textItalic')?.classList.contains('active') ? 'italic ' : '';

        ctx.font = `${italic}${bold}${size}px Inter, sans-serif`;
        ctx.textBaseline = 'top';

        // Draw text stroke if enabled
        if (strokeOn) {
            ctx.strokeStyle = strokeColor;
            ctx.lineWidth = Math.max(2, size / 8);
            ctx.lineJoin = 'round';
            ctx.strokeText(text, x, y);
        }

        ctx.fillStyle = color;
        ctx.fillText(text, x, y);
        editor._saveHistory();
    },

    // === Crop ===
    _cropStart: null,
    _cropEnd: null,

    startCrop(editor, x, y) {
        this._cropStart = { x, y };
        this._cropEnd = { x, y };
    },

    updateCrop(editor, x, y) {
        if (!this._cropStart) return;
        this._cropEnd = { x, y };
        const canvas = editor.getCanvas();
        const ctx = editor.getCtx();

        if (editor._history.length > 0) {
            ctx.putImageData(editor._history[editor._historyIndex], 0, 0);
        }

        const sx = Math.min(this._cropStart.x, this._cropEnd.x);
        const sy = Math.min(this._cropStart.y, this._cropEnd.y);
        const sw = Math.abs(this._cropEnd.x - this._cropStart.x);
        const sh = Math.abs(this._cropEnd.y - this._cropStart.y);

        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.clearRect(sx, sy, sw, sh);
        if (editor._history.length > 0) {
            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = canvas.width;
            tempCanvas.height = canvas.height;
            tempCanvas.getContext('2d').putImageData(editor._history[editor._historyIndex], 0, 0);
            ctx.drawImage(tempCanvas, sx, sy, sw, sh, sx, sy, sw, sh);
        }

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
            if (editor._history.length > 0) {
                editor.getCtx().putImageData(editor._history[editor._historyIndex], 0, 0);
            }
            this._cropStart = null;
            return;
        }

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
        editor._updateImageFromCanvas();

        this._cropStart = null;
        this._cropEnd = null;
    },

    // ============================
    // === Shape Tools ===
    // ============================
    _shapeStart: null,

    startShape(editor, x, y) {
        this._shapeStart = { x, y };
    },

    updateShape(editor, x, y) {
        if (!this._shapeStart) return;
        const canvas = editor.getCanvas();
        const ctx = editor.getCtx();

        // Restore from history to clear previous preview
        if (editor._history.length > 0) {
            ctx.putImageData(editor._history[editor._historyIndex], 0, 0);
        }

        this._drawShape(ctx, this._shapeStart.x, this._shapeStart.y, x, y);
    },

    finishShape(editor) {
        if (!this._shapeStart) return;
        editor._saveHistory();
        this._shapeStart = null;
    },

    _drawShape(ctx, x1, y1, x2, y2) {
        const shapeType = document.getElementById('shapeType')?.value || 'rect';
        const strokeColor = document.getElementById('shapeStrokeColor')?.value || '#ffffff';
        const fillColor = document.getElementById('shapeFillColor')?.value || '#7c5bf5';
        const strokeWidth = parseInt(document.getElementById('shapeStrokeWidth')?.value || 3);
        const doFill = document.getElementById('shapeFill')?.checked;

        ctx.save();
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = strokeWidth;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';

        switch (shapeType) {
            case 'rect':
                if (doFill) {
                    ctx.fillStyle = fillColor;
                    ctx.fillRect(x1, y1, x2 - x1, y2 - y1);
                }
                ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
                break;

            case 'circle': {
                const rx = Math.abs(x2 - x1) / 2;
                const ry = Math.abs(y2 - y1) / 2;
                const cx = Math.min(x1, x2) + rx;
                const cy = Math.min(y1, y2) + ry;
                ctx.beginPath();
                ctx.ellipse(cx, cy, Math.max(rx, 1), Math.max(ry, 1), 0, 0, Math.PI * 2);
                if (doFill) { ctx.fillStyle = fillColor; ctx.fill(); }
                ctx.stroke();
                break;
            }

            case 'line':
                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(x2, y2);
                ctx.stroke();
                break;

            case 'arrow': {
                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(x2, y2);
                ctx.stroke();
                const angle = Math.atan2(y2 - y1, x2 - x1);
                const headLen = Math.max(strokeWidth * 4, 12);
                ctx.beginPath();
                ctx.moveTo(x2, y2);
                ctx.lineTo(x2 - headLen * Math.cos(angle - 0.4), y2 - headLen * Math.sin(angle - 0.4));
                ctx.moveTo(x2, y2);
                ctx.lineTo(x2 - headLen * Math.cos(angle + 0.4), y2 - headLen * Math.sin(angle + 0.4));
                ctx.stroke();
                break;
            }
        }

        ctx.restore();
    },

    // ============================
    // === Sticker Outline ===
    // ============================
    applyOutline(editor) {
        const canvas = editor.getCanvas();
        const ctx = editor.getCtx();
        const w = canvas.width, h = canvas.height;

        const color = document.getElementById('outlineColor')?.value || '#ffffff';
        const thickness = parseInt(document.getElementById('outlineWidth')?.value || 4);

        // Save current content to temp canvas
        const temp = document.createElement('canvas');
        temp.width = w; temp.height = h;
        temp.getContext('2d').drawImage(canvas, 0, 0);

        ctx.clearRect(0, 0, w, h);

        // Stamp image at offsets around a circle to create expanded silhouette
        const steps = Math.max(24, thickness * 4);
        for (let i = 0; i < steps; i++) {
            const angle = (i / steps) * Math.PI * 2;
            ctx.drawImage(temp,
                Math.cos(angle) * thickness,
                Math.sin(angle) * thickness
            );
        }

        // Fill the expanded silhouette with outline color
        ctx.globalCompositeOperation = 'source-in';
        ctx.fillStyle = color;
        ctx.fillRect(0, 0, w, h);
        ctx.globalCompositeOperation = 'source-over';

        // Draw original on top
        ctx.drawImage(temp, 0, 0);

        editor._saveHistory();
        editor._updateImageFromCanvas();
    },

    // ============================
    // === Drop Shadow ===
    // ============================
    applyShadow(editor) {
        const canvas = editor.getCanvas();
        const ctx = editor.getCtx();
        const w = canvas.width, h = canvas.height;

        const color = document.getElementById('shadowColor')?.value || '#000000';
        const blur = parseInt(document.getElementById('shadowBlur')?.value || 6);
        const offsetX = parseInt(document.getElementById('shadowX')?.value || 4);
        const offsetY = parseInt(document.getElementById('shadowY')?.value || 4);

        const temp = document.createElement('canvas');
        temp.width = w; temp.height = h;
        temp.getContext('2d').drawImage(canvas, 0, 0);

        ctx.clearRect(0, 0, w, h);

        // Draw with shadow
        ctx.save();
        ctx.shadowColor = color;
        ctx.shadowBlur = blur;
        ctx.shadowOffsetX = offsetX;
        ctx.shadowOffsetY = offsetY;
        ctx.drawImage(temp, 0, 0);
        ctx.restore();

        // Re-draw original on top cleanly (without shadow)
        ctx.drawImage(temp, 0, 0);

        editor._saveHistory();
        editor._updateImageFromCanvas();
    },

    // ============================
    // === Image Overlay ===
    // ============================
    addImage(editor) {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.onchange = (e) => {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (ev) => {
                const img = new Image();
                img.onload = () => {
                    const canvas = editor.getCanvas();
                    const ctx = editor.getCtx();
                    // Scale overlay to fit within 50% of canvas
                    const maxW = canvas.width * 0.5;
                    const maxH = canvas.height * 0.5;
                    const scale = Math.min(maxW / img.width, maxH / img.height, 1);
                    const w = img.width * scale;
                    const h = img.height * scale;
                    const x = (canvas.width - w) / 2;
                    const y = (canvas.height - h) / 2;
                    ctx.drawImage(img, x, y, w, h);
                    editor._saveHistory();
                    editor._updateImageFromCanvas();
                    Utils.showToast('Image added to canvas', 'success');
                };
                img.src = ev.target.result;
            };
            reader.readAsDataURL(file);
        };
        input.click();
    },

    // ============================
    // === Filters ===
    // ============================
    applyFilter(editor, filterName) {
        const canvas = editor.getCanvas();
        const ctx = editor.getCtx();
        const w = canvas.width, h = canvas.height;

        const temp = document.createElement('canvas');
        temp.width = w; temp.height = h;
        temp.getContext('2d').drawImage(canvas, 0, 0);

        ctx.clearRect(0, 0, w, h);

        switch (filterName) {
            case 'blur':
                ctx.filter = 'blur(2px)';
                ctx.drawImage(temp, 0, 0);
                ctx.filter = 'none';
                break;

            case 'sharpen':
                this._applySharpen(ctx, w, h, temp);
                break;

            case 'glow':
                // Blurred bright copy underneath, then original on top
                ctx.filter = 'blur(6px) brightness(150%)';
                ctx.globalCompositeOperation = 'lighter';
                ctx.globalAlpha = 0.5;
                ctx.drawImage(temp, 0, 0);
                ctx.globalAlpha = 1;
                ctx.globalCompositeOperation = 'source-over';
                ctx.filter = 'none';
                ctx.drawImage(temp, 0, 0);
                break;

            case 'pixelate':
                this._applyPixelate(ctx, w, h, temp);
                break;

            case 'invert':
                ctx.filter = 'invert(1)';
                ctx.drawImage(temp, 0, 0);
                ctx.filter = 'none';
                break;

            case 'sepia':
                ctx.filter = 'sepia(1)';
                ctx.drawImage(temp, 0, 0);
                ctx.filter = 'none';
                break;
        }

        editor._saveHistory();
        editor._updateImageFromCanvas();
    },

    _applySharpen(ctx, w, h, src) {
        const srcCtx = src.getContext('2d');
        const imageData = srcCtx.getImageData(0, 0, w, h);
        const data = imageData.data;
        const output = ctx.createImageData(w, h);
        const out = output.data;
        // Sharpen kernel
        const kernel = [0, -1, 0, -1, 5, -1, 0, -1, 0];

        for (let y = 1; y < h - 1; y++) {
            for (let x = 1; x < w - 1; x++) {
                for (let c = 0; c < 3; c++) {
                    let val = 0;
                    for (let ky = -1; ky <= 1; ky++) {
                        for (let kx = -1; kx <= 1; kx++) {
                            const idx = ((y + ky) * w + (x + kx)) * 4 + c;
                            val += data[idx] * kernel[(ky + 1) * 3 + (kx + 1)];
                        }
                    }
                    out[(y * w + x) * 4 + c] = Math.max(0, Math.min(255, val));
                }
                out[(y * w + x) * 4 + 3] = data[(y * w + x) * 4 + 3];
            }
        }
        // Copy edge pixels unchanged
        for (let x = 0; x < w; x++) {
            for (let c = 0; c < 4; c++) {
                out[x * 4 + c] = data[x * 4 + c];
                out[((h - 1) * w + x) * 4 + c] = data[((h - 1) * w + x) * 4 + c];
            }
        }
        for (let y = 0; y < h; y++) {
            for (let c = 0; c < 4; c++) {
                out[(y * w) * 4 + c] = data[(y * w) * 4 + c];
                out[(y * w + w - 1) * 4 + c] = data[(y * w + w - 1) * 4 + c];
            }
        }

        ctx.putImageData(output, 0, 0);
    },

    _applyPixelate(ctx, w, h, src) {
        const size = 8;
        const smallW = Math.ceil(w / size);
        const smallH = Math.ceil(h / size);

        const small = document.createElement('canvas');
        small.width = smallW;
        small.height = smallH;
        const smallCtx = small.getContext('2d');
        smallCtx.imageSmoothingEnabled = false;
        smallCtx.drawImage(src, 0, 0, smallW, smallH);

        ctx.imageSmoothingEnabled = false;
        ctx.drawImage(small, 0, 0, w, h);
        ctx.imageSmoothingEnabled = true;
    },
};

// Bold/Italic toggle
document.getElementById('textBold')?.addEventListener('click', function () { this.classList.toggle('active'); });
document.getElementById('textItalic')?.addEventListener('click', function () { this.classList.toggle('active'); });
