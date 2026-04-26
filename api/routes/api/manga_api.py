"""
Manga API routes — JSON endpoints for manga data and image proxy.
"""
import logging

import requests as std_requests
from flask import Blueprint, jsonify, request, Response, stream_with_context

from api.providers.manga import MangaScraper, SOURCES

logger = logging.getLogger(__name__)

manga_api_bp = Blueprint('manga_api', __name__)


@manga_api_bp.route('/home', methods=['GET'])
def manga_home_api():
    """Return manga home page data for a given source."""
    source = request.args.get('source', 'atsumaru')
    try:
        data = MangaScraper.home(source)
        return jsonify({"success": True, "source": source, "data": data})
    except Exception as e:
        logger.error(f"Manga home API error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@manga_api_bp.route('/search', methods=['GET'])
def manga_search_api():
    """Search manga across a specific source."""
    query = request.args.get('q', '').strip()
    source = request.args.get('source', 'atsumaru')
    if not query:
        return jsonify({"success": False, "error": "Query is required"}), 400
    try:
        data = MangaScraper.search(query, source)
        return jsonify({"success": True, "source": source, "data": data})
    except Exception as e:
        logger.error(f"Manga search API error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@manga_api_bp.route('/<source>/<path:manga_id>/details', methods=['GET'])
def manga_details_api(source, manga_id):
    """Return manga details (info + chapter list)."""
    try:
        data = MangaScraper.details(manga_id, source)
        if data is None:
            return jsonify({"success": False, "error": "Manga not found"}), 404
        return jsonify({"success": True, "source": source, "data": data})
    except Exception as e:
        logger.error(f"Manga details API error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@manga_api_bp.route('/<source>/<path:manga_id>/<chapter_id>/images', methods=['GET'])
def manga_chapter_images_api(source, manga_id, chapter_id):
    """Return chapter image URLs."""
    try:
        images, referer = MangaScraper.chapter_images(manga_id, chapter_id, source)
        return jsonify({
            "success": True, "source": source,
            "data": {"images": images, "referer": referer}
        })
    except Exception as e:
        logger.error(f"Manga chapter images API error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@manga_api_bp.route('/sources', methods=['GET'])
def manga_sources_api():
    """Return available manga sources."""
    return jsonify({"success": True, "sources": MangaScraper.get_sources()})


@manga_api_bp.route('/image-proxy', methods=['GET'])
def manga_image_proxy():
    """
    Proxy manga images to bypass referer/hotlinking restrictions.
    Usage: /api/manga/image-proxy?url=<encoded_url>&referer=<referer>
    """
    image_url = request.args.get('url', '')
    referer = request.args.get('referer', '')

    if not image_url:
        return jsonify({"error": "Missing url parameter"}), 400

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
        "Accept": "image/avif,image/webp,image/png,image/svg+xml,image/*;q=0.8,*/*;q=0.5",
        "Accept-Language": "en-US,en;q=0.9",
        "DNT": "1",
        "Sec-Fetch-Dest": "image",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-origin",
        "Connection": "keep-alive",
    }
    if referer:
        headers["Referer"] = referer + "/"

    try:
        # Try curl_cffi first (handles anti-bot sites like Atsumaru)
        try:
            from curl_cffi import requests as cffi_requests
            resp = cffi_requests.get(
                image_url, headers=headers, impersonate="chrome124", timeout=15
            )
            content_type = resp.headers.get('Content-Type', 'image/jpeg')
            return Response(
                resp.content,
                content_type=content_type,
                headers={
                    'Cache-Control': 'public, max-age=86400',
                    'Access-Control-Allow-Origin': '*',
                }
            )
        except ImportError:
            pass

        # Fallback to standard requests
        resp = std_requests.get(image_url, headers=headers, stream=True, timeout=15)
        resp.raise_for_status()

        content_type = resp.headers.get('Content-Type', 'image/jpeg')

        def generate():
            for chunk in resp.iter_content(chunk_size=8192):
                yield chunk

        return Response(
            stream_with_context(generate()),
            content_type=content_type,
            headers={
                'Cache-Control': 'public, max-age=86400',
                'Access-Control-Allow-Origin': '*',
            }
        )
    except Exception as e:
        logger.error(f"Image proxy error for {image_url}: {e}")
        return jsonify({"error": "Failed to fetch image"}), 502
