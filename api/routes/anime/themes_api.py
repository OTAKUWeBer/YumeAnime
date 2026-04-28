"""
AnimeThemes API proxy routes.
Fetches opening/ending theme data from https://api.animethemes.moe
"""
import aiohttp
import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

themes_api_bp = Blueprint('themes_api', __name__)

ANIMETHEMES_BASE = "https://api.animethemes.moe"
ANIMETHEMES_INCLUDES = "animethemes.song.artists,animethemes.animethemeentries.videos,images"


async def _fetch_themes_by_slug(slug: str) -> dict:
    """Fetch anime themes from AnimeThemes API using the anime slug."""
    url = f"{ANIMETHEMES_BASE}/anime/{slug}?include={ANIMETHEMES_INCLUDES}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("anime", {})
                return {}
    except Exception as e:
        logger.error(f"Error fetching themes for slug '{slug}': {e}")
        return {}


async def _search_anime_slug(title: str) -> str:
    """Search AnimeThemes for an anime by title and return the best-matching slug."""
    url = f"{ANIMETHEMES_BASE}/search?q={title}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    anime_list = data.get("search", {}).get("anime", [])
                    if anime_list:
                        # Try exact match first
                        title_lower = title.lower().strip()
                        for anime in anime_list:
                            if anime.get("name", "").lower().strip() == title_lower:
                                return anime.get("slug", "")
                        # Fallback to first result
                        return anime_list[0].get("slug", "")
                return ""
    except Exception as e:
        logger.error(f"Error searching AnimeThemes for '{title}': {e}")
        return ""


def _parse_themes(anime_data: dict) -> dict:
    """Parse raw AnimeThemes API data into a clean openings/endings structure."""
    themes = anime_data.get("animethemes", [])
    openings = []
    endings = []

    for theme in themes:
        theme_type = theme.get("type", "")
        sequence = theme.get("sequence", 1)
        slug = theme.get("slug", "")

        song = theme.get("song", {}) or {}
        song_title = song.get("title", "Unknown")
        artists = song.get("artists", []) or []
        artist_names = []
        for artist in artists:
            name = artist.get("name", "")
            alias = ""
            artist_song = artist.get("artistsong", {}) or {}
            if artist_song.get("as"):
                alias = artist_song["as"]
            artist_names.append({"name": name, "as": alias})

        # Get entries and their videos
        entries = theme.get("animethemeentries", []) or []
        videos = []
        episodes_str = ""
        for entry in entries:
            if not episodes_str:
                episodes_str = entry.get("episodes", "")
            entry_videos = entry.get("videos", []) or []
            for video in entry_videos:
                videos.append({
                    "url": video.get("link", ""),
                    "resolution": video.get("resolution"),
                    "source": video.get("source", ""),
                    "nc": video.get("nc", False),
                    "tags": video.get("tags", ""),
                })

        theme_entry = {
            "slug": slug,
            "title": song_title,
            "sequence": sequence,
            "artists": artist_names,
            "episodes": episodes_str,
            "videos": videos,
        }

        if theme_type == "OP":
            openings.append(theme_entry)
        elif theme_type == "ED":
            endings.append(theme_entry)

    # Sort by sequence
    openings.sort(key=lambda x: x.get("sequence", 0))
    endings.sort(key=lambda x: x.get("sequence", 0))

    # Extract cover image
    images = anime_data.get("images", []) or []
    cover_image = ""
    for img in images:
        facet = (img.get("facet") or "").lower()
        if "large" in facet and img.get("link"):
            cover_image = img["link"]
            break
    if not cover_image:
        for img in images:
            if img.get("link"):
                cover_image = img["link"]
                break

    return {
        "anime_name": anime_data.get("name", ""),
        "anime_slug": anime_data.get("slug", ""),
        "cover_image": cover_image,
        "openings": openings,
        "endings": endings,
    }


@themes_api_bp.route('/api/anime-themes', methods=['GET'])
async def get_anime_themes():
    """
    Fetch anime opening/ending themes from AnimeThemes API.
    Query params:
      - title: anime title to search for
    """
    title = request.args.get('title', '').strip()
    if not title:
        return jsonify({"error": "Missing 'title' parameter"}), 400

    # Step 1: Search for the anime slug
    slug = await _search_anime_slug(title)
    if not slug:
        return jsonify({"openings": [], "endings": [], "anime_name": "", "anime_slug": ""})

    # Step 2: Fetch themes by slug
    anime_data = await _fetch_themes_by_slug(slug)
    if not anime_data:
        return jsonify({"openings": [], "endings": [], "anime_name": "", "anime_slug": ""})

    # Step 3: Parse and return
    result = _parse_themes(anime_data)
    return jsonify(result)
