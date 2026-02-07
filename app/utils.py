"""Utility functions for validation, file type detection, and logging."""

import os
import logging
from pathlib import Path
from app.config import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, ANIMATED_EXTENSIONS

logger = logging.getLogger('telesticker')


def setup_logging():
    """Configure structured logging."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)s %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    ))
    root = logging.getLogger('telesticker')
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    return root


def detect_file_type(filename):
    """Detect file type from extension. Returns 'image', 'video', 'animated_gif', or None."""
    ext = Path(filename).suffix.lower().lstrip('.')
    if ext in ANIMATED_EXTENSIONS:
        return 'animated_gif'
    if ext in IMAGE_EXTENSIONS:
        return 'image'
    if ext in VIDEO_EXTENSIONS:
        return 'video'
    return None


def is_animated_gif(filepath):
    """Check if a GIF file is actually animated (has multiple frames)."""
    try:
        from PIL import Image
        with Image.open(filepath) as img:
            try:
                img.seek(1)
                return True
            except EOFError:
                return False
    except Exception:
        return False


def validate_file(filename, filesize=None):
    """Validate an uploaded file. Returns (valid, warnings) tuple."""
    warnings = []
    file_type = detect_file_type(filename)

    if file_type is None:
        return False, ['Unsupported file type']

    if filesize and filesize > 50 * 1024 * 1024:
        warnings.append('File is very large, processing may be slow')

    return True, warnings


def format_size(size_bytes):
    """Format byte size to human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f'{size_bytes:.1f} {unit}'
        size_bytes /= 1024
    return f'{size_bytes:.1f} TB'
