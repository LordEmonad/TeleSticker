"""Telegram integration routes."""

from flask import Blueprint, request, jsonify
from app.services.telegram_api import validate_token, create_sticker_set, add_sticker_to_set, get_sticker_set
from app.routes.upload import get_sticker
from app.config import OUTPUT_FOLDER
import os

telegram_bp = Blueprint('telegram', __name__, url_prefix='/api/telegram')


@telegram_bp.route('/validate', methods=['POST'])
def validate():
    """Validate a bot token."""
    data = request.get_json()
    token = data.get('token', '')
    if not token:
        return jsonify({'error': 'Token required'}), 400

    info = validate_token(token)
    if info:
        return jsonify({'ok': True, 'bot': info})
    return jsonify({'ok': False, 'error': 'Invalid token'}), 401


@telegram_bp.route('/create-set', methods=['POST'])
def create_set():
    """Create a new sticker set on Telegram."""
    data = request.get_json()
    token = data.get('token')
    user_id = data.get('user_id')
    name = data.get('name')
    title = data.get('title')
    sticker_configs = data.get('stickers', [])

    if not all([token, user_id, name, title, sticker_configs]):
        return jsonify({'error': 'Missing required fields'}), 400

    # Build sticker file list
    stickers = []
    for sc in sticker_configs:
        file_id = sc.get('file_id')
        sticker = get_sticker(file_id)
        if not sticker:
            continue

        # Use processed path if available, otherwise upload path
        file_path = sticker.get('processed_path') or sticker.get('upload_path')
        if not file_path or not os.path.exists(file_path):
            continue

        fmt = 'video' if sticker['file_type'] in ('video', 'animated_gif') else 'static'
        stickers.append({
            'file_path': file_path,
            'emoji': sc.get('emoji', '🎨'),
            'format': fmt,
        })

    if not stickers:
        return jsonify({'error': 'No valid stickers to upload'}), 400

    result = create_sticker_set(token, user_id, name, title, stickers)
    return jsonify(result)


@telegram_bp.route('/add-sticker', methods=['POST'])
def add_sticker():
    """Add a sticker to an existing set."""
    data = request.get_json()
    token = data.get('token')
    user_id = data.get('user_id')
    name = data.get('name')
    file_id = data.get('file_id')
    emoji = data.get('emoji', '🎨')

    sticker = get_sticker(file_id)
    if not sticker:
        return jsonify({'error': 'Sticker not found'}), 404

    file_path = sticker.get('processed_path') or sticker.get('upload_path')
    fmt = 'video' if sticker['file_type'] in ('video', 'animated_gif') else 'static'

    result = add_sticker_to_set(token, user_id, name, {
        'file_path': file_path,
        'emoji': emoji,
        'format': fmt,
    })
    return jsonify(result)


@telegram_bp.route('/get-set', methods=['POST'])
def get_set():
    """Get sticker set info."""
    data = request.get_json()
    token = data.get('token')
    name = data.get('name')

    info = get_sticker_set(token, name)
    if info:
        return jsonify({'ok': True, 'set': info})
    return jsonify({'ok': False, 'error': 'Set not found'}), 404
