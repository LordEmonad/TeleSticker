"""Image processing service for Telegram sticker conversion."""

import io
import os
import logging
from PIL import Image
from app.config import MAX_IMAGE_SIZE, MAX_IMAGE_SIZE_KB, ICON_SIZE, CUSTOM_EMOJI_SIZE

logger = logging.getLogger('telesticker.image')


def detect_transparency(filepath):
    """Check if an image has transparency."""
    try:
        with Image.open(filepath) as img:
            if img.mode == 'RGBA':
                extrema = img.getextrema()
                if len(extrema) >= 4 and extrema[3][0] < 255:
                    return True
            elif img.mode == 'PA':
                return True
            elif img.info.get('transparency') is not None:
                return True
        return False
    except Exception:
        return False


def generate_thumbnail(filepath, thumb_path, size=(200, 200)):
    """Generate a thumbnail for preview."""
    try:
        with Image.open(filepath) as img:
            img.thumbnail(size, Image.LANCZOS)
            if img.mode == 'RGBA':
                img.save(thumb_path, 'PNG')
            else:
                img.save(thumb_path, 'WEBP', quality=80)
        return True
    except Exception as e:
        logger.error(f'Thumbnail generation failed: {e}')
        return False


def estimate_output_size(img, fmt='webp', quality=95):
    """Estimate output file size without writing to disk."""
    buf = io.BytesIO()
    if fmt == 'webp':
        img.save(buf, 'WEBP', quality=quality)
    else:
        img.save(buf, 'PNG')
    return buf.tell()


def resize_image(input_path, output_path, output_format='webp', is_icon=False, is_emoji=False):
    """Resize image to Telegram sticker specs with quality iteration."""
    try:
        img = Image.open(input_path)

        # Preserve RGBA for transparency
        if img.mode not in ('RGBA', 'RGB'):
            img = img.convert('RGBA')

        # Determine target size
        if is_icon:
            target = ICON_SIZE
        elif is_emoji:
            target = CUSTOM_EMOJI_SIZE
        else:
            target = MAX_IMAGE_SIZE

        width, height = img.size

        if is_icon or is_emoji:
            # Square resize for icons/emoji
            new_width = new_height = target
        else:
            # Scale so the longest side = target
            ratio = target / max(width, height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)

        img = img.resize((new_width, new_height), Image.LANCZOS)

        max_kb = MAX_IMAGE_SIZE_KB
        if is_icon:
            max_kb = 32

        if output_format == 'webp':
            # Iterative quality reduction to meet size limit
            quality = 95
            for _ in range(10):
                size = estimate_output_size(img, 'webp', quality)
                if size <= max_kb * 1024:
                    img.save(output_path, 'WEBP', quality=quality)
                    return True
                quality = max(10, quality - 10)
            # Last resort
            img.save(output_path, 'WEBP', quality=quality)
        else:
            img.save(output_path, 'PNG')

        return True
    except Exception as e:
        logger.error(f'Image resize failed: {e}')
        return False


def get_image_info(filepath):
    """Get image dimensions and basic info."""
    try:
        with Image.open(filepath) as img:
            return {
                'width': img.width,
                'height': img.height,
                'mode': img.mode,
                'format': img.format,
            }
    except Exception:
        return None
