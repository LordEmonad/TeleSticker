/* TeleSticker v2 — Settings Panel */

const Settings = {
    init() {
        // Load saved settings
        const saved = JSON.parse(localStorage.getItem('telesticker-settings') || '{}');
        if (saved.format) AppState.set('settings.format', saved.format);
        if (saved.emojiMode) AppState.set('settings.emojiMode', saved.emojiMode);
        if (saved.autoProcess) AppState.set('settings.autoProcess', saved.autoProcess);

        // Apply to UI
        if (saved.format === 'png') {
            const radio = document.querySelector('input[name="settingsFormat"][value="png"]');
            if (radio) radio.checked = true;
        }
        const emojiEl = document.getElementById('settingsEmojiMode');
        if (emojiEl) emojiEl.checked = !!saved.emojiMode;
        const autoEl = document.getElementById('settingsAutoProcess');
        if (autoEl) autoEl.checked = !!saved.autoProcess;

        // Modal open/close
        document.getElementById('settingsBtn')?.addEventListener('click', () => {
            document.getElementById('settingsModal').classList.add('active');
        });
        document.getElementById('closeSettingsBtn')?.addEventListener('click', () => {
            this._save();
            document.getElementById('settingsModal').classList.remove('active');
        });
        document.getElementById('settingsModal')?.addEventListener('click', (e) => {
            if (e.target.id === 'settingsModal') {
                this._save();
                document.getElementById('settingsModal').classList.remove('active');
            }
        });

        // Format change
        document.querySelectorAll('input[name="settingsFormat"]').forEach(r => {
            r.addEventListener('change', () => {
                AppState.set('settings.format', r.value);
                // Sync global format radio
                const globalRadio = document.querySelector(`input[name="globalFormat"][value="${r.value}"]`);
                if (globalRadio) globalRadio.checked = true;
            });
        });

        // Emoji mode toggle
        document.getElementById('settingsEmojiMode')?.addEventListener('change', (e) => {
            AppState.set('settings.emojiMode', e.target.checked);
        });

        // Auto process toggle
        document.getElementById('settingsAutoProcess')?.addEventListener('change', (e) => {
            AppState.set('settings.autoProcess', e.target.checked);
        });
    },

    _save() {
        const settings = {
            format: AppState.get('settings.format'),
            emojiMode: AppState.get('settings.emojiMode'),
            autoProcess: AppState.get('settings.autoProcess'),
        };
        localStorage.setItem('telesticker-settings', JSON.stringify(settings));
    },
};
