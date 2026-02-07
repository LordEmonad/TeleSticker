#!/usr/bin/env python3
"""TeleSticker v2 Auto-Installer."""

import os
import sys
import subprocess
import platform
from pathlib import Path


def print_header():
    print("TeleSticker v2 — Auto-Installer")
    print("=" * 40)
    print("Setting up the ultimate Telegram sticker maker...")
    print()


def check_python():
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"[OK] Python {version.major}.{version.minor} detected")
        return True
    else:
        print(f"[FAIL] Python 3.8+ required. You have {version.major}.{version.minor}")
        return False


def install_core_packages():
    print("Installing core packages...")
    try:
        subprocess.run([
            sys.executable, '-m', 'pip', 'install',
            'Flask==3.0.0', 'Flask-SocketIO==5.3.6', 'Pillow==10.2.0',
            'Werkzeug==3.0.1', 'python-socketio==5.11.0', 'eventlet==0.35.1',
            'httpx==0.27.0',
        ], check=True, capture_output=True)
        print("[OK] Core packages installed!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[FAIL] Failed to install packages: {e}")
        return False


def install_rembg():
    print()
    print("rembg enables AI background removal (optional, ~170MB model download on first use)")
    choice = input("Install rembg for background removal? (y/n): ").strip().lower()
    if choice == 'y':
        print("Installing rembg + onnxruntime (this may take a few minutes)...")
        try:
            subprocess.run([
                sys.executable, '-m', 'pip', 'install',
                'rembg==2.0.50', 'onnxruntime==1.17.0',
            ], check=True, capture_output=True)
            print("[OK] rembg installed! Background removal is now available.")
            return True
        except subprocess.CalledProcessError:
            print("[WARN] Failed to install rembg. Background removal will be disabled.")
            return False
    else:
        print("[INFO] Skipping rembg. Background removal will be disabled.")
        return False


def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("[OK] FFmpeg is installed")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[WARN] FFmpeg not found")
        return False


def install_ffmpeg_windows():
    import urllib.request
    import zipfile

    print("Downloading FFmpeg for Windows...")
    ffmpeg_dir = Path("ffmpeg")
    ffmpeg_dir.mkdir(exist_ok=True)

    url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    zip_path = ffmpeg_dir / "ffmpeg.zip"

    try:
        urllib.request.urlretrieve(url, zip_path)
        print("[OK] FFmpeg downloaded")
        print("Extracting...")
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(ffmpeg_dir)

        for root, dirs, files in os.walk(ffmpeg_dir):
            if 'ffmpeg.exe' in files:
                src = Path(root) / 'ffmpeg.exe'
                dst = Path('ffmpeg.exe')
                src.rename(dst)
                # Also grab ffprobe
                probe = Path(root) / 'ffprobe.exe'
                if probe.exists():
                    probe.rename(Path('ffprobe.exe'))
                print("[OK] FFmpeg installed!")
                break

        zip_path.unlink(missing_ok=True)
        return True
    except Exception as e:
        print(f"[FAIL] FFmpeg install failed: {e}")
        return False


def main():
    print_header()

    if not check_python():
        input("Press Enter to exit...")
        return

    if not install_core_packages():
        input("Press Enter to exit...")
        return

    install_rembg()

    if not check_ffmpeg():
        if platform.system() == "Windows":
            if input("Install FFmpeg automatically? (y/n): ").lower() == 'y':
                install_ffmpeg_windows()
        else:
            print("Please install FFmpeg manually:")
            print("  macOS: brew install ffmpeg")
            print("  Linux: sudo apt-get install ffmpeg")

    # Create required directories
    for d in ['uploads', 'output', 'packs']:
        os.makedirs(d, exist_ok=True)

    print()
    print("Installation complete!")
    print("Run 'python run.py' or double-click 'start.bat' to launch TeleSticker")
    print("The app will open in your browser at http://localhost:5000")
    print()

    if input("Launch TeleSticker now? (y/n): ").lower() == 'y':
        try:
            from run import main as run_main
            run_main()
        except ImportError:
            subprocess.run([sys.executable, 'run.py'])


if __name__ == '__main__':
    main()
