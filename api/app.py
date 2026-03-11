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
_POW_DIFFICULTY    = 2                # SHA256 prefix zeros for proof-of-work (~256 avg iters, ~50ms in browser)
_PAGE_TOKEN_TTL    = 60 * 60          # signed page token valid 1 hour — required on all /api/ calls

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


def _verify_pow(challenge: str, solution: str, difficulty: int = None) -> bool:
    """Verify FNV-1a(challenge + solution) starts with `difficulty` hex zeros.
    Uses same FNV-1a as the browser JS — works on HTTP and HTTPS alike.
    """
    if difficulty is None:
        difficulty = _POW_DIFFICULTY
    try:
        n   = int(solution)
        s   = f"{challenge}{n}"
        h   = 0x811c9dc5
        for c in s.encode():
            h ^= c
            h  = (h * 0x01000193) & 0xFFFFFFFF
        digest = format(h, '08x')
        return digest.startswith('0' * difficulty)
    except Exception:
        return False


def _make_page_token(secret: str, ip: str) -> str:
    """Short-lived IP-bound token injected into every HTML page as a meta tag.
    JS reads it and adds it as X-PT header on all /api/ fetch calls.
    """
    bucket = int(time.time()) // _PAGE_TOKEN_TTL
    msg    = f"pt:{bucket}:{ip}".encode()
    sig    = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()[:20]
    return f"{bucket}.{sig}"


