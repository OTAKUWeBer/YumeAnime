import os
import re
import base64
import hmac
import hashlib
import logging
import secrets
import time

from flask import Flask, render_template, request, abort, make_response, redirect, jsonify, session
from dotenv import load_dotenv

load_dotenv(override=False)

from api.core.config import Config
from api.providers import UnifiedScraper
from api.routes.main import main_bp
from api.routes.auth import auth_bp
from api.routes.watchlist import watchlist_bp
from api.routes.api import api_bp
from api.core.extensions import limiter
from api.models.user import get_user_by_id

# ── Security constants ────────────────────────────────────────────────────────
_CHALLENGE_COOKIE = '__utmz'
_CHALLENGE_SECRET = None           # set in create_app()
_CHALLENGE_TTL    = 60 * 60 * 6   # 6 hours
_CHALLENGE_VER    = 'v3'           # bump to invalidate all existing cookies instantly
_POW_DIFFICULTY   = 2              # FNV-1a prefix zeros (~256 avg iters, ~50ms browser)
_PAGE_TOKEN_TTL   = 60 * 60        # 1 hour

_CHALLENGE_SKIP_PREFIXES = ('/static/', '/api/', '/auth/', '/_challenge', '/_verify')

_BOT_SIGNATURES = (
    'curl/', 'wget/', 'python-requests', 'python-urllib',
    'httpx', 'aiohttp', 'scrapy', 'java/', 'go-http-client',
    'libwww-perl', 'ruby', 'php/', 'node-fetch', 'axios',
)

# Pre-compiled regex (avoids recompiling on every template render)
_RE_STRIP_ANIME_ID = re.compile(r'-\d+$')

# XOR key used in JS challenge — must match browser-side decode
_XOR_KEY     = [0x4e, 0x7a, 0x51, 0x6b, 0x38, 0x59, 0x32, 0x78]
_XOR_KEY_STR = ','.join(str(k) for k in _XOR_KEY)


# ── Security helpers ──────────────────────────────────────────────────────────

def _hmac_sig(secret: str, msg: str, length: int = 24) -> str:
    """Convenience wrapper — single HMAC-SHA256 call, trimmed to `length` hex chars."""
    return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()[:length]


def _make_challenge_token(secret: str, ip: str, ua: str) -> str:
    """Time-bucketed HMAC token bound to version + IP + User-Agent."""
    bucket = int(time.time()) // _CHALLENGE_TTL
    sig    = _hmac_sig(secret, f"yume:{_CHALLENGE_VER}:{bucket}:{ip}:{ua[:64]}")
    return f"{_CHALLENGE_VER}.{bucket}.{sig}"


