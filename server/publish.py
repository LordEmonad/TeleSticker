"""Publishing a pack to Telegram, as a background job that reports every step over SSE.

A pack remembers what it published: {name, title, type, bot, stickers: {sticker id: file_id}}, so a second
publish adds only what is new, replaces what was re-edited (its out.gen moved on), and can reorder, retitle,
re-emoji or delete without rebuilding the set.
"""
import logging
import threading
import time

from . import events, library, telegram
from .config import TG

log = logging.getLogger('emosticker.publish')
_lock = threading.Lock()
_active = {'running': False}


def _say(pid, kind, text, **extra):
    events.emit('publish', dict(pack=pid, kind=kind, text=text, t=int(time.time() * 1000), **extra))


def start(pid, token, user_id, name, title, bot_username, sticker_type='regular', needs_repainting=False):
    with _lock:
        if _active['running']:
            raise RuntimeError('A publish is already running')
        _active['running'] = True
    events.run_async(lambda: _run(pid, token, user_id, name, title, bot_username, sticker_type, needs_repainting))


def _run(pid, token, user_id, name, title, bot_username, sticker_type, needs_repainting):
    try:
        _publish(pid, token, user_id, name, title, bot_username, sticker_type, needs_repainting)
    except telegram.TelegramError as e:
        _say(pid, 'error', e.human(), raw=e.description)
    except Exception as e:
        log.exception('publish failed')
        _say(pid, 'error', str(e))
    finally:
        _active['running'] = False
        _say(pid, 'end', 'done')


