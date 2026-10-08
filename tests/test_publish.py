"""Publishing against a fake Telegram: the create, then an update that adds, replaces and reorders.

The fake answers the Bot API methods publish.py uses the way Telegram does (file ids by position, sets by name),
so the bookkeeping (our ids -> Telegram's file ids, generations, order) is what is tested.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv('EMOSTICKER_DATA', str(tmp_path / 'data'))
    for m in [k for k in list(sys.modules) if k == 'server' or k.startswith('server.')]:
        del sys.modules[m]
    from server import config, library, publish, telegram, events
    config.DATA_DIR = tmp_path / 'data'; config.MEDIA_DIR = config.DATA_DIR / 'media'
    config.LIBRARY_FILE = config.DATA_DIR / 'library.json'; config.SETTINGS_FILE = config.DATA_DIR / 'settings.json'
    library.LIBRARY_FILE = config.LIBRARY_FILE; library.MEDIA_DIR = config.MEDIA_DIR; library.SETTINGS_FILE = config.SETTINGS_FILE
    library._db = None

    sets = {}
    calls = []
    counter = [0]

    def fake_call(token, method, data=None, files=None, retries=2):
        data = data or {}
        calls.append((method, dict(data)))
        if method == 'getStickerSet':
            if data['name'] not in sets:
                raise telegram.TelegramError('Bad Request: STICKERSET_INVALID')
            s = sets[data['name']]
            return dict(name=s['name'], title=s['title'], sticker_type=s['type'], stickers=[dict(file_id=f, emoji='🥀') for f in s['stickers']])
        if method == 'createNewStickerSet':
            if data['name'] in sets:
                raise telegram.TelegramError('Bad Request: sticker set name is already occupied')
            inputs = json.loads(data['stickers'])
            assert all(i['format'] in ('static', 'video') and i['emoji_list'] for i in inputs)
            ids = []
            for i in inputs:
                counter[0] += 1; ids.append(f'file{counter[0]}')
            sets[data['name']] = dict(name=data['name'], title=data['title'], type=data.get('sticker_type', 'regular'), stickers=ids)
            return True
        if method == 'addStickerToSet':
            s = sets[data['name']]
            json.loads(data['sticker'])['format']
            counter[0] += 1; s['stickers'].append(f'file{counter[0]}')
            return True
        if method == 'replaceStickerInSet':
            s = sets[data['name']]
            pos = s['stickers'].index(data['old_sticker'])
            counter[0] += 1; s['stickers'][pos] = f'file{counter[0]}'
            return True
        if method == 'setStickerPositionInSet':
            for s in sets.values():
                if data['sticker'] in s['stickers']:
                    s['stickers'].remove(data['sticker']); s['stickers'].insert(int(data['position']), data['sticker'])
            return True
        if method == 'setStickerSetTitle':
            sets[data['name']]['title'] = data['title']; return True
        if method in ('setStickerEmojiList', 'setStickerKeywords'):
            return True
        raise AssertionError('unexpected method ' + method)

    monkeypatch.setattr(telegram, 'call', fake_call)
    monkeypatch.setattr(events, 'emit', lambda *a, **k: None)

    def make_sticker(name, gen=1):
        sid = library.new_id()
        d = library.media_dir(sid)
        Image.fromarray(np.zeros((512, 512, 4), np.uint8)).save(d / 'out.webp')
        rec = dict(id=sid, name=name, source=dict(kind='image', path=str(d / 'out.webp')), emoji=['🥀'], keywords=[],
                   edit={}, out=dict(status='done', ready=True, kind='image', file='out.webp', gen=gen, final=True))
        library.add_sticker(rec)
        return sid

    return dict(library=library, publish=publish, telegram=telegram, sets=sets, calls=calls, make=make_sticker)


def test_create_then_update(world):
    lib, pub, sets, calls, make = world['library'], world['publish'], world['sets'], world['calls'], world['make']
    a, b, c = make('a'), make('b'), make('c')
    pid = lib.current_pack()['id']
    pub._publish(pid, 'tok', 42, 'emo_by_bot', 'Emo', 'bot', 'regular', False)
    p = lib.current_pack()
    assert p['published']['stickers'] == {a: 'file1', b: 'file2', c: 'file3'}
    assert sets['emo_by_bot']['stickers'] == ['file1', 'file2', 'file3']
    create = next(d for m, d in calls if m == 'createNewStickerSet')
    assert 'sticker_format' not in create and create['sticker_type'] == 'regular'
    # re-edit b (new generation), add d, reorder d first, retitle
    lib.update_sticker(b, out=dict(gen=2))
    d = make('d')
    lib.update_pack(pid, stickers=[d, a, b, c])
    calls.clear()
    pub._publish(pid, 'tok', 42, 'emo_by_bot', 'Emo 2', 'bot', 'regular', False)
    methods = [m for m, _ in calls]
    assert 'createNewStickerSet' not in methods
    assert methods.count('replaceStickerInSet') == 1 and methods.count('addStickerToSet') == 1
    assert 'setStickerSetTitle' in methods
    p = lib.current_pack()
    published = p['published']['stickers']
    assert set(published) == {a, b, c, d}
    assert sets['emo_by_bot']['stickers'] == [published[d], published[a], published[b], published[c]]
    assert sets['emo_by_bot']['title'] == 'Emo 2'
    # a third run changes nothing
    calls.clear()
    pub._publish(pid, 'tok', 42, 'emo_by_bot', 'Emo 2', 'bot', 'regular', False)
    assert not any(m in ('addStickerToSet', 'replaceStickerInSet', 'setStickerPositionInSet') for m, _ in calls)


def test_not_ready_left_out_and_empty_refused(world):
    lib, pub, make = world['library'], world['publish'], world['make']
    a = make('a')
    lib.update_sticker(a, out=dict(ready=False))
    with pytest.raises(RuntimeError):
        pub._publish(lib.current_pack()['id'], 'tok', 42, 'x_by_bot', 'X', 'bot', 'regular', False)


def test_type_mismatch_refused(world):
    lib, pub, sets, make = world['library'], world['publish'], world['sets'], world['make']
    make('a')
    sets['x_by_bot'] = dict(name='x_by_bot', title='X', type='custom_emoji', stickers=['f0'])
    with pytest.raises(RuntimeError):
        pub._publish(lib.current_pack()['id'], 'tok', 42, 'x_by_bot', 'X', 'bot', 'regular', False)
