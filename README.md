# EmoSticker

Make Telegram sticker packs on your own computer, from any pictures or videos, and publish them with one button.

Drop files in, see each one exactly as it will look in a chat, fix what needs fixing (crop, outline, background,
trim, loop), and press Publish. Nothing is uploaded anywhere until that button. By Emonad.

## Run it

You need Python 3.9 or newer and, for video and GIF stickers, ffmpeg.

```
git clone https://github.com/LordEmonad/TeleSticker.git EmoSticker
cd EmoSticker
python3 emosticker.py
```

The first run makes a private `.venv`, installs four Python packages and opens `http://127.0.0.1:4747`.
After that it starts in a second. On a Mac you can also double-click `Start EmoSticker.command`; on Windows `start.bat`.

ffmpeg: `brew install ffmpeg` (Mac), `winget install Gyan.FFmpeg` (Windows), `sudo apt install ffmpeg` (Linux).
On Windows `python emosticker.py --get-ffmpeg` downloads a copy into the folder instead.

Options: `--port 5000`, `--no-browser`, `--lan` (use it from your phone on the same Wi-Fi), `--ai` (also install
AI background removal, about 300 MB; the app can install it later from Settings too).

## What it does

**One workspace.** The grid is your pack. Drop files anywhere, paste from the clipboard (⌘V), paste a link, or drop
a whole folder. Every file is rendered to Telegram's exact spec the moment it lands, and again after every edit, so
there is never a "process" step: a green dot means the file on disk is accepted by Telegram as it is.

**The inspector** shows the selected sticker in a light or dark chat bubble at chat size or 1:1, with the facts
Telegram checks: size, bytes against the limit, length, frame rate, transparency.

- **Look**: Fit (one side 512, the whole picture), Square (padded), Fill (cropped about a focus point you drag), a
  crop box, breathing room, rotate and flip, an outline in any colour, a drop shadow, WebP or PNG, automatic removal
  of black bars.
- **Background**: a colour key that needs no model (tap the colour on the picture, or let it read the border):
  green screens, flat backgrounds and white cards, on stills and on video; tolerance, softness, edge shrink, feather,
  despill. Or an AI cut-out (rembg) for photos, installed from inside the app.
- **Motion** (video and GIF): a trim slider over a filmstrip; when the trim is longer than Telegram's 3 seconds,
  speed it up, cut it, or **Find loop** (the stretch that wraps round best); Boomerang (forward then back); blend
  the loop point; reverse; 30/24/20/15 fps.
- **Emoji & tags**: up to 20 emoji per sticker with a searchable picker, and search keywords.

**The engine.** Video is VP9 WebM with alpha, two-pass, at the best quality that fits under 256 KB (a secant search
on CRF, usually three encodes), bt601-tagged, no audio, no metadata, then read back with libvpx to confirm the alpha
and the numbers. Stills are lossless WebP when that fits, otherwise the highest quality that does. Alpha WebM, GIF,
APNG, animated WebP, MOV with alpha, HEIC and AVIF (with `pillow-heif`) all come in.

**Publishing.** Connect a bot once (the token stays in `data/settings.json` on your computer). Telegram needs to
know which account owns the set: open your bot, press Start, and EmoSticker picks your account up from that
message. Then Publish creates the set, or, if it exists, adds what is new, replaces what you re-edited, fixes the
order and the title. Manage set shows what Telegram has, removes stickers, sets the set icon, deletes the set.
Custom emoji sets (100×100) are a switch on the pack.

**Packs and exports.** Several packs, move stickers between them, copy a look from one sticker and paste it on many,
bulk emoji. Export the pack as a ZIP for Telegram, or re-encoded for WhatsApp, Discord or Signal.

**Everything stays.** `data/library.json` and `data/media/` hold your stickers, edits and packs; close the app and
open it a week later and it is all there.

## Telegram's rules, as enforced

| | Static | Video | Custom emoji |
|---|---|---|---|
| Format | WebP or PNG | WebM, VP9, no audio | same, 100×100 |
| Size | one side exactly 512 px, the other ≤ 512 | same | exactly 100×100 |
| Bytes | ≤ 512 KB | ≤ 256 KB | same |
| Time | | ≤ 3 s, ≤ 30 fps, looped | same |
| Per set | 120 | 120 | 200 |

Set names are letters, digits and underscores, start with a letter, and end in `_by_<yourbot>`; EmoSticker builds
them from the short name you type.

## Development

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m pytest tests -q
```

`server/` is the Flask app (`media/` holds the engine: probe, frames, key, transform, loop, encode), `web/` is the
page (plain ES modules, no build step). Set `EMOSTICKER_DATA` to keep the library somewhere else.

## Licence

MIT.
