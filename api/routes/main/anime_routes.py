"""
Anime information and episodes routes
"""
import asyncio
from flask import Blueprint, request, render_template, current_app

anime_routes_bp = Blueprint('anime_routes', __name__)


@anime_routes_bp.route('/anime/<anime_id>', methods=['GET'])
def anime_info(anime_id: str):
    """Fetch and display anime information"""
    current_path = request.path
    get_info_method = getattr(current_app.ha_scraper, "get_anime_info", None)
    if not get_info_method:
        return "Anime info function not found", 500
    
    anime_info = asyncio.run(get_info_method(anime_id))
    if not anime_info:
        return f"No info found for anime ID: {anime_id}", 404
    
    # Normalize: if the payload nests under "info", extract it
    if isinstance(anime_info, dict) and "info" in anime_info and isinstance(anime_info["info"], dict):
        anime = anime_info["info"]
    else:
        anime = anime_info
    
    # Safety: ensure an 'id' exists
    anime.setdefault("id", anime_id)
    suggestions = {
        "related": anime.get("relatedAnimes", []),
        "recommended": anime.get("recommendedAnimes", []),
    }

    current_app.logger.debug("Rendering anime page for id=%s, anime keys=%s", anime.get("id"), list(anime.keys()))
    return render_template(
        "info.html",
        anime=anime,
        suggestions=suggestions,
        current_path=current_path,
        current_season_id=anime_id
    )



