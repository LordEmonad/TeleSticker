"""Preview routes — serve thumbnails and processed previews."""

from flask import Blueprint, send_from_directory, abort
from app.config import UPLOAD_FOLDER, OUTPUT_FOLDER
import os

preview_bp = Blueprint('preview', __name__, url_prefix='/api')


@preview_bp.route('/preview/<filename>')
def serve_preview(filename):
    """Serve a thumbnail or preview image from uploads or output."""
    # Check uploads first (thumbnails)
    path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(path):
        return send_from_directory(UPLOAD_FOLDER, filename)

    # Check output (processed previews)
    path = os.path.join(OUTPUT_FOLDER, filename)
    if os.path.exists(path):
        return send_from_directory(OUTPUT_FOLDER, filename)

    abort(404)
