/* TeleSticker v2 — Application Entry Point */

document.addEventListener('DOMContentLoaded', () => {
    // Initialize all modules
    Theme.init();
    Socket.init();
    BgRemoval.init();
    Upload.init();
    Preview.init();
    Editor.init();
    EmojiPicker.init();
    Pack.init();
    Telegram.init();
    Settings.init();
    Shortcuts.init();

    // Tab navigation
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            if (!tab) return;

            // Update buttons
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Update content
            document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
            const content = document.getElementById(`tab-${tab}`);
            if (content) content.classList.add('active');
        });
    });

    // Check bg removal availability
    API.bgStatus().then(data => {
        if (!data.available) {
            // Hide remove-bg buttons or mark them disabled
            document.querySelectorAll('[data-action="remove-bg"]').forEach(btn => {
                btn.title = 'Install rembg to enable background removal';
                btn.style.opacity = '0.3';
            });
        }
    }).catch(() => {});

    console.log('TeleSticker v2 initialized');
});
