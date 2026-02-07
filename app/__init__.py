"""TeleSticker Flask application factory."""

from flask import Flask
from app.config import SECRET_KEY, MAX_CONTENT_LENGTH, UPLOAD_FOLDER, OUTPUT_FOLDER, PACKS_FOLDER
from app.extensions import socketio
from app.routes import register_blueprints
from app.socket_handlers import register_handlers
from app.services.file_manager import ensure_dirs, start_cleanup_scheduler
from app.utils import setup_logging


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

    # Register routes and socket handlers
    register_blueprints(app)
    register_handlers()

    # Start background cleanup
    start_cleanup_scheduler()

    return app