def _verify_challenge_token(token: str, secret: str, ip: str, ua: str) -> bool:
    try:
        ver, bucket_str, sig = token.split('.')
        if ver != _CHALLENGE_VER:
            return False
        bucket = int(bucket_str)
        if abs(int(time.time()) // _CHALLENGE_TTL - bucket) > 2:
            return False
        expected = _hmac_sig(secret, f"yume:{_CHALLENGE_VER}:{bucket}:{ip}:{ua[:64]}")
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False


def _verify_pow(challenge: str, solution: str) -> bool:
    """Verify FNV-1a(challenge + solution) starts with `_POW_DIFFICULTY` hex zeros."""
    try:
        s = f"{challenge}{int(solution)}"
        h = 0x811c9dc5
        for c in s.encode():
            h ^= c
            h  = (h * 0x01000193) & 0xFFFFFFFF
        return format(h, '08x').startswith('0' * _POW_DIFFICULTY)
    except Exception:
        return False


def _make_page_token(secret: str, ip: str) -> str:
    bucket = int(time.time()) // _PAGE_TOKEN_TTL
    sig    = _hmac_sig(secret, f"pt:{bucket}:{ip}", length=20)
    return f"{bucket}.{sig}"


def _verify_page_token(token: str, secret: str, ip: str) -> bool:
    try:
        bucket_str, sig = token.split('.', 1)
        bucket = int(bucket_str)
        if abs(int(time.time()) // _PAGE_TOKEN_TTL - bucket) > 2:
            return False
        expected = _hmac_sig(secret, f"pt:{bucket}:{ip}", length=20)
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False


def _client_ip() -> str:
    """Extract real client IP, respecting reverse-proxy forwarding."""
    return request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()


# ── App factory ───────────────────────────────────────────────────────────────

def create_app():
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config)

    try:
        Config.validate()
    except (AttributeError, Exception):
        pass

    # Secret key ---------------------------------------------------------------
    if not app.config.get("SECRET_KEY"):
        env_secret = os.environ.get("FLASK_KEY") or os.environ.get("SECRET_KEY")
        if env_secret:
            app.config["SECRET_KEY"] = env_secret
        else:
            app.config["SECRET_KEY"] = secrets.token_urlsafe(64)
            app.logger.warning(
                "No SECRET_KEY set — using auto-generated key. Set FLASK_KEY in production."
            )

    global _CHALLENGE_SECRET
    _CHALLENGE_SECRET = os.environ.get("CHALLENGE_SECRET") or app.config["SECRET_KEY"]

    # Logging ------------------------------------------------------------------
    log_level_name = getattr(Config, "LOG_LEVEL", None) or os.environ.get("LOG_LEVEL", "INFO")
    logging.basicConfig(level=getattr(logging, log_level_name.upper(), logging.INFO))

    # Session cookies ----------------------------------------------------------
    is_debug = bool(app.config.get("DEBUG") or app.debug)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=not is_debug,
        TEMPLATES_AUTO_RELOAD=is_debug,
    )

    # Jinja2 filters (pre-compiled regex at module level) ----------------------
    app.jinja_env.filters['regex_replace'] = (
        lambda s, pat, rep: re.sub(pat, rep, str(s)) if s is not None else ''
    )
    app.jinja_env.filters['strip_anime_id'] = (
        lambda s: _RE_STRIP_ANIME_ID.sub('', str(s)) if s is not None else ''
    )

    # Extensions & scraper -----------------------------------------------------
    app.ha_scraper = UnifiedScraper()
    limiter.init_app(app)

    # Blueprints ---------------------------------------------------------------
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp,      url_prefix='/auth')
    app.register_blueprint(watchlist_bp, url_prefix='/watchlist')
    app.register_blueprint(api_bp,       url_prefix='/api')

    # ── Context processor ─────────────────────────────────────────────────────
    @app.context_processor
    def inject_page_token():
        """Inject signed page token into every HTML template as a meta tag."""
        return dict(page_token=_make_page_token(_CHALLENGE_SECRET, _client_ip()))

    # ── JS Challenge ──────────────────────────────────────────────────────────
    @app.route('/_challenge')
    def js_challenge():
        """
        Layer 1 — JS execution gate (curl/wget can't run JS).
        Layer 2 — Proof-of-Work (adds CPU cost, deters bots).
        """
        next_url = request.args.get('next', '/')
        if not next_url.startswith('/') or next_url.startswith('//'):
            next_url = '/'

        ip    = _client_ip()
        ua    = request.headers.get('User-Agent', '')
        nonce = _make_challenge_token(_CHALLENGE_SECRET, ip, ua)

        # Obfuscate nonce: XOR + base64, split into 3 parts
        xored = bytes([b ^ _XOR_KEY[i % len(_XOR_KEY)] for i, b in enumerate(nonce.encode())])
        enc_n = base64.b64encode(xored).decode()
        c     = len(enc_n) // 3
        p1, p2, p3 = enc_n[:c], enc_n[c:2*c], enc_n[2*c:]
        enc_x  = base64.b64encode(next_url.encode()).decode()
        pow_ch = secrets.token_hex(8)

        html = (
            "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
            "<title>Checking your browser\u2026</title>"
            "<style>body{margin:0;background:#0d0d0d;display:flex;align-items:center;"
            "justify-content:center;height:100vh;font-family:monospace;color:#888;}</style>"
            "</head><body><p>Verifying browser\u2026</p><script>\n"
            "!function(){\n"
            f"  var _a={p1!r},_b={p2!r},_c={p3!r};\n"
            f"  var _k=[{_XOR_KEY_STR}];\n"
            f"  var _x={enc_x!r};\n"
            f"  var _pw={pow_ch!r};\n"
            "  var _atob=function(s){try{return atob(s);}catch(e){return '';}};\n"
            "  var _xd=function(s){var b=_atob(s),o='';\n"
            "    for(var i=0;i<b.length;i++)o+=String.fromCharCode(b.charCodeAt(i)^_k[i%_k.length]);\n"
            "    return o;};\n"
            "  var _n=_xd(_a+_b+_c);\n"
            "  var _u=_atob(_x);\n"
            "  var _h=function(s){var h=0x811c9dc5>>>0,i=0;"
            "for(;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,0x01000193)>>>0;}"
            "return h.toString(16).padStart(8,'0');};\n"
            "  var _sol=0;while(_sol<500000){if(_h(_pw+_sol).slice(0,2)==='00')break;_sol++;}\n"
            "  fetch('/_verify',{\n"
            "    method:'POST',credentials:'same-origin',\n"
            "    headers:{'Content-Type':'application/json'},\n"
            "    body:JSON.stringify({n:_n,x:_u,pw_c:_pw,pw_s:_sol})\n"
            "  }).then(function(r){return r.json();}).then(function(d){\n"
            "    if(d.ok)window.location.replace(d.x||'//');\n"
            "    else window.location.replace('/');\n"
            "  }).catch(function(){window.location.replace('/');});\n"
            "}();\n"
            "</script></body></html>"
        )
        resp = make_response(html, 200)
        resp.headers['Content-Type']  = 'text/html; charset=utf-8'
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        resp.headers['Pragma']        = 'no-cache'
        return resp

    @app.route('/_verify', methods=['POST'])
    @limiter.limit("10 per minute")   # Layer 5 — stops brute-force PoW bypass
    def js_verify():
        """Verify HMAC nonce + PoW, then set HttpOnly challenge cookie and page token."""
        data     = request.get_json(silent=True) or {}
        nonce    = data.get('n', '')
        next_url = data.get('x', '/')
        pow_c    = data.get('pw_c', '')
        pow_s    = str(data.get('pw_s', ''))

        if not next_url.startswith('/') or next_url.startswith('//'):
            next_url = '/'

        ip = _client_ip()
        ua = request.headers.get('User-Agent', '')

        if not _verify_challenge_token(nonce, _CHALLENGE_SECRET, ip, ua):
            app.logger.warning(f"/_verify: invalid nonce from {ip}")
            return jsonify(ok=False, e='nonce'), 403

        if not _verify_pow(pow_c, pow_s):
            app.logger.warning(f"/_verify: invalid PoW from {ip}")
            return jsonify(ok=False, e='pow'), 403

        is_secure   = not is_debug
        fresh_token = _make_challenge_token(_CHALLENGE_SECRET, ip, ua)
        page_token  = _make_page_token(_CHALLENGE_SECRET, ip)

        resp = make_response(jsonify(ok=True, x=next_url), 200)
        resp.set_cookie(
            _CHALLENGE_COOKIE, fresh_token,
            max_age=_CHALLENGE_TTL * 2, httponly=True,
            secure=is_secure, samesite='Lax', path='/',
        )
        resp.set_cookie(
            '__pt', page_token,
            max_age=_PAGE_TOKEN_TTL * 2, httponly=False,  # JS must read for X-PT header
            secure=is_secure, samesite='Lax', path='/',
        )
        return resp

    # ── Before-request hooks ──────────────────────────────────────────────────
    @app.before_request
    def js_challenge_gate():
        """Gate every HTML page load behind the JS challenge."""
        if any(request.path.startswith(p) for p in _CHALLENGE_SKIP_PREFIXES):
            return
        if not request.accept_mimetypes.accept_html:
            return
        ip = _client_ip()
        ua = request.headers.get('User-Agent', '')
        if _verify_challenge_token(request.cookies.get(_CHALLENGE_COOKIE, ''), _CHALLENGE_SECRET, ip, ua):
            return  # ✅ valid cookie — real browser
        app.logger.info(f"JS challenge: PATH={request.path} IP={ip} UA={ua[:80]}")
        return redirect(f'/_challenge?next={request.path}', 302)

    @app.before_request
    def block_obvious_bots():
        """Block well-known bot User-Agents on all non-static routes."""
        if request.path.startswith('/static/'):
            return
        ua = request.headers.get('User-Agent', '').lower()
        if not ua or any(sig in ua for sig in _BOT_SIGNATURES):
            app.logger.warning(f"Blocked bot UA='{ua[:80]}' PATH={request.path} IP={request.remote_addr}")
            abort(403)

    @app.before_request
    def check_api_page_token():
        """Require valid X-PT header on /api/ calls — prevents direct API scraping."""
        if not request.path.startswith('/api/') or request.path.startswith('/api/auth/'):
            return
        ip    = _client_ip()
        token = request.headers.get('X-PT', '') or request.cookies.get('__pt', '')
        if not token or not _verify_page_token(token, _CHALLENGE_SECRET, ip):
            return jsonify(error='Forbidden', message='Missing page token'), 403

    @app.before_request
    def hydrate_legacy_sessions():
        """Backfill avatar/anilist fields missing from older sessions."""
        if '_id' not in session or 'anilist_authenticated' in session:
            return  # nothing to do — fast exit
        try:
            user = get_user_by_id(session['_id'])
            if user:
                session['anilist_authenticated'] = bool(user.get('anilist_id'))
                session['avatar']                = user.get('avatar')
                if user.get('anilist_id'):
                    session['anilist_id'] = user['anilist_id']
                session.modified = True
        except Exception as e:
            app.logger.error(f"Session hydration error for {session.get('_id')}: {e}")

    # ── Error handlers ────────────────────────────────────────────────────────
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