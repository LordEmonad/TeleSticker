"""AI background removal through rembg, when it is installed. Models download on first use (~170 MB)."""
import logging
import subprocess
import sys
import threading

import numpy as np
from PIL import Image

log = logging.getLogger('emosticker.rembg')
_sessions = {}
_lock = threading.Lock()

MODELS = [
    ('isnet-general-use', 'General (best edges)'),
    ('u2net', 'Classic'),
    ('u2net_human_seg', 'People'),
    ('isnet-anime', 'Anime and cartoons'),
    ('silueta', 'Fast, small'),
]


def available():
    try:
        import rembg  # noqa: F401
        return True
    except Exception:
        return False


def session(model):
    with _lock:
        if model not in _sessions:
            from rembg import new_session
            _sessions[model] = new_session(model)
        return _sessions[model]


def remove(rgba, model='isnet-general-use', matting=True, fg=240, bg=10, erode=10):
    from rembg import remove as _remove
    im = Image.fromarray(rgba)
    out = _remove(im, session=session(model), alpha_matting=bool(matting),
                  alpha_matting_foreground_threshold=int(fg), alpha_matting_background_threshold=int(bg),
                  alpha_matting_erode_size=int(erode), post_process_mask=False)
    return np.asarray(out.convert('RGBA'), dtype=np.uint8).copy()


def remove_frames(frames, **kw):
    # the mask is computed per frame; for cartoons that is steadier than it sounds, and it is what rembg offers
    return np.stack([remove(f, **kw) for f in frames])


def install(progress):
    """pip install rembg + onnxruntime into this interpreter, streaming lines to progress(line)."""
    cmd = [sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', 'rembg>=2.0.60', 'onnxruntime>=1.17']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in p.stdout:
        progress(line.rstrip())
    return p.wait() == 0
