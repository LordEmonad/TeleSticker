"""Editor routes — background removal, crop, etc."""

import os
from flask import Blueprint, request, jsonify
from app.config import UPLOAD_FOLDER
from app.services.background_remover import (
    is_available, remove_background, remove_background_preview, get_available_models
)
from app.routes.upload import get_sticker

editor_bp = Blueprint('editor', __name__, url_prefix='/api/editor')


@editor_bp.route('/remove-bg', methods=['POST'])
def remove_bg():
    """Remove background from a sticker image with adjustable settings."""
    if not is_available():
        return jsonify({'error': 'Background removal is not available. Install rembg to enable.'}), 503

    data = request.get_json()
    file_id = data.get('file_id')
    sticker = get_sticker(file_id)
    if not sticker:
        return jsonify({'error': 'Sticker not found'}), 404

    if sticker['file_type'] != 'image':
        return jsonify({'error': 'Background removal only works on images'}), 400

    # User-adjustable settings
    model = data.get('model', 'isnet-general-use')
    alpha_matting = data.get('alpha_matting', True)
    fg_threshold = int(data.get('fg_threshold', 270))
    bg_threshold = int(data.get('bg_threshold', 20))
    erode_size = int(data.get('erode_size', 15))

    input_path = sticker['upload_path']
    output_path = os.path.join(UPLOAD_FOLDER, f'{file_id}_nobg.png')

    result = remove_background(
        input_path, output_path,
        model=model,
        alpha_matting=alpha_matting,
        fg_threshold=fg_threshold,
        bg_threshold=bg_threshold,
        erode_size=erode_size,
    )
    if result:
        sticker['bg_removed_path'] = result
        sticker['use_bg_removed'] = True
        thumb_name = f'{file_id}_nobg.png'
        return jsonify({
            'ok': True,
            'preview_url': f'/api/preview/{thumb_name}',
        })

    return jsonify({'error': 'Background removal failed'}), 500


@editor_bp.route('/remove-bg/preview', methods=['POST'])
def remove_bg_preview():
    """Get a base64 preview of background removal with adjustable settings."""
    if not is_available():
        return jsonify({'error': 'Background removal not available'}), 503

    data = request.get_json()
    file_id = data.get('file_id')
    sticker = get_sticker(file_id)
    if not sticker:
        return jsonify({'error': 'Sticker not found'}), 404

    model = data.get('model', 'isnet-general-use')
    alpha_matting = data.get('alpha_matting', True)
    fg_threshold = int(data.get('fg_threshold', 270))
    bg_threshold = int(data.get('bg_threshold', 20))
    erode_size = int(data.get('erode_size', 15))

    preview = remove_background_preview(
        sticker['upload_path'],
        model=model,
        alpha_matting=alpha_matting,
        fg_threshold=fg_threshold,
        bg_threshold=bg_threshold,
        erode_size=erode_size,
    )
    if preview:
        return jsonify({'ok': True, 'data_url': preview})

    return jsonify({'error': 'Preview generation failed'}), 500


@editor_bp.route('/bg-status', methods=['GET'])
def bg_status():
    """Check if background removal is available and return model list."""
    available = is_available()
    return jsonify({
        'available': available,
        'models': get_available_models() if available else [],
    })
