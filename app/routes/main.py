"""Main route — serves the SPA shell."""

from flask import Blueprint, render_template
from app.services.background_remover import is_available as bg_available

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return render_template('index.html', bg_removal_available=bg_available())
