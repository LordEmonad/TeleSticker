"""From a sticker's source and its edit settings to the files the platforms accept.

A sticker record:
  id, name, source{path, kind, width, height, duration, fps, alpha, ...}, emoji[], keywords[], edit{...},
  out{status, file, preview, kind, width, height, bytes, duration, fps, crf, alpha, ready, reasons[], ...}

edit (every field optional, the defaults make the file the platform takes):
  rotate 0|90|180|270, flip_h, flip_v
  crop [x, y, w, h] (fractions of the source after rotate/flip)      trim_content: bool
  fit 'fit'|'square'|'fill', focus [x, y], margin 0..0.3
  bg {mode: 'none'|'key'|'ai', color [r,g,b]|null, tolerance, softness, despill, erode, feather, keep_inside,
      model, matting}
  outline {width, color [r,g,b], opacity}, shadow {blur, offset [x,y], opacity}
  video: start, end (seconds of the source), fit_time 'speed'|'cut'|'loop'  (loop = auto-find the window),
         boomerang, blend (frames crossfaded at the wrap), fps 30|24|20|15, reverse
  format 'webp'|'png' (stills)
"""
import logging
import os
import shutil
import sys
import time

import numpy as np
from PIL import Image

from . import events, library
from .config import TARGETS, TG
from .media import encode, key, loop, transform
from .media.frames import filmstrip, load_frames, load_image
from .media.probe import probe

log = logging.getLogger('emosticker.render')


def target_for(sticker, pack_type='regular', target='telegram'):
    if target == 'telegram' and pack_type == 'custom_emoji':
        target = 'telegram_emoji'
    return TARGETS[target], target


# ---- the frame pipeline, shared by preview, final and exports -------------------------------------------

def _source_frames(st, edit, spec, is_video, for_preview=False):
    """Decode the chosen window of the source at a working size a little above the target (crop needs room)."""
    src = st['source']
    side = max(spec['side'] * 2, 768) if spec['side'] <= 320 else spec['side'] * 2
    side = min(side, 1024)
    if not is_video:
        return load_image(src['path'], side)[None], 1.0
    start = float(edit.get('start') or 0.0)
    end = edit.get('end')
    end = float(end) if end not in (None, '', 0) else None
    want_fps = float(edit.get('fps') or spec.get('fps', 30))
    frames, fps = load_frames(src['path'], src, side, start, end, fps=min(want_fps, src.get('fps') or want_fps) if src.get('fps') else want_fps)
    return frames, fps


def _look(frames, edit, spec, preview_only=False):
    """Geometry and looks, in the order a person expects: rotate, crop, background, trim, outline, shadow, fit."""
    if edit.get('bars', True) and not edit.get('crop'):
        box = transform.bars_box(frames)
        if box:
            frames = transform.crop(frames, box)
    frames = transform.rotate_flip(frames, int(edit.get('rotate') or 0), bool(edit.get('flip_h')), bool(edit.get('flip_v')))
    if edit.get('crop'):
        frames = transform.crop_rel(frames, edit['crop'])
    bg = edit.get('bg') or {}
    key_color = None
    if bg.get('mode') == 'key':
        frames, key_color = key.apply_key_frames(frames, bg)
    elif bg.get('mode') == 'ai':
        from .media import rembg_bridge
        if rembg_bridge.available():
            frames = rembg_bridge.remove_frames(frames, model=bg.get('model') or 'isnet-general-use',
                                                matting=bg.get('matting', True), fg=bg.get('fg', 240),
                                                bg=bg.get('bgt', 10), erode=bg.get('erode_ai', 10))
    if edit.get('trim_content', True) and (bg.get('mode') in ('key', 'ai') or edit.get('trim_content') is True):
        frames = transform.trim_to_content(frames)
    ol = edit.get('outline') or {}
    if ol.get('width'):
        # outline width is given in output pixels; frames are at working size, so scale it
        scale = max(frames.shape[1], frames.shape[2]) / spec['side']
        frames = transform.outline(frames, max(1, round(float(ol['width']) * scale)),
                                   tuple(ol.get('color') or (255, 255, 255)), float(ol.get('opacity', 1.0)))
    sh = edit.get('shadow') or {}
    if sh.get('opacity'):
        scale = max(frames.shape[1], frames.shape[2]) / spec['side']
        off = sh.get('offset') or [0, 4]
        frames = transform.shadow(frames, float(sh.get('blur', 6)) * scale,
                                  (round(off[0] * scale), round(off[1] * scale)), float(sh['opacity']))
    mode = edit.get('fit') or 'fit'
    if spec.get('square'):
        mode = 'square' if mode != 'fill' else 'fill'
    focus = edit.get('focus') or [0.5, 0.5]
    frames = transform.fit(frames, spec['side'], mode, (float(focus[0]), float(focus[1])), float(edit.get('margin') or 0))
    frames = transform.exact_side(frames, spec['side']) if not spec.get('square') else frames
    return frames, key_color


