"""Shared Flask extensions."""

from flask_socketio import SocketIO

socketio = SocketIO(cors_allowed_origins=["http://localhost:5000", "http://127.0.0.1:5000"])
