"""
Watch episode routes — Clean URL format: /watch/<anime_id>/ep-<number>
Server, language, and provider are resolved internally (not in URL).
"""

import asyncio
import json
import re
from flask import (
    Blueprint,
    request,
    session,
    redirect,
    url_for,
    render_template,
    current_app,
    jsonify,
    make_response,
)
from urllib.parse import parse_qs

from ...models.watchlist import get_watchlist_entry

watch_routes_bp = Blueprint("watch_routes", __name__)


def _get_preferred_lang():
    """Get the user's preferred language from cookie → session → default."""
    lang = request.cookies.get("preferred_language")
    if lang in ("sub", "dub"):
        return lang
    return session.get("preferred_language", "sub")


def _get_preferred_provider():
    """Get the user's preferred provider from cookie → session → default."""
    return request.cookies.get("preferred_server") or session.get("last_used_server", None)


def _resolve_episode(episodes_data, ep_number, preferred_provider=None):
    """
    Given episodes data and a target episode number, resolve the full internal
    episode ID and provider info.

    Returns dict with: episode_item, episode_id, provider_name, or None.
    """
    eps_list = episodes_data.get("episodes", []) if episodes_data else []
    providers_map = episodes_data.get("providers_map", {}) if episodes_data else {}
    default_provider = episodes_data.get("default_provider", "kiwi") if episodes_data else "kiwi"

    if not eps_list:
        return None

    # Find the episode item by number
    target_item = None
    target_idx = None
    for i, ep in enumerate(eps_list):
        if str(ep.get("number", "")) == str(ep_number):
            target_item = ep
            target_idx = i
            break

    if target_item is None:
        return None

    # Try to find the episode ID from the preferred provider
    provider_name = preferred_provider or default_provider

    # If the preferred provider doesn't exist, fall back to default
    if provider_name not in providers_map:
        provider_name = default_provider

    return {
        "episode_item": target_item,
        "episode_idx": target_idx,
        "episode_id": target_item.get("episodeId", ""),
        "provider_name": provider_name,
        "eps_list": eps_list,
    }


def _find_episode_id_for_provider(providers_map, provider_name, ep_number, category="sub"):
    """Find the episode ID for a specific provider and episode number."""
    if not providers_map or provider_name not in providers_map:
        return None

    provider_data = providers_map[provider_name]
    episodes_data = provider_data.get("episodes", {})
    cat_episodes = episodes_data.get(category, [])

    for ep in cat_episodes:
        if str(ep.get("number", "")) == str(ep_number):
            return ep.get("id", "")

    return None


def _build_clean_url(anime_id, ep_number):
    """Build a clean episode URL."""
    return f"/watch/{anime_id}/ep-{ep_number}"


def _fetch_video_data(full_slug, lang, server, anilist_id):
    """Fetch video data from the scraper and return structured result."""
    raw = asyncio.run(
        current_app.ha_scraper.video(full_slug, lang, server, anilist_id)
    )

    video_link = None
    subtitle_tracks = []
    intro = outro = None
    video_sources = []
    available_qualities = []
    embed_sources = []
    hls_sources = []
    source_type = None

    if isinstance(raw, dict):
        source_type = raw.get("source_type")
        embed_sources = raw.get("embed_sources", [])
        hls_sources = raw.get("hls_sources", raw.get("sources", []))
        video_link = raw.get("video_link")

        if not source_type:
            if embed_sources:
                source_type = "embed"
            elif video_link or hls_sources:
                source_type = "hls"

        if source_type == "hls" and not video_link:
            sources = raw.get("sources")
            if isinstance(sources, dict):
                video_link = sources.get("file") or sources.get("url")
            elif isinstance(sources, list) and sources:
                first_source = sources[0]
                if isinstance(first_source, dict):
                    video_link = first_source.get("file") or first_source.get("url")
                elif isinstance(first_source, str):
                    video_link = first_source

        all_sources = raw.get("sources", [])
        if isinstance(all_sources, list):
            video_sources = [
                s for s in all_sources if isinstance(s, dict) and s.get("file")
            ]

        available_qualities = raw.get("available_qualities", [])
        subtitle_tracks = raw.get("tracks", [])
        intro = raw.get("intro")
        outro = raw.get("outro")

    return {
        "video_link": video_link,
        "subtitle_tracks": subtitle_tracks,
        "intro": intro,
        "outro": outro,
        "video_sources": video_sources,
        "available_qualities": available_qualities,
        "embed_sources": embed_sources,
        "hls_sources": hls_sources,
        "source_type": source_type,
    }


