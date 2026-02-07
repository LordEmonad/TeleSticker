"""Download routes for processed files."""

from flask import Blueprint, send_from_directory
from app.config import OUTPUT_FOLDER

download_bp = Blueprint('download', __name__, url_prefix='/api')


@download_bp.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)
