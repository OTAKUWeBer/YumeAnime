"""
Manga API routes — optimized JSON endpoints for manga data and image proxy.
"""

import logging
from urllib.parse import urlparse

import requests as std_requests
from flask import Blueprint, jsonify, request, Response, stream_with_context

from api.providers.manga import MangaScraper

logger = logging.getLogger(__name__)

manga_api_bp = Blueprint("manga_api", __name__)

# Only allow trusted image hosts
ALLOWED_IMAGE_DOMAINS = (
    "atsumaru.me",
    "atsu.moe",
    "mangadex.org",
)


# =========================
# API ROUTES
# =========================

@manga_api_bp.route("/home", methods=["GET"])
def manga_home_api():
    source = request.args.get("source", "atsumaru")

    try:
        data = MangaScraper.home(source)

        response = jsonify({
            "success": True,
            "source": source,
            "data": data
        })

        # Cache homepage briefly
        response.headers["Cache-Control"] = (
            "public, max-age=300, s-maxage=1800"
        )

        return response

    except Exception as e:
        logger.error(f"Manga home API error: {e}")

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@manga_api_bp.route("/search", methods=["GET"])
def manga_search_api():
    query = request.args.get("q", "").strip()
    source = request.args.get("source", "atsumaru")

    if not query:
        return jsonify({
            "success": False,
            "error": "Query is required"
        }), 400

    try:
        data = MangaScraper.search(query, source)

        response = jsonify({
            "success": True,
            "source": source,
            "data": data
        })

        # Search changes often
        response.headers["Cache-Control"] = (
            "public, max-age=60, s-maxage=300"
        )

        return response

    except Exception as e:
        logger.error(f"Manga search API error: {e}")

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@manga_api_bp.route("/<source>/<path:manga_id>/details", methods=["GET"])
def manga_details_api(source, manga_id):
    try:
        data = MangaScraper.details(manga_id, source)

        if data is None:
            return jsonify({
                "success": False,
                "error": "Manga not found"
            }), 404

        response = jsonify({
            "success": True,
            "source": source,
            "data": data
        })

        # Details don't change often
        response.headers["Cache-Control"] = (
            "public, max-age=1800, s-maxage=7200"
        )

        return response

    except Exception as e:
        logger.error(f"Manga details API error: {e}")

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@manga_api_bp.route(
    "/<source>/<path:manga_id>/<chapter_id>/images",
    methods=["GET"]
)
def manga_chapter_images_api(source, manga_id, chapter_id):
    try:
        images, referer = MangaScraper.chapter_images(
            manga_id,
            chapter_id,
            source
        )

        response = jsonify({
            "success": True,
            "source": source,
            "data": {
                "images": images,
                "referer": referer
            }
        })

        # Chapter image lists almost never change
        response.headers["Cache-Control"] = (
            "public, max-age=86400, s-maxage=604800"
        )

        return response

    except Exception as e:
        logger.error(f"Manga chapter images API error: {e}")

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@manga_api_bp.route("/sources", methods=["GET"])
def manga_sources_api():
    response = jsonify({
        "success": True,
        "sources": MangaScraper.get_sources()
    })

    response.headers["Cache-Control"] = (
        "public, max-age=86400"
    )

    return response


# =========================
# IMAGE PROXY
# =========================

@manga_api_bp.route("/image-proxy", methods=["GET"])
def manga_image_proxy():
    """
    Optimized manga image proxy with:
    - streaming
    - long-term CDN caching
    - domain protection
    - reduced memory usage
    """

    image_url = request.args.get("url", "").strip()
    referer = request.args.get("referer", "").strip()

    if not image_url:
        return jsonify({
            "error": "Missing url parameter"
        }), 400

    # Validate domain
    parsed = urlparse(image_url)
    hostname = parsed.hostname

    if not hostname or hostname not in ALLOWED_IMAGE_DOMAINS:
        return jsonify({
            "error": "Domain not allowed"
        }), 403

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0)"
        ),
        "Accept": "image/*,*/*;q=0.8",
    }

    if referer:
        headers["Referer"] = referer.rstrip("/") + "/"

    try:
        # Try curl_cffi first
        try:
            from curl_cffi import requests as cffi_requests

            try:
                upstream = cffi_requests.get(
                    image_url,
                    headers=headers,
                    impersonate="chrome124",
                    stream=True,
                    timeout=20
                )
            except Exception:
                upstream = std_requests.get(
                    image_url,
                    headers=headers,
                    stream=True,
                    timeout=20
                )

        except ImportError:
            upstream = std_requests.get(
                image_url,
                headers=headers,
                stream=True,
                timeout=20
            )

        upstream.raise_for_status()

        content_type = upstream.headers.get(
            "Content-Type",
            "image/jpeg"
        )

        def generate():
            for chunk in upstream.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

        response = Response(
            stream_with_context(generate()),
            content_type=content_type
        )

        # 1 YEAR CACHE
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable"
        )

        response.headers["CDN-Cache-Control"] = (
            "max-age=31536000"
        )

        response.headers["Vercel-CDN-Cache-Control"] = (
            "max-age=31536000"
        )

        response.headers["Access-Control-Allow-Origin"] = "*"

        # Forward cache validation headers
        if "ETag" in upstream.headers:
            response.headers["ETag"] = upstream.headers["ETag"]

        if "Last-Modified" in upstream.headers:
            response.headers["Last-Modified"] = (
                upstream.headers["Last-Modified"]
            )

        return response

    except Exception as e:
        logger.error(f"Image proxy error for {image_url}: {e}")

        return jsonify({
            "error": "Failed to fetch image"
        }), 502