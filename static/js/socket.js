/* TeleSticker v2 — Socket.IO connection */

const Socket = {
    _socket: null,

    init() {
        this._socket = io();

        this._socket.on('connect', () => {
            console.log('Socket connected');
        });

        this._socket.on('connected', (data) => {
            AppState.set('sid', data.sid);
        });

        this._socket.on('disconnect', () => {
            console.log('Socket disconnected');
        });

        this._socket.on('processing_update', (data) => {
            if (data.job_id === AppState.get('processing.jobId')) {
                AppState.set('processing.progress', data.progress);
                if (typeof Upload !== 'undefined' && Upload.onProcessingUpdate) {
                    Upload.onProcessingUpdate(data);
                }
            }
        });

        this._socket.on('file_processed', (data) => {
            if (typeof Upload !== 'undefined' && Upload.onFileProcessed) {
                Upload.onFileProcessed(data);
            }
        });

        this._socket.on('processing_complete', (data) => {
            if (data.job_id === AppState.get('processing.jobId')) {
                AppState.set('processing.active', false);
                AppState.set('processing.progress', 100);
                if (typeof Upload !== 'undefined' && Upload.onProcessingComplete) {
                    Upload.onProcessingComplete(data);
                }
            }
        });
    },

    emit(event, data) {
        if (this._socket) this._socket.emit(event, data);
    },

    cancelJob(jobId) {
        this.emit('cancel_job', { job_id: jobId });
    },
};
