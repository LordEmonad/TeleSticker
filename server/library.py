"""The library: every sticker and pack, kept on disk so a restart changes nothing.

One JSON file written atomically under a lock. Media lives in data/media/<sticker id>/.
"""
import json
import os
import shutil
import threading
import time
import uuid
from copy import deepcopy

from .config import LIBRARY_FILE, MEDIA_DIR, SETTINGS_FILE, ensure_dirs

_lock = threading.RLock()
_db = None

EMPTY = {'version': 1, 'stickers': {}, 'packs': {}, 'order': []}


def _load():
    global _db
    if _db is not None:
        return _db
    ensure_dirs()
    if LIBRARY_FILE.exists():
        try:
            _db = json.loads(LIBRARY_FILE.read_text('utf-8'))
        except Exception:
            bad = LIBRARY_FILE.with_suffix('.corrupt-%d.json' % int(time.time()))
            shutil.copy(LIBRARY_FILE, bad)
            _db = deepcopy(EMPTY)
    else:
        _db = deepcopy(EMPTY)
    for k, v in EMPTY.items():
        _db.setdefault(k, deepcopy(v))
    if not _db['packs']:
        pid = new_id()
        _db['packs'][pid] = {'id': pid, 'title': 'My stickers', 'name': '', 'type': 'regular',
                             'stickers': [], 'created': now(), 'published': None}
        _db['current_pack'] = pid
    return _db


def _save():
    tmp = LIBRARY_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(_db, ensure_ascii=False, indent=1), 'utf-8')
    os.replace(tmp, LIBRARY_FILE)


def now():
    return int(time.time() * 1000)


def new_id():
    return uuid.uuid4().hex[:12]


def snapshot():
    with _lock:
        return deepcopy(_load())


def media_dir(sid):
    d = MEDIA_DIR / sid
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---- stickers ----------------------------------------------------------------------------------------

def add_sticker(record):
    with _lock:
        db = _load()
        db['stickers'][record['id']] = record
        pack = db['packs'][db.get('current_pack') or next(iter(db['packs']))]
        pack['stickers'].append(record['id'])
        _save()
        return deepcopy(record)


def get_sticker(sid):
    with _lock:
        s = _load()['stickers'].get(sid)
        return deepcopy(s) if s else None


def update_sticker(sid, **fields):
    with _lock:
        db = _load()
        s = db['stickers'].get(sid)
        if not s:
            return None
        for k, v in fields.items():
            if isinstance(v, dict) and isinstance(s.get(k), dict) and k in ('edit', 'out', 'source'):
                s[k].update(v)
            else:
                s[k] = v
        s['updated'] = now()
        _save()
        return deepcopy(s)


def delete_sticker(sid):
    with _lock:
        db = _load()
        s = db['stickers'].pop(sid, None)
        for p in db['packs'].values():
            if sid in p['stickers']:
                p['stickers'].remove(sid)
        _save()
    if s:
        shutil.rmtree(MEDIA_DIR / sid, ignore_errors=True)
    return s is not None


# ---- packs -------------------------------------------------------------------------------------------

def current_pack():
    with _lock:
        db = _load()
        return deepcopy(db['packs'][db['current_pack']])


def update_pack(pid, **fields):
    with _lock:
        db = _load()
        p = db['packs'].get(pid)
        if not p:
            return None
        for k, v in fields.items():
            if k == 'stickers':
                known = [x for x in v if x in db['stickers']]
                # keep any sticker the client did not mention, so a stale reorder cannot lose one
                for x in p['stickers']:
                    if x not in known and x in db['stickers']:
                        known.append(x)
                p['stickers'] = known
            else:
                p[k] = v
        p['updated'] = now()
        _save()
        return deepcopy(p)


def new_pack(title):
    with _lock:
        db = _load()
        pid = new_id()
        db['packs'][pid] = {'id': pid, 'title': title or 'New pack', 'name': '', 'type': 'regular',
                            'stickers': [], 'created': now(), 'published': None}
        db['current_pack'] = pid
        _save()
        return deepcopy(db['packs'][pid])


def switch_pack(pid):
    with _lock:
        db = _load()
        if pid in db['packs']:
            db['current_pack'] = pid
            _save()
            return deepcopy(db['packs'][pid])
        return None


def delete_pack(pid, with_stickers=False):
    with _lock:
        db = _load()
        if pid not in db['packs'] or len(db['packs']) == 1:
            return False
        p = db['packs'].pop(pid)
        if with_stickers:
            for sid in p['stickers']:
                if not any(sid in q['stickers'] for q in db['packs'].values()):
                    db['stickers'].pop(sid, None)
                    shutil.rmtree(MEDIA_DIR / sid, ignore_errors=True)
        if db['current_pack'] == pid:
            db['current_pack'] = next(iter(db['packs']))
        _save()
        return True


def move_stickers(sids, to_pid):
    """Move stickers into another pack (or copy, if they are the same ids in both: a sticker may be in two packs)."""
    with _lock:
        db = _load()
        dst = db['packs'].get(to_pid)
        if not dst:
            return None
        for sid in sids:
            if sid in db['stickers'] and sid not in dst['stickers']:
                dst['stickers'].append(sid)
        _save()
        return deepcopy(dst)


# ---- settings ----------------------------------------------------------------------------------------

def settings():
    with _lock:
        ensure_dirs()
        if SETTINGS_FILE.exists():
            try:
                return json.loads(SETTINGS_FILE.read_text('utf-8'))
            except Exception:
                return {}
        return {}


def save_settings(**fields):
    with _lock:
        s = settings()
        s.update(fields)
        tmp = SETTINGS_FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps(s, indent=1), 'utf-8')
        os.replace(tmp, SETTINGS_FILE)
        try:
            os.chmod(SETTINGS_FILE, 0o600)
        except Exception:
            pass
        return s
