"""Upload and processing routes."""

import os
import uuid
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from app.config import UPLOAD_FOLDER, OUTPUT_FOLDER
from app.utils import detect_file_type, validate_file, is_animated_gif
from app.services.image_processor import generate_thumbnail, detect_transparency, get_image_info
from app.services.video_processor import generate_video_thumbnail, probe_video
from app.services.job_queue import submit_job, get_job, cancel_job
from app.extensions import socketio

upload_bp = Blueprint('upload', __name__, url_prefix='/api')

# In-memory sticker store (keyed by file_id)
_stickers = {}


def get_sticker(file_id):
    return _stickers.get(file_id)


def get_all_stickers():
    return _stickers


@upload_bp.route('/upload', methods=['POST'])
def upload_files():
    """Upload files without processing — returns metadata + thumbnails."""
    try:
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

        results = []

        for key in request.files:
            files = request.files.getlist(key)
            for file in files:
                if not file.filename:
                    continue

                filename = secure_filename(file.filename)
                valid, warnings = validate_file(filename)
                if not valid:
                    continue

                file_id = str(uuid.uuid4())
                save_name = f'{file_id}_{filename}'
                save_path = os.path.join(UPLOAD_FOLDER, save_name)
                file.save(save_path)

                file_type = detect_file_type(filename)
                file_size = os.path.getsize(save_path)

                # Check if it's an animated GIF
                if file_type == 'image' and filename.lower().endswith('.gif') and is_animated_gif(save_path):
                    file_type = 'animated_gif'

                # Generate thumbnail
                thumb_name = f'{file_id}_thumb.webp'
                thumb_path = os.path.join(UPLOAD_FOLDER, thumb_name)
                thumb_url = None

                info = {}
                has_transparency = False

                if file_type in ('image', 'animated_gif'):
                    if generate_thumbnail(save_path, thumb_path):
                        thumb_url = f'/api/preview/{thumb_name}'
                    info = get_image_info(save_path) or {}
                    has_transparency = detect_transparency(save_path)
                elif file_type == 'video':
                    video_thumb = thumb_path.rsplit('.', 1)[0] + '.jpg'
                    if generate_video_thumbnail(save_path, video_thumb):
                        thumb_name = os.path.basename(video_thumb)
                        thumb_url = f'/api/preview/{thumb_name}'
                    info = probe_video(save_path)

                sticker_data = {
                    'file_id': file_id,
                    'original_filename': filename,
                    'file_type': file_type,
                    'upload_path': save_path,
                    'thumbnail_url': thumb_url,
                    'file_size': file_size,
                    'width': info.get('width', 0),
                    'height': info.get('height', 0),
                    'has_transparency': has_transparency,
                    'warnings': warnings,
                    'output_format': 'webp',
                    'mode': 'sticker',
                    'status': 'uploaded',
                }
                _stickers[file_id] = sticker_data
                results.append(sticker_data)

        if not results:
            return jsonify({'error': 'No valid files uploaded'}), 400

        return jsonify({'files': results})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@upload_bp.route('/process', methods=['POST'])
def process_files():
    """Trigger processing for uploaded files with per-file config."""
    try:
        data = request.get_json()
        file_configs = data.get('files', [])

        if not file_configs:
            return jsonify({'error': 'No files specified'}), 400

        configs = []
        for fc in file_configs:
            file_id = fc.get('file_id')
            sticker = _stickers.get(file_id)
            if not sticker:
                continue

            # Apply per-file overrides
            sticker['output_format'] = fc.get('output_format', sticker.get('output_format', 'webp'))
            sticker['mode'] = fc.get('mode', sticker.get('mode', 'sticker'))

            configs.append({
                'file_id': file_id,
                'upload_path': sticker['upload_path'],
                'file_type': sticker['file_type'],
                'output_format': sticker['output_format'],
                'mode': sticker['mode'],
            })

        if not configs:
            return jsonify({'error': 'No valid files to process'}), 400

        # Get requesting client's SID for targeted emit
        sid = request.args.get('sid') or data.get('sid')
        job_id = submit_job(configs, socketio, sid=sid)

        return jsonify({'job_id': job_id, 'message': f'Processing {len(configs)} files'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@upload_bp.route('/job/<job_id>', methods=['GET'])
def job_status(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(job.to_dict())


@upload_bp.route('/job/<job_id>/cancel', methods=['POST'])
def cancel(job_id):
    if cancel_job(job_id):
        return jsonify({'ok': True})
    return jsonify({'error': 'Job not found'}), 404


@upload_bp.route('/stickers', methods=['GET'])
def list_stickers():
    """Return all uploaded stickers."""
    return jsonify({'stickers': list(_stickers.values())})


@upload_bp.route('/sticker/<file_id>', methods=['DELETE'])
def delete_sticker(file_id):
    """Remove an uploaded sticker."""
    sticker = _stickers.pop(file_id, None)
    if not sticker:
        return jsonify({'error': 'Not found'}), 404
    # Clean up files
    for key in ('upload_path', 'processed_path', 'bg_removed_path'):
        path = sticker.get(key)
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
    return jsonify({'ok': True})
