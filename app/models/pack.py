"""Sticker pack data model."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Pack:
    pack_id: str
    name: str  # short_name for Telegram (alphanumeric + underscores)
    title: str  # display title
    author: str = ''
    sticker_ids: List[str] = field(default_factory=list)
    icon_sticker_id: Optional[str] = None
    created_at: str = ''
    updated_at: str = ''

    def to_dict(self):
        return {
            'pack_id': self.pack_id,
            'name': self.name,
            'title': self.title,
            'author': self.author,
            'sticker_ids': self.sticker_ids,
            'icon_sticker_id': self.icon_sticker_id,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }
