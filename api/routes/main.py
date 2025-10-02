"""
Main blueprint - aggregates all main route sub-blueprints
"""
from flask import Blueprint

from .main.home_routes.home_routes import home_routes_bp
from .main.search_routes import search_routes_bp
from .main.anime_routes import anime_routes_bp
from .main.watch_routes import watch_routes_bp
from .main.catalog_routes import catalog_routes_bp

main_bp = Blueprint('main', __name__)

main_bp.register_blueprint(home_routes_bp)
main_bp.register_blueprint(search_routes_bp)
main_bp.register_blueprint(anime_routes_bp)
main_bp.register_blueprint(watch_routes_bp)
main_bp.register_blueprint(catalog_routes_bp)
