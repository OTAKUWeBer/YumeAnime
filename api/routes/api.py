"""
Main API blueprint - aggregates all API sub-blueprints
"""
from flask import Blueprint

from .api.auth_api import auth_api_bp
from .api.anilist_api import anilist_api_bp
from .api.watchlist_api import watchlist_api_bp

api_bp = Blueprint('api', __name__)

api_bp.register_blueprint(auth_api_bp, url_prefix='')
api_bp.register_blueprint(anilist_api_bp, url_prefix='/anilist')
api_bp.register_blueprint(watchlist_api_bp, url_prefix='/watchlist')
