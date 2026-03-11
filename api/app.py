# api/app.py
import os
import logging
import secrets
import hmac
import hashlib
import time

from flask import Flask, render_template, request, abort, make_response, redirect
from dotenv import load_dotenv

# Load .env first so Config can read it
load_dotenv(override=False)

from api.core.config import Config
from api.providers import UnifiedScraper

from api.routes.main import main_bp
from api.routes.auth import auth_bp
from api.routes.watchlist import watchlist_bp
from api.routes.api import api_bp

# ── JS Challenge constants ────────────────────────────────────────────────────
_CHALLENGE_COOKIE  = '__utmz'       # cookie name
_CHALLENGE_SECRET  = None             # set in create_app() from env/config
_CHALLENGE_TTL     = 60 * 60 * 6     # cookie valid for 6 hours (seconds)
_CHALLENGE_VER     = 'v3'             # bump this to instantly invalidate ALL existing cookies

# Paths that skip the JS challenge entirely
_CHALLENGE_SKIP_PREFIXES = (
    '/static/',
    '/api/',
    '/auth/',
    '/_challenge',
    '/_verify',
)

def _make_challenge_token(secret: str, ip: str, ua: str) -> str:
    """Generate a time-bucketed HMAC token bound to version + IP + User-Agent."""
    bucket  = int(time.time()) // _CHALLENGE_TTL
    ua_key  = ua[:64]
    msg     = f"yume:{_CHALLENGE_VER}:{bucket}:{ip}:{ua_key}".encode()
    sig     = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()[:24]
    return f"{_CHALLENGE_VER}.{bucket}.{sig}"

def _verify_challenge_token(token: str, secret: str, ip: str, ua: str) -> bool:
    """Return True if token matches version + IP + UA and is within TTL."""
    try:
        parts = token.split('.')
        # Format: ver.bucket.sig  (3 parts)
        if len(parts) != 3:
            return False
        ver, bucket_str, sig = parts
        # Reject any token from a different version — instant invalidation
        if ver != _CHALLENGE_VER:
            return False
        bucket     = int(bucket_str)
        now_bucket = int(time.time()) // _CHALLENGE_TTL
        if abs(now_bucket - bucket) > 2:  # accept up to 2 expired buckets (~36h grace)
            return False
        ua_key   = ua[:64]
        msg      = f"yume:{_CHALLENGE_VER}:{bucket}:{ip}:{ua_key}".encode()
        expected = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()[:24]
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False


