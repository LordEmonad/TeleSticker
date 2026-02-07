"""Telegram Bot API client for sticker set management."""

import logging

logger = logging.getLogger('telesticker.telegram')

_httpx = None


def _get_httpx():
    global _httpx
    if _httpx is None:
        import httpx
        _httpx = httpx
    return _httpx


def _api_url(token, method):
    return f'https://api.telegram.org/bot{token}/{method}'


def validate_token(token):
    """Validate a bot token, returns bot info dict or None."""
    httpx = _get_httpx()
    try:
        r = httpx.get(_api_url(token, 'getMe'), timeout=10)
        data = r.json()
        if data.get('ok'):
            return data['result']
        return None
    except Exception as e:
        logger.error(f'Token validation failed: {e}')
        return None


def create_sticker_set(token, user_id, name, title, stickers):
    """Create a new sticker set.
    stickers: list of dicts with 'file_path', 'emoji', 'format' ('static'/'video')
    """
    httpx = _get_httpx()
    try:
        first = stickers[0]
        files = {}
        data = {
            'user_id': user_id,
            'name': name,
            'title': title,
            'sticker_format': first.get('format', 'static'),
        }

        # Build sticker input for first sticker
        sticker_data = {
            'emoji_list': [first.get('emoji', '🎨')],
        }

        with open(first['file_path'], 'rb') as f:
            file_bytes = f.read()

        # Use input_sticker format
        import json as _json
        sticker_data['sticker'] = 'attach://sticker_file'
        data['stickers'] = _json.dumps([sticker_data])
        files['sticker_file'] = ('sticker', file_bytes)

        r = httpx.post(
            _api_url(token, 'createNewStickerSet'),
            data=data, files=files, timeout=30
        )
        result = r.json()
        if not result.get('ok'):
            return {'ok': False, 'error': result.get('description', 'Unknown error')}

        # Add remaining stickers
        errors = []
        for i, s in enumerate(stickers[1:], start=2):
            res = add_sticker_to_set(token, user_id, name, s)
            if not res.get('ok'):
                errors.append(f'Sticker {i}: {res.get("error", "failed")}')

        return {'ok': True, 'errors': errors}
    except Exception as e:
        logger.error(f'Create sticker set failed: {e}')
        return {'ok': False, 'error': str(e)}


def add_sticker_to_set(token, user_id, name, sticker):
    """Add a single sticker to an existing set."""
    httpx = _get_httpx()
    try:
        import json as _json
        sticker_data = {
            'emoji_list': [sticker.get('emoji', '🎨')],
            'sticker': 'attach://sticker_file',
        }

        with open(sticker['file_path'], 'rb') as f:
            file_bytes = f.read()

        data = {
            'user_id': user_id,
            'name': name,
            'sticker': _json.dumps(sticker_data),
        }
        files = {'sticker_file': ('sticker', file_bytes)}

        r = httpx.post(
            _api_url(token, 'addStickerToSet'),
            data=data, files=files, timeout=30
        )
        result = r.json()
        if result.get('ok'):
            return {'ok': True}
        return {'ok': False, 'error': result.get('description', 'Unknown error')}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def get_sticker_set(token, name):
    """Get sticker set info."""
    httpx = _get_httpx()
    try:
        r = httpx.get(
            _api_url(token, 'getStickerSet'),
            params={'name': name}, timeout=10
        )
        data = r.json()
        if data.get('ok'):
            return data['result']
        return None
    except Exception as e:
        logger.error(f'Get sticker set failed: {e}')
        return None
