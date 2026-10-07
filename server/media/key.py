"""Background removal that needs no model: a colour key, for green screens and flat backgrounds.

alpha = how far the pixel's colour is from the key colour, in a space where luma counts less than chroma
(a shaded green wall is still green), through a soft threshold; then despill (the key colour's cast on the
edges is pulled toward neutral) and an optional edge erosion for footage with dark fringes.

The key colour is picked by the person (a tap on the picture) or found by looking at the borders: the colour
most of the frame's edge pixels share. Works per frame on video with the same settings, which keeps a loop
consistent. The AI route (rembg) lives in rembg_bridge.py and is used when it is installed and chosen.
"""
import numpy as np

# luma-light weights: Cb/Cr count 1, Y counts 0.35
_W = np.array([0.35, 1.0, 1.0], np.float32)


def to_ycc(rgb):
    rgb = rgb.astype(np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cb = 128 + (b - y) * 0.564
    cr = 128 + (r - y) * 0.713
    return np.stack([y, cb, cr], -1)


def border_color(rgba, band=0.04):
    """The dominant colour on the picture's border (quantised, most common bin), as an (r, g, b) tuple."""
    h, w = rgba.shape[:2]
    b = max(2, int(round(min(h, w) * band)))
    edge = np.concatenate([rgba[:b].reshape(-1, 4), rgba[-b:].reshape(-1, 4),
                           rgba[:, :b].reshape(-1, 4), rgba[:, -b:].reshape(-1, 4)])
    edge = edge[edge[..., 3] > 0][:, :3]
    if len(edge) == 0:
        return (0, 255, 0)
    q = (edge // 16).astype(np.int32)
    keys = q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2]
    vals, counts = np.unique(keys, return_counts=True)
    top = vals[np.argmax(counts)]
    sel = edge[keys == top]
    return tuple(int(x) for x in np.median(sel, axis=0))


def key_alpha(rgb, color, tolerance=0.18, softness=0.10):
    """0..1 alpha from colour distance. tolerance/softness are fractions of the colour space's range."""
    ycc = to_ycc(rgb)
    kc = to_ycc(np.array(color, np.float32)[None, None])[0, 0]
    d = np.sqrt((((ycc - kc) * _W) ** 2).sum(-1)) / (255.0 * np.sqrt(1 + 1 + 0.35 ** 2))
    lo = max(0.0, tolerance - softness / 2)
    hi = tolerance + softness / 2
    a = np.clip((d - lo) / max(1e-6, hi - lo), 0, 1)
    return a * a * (3 - 2 * a)  # smoothstep


def despill(rgb, color, alpha, amount=1.0):
    """Pull the key colour's cast out of the semi-transparent edge (and of spill inside the subject)."""
    rgb = rgb.astype(np.float32)
    c = np.array(color, np.float32)
    dom = int(np.argmax(c))
    others = [i for i in range(3) if i != dom]
    if c[dom] - c[others].mean() < 40:   # not a saturated key (white, grey): nothing to despill
        return rgb
    limit = rgb[..., others].mean(-1)
    excess = np.clip(rgb[..., dom] - limit, 0, None)
    # strongest at the edge, a little inside
    strength = amount * np.clip(1.4 - alpha, 0.25, 1.0)
    rgb[..., dom] -= excess * strength
    # give the removed energy back as grey so edges do not darken
    rgb[..., others[0]] += excess * strength * 0.25
    rgb[..., others[1]] += excess * strength * 0.25
    return np.clip(rgb, 0, 255)


def erode_alpha(alpha, px):
    if px <= 0:
        return alpha
    out = alpha
    for _ in range(int(px)):
        p = np.pad(out, 1, mode='edge')
        out = np.minimum.reduce([p[1:-1, 1:-1], p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]])
    return out


def feather_alpha(alpha, px):
    if px <= 0:
        return alpha
    out = alpha.astype(np.float32)
    for _ in range(int(px)):
        p = np.pad(out, 1, mode='edge')
        out = (p[1:-1, 1:-1] * 4 + p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) / 8
    return out


def apply_key(rgba, settings):
    """rgba uint8 [h, w, 4] -> keyed rgba. settings: color [r,g,b] or None (auto), tolerance, softness, despill,
    erode, feather, keep_inside (holes fully enclosed by the subject stay opaque)."""
    color = settings.get('color') or border_color(rgba)
    a_key = key_alpha(rgba[..., :3], color, float(settings.get('tolerance', 0.18)), float(settings.get('softness', 0.10)))
    a_key = erode_alpha(a_key, int(settings.get('erode', 0)))
    a_key = feather_alpha(a_key, int(settings.get('feather', 0)))
    if settings.get('keep_inside'):
        a_key = np.maximum(a_key, _enclosed(a_key))
    rgb = despill(rgba[..., :3], color, a_key, float(settings.get('despill', 1.0))) if settings.get('despill', 1.0) else rgba[..., :3].astype(np.float32)
    out = np.empty_like(rgba)
    out[..., :3] = np.round(rgb).astype(np.uint8)
    out[..., 3] = np.round(rgba[..., 3].astype(np.float32) * a_key).astype(np.uint8)
    return out


def _enclosed(alpha, thresh=0.5):
    """1 where a transparent region does not touch the border (a hole inside the subject)."""
    bg = alpha < thresh
    h, w = bg.shape
    reach = np.zeros_like(bg)
    reach[0, :] = bg[0, :]; reach[-1, :] = bg[-1, :]; reach[:, 0] = bg[:, 0]; reach[:, -1] = bg[:, -1]
    # flood fill from the border through bg, by repeated dilation (cheap enough at 512px)
    for _ in range(h + w):
        p = np.pad(reach, 1)
        grown = (p[1:-1, 1:-1] | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]) & bg
        if np.array_equal(grown, reach):
            break
        reach = grown
    return (bg & ~reach).astype(np.float32)


def apply_key_frames(frames, settings):
    """The same key on every frame. The auto colour is measured once, on the frames' borders together."""
    s = dict(settings)
    if not s.get('color'):
        sample = frames[:: max(1, len(frames) // 8)]
        s['color'] = border_color(np.concatenate(list(sample), axis=0))
    return np.stack([apply_key(f, s) for f in frames]), s['color']
