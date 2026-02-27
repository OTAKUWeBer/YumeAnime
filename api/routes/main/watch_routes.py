"""
Watch episode routes
"""

import asyncio
from flask import (
    Blueprint,
    request,
    session,
    redirect,
    url_for,
    render_template,
    current_app,
)
from urllib.parse import parse_qs

from ...models.watchlist import get_watchlist_entry

watch_routes_bp = Blueprint("watch_routes", __name__)


@watch_routes_bp.route("/watch/<eps_title>", methods=["GET", "POST"])
def watch(eps_title):
    """Watch episode page with video player"""
    ep_param = request.args.get("ep")

    # full slug + query
    full_slug = (
        f"{eps_title}?{request.query_string.decode()}"
        if request.query_string
        else eps_title
    )

    # Check user's preferred language setting
    preferred_lang = "sub"  # default
    last_server = session.get("last_used_server", "hd-2")

    if "username" in session and "_id" in session:
        try:
            # Try to get from user settings (stored in localStorage on frontend)
            pass
        except Exception:
            pass

    # Parse episode number and language
    ep_number, lang = None, preferred_lang
    if ep_param:
        parts = ep_param.split("-", 1)
        ep_number = parts[0]
        if len(parts) > 1:
            lang = parts[1]

    # If no episode parameter is provided, determine the best episode to watch
    if not ep_param:
        try:
            # Fetch episodes list first
            eps_title_clean = eps_title.split("?", 1)[0]
            all_episodes = asyncio.run(current_app.ha_scraper.episodes(eps_title_clean))
            eps_list = all_episodes.get("episodes", []) if all_episodes else []

            if not eps_list:
                return render_template(
                    "404.html", error_message="No episodes found for this anime."
                ), 404

            # Default to first episode
            target_ep = eps_list[0]

            # Check user watchlist for progress if logged in
            if "username" in session and "_id" in session:
                try:
                    user_id = session.get("_id")
                    # Use eps_title_clean as anime_id
                    watchlist_entry = get_watchlist_entry(user_id, eps_title_clean)

                    if watchlist_entry:
                        watched_count = watchlist_entry.get("watched_episodes", 0)
                        if watched_count > 0:
                            # If watched 1, index 1 is Ep 2.
                            # If watched_count is valid index, use it.
                            if watched_count < len(eps_list):
                                target_ep = eps_list[watched_count]
                            else:
                                # If completed or out of bounds, maybe show the last one?
                                # Or keep default to 0?
                                # Usually if completed, user might want to rewatch or just go to last.
                                # Let's go to the last one they watched (which is index - 1)
                                target_ep = eps_list[-1]
                except Exception as e:
                    current_app.logger.error(
                        f"Error fetching watchlist entry in watch route: {e}"
                    )

            # Extract the 'ep' parameter from the target episode's ID
            target_ep_id = target_ep.get("episodeId", "")
            if "?ep=" in target_ep_id:
                ep_val = target_ep_id.split("?ep=")[1]
            else:
                ep_val = target_ep_id  # Fallback

            return redirect(
                url_for("main.watch_routes.watch", eps_title=eps_title, ep=ep_val)
            )

        except Exception as e:
            current_app.logger.error(f"Error checking default episode: {e}")
            # If anything fails, let it fall through or error out,
            # but ideally we should have redirected.
            pass

    # If no language specified in URL, check if dub is available
    if ep_param and "-" not in ep_param:
        try:
            dub_available = asyncio.run(
                current_app.ha_scraper.is_dub_available(eps_title, ep_number)
            )
        except Exception:
            pass

    # Check if dub is available
    try:
        dub_available = asyncio.run(
            current_app.ha_scraper.is_dub_available(eps_title, ep_number)
        )
    except Exception:
        dub_available = False

    # Redirect to sub if dub requested but not available
    if lang == "dub" and not dub_available:
        return redirect(
            url_for(
                "main.watch_routes.watch", eps_title=eps_title, ep=f"{ep_number}-sub"
            )
        )

    # --- Fetch available servers first ---
    available_servers = []
    try:
        servers_data = asyncio.run(current_app.ha_scraper.episode_servers(full_slug))
        if servers_data:
            available_servers = servers_data.get(lang, [])
    except Exception as e:
        print(f"Error fetching servers: {e}")

    # --- Determine which server to use with fallback logic ---
    # Check if frontend sent a preferred server via cookie/header
    preferred_server = request.cookies.get("preferred_server", last_server)
    selected_server = preferred_server

    # If selected server not in available servers, use first available or fallback to hd-1
    if available_servers:
        server_names = [
            s.get("serverName") for s in available_servers if s.get("serverName")
        ]
        if selected_server not in server_names and server_names:
            selected_server = server_names[0]
            print(f"Server {preferred_server} not available, using {selected_server}")
    else:
        selected_server = "hd-1"

    print(
        f"Selected server: {selected_server}, Available: {[s.get('serverName') for s in available_servers]}"
    )

    # --- Fetch video data from the API ---
    hianime_al_id = None
    try:
        anime_info_for_video = asyncio.run(
            current_app.ha_scraper.get_anime_info(eps_title.split("?", 1)[0])
        )
        if isinstance(anime_info_for_video, dict):
            if "info" in anime_info_for_video and isinstance(
                anime_info_for_video["info"], dict
            ):
                anime_for_video = anime_info_for_video["info"]
            else:
                anime_for_video = anime_info_for_video
            hianime_al_id = anime_for_video.get("anilistId") or anime_for_video.get(
                "alID"
            )
            if hianime_al_id:
                try:
                    hianime_al_id = int(hianime_al_id)
                except (ValueError, TypeError):
                    hianime_al_id = None
    except Exception:
        pass

    raw = asyncio.run(
        current_app.ha_scraper.video(full_slug, lang, selected_server, hianime_al_id)
    )

    video_link = None
    subtitle_tracks = []
    intro = outro = None
    video_sources = []  # All quality sources for quality selector
    available_qualities = []

    if isinstance(raw, dict):
        # Video source - prioritize video_link if available (already proxied)
        video_link = raw.get("video_link")

        # Fallback to sources if video_link not available
        if not video_link:
            sources = raw.get("sources")
            if isinstance(sources, dict):
                video_link = sources.get("file") or sources.get("url")
            elif isinstance(sources, list) and sources:
                first_source = sources[0]
                if isinstance(first_source, dict):
                    video_link = first_source.get("file") or first_source.get("url")
                elif isinstance(first_source, str):
                    video_link = first_source

        # All quality sources for frontend quality selector
        all_sources = raw.get("sources", [])
        if isinstance(all_sources, list):
            video_sources = [
                s for s in all_sources if isinstance(s, dict) and s.get("file")
            ]

        available_qualities = raw.get("available_qualities", [])

        # Subtitles
        subtitle_tracks = raw.get("tracks", [])
        print(f"[Watch] Subtitle tracks received: {len(subtitle_tracks)} tracks")
        if subtitle_tracks:
            print(
                f"[Watch] First track sample: {subtitle_tracks[0] if subtitle_tracks else 'none'}"
            )

        # Intro/outro markers
        intro = raw.get("intro")
        outro = raw.get("outro")

    # ✅ --- Save last used server in cache (session) ---
    if selected_server:
        session["last_used_server"] = selected_server

    # Fetch episodes list
    eps_title_clean = eps_title.split("?", 1)[0]
    try:
        all_episodes = asyncio.run(current_app.ha_scraper.episodes(eps_title_clean))
    except Exception:
        all_episodes = None

    try:
        # Also try to fetch next episode schedule for the watch page
        anime_info = asyncio.run(current_app.ha_scraper.get_anime_info(eps_title_clean))
        get_schedule_method = getattr(
            current_app.ha_scraper, "next_episode_schedule", None
        )
        next_episode_schedule = (
            asyncio.run(get_schedule_method(eps_title_clean))
            if get_schedule_method
            else None
        )
    except Exception:
        anime_info = None
        next_episode_schedule = None

    if (
        isinstance(anime_info, dict)
        and "info" in anime_info
        and isinstance(anime_info["info"], dict)
    ):
        anime = anime_info["info"]
    else:
        anime = anime_info or {}

    # Auto-save IDs to cache (for Vercel — grows the DB as users browse)
    try:
        from api.utils.id_cache import auto_cache_from_info

        auto_cache_from_info(eps_title_clean, anime)
    except Exception:
        pass

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
        hianime_al_id = anime.get("anilistId") or anime.get("alID")
        hianime_mal_id = anime.get("malId") or anime.get("malID")
        hianime_title = anime.get("title")

        if hianime_al_id or hianime_mal_id or hianime_title:
            try:
                from api.utils.helpers import fetch_anilist_next_episode

                async def fetch_fallback():
                    return await fetch_anilist_next_episode(
                        anilist_id=hianime_al_id,
                        mal_id=hianime_mal_id,
                        search_title=hianime_title,
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
    # Build previous/next episode URLs
    prev_episode_url = next_episode_url = None
    prev_episode_number = next_episode_number = None
    Episode = "Special"
    episode_number = None
    eps_list = all_episodes.get("episodes", []) if all_episodes else []

    ep_base = ep_number or (ep_param.split("-", 1)[0] if ep_param else None)
    current_idx = None

    if ep_base and eps_list:
        for i, item in enumerate(eps_list):
            eid = item.get("episodeId", "")
            val = (
                parse_qs(eid.split("?", 1)[1]).get("ep", [None])[0]
                if "?" in eid
                else eid
            )
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
            ep_val = (
                parse_qs(eid.split("?", 1)[1]).get("ep", [None])[0]
                if "?" in eid
                else eid
            )
            slug = eid.split("?", 1)[0] if "?" in eid else eps_title_clean
            return (
                url_for(
                    "main.watch_routes.watch", eps_title=slug, ep=f"{ep_val}-{lang}"
                )
                if ep_val
                else None
            )

        if current_idx > 0:
            prev_episode_url = build_episode_url(current_idx - 1)
            prev_episode_number = eps_list[current_idx - 1].get("number")
        if current_idx < len(eps_list) - 1:
            next_episode_url = build_episode_url(current_idx + 1)
            next_episode_number = eps_list[current_idx + 1].get("number")

    # Language switch URLs
    sub_url = (
        url_for(
            "main.watch_routes.watch", eps_title=eps_title_clean, ep=f"{ep_number}-sub"
        )
        if ep_number
        else None
    )
    dub_url = (
        url_for(
            "main.watch_routes.watch", eps_title=eps_title_clean, ep=f"{ep_number}-dub"
        )
        if ep_number and dub_available
        else None
    )

    # External player link (removed - using Miruro only)
    external_link = ""

    # Render watch page
    try:
        return render_template(
            "watch.html",
            back_to_ep=eps_title_clean,
            video_link=video_link,
            subtitles=subtitle_tracks,
            intro=intro,
            outro=outro,
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
            dub_url=dub_url,
            selected_server=selected_server,
            available_servers=available_servers,
            external_link=external_link,
            next_episode_schedule=next_episode_schedule,
            video_sources=video_sources,
            available_qualities=available_qualities,
        )
    except Exception as e:
        print("watch error:", e)
        return render_template(
            "404.html", error_message="An error occurred while fetching the episode."
        )