def _publish(pid, token, user_id, name, title, bot_username, sticker_type, needs_repainting):
    db = library.snapshot()
    pack = db['packs'][pid]
    stickers = [db['stickers'][s] for s in pack['stickers'] if s in db['stickers']]
    ready = [s for s in stickers if (s.get('out') or {}).get('ready')]
    not_ready = [s for s in stickers if not (s.get('out') or {}).get('ready')]
    for s in not_ready:
        _say(pid, 'skip', f'{s["name"]} is not ready and was left out')
    if not ready:
        raise RuntimeError('No sticker is ready to publish')
    limit = TG['emoji_set_max'] if sticker_type == 'custom_emoji' else TG['set_max']
    pub = pack.get('published') or {}
    published = dict(pub.get('stickers') or {})
    exists = False
    remote = None
    if pub.get('name') == name:
        try:
            remote = telegram.get_set(token, name)
            exists = True
        except telegram.TelegramError:
            exists = False
    elif name:
        try:
            remote = telegram.get_set(token, name)
            exists = True
            if not pub:
                _say(pid, 'info', f'{name} already exists on Telegram; adding to it')
        except telegram.TelegramError:
            exists = False

    remote_ids = set()
    if remote:
        remote_ids = {s['file_id'] for s in remote.get('stickers', [])}
        # forget stickers deleted in the Telegram app
        published = {k: v for k, v in published.items() if v in remote_ids}
        if remote.get('sticker_type') != sticker_type:
            raise RuntimeError(f'{name} is a {remote.get("sticker_type")} set; this pack is {sticker_type}')

    if not exists:
        if len(ready) > limit:
            _say(pid, 'skip', f'Only the first {limit} go in; the set is full after that')
            ready = ready[:limit]
        _say(pid, 'info', f'Creating {name} ({len(ready)} stickers)')
        res = telegram.create_set(token, user_id, name, title, ready, sticker_type, needs_repainting,
                                  progress=lambda t: _say(pid, 'step', t))
        remote = telegram.get_set(token, name)
        # map our ids onto Telegram's file_ids by position
        for st, tg in zip([s for s in ready if s['id'] in res['added']], remote.get('stickers', [])):
            published[st['id']] = tg['file_id']
        for sid, why in res['failed']:
            _say(pid, 'error', f'{db["stickers"][sid]["name"]}: {why}')
        gens = {s['id']: (s['out'] or {}).get('gen') for s in ready}
        library.update_pack(pid, name=name, title=title, published=dict(
            name=name, title=title, type=sticker_type, bot=bot_username, user_id=int(user_id), stickers=published,
            gens=gens, at=library.now(), link=f'https://t.me/addstickers/{name}'))
        _say(pid, 'done', f'Published {len(published)} stickers', link=f'https://t.me/addstickers/{name}')
        return

    # the set exists: add new, replace changed, retitle, then order
    gens = dict(pub.get('gens') or {})
    if remote.get('title') != title:
        telegram.set_title(token, name, title)
        _say(pid, 'step', f'Title set to {title}')
    count = len(remote_ids)
    for st in ready:
        sid = st['id']
        gen = (st.get('out') or {}).get('gen')
        try:
            if sid in published and published[sid] in remote_ids:
                if gens.get(sid) != gen:
                    telegram.replace_sticker(token, user_id, name, published[sid], st)
                    fresh = telegram.get_set(token, name)
                    # the replacement keeps the position; find the file_id at that position
                    pos = next((i for i, s in enumerate(remote['stickers']) if s['file_id'] == published[sid]), None)
                    if pos is not None and pos < len(fresh['stickers']):
                        published[sid] = fresh['stickers'][pos]['file_id']
                    remote = fresh
                    remote_ids = {s['file_id'] for s in remote['stickers']}
                    gens[sid] = gen
                    _say(pid, 'step', f'Replaced {st["name"]}')
                else:
                    # emoji or keywords may have changed
                    tg = next((s for s in remote['stickers'] if s['file_id'] == published[sid]), None)
                    if tg and tg.get('emoji') and st.get('emoji') and tg['emoji'] != st['emoji'][0]:
                        telegram.set_emoji(token, published[sid], st['emoji'])
                        _say(pid, 'step', f'Emoji set on {st["name"]}')
                continue
            if count >= limit:
                _say(pid, 'skip', f'{st["name"]}: the set is full')
                continue
            telegram.add_sticker(token, user_id, name, st)
            fresh = telegram.get_set(token, name)
            new_ids = [s['file_id'] for s in fresh['stickers'] if s['file_id'] not in remote_ids]
            if new_ids:
                published[sid] = new_ids[-1]
            remote = fresh
            remote_ids = {s['file_id'] for s in remote['stickers']}
            gens[sid] = gen
            count += 1
            _say(pid, 'step', f'Added {st["name"]}')
        except telegram.TelegramError as e:
            _say(pid, 'error', f'{st["name"]}: {e.human()}', raw=e.description)
    # order: walk the pack's order and move each known sticker to its index
    want = [published[s['id']] for s in ready if s['id'] in published]
    current = [s['file_id'] for s in remote.get('stickers', [])]
    if want and current[: len(want)] != want:
        for i, fid in enumerate(want):
            if i < len(current) and current[i] == fid:
                continue
            try:
                telegram.move_sticker(token, fid, i)
                current.remove(fid)
                current.insert(i, fid)
            except telegram.TelegramError as e:
                _say(pid, 'error', f'reorder: {e.human()}')
                break
        _say(pid, 'step', 'Order updated')
    library.update_pack(pid, name=name, title=title, published=dict(
        name=name, title=title, type=sticker_type, bot=bot_username, user_id=int(user_id), stickers=published,
        gens=gens, at=library.now(), link=f'https://t.me/addstickers/{name}'))
    _say(pid, 'done', f'{name} is up to date ({len(published)} stickers)', link=f'https://t.me/addstickers/{name}')


def remove_remote(pid, token, sid):
    pack = library.current_pack() if library.current_pack()['id'] == pid else None
    pub = (pack or {}).get('published') or {}
    fid = (pub.get('stickers') or {}).get(sid)
    if not fid:
        return False
    telegram.delete_sticker(token, fid)
    pub['stickers'].pop(sid, None)
    library.update_pack(pid, published=pub)
    return True
