"""Server-sent events: one queue per open tab, and a thread pool for the renders.

A render is keyed by sticker: asking for a sticker that is already queued replaces the queued request (the
newest edit wins) and a render already running is let finish and then re-run, so a slider dragged ten times
costs two renders, not ten.
"""
import json
import logging
import queue
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor

from .config import WORKERS

log = logging.getLogger('emosticker.events')

_clients = set()
_clients_lock = threading.Lock()


def subscribe():
    q = queue.Queue(maxsize=500)
    with _clients_lock:
        _clients.add(q)
    return q


def unsubscribe(q):
    with _clients_lock:
        _clients.discard(q)


def emit(event, data):
    msg = f'event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'
    with _clients_lock:
        dead = []
        for q in _clients:
            try:
                q.put_nowait(msg)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _clients.discard(q)


def stream(q):
    yield 'retry: 1500\n\n'
    while True:
        try:
            yield q.get(timeout=20)
        except queue.Empty:
            yield ': ping\n\n'


# ---- the render queue ---------------------------------------------------------------------------------

_pool = ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix='render')
_state_lock = threading.Lock()
_pending = {}      # key -> fn to run next
_running = set()   # keys being rendered now


def schedule(key, fn):
    """Run fn for key soon. Coalesces: the latest fn for a key wins, and a key never runs twice at once."""
    with _state_lock:
        _pending[key] = fn
        if key in _running:
            return
        _running.add(key)
    _pool.submit(_drain, key)


def _drain(key):
    while True:
        with _state_lock:
            fn = _pending.pop(key, None)
            if fn is None:
                _running.discard(key)
                return
        try:
            fn()
        except Exception as e:  # a render failure is reported, never fatal
            log.error('render %s failed: %s\n%s', key, e, traceback.format_exc())
            emit('error', {'key': key, 'message': str(e)})


def busy():
    with _state_lock:
        return len(_running) + len(_pending)


def run_async(fn):
    return _pool.submit(fn)