def _verify_page_token(token: str, secret: str, ip: str) -> bool:
    """Return True if page token is valid for this IP and not expired."""
    try:
        bucket_str, sig = token.split('.', 1)
        bucket     = int(bucket_str)
        now_bucket = int(time.time()) // _PAGE_TOKEN_TTL
        if abs(now_bucket - bucket) > 2:
            return False
        msg      = f"pt:{bucket}:{ip}".encode()
        expected = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()[:20]
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

    @app.context_processor
    def inject_page_token():
        """Layer 4 — inject signed page token into every HTML template as a meta tag.
        base.html reads it and adds X-PT header on all /api/ fetch calls.
        """
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        return dict(page_token=_make_page_token(_CHALLENGE_SECRET, client_ip))

    # ── JS Challenge endpoint ─────────────────────────────────────────────────
    @app.route('/_challenge')
    def js_challenge():
        """
        Layer 1 — JS execution gate (curl can't run JS).
        Layer 2 — Proof-of-Work baked into challenge page (adds CPU cost for bots).
        Cookie is set HttpOnly server-side — invisible in devtools.
        """
        next_url = request.args.get('next', '/')
        if not next_url.startswith('/') or next_url.startswith('//'):
            next_url = '/'

        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        client_ua = request.headers.get('User-Agent', '')
        nonce = _make_challenge_token(_CHALLENGE_SECRET, client_ip, client_ua)

        # Obfuscate nonce: XOR + base64 split into 3 parts
        import base64, secrets as _sec
        xor_key = [0x4e, 0x7a, 0x51, 0x6b, 0x38, 0x59, 0x32, 0x78]
        xored   = bytes([b ^ xor_key[i % len(xor_key)] for i, b in enumerate(nonce.encode())])
        enc_n   = base64.b64encode(xored).decode()
        c       = len(enc_n) // 3
        p1, p2, p3 = enc_n[:c], enc_n[c:2*c], enc_n[2*c:]
        enc_x   = base64.b64encode(next_url.encode()).decode()
        xk      = ','.join(str(k) for k in xor_key)
        # PoW: random challenge string — browser must find N where sha256(pw+N) starts with '00'
        pow_ch  = _sec.token_hex(8)

        html = (
            "<!DOCTYPE html>\n<html>\n"
            "<head><meta charset=\"utf-8\"><title>Checking your browser...</title>"
            "<style>body{margin:0;background:#0d0d0d;display:flex;align-items:center;"
            "justify-content:center;height:100vh;font-family:monospace;color:#888;}</style>"
            "</head>\n<body><p>Verifying browser\u2026</p>\n<script>\n"
            "!function(){\n"
            f"  var _a={p1!r},_b={p2!r},_c={p3!r};\n"
            f"  var _k=[{xk}];\n"
            f"  var _x={enc_x!r};\n"
            f"  var _pw={pow_ch!r};\n"
            "  var _atob=function(s){{try{{return atob(s);}}catch(e){{return '';}}}};\n"
            "  var _xd=function(s){{var b=_atob(s),o='';\n"
            "    for(var i=0;i<b.length;i++)o+=String.fromCharCode(b.charCodeAt(i)^_k[i%_k.length]);\n"
            "    return o;}};\n"
            "  var _n=_xd(_a+_b+_c);\n"
            "  var _u=_atob(_x);\n"
            "  var _h=function(s){var h=0x811c9dc5>>>0,i=0;for(;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,0x01000193)>>>0;}return h.toString(16).padStart(8,'0');}\n"
            "  var _sol=0;while(_sol<500000){if(_h(_pw+_sol).slice(0,2)==='00')break;_sol++;}\n"
            "  fetch('\x2f\x5f\x76\x65\x72\x69\x66\x79',{\n"
            "    method:'\x50\x4f\x53\x54',\n"
            "    credentials:'same-origin',\n"
            "    headers:{'\x43\x6f\x6e\x74\x65\x6e\x74\x2d\x54\x79\x70\x65':'application/json'},\n"
            "    body:JSON.stringify({n:_n,x:_u,pw_c:_pw,pw_s:_sol})\n"
            "  }).then(function(r){return r.json();}).then(function(d){\n"
            "    if(d.ok)window.location.replace(d.x||'//');\n"
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
    @limiter.limit("10 per minute")   # Layer 5 — rate limit: stops brute-force PoW bypass
    def js_verify():
        """
        Layer 1 — verifies HMAC nonce (IP+UA bound, time-bucketed).
        Layer 2 — verifies Proof-of-Work solution.
        Sets HttpOnly cookie (Layer 3 — invisible in devtools).
        Also issues a signed page token stored in a readable cookie for API auth.
        """
        from flask import jsonify
        try:
            data    = request.get_json(silent=True) or {}
            nonce   = data.get('n', '')
            next_url= data.get('x', '/')
            pow_c   = data.get('pw_c', '')
            pow_s   = data.get('pw_s', '')
            if not next_url.startswith('/') or next_url.startswith('//'):
                next_url = '/'

            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
            client_ua = request.headers.get('User-Agent', '')

            # Layer 1: verify HMAC nonce
            if not _verify_challenge_token(nonce, _CHALLENGE_SECRET, client_ip, client_ua):
                app.logger.warning(f"/_verify: invalid nonce from {client_ip}")
                return jsonify(ok=False, e='nonce'), 403

            # Layer 2: verify Proof-of-Work
            if not _verify_pow(pow_c, str(pow_s)):
                app.logger.warning(f"/_verify: invalid PoW from {client_ip}")
                return jsonify(ok=False, e='pow'), 403

            # Layer 3: set HttpOnly challenge cookie — invisible in devtools
            fresh_token  = _make_challenge_token(_CHALLENGE_SECRET, client_ip, client_ua)
            # Layer 4: page token — readable by JS, used as X-PT header on /api/ calls
            page_token   = _make_page_token(_CHALLENGE_SECRET, client_ip)
            is_secure    = not (app.config.get("DEBUG") or app.debug)

            resp = make_response(jsonify(ok=True, x=next_url), 200)
            resp.set_cookie(
                _CHALLENGE_COOKIE, fresh_token,
                max_age=_CHALLENGE_TTL * 2,
                httponly=True, secure=is_secure, samesite='Lax', path='/',
            )
            resp.set_cookie(
                '__pt', page_token,
                max_age=_PAGE_TOKEN_TTL * 2,
                httponly=False,   # JS must read this to send as header
                secure=is_secure, samesite='Lax', path='/',
            )
            return resp
        except Exception as e:
            app.logger.error(f"/_verify error: {e}")
            from flask import jsonify
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
    def check_api_page_token():
        """Layer 4 — require valid X-PT header on /api/ calls (except auth).
        Prevents direct API scraping without first loading a real page.
        """
        if not request.path.startswith('/api/'):
            return
        # Skip auth endpoints — login/signup don't need a page token
        if request.path.startswith('/api/auth/'):
            return
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        token     = request.headers.get('X-PT', '') or request.cookies.get('__pt', '')
        if not token or not _verify_page_token(token, _CHALLENGE_SECRET, client_ip):
            from flask import jsonify
            return jsonify(error='Forbidden', message='Missing page token'), 403

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