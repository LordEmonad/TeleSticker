"""The Telegram Bot API, the sticker parts, as of Bot API 9.x: per-sticker `format`, mixed sets allowed,
1-50 initial stickers, `_by_<bot>` names, 120 per set (200 for custom emoji).

Every error Telegram returns is translated into a sentence a person can act on (ERRORS); the raw description
rides along for the log.
"""
import json
import logging
import re
import time

import httpx

from . import library

log = logging.getLogger('emosticker.telegram')
API = 'https://api.telegram.org/bot{token}/{method}'

ERRORS = [
    ('PEER_ID_INVALID', 'Telegram does not know this user for your bot yet. Open the bot in Telegram and press Start, then try again.'),
    ('USER_IS_BOT', 'The owner must be a person, not a bot.'),
    ('STICKERSET_INVALID', 'That sticker set does not exist, or this bot did not create it.'),
    ('sticker set name is already occupied', 'That set name is taken. Pick another short name.'),
    ('STICKERSET_NAME_OCCUPIED', 'That set name is taken. Pick another short name.'),
    ('STICKER_PNG_DIMENSIONS', 'Telegram rejected the picture size (one side must be exactly 512 px).'),
    ('STICKER_PNG_NOPNG', 'Telegram did not accept the image file.'),
    ('STICKER_VIDEO_BIG', 'The video sticker is over Telegram\'s 256 KB limit.'),
    ('STICKER_VIDEO_NOWEBM', 'Telegram did not accept the video file (it must be VP9 WebM).'),
    ('STICKER_EMOJI_INVALID', 'One of the emoji is not an emoji Telegram knows.'),
    ('STICKERS_TOO_MUCH', 'The set is full (120 stickers, 200 for custom emoji).'),
    ('STICKERSET_NOT_MODIFIED', 'Nothing changed.'),
    ('STICKER_FILE_INVALID', 'Telegram could not use that file.'),
    ('STICKER_TGS_NOTGS', 'Telegram expected a .TGS animation here.'),
    ('Unauthorized', 'The bot token is wrong or was revoked.'),
    ('bot was blocked by the user', 'You blocked this bot in Telegram. Unblock it and press Start.'),
    ('STICKERSET_OWNER_ANONYMOUS', 'The set owner is anonymous; Telegram refuses that.'),
    ('PACK_SHORT_NAME_INVALID', 'The short name is not allowed. Letters, digits and underscores, starting with a letter, ending in _by_<yourbot>.'),
    ('PACK_SHORT_NAME_OCCUPIED', 'That set name is taken. Pick another short name.'),
    ('PACK_TITLE_INVALID', 'The title is not allowed (1-64 characters).'),
    ('STICKER_THUMB_PNG_NOPNG', 'The set icon must be a .WEBP or .PNG of exactly 100x100.'),
    ('STICKER_THUMB_TGS_NOTGS', 'The set icon format must match the stickers\' format.'),
    ('wrong file identifier', 'Telegram no longer knows that sticker (it may have been deleted in the app).'),
    ('Too Many Requests', 'Telegram asked us to slow down. Wait a few seconds and try again.'),
]


class TelegramError(Exception):
    def __init__(self, description, code=None, retry_after=None):
        super().__init__(description)
        self.description = description
        self.code = code
        self.retry_after = retry_after

    def human(self):
        for key, text in ERRORS:
            if key.lower() in (self.description or '').lower():
                return text
        return self.description or 'Telegram refused the request.'


def _client():
    return httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0))


def call(token, method, data=None, files=None, retries=2):
    url = API.format(token=token, method=method)
    last = None
    for attempt in range(retries + 1):
        try:
            with _client() as c:
                r = c.post(url, data=data or {}, files=files or None)
            body = r.json()
        except (httpx.HTTPError, ValueError) as e:
            last = TelegramError(f'network: {e}')
            time.sleep(1.0 * (attempt + 1))
            continue
        if body.get('ok'):
            return body['result']
        desc = body.get('description', 'unknown error')
        params = body.get('parameters') or {}
        err = TelegramError(desc, body.get('error_code'), params.get('retry_after'))
        if err.retry_after and attempt < retries:
            time.sleep(min(30, err.retry_after + 0.5))
            continue
        raise err
    raise last


def get_me(token):
    return call(token, 'getMe')


def valid_token(token):
    return bool(re.fullmatch(r'\d{6,12}:[A-Za-z0-9_-]{30,}', (token or '').strip()))


def set_name(short, bot_username):
    """Build a legal set name from a short slug and the bot's username."""
    slug = re.sub(r'[^A-Za-z0-9_]+', '_', short or '').strip('_')
    slug = re.sub(r'_+', '_', slug)
    if not slug or not slug[0].isalpha():
        slug = 'pack_' + slug if slug else 'pack'
    tail = f'_by_{bot_username}'
    slug = slug[: max(1, 64 - len(tail))].rstrip('_')
    return slug + tail


def check_name(name, bot_username):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', name or ''):
        return 'Letters, digits and underscores only, starting with a letter, 1-64 characters.'
    if '__' in name:
        return 'No double underscores.'
    if not name.lower().endswith(f'_by_{bot_username}'.lower()):
        return f'Must end in _by_{bot_username}.'
    return None


