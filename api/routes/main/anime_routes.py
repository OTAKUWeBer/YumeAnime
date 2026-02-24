"""
Anime information and episodes routes
"""
import asyncio
from flask import Blueprint, request, render_template, current_app

anime_routes_bp = Blueprint('anime_routes', __name__)


@anime_routes_bp.route('/anime/<anime_id>', methods=['GET'])
async def anime_info(anime_id: str):
    """Fetch and display anime information"""
    current_path = request.path
    get_info_method = getattr(current_app.ha_scraper, "get_anime_info", None)
    get_schedule_method = getattr(current_app.ha_scraper, "next_episode_schedule", None)
    
    if not get_info_method:
        return "Anime info function not found", 500
        
    try:
        anime_info, next_episode_schedule = await asyncio.gather(
            get_info_method(anime_id),
            get_schedule_method(anime_id) if get_schedule_method else asyncio.sleep(0),
            return_exceptions=True
        )
    except Exception as e:
        current_app.logger.error(f"Error gathering info for {anime_id}: {e}")
        anime_info, next_episode_schedule = None, None
        
    if isinstance(anime_info, Exception):
        current_app.logger.error(f"Error fetching anime info for {anime_id}: {anime_info}")
        anime_info = None
        
    if isinstance(next_episode_schedule, Exception):
        current_app.logger.error(f"Error fetching anime schedule for {anime_id}: {next_episode_schedule}")
        next_episode_schedule = None
        
    if not anime_info:
        return f"No info found for anime ID: {anime_id}", 404
    
    # Normalize: if the payload nests under "info", extract it
    if isinstance(anime_info, dict) and "info" in anime_info and isinstance(anime_info["info"], dict):
        anime = anime_info["info"]
    else:
        anime = anime_info

    # Auto-save IDs to cache (for Vercel — grows the DB as users browse)
    try:
        from api.utils.id_cache import auto_cache_from_info
        auto_cache_from_info(anime_id, anime)
    except Exception:
        pass
        
    # Fallback to AniList if Hianime next episode schedule isn't available
    # OR if the schedule is expired/in the past (time < 0)
    needs_fallback = False
    if not next_episode_schedule:
        needs_fallback = True
    elif not next_episode_schedule.get("airingTimestamp"):
        needs_fallback = True
    else:
        time_until = next_episode_schedule.get("secondsUntilAiring") or next_episode_schedule.get("timeUntilAiring")
        if time_until is not None:
            try:
                if int(time_until) < 0:
                    needs_fallback = True
            except ValueError:
                needs_fallback = True

    if needs_fallback:
        hianime_al_id = anime.get("anilistId") or anime.get("alID")
        hianime_mal_id = anime.get("malId") or anime.get("malID")
        hianime_title = anime.get("title")
        
        if hianime_al_id or hianime_mal_id or hianime_title:
            try:
                from api.utils.helpers import fetch_anilist_next_episode
                
                fallback_schedule = await fetch_anilist_next_episode(
                    anilist_id=hianime_al_id,
                    mal_id=hianime_mal_id,
                    search_title=hianime_title
                )
                
                if fallback_schedule and fallback_schedule.get("airingTimestamp"):
                    next_episode_schedule = fallback_schedule
            except Exception as e:
                current_app.logger.error(f"Failed to fetch fallback schedule from AniList for {anime_id}: {e}")

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
        next_episode_schedule=next_episode_schedule,
        current_path=current_path,
        current_season_id=anime_id
    )

