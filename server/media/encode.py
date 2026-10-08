"""Encoders. Every one searches for the best quality that fits the platform's byte limit, and verify() reads
the file back the way the platform will (libvpx for alpha, Pillow for stills) and reports the facts.

VP9 + alpha WebM (Telegram video stickers): two-pass, constant quality (CRF), bt601 tagged like the pipeline that
made the Emonad pack, no audio, no metadata. The CRF is found by a secant search on log(size): two or three encodes
usually, never more than six.
"""
import glob
import io
import json
import math
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image

from ..config import ffmpeg_bin

FFMPEG = lambda: ffmpeg_bin('ffmpeg')  # noqa: E731
FFPROBE = lambda: ffmpeg_bin('ffprobe')  # noqa: E731
SLACK = 3072  # bytes left under a limit, so a container's rounding never tips a file over


class EncodeError(RuntimeError):
    pass


def _pipe(frames, fps, args, out, pix_in='rgba'):
    h, w = frames[0].shape[:2]
    cmd = [FFMPEG(), '-y', '-v', 'error', '-nostdin', '-f', 'rawvideo', '-pix_fmt', pix_in, '-s', f'{w}x{h}',
           '-framerate', f'{fps:.6f}', '-i', '-'] + args + [out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for f in frames:
            p.stdin.write(f.tobytes())
        p.stdin.close()
    except (BrokenPipeError, OSError):   # ffmpeg quit early: its stderr below says why (Windows raises OSError 22)
        pass
    err = p.stderr.read().decode('utf-8', 'replace')
    if p.wait() != 0:
        raise EncodeError(err.strip()[-500:] or 'ffmpeg failed')


# ---- VP9 WebM with alpha --------------------------------------------------------------------------------

_VF = ('[0:v]scale=out_color_matrix=bt601:out_range=tv:flags=lanczos+accurate_rnd+full_chroma_int,'
       'format=yuva420p[v]')


def _vp9_args(crf, passlog, speed=1):
    return ['-filter_complex', _VF, '-map', '[v]', '-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', str(int(crf)),
            '-deadline', 'good', '-cpu-used', str(speed), '-row-mt', '1', '-threads', '4', '-tile-columns', '1',
            '-passlogfile', passlog, '-colorspace', 'smpte170m', '-color_primaries', 'smpte170m',
            '-color_trc', 'smpte170m', '-color_range', 'tv', '-an', '-sn', '-map_metadata', '-1',
            '-metadata:s:v', 'alpha_mode=1']


def encode_webm_once(frames, fps, out, crf, two_pass=True, speed=1):
    passlog = out + '.pass'
    args = _vp9_args(crf, passlog, speed)
    if two_pass:
        _pipe(frames, fps, args + ['-pass', '1', '-f', 'null'], os.devnull)
        _pipe(frames, fps, args + ['-pass', '2', '-f', 'webm'], out)
    else:
        _pipe(frames, fps, args + ['-f', 'webm'], out)
    for f in glob.glob(passlog + '*'):
        os.remove(f)
    return os.path.getsize(out)


def encode_webm(frames, fps, out, max_bytes, progress=None, fast=False):
    """Best CRF (lowest) that fits under max_bytes. Returns dict(crf, bytes, tries)."""
    limit = max_bytes - SLACK
    tries = []
    tmp = out + '.try.webm'
    speed = 2 if fast else 1

    def attempt(crf):
        crf = int(max(4, min(63, round(crf))))
        for c, s in tries:
            if c == crf:
                return s
        size = encode_webm_once(frames, fps, tmp, crf, two_pass=not fast, speed=speed)
        tries.append((crf, size))
        if progress:
            progress(len(tries), crf, size)
        return size

    # size falls roughly exponentially with CRF. Keep a bracket [lo, hi] of CRFs: everything below lo is known
    # or assumed too big, hi is the best CRF known to fit. Each step guesses by a secant on log(size), clamped
    # inside the bracket; a bracket one wide is the answer.
    lo, hi = 4, 63          # lo: lowest CRF still possible; hi: a CRF that fits (63 assumed)
    lo_fit = None           # (crf, size) best that fits
    crf = 30
    for _ in range(7):
        size = attempt(crf)
        if size <= limit:
            if lo_fit is None or crf < lo_fit[0]:
                lo_fit = (crf, size)
            hi = crf
        else:
            lo = crf + 1
        if hi <= lo:
            break
        fits = sorted(p for p in tries if p[1] <= limit)
        over = sorted(p for p in tries if p[1] > limit)
        if fits and over:
            a, b = over[-1], fits[0]
        elif len(tries) >= 2:
            a, b = sorted(tries)[-2], sorted(tries)[-1]
        else:
            a = b = None
        if a and b and a[0] != b[0] and a[1] != b[1] and a[1] > 0 and b[1] > 0:
            k = (math.log(a[1]) - math.log(b[1])) / (b[0] - a[0])
            if k > 1e-4:
                guess = a[0] + (math.log(a[1]) - math.log(limit * 0.94)) / k
            else:
                guess = lo if fits else hi
        else:
            guess = (lo + hi) / 2 if fits else min(63, crf + 12)
        guess = int(round(guess))
        guess = max(lo, min(hi - 1 if fits else hi, guess))
        if any(c == guess for c, _ in tries):
            guess = guess - 1 if fits and guess - 1 >= lo else guess + 1
            if any(c == guess for c, _ in tries) or guess < lo or guess > hi:
                break
        crf = guess
    if lo_fit is None:
        os.path.exists(tmp) and os.remove(tmp)
        raise EncodeError('cannot fit under the size limit even at the lowest quality')
    # re-encode the winner if the last try was not it
    if tries[-1][0] != lo_fit[0] or not os.path.exists(tmp):
        encode_webm_once(frames, fps, tmp, lo_fit[0], two_pass=not fast, speed=speed)
    os.replace(tmp, out)
    return dict(crf=lo_fit[0], bytes=os.path.getsize(out), tries=len(tries))


# ---- stills ------------------------------------------------------------------------------------------

def encode_still(frame, out, fmt, max_bytes):
    """webp (lossless first, then quality search) or png (optimised, then palette fallback). Returns dict."""
    im = Image.fromarray(frame)
    limit = max_bytes - 512
    if fmt == 'webp':
        buf = io.BytesIO()
        im.save(buf, 'WEBP', lossless=True, quality=100, method=6, exact=False)
        if buf.tell() <= limit:
            open(out, 'wb').write(buf.getvalue())
            return dict(bytes=buf.tell(), lossless=True, quality=100)
        lo, hi, best = 30, 99, None
        while lo <= hi:
            q = (lo + hi) // 2
            buf = io.BytesIO()
            im.save(buf, 'WEBP', quality=q, method=6, alpha_quality=100)
            if buf.tell() <= limit:
                best = (q, buf.getvalue()); lo = q + 1
            else:
                hi = q - 1
        if best is None:
            buf = io.BytesIO(); im.save(buf, 'WEBP', quality=20, method=6); best = (20, buf.getvalue())
        open(out, 'wb').write(best[1])
        return dict(bytes=len(best[1]), lossless=False, quality=best[0])
    # png
    buf = io.BytesIO()
    im.save(buf, 'PNG', optimize=True)
    if buf.tell() <= limit:
        open(out, 'wb').write(buf.getvalue())
        return dict(bytes=buf.tell(), lossless=True)
    for colors in (256, 128, 64):
        q = im.quantize(colors=colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG)
        buf = io.BytesIO(); q.save(buf, 'PNG', optimize=True)
        if buf.tell() <= limit:
            open(out, 'wb').write(buf.getvalue())
            return dict(bytes=buf.tell(), lossless=False, colors=colors)
    open(out, 'wb').write(buf.getvalue())
    return dict(bytes=buf.tell(), lossless=False, colors=64, over=True)


# ---- other animated containers (exports) -------------------------------------------------------------

def thin(frames, fps, new_fps):
    """Drop frames to a lower rate (the export fallbacks: fewer frames, more bytes each)."""
    if new_fps >= fps:
        return frames, fps
    n = max(2, int(round(len(frames) * new_fps / fps)))
    idx = [min(len(frames) - 1, int(k * len(frames) / n)) for k in range(n)]
    return np.stack([frames[i] for i in idx]), new_fps


FALLBACK_FPS = (20, 15, 12, 10, 8)


def encode_apng(frames, fps, out, max_bytes):
    """APNG through ffmpeg (Pillow's writer trips over frames whose changed area moves). True colour first, then a
    palette, then fewer frames per second."""
    limit = max_bytes - 512
    attempts = [(frames, fps, False), (frames, fps, True)]
    for f in FALLBACK_FPS:
        if f < fps:
            attempts.append((thin(frames, fps, f)[0], f, True))
    last = None
    for fr, r, palette in attempts:
        args = ['-f', 'apng', '-plays', '0', '-pred', 'mixed']
        if palette:
            args = ['-filter_complex', 'split[a][b];[a]palettegen=max_colors=255:reserve_transparent=1:stats_mode=diff[p];'
                    '[b][p]paletteuse=alpha_threshold=1:dither=sierra2_4a:diff_mode=rectangle'] + args
        _pipe(fr, r, args, out)
        size = os.path.getsize(out)
        last = dict(bytes=size, fps=r, palette=palette, over=size > limit)
        if size <= limit:
            return last
    return last


def encode_awebp(frames, fps, out, max_bytes):
    """Animated WebP through Pillow. The alpha plane is lossless at alpha_quality 100, which is most of the bytes of a
    cut-out, so the search lowers the picture and the alpha quality together, then the frame rate."""
    limit = max_bytes - 512

    def once(fr, r, q):
        ims = [Image.fromarray(f) for f in fr]
        buf = io.BytesIO()
        ims[0].save(buf, 'WEBP', save_all=True, append_images=ims[1:], duration=int(round(1000 / r)), loop=0,
                    quality=q, alpha_quality=max(40, min(100, q + 10)), method=3, minimize_size=True)
        return buf.getvalue()

    rates = [fps] + [f for f in FALLBACK_FPS if f < fps]
    best = None
    for r in rates:
        fr, r = thin(frames, fps, r)
        lo, hi = 20, 92
        fit = None
        data = once(fr, r, lo)
        if len(data) > limit:
            best = best or (data, lo, r)
            continue
        fit = (data, lo)
        while lo <= hi:
            q = (lo + hi) // 2
            data = once(fr, r, q)
            if len(data) <= limit:
                fit = (data, q); lo = q + 1
            else:
                hi = q - 1
        open(out, 'wb').write(fit[0])
        return dict(bytes=len(fit[0]), quality=fit[1], fps=r, over=False)
    open(out, 'wb').write(best[0])
    return dict(bytes=len(best[0]), quality=best[1], fps=best[2], over=True)


def encode_gif(frames, fps, out):
    fc = ('split[a][b];[a]palettegen=max_colors=255:reserve_transparent=1:stats_mode=diff[p];'
          '[b][p]paletteuse=alpha_threshold=128:dither=sierra2_4a:diff_mode=rectangle')
    _pipe(frames, fps, ['-filter_complex', fc, '-loop', '0', '-f', 'gif'], out)
    return dict(bytes=os.path.getsize(out))


def encode_preview_mp4(frames, fps, out):
    """HEVC with alpha for Safari previews (VideoToolbox on a Mac). Returns False where the encoder is missing."""
    bgra = [np.ascontiguousarray(f[..., [2, 1, 0, 3]]) for f in frames]
    try:
        _pipe(bgra, fps, ['-c:v', 'hevc_videotoolbox', '-allow_sw', '1', '-alpha_quality', '0.75', '-q:v', '60',
                          '-tag:v', 'hvc1', '-movflags', '+faststart', '-an', '-f', 'mp4'], out, pix_in='bgra')
        return True
    except EncodeError:
        return False


# ---- verification ------------------------------------------------------------------------------------

def verify_webm(path):
    pr = json.loads(subprocess.run(
        [FFPROBE(), '-v', 'error', '-show_entries',
         'stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames:stream_tags=alpha_mode:format=duration',
         '-of', 'json', path], capture_output=True, text=True, check=True).stdout)
    v = [s for s in pr['streams'] if s['codec_type'] == 'video'][0]
    audio = any(s['codec_type'] == 'audio' for s in pr['streams'])
    raw = subprocess.run([FFMPEG(), '-v', 'error', '-c:v', 'libvpx-vp9', '-i', path, '-frames:v', '1',
                          '-f', 'rawvideo', '-pix_fmt', 'rgba', '-'], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.uint8).reshape(v['height'], v['width'], 4)[..., 3]
    num, den = map(int, v['r_frame_rate'].split('/'))
    return dict(codec=v['codec_name'], width=v['width'], height=v['height'], fps=num / den,
                duration=float(pr['format']['duration']), audio=audio,
                alpha=bool((a < 255).any()), bytes=os.path.getsize(path), frames=int(v.get('nb_frames') or 0))


def verify_still(path):
    with Image.open(path) as im:
        return dict(format=(im.format or '').lower(), width=im.width, height=im.height,
                    alpha=im.mode in ('RGBA', 'LA', 'P') and ('transparency' in im.info or im.mode != 'P'),
                    bytes=os.path.getsize(path), frames=getattr(im, 'n_frames', 1))
