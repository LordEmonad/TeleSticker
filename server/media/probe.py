"""What is this file? Dimensions, duration, frame rate, alpha, animated or still."""
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageSequence

from ..config import IMAGE_EXT, VIDEO_EXT, ffmpeg_bin

Image.MAX_IMAGE_PIXELS = 120_000_000

try:  # HEIC/AVIF from phones, if the optional plugin is installed
    import pillow_heif  # noqa: F401
    pillow_heif.register_heif_opener()
except Exception:
    pass


def ffprobe(path):
    cmd = [ffmpeg_bin('ffprobe'), '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[-400:] or 'ffprobe failed')
    return json.loads(r.stdout or '{}')


def _frac(s):
    try:
        a, b = s.split('/')
        return float(a) / float(b) if float(b) else 0.0
    except Exception:
        return 0.0


def probe(path):
    """Returns dict(kind='image'|'video', width, height, duration, fps, frames, alpha, codec)."""
    path = Path(path)
    ext = path.suffix.lower().lstrip('.')
    info = None
    if ext in IMAGE_EXT:
        try:
            info = _probe_image(path)
        except Exception:
            info = None
    if info is None and (ext in VIDEO_EXT or info is None):
        info = _probe_video(path)
    return info


def _probe_image(path):
    with Image.open(path) as im:
        n = getattr(im, 'n_frames', 1)
        if n > 1:
            durs = []
            for fr in ImageSequence.Iterator(im):
                durs.append(fr.info.get('duration', 100) or 100)
                if len(durs) >= 600:
                    break
            total = sum(durs) / 1000.0
            fps = len(durs) / total if total else 10.0
            return dict(kind='video', width=im.width, height=im.height, duration=round(total, 3),
                        fps=round(min(fps, 60), 3), frames=n, alpha=True, codec=im.format.lower(), container=im.format.lower())
        alpha = im.mode in ('RGBA', 'LA', 'PA') or 'transparency' in im.info
        return dict(kind='image', width=im.width, height=im.height, duration=0, fps=0, frames=1,
                    alpha=alpha, codec=(im.format or '').lower(), container=(im.format or '').lower())


def _probe_video(path):
    data = ffprobe(path)
    v = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
    if not v:
        raise ValueError('No picture in this file')
    fmt = data.get('format', {})
    fps = _frac(v.get('avg_frame_rate', '0/1')) or _frac(v.get('r_frame_rate', '0/1')) or 24.0
    duration = float(v.get('duration') or fmt.get('duration') or 0)
    frames = int(v.get('nb_frames') or 0) or int(round(duration * fps))
    pix = v.get('pix_fmt', '')
    alpha = ('a' in pix.replace('yuv', '').replace('gbr', '')) or v.get('tags', {}).get('alpha_mode') == '1' \
        or pix in ('rgba', 'bgra', 'argb', 'abgr', 'yuva420p', 'yuva444p', 'gbrap', 'ya8', 'pal8')
    rot = 0
    for sd in v.get('side_data_list', []) or []:
        if 'rotation' in sd:
            rot = int(sd['rotation'])
    w, h = int(v.get('width', 0)), int(v.get('height', 0))
    if rot % 180:
        w, h = h, w
    if duration == 0 and frames <= 1:
        return dict(kind='image', width=w, height=h, duration=0, fps=0, frames=1, alpha=alpha,
                    codec=v.get('codec_name', ''), container=fmt.get('format_name', ''))
    return dict(kind='video', width=w, height=h, duration=round(duration, 3), fps=round(min(fps, 120), 3),
                frames=frames, alpha=alpha, codec=v.get('codec_name', ''), container=fmt.get('format_name', ''),
                audio=any(s.get('codec_type') == 'audio' for s in data.get('streams', [])))
