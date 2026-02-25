"""TeleSticker Flask application factory."""

from flask import Flask, request, jsonify
from app.config import SECRET_KEY, MAX_CONTENT_LENGTH, UPLOAD_FOLDER, OUTPUT_FOLDER, PACKS_FOLDER
from app.extensions import socketio
from app.routes import register_blueprints
from app.socket_handlers import register_handlers
from app.services.file_manager import ensure_dirs, start_cleanup_scheduler, init_sticker_cleanup
from app.utils import setup_logging

# Custom header for CSRF protection (double-submit pattern).
# Browsers prevent cross-origin JS from setting custom headers, so the
# mere presence of this header proves the request came from our own origin.
CSRF_HEADER = 'X-TeleSticker-CSRF'
CSRF_HEADER_VALUE = '1'


def create_app():
    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static',
    )
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

    setup_logging()
    ensure_dirs()

    # Init extensions
    socketio.init_app(app)

    # CSRF protection: require custom header on state-changing API requests
    @app.before_request
    def _csrf_check():
        if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            if request.path.startswith('/api/'):
                if request.headers.get(CSRF_HEADER) != CSRF_HEADER_VALUE:
                    return jsonify({'error': 'Missing or invalid CSRF header'}), 403

    # Register routes and socket handlers
    register_blueprints(app)
    register_handlers()

    # Register sticker store with cleanup scheduler so stale entries get evicted
    from app.routes.upload import _stickers, _lock
    init_sticker_cleanup(_stickers, _lock)

    # Start background cleanup
    start_cleanup_scheduler()

    return app
