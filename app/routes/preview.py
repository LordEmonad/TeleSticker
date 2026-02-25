"""Preview routes — serve thumbnails and processed previews."""

from flask import Blueprint, send_from_directory, abort
from werkzeug.utils import secure_filename as _secure
from app.config import UPLOAD_FOLDER, OUTPUT_FOLDER
import os

preview_bp = Blueprint('preview', __name__, url_prefix='/api')


@preview_bp.route('/preview/<filename>')
def serve_preview(filename):
    """Serve a thumbnail or preview image from uploads or output."""
    filename = _secure(filename)
    # Check uploads first (thumbnails)
    path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(path):
        return send_from_directory(UPLOAD_FOLDER, filename)

    # Check output (processed previews)
    path = os.path.join(OUTPUT_FOLDER, filename)
    if os.path.exists(path):
        return send_from_directory(OUTPUT_FOLDER, filename)

    abort(404)


@preview_bp.route('/preview/full/<file_id>')
def serve_full(file_id):
    """Serve the full-resolution uploaded image for the editor."""
    from app.routes.upload import get_sticker
    sticker = get_sticker(file_id)
    if not sticker:
        abort(404)
    # Prefer edited > bg_removed > original
    for key in ('edited_path', 'bg_removed_path', 'upload_path'):
        path = sticker.get(key)
        if key == 'bg_removed_path' and not sticker.get('use_bg_removed'):
            continue
        if path and os.path.exists(path):
            directory = os.path.dirname(path)
            fname = os.path.basename(path)
            return send_from_directory(directory, fname)
    abort(404)
