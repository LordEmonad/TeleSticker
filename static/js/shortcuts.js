/* TeleSticker v2 — Keyboard Shortcuts */

const Shortcuts = {
    init() {
        document.addEventListener('keydown', (e) => {
            // Don't intercept when typing in inputs
            const tag = e.target.tagName.toLowerCase();
            if (tag === 'input' || tag === 'textarea') return;

            const ctrl = e.ctrlKey || e.metaKey;

            // Ctrl+Z — undo
            if (ctrl && e.key === 'z' && !e.shiftKey) {
                e.preventDefault();
                if (typeof Editor !== 'undefined') Editor.undo();
            }

            // Ctrl+Y or Ctrl+Shift+Z — redo
            if ((ctrl && e.key === 'y') || (ctrl && e.shiftKey && e.key === 'z') || (ctrl && e.shiftKey && e.key === 'Z')) {
                e.preventDefault();
                if (typeof Editor !== 'undefined') Editor.redo();
            }

            // Ctrl+S — save pack
            if (ctrl && e.key === 's') {
                e.preventDefault();
                if (typeof Pack !== 'undefined') Pack.savePack();
            }

            // Ctrl+Enter — process
            if (ctrl && e.key === 'Enter') {
                e.preventDefault();
                document.getElementById('processBtn')?.click();
            }

            // Escape — close modals
            if (e.key === 'Escape') {
                document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
            }

            // Delete — remove selected sticker
            if (e.key === 'Delete') {
                const currentEdit = AppState.get('currentEditor');
                if (currentEdit) {
                    AppState.removeSticker(currentEdit);
                    AppState.set('currentEditor', null);
                    document.getElementById('editorEmpty').style.display = '';
                    document.getElementById('editorWrapper').style.display = 'none';
                }
            }

            // Editor tool shortcuts
            if (e.key === 'v' || e.key === 'V') {
                document.querySelector('[data-tool="select"]')?.click();
            }
            if (e.key === 'c' && !ctrl) {
                document.querySelector('[data-tool="crop"]')?.click();
            }
            if (e.key === 't' || e.key === 'T') {
                document.querySelector('[data-tool="text"]')?.click();
            }
            if (e.key === 'd' && !ctrl) {
                document.querySelector('[data-tool="draw"]')?.click();
            }
            if (e.key === 'e' || e.key === 'E') {
                document.querySelector('[data-tool="eraser"]')?.click();
            }
        });
    },
};
