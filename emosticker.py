#!/usr/bin/env python3
"""EmoSticker: run this. It makes itself a virtual environment on first run, installs what it needs, checks for
ffmpeg, starts the app and opens your browser.

    python3 emosticker.py              start (http://127.0.0.1:4747)
    python3 emosticker.py --port 5000  another port
    python3 emosticker.py --no-browser
    python3 emosticker.py --ai         also install AI background removal (rembg, ~300 MB)
    python3 emosticker.py --lan        reachable from your phone on the same Wi-Fi
"""
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / '.venv'
REQ = ROOT / 'requirements.txt'
MIN_PY = (3, 9)


def venv_python():
    return VENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def in_venv():
    # sys.prefix is the venv's own folder when running inside it; sys.executable may be a symlink to the system python
    try:
        return Path(sys.prefix).resolve() == VENV.resolve()
    except Exception:
        return False


def bootstrap():
    if sys.version_info < MIN_PY:
        sys.exit(f'EmoSticker needs Python {MIN_PY[0]}.{MIN_PY[1]} or newer (you have {platform.python_version()}).')
    if in_venv():
        return
    if not venv_python().exists():
        print('First run: making a private Python environment in .venv (one time)...')
        import venv
        venv.EnvBuilder(with_pip=True, clear=False, symlinks=os.name != 'nt').create(VENV)
    stamp = VENV / 'requirements.stamp'
    want = REQ.read_text() if REQ.exists() else ''
    if not stamp.exists() or stamp.read_text() != want:
        print('Installing dependencies...')
        r = subprocess.run([str(venv_python()), '-m', 'pip', 'install', '--disable-pip-version-check', '-q', '-r', str(REQ)])
        if r.returncode != 0:
            sys.exit('pip could not install the requirements. Check your internet connection and run again.')
        stamp.write_text(want)
    if '--ai' in sys.argv:
        print('Installing AI background removal (rembg)...')
        subprocess.run([str(venv_python()), '-m', 'pip', 'install', '--disable-pip-version-check', '-q', 'rembg>=2.0.60', 'onnxruntime>=1.17'])
    args = [str(venv_python()), str(ROOT / 'emosticker.py')] + [a for a in sys.argv[1:] if a != '--ai']
    if os.name == 'nt':
        # execv does not replace the process on Windows: run the venv python and wait for it, so Ctrl+C and the
        # console window belong to the server
        try:
            sys.exit(subprocess.run(args).returncode)
        except KeyboardInterrupt:
            sys.exit(0)
    os.execv(args[0], args)


def ffmpeg_hint():
    from server.config import ffmpeg_bin
    ok = all(shutil.which(ffmpeg_bin(n)) or os.path.exists(ffmpeg_bin(n)) for n in ('ffmpeg', 'ffprobe'))
    if ok:
        return True
    print('\nffmpeg was not found. Pictures work without it; video and GIF stickers need it.')
    if sys.platform == 'darwin':
        print('  Install it with Homebrew:   brew install ffmpeg')
    elif os.name == 'nt':
        print('  Install it with winget:     winget install Gyan.FFmpeg     (then open a new terminal)')
        print('  or run:  python emosticker.py --get-ffmpeg   to download a copy into this folder')
    else:
        print('  Debian/Ubuntu: sudo apt install ffmpeg      Fedora: sudo dnf install ffmpeg')
    print()
    return False


def get_ffmpeg_windows():
    import urllib.request
    import zipfile
    url = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'
    dst = ROOT / 'bin'
    dst.mkdir(exist_ok=True)
    zpath = dst / 'ffmpeg.zip'
    print('Downloading ffmpeg (about 90 MB)...')
    urllib.request.urlretrieve(url, zpath)
    with zipfile.ZipFile(zpath) as z:
        for m in z.namelist():
            if m.endswith(('bin/ffmpeg.exe', 'bin/ffprobe.exe')):
                (dst / Path(m).name).write_bytes(z.read(m))
    zpath.unlink()
    print('ffmpeg is in', dst)


def main():
    if '--get-ffmpeg' in sys.argv:
        if os.name != 'nt':
            sys.exit('--get-ffmpeg is for Windows; on a Mac use: brew install ffmpeg')
        get_ffmpeg_windows()
        return
    bootstrap()
    sys.path.insert(0, str(ROOT))
    import logging
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s', datefmt='%H:%M:%S')
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    from server import config
    from server.app import create_app
    port = config.PORT
    host = '0.0.0.0' if '--lan' in sys.argv else config.HOST
    if '--port' in sys.argv:
        port = int(sys.argv[sys.argv.index('--port') + 1])
    ffmpeg_hint()
    app = create_app()
    url = f'http://127.0.0.1:{port}'
    print(f'\n  EmoSticker is running at {url}\n  (Ctrl+C stops it; your stickers stay in {config.DATA_DIR})\n')
    if '--lan' in sys.argv:
        try:
            import socket
            ip = socket.gethostbyname(socket.gethostname())
            print(f'  On your phone: http://{ip}:{port}\n')
        except Exception:
            pass
    if '--no-browser' not in sys.argv:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        app.run(host=host, port=port, threaded=True, debug=False, use_reloader=False)
    except OSError as e:
        if 'Address already in use' in str(e) or getattr(e, 'errno', None) in (48, 98):
            sys.exit(f'Port {port} is taken (another EmoSticker open?). Try: python3 emosticker.py --port {port + 1}')
        raise


if __name__ == '__main__':
    main()