def create_app():
    """Application factory pattern."""
    app = Flask(__name__, instance_relative_config=False)

    # Load configuration
    app.config.from_object(Config)

    # Validate config if your Config.validate exists
    try:
        Config.validate()
    except AttributeError:
        pass
    except Exception:
        app.logger.exception("Config.validate() raised an exception")

    # --- Ensure SECRET_KEY exists (dev fallback, but warn) ---
    if not app.config.get("SECRET_KEY"):
        env_secret = os.environ.get("FLASK_KEY") or os.environ.get("SECRET_KEY")
        if env_secret:
            app.config["SECRET_KEY"] = env_secret
        else:
            app.config["SECRET_KEY"] = secrets.token_urlsafe(64)
            app.config["_AUTO_GENERATED_SECRET"] = True
            app.logger.warning(
                "No SECRET_KEY found in environment. Using an auto-generated key for development. "
                "Do NOT use this in production — set FLASK_KEY or SECRET_KEY in the environment."
            )
    else:
        app.logger.debug("SECRET_KEY loaded from Config")

    # --- Challenge secret (can be same as SECRET_KEY or separate) ---
    global _CHALLENGE_SECRET
    _CHALLENGE_SECRET = (
        os.environ.get("CHALLENGE_SECRET")
        or app.config.get("SECRET_KEY")
    )

    # Set up logging
    log_level_name = getattr(Config, "LOG_LEVEL", None) or os.environ.get("LOG_LEVEL", "INFO")
    try:
        log_level = getattr(logging, log_level_name.upper())
    except Exception:
        log_level = logging.INFO
    logging.basicConfig(level=log_level)

    # Security: session cookie settings
    if app.config.get("DEBUG") or app.debug:
        app.config.update(
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",
            TEMPLATES_AUTO_RELOAD=True,
        )
    else:
        app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",
        )

    # Custom Jinja2 filters
    import re

    def regex_replace(s, pattern, replacement):
        if s is None:
            return ''
        return re.sub(pattern, replacement, str(s))

    def strip_anime_id(s):
        if s is None:
            return ''
        return re.sub(r'-\d+$', '', str(s))

    app.jinja_env.filters['regex_replace'] = regex_replace
    app.jinja_env.filters['strip_anime_id'] = strip_anime_id

    # Initialize scraper
    app.ha_scraper = UnifiedScraper()

    # Initialize extensions
    from api.core.extensions import limiter
    limiter.init_app(app)

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp,      url_prefix='/auth')
    app.register_blueprint(watchlist_bp, url_prefix='/watchlist')
    app.register_blueprint(api_bp,       url_prefix='/api')

    # ── JS Challenge endpoint ─────────────────────────────────────────────────
    @app.route('/_challenge')
    def js_challenge():
        """
        Step 1: Serve challenge page with signed nonce baked into JS.
        JS must POST the nonce back to /_verify — curl cannot do this without
        running JS. The real cookie is set server-side as HttpOnly, meaning
        it is COMPLETELY INVISIBLE in browser devtools and cannot be copied.
        """
        next_url = request.args.get('next', '/')
        if not next_url.startswith('/') or next_url.startswith('//'):
            next_url = '/'

        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        client_ua = request.headers.get('User-Agent', '')
        nonce = _make_challenge_token(_CHALLENGE_SECRET, client_ip, client_ua)

        # Obfuscate nonce: XOR each char with a rotating key, then base64
        import base64
        xor_key = [0x4e, 0x7a, 0x51, 0x6b, 0x38, 0x59, 0x32, 0x78]
        nonce_bytes = nonce.encode()
        xored = bytes([b ^ xor_key[i % len(xor_key)] for i, b in enumerate(nonce_bytes)])
        enc_nonce = base64.b64encode(xored).decode()
        # Split into 3 chunks so no single variable holds the full value
        c = len(enc_nonce) // 3
        p1, p2, p3 = enc_nonce[:c], enc_nonce[c:2*c], enc_nonce[2*c:]
        # Also obfuscate next_url trivially
        enc_next = base64.b64encode(next_url.encode()).decode()
        # XOR key as JS array
        xk = ','.join(str(k) for k in xor_key)

        html = (
            "<!DOCTYPE html>\n<html>\n"
            "<head><meta charset=\"utf-8\"><title>Checking your browser...</title>"
            "<style>body{margin:0;background:#0d0d0d;display:flex;align-items:center;"
            "justify-content:center;height:100vh;font-family:monospace;color:#888;}</style>"
            "</head>\n<body><p>Verifying browser\u2026</p>\n<script>\n"
            "!function(){\n"
            f"  var _a={p1!r},_b={p2!r},_c={p3!r};\n"
            f"  var _k=[{xk}];\n"
            f"  var _x={enc_next!r};\n"
            "  var _atob=function(s){try{return atob(s);}catch(e){return '';}};\n"
            "  var _xd=function(s){var b=_atob(s),o='';\n"
            "    for(var i=0;i<b.length;i++)o+=String.fromCharCode(b.charCodeAt(i)^_k[i%_k.length]);\n"
            "    return o;};\n"
            "  var _n=_xd(_a+_b+_c);\n"
            "  var _u=_atob(_x);\n"
            "  fetch('\x2f\x5f\x76\x65\x72\x69\x66\x79',{\n"
            "    method:'\x50\x4f\x53\x54',\n"
            "    credentials:'same-origin',\n"
            "    headers:{'\x43\x6f\x6e\x74\x65\x6e\x74\x2d\x54\x79\x70\x65':'application/json'},\n"
            "    body:JSON.stringify({n:_n,x:_u})\n"
            "  }).then(function(r){return r.json();}).then(function(d){\n"
            "    if(d.ok)window.location.replace(d.x||'/');\n"
            "    else window.location.replace('/');\n"
            "  }).catch(function(){window.location.replace('/');});\n"
            "}();\n"
            "</script>\n</body>\n</html>"
        )
        resp = make_response(html, 200)
        resp.headers['Content-Type']  = 'text/html; charset=utf-8'
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        resp.headers['Pragma']        = 'no-cache'
        return resp

    @app.route('/_verify', methods=['POST'])
    def js_verify():
        """
        Step 2: JS POSTs the nonce here. We verify it and set an HttpOnly
        cookie — completely invisible in browser devtools Application tab.
        curl cannot copy what it cannot see.
        """
        from flask import jsonify
        try:
            data      = request.get_json(silent=True) or {}
            nonce     = data.get('n', '')
            next_url  = data.get('x', '/')
            if not next_url.startswith('/') or next_url.startswith('//'):
                next_url = '/'

            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
            client_ua = request.headers.get('User-Agent', '')

            if not _verify_challenge_token(nonce, _CHALLENGE_SECRET, client_ip, client_ua):
                return jsonify(ok=False), 403

            # Issue fresh token and set it as HttpOnly — invisible to devtools
            fresh_token = _make_challenge_token(_CHALLENGE_SECRET, client_ip, client_ua)
            resp = make_response(jsonify(ok=True, x=next_url), 200)
            resp.set_cookie(
                _CHALLENGE_COOKIE,
                fresh_token,
                max_age=_CHALLENGE_TTL * 2,  # cookie lives 2x the bucket window
                httponly=True,               # invisible in devtools Application tab
                secure=not (app.config.get("DEBUG") or app.debug),
                samesite='Lax',
                path='/',
            )
            return resp
        except Exception as e:
            app.logger.error(f"/_verify error: {e}")
            return jsonify(ok=False), 500


    # ── Error handlers ────────────────────────────────────────────────────────
    @app.errorhandler(404)
    def page_not_found(e):
        app.logger.warning(f"404 error: {request.url}")
        return render_template('404.html', error_message="Page not found"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        app.logger.error(f"500 error: {str(e)}")
        return render_template('404.html', error_message="Internal server error"), 500

    @app.errorhandler(429)
    def ratelimit_handler(e):
        app.logger.warning(f"Rate limit exceeded: {request.url} - {request.remote_addr}")
        from flask import jsonify
        return jsonify(success=False, message="Too many attempts. Please try again later."), 429

    # ── Before-request hooks ──────────────────────────────────────────────────
    @app.before_request
    def js_challenge_gate():
        """
        Gate every HTML page request behind the JS challenge.
        Bots that cannot run JavaScript will NEVER obtain a valid signed cookie,
        so they always hit the challenge page and get nothing useful.
        """
        # Skip paths that don't need the challenge
        if any(request.path.startswith(p) for p in _CHALLENGE_SKIP_PREFIXES):
            return

        # Only challenge HTML page loads, not XHR/fetch/JSON requests
        if not request.accept_mimetypes.accept_html:
            return

        cookie_val = request.cookies.get(_CHALLENGE_COOKIE, '')
        client_ip  = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        client_ua  = request.headers.get('User-Agent', '')
        if _verify_challenge_token(cookie_val, _CHALLENGE_SECRET, client_ip, client_ua):
            return  # ✅ Valid — real browser, correct IP+UA, within TTL

        # ❌ No valid cookie — redirect to JS challenge
        app.logger.info(
            f"JS challenge triggered: PATH={request.path} "
            f"IP={request.remote_addr} UA={request.headers.get('User-Agent','')[:80]}"
        )
        return redirect(f'/_challenge?next={request.path}', 302)

    @app.before_request
    def block_obvious_bots():
        """
        Secondary filter: block truly obvious bots even on /api/ and /auth/ routes
        that the JS challenge skips (those endpoints use JSON, not HTML).
        """
        if request.path.startswith('/static/'):
            return

        ua = request.headers.get('User-Agent', '')
        bot_signatures = [
            'curl/', 'wget/', 'python-requests', 'python-urllib',
            'httpx', 'aiohttp', 'scrapy', 'java/', 'go-http-client',
            'libwww-perl', 'ruby', 'php/', 'node-fetch', 'axios',
        ]
        if not ua or any(sig in ua.lower() for sig in bot_signatures):
            app.logger.warning(
                f"Blocked bot UA='{ua[:80]}' PATH={request.path} IP={request.remote_addr}"
            )
            abort(403)

    @app.before_request
    def hydrate_legacy_sessions():
        """Ensure older sessions have required avatar/anilist data for navbar rendering."""
        from flask import session

        if '_id' in session and 'anilist_authenticated' not in session:
            try:
                from api.models.user import get_user_by_id
                user = get_user_by_id(session['_id'])
                if user:
                    session['anilist_authenticated'] = bool(user.get('anilist_id'))
                    session['avatar']                = user.get('avatar')
                    if user.get('anilist_id'):
                        session['anilist_id'] = user.get('anilist_id')
                    session.modified = True
            except Exception as e:
                app.logger.error(f"Error hydrating session for user {session.get('_id')}: {e}")

    return app


# For backward compatibility
app = create_app()

if __name__ == '__main__':
    app.run(debug=True)