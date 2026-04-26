# Shared routes package
from .auth import auth_bp
from .watchlist import watchlist_bp
from .api import api_bp
from .home_routes import home_routes_bp
from .search_routes import search_routes_bp

__all__ = ['auth_bp', 'watchlist_bp', 'api_bp', 'home_routes_bp', 'search_routes_bp']
