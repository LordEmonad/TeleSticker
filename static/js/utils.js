/* TeleSticker v2 — Shared utility helpers */

const Utils = {
    formatSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    },

    debounce(fn, ms = 250) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), ms);
        };
    },

    $(selector) {
        return document.querySelector(selector);
    },

    $$(selector) {
        return document.querySelectorAll(selector);
    },

    el(tag, attrs = {}, children = []) {
        const elem = document.createElement(tag);
        for (const [k, v] of Object.entries(attrs)) {
            if (k === 'class') elem.className = v;
            else if (k === 'style' && typeof v === 'object') Object.assign(elem.style, v);
            else if (k.startsWith('on')) elem.addEventListener(k.slice(2).toLowerCase(), v);
            else if (k === 'html') elem.innerHTML = v;
            else if (k === 'text') elem.textContent = v;
            else elem.setAttribute(k, v);
        }
        for (const c of children) {
            if (typeof c === 'string') elem.appendChild(document.createTextNode(c));
            else if (c) elem.appendChild(c);
        }
        return elem;
    },

    getFileIcon(fileType) {
        if (fileType === 'video' || fileType === 'animated_gif') return 'fas fa-video';
        return 'fas fa-image';
    },

    getTypeBadge(fileType) {
        if (fileType === 'video') return '<span class="type-badge video">VIDEO</span>';
        if (fileType === 'animated_gif') return '<span class="type-badge gif">GIF</span>';
        return '<span class="type-badge image">IMAGE</span>';
    },

    showToast(message, type = 'info', duration = 4000) {
        const container = document.getElementById('toastContainer');
        const icons = { success: 'fa-check-circle', error: 'fa-times-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' };
        const toast = Utils.el('div', { class: `toast ${type}` }, [
            Utils.el('i', { class: `fas ${icons[type] || icons.info} toast-icon` }),
            Utils.el('span', { class: 'toast-message', text: message }),
            Utils.el('button', { class: 'toast-close', html: '&times;', onClick() { removeToast(toast); } }),
        ]);
        container.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add('show'));

        function removeToast(t) {
            t.classList.remove('show');
            setTimeout(() => t.remove(), 300);
        }
        setTimeout(() => removeToast(toast), duration);
    },

    generateClientThumbnail(file) {
        return new Promise((resolve) => {
            if (file.type.startsWith('image/')) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const img = new Image();
                    img.onload = () => {
                        const canvas = document.createElement('canvas');
                        const size = 200;
                        const scale = Math.min(size / img.width, size / img.height);
                        canvas.width = img.width * scale;
                        canvas.height = img.height * scale;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                        resolve(canvas.toDataURL('image/webp', 0.8));
                    };
                    img.onerror = () => resolve(null);
                    img.src = e.target.result;
                };
                reader.onerror = () => resolve(null);
                reader.readAsDataURL(file);
            } else {
                // Video: extract first frame
                const video = document.createElement('video');
                video.preload = 'metadata';
                video.muted = true;
                video.onloadeddata = () => {
                    video.currentTime = 0.1;
                };
                video.onseeked = () => {
                    const canvas = document.createElement('canvas');
                    const size = 200;
                    const scale = Math.min(size / video.videoWidth, size / video.videoHeight);
                    canvas.width = video.videoWidth * scale;
                    canvas.height = video.videoHeight * scale;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    resolve(canvas.toDataURL('image/webp', 0.8));
                    URL.revokeObjectURL(video.src);
                };
                video.onerror = () => resolve(null);
                video.src = URL.createObjectURL(file);
            }
        });
    }
};
