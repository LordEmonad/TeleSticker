"""TeleSticker configuration constants."""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Directories
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'output')
PACKS_FOLDER = os.path.join(BASE_DIR, 'packs')

# Telegram sticker specs
MAX_IMAGE_SIZE = 512          # pixels - one side must be exactly 512
MAX_VIDEO_DURATION = 3        # seconds
MAX_VIDEO_SIZE_KB = 256       # KB
MAX_IMAGE_SIZE_KB = 512       # KB
ICON_SIZE = 100               # pixels
MAX_ICON_SIZE_KB = 32         # KB
VIDEO_FPS = 30                # frames per second
CUSTOM_EMOJI_SIZE = 100       # pixels for custom emoji mode

# Upload limits
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max upload

# Processing
MAX_WORKERS = 3               # ThreadPoolExecutor workers
VIDEO_TIMEOUT = 120           # seconds before video conversion times out
CLEANUP_INTERVAL_HOURS = 1    # how often to run file cleanup
FILE_MAX_AGE_HOURS = 24       # delete files older than this

# Supported file types
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tiff'}
VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi', 'wmv', 'webm', 'mkv'}
ANIMATED_EXTENSIONS = {'gif'}

# Flask config
SECRET_KEY = 'telesticker_secret_key_v2'
