"""Sticker data model."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Sticker:
    file_id: str
    original_filename: str
    file_type: str  # 'image', 'video', 'animated_gif'
    upload_path: str
    thumbnail_path: Optional[str] = None
    processed_path: Optional[str] = None
    bg_removed_path: Optional[str] = None
    use_bg_removed: bool = False
    output_format: str = 'webp'  # 'webp' or 'png'
    mode: str = 'sticker'  # 'sticker' or 'emoji'
    emoji: str = ''
    file_size: int = 0
    width: int = 0
    height: int = 0
    has_transparency: bool = False
    status: str = 'uploaded'  # uploaded, processing, processed, error
    error_message: str = ''

    def to_dict(self):
        return {
            'file_id': self.file_id,
            'original_filename': self.original_filename,
            'file_type': self.file_type,
            'thumbnail_path': self.thumbnail_path,
            'processed_path': self.processed_path,
            'output_format': self.output_format,
            'mode': self.mode,
            'emoji': self.emoji,
            'file_size': self.file_size,
            'width': self.width,
            'height': self.height,
            'has_transparency': self.has_transparency,
            'use_bg_removed': self.use_bg_removed,
            'status': self.status,
            'error_message': self.error_message,
        }
