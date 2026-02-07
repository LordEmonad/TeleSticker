"""Register all blueprints."""

from app.routes.main import main_bp
from app.routes.upload import upload_bp
from app.routes.download import download_bp
from app.routes.preview import preview_bp
from app.routes.editor import editor_bp
from app.routes.telegram import telegram_bp
from app.routes.pack import pack_bp


def register_blueprints(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(download_bp)
    app.register_blueprint(preview_bp)
    app.register_blueprint(editor_bp)
    app.register_blueprint(telegram_bp)
    app.register_blueprint(pack_bp)
