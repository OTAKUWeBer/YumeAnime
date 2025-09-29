# config.py
import os
import secrets
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

class Config:
    """Base configuration class"""
    # Prefer FLASK_KEY for backward compatibility, then SECRET_KEY.
    SECRET_KEY = os.getenv("FLASK_KEY") or os.getenv("SECRET_KEY")

    # If no secret key is provided, create a random one for development usage.
    # WARNING: auto-generated keys are unstable across restarts and MUST NOT be used in production.
    if not SECRET_KEY:
        SECRET_KEY = secrets.token_urlsafe(64)
        _AUTO_GENERATED_SECRET = True
    else:
        _AUTO_GENERATED_SECRET = False

    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    # Cloudflare
    CLOUDFLARE_SECRET = os.getenv("CLOUDFLARE_SECRET")

    # AniList OAuth
    ANILIST_CLIENT_ID = os.getenv("ANILIST_CLIENT_ID")
    ANILIST_CLIENT_SECRET = os.getenv("ANILIST_CLIENT_SECRET")
    ANILIST_REDIRECT_URI = os.getenv("ANILIST_REDIRECT_URI")

    # Application settings
    DEBUG = os.getenv("FLASK_ENV") == "development"

    @classmethod
    def validate(cls):
        """Validate that required environment variables are set."""
        missing = []
        
        # Check AniList OAuth credentials
        if not cls.ANILIST_CLIENT_ID:
            missing.append("ANILIST_CLIENT_ID")
        if not cls.ANILIST_CLIENT_SECRET:
            missing.append("ANILIST_CLIENT_SECRET")
        if not cls.ANILIST_REDIRECT_URI:
            missing.append("ANILIST_REDIRECT_URI")
        
        if missing:
            logger.warning(f"Missing environment variables: {', '.join(missing)}")
            logger.warning("AniList OAuth will not work without these variables.")
        else:
            logger.info("All required AniList OAuth environment variables are set.")
            logger.info(f"AniList Redirect URI: {cls.ANILIST_REDIRECT_URI}")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
