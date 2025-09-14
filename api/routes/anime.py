"""
Anime routes blueprint - handles anime info, episodes, and watch functionality
File: api/routes/anime.py

Route Structure:
- /anime/<anime_id> (GET) - Anime information page
- /anime/episodes/<anime_id> (GET) - Episodes list page
- /anime/watch/<eps_title> (GET) - Watch episode page
"""
from flask import Blueprint, render_template, request, redirect, url_for
from urllib.parse import parse_qs
import asyncio
import logging

from ..scrapers import HianimeScraper

anime_bp = Blueprint('anime_bp', __name__)
HA = HianimeScraper()
logger = logging.getLogger(__name__)


@anime_bp.route('/<anime_id>', methods=['GET'])
async def anime_info(anime_id: str):
    """
    Fetch and display anime information
    GET /anime/<anime_id>
    """
    current_path = request.path
    
    try:
        get_info_method = getattr(HA, "get_anime_info", None)
        if not get_info_method:
            return "Anime info function not found", 500
        
        anime_info = await get_info_method(anime_id)
        if not anime_info:
            return f"No info found for anime ID: {anime_id}", 404
        
        # Normalize: if the payload nests under "info", extract it
        if isinstance(anime_info, dict) and "info" in anime_info and isinstance(anime_info["info"], dict):
            anime = anime_info["info"]
        else:
            anime = anime_info
        
        # Safety: ensure an 'id' exists so template doesn't blow up
        anime.setdefault("id", anime_id)
        
        suggestions = {
            "related": anime.get("relatedAnimes", []),
            "recommended": anime.get("recommendedAnimes", [])
        }
        
        logger.debug("Rendering anime page for id=%s, anime keys=%s", anime.get("id"), list(anime.keys()))
        
        return render_template(
            "info.html",
            anime=anime,
            suggestions=suggestions,
            current_path=current_path,
            current_season_id=anime_id
        )
        
    except Exception as e:
        logger.error(f"Error fetching anime info for {anime_id}: {e}")
        return render_template('404.html', error_message=f"Error loading anime: {e}"), 500


@anime_bp.route('/episodes/<anime_id>', methods=['GET'])
async def episodes(anime_id: str):
    """
    Fetch and display episodes for the selected anime
    GET /anime/episodes/<anime_id>
    """
    info = "Episodes"
    suggestions = {}
    
    try:
        # Fetch anime info
        anime_info = await HA.get_anime_info(anime_id)
        if not anime_info:
            return render_template(
                'index.html',
                error=f"Anime with ID {anime_id} not found.",
                suggestions=suggestions,
                info=info
            )

        # Fetch episodes
        ep_data = await HA.get_episodes(anime_id)
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
        genre = anime_info.get("genres", [])

        return render_template(
            'episodes.html',
            title=anime_info.get("title", "Unknown Title"),
            status=anime_info.get("status", "Unknown"),
            genre=", ".join(genre),
            total_episodes=len(episodes),
            total_sub_episodes=total_sub_episodes,
            total_dub_episodes=total_dub_episodes,
            anime_id=anime_id,
            episodes=episodes
        )

    except Exception as e:
        logger.error(f"Error fetching episodes for {anime_id}: {e}")
        return render_template(
            'index.html',
            error=f"Error fetching episodes: {e}",
            suggestions=suggestions,
            info=info
        )


@anime_bp.route('/watch/<eps_title>', methods=['GET'])
async def watch(eps_title):
    """
    Watch episode page with video player
    GET /anime/watch/<eps_title>?ep=<episode_param>
    """
    ep_param = request.args.get("ep")  # e.g. "141637" or "141637-sub"

    # Parse episode number and language
    ep_number, lang = None, "sub"
    if ep_param:
        parts = ep_param.split("-", 1)
        ep_number = parts[0]
        if len(parts) > 1:
            lang = parts[1]

    try:
        # Check if dub is available
        dub_available = await HA.is_dub_available(eps_title, ep_number)
        
        # Redirect to sub if dub requested but not available
        if lang == "dub" and not dub_available:
            return redirect(url_for('anime.watch', eps_title=eps_title, ep=f"{ep_number}-sub"))

        # Get video embed URL
        raw = await HA.video(ep_number, lang, fetch_url=False)
        embed_url = raw.get("embed_url") if isinstance(raw, dict) else raw
        if not embed_url and isinstance(raw, dict):
            embed_url = raw.get("url") or next(iter(raw.values()), None)

        # Fetch episodes list
        eps_title_clean = eps_title.split('?', 1)[0]
        
        try:
            all_episodes = await HA.episodes(eps_title_clean)
        except Exception as e:
            logger.warning(f"Failed to fetch episodes list: {e}")
            all_episodes = None

        # Build previous/next episode URLs
        prev_episode_url = next_episode_url = None
        prev_episode_number = next_episode_number = None
        Episode = "Special"
        episode_number = None
        eps_list = all_episodes.get("episodes", []) if all_episodes else []

        ep_base = ep_number or (ep_param.split('-', 1)[0] if ep_param else None)
        current_idx = None

        if ep_base and eps_list:
            for i, item in enumerate(eps_list):
                eid = item.get("episodeId", "")
                val = parse_qs(eid.split("?", 1)[1]).get("ep", [None])[0] if "?" in eid else eid
                if str(val) == str(ep_base):
                    current_idx = i
                    break

        if current_idx is not None:
            current_item = eps_list[current_idx]
            episode_number = current_item.get("number")
            Episode = str(episode_number) if episode_number else "Special"

            def build_episode_url(item_idx):
                item = eps_list[item_idx]
                eid = item.get("episodeId", "")
                ep_val = parse_qs(eid.split("?", 1)[1]).get("ep", [None])[0] if "?" in eid else eid
                slug = eid.split("?", 1)[0] if "?" in eid else eps_title_clean
                return url_for('anime.watch', eps_title=slug, ep=f"{ep_val}-{lang}") if ep_val else None

            if current_idx > 0:
                prev_episode_url = build_episode_url(current_idx - 1)
                prev_episode_number = eps_list[current_idx - 1].get("number")
            if current_idx < len(eps_list) - 1:
                next_episode_url = build_episode_url(current_idx + 1)
                next_episode_number = eps_list[current_idx + 1].get("number")

        # Language switch URLs
        sub_url = url_for('anime.watch', eps_title=eps_title_clean, ep=f"{ep_number}-sub") if ep_number else None
        dub_url = url_for('anime.watch', eps_title=eps_title_clean, ep=f"{ep_number}-dub") if ep_number and dub_available else None

        # Render watch page
        return render_template('watch.html',
                               back_to_ep=eps_title_clean,
                               video_link=embed_url,
                               Episode=Episode,
                               episode_number=episode_number,
                               prev_episode_url=prev_episode_url,
                               next_episode_url=next_episode_url,
                               prev_episode_number=prev_episode_number,
                               next_episode_number=next_episode_number,
                               eps_title=eps_title,
                               lang=lang,
                               episodes=all_episodes,
                               dub_available=dub_available,
                               sub_url=sub_url,
                               dub_url=dub_url)

    except Exception as e:
        logger.error(f"Watch error for {eps_title}: {e}")
        return render_template('404.html', error_message="An error occurred while fetching the episode."), 500