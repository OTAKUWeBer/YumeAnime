"""
Main routes package
Exports all main route blueprints and aggregates them into main_bp
"""
from flask import Blueprint

from .home_routes import home_routes_bp
from .search_routes import search_routes_bp
from .anime_routes import anime_routes_bp
from .watch_routes import watch_routes_bp
from .catalog_routes import catalog_routes_bp

main_bp = Blueprint('main', __name__)

main_bp.register_blueprint(home_routes_bp)
main_bp.register_blueprint(search_routes_bp)
main_bp.register_blueprint(anime_routes_bp)
main_bp.register_blueprint(watch_routes_bp)
main_bp.register_blueprint(catalog_routes_bp)

__all__ = [
    'main_bp',
    'home_routes_bp',
    'search_routes_bp',
    'anime_routes_bp',
    'watch_routes_bp',
    'catalog_routes_bp'
]
