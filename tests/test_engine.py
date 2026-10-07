"""The engine against synthetic media: specs are checked on the files themselves, not on our own bookkeeping.

    python -m pytest tests -q     (needs ffmpeg on the PATH for the video tests)
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault('EMOSTICKER_DATA', str(ROOT / 'tests' / '.data'))

from server.media import encode, key, loop, transform  # noqa: E402
from server.media.frames import load_frames, load_image  # noqa: E402
from server.media.probe import probe  # noqa: E402
from server import telegram  # noqa: E402

HAS_FFMPEG = shutil.which('ffmpeg') is not None or os.path.exists('/opt/homebrew/bin/ffmpeg')
needs_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason='ffmpeg not installed')


@pytest.fixture(scope='session')
def media(tmp_path_factory):
    d = tmp_path_factory.mktemp('media')
    # a pink box with a dark centre on green, 800x600
    im = Image.new('RGB', (800, 600), (34, 204, 68))
    px = im.load()
    for y in range(150, 450):
        for x in range(250, 550):
            px[x, y] = (255, 77, 141)
    for y in range(250, 350):
        for x in range(350, 450):
            px[x, y] = (17, 17, 17)
    im.save(d / 'box.png')
    if HAS_FFMPEG:
        ff = shutil.which('ffmpeg') or '/opt/homebrew/bin/ffmpeg'
        subprocess.run([ff, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=0x1fe03a:s=640x360:r=24:d=5',
                        '-f', 'lavfi', '-i', 'color=c=0xff4d8d:s=120x120:r=24:d=5',
                        '-filter_complex', "[0][1]overlay=x='260+150*sin(t*2)':y='120+80*cos(t*3)':eval=frame,format=yuv420p",
                        '-c:v', 'libx264', str(d / 'ball.mp4')], check=True)
    return d


def test_probe_image(media):
    info = probe(media / 'box.png')
    assert info['kind'] == 'image' and info['width'] == 800 and info['height'] == 600 and not info['alpha']


def test_key_removes_green_keeps_subject(media):
    im = load_image(media / 'box.png', 512)
    assert key.border_color(im) == (34, 204, 68)
    out = key.apply_key(im, {'tolerance': 0.18, 'softness': 0.1})
    a = out[..., 3]
    assert (a == 0).mean() > 0.7            # the green is gone
    h, w = a.shape
    assert a[h // 2, w // 2] == 255          # the dark centre stays
    assert a[int(h * 0.3), int(w * 0.35)] == 255   # pink stays


def test_outline_and_fit_sizes():
    f = np.zeros((1, 300, 200, 4), np.uint8)
    f[:, 50:250, 50:150] = (255, 0, 0, 255)
    o = transform.outline(f, 8, (255, 255, 255))
    assert o.shape[1] > 300 and o.shape[2] > 200
    fitted = transform.fit(o, 512, 'fit')
    assert max(fitted.shape[1], fitted.shape[2]) == 512
    sq = transform.fit(o, 512, 'square')
    assert sq.shape[1:3] == (512, 512)
    fill = transform.fit(o, 512, 'fill', (0.5, 0.5))
    assert fill.shape[1:3] == (512, 512)


def test_still_encoders_fit_limits(tmp_path):
    rng = np.random.default_rng(1)
    noisy = rng.integers(0, 255, (512, 512, 4), dtype=np.uint8)   # incompressible: forces the quality search
    noisy[..., 3] = 255
    r = encode.encode_still(noisy, str(tmp_path / 'n.webp'), 'webp', 100 * 1024)
    assert r['bytes'] <= 100 * 1024 and not r['lossless']
    flat = np.zeros((300, 512, 4), np.uint8); flat[..., :3] = 200; flat[..., 3] = 255   # h=300, w=512
    r = encode.encode_still(flat, str(tmp_path / 'f.webp'), 'webp', 512 * 1024)
    assert r['lossless']
    v = encode.verify_still(str(tmp_path / 'f.webp'))
    assert v['width'] == 512 and v['height'] == 300


def test_bars_detection():
    f = np.zeros((2, 360, 640, 4), np.uint8)
    f[..., 3] = 255
    f[:, 45:315, :, :3] = (120, 60, 200)     # picture between black bars
    assert transform.bars_box(f) == (0, 45, 640, 315)
    f[:, :, :, :3] = (120, 60, 200)
    assert transform.bars_box(f) is None


def test_schedule_and_boomerang():
    idx, fps, speed = loop.schedule(120, 24, 3.0, 30)
    assert fps == 24 and len(idx) == 72 and abs(speed - 5 / 3) < 1e-6
    idx, fps, speed = loop.schedule(48, 24, 3.0, 30)
    assert speed == 1.0 and len(idx) == 48
    idx, fps, speed = loop.schedule(240, 60, 3.0, 30)
    assert fps == 30 and len(idx) == 90
    fr = np.zeros((5, 4, 4, 4), np.uint8)
    for i in range(5):
        fr[i, ..., 0] = i
    b = loop.boomerang(fr)
    assert [int(x[0, 0, 0]) for x in b] == [0, 1, 2, 3, 4, 3, 2, 1]


def test_set_names():
    assert telegram.set_name('Emo Pack!', 'EmoBot') == 'Emo_Pack_by_EmoBot'
    assert telegram.set_name('9lives', 'EmoBot') == 'pack_9lives_by_EmoBot'
    assert telegram.set_name('', 'EmoBot') == 'pack_by_EmoBot'
    long = telegram.set_name('a' * 100, 'EmoBot')
    assert len(long) <= 64 and long.endswith('_by_EmoBot')
    assert telegram.check_name('Emo_Pack_by_EmoBot', 'EmoBot') is None
    assert telegram.check_name('Emo__Pack_by_EmoBot', 'EmoBot')
    assert telegram.check_name('Emo_Pack', 'EmoBot')
    assert telegram.valid_token('123456789:AAHeqTuerb571TjKN0XaqPkXyFjpWGtfIIw')
    assert not telegram.valid_token('hello')


@needs_ffmpeg
def test_video_pipeline_meets_telegram_spec(media, tmp_path):
    info = probe(media / 'ball.mp4')
    assert info['kind'] == 'video' and abs(info['duration'] - 5.0) < 0.1
    frames, fps = load_frames(media / 'ball.mp4', info, 512)
    assert frames.shape[1:] == (288, 512, 4) and fps == 24
    keyed, color = key.apply_key_frames(frames, {})
    assert color[1] > 150 and color[0] < 80
    a, b, seam = loop.find_loop(keyed, fps, 3.0)
    assert 0.6 <= (b - a) / fps <= 3.0
    idx, ofps, speed = loop.schedule(b - a, fps, 3.0, 30)
    win = transform.even(transform.fit(loop.pick(keyed[a:b], idx), 512, 'fit'))
    out = str(tmp_path / 'ball.webm')
    r = encode.encode_webm(win, ofps, out, 256 * 1024)
    v = encode.verify_webm(out)
    assert v['codec'] == 'vp9' and max(v['width'], v['height']) == 512 and v['width'] % 2 == 0
    assert v['duration'] <= 3.05 and v['fps'] <= 30 and not v['audio'] and v['alpha']
    assert v['bytes'] <= 256 * 1024 and r['crf'] >= 4


@needs_ffmpeg
def test_webm_search_hits_limit_on_busy_content(tmp_path):
    rng = np.random.default_rng(7)
    frames = rng.integers(0, 255, (30, 256, 256, 4), dtype=np.uint8)   # noise: cannot be small
    frames[..., 3] = 255
    out = str(tmp_path / 'noise.webm')
    r = encode.encode_webm(frames, 30, out, 64 * 1024)
    assert os.path.getsize(out) <= 64 * 1024
    assert r['tries'] <= 7
