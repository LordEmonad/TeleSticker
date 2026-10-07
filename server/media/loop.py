"""Making a clip loop: finding the window that wraps best, fitting it into the time limit, closing the seam.

The seam measure is the one the Emonad sticker pipeline used: how big the step from the last frame back to
the first is, compared with a typical step inside the clip. 1.0 means the wrap looks like any other frame
step; 4+ is a visible jump.
"""
import numpy as np
from PIL import Image


def _small(frames, side=48):
    """Grey thumbnails as float arrays, premultiplied so transparent areas compare as black."""
    out = []
    for f in frames:
        im = Image.fromarray(f).resize((side, side), Image.BILINEAR)
        a = np.asarray(im, np.float32)
        g = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]) * a[..., 3] / 255
        out.append(g)
    return np.stack(out)


def seam_ratio(frames):
    if len(frames) < 3:
        return 0.0
    s = _small(frames)
    steps = np.abs(np.diff(s, axis=0)).mean(axis=(1, 2))
    wrap = np.abs(s[-1] - s[0]).mean()
    return float(wrap / (np.median(steps) + 1e-6))


def find_loop(frames, fps, max_seconds=3.0, min_seconds=0.6):
    """The (start, end) frame indices (end exclusive) of the window up to max_seconds that wraps best.
    Prefers longer windows: score = seam / sqrt(length). Returns (start, end, seam)."""
    n = len(frames)
    if n < 4:
        return 0, n, 0.0
    s = _small(frames)
    steps = np.abs(np.diff(s, axis=0)).mean(axis=(1, 2))
    typical = np.median(steps) + 1e-6
    max_len = max(2, min(n, int(round(max_seconds * fps))))
    min_len = max(2, min(max_len, int(round(min_seconds * fps))))
    flat = s.reshape(n, -1)
    best = (0, min(n, max_len), 1e9)
    best_score = 1e9
    # for each start, the wrap step to every candidate end frame (end-1), vectorised
    for a in range(0, n - min_len + 1):
        hi = min(n, a + max_len)
        ends = np.arange(a + min_len, hi + 1)          # exclusive ends
        last = flat[ends - 1]                            # frame before the wrap
        wrap = np.abs(last - flat[a]).mean(axis=1) / typical
        length = ends - a
        score = wrap / np.sqrt(length / fps)
        k = int(np.argmin(score))
        if score[k] < best_score:
            best_score = float(score[k])
            best = (a, int(ends[k]), float(wrap[k]))
    return best


def close_loop(frames, n_blend):
    """Blend the last n frames toward the first (premultiplied), so the wrap is a dissolve, not a cut."""
    if n_blend <= 0 or len(frames) <= 2 * n_blend:
        return frames
    out = frames.copy()
    f0 = frames[0].astype(np.float32)
    p0 = np.concatenate([f0[..., :3] * f0[..., 3:] / 255, f0[..., 3:]], -1)
    for k in range(1, n_blend + 1):
        i = len(frames) - n_blend - 1 + k
        w = k / (n_blend + 1)
        f = frames[i].astype(np.float32)
        p = (1 - w) * np.concatenate([f[..., :3] * f[..., 3:] / 255, f[..., 3:]], -1) + w * p0
        a = p[..., 3:]
        rgb = np.where(a > 0.5, p[..., :3] * 255 / np.maximum(a, 1e-3), (1 - w) * f[..., :3] + w * f0[..., :3])
        out[i] = np.dstack([np.clip(rgb, 0, 255), np.clip(a, 0, 255)]).round().astype(np.uint8)
    return out


def boomerang(frames):
    """Forward then back: any clip loops. The end frames are not repeated, so the turn is not a freeze."""
    if len(frames) < 3:
        return frames
    return np.concatenate([frames, frames[-2:0:-1]])


def schedule(n, src_fps, max_seconds, out_fps, mode='speed'):
    """Which source frames make the output. Returns (indices, fps, speed).
    speed: the whole window played faster if it is too long. cut: the first max_seconds. Output fps capped at out_fps."""
    dur = n / src_fps
    fps = min(src_fps, out_fps)
    if dur <= max_seconds + 1e-6:
        if fps == src_fps:
            return list(range(n)), src_fps, 1.0
        n_out = max(1, int(round(dur * fps)))
        return [min(n - 1, int(k * n / n_out)) for k in range(n_out)], fps, 1.0
    if mode == 'cut':
        keep = int(round(max_seconds * src_fps))
        return schedule(keep, src_fps, max_seconds, out_fps, 'speed')
    n_out = max(2, int(max_seconds * fps))
    return [min(n - 1, int(k * n / n_out)) for k in range(n_out)], fps, dur / max_seconds


def pick(frames, idx):
    return np.stack([frames[i] for i in idx])
