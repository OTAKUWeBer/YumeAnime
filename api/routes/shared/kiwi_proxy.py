"""
Generic backend proxy for HLS streams.

Route: GET /api/proxy/<target_url>

Example:
  /api/proxy/https://cluster.lunaranime.ru/api/proxy/hls/custom?url=...&referer=...

The proxy:
  1. Reconstructs the full target URL (path + query string)
  2. Fetches it with the same headers Chrome sends to cluster
  3. In m3u8 responses, rewrites any https://cluster.lunaranime.ru URLs
     to /api/proxy/https://cluster.lunaranime.ru/... so segments also
     flow through us.
  4. Streams segment/key responses chunk-by-chunk to avoid buffering.
  5. Returns the response with CORS headers.
"""

import logging
import re

import requests
from flask import Blueprint, request, Response

logger = logging.getLogger(__name__)

kiwi_proxy_bp = Blueprint("kiwi_proxy", __name__)

# ── Persistent session for connection pooling ──
# Reusing TCP connections dramatically reduces latency for sequential
# segment fetches that hit the same upstream host.
_session = requests.Session()
_session.verify = False
# Allow up to 20 concurrent connections per host
adapter = requests.adapters.HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
    max_retries=1,
)
_session.mount("https://", adapter)
_session.mount("http://", adapter)

# Timeout for upstream requests (connect, read)
_UPSTREAM_TIMEOUT = (10, 30)

# Chunk size for streaming segment data (64 KB)
_STREAM_CHUNK_SIZE = 65536

# Domains whose URLs we rewrite inside m3u8 manifests
_REWRITE_DOMAINS = [
    "https://cluster.lunaranime.ru",
    "http://cluster.lunaranime.ru",
]

# The proxy prefix we add — used to prevent double-rewriting
_PROXY_PREFIX = "/api/proxy/"


def _fix_merged_slashes(url: str) -> str:
    """
    Flask/Werkzeug merges consecutive slashes in paths, so
    'https://host' in the <path:target> becomes 'https:/host'.
    Restore the double slash after the scheme.
    """
    if url.startswith("https:/") and not url.startswith("https://"):
        url = "https://" + url[7:]
    elif url.startswith("http:/") and not url.startswith("http://"):
        url = "http://" + url[6:]
    return url


def _build_upstream_headers(upstream_url: str) -> dict:
    """
    Build headers that match what Chrome sends when playing
    directly from cluster.lunaranime.ru.
    """
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/147.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "video",
        "sec-fetch-mode": "no-cors",
        "sec-fetch-site": "same-origin",
    }


def _rewrite_m3u8(body: str) -> str:
    """
    Rewrite cluster URLs in the m3u8 body so they route through our proxy.
    e.g.  https://cluster.lunaranime.ru/api/proxy/hls/custom?url=X&referer=Y
      =>  /api/proxy/https://cluster.lunaranime.ru/api/proxy/hls/custom?url=X&referer=Y

    Guards against double-rewriting by first undoing any existing proxy
    prefixes (shouldn't normally happen, but protects against edge cases).
    """
    for domain in _REWRITE_DOMAINS:
        # Prevent double-rewriting: strip any existing proxy prefix first
        body = body.replace(f"{_PROXY_PREFIX}{domain}", domain)
        # Now apply the rewrite
        body = body.replace(domain, f"{_PROXY_PREFIX}{domain}")
    return body


# ── Standard CORS headers applied to every response ──
_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Range, Content-Type",
    "Access-Control-Expose-Headers": "Content-Length, Content-Range, Accept-Ranges",
}


@kiwi_proxy_bp.route("/proxy/<path:target>", methods=["GET", "OPTIONS"])
def proxy_passthrough(target: str):
    """
    Proxy any URL.  The full target URL is reconstructed from the path
    variable + the raw query string.

    Example request:
      GET /api/proxy/https://cluster.lunaranime.ru/api/proxy/hls/custom?url=...&referer=...
    """
    # Handle CORS preflight
    if request.method == "OPTIONS":
        return Response("", status=204, headers=_CORS_HEADERS)

    # Reconstruct the full upstream URL
    # Fix Flask's merged slashes: https:/ → https://
    target = _fix_merged_slashes(target)
    qs = request.query_string.decode("utf-8")
    upstream_url = target if not qs else f"{target}?{qs}"

    if not upstream_url.startswith("http"):
        return Response("Target must be an absolute URL", status=400)

    logger.info("[Proxy] → %s", upstream_url[:200])

    headers = _build_upstream_headers(upstream_url)

    # Forward Range header (Chrome sends "Range: bytes=0-" for segments)
    range_header = request.headers.get("Range")
    if range_header:
        headers["Range"] = range_header

    try:
        upstream_resp = _session.get(
            upstream_url,
            headers=headers,
            timeout=_UPSTREAM_TIMEOUT,
            stream=True,
        )
    except requests.RequestException as exc:
        logger.error("[Proxy] Upstream failed: %s — %s", upstream_url[:160], exc)
        return Response(f"Upstream request failed: {exc}", status=502)

    content_type = upstream_resp.headers.get("Content-Type", "")
    content_length = upstream_resp.headers.get("Content-Length")
    logger.info("[Proxy] ← %s  ct=%s  len=%s",
                upstream_resp.status_code, content_type,
                content_length or "?")

    # ── m3u8 manifests: rewrite cluster URLs → local proxy ──
    is_m3u8 = "mpegurl" in content_type.lower() or upstream_url.endswith(".m3u8")
    if is_m3u8:
        body = upstream_resp.text
        upstream_resp.close()
        rewritten = _rewrite_m3u8(body)

        resp_headers = {
            "Content-Type": "application/vnd.apple.mpegurl",
            "Cache-Control": "no-cache, no-store",
        }
        resp_headers.update(_CORS_HEADERS)
        return Response(rewritten, status=upstream_resp.status_code, headers=resp_headers)

    # ── Segments / keys: STREAM through chunk by chunk ──
    # This is critical: instead of buffering the entire segment (which
    # blocks until the full file downloads from the double-hop), we pipe
    # chunks as they arrive. HLS.js starts processing immediately.
    excluded = {
        "transfer-encoding", "content-encoding", "connection",
        "content-disposition",  # prevents HLS.js from reading key files
    }
    resp_headers = {
        k: v for k, v in upstream_resp.headers.items() if k.lower() not in excluded
    }
    resp_headers.update(_CORS_HEADERS)

    # For AES-128 key files, force proper content-type
    if ".key" in upstream_url or "mon.key" in upstream_url:
        content_type = "application/octet-stream"

    # Generator that streams chunks from upstream → client
    def stream_upstream():
        try:
            for chunk in upstream_resp.iter_content(chunk_size=_STREAM_CHUNK_SIZE):
                if chunk:
                    yield chunk
        finally:
            upstream_resp.close()

    return Response(
        stream_upstream(),
        status=upstream_resp.status_code,
        headers=resp_headers,
        content_type=content_type or "application/octet-stream",
    )
