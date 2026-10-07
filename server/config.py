"""EmoSticker settings and the sticker specs of every platform it exports to.

Everything here is a number from the platform's own documentation (Telegram: core.telegram.org/bots/api and
core.telegram.org/stickers; the others from their developer pages). The numbers are enforced by the encoders
and checked again by verify(), so a file the app calls ready really is.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get('EMOSTICKER_DATA') or ROOT / 'data')
MEDIA_DIR = DATA_DIR / 'media'
LIBRARY_FILE = DATA_DIR / 'library.json'
SETTINGS_FILE = DATA_DIR / 'settings.json'
WEB_DIR = ROOT / 'web'

HOST = os.environ.get('EMOSTICKER_HOST', '127.0.0.1')
PORT = int(os.environ.get('EMOSTICKER_PORT', '4747'))
MAX_UPLOAD_BYTES = 400 * 1024 * 1024
WORKERS = max(2, min(4, (os.cpu_count() or 4) // 2))

APP_NAME = 'EmoSticker'
VERSION = '3.0.0'

# Telegram, the primary target. One side exactly 512, the other 512 or less.
TG = dict(
    side=512,
    static_bytes=512 * 1024,       # the Bot API refuses larger .WEBP/.PNG
    video_bytes=256 * 1024,
    video_seconds=3.0,
    video_fps=30,
    emoji_side=100,                # custom emoji: exactly 100x100
    thumb_side=100,                # set icon: exactly 100x100
    thumb_static_bytes=128 * 1024,
    thumb_video_bytes=32 * 1024,
    set_max=120,
    emoji_set_max=200,
    initial_max=50,                # createNewStickerSet takes 1-50
    emoji_per_sticker=20,
    keywords_total=64,
)

# Export presets. Each is a kind of file the engine knows how to make, with the platform's limits.
TARGETS = {
    'telegram': dict(label='Telegram', static=dict(fmt='webp', side=512, square=False, bytes=TG['static_bytes']),
                     video=dict(fmt='webm', side=512, square=False, bytes=TG['video_bytes'], seconds=3.0, fps=30)),
    'telegram_emoji': dict(label='Telegram custom emoji',
                           static=dict(fmt='webp', side=100, square=True, bytes=TG['static_bytes']),
                           video=dict(fmt='webm', side=100, square=True, bytes=TG['video_bytes'], seconds=3.0, fps=30)),
    'whatsapp': dict(label='WhatsApp', static=dict(fmt='webp', side=512, square=True, bytes=100 * 1024),
                     video=dict(fmt='awebp', side=512, square=True, bytes=500 * 1024, seconds=10.0, fps=30)),
    'discord': dict(label='Discord', static=dict(fmt='png', side=320, square=True, bytes=512 * 1024),
                    video=dict(fmt='apng', side=320, square=True, bytes=512 * 1024, seconds=5.0, fps=30)),
    'signal': dict(label='Signal', static=dict(fmt='webp', side=512, square=True, bytes=300 * 1024),
                   video=dict(fmt='apng', side=512, square=True, bytes=300 * 1024, seconds=3.0, fps=30)),
}

IMAGE_EXT = {'png', 'jpg', 'jpeg', 'webp', 'bmp', 'tif', 'tiff', 'heic', 'heif', 'avif', 'gif', 'apng'}
VIDEO_EXT = {'mp4', 'mov', 'm4v', 'webm', 'mkv', 'avi', 'wmv', 'gif', 'apng', 'webp'}
ALL_EXT = IMAGE_EXT | VIDEO_EXT

# The whole working set of a video is held in memory as RGBA frames at the output size.
MAX_WORK_FRAMES = 450            # 15 s at 30 fps: trims pick a window inside it
PREVIEW_FRAMES = 12              # the filmstrip under the trim slider


def ensure_dirs():
    for d in (DATA_DIR, MEDIA_DIR):
        d.mkdir(parents=True, exist_ok=True)


def ffmpeg_bin(name):
    """ffmpeg/ffprobe: a bundled copy beside the app wins, then PATH, then Homebrew's usual place."""
    exe = name + ('.exe' if sys.platform == 'win32' else '')
    for cand in (ROOT / 'bin' / exe, ROOT / exe):
        if cand.exists():
            return str(cand)
    import shutil
    found = shutil.which(name)
    if found:
        return found
    for cand in ('/opt/homebrew/bin/' + name, '/usr/local/bin/' + name):
        if os.path.exists(cand):
            return cand
    return name
