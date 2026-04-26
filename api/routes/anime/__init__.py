# Anime routes package
from .anime_routes import anime_routes_bp
from .watch_routes import watch_routes_bp
from .catalog_routes import catalog_routes_bp
from .anilist_api import anilist_api_bp

__all__ = ['anime_routes_bp', 'watch_routes_bp', 'catalog_routes_bp', 'anilist_api_bp']
