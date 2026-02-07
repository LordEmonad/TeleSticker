/* TeleSticker v2 — Theme toggle */

const Theme = {
    init() {
        const saved = localStorage.getItem('telesticker-theme') || 'dark';
        this.apply(saved);

        const btn = document.getElementById('themeToggle');
        if (btn) {
            btn.addEventListener('click', () => {
                const current = document.documentElement.getAttribute('data-theme');
                const next = current === 'dark' ? 'light' : 'dark';
                this.apply(next);
                localStorage.setItem('telesticker-theme', next);
            });
        }
    },

    apply(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        const icon = document.querySelector('#themeToggle i');
        if (icon) {
            icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
    },
};