# ──────────────────────────────────────────────────────────────
#  LEGACY REDIRECT: old ?ep= format → new clean URL
# ──────────────────────────────────────────────────────────────

@watch_routes_bp.route("/watch/<eps_title>", methods=["GET"])
def watch_legacy(eps_title):
    """Handle old URL format and redirect to clean URLs."""
    ep_param = request.args.get("ep")

    # If there's no ?ep= param, this is just /watch/<anime_id> — redirect to best episode
    if not ep_param:
        return _redirect_to_best_episode(eps_title)

    # Try to extract episode number from old ep_param formats
    ep_number = _extract_ep_number_from_legacy(ep_param, eps_title)

    if ep_number is not None:
        return redirect(_build_clean_url(eps_title, ep_number), code=301)

    # If we can't extract, try fetching episodes to resolve
    return _redirect_to_best_episode(eps_title)


def _extract_ep_number_from_legacy(ep_param, anime_id):
    """Try to extract a simple episode number from the old ?ep= format."""
    # Format: watch/kiwi/179062/sub/animepahe-1 → extract trailing number
    if ep_param.startswith("watch/"):
        parts = ep_param.split("/")
        if len(parts) >= 5:
            slug = parts[-1]  # e.g. animepahe-1
            num_match = re.search(r"(\d+)$", slug)
            if num_match:
                return int(num_match.group(1))

    # Format: 12345-sub or just 12345
    parts = ep_param.split("-", 1)
    if parts[0].isdigit():
        return int(parts[0])

    # Try extracting trailing number from any format
    num_match = re.search(r"(\d+)$", ep_param.split("-sub")[0].split("-dub")[0])
    if num_match:
        return int(num_match.group(1))

    return None


def _redirect_to_best_episode(anime_id):
    """
    Redirects to the user's next unwatched episode based on DB history.
    Clamps to released episodes so we never redirect to an unreleased episode.
    """
    anime_id_clean = anime_id.split("?", 1)[0]
    target_ep = 1

    # Fetch released episode count to clamp
    max_released = 0
    try:
        anime_info = asyncio.run(current_app.ha_scraper.get_anime_info(anime_id_clean))
        if isinstance(anime_info, dict):
            info = anime_info.get("info", anime_info) if "info" in anime_info else anime_info
            max_released = info.get("released_episodes") or info.get("total_sub_episodes") or 0
    except Exception as e:
        current_app.logger.error(f"Error fetching anime info for episode clamp: {e}")

    # Check user watchlist for progress if logged in
    if "username" in session and "_id" in session:
        try:
            from api.models.watchlist import get_watchlist_entry
            user_id = session.get("_id")
            watchlist_entry = get_watchlist_entry(user_id, anime_id_clean)

            if watchlist_entry:
                watched_count = watchlist_entry.get("watched_episodes", 0)
                if watched_count > 0:
                    target_ep = watched_count + 1
                    # Clamp to max released episodes
                    if max_released > 0 and target_ep > max_released:
                        target_ep = max_released
        except Exception as e:
            current_app.logger.error(f"Error fetching watchlist entry in watch route: {e}")

    return redirect(_build_clean_url(anime_id_clean, target_ep))

# ──────────────────────────────────────────────────────────────
#  MAIN CLEAN ROUTE: /watch/<anime_id>/ep-<number>
# ──────────────────────────────────────────────────────────────

