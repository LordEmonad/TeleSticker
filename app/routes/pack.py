"""Pack management routes."""

from flask import Blueprint, request, jsonify
from app.services.pack_manager import list_packs, get_pack, create_pack, update_pack, delete_pack

pack_bp = Blueprint('pack', __name__, url_prefix='/api/pack')


@pack_bp.route('', methods=['GET'])
def list_all():
    return jsonify({'packs': list_packs()})


@pack_bp.route('', methods=['POST'])
def create():
    data = request.get_json()
    name = data.get('name', '').strip()
    title = data.get('title', '').strip()
    author = data.get('author', '').strip()

    if not name or not title:
        return jsonify({'error': 'Name and title are required'}), 400

    pack = create_pack(name, title, author)
    return jsonify(pack), 201


@pack_bp.route('/<pack_id>', methods=['GET'])
def get_one(pack_id):
    pack = get_pack(pack_id)
    if not pack:
        return jsonify({'error': 'Pack not found'}), 404
    return jsonify(pack)


@pack_bp.route('/<pack_id>', methods=['PUT'])
def update(pack_id):
    data = request.get_json()
    pack = update_pack(pack_id, data)
    if not pack:
        return jsonify({'error': 'Pack not found'}), 404
    return jsonify(pack)


@pack_bp.route('/<pack_id>', methods=['DELETE'])
def delete(pack_id):
    if delete_pack(pack_id):
        return jsonify({'ok': True})
    return jsonify({'error': 'Pack not found'}), 404
