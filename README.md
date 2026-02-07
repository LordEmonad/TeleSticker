# TeleSticker

A powerful, self-hosted Telegram sticker maker that runs entirely on your machine. Upload images and videos, remove backgrounds with AI, fine-tune stickers in a built-in editor, organize packs with emoji, and push them directly to Telegram — all from a sleek dark-themed web interface.

## Demo

https://github.com/LordEmonad/TeleSticker/raw/master/demo.mp4

## Features

- **Drag-and-drop upload** — batch upload images and videos with instant thumbnail previews
- **AI background removal** — local, offline background removal powered by rembg with adjustable settings (model selection, alpha matting, threshold sliders, live preview)
- **Built-in image editor** — crop, rotate, flip, brightness/contrast/saturation, freehand draw, text overlay, undo/redo history
- **Sticker pack manager** — organize stickers into packs, drag-to-reorder, assign emoji per sticker
- **Direct Telegram upload** — connect your bot token, create or update sticker sets, upload with one click
- **Video & GIF support** — animated GIFs auto-detected and converted through the video pipeline (FFmpeg)
- **Custom emoji mode** — toggle 100x100px output for Telegram custom emoji
- **Format options** — choose WEBP or PNG per sticker, with automatic size optimization under 512KB
- **Real-time progress** — Socket.IO powered processing with per-file status updates
- **Dark & light themes** — glassmorphism UI, dark by default, toggle anytime
- **Keyboard shortcuts** — Ctrl+Z/Y undo/redo, Ctrl+S save, Ctrl+Enter process, and more
- **ZIP download** — batch download all processed stickers in one click

## Quick Start

### Option 1: One-Click Launch
```
start.bat
```
Double-click `start.bat` — it installs dependencies on first run and opens the app in your browser.

### Option 2: Manual Setup
```bash
python install.py      # install dependencies (first time only)
python run.py          # launch the app
```

### Option 3: Direct
```bash
pip install -r requirements.txt
python web_app.py
```

The app opens at **http://localhost:5000**.

## Requirements

- **Python 3.8+**
- **FFmpeg** — required for video/GIF processing (auto-installed on Windows via `install.py`)
- **rembg** (optional) — enables AI background removal. Install via `install.py` or manually with `pip install rembg onnxruntime`

## Usage

1. **Upload** — drag images/videos into the upload zone or click to browse
2. **Edit** (optional) — click the pencil icon on any sticker to open the canvas editor
3. **Remove Background** (optional) — click the wand icon on image stickers to open the background removal panel with adjustable settings
4. **Configure** — select output format (WEBP/PNG) and sticker mode
5. **Process** — hit Process All to convert everything to Telegram-ready specs
6. **Preview** — inspect processed stickers at actual size on a transparency grid
7. **Organize** — switch to the Pack tab to arrange stickers, assign emoji, and reorder by dragging
8. **Upload to Telegram** — enter your bot token and user ID in the Telegram tab, then create your sticker set

## Telegram Bot Setup

1. Message [@BotFather](https://t.me/BotFather) on Telegram and send `/newbot` to create a bot and get your token
2. Get your user ID from [@userinfobot](https://t.me/userinfobot)
3. Paste both into the Telegram tab, validate your token, then create or update your sticker set

## Sticker Specs Reference

| Type | Format | Dimensions | Max Size | Notes |
|------|--------|------------|----------|-------|
| Static sticker | PNG / WEBP | 512px (one side) | 512 KB | — |
| Video sticker | WEBM (VP9) | 512px (one side) | 256 KB | 1–3s, 30fps, no audio |
| Custom emoji | PNG / WEBP | 100 x 100 px | 512 KB | — |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Z` | Undo (editor) |
| `Ctrl+Y` | Redo (editor) |
| `Ctrl+S` | Save pack |
| `Ctrl+Enter` | Process all stickers |
| `Escape` | Close modals |
| `Delete` | Remove selected sticker |
| `V` / `C` / `T` / `D` / `E` | Select / Crop / Text / Draw / Eraser tool |

## License

MIT
