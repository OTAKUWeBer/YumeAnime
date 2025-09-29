# Routes package initialization
from .main import main_bp
from .auth import auth_bp
from .watchlist import watchlist_bp
from .api import api_bp
from .aniwatch import aniwatch_bp

__all__ = ['main_bp', 'auth_bp', 'watchlist_bp', 'api_bp', 'aniwatch_bp']
