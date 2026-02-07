"""File lifecycle management — temp file cleanup scheduler."""

import os
import time
import logging
import threading
from app.config import UPLOAD_FOLDER, OUTPUT_FOLDER, CLEANUP_INTERVAL_HOURS, FILE_MAX_AGE_HOURS

logger = logging.getLogger('telesticker.files')


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
