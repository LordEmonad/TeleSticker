/* TeleSticker v2 — Telegram Integration */

const Telegram = {
    init() {
        // Load saved token
        const savedToken = localStorage.getItem('telesticker-bot-token') || '';
        const savedUserId = localStorage.getItem('telesticker-user-id') || '';
        document.getElementById('botToken').value = savedToken;
        document.getElementById('userId').value = savedUserId;

        if (savedToken) AppState.set('telegram.token', savedToken);
        if (savedUserId) AppState.set('telegram.userId', savedUserId);

        document.getElementById('validateTokenBtn')?.addEventListener('click', () => this.validateToken());
        document.getElementById('createSetBtn')?.addEventListener('click', () => this.createSet());

        // Save user ID on change
        document.getElementById('userId')?.addEventListener('change', (e) => {
            const val = e.target.value.trim();
            AppState.set('telegram.userId', val);
            localStorage.setItem('telesticker-user-id', val);
            this._updateCreateBtn();
        });

        // Auto-validate if token exists
        if (savedToken) this.validateToken();
    },

    async validateToken() {
        const token = document.getElementById('botToken').value.trim();
        if (!token) {
            Utils.showToast('Enter a bot token', 'warning');
            return;
        }

        try {
            const data = await API.validateToken(token);
            if (data.ok && data.bot) {
                AppState.set('telegram.token', token);
                AppState.set('telegram.botInfo', data.bot);
                AppState.set('telegram.validated', true);
                localStorage.setItem('telesticker-bot-token', token);

                document.getElementById('botInfo').style.display = '';
                document.getElementById('botName').textContent = data.bot.first_name;
                document.getElementById('botUsername').textContent = `@${data.bot.username}`;
                Utils.showToast('Bot connected!', 'success');
                this._updateCreateBtn();
            }
        } catch (err) {
            AppState.set('telegram.validated', false);
            document.getElementById('botInfo').style.display = 'none';
            Utils.showToast(`Invalid token: ${err.message}`, 'error');
        }
    },

    _updateCreateBtn() {
        const valid = AppState.get('telegram.validated');
        const userId = AppState.get('telegram.userId');
        document.getElementById('createSetBtn').disabled = !(valid && userId);
    },

    async createSet() {
        const token = AppState.get('telegram.token');
        const userId = AppState.get('telegram.userId');
        const name = document.getElementById('tgSetName')?.value.trim();
        const title = document.getElementById('tgSetTitle')?.value.trim();

        if (!name || !title) {
            Utils.showToast('Set name and title are required', 'warning');
            return;
        }

        // Get stickers from pack
        const packIds = AppState.get('pack.sticker_ids') || [];
        const allStickers = AppState.get('stickers') || {};
        const stickerConfigs = [];

        for (const fileId of packIds) {
            const s = allStickers[fileId];
            if (!s) continue;
            stickerConfigs.push({
                file_id: fileId,
                emoji: s.emoji || '🎨',
            });
        }

        if (stickerConfigs.length === 0) {
            Utils.showToast('Add stickers to the pack first', 'warning');
            return;
        }

        const progressEl = document.getElementById('tgUploadProgress');
        const fillEl = document.getElementById('tgProgressFill');
        const logEl = document.getElementById('tgStatusLog');
        progressEl.style.display = '';
        fillEl.style.width = '0%';
        logEl.innerHTML = '';
        document.getElementById('createSetBtn').disabled = true;

        const addLog = (msg) => {
            logEl.innerHTML += `<div>${new Date().toLocaleTimeString()}: ${msg}</div>`;
            logEl.scrollTop = logEl.scrollHeight;
        };

        try {
            addLog(`Creating sticker set "${title}" with ${stickerConfigs.length} stickers...`);
            fillEl.style.width = '20%';

            const result = await API.createStickerSet(token, userId, name, title, stickerConfigs);

            if (result.ok) {
                fillEl.style.width = '100%';
                fillEl.classList.add('success');
                addLog('Sticker set created successfully!');
                if (result.errors && result.errors.length > 0) {
                    result.errors.forEach(e => addLog(`Warning: ${e}`));
                }
                Utils.showToast('Sticker set created on Telegram!', 'success');
            } else {
                addLog(`Error: ${result.error}`);
                Utils.showToast(`Failed: ${result.error}`, 'error');
            }
        } catch (err) {
            addLog(`Error: ${err.message}`);
            Utils.showToast(`Upload failed: ${err.message}`, 'error');
        } finally {
            document.getElementById('createSetBtn').disabled = false;
        }
    },
};