def _time(frames, fps, edit, spec):
    """Trim/loop/speed to the platform's seconds. Returns frames, fps, info."""
    info = {}
    if edit.get('reverse'):
        frames = frames[::-1]
    max_s = float(spec.get('seconds', 3.0))
    want_fps = float(edit.get('fps') or spec.get('fps', 30))
    mode = edit.get('fit_time') or 'speed'
    if mode == 'loop':
        a, b, seam = loop.find_loop(frames, fps, max_s)
        frames = frames[a:b]
        info['loop_window'] = [round(a / fps, 3), round(b / fps, 3)]
        info['seam_found'] = round(seam, 2)
    if edit.get('boomerang'):
        frames = loop.boomerang(frames)
    idx, out_fps, speed = loop.schedule(len(frames), fps, max_s, want_fps, 'cut' if mode == 'cut' else 'speed')
    frames = loop.pick(frames, idx)
    info['speed'] = round(speed, 2)
    blend = int(edit.get('blend') or 0)
    if blend:
        frames = loop.close_loop(frames, min(blend, len(frames) // 3))
    info['seam'] = round(loop.seam_ratio(frames), 2)
    return frames, out_fps, info


def pipeline(st, edit, spec, is_video):
    frames, fps = _source_frames(st, edit, spec, is_video)
    frames, key_color = _look(frames, edit, spec)
    info = {'key_color': key_color}
    if is_video:
        frames, fps, tinfo = _time(frames, fps, edit, spec)
        info.update(tinfo)
    frames = transform.even(frames) if is_video else frames
    return frames, fps, info


# ---- rendering a sticker ---------------------------------------------------------------------------------

def render(sid, final=True):
    """Make the deliverable for the current pack target and save what it is. Emits 'sticker' events."""
    st = library.get_sticker(sid)
    if not st:
        return
    pack = library.current_pack()
    spec_all, tname = target_for(st, pack.get('type', 'regular'))
    is_video = st['source']['kind'] == 'video'
    spec = spec_all['video' if is_video else 'static']
    edit = st.get('edit') or {}
    d = library.media_dir(sid)
    t0 = time.time()
    library.update_sticker(sid, out={'status': 'rendering'})
    events.emit('sticker', {'id': sid, 'out': {'status': 'rendering'}})
    try:
        frames, fps, info = pipeline(st, edit, spec, is_video)
        out = dict(info)
        gen = int(time.time() * 1000)
        if is_video:
            path = str(d / 'out.webm')
            tmp = str(d / 'out.tmp.webm')
            if final:
                r = encode.encode_webm(frames, fps, tmp, spec['bytes'])
            else:
                r = dict(crf=32, bytes=encode.encode_webm_once(frames, fps, tmp, 32, two_pass=False, speed=4), tries=1)
            os.replace(tmp, path)
            v = encode.verify_webm(path)
            out.update(kind='video', file='out.webm', bytes=v['bytes'], width=v['width'], height=v['height'],
                       fps=round(v['fps'], 3), duration=round(v['duration'], 3), crf=r['crf'], alpha=v['alpha'],
                       audio=v['audio'], frames=len(frames), tries=r['tries'])
            reasons = []
            if max(v['width'], v['height']) != spec['side'] or (spec.get('square') and min(v['width'], v['height']) != spec['side']):
                reasons.append('size')
            if v['duration'] > spec['seconds'] + 0.05:
                reasons.append('too long')
            if v['bytes'] > spec['bytes']:
                reasons.append('too big')
            if v['fps'] > spec['fps'] + 0.01:
                reasons.append('fps')
            if v['audio']:
                reasons.append('audio')
            out['ready'] = not reasons and final
            out['reasons'] = reasons
            Image.fromarray(frames[0]).save(d / 'poster.png')
            out['poster'] = 'poster.png'
            if final and sys.platform == 'darwin':
                # Safari cannot play VP9 with alpha: an HEVC-alpha twin, preview only, never published
                if encode.encode_preview_mp4(frames, fps, str(d / 'preview.mp4')):
                    out['preview_mp4'] = 'preview.mp4'
        else:
            fmt = edit.get('format') or spec['fmt']
            if fmt not in ('webp', 'png'):
                fmt = spec['fmt']
            path = str(d / f'out.{fmt}')
            for old in ('out.webp', 'out.png'):
                if old != f'out.{fmt}' and (d / old).exists():
                    os.remove(d / old)
            r = encode.encode_still(frames[0], path, fmt, spec['bytes'])
            v = encode.verify_still(path)
            out.update(kind='image', file=f'out.{fmt}', bytes=v['bytes'], width=v['width'], height=v['height'],
                       alpha=v['alpha'], lossless=r.get('lossless', False), quality=r.get('quality'), frames=1)
            reasons = []
            if max(v['width'], v['height']) != spec['side'] or (spec.get('square') and min(v['width'], v['height']) != spec['side']):
                reasons.append('size')
            if v['bytes'] > spec['bytes']:
                reasons.append('too big')
            out['ready'] = not reasons
            out['reasons'] = reasons
        out.update(status='done', final=final, gen=gen, target=tname, took=round(time.time() - t0, 2),
                   limit=spec['bytes'], side=spec['side'])
        library.update_sticker(sid, out=out)
        events.emit('sticker', {'id': sid, 'out': out})
    except Exception as e:
        log.exception('render failed for %s', sid)
        out = dict(status='error', error=str(e)[-300:], ready=False, gen=int(time.time() * 1000))
        library.update_sticker(sid, out=out)
        events.emit('sticker', {'id': sid, 'out': out})


def schedule_render(sid, final=True):
    events.schedule(f'render:{sid}', lambda: render(sid, final=final))


# ---- intake ------------------------------------------------------------------------------------------

def intake(path, name):
    """Probe a new file, make its thumbnail and filmstrip, add it to the library and queue its first render."""
    try:
        info = probe(path)
        if not info or info['width'] < 1 or info['height'] < 1:
            raise ValueError('no picture')
        # decode one frame now: a file that cannot be read is refused here, not shown as a broken sticker
        fr, _ = load_frames(path, info, 256, 0, min(0.2, info['duration'] or 0.2) if info['kind'] == 'video' else None, fps=5, max_frames=2)
    except Exception as e:
        log.info('refused %s: %s', name, str(e)[-200:])
        raise ValueError('This file could not be read as a picture or a video') from e
    sid = library.new_id()
    d = library.media_dir(sid)
    ext = os.path.splitext(name)[1].lower() or '.bin'
    src_path = d / ('source' + ext)
    shutil.move(path, src_path)   # the upload lands in the system temp folder, often another disk than data/
    info['path'] = str(src_path)
    info['name'] = name
    info['bytes'] = os.path.getsize(src_path)
    Image.fromarray(fr[0]).save(d / 'thumb.png')
    if info['kind'] == 'video':
        try:
            strip = filmstrip(str(src_path), info)
            if strip is not None:
                strip.convert('RGB').save(d / 'strip.jpg', quality=82)
        except Exception as e:
            log.warning('filmstrip failed: %s', e)
    edit = {}
    if info['kind'] == 'video' and (info['duration'] or 0) > TG['video_seconds']:
        edit['fit_time'] = 'loop'      # a long clip: find its best loop by default
    if info['kind'] == 'video' and not info.get('alpha'):
        pass  # the person decides on keying; auto-keying a live video would eat skin tones
    rec = dict(id=sid, name=name, source=info, emoji=[default_emoji(name)], keywords=[], edit=edit,
               out={'status': 'queued'}, created=library.now(), updated=library.now())
    library.add_sticker(rec)
    events.emit('sticker', {'id': sid, 'record': rec})
    schedule_render(sid)
    return rec


_EMOJI_HINTS = [('laugh', '😂'), ('lol', '😂'), ('cry', '😭'), ('sad', '😢'), ('love', '❤️'), ('heart', '❤️'),
                ('fire', '🔥'), ('cool', '😎'), ('angry', '😡'), ('rage', '😡'), ('wow', '😮'), ('shock', '😱'),
                ('think', '🤔'), ('hmm', '🤔'), ('party', '🎉'), ('dance', '💃'), ('sleep', '😴'), ('gm', '☀️'),
                ('gn', '🌙'), ('money', '💸'), ('cash', '💸'), ('pump', '🚀'), ('moon', '🚀'), ('dead', '💀'),
                ('skull', '💀'), ('wave', '👋'), ('hi', '👋'), ('ok', '👌'), ('yes', '👍'), ('no', '👎'),
                ('kiss', '😘'), ('eyes', '👀'), ('clown', '🤡'), ('emo', '🥀'), ('rose', '🥀'), ('cat', '🐱')]


def default_emoji(name):
    low = os.path.splitext(name)[0].lower()
    for k, e in _EMOJI_HINTS:
        if k in low.replace('_', ' ').replace('-', ' ').split() or (len(k) > 3 and k in low):
            return e
    return '🥀'


def export_file(sid, target, out_dir, pack_type='regular'):
    """Render a sticker for another platform (an export), to out_dir. Returns (path, verify dict)."""
    st = library.get_sticker(sid)
    spec_all, tname = target_for(st, pack_type, target)
    is_video = st['source']['kind'] == 'video'
    spec = spec_all['video' if is_video else 'static']
    frames, fps, info = pipeline(st, st.get('edit') or {}, spec, is_video)
    base = safe_name(st['name'])
    if is_video:
        fmt = spec['fmt']
        if fmt == 'webm':
            path = os.path.join(out_dir, base + '.webm')
            encode.encode_webm(transform.even(frames), fps, path, spec['bytes'])
            return path, encode.verify_webm(path)
        if fmt == 'apng':
            path = os.path.join(out_dir, base + '.png')
            encode.encode_apng(frames, fps, path, spec['bytes'])
        elif fmt == 'awebp':
            path = os.path.join(out_dir, base + '.webp')
            encode.encode_awebp(frames, fps, path, spec['bytes'])
        else:
            path = os.path.join(out_dir, base + '.gif')
            encode.encode_gif(frames, fps, path)
        return path, encode.verify_still(path)
    fmt = spec['fmt']
    path = os.path.join(out_dir, f'{base}.{fmt}')
    encode.encode_still(frames[0], path, fmt, spec['bytes'])
    return path, encode.verify_still(path)


def safe_name(name):
    base = os.path.splitext(os.path.basename(name))[0]
    keep = ''.join(c if c.isalnum() or c in '-_ ' else '_' for c in base).strip() or 'sticker'
    return keep[:60]


def preview_pick(sid, x, y):
    """The source colour under a tap on the preview (fractions), for the key picker."""
    st = library.get_sticker(sid)
    frames, _ = _source_frames(st, st.get('edit') or {}, TARGETS['telegram']['static'], st['source']['kind'] == 'video')
    edit = st.get('edit') or {}
    if edit.get('bars', True) and not edit.get('crop'):
        box = transform.bars_box(frames[:1])
        if box:
            frames = transform.crop(frames[:1], box)
    f = transform.rotate_flip(frames[:1], int(edit.get('rotate') or 0), bool(edit.get('flip_h')), bool(edit.get('flip_v')))[0]
    h, w = f.shape[:2]
    px = f[min(h - 1, max(0, int(y * h))), min(w - 1, max(0, int(x * w)))]
    # average a small patch so compressed noise does not pick a stray pixel
    y0, x0 = max(0, int(y * h) - 2), max(0, int(x * w) - 2)
    patch = f[y0:y0 + 5, x0:x0 + 5, :3].reshape(-1, 3)
    return [int(v) for v in np.median(patch, axis=0)] if len(patch) else [int(v) for v in px[:3]]


def source_frame_png(sid, t=0.0):
    """One source frame (after rotate/flip/crop) as PNG bytes, for the editor's picker views."""
    st = library.get_sticker(sid)
    edit = st.get('edit') or {}
    src = st['source']
    if src['kind'] == 'video':
        fr, _ = load_frames(src['path'], src, 512, float(t), float(t) + 0.3, fps=10, max_frames=1)
    else:
        fr = load_image(src['path'], 512)[None]
    if edit.get('bars', True) and not edit.get('crop'):
        box = transform.bars_box(fr)
        if box:
            fr = transform.crop(fr, box)
    fr = transform.rotate_flip(fr, int(edit.get('rotate') or 0), bool(edit.get('flip_h')), bool(edit.get('flip_v')))
    import io
    buf = io.BytesIO()
    Image.fromarray(fr[0]).save(buf, 'PNG')
    return buf.getvalue()
