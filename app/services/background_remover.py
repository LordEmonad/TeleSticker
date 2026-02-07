"""AI background removal using rembg (lazy-loaded, optional)."""

import os
import io
import base64
import logging

logger = logging.getLogger('telesticker.bg')

_sessions = {}
_available = None

MODELS = ['isnet-general-use', 'u2net', 'silueta']
DEFAULT_MODEL = 'isnet-general-use'


def is_available():
    """Check if rembg is installed."""
    global _available
    if _available is None:
        try:
            import rembg  # noqa: F401
            _available = True
        except Exception:
            _available = False
            logger.info('rembg not available — background removal disabled')
    return _available


def _get_session(model=None):
    """Lazy-load a rembg model session. Caches per model name."""
    model = model or DEFAULT_MODEL
    if model not in _sessions:
        from rembg import new_session
        _sessions[model] = new_session(model)
        logger.info(f'rembg model loaded: {model}')
    return _sessions[model]


def _refine_alpha(result):
    """Refine alpha: only feather the edges, keep solid foreground fully opaque."""
    from PIL import ImageFilter, Image
    import numpy as np

    alpha = result.split()[-1]
    a = np.array(alpha, dtype=np.float32)

    is_edge = (a > 5) & (a < 250)

    blurred = alpha.filter(ImageFilter.GaussianBlur(radius=1))
    b = np.array(blurred, dtype=np.float32)

    out = a.copy()
    out[is_edge] = b[is_edge]
    out[a >= 250] = 255
    out[a <= 5] = 0

    refined = Image.fromarray(out.astype(np.uint8), mode='L')
    result.putalpha(refined)
    return result


def remove_background(input_path, output_path=None, model=None,
                      alpha_matting=True, fg_threshold=270,
                      bg_threshold=20, erode_size=15):
    """Remove background with user-adjustable parameters."""
    if not is_available():
        return None

    from rembg import remove
    from PIL import Image

    try:
        session = _get_session(model)
        img = Image.open(input_path).convert('RGBA')

        result = remove(
            img,
            session=session,
            alpha_matting=alpha_matting,
            alpha_matting_foreground_threshold=fg_threshold,
            alpha_matting_background_threshold=bg_threshold,
            alpha_matting_erode_size=erode_size,
            post_process_mask=True,
        )

        result = _refine_alpha(result)

        if output_path is None:
            base, _ = os.path.splitext(input_path)
            output_path = base + '_nobg.png'

        result.save(output_path, 'PNG')
        return output_path
    except Exception as e:
        logger.error(f'Background removal failed: {e}')
        if alpha_matting:
            logger.info('Retrying without alpha matting...')
            return remove_background(input_path, output_path, model,
                                     alpha_matting=False, fg_threshold=fg_threshold,
                                     bg_threshold=bg_threshold, erode_size=erode_size)
        return None


def remove_background_preview(input_path, model=None,
                              alpha_matting=True, fg_threshold=270,
                              bg_threshold=20, erode_size=15):
    """Remove background and return base64 data URL for preview."""
    if not is_available():
        return None

    from rembg import remove
    from PIL import Image

    try:
        session = _get_session(model)
        img = Image.open(input_path).convert('RGBA')
        preview = img.copy()
        preview.thumbnail((512, 512), Image.LANCZOS)

        try:
            result = remove(
                preview,
                session=session,
                alpha_matting=alpha_matting,
                alpha_matting_foreground_threshold=fg_threshold,
                alpha_matting_background_threshold=bg_threshold,
                alpha_matting_erode_size=erode_size,
                post_process_mask=True,
            )
        except Exception:
            result = remove(preview, session=session, post_process_mask=True)

        result = _refine_alpha(result)

        buf = io.BytesIO()
        result.save(buf, 'PNG')
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f'data:image/png;base64,{b64}'
    except Exception as e:
        logger.error(f'Background removal preview failed: {e}')
        return None


def get_available_models():
    return MODELS
