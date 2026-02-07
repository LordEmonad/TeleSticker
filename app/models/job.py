"""Processing job data model."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class Job:
    job_id: str
    status: str = 'pending'  # pending, processing, complete, error, cancelled
    total_files: int = 0
    processed_files: int = 0
    file_results: List[Dict[str, Any]] = field(default_factory=list)
    error_message: str = ''
    zip_path: Optional[str] = None
    cancelled: bool = False

    @property
    def progress(self):
        if self.total_files == 0:
            return 0
        return int((self.processed_files / self.total_files) * 100)

    def to_dict(self):
        return {
            'job_id': self.job_id,
            'status': self.status,
            'total_files': self.total_files,
            'processed_files': self.processed_files,
            'progress': self.progress,
            'file_results': self.file_results,
            'error_message': self.error_message,
        }