@watch_routes_bp.route("/watch/<anime_id>/ep-<int:ep_number>", methods=["GET", "POST"])
def watch(anime_id, ep_number):
    """Watch episode page — clean URL format."""
    # User preferences (not in URL)
    lang = _get_preferred_lang()
    preferred_provider = _get_preferred_provider()

    # ── Fetch anime info ──
    anime_info = None
    anilist_id = None
    anime_id_clean = anime_id.split("?", 1)[0]

    try:
        anime_info = asyncio.run(current_app.ha_scraper.get_anime_info(anime_id_clean))
        if isinstance(anime_info, dict):
            if "info" in anime_info and isinstance(anime_info["info"], dict):
                anime = anime_info["info"]
            else:
                anime = anime_info
            anilist_id = anime.get("anilistId") or anime.get("alID")
            if anilist_id:
                try:
                    anilist_id = int(anilist_id)
                except (ValueError, TypeError):
                    anilist_id = None
    except Exception as e:
        current_app.logger.error(f"[Watch] Error getting anime info: {e}")

    # ── Fetch episodes list ──
    try:
        if anilist_id:
            all_episodes = asyncio.run(
                current_app.ha_scraper.episodes(str(anilist_id))
            )
        else:
            all_episodes = asyncio.run(current_app.ha_scraper.episodes(anime_id_clean))
    except Exception:
        all_episodes = None

    eps_list = all_episodes.get("episodes", []) if all_episodes else []
    providers_map = all_episodes.get("providers_map", {}) if all_episodes else {}
    default_provider = all_episodes.get("default_provider", "kiwi") if all_episodes else "kiwi"

    if not eps_list:
        return render_template(
            "404.html", error_message="No episodes found for this anime."
        ), 404

    # ── Resolve episode ──
    resolved = _resolve_episode(all_episodes, ep_number, preferred_provider)
    if not resolved:
        return render_template(
            "404.html", error_message=f"Episode {ep_number} not found."
        ), 404

    current_item = resolved["episode_item"]
    current_idx = resolved["episode_idx"]
    episode_id = resolved["episode_id"]
    provider_name = resolved["provider_name"]

    # Find the episode ID for the chosen provider specifically
    provider_ep_id = _find_episode_id_for_provider(
        providers_map, provider_name, ep_number, lang
    )
    if provider_ep_id:
        episode_id = provider_ep_id

    # If provider episode ID format is watch/..., use it directly
    # Otherwise construct the full slug
    if episode_id.startswith("watch/"):
        # Replace category in the ID to match the currently selected language
        parts = episode_id.split("/")
        if len(parts) >= 5:
            parts[3] = lang  # Set category to sub/dub
        full_slug = "/".join(parts)
    else:
        full_slug = episode_id

    # ── Check dub availability locally since we already fetched episodes ──
    dub_available = False
    try:
        if isinstance(all_episodes, dict):
            # Miruro unified returns total_dub_episodes and total_sub_episodes
            dub_ep_count = all_episodes.get("total_dub_episodes") or all_episodes.get("totalDubEpisodes") or 0
            if dub_ep_count > 0:
                dub_available = True
            elif all_episodes.get("episodes") and len(all_episodes["episodes"]) > 0:
                # Direct check across all providers just in case
                for pv_data in providers_map.values():
                    if isinstance(pv_data, dict) and "episodes" in pv_data and isinstance(pv_data["episodes"], dict):
                        if pv_data["episodes"].get("dub"):
                            dub_available = True
                            break
    except Exception as e:
        current_app.logger.warning(f"Error checking dub locally: {e}")

    # If dub requested but not available, fall back to sub
    if lang == "dub" and not dub_available:
        lang = "sub"
        if full_slug.startswith("watch/"):
            parts = full_slug.split("/")
            if len(parts) >= 5:
                parts[3] = "sub"
            full_slug = "/".join(parts)

    # ── Fetch available servers ──
    available_servers = []
    try:
        servers_data = asyncio.run(current_app.ha_scraper.episode_servers(full_slug))
        if servers_data:
            available_servers = servers_data.get(lang, [])
    except Exception:
        pass

    # Determine which server to use
    selected_server = preferred_provider or default_provider
    if available_servers:
        server_names = [
            s.get("serverName") for s in available_servers if s.get("serverName")
        ]
        if selected_server not in server_names and server_names:
            selected_server = server_names[0]
    else:
        if not selected_server:
            selected_server = "hd-1"

    # ── Fetch video data ──
    video_data = _fetch_video_data(full_slug, lang, selected_server, anilist_id)

    # Save last used server
    if selected_server:
        session["last_used_server"] = selected_server

    # ── Resolve anime info dict ──
    if (
        isinstance(anime_info, dict)
        and "info" in anime_info
        and isinstance(anime_info["info"], dict)
    ):
        anime = anime_info["info"]
    else:
        anime = anime_info or {}
        
    actual_title = anime.get("name") or anime.get("title")
    if not actual_title:
        actual_title = anime_id_clean.replace('-', ' ').title()
        
    # ── Fetch server progress if logged in (Disabled per user request, using local storage instead) ──
    server_progress_dict = {}
    is_logged_in = False
    if "username" in session and "_id" in session:
        is_logged_in = True

    # ── Fetch next episode schedule ──
    # Miruro Native API includes this natively inside get_anime_info response
    next_episode_schedule = anime.get("nextAiringEpisode")

    # Fallback schedule from AniList if not provided by Miruro
    needs_fallback = False
    if not next_episode_schedule or not next_episode_schedule.get("airingTimestamp"):
        needs_fallback = True
    else:
        time_until = next_episode_schedule.get(
            "secondsUntilAiring"
        ) or next_episode_schedule.get("timeUntilAiring")
        if time_until is not None:
            try:
                if int(time_until) < 0:
                    needs_fallback = True
            except ValueError:
                needs_fallback = True

    if needs_fallback:
        al_id = anime.get("anilistId") or anime.get("alID") if isinstance(anime, dict) else None
        mal_id = anime.get("malId") or anime.get("malID") if isinstance(anime, dict) else None
        anime_title = anime.get("title") if isinstance(anime, dict) else None

        if al_id or mal_id or anime_title:
            try:
                from api.utils.helpers import fetch_anilist_next_episode

                async def fetch_fallback():
                    return await fetch_anilist_next_episode(
                        anilist_id=al_id,
                        mal_id=mal_id,
                        search_title=anime_title,
                    )

                try:
                    loop = asyncio.get_running_loop()
                    fallback_schedule = loop.run_until_complete(fetch_fallback())
                except RuntimeError:
                    fallback_schedule = asyncio.run(fetch_fallback())

                if fallback_schedule and fallback_schedule.get("airingTimestamp"):
                    next_episode_schedule = fallback_schedule
            except Exception as e:
                current_app.logger.error(
                    f"Failed to fetch fallback schedule from AniList in watch: {e}"
                )

    # ── Build prev/next episode info ──
    episode_number = current_item.get("number")
    episode_title = current_item.get("title")
    Episode = str(episode_number) if episode_number else "Special"

    prev_episode_url = next_episode_url = None
    prev_episode_number = next_episode_number = None

    if current_idx > 0:
        prev_ep = eps_list[current_idx - 1]
        prev_episode_number = prev_ep.get("number")
        prev_episode_url = _build_clean_url(anime_id_clean, prev_episode_number)

    if current_idx < len(eps_list) - 1:
        next_ep = eps_list[current_idx + 1]
        next_episode_number = next_ep.get("number")
        next_episode_url = _build_clean_url(anime_id_clean, next_episode_number)

    # ── Render ──
    try:
        return render_template(
            "watch.html",
            back_to_ep=anime_id_clean,
            anime_id=anime_id_clean,
            video_link=video_data["video_link"],
            subtitles=video_data["subtitle_tracks"],
            intro=video_data["intro"],
            outro=video_data["outro"],
            Episode=Episode,
            episode_number=episode_number,
            episode_title=episode_title,
            prev_episode_url=prev_episode_url,
            next_episode_url=next_episode_url,
            prev_episode_number=prev_episode_number,
            next_episode_number=next_episode_number,
            eps_title=anime_id_clean,
            anime_title=actual_title,
            anime=anime,
            lang=lang,
            episodes=all_episodes,
            dub_available=dub_available,
            selected_server=selected_server,
            available_servers=available_servers,
            next_episode_schedule=next_episode_schedule,
            video_sources=video_data["video_sources"],
            available_qualities=video_data["available_qualities"],
            source_type=video_data["source_type"],
            embed_sources=video_data["embed_sources"],
            hls_sources=video_data["hls_sources"],
            server_progress=server_progress_dict,
            is_logged_in=is_logged_in,
        )
    except Exception as e:
        print("watch error:", e)
        return render_template(
            "404.html", error_message="An error occurred while fetching the episode."
        )


