#!/usr/bin/env python3
"""TeleSticker v2 — Launcher."""

import os
import sys
import subprocess
import webbrowser
import time
import threading
from pathlib import Path


def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_requirements():
    print("Installing required packages...")
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], check=True)
        print("Packages installed successfully!")
        return True
    except subprocess.CalledProcessError:
        print("Failed to install packages. Please run: pip install -r requirements.txt")
        return False


def open_browser():
    time.sleep(2)
    webbrowser.open('http://localhost:5000')


def main():
    print("TeleSticker v2 — The Ultimate Telegram Sticker Maker")
    print("=" * 55)

    if not Path('web_app.py').exists():
        print("Error: web_app.py not found. Please run from the TeleSticker directory.")
        input("Press Enter to exit...")
        return

    if not check_ffmpeg():
        print("Warning: FFmpeg not found!")
        print("  Video processing requires FFmpeg.")
        print("  Windows: Download from https://ffmpeg.org/download.html")
        print("  macOS: brew install ffmpeg")
        print("  Linux: sudo apt-get install ffmpeg")
        print()

    try:
        import flask
        import flask_socketio
        print("Required packages found!")
    except ImportError:
        if not install_requirements():
            input("Press Enter to exit...")
            return

    print("Starting TeleSticker web server...")
    print("Open your browser at: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    print()

    threading.Thread(target=open_browser, daemon=True).start()

    try:
        from web_app import app, socketio
        socketio.run(app, debug=False, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\nTeleSticker stopped. Thanks for using our app!")
    except Exception as e:
        print(f"Error starting server: {e}")
        input("Press Enter to exit...")


if __name__ == '__main__':
    main()
