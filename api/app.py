import os
import re
import logging
import secrets

from flask import Flask, render_template, request, abort, jsonify
from dotenv import load_dotenv

load_dotenv(override=False)

from api.core.config import Config
from api.providers import UnifiedScraper
from api.routes.main import main_bp
from api.routes.auth import auth_bp
from api.routes.watchlist import watchlist_bp
from api.routes.api import api_bp
from api.core.extensions import limiter

_RE_STRIP_ANIME_ID = re.compile(r'-\d+$')

HEADLESS_PATTERNS = [
    r"headless", r"phantom", r"selenium", r"puppeteer",
    r"playwright", r"chromium", r"firefox.*headless",
    r"chrome.*headless", r"wpdt", r"webdriver",
    r"python-requests", r"go-http-client", r"curl", r"wget",
    r"scrapy", r"httpclient", r"libwww", r"jakarta", r"httpx",
]


def create_app():
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config)

    try:
        Config.validate()
    except (AttributeError, Exception):
        pass

    if not app.config.get("SECRET_KEY"):
        env_secret = os.environ.get("FLASK_KEY") or os.environ.get("SECRET_KEY")
        if env_secret:
            app.config["SECRET_KEY"] = env_secret
        else:
            app.config["SECRET_KEY"] = secrets.token_urlsafe(64)
            app.logger.warning(
                "No SECRET_KEY set — using auto-generated key. Set FLASK_KEY in production."
            )

    log_level_name = getattr(Config, "LOG_LEVEL", None) or os.environ.get("LOG_LEVEL", "INFO")
    logging.basicConfig(level=getattr(logging, log_level_name.upper(), logging.INFO))

    is_debug = bool(app.config.get("DEBUG") or app.debug)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=not is_debug,
        TEMPLATES_AUTO_RELOAD=is_debug,
    )

    app.jinja_env.filters['regex_replace'] = (
        lambda s, pat, rep: re.sub(pat, rep, str(s)) if s is not None else ''
    )
    app.jinja_env.filters['strip_anime_id'] = (
        lambda s: _RE_STRIP_ANIME_ID.sub('', str(s)) if s is not None else ''
    )

    app.ha_scraper = UnifiedScraper()
    limiter.init_app(app)

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp,      url_prefix='/auth')
    app.register_blueprint(watchlist_bp, url_prefix='/watchlist')
    app.register_blueprint(api_bp,       url_prefix='/api')

    @app.before_request
    def block_obvious_bots():
        if request.path.startswith('/static/'):
            return
        ua = request.headers.get('User-Agent', '').lower()
        if not ua or any(re.search(p, ua) for p in HEADLESS_PATTERNS):
            app.logger.warning(f"Blocked bot UA='{ua[:80]}' PATH={request.path} IP={request.remote_addr}")
            abort(403)


    @app.errorhandler(404)
    def page_not_found(e):
        app.logger.warning(f"404: {request.url}")
        return render_template('404.html', error_message="Page not found"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        app.logger.error(f"500: {e}")
        return render_template('404.html', error_message="Internal server error"), 500

    @app.errorhandler(429)
    def ratelimit_handler(e):
        app.logger.warning(f"Rate limit: {request.url} — {request.remote_addr}")
        return jsonify(success=False, message="Too many attempts. Please try again later."), 429

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True)