# ──────────────────────────────────────────────────────────────
#  AJAX ENDPOINT: Switch server/language without page reload
# ──────────────────────────────────────────────────────────────

@watch_routes_bp.route("/api/watch/sources", methods=["POST"])
def get_watch_sources():
    """
    AJAX endpoint for switching server/language/provider without changing the URL.
    Accepts JSON: { anime_id, episode_number, language, provider }
    Returns JSON with video sources data.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    anime_id = data.get("anime_id")
    ep_number = data.get("episode_number")
    lang = data.get("language", "sub")
    provider = data.get("provider")

    if not anime_id or ep_number is None:
        return jsonify({"error": "Missing anime_id or episode_number"}), 400

    anime_id_clean = str(anime_id).split("?", 1)[0]

    # Resolve anilist_id
    anilist_id = None
    try:
        anime_info = asyncio.run(current_app.ha_scraper.get_anime_info(anime_id_clean))
        if isinstance(anime_info, dict):
            info = anime_info.get("info", anime_info)
            if isinstance(info, dict):
                anilist_id = info.get("anilistId") or info.get("alID")
                if anilist_id:
                    anilist_id = int(anilist_id)
    except Exception:
        pass

    # Fetch episodes
    try:
        if anilist_id:
            all_episodes = asyncio.run(
                current_app.ha_scraper.episodes(str(anilist_id))
            )
        else:
            all_episodes = asyncio.run(current_app.ha_scraper.episodes(anime_id_clean))
    except Exception:
        return jsonify({"error": "Failed to fetch episodes"}), 500

    providers_map = all_episodes.get("providers_map", {}) if all_episodes else {}
    default_provider = all_episodes.get("default_provider", "kiwi") if all_episodes else "kiwi"

    # Resolve provider
    provider_name = provider or default_provider
    if provider_name not in providers_map:
        provider_name = default_provider

    # Find episode ID for this provider
    episode_id = _find_episode_id_for_provider(
        providers_map, provider_name, ep_number, lang
    )

    # Fallback: try the default episode list
    if not episode_id:
        resolved = _resolve_episode(all_episodes, ep_number, provider_name)
        if resolved:
            episode_id = resolved["episode_id"]

    if not episode_id:
        return jsonify({"error": f"Episode {ep_number} not found"}), 404

    # Build full slug
    if episode_id.startswith("watch/"):
        parts = episode_id.split("/")
        if len(parts) >= 5:
            parts[3] = lang
        full_slug = "/".join(parts)
    else:
        full_slug = episode_id

    # Determine server (provider IS the server in Miruro's model)
    selected_server = provider_name

    # Fetch available servers for this episode slug
    available_servers = []
    try:
        servers_data = asyncio.run(current_app.ha_scraper.episode_servers(full_slug))
        if servers_data:
            available_servers = servers_data.get(lang, [])
    except Exception:
        pass

    # Fetch video data
    video_data = _fetch_video_data(full_slug, lang, selected_server, anilist_id)

    # Save preferences
    if selected_server:
        session["last_used_server"] = selected_server

    # Build response — include everything the frontend needs to update its UI
    response_data = {
        "video_link": video_data["video_link"],
        "subtitles": video_data["subtitle_tracks"],
        "intro": video_data["intro"],
        "outro": video_data["outro"],
        "source_type": video_data["source_type"],
        "embed_sources": video_data["embed_sources"],
        "hls_sources": video_data["hls_sources"],
        "video_sources": video_data["video_sources"],
        "available_qualities": video_data["available_qualities"],
        "provider": provider_name,
        "language": lang,
        "available_servers": available_servers,
    }

    resp = make_response(jsonify(response_data))
    # Save preferences in cookies too
    resp.set_cookie("preferred_language", lang, max_age=365*24*60*60, samesite="Lax")
    resp.set_cookie("preferred_server", provider_name, max_age=365*24*60*60, samesite="Lax")

    return resp
