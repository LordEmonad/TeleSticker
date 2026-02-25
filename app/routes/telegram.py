"""Telegram integration routes."""

import re
from flask import Blueprint, request, jsonify
from app.services.telegram_api import validate_token, create_sticker_set, add_sticker_to_set, get_sticker_set
from app.routes.upload import get_sticker
from app.config import OUTPUT_FOLDER
import os

telegram_bp = Blueprint('telegram', __name__, url_prefix='/api/telegram')

# Telegram sticker set names: 1-64 chars, alphanumeric + underscores, must end with _by_<botname>
_SET_NAME_RE = re.compile(r'^[A-Za-z0-9_]{1,64}$')


def _validate_user_id(val):
    """Return int user_id or None if invalid."""
    try:
        uid = int(val)
        return uid if uid > 0 else None
    except (TypeError, ValueError):
        return None


def _validate_set_name(name):
    """Return (valid: bool, error: str|None)."""
    if not name or not isinstance(name, str):
        return False, 'Set name is required'
    if len(name) > 64:
        return False, 'Set name must be 64 characters or fewer'
    if not _SET_NAME_RE.match(name):
        return False, 'Set name must contain only letters, digits, and underscores'
    return True, None


def _validate_title(title):
    if not title or not isinstance(title, str):
        return False, 'Title is required'
    if len(title) > 64:
        return False, 'Title must be 64 characters or fewer'
    return True, None


@telegram_bp.route('/validate', methods=['POST'])
def validate():
    """Validate a bot token."""
    data = request.get_json()
    token = data.get('token', '')
    if not token or not isinstance(token, str):
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

    user_id = _validate_user_id(user_id)
    if not user_id:
        return jsonify({'error': 'user_id must be a positive integer'}), 400

    valid, err = _validate_set_name(name)
    if not valid:
        return jsonify({'error': err}), 400

    valid, err = _validate_title(title)
    if not valid:
        return jsonify({'error': err}), 400

    # Build sticker file list, tracking which ones were skipped
    stickers = []
    skipped = []
    for sc in sticker_configs:
        file_id = sc.get('file_id')
        sticker = get_sticker(file_id)
        if not sticker:
            skipped.append({'file_id': file_id, 'reason': 'Sticker not found (may have been deleted)'})
            continue

        file_path = sticker.get('processed_path') or sticker.get('upload_path')
        if not file_path or not os.path.exists(file_path):
            skipped.append({'file_id': file_id, 'reason': 'File missing from disk'})
            continue

        fmt = 'video' if sticker['file_type'] in ('video', 'animated_gif') else 'static'
        stickers.append({
            'file_path': file_path,
            'emoji': sc.get('emoji', '🎨'),
            'format': fmt,
        })

    if not stickers:
        return jsonify({
            'error': 'No valid stickers to upload',
            'skipped': skipped,
        }), 400

    result = create_sticker_set(token, user_id, name, title, stickers)
    if skipped:
        result['skipped'] = skipped
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

    if not all([token, user_id, name, file_id]):
        return jsonify({'error': 'Missing required fields'}), 400

    user_id = _validate_user_id(user_id)
    if not user_id:
        return jsonify({'error': 'user_id must be a positive integer'}), 400

    valid, err = _validate_set_name(name)
    if not valid:
        return jsonify({'error': err}), 400

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
