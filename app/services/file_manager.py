"""File lifecycle management — temp file cleanup scheduler."""

import os
import time
import logging
import threading
from app.config import UPLOAD_FOLDER, OUTPUT_FOLDER, CLEANUP_INTERVAL_HOURS, FILE_MAX_AGE_HOURS

logger = logging.getLogger('telesticker.files')

# Reference to sticker store + lock, set by init_sticker_cleanup()
_sticker_store = None
_sticker_lock = None


def init_sticker_cleanup(store, lock):
    """Register the in-memory sticker store so cleanup can evict stale entries."""
    global _sticker_store, _sticker_lock
    _sticker_store = store
    _sticker_lock = lock


def ensure_dirs():
    """Create required directories if they don't exist."""
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def cleanup_old_files():
    """Delete files older than FILE_MAX_AGE_HOURS from uploads and output."""
    max_age = FILE_MAX_AGE_HOURS * 3600
    now = time.time()
    count = 0

    for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
        if not os.path.isdir(folder):
            continue
        for fname in os.listdir(folder):
            fpath = os.path.join(folder, fname)
            try:
                if os.path.isfile(fpath) and (now - os.path.getmtime(fpath)) > max_age:
                    os.remove(fpath)
                    count += 1
            except Exception as e:
                logger.warning(f'Failed to remove {fpath}: {e}')

    # Evict sticker entries whose upload file no longer exists on disk
    if _sticker_store is not None and _sticker_lock is not None:
        stale_ids = []
        with _sticker_lock:
            for fid, s in _sticker_store.items():
                upload = s.get('upload_path', '')
                if upload and not os.path.exists(upload):
                    stale_ids.append(fid)
            for fid in stale_ids:
                del _sticker_store[fid]
        if stale_ids:
            logger.info(f'Evicted {len(stale_ids)} stale sticker entries')

    if count:
        logger.info(f'Cleaned up {count} old files')


def start_cleanup_scheduler():
    """Start a background thread that cleans old files periodically."""
    def _loop():
        while True:
            time.sleep(CLEANUP_INTERVAL_HOURS * 3600)
            cleanup_old_files()

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    logger.info('File cleanup scheduler started')
