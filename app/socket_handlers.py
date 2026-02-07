"""Socket.IO event handlers with room-based isolation."""

import logging
from flask import request
from app.extensions import socketio

logger = logging.getLogger('telesticker.socket')


def register_handlers():
    @socketio.on('connect')
    def handle_connect():
        sid = request.sid
        logger.info(f'Client connected: {sid}')
        socketio.emit('connected', {'sid': sid}, to=sid)

    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info(f'Client disconnected: {request.sid}')

    @socketio.on('cancel_job')
    def handle_cancel(data):
        from app.services.job_queue import cancel_job
        job_id = data.get('job_id')
        if job_id:
            cancel_job(job_id)
