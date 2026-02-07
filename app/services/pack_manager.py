"""Sticker pack management with JSON persistence."""

import os
import json
import uuid
import logging
from datetime import datetime
from app.config import PACKS_FOLDER
from app.models.pack import Pack

logger = logging.getLogger('telesticker.packs')


def _ensure_dir():
    os.makedirs(PACKS_FOLDER, exist_ok=True)


def _pack_path(pack_id):
    return os.path.join(PACKS_FOLDER, f'{pack_id}.json')


def list_packs():
    """Return list of all saved packs."""
    _ensure_dir()
    packs = []
    for fname in os.listdir(PACKS_FOLDER):
        if fname.endswith('.json'):
            try:
                with open(os.path.join(PACKS_FOLDER, fname), 'r') as f:
                    packs.append(json.load(f))
            except Exception as e:
                logger.warning(f'Failed to load pack {fname}: {e}')
    return packs


def get_pack(pack_id):
    """Load a single pack by ID."""
    path = _pack_path(pack_id)
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        return json.load(f)


def create_pack(name, title, author=''):
    """Create a new pack and save to disk."""
    _ensure_dir()
    pack_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    pack = Pack(
        pack_id=pack_id, name=name, title=title, author=author,
        created_at=now, updated_at=now
    )
    _save(pack)
    return pack.to_dict()


def update_pack(pack_id, data):
    """Update pack fields and save."""
    existing = get_pack(pack_id)
    if not existing:
        return None
    for key in ('name', 'title', 'author', 'sticker_ids', 'icon_sticker_id'):
        if key in data:
            existing[key] = data[key]
    existing['updated_at'] = datetime.utcnow().isoformat()
    with open(_pack_path(pack_id), 'w') as f:
        json.dump(existing, f, indent=2)
    return existing


def delete_pack(pack_id):
    """Delete a pack file."""
    path = _pack_path(pack_id)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def _save(pack):
    with open(_pack_path(pack.pack_id), 'w') as f:
        json.dump(pack.to_dict(), f, indent=2)
