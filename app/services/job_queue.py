"""Job queue for background file processing."""

import os
import time
import uuid
import logging
import zipfile
from concurrent.futures import ThreadPoolExecutor
from app.config import MAX_WORKERS, OUTPUT_FOLDER
from app.models.job import Job
from app.services.image_processor import resize_image
from app.services.video_processor import convert_video, convert_gif_to_video
from app.utils import is_animated_gif

logger = logging.getLogger('telesticker.jobs')

# Global state
_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
_jobs = {}


def get_job(job_id):
    return _jobs.get(job_id)


def cancel_job(job_id):
    job = _jobs.get(job_id)
    if job:
        job.cancelled = True
        return True
    return False


def submit_job(files_config, socketio, sid=None):
    """Submit a processing job. files_config is a list of dicts with:
    - file_id, upload_path, file_type, output_format, mode
    """
    job_id = str(uuid.uuid4())
    job = Job(job_id=job_id, total_files=len(files_config))
    _jobs[job_id] = job

    def emit(event, data):
        if sid:
            socketio.emit(event, data, to=sid)
        else:
            socketio.emit(event, data)

    def process():
        job.status = 'processing'
        emit('processing_update', {
            'job_id': job_id,
            'status': 'processing',
            'message': f'Starting processing of {job.total_files} files...',
            'progress': 0
        })

        for i, fc in enumerate(files_config):
            if job.cancelled:
                job.status = 'cancelled'
                emit('processing_update', {
                    'job_id': job_id, 'status': 'cancelled',
                    'message': 'Processing cancelled', 'progress': job.progress
                })
                return

            file_id = fc['file_id']
            input_path = fc['upload_path']
            file_type = fc['file_type']
            output_format = fc.get('output_format', 'webp')
            mode = fc.get('mode', 'sticker')
            is_icon = mode == 'icon'
            is_emoji = mode == 'emoji'
            original_name = os.path.basename(input_path)

            emit('processing_update', {
                'job_id': job_id,
                'file_id': file_id,
                'status': 'processing',
                'message': f'Processing {original_name}...',
                'progress': int((i / job.total_files) * 100)
            })

            try:
                ts = int(time.time())
                success = False

                if file_type == 'animated_gif' or (file_type == 'image' and is_animated_gif(input_path)):
                    out_name = f'sticker_{i+1}_{ts}.webm'
                    out_path = os.path.join(OUTPUT_FOLDER, out_name)
                    success = convert_gif_to_video(input_path, out_path, is_icon=is_icon)
                elif file_type == 'video':
                    out_name = f'sticker_{i+1}_{ts}.webm'
                    out_path = os.path.join(OUTPUT_FOLDER, out_name)
                    success = convert_video(input_path, out_path, is_icon=is_icon)
                elif file_type == 'image':
                    ext = output_format if output_format in ('webp', 'png') else 'webp'
                    out_name = f'sticker_{i+1}_{ts}.{ext}'
                    out_path = os.path.join(OUTPUT_FOLDER, out_name)
                    success = resize_image(input_path, out_path, output_format, is_icon=is_icon, is_emoji=is_emoji)

                if success:
                    job.file_results.append({
                        'file_id': file_id,
                        'original': original_name,
                        'processed': out_name,
                        'path': out_path,
                        'size': os.path.getsize(out_path),
                    })
                    emit('file_processed', {
                        'job_id': job_id,
                        'file_id': file_id,
                        'status': 'success',
                        'processed_name': out_name,
                        'size': os.path.getsize(out_path),
                    })
                else:
                    emit('file_processed', {
                        'job_id': job_id,
                        'file_id': file_id,
                        'status': 'error',
                        'message': f'Failed to process {original_name}',
                    })

            except Exception as e:
                logger.error(f'Error processing {original_name}: {e}')
                emit('file_processed', {
                    'job_id': job_id,
                    'file_id': file_id,
                    'status': 'error',
                    'message': str(e),
                })

            job.processed_files = i + 1

        # Create ZIP
        if job.file_results:
            zip_name = f'telegram_stickers_{job_id}.zip'
            zip_path = os.path.join(OUTPUT_FOLDER, zip_name)
            with zipfile.ZipFile(zip_path, 'w') as zf:
                for fr in job.file_results:
                    zf.write(fr['path'], fr['processed'])
            job.zip_path = zip_path
            job.status = 'complete'

            emit('processing_complete', {
                'job_id': job_id,
                'status': 'complete',
                'message': f'Successfully processed {len(job.file_results)} files!',
                'progress': 100,
                'download_url': f'/api/download/{zip_name}',
                'files': job.file_results,
            })
        else:
            job.status = 'error'
            job.error_message = 'No files were successfully processed.'
            emit('processing_complete', {
                'job_id': job_id,
                'status': 'error',
                'message': 'No files were successfully processed.',
                'progress': 100,
            })

    _executor.submit(process)
    return job_id
