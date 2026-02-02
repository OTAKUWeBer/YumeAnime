# api/app.py
import os
import logging
import secrets
from datetime import timedelta

from flask import Flask, render_template, request

from dotenv import load_dotenv
from api.core.config import Config
from api.scrapers import HianimeScraper


from api.routes.main import main_bp
from api.routes.auth import auth_bp
from api.routes.watchlist import watchlist_bp
from api.routes.api import api_bp


# Load .env (optional; safe to call in production if python-dotenv isn't installed it'll fail — install it for dev)
load_dotenv(override=False)


def create_app():
    """Application factory pattern."""
    app = Flask(__name__, instance_relative_config=False)

    # Load configuration
    app.config.from_object(Config)

    # Validate config if your Config.validate exists
    try:
        Config.validate()
    except AttributeError:
        # If Config.validate isn't present, ignore silently
        pass
    except Exception:
        app.logger.exception("Config.validate() raised an exception")

    # --- Ensure SECRET_KEY exists (dev fallback, but warn) ---
    # Prefer the explicit config value (Config should have read FLASK_KEY or SECRET_KEY from env)
    if not app.config.get("SECRET_KEY"):
        # Try env var fallbacks in case config uses a different name
        env_secret = os.environ.get("FLASK_KEY") or os.environ.get("SECRET_KEY")
        if env_secret:
            app.config["SECRET_KEY"] = env_secret
        else:
            # Last resort: auto-generate a key for development only
            app.config["SECRET_KEY"] = secrets.token_urlsafe(64)
            # Flag for other code to detect auto-generation (optional)
            app.config["_AUTO_GENERATED_SECRET"] = True
            app.logger.warning(
                "No SECRET_KEY found in environment. Using an auto-generated key for development. "
                "Do NOT use this in production — set FLASK_KEY or SECRET_KEY in the environment."
            )
    else:
        app.logger.debug("SECRET_KEY loaded from Config")

    # Set up logging (use config value if available)
    log_level_name = getattr(Config, "LOG_LEVEL", None) or os.environ.get("LOG_LEVEL", "INFO")
    try:
        log_level = getattr(logging, log_level_name.upper())
    except Exception:
        log_level = logging.INFO
    logging.basicConfig(level=log_level)

    # Security: session cookie settings
    if app.config.get("DEBUG") or app.debug:
        # dev friendly
        app.config.update(
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",
            TEMPLATES_AUTO_RELOAD=True  # Enable template auto-reload in development
        )
    else:
        # production recommended options
        app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",
        )

    # Custom Jinja2 filters
    import re
    
    def regex_replace(s, pattern, replacement):
        """Replace regex pattern in string"""
        if s is None:
            return ''
        return re.sub(pattern, replacement, str(s))
    
    def strip_anime_id(s):
        """Strip trailing numeric ID from anime slug (e.g., 'anime-name-12345' -> 'anime-name')"""
        if s is None:
            return ''
        return re.sub(r'-\d+$', '', str(s))
    
    app.jinja_env.filters['regex_replace'] = regex_replace
    app.jinja_env.filters['strip_anime_id'] = strip_anime_id

    # Initialize scraper
    app.ha_scraper = HianimeScraper()

    # Initialize extensions
    from api.core.extensions import limiter
    limiter.init_app(app)

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(watchlist_bp, url_prefix='/watchlist')
    app.register_blueprint(api_bp, url_prefix='/api')

    # Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        """Handle 404 errors."""
        app.logger.warning(f"404 error: {request.url}")
        return render_template('404.html', error_message="Page not found"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        """Handle 500 errors."""
        app.logger.error(f"500 error: {str(e)}")
        return render_template('404.html', error_message="Internal server error"), 500

    @app.errorhandler(429)
    def ratelimit_handler(e):
        """Handle 429 errors (Rate Limit Exceeded)."""
        app.logger.warning(f"Rate limit exceeded: {request.url} - {request.remote_addr}")
        from flask import jsonify
        return jsonify(success=False, message="Too many attempts. Please try again later."), 429

    return app


# For backward compatibility
app = create_app()

if __name__ == '__main__':
    # Use the created app for local dev
    app.run(debug=True)
