"""Video processing service for Telegram sticker conversion."""

import os
import json
import logging
import subprocess
from app.config import (
    MAX_IMAGE_SIZE, MAX_VIDEO_DURATION, MAX_VIDEO_SIZE_KB,
    ICON_SIZE, MAX_ICON_SIZE_KB, VIDEO_FPS, VIDEO_TIMEOUT
)

logger = logging.getLogger('telesticker.video')


def probe_video(filepath):
    """Extract video metadata using ffprobe."""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,duration,nb_frames,codec_name',
            '-show_entries', 'format=duration',
            '-of', 'json',
            filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
        stream = data.get('streams', [{}])[0]
        fmt = data.get('format', {})
        return {
            'width': int(stream.get('width', 0)),
            'height': int(stream.get('height', 0)),
            'duration': float(fmt.get('duration', stream.get('duration', 0))),
            'codec': stream.get('codec_name', ''),
            'frames': int(stream.get('nb_frames', 0)),
        }
    except Exception as e:
        logger.error(f'Video probe failed: {e}')
        return {'width': 1280, 'height': 720, 'duration': 0, 'codec': '', 'frames': 0}


def generate_video_thumbnail(filepath, thumb_path):
    """Extract first frame as thumbnail."""
    try:
        cmd = [
            'ffmpeg', '-y', '-i', filepath,
            '-vframes', '1', '-q:v', '2',
            thumb_path
        ]
        subprocess.run(cmd, capture_output=True, timeout=30)
        return os.path.exists(thumb_path)
    except Exception as e:
        logger.error(f'Video thumbnail failed: {e}')
        return False


def convert_video(input_path, output_path, is_icon=False, progress_callback=None):
    """Convert video to WEBM VP9 for Telegram stickers with timeout."""
    try:
        if not output_path.endswith('.webm'):
            output_path = output_path.rsplit('.', 1)[0] + '.webm'

        target_size = ICON_SIZE if is_icon else MAX_IMAGE_SIZE
        max_size_kb = MAX_ICON_SIZE_KB if is_icon else MAX_VIDEO_SIZE_KB

        info = probe_video(input_path)
        width = info['width'] or 1280
        height = info['height'] or 720

        if is_icon:
            new_width = new_height = ICON_SIZE
        else:
            ratio = target_size / max(width, height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            # Ensure even dimensions for codec
            new_width = new_width + (new_width % 2)
            new_height = new_height + (new_height % 2)

        bitrate = 150 if is_icon else 300

        for attempt in range(5):
            loop_filter = ',loop=0:32767:0' if is_icon else ''
            cmd = [
                'ffmpeg', '-y', '-i', input_path,
                '-t', str(MAX_VIDEO_DURATION),
                '-vf', f'scale={new_width}:{new_height},fps={VIDEO_FPS}{loop_filter}',
                '-c:v', 'libvpx-vp9',
                '-pix_fmt', 'yuva420p',
                '-an',
                '-b:v', f'{bitrate}k',
                '-crf', '30',
                '-deadline', 'good',
                '-auto-alt-ref', '0',
                output_path
            ]

            subprocess.run(cmd, capture_output=True, check=True, timeout=VIDEO_TIMEOUT)

            file_size_kb = os.path.getsize(output_path) / 1024
            if progress_callback:
                progress_callback(attempt + 1, 5)

            if file_size_kb <= max_size_kb:
                return True

            bitrate = int(bitrate * 0.6)

        return False

    except subprocess.TimeoutExpired:
        logger.error(f'Video conversion timed out after {VIDEO_TIMEOUT}s')
        return False
    except Exception as e:
        logger.error(f'Video conversion failed: {e}')
        return False


def convert_gif_to_video(gif_path, output_path, is_icon=False, progress_callback=None):
    """Convert animated GIF to WEBM video sticker."""
    return convert_video(gif_path, output_path, is_icon=is_icon, progress_callback=progress_callback)