def slug_of(name, bot_username):
    tail = f'_by_{bot_username}'.lower()
    return name[: -len(tail)] if name.lower().endswith(tail) else name


# ---- users: find the person's id from them pressing Start -------------------------------------------------

def find_user(token, since_update=0):
    """Look at the bot's pending updates for a private /start (or any private message). Returns dict(user, offset)."""
    res = call(token, 'getUpdates', {'offset': since_update, 'timeout': 0, 'allowed_updates': json.dumps(['message'])})
    user, last = None, since_update
    for u in res:
        last = max(last, u['update_id'] + 1)
        m = u.get('message') or {}
        chat = m.get('chat') or {}
        if chat.get('type') == 'private' and m.get('from'):
            user = m['from']
    return {'user': user, 'offset': last, 'count': len(res)}


def webhook_info(token):
    return call(token, 'getWebhookInfo')


# ---- sets -------------------------------------------------------------------------------------------------

def _input_sticker(st, attach_name):
    fmt = 'video' if st['out']['kind'] == 'video' else 'static'
    d = {'sticker': f'attach://{attach_name}', 'format': fmt, 'emoji_list': st.get('emoji') or ['🥀']}
    if st.get('keywords'):
        d['keywords'] = st['keywords'][:20]
    return d


def _file_tuple(st, attach_name):
    path = library.media_dir(st['id']) / st['out']['file']
    mime = 'video/webm' if st['out']['kind'] == 'video' else ('image/webp' if path.suffix == '.webp' else 'image/png')
    return attach_name, (path.name, open(path, 'rb').read(), mime)


def create_set(token, user_id, name, title, stickers, sticker_type='regular', needs_repainting=False, progress=None):
    """createNewStickerSet with up to 50 stickers at once, then addStickerToSet for the rest.
    Returns dict(added=[ids], failed=[(id, human error)])."""
    first, rest = stickers[:50], stickers[50:]
    data = {'user_id': int(user_id), 'name': name, 'title': title, 'sticker_type': sticker_type}
    if sticker_type == 'custom_emoji' and needs_repainting:
        data['needs_repainting'] = 'true'
    inputs, files = [], {}
    for i, st in enumerate(first):
        att = f's{i}'
        inputs.append(_input_sticker(st, att))
        k, v = _file_tuple(st, att)
        files[k] = v
    data['stickers'] = json.dumps(inputs, ensure_ascii=False)
    if progress:
        progress(f'Creating {name} with {len(first)} sticker(s)')
    call(token, 'createNewStickerSet', data, files)
    added = [s['id'] for s in first]
    failed = []
    for st in rest:
        try:
            add_sticker(token, user_id, name, st)
            added.append(st['id'])
            if progress:
                progress(f'Added {st["name"]}')
        except TelegramError as e:
            failed.append((st['id'], e.human()))
            if progress:
                progress(f'{st["name"]}: {e.human()}')
    return {'added': added, 'failed': failed}


def add_sticker(token, user_id, name, st):
    att = 'sticker'
    k, v = _file_tuple(st, att)
    data = {'user_id': int(user_id), 'name': name, 'sticker': json.dumps(_input_sticker(st, att), ensure_ascii=False)}
    return call(token, 'addStickerToSet', data, {k: v})


def replace_sticker(token, user_id, name, old_file_id, st):
    att = 'sticker'
    k, v = _file_tuple(st, att)
    data = {'user_id': int(user_id), 'name': name, 'old_sticker': old_file_id,
            'sticker': json.dumps(_input_sticker(st, att), ensure_ascii=False)}
    return call(token, 'replaceStickerInSet', data, {k: v})


def get_set(token, name):
    return call(token, 'getStickerSet', {'name': name})


def delete_sticker(token, file_id):
    return call(token, 'deleteStickerFromSet', {'sticker': file_id})


def move_sticker(token, file_id, position):
    return call(token, 'setStickerPositionInSet', {'sticker': file_id, 'position': int(position)})


def set_emoji(token, file_id, emoji_list):
    return call(token, 'setStickerEmojiList', {'sticker': file_id, 'emoji_list': json.dumps(emoji_list, ensure_ascii=False)})


def set_keywords(token, file_id, keywords):
    return call(token, 'setStickerKeywords', {'sticker': file_id, 'keywords': json.dumps(keywords, ensure_ascii=False)})


def set_title(token, name, title):
    return call(token, 'setStickerSetTitle', {'name': name, 'title': title})


def delete_set(token, name):
    return call(token, 'deleteStickerSet', {'name': name})


def set_thumbnail(token, user_id, name, path, fmt):
    files = {'thumbnail': (path.name, open(path, 'rb').read(), 'video/webm' if fmt == 'video' else 'image/webp')}
    return call(token, 'setStickerSetThumbnail', {'name': name, 'user_id': int(user_id), 'format': fmt}, files)


def drop_thumbnail(token, user_id, name, fmt):
    return call(token, 'setStickerSetThumbnail', {'name': name, 'user_id': int(user_id), 'format': fmt})


def set_emoji_thumbnail(token, name, custom_emoji_id=''):
    return call(token, 'setCustomEmojiStickerSetThumbnail', {'name': name, 'custom_emoji_id': custom_emoji_id})


def file_url(token, file_id):
    f = call(token, 'getFile', {'file_id': file_id})
    return f'https://api.telegram.org/file/bot{token}/{f["file_path"]}'
