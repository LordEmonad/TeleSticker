"""Decoding: any source into RGBA numpy frames at a working size.

Video goes through one ffmpeg pipe (every container and codec ffmpeg knows, alpha kept when the source has it,
rotation metadata honoured). Still images and animated GIF/APNG/WebP go through Pillow, which keeps their
palettes' transparency exactly.
"""
import subprocess

import numpy as np
from PIL import Image, ImageOps, ImageSequence

from ..config import MAX_WORK_FRAMES, ffmpeg_bin
from .probe import probe


def working_size(w, h, side):
    """Scale so the long side is `side` (never upscale past 2x: tiny sources stay crisp-ish, not blurry giants)."""
    if max(w, h) == 0:
        return side, side
    r = side / max(w, h)
    r = min(r, 2.0)
    return max(2, round(w * r)), max(2, round(h * r))


def load_image(path, side=512):
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        im = im.convert('RGBA')
        w, h = working_size(im.width, im.height, side)
        if (w, h) != im.size:
            im = im.resize((w, h), Image.LANCZOS)
        return np.asarray(im, dtype=np.uint8).copy()


def load_frames(path, info=None, side=512, start=0.0, end=None, fps=None, max_frames=MAX_WORK_FRAMES):
    """RGBA frames [n, h, w, 4] and the fps they are at, for the window start..end seconds of the source."""
    info = info or probe(path)
    if info['kind'] == 'image':
        return load_image(path, side)[None], 1.0
    if info.get('container') in ('gif', 'png', 'webp', 'apng') and info.get('codec') in ('gif', 'png', 'webp', 'apng'):
        try:
            return _pil_frames(path, side, start, end, fps, max_frames)
        except Exception:
            pass
    return _ffmpeg_frames(path, info, side, start, end, fps, max_frames)


def _pil_frames(path, side, start, end, fps, max_frames):
    frames, times = [], []
    t = 0.0
    with Image.open(path) as im:
        w, h = working_size(im.width, im.height, side)
        for fr in ImageSequence.Iterator(im):
            d = (fr.info.get('duration', 100) or 100) / 1000.0
            if t >= start and (end is None or t < end):
                f = fr.convert('RGBA')
                if f.size != (w, h):
                    f = f.resize((w, h), Image.LANCZOS)
                frames.append(np.asarray(f, dtype=np.uint8).copy())
                times.append(t)
            t += d
            if len(frames) >= max_frames * 4:
                break
    if not frames:
        raise ValueError('empty animation')
    # resample the (possibly irregular) frame times onto a steady clock
    src_fps = len(frames) / max(1e-6, (times[-1] - times[0]) + (t - times[-1]) / max(1, len(times)))
    out_fps = min(fps or src_fps, 30.0) if fps or src_fps > 30 else src_fps
    total = (end if end is not None else t) - start
    n = max(1, min(max_frames, int(round(total * out_fps))))
    idx = []
    for k in range(n):
        tk = start + k / out_fps
        j = int(np.searchsorted(np.array(times), tk, side='right') - 1)
        idx.append(min(max(j, 0), len(frames) - 1))
    return np.stack([frames[i] for i in idx]), float(out_fps)


def _ffmpeg_frames(path, info, side, start, end, fps, max_frames):
    w, h = working_size(info['width'], info['height'], side)
    src_fps = info.get('fps') or 24.0
    out_fps = float(fps or min(src_fps, 30.0))
    dur = (end if end is not None else info['duration']) - start
    if dur <= 0:
        dur = info['duration'] or 1.0
    n_est = int(round(dur * out_fps))
    if n_est > max_frames:  # too long: take the window at fewer fps rather than a shorter window
        out_fps = max(5.0, max_frames / dur)
    vf = f'fps={out_fps:.4f},scale={w}:{h}:flags=lanczos+accurate_rnd+full_chroma_int'
    cmd = [ffmpeg_bin('ffmpeg'), '-v', 'error', '-nostdin'] + _alpha_decoder(info)
    if start > 0:
        cmd += ['-ss', f'{start:.4f}']
    cmd += ['-i', str(path)]
    if end is not None:
        cmd += ['-t', f'{max(0.01, end - start):.4f}']
    cmd += ['-an', '-sn', '-vf', vf, '-f', 'rawvideo', '-pix_fmt', 'rgba', '-']
    r = subprocess.run(cmd, capture_output=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode('utf-8', 'replace').strip()[-400:] or 'decode failed')
    buf = np.frombuffer(r.stdout, np.uint8)
    per = w * h * 4
    n = len(buf) // per
    if n == 0:
        raise ValueError('No frames could be read from this file')
    frames = buf[: n * per].reshape(n, h, w, 4).copy()
    if not info.get('alpha'):
        frames[..., 3] = 255
    return frames[:max_frames], out_fps


def _alpha_decoder(info):
    """ffmpeg's native VP8/VP9 decoders drop the alpha plane of a WebM; libvpx keeps it."""
    codec = (info or {}).get('codec', '')
    if codec == 'vp9':
        return ['-c:v', 'libvpx-vp9']
    if codec == 'vp8':
        return ['-c:v', 'libvpx']
    return []


def filmstrip(path, info, n=12, height=72):
    """A row of n frames across the whole source, as one RGBA array (the trim slider's backdrop)."""
    if info['kind'] == 'image':
        return None
    dur = info['duration'] or 1.0
    w, h = working_size(info['width'], info['height'], 160)
    cmd = [ffmpeg_bin('ffmpeg'), '-v', 'error', '-nostdin'] + _alpha_decoder(info) + ['-i', str(path), '-an',
           '-vf', f'fps={n / dur:.6f},scale={w}:{h}', '-frames:v', str(n), '-f', 'rawvideo', '-pix_fmt', 'rgba', '-']
    r = subprocess.run(cmd, capture_output=True, timeout=300)
    buf = np.frombuffer(r.stdout, np.uint8)
    per = w * h * 4
    k = len(buf) // per
    if k == 0:
        return None
    fr = buf[: k * per].reshape(k, h, w, 4)
    strip = np.concatenate(list(fr), axis=1)
    if not info.get('alpha'):
        strip = strip.copy()
        strip[..., 3] = 255
    im = Image.fromarray(strip)
    im = im.resize((round(im.width * height / im.height), height), Image.LANCZOS)
    return im
