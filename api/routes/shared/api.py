"""
Main API blueprint - aggregates all API sub-blueprints
"""
from flask import Blueprint, request, session, jsonify

from .auth_api import auth_api_bp
from ..anime.anilist_api import anilist_api_bp
from .watchlist_api import watchlist_api_bp
from ..manga.manga_api import manga_api_bp
from .comments_api import comments_api_bp

api_bp = Blueprint('api', __name__)

api_bp.register_blueprint(auth_api_bp, url_prefix='/auth')
api_bp.register_blueprint(anilist_api_bp, url_prefix='/anilist')
api_bp.register_blueprint(watchlist_api_bp, url_prefix='/watchlist')
api_bp.register_blueprint(manga_api_bp, url_prefix='/manga')
api_bp.register_blueprint(comments_api_bp, url_prefix='')

@api_bp.route('/set-server', methods=['POST'])
def set_server():
    """Store preferred server in session"""
    data = request.get_json()
    server = data.get('server')
    if server:
        session['last_used_server'] = server
        return jsonify({'success': True})
    return jsonify({'success': False}), 400
