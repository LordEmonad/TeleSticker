"""Geometry and looks on RGBA frames: crop, fit, pad, flip, rotate, outline, shadow, trim-to-content.

All of it is numpy + Pillow and the same function serves a still (n=1) and a clip (n frames), so a video
sticker gets exactly the look its still preview showed.
"""
import numpy as np
from PIL import Image, ImageFilter


def _pil(f):
    return Image.fromarray(f)


def _np(im):
    return np.asarray(im.convert('RGBA'), dtype=np.uint8)


def rotate_flip(frames, rotate=0, flip_h=False, flip_v=False):
    if not (rotate % 360 or flip_h or flip_v):
        return frames
    k = (rotate // 90) % 4
    out = frames
    if k:
        out = np.rot90(out, k=-k, axes=(1, 2))
    if flip_h:
        out = out[:, :, ::-1]
    if flip_v:
        out = out[:, ::-1]
    return np.ascontiguousarray(out)


def bars_box(frames, dark=22, min_frac=0.02):
    """Letterbox/pillarbox: rows and columns at the edges that stay near-black (or near-white) in every frame.
    Returns (x0, y0, x1, y1) of the picture inside them, or None when there are no bars."""
    n, h, w = frames.shape[:3]
    sample = frames[:: max(1, n // 12)]
    rgb = sample[..., :3].astype(np.int16)
    lum = rgb.max(axis=3)              # a bar is dark in every channel
    bright = rgb.min(axis=3)           # or white in every channel
    col_dark = (lum.max(axis=(0, 1)) < dark) | (bright.min(axis=(0, 1)) > 255 - dark)
    row_dark = (lum.max(axis=(0, 2)) < dark) | (bright.min(axis=(0, 2)) > 255 - dark)

    def run(mask):
        a = 0
        while a < len(mask) and mask[a]:
            a += 1
        b = len(mask)
        while b > a and mask[b - 1]:
            b -= 1
        return a, b
    x0, x1 = run(col_dark)
    y0, y1 = run(row_dark)
    if x1 - x0 < w * 0.3 or y1 - y0 < h * 0.3:
        return None                   # the whole picture is dark: not bars
    if x0 < w * min_frac and (w - x1) < w * min_frac and y0 < h * min_frac and (h - y1) < h * min_frac:
        return None
    return x0, y0, x1, y1


def content_box(frames, thresh=8):
    """Bounding box of everything not transparent, across all frames: (x0, y0, x1, y1) or None."""
    a = (frames[..., 3] > thresh).any(axis=0)
    ys, xs = np.where(a)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def crop(frames, box):
    x0, y0, x1, y1 = box
    return np.ascontiguousarray(frames[:, y0:y1, x0:x1])


def crop_rel(frames, rel):
    """rel = [x, y, w, h] as fractions of the picture."""
    n, h, w = frames.shape[:3]
    x0 = int(round(rel[0] * w)); y0 = int(round(rel[1] * h))
    x1 = int(round((rel[0] + rel[2]) * w)); y1 = int(round((rel[1] + rel[3]) * h))
    x0, y0 = max(0, min(w - 2, x0)), max(0, min(h - 2, y0))
    x1, y1 = max(x0 + 2, min(w, x1)), max(y0 + 2, min(h, y1))
    return crop(frames, (x0, y0, x1, y1))


def resize(frames, w, h):
    if frames.shape[2] == w and frames.shape[1] == h:
        return frames
    return np.stack([_np(_pil(f).resize((w, h), Image.LANCZOS)) for f in frames])


def fit(frames, side, mode='fit', focus=(0.5, 0.5), margin=0.0):
    """Bring frames to the platform's canvas.
    fit: long side = side, the other scaled (Telegram's rule). square: fit inside side x side with transparent padding.
    fill: cover side x side, cropped about the focus point. margin: fraction of the canvas left empty round the subject."""
    n, h, w = frames.shape[:3]
    inner = side * (1 - 2 * margin)
    if mode == 'fill':
        r = side / min(w, h)
        nw, nh = max(side, round(w * r)), max(side, round(h * r))
        out = resize(frames, nw, nh)
        x0 = int(round((nw - side) * focus[0])); y0 = int(round((nh - side) * focus[1]))
        return np.ascontiguousarray(out[:, y0:y0 + side, x0:x0 + side])
    r = inner / max(w, h)
    nw, nh = max(1, round(w * r)), max(1, round(h * r))
    out = resize(frames, nw, nh)
    if mode == 'square' or margin > 0:
        cw = ch = side
    else:
        # one side exactly `side`: the scaled long side already is, unless a margin shrank it
        cw, ch = (side, nh) if w >= h else (nw, side)
    if (cw, ch) == (nw, nh):
        return out
    canvas = np.zeros((n, ch, cw, 4), np.uint8)
    x0 = (cw - nw) // 2; y0 = (ch - nh) // 2
    canvas[:, y0:y0 + nh, x0:x0 + nw] = out
    return canvas


def even(frames):
    """VP9 wants even dimensions: pad by one transparent row/column if needed (never crop content)."""
    n, h, w = frames.shape[:3]
    if h % 2 == 0 and w % 2 == 0:
        return frames
    out = np.zeros((n, h + h % 2, w + w % 2, 4), np.uint8)
    out[:, :h, :w] = frames
    return out


def exact_side(frames, side):
    """After rounding, make sure the long side is exactly `side` (Telegram checks it to the pixel)."""
    n, h, w = frames.shape[:3]
    if max(h, w) == side:
        return frames
    r = side / max(h, w)
    return resize(frames, max(1, round(w * r)) if w < h else side, side if h >= w else max(1, round(h * r)))


def _dilate_alpha(alpha, px):
    """Max filter by a disc of radius px (separable approximation: square then corner rounding by a second pass)."""
    if px <= 0:
        return alpha
    im = Image.fromarray(alpha)
    size = 2 * int(px) + 1
    out = im.filter(ImageFilter.MaxFilter(size))
    # soften corners of the square kernel into a disc-ish shape
    out = out.filter(ImageFilter.GaussianBlur(radius=max(0.6, px * 0.35)))
    return np.asarray(out, dtype=np.uint8)


def outline(frames, width, color=(255, 255, 255), opacity=1.0):
    """A sticker border: the alpha dilated by `width` px in `color`, composited under the picture."""
    if width <= 0 or opacity <= 0:
        return frames
    n, h, w = frames.shape[:3]
    pad = int(width) + 2
    out = np.zeros((n, h + 2 * pad, w + 2 * pad, 4), np.uint8)
    col = np.array(color, np.float32)
    for i in range(n):
        f = np.zeros((h + 2 * pad, w + 2 * pad, 4), np.uint8)
        f[pad:pad + h, pad:pad + w] = frames[i]
        a = _dilate_alpha(f[..., 3], width)
        a = np.clip(a.astype(np.float32) * 1.6, 0, 255)  # crisp edge
        edge = np.zeros_like(f)
        edge[..., :3] = col
        edge[..., 3] = np.round(a * opacity).astype(np.uint8)
        out[i] = composite(f, edge)
    return out


def shadow(frames, blur=6, offset=(0, 4), opacity=0.45, color=(0, 0, 0)):
    if opacity <= 0:
        return frames
    n, h, w = frames.shape[:3]
    pad = int(blur * 2 + max(abs(offset[0]), abs(offset[1])) + 2)
    out = np.zeros((n, h + 2 * pad, w + 2 * pad, 4), np.uint8)
    for i in range(n):
        f = np.zeros((h + 2 * pad, w + 2 * pad, 4), np.uint8)
        f[pad:pad + h, pad:pad + w] = frames[i]
        a = Image.fromarray(f[..., 3]).filter(ImageFilter.GaussianBlur(blur))
        a = np.roll(np.asarray(a), (offset[1], offset[0]), axis=(0, 1))
        sh = np.zeros_like(f)
        sh[..., :3] = color
        sh[..., 3] = np.round(a * opacity).astype(np.uint8)
        out[i] = composite(f, sh)
    return out


def composite(top, under):
    """top over under, both straight-alpha RGBA uint8."""
    ta = top[..., 3:4].astype(np.float32) / 255
    ua = under[..., 3:4].astype(np.float32) / 255
    oa = ta + ua * (1 - ta)
    rgb = (top[..., :3] * ta + under[..., :3] * ua * (1 - ta)) / np.maximum(oa, 1e-6)
    out = np.empty_like(top)
    out[..., :3] = np.round(rgb).astype(np.uint8)
    out[..., 3] = np.round(oa[..., 0] * 255).astype(np.uint8)
    return out


def trim_to_content(frames, pad_px=0):
    box = content_box(frames)
    if not box:
        return frames
    n, h, w = frames.shape[:3]
    x0, y0, x1, y1 = box
    x0, y0 = max(0, x0 - pad_px), max(0, y0 - pad_px)
    x1, y1 = min(w, x1 + pad_px), min(h, y1 + pad_px)
    return crop(frames, (x0, y0, x1, y1))


def premultiply_edges(frames):
    """Colour fully transparent pixels like their nearest opaque neighbours so lossy encoders do not ring dark fringes."""
    out = frames.copy()
    for i in range(len(out)):
        f = out[i]
        a = f[..., 3]
        if (a == 0).any() and (a > 0).any():
            im = Image.fromarray(f)
            # a cheap bleed: blur the premultiplied colour and use it where alpha is zero
            rgb = np.asarray(im.convert('RGB'), np.float32)
            af = a.astype(np.float32) / 255
            pm = rgb * af[..., None]
            k = 7
            num = np.asarray(Image.fromarray(np.clip(pm, 0, 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(k)), np.float32)
            den = np.asarray(Image.fromarray((af * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(k)), np.float32) / 255
            fill = num / np.maximum(den[..., None], 1e-3)
            m = a == 0
            f[..., :3][m] = np.clip(fill[m], 0, 255).astype(np.uint8)
    return out
