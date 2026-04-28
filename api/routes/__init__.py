# Routes package initialization
from .anime import anime_routes_bp, watch_routes_bp, catalog_routes_bp, anilist_api_bp, themes_api_bp
from .manga import manga_routes_bp, manga_api_bp
from .shared import auth_bp, watchlist_bp, api_bp, home_routes_bp, search_routes_bp

__all__ = [
    'anime_routes_bp', 'watch_routes_bp', 'catalog_routes_bp', 'anilist_api_bp', 'themes_api_bp',
    'manga_routes_bp', 'manga_api_bp',
    'auth_bp', 'watchlist_bp', 'api_bp', 'home_routes_bp', 'search_routes_bp'
]
