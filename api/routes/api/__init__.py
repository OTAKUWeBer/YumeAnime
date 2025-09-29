"""
API routes package
Exports all API blueprints and aggregates them into api_bp
"""
from flask import Blueprint

from .auth_api import auth_api_bp
from .anilist_api import anilist_api_bp
from .watchlist_api import watchlist_api_bp

api_bp = Blueprint('api', __name__)

api_bp.register_blueprint(auth_api_bp, url_prefix='')
api_bp.register_blueprint(anilist_api_bp, url_prefix='')
api_bp.register_blueprint(watchlist_api_bp, url_prefix='/watchlist')

__all__ = ['api_bp', 'auth_api_bp', 'anilist_api_bp', 'watchlist_api_bp']
