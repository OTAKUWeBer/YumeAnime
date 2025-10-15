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


@anime_routes_bp.route('/episodes/<anime_id>', methods=['GET'])
def episodes(anime_id: str):
    """Fetch and display episodes for the selected anime"""
    info = "Episodes"
    suggestions = {"data": {"spotlightAnimes": []}}

    try:
        # Fetch anime info
        anime_info = asyncio.run(current_app.ha_scraper.get_anime_info(anime_id))
        current_app.logger.debug("episodes() - got anime_info for %s: %s", anime_id, bool(anime_info))
        if not anime_info:
            return render_template(
                'index.html',
                error=f"Anime with ID {anime_id} not found.",
                suggestions=suggestions,
                info=info
            )

        # Fetch episodes
        ep_data = asyncio.run(current_app.ha_scraper.get_episodes(anime_id))
        current_app.logger.debug("episodes() - ep_data type=%s, repr=%s", type(ep_data), repr(ep_data)[:800])

        if not isinstance(ep_data, dict):
            raise RuntimeError(f"get_episodes returned non-dict: {type(ep_data)}")

        episodes_list = ep_data.get("episodes", [])

        # Prepare episodes: tuple (episode_url, episode_number, episode_title)
        episodes = [
            (
                ep.get("episodeId", "#"),
                ep.get("number", idx + 1),
                ep.get("title", f"Episode {idx + 1}")
            )
            for idx, ep in enumerate(episodes_list)
        ]

        total_sub_episodes = ep_data.get("total_sub_episodes", len(episodes_list))
        total_dub_episodes = ep_data.get("total_dub_episodes", 0)

        # Prepare other display info
        genre = anime_info.get("genres", []) if isinstance(anime_info, dict) else []

        return render_template(
            'episodes.html',
            title=anime_info.get("title", "Unknown Title") if isinstance(anime_info, dict) else "Unknown Title",
            status=anime_info.get("status", "Unknown") if isinstance(anime_info, dict) else "Unknown",
            genre=", ".join(genre),
            total_episodes=len(episodes),
            total_sub_episodes=total_sub_episodes,
            total_dub_episodes=total_dub_episodes,
            anime_id=anime_id,
            episodes=episodes,
            suggestions=suggestions,
            info=info
        )

    except Exception as e:
        current_app.logger.exception("Error in episodes(%s): %s", anime_id, e)
        return render_template(
            'index.html',
            error=f"Error fetching episodes for {anime_id}: {e}",
            suggestions=suggestions,
            info=info
        )
