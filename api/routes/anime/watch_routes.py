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
    return request.cookies.get("preferred_server") or session.get(
        "last_used_server", None
    )


def _parse_ep_number(num):
    """
    Safely parse an episode number to float for robust comparison.
    Handles int, float, "1", "1.0", "1.5", etc.
    """
    try:
        return float(str(num).strip())
    except (ValueError, TypeError, AttributeError):
        return -1.0


def _resolve_episode(episodes_data, ep_number, preferred_provider=None):
    """
    Given episodes data and a target episode number, resolve the full internal
    episode ID and provider info.

    FIX 1: Always sort ascending.
    FIX 2: If exact float match fails, fall back to positional lookup
            (handles scrapers that use 0-based numbering, e.g. Miruro ep
            number=1 actually means display episode 2).
    """
    eps_list = episodes_data.get("episodes", []) if episodes_data else []
    providers_map = episodes_data.get("providers_map", {}) if episodes_data else {}
    default_provider = (
        episodes_data.get("default_provider", "kiwi") if episodes_data else "kiwi"
    )

    if not eps_list:
        return None

    try:
        sorted_eps = sorted(
            eps_list, key=lambda e: _parse_ep_number(e.get("number", 0))
        )
    except Exception:
        sorted_eps = list(eps_list)

    ep_num_float = _parse_ep_number(ep_number)

    # ── Pass 1: exact float match ──────────────────────────────────────────
    target_item = None
    target_idx = None
    for i, ep in enumerate(sorted_eps):
        if _parse_ep_number(ep.get("number")) == ep_num_float:
            target_item = ep
            target_idx = i
            break

    # ── Pass 2: positional fallback for 0-based scrapers ──────────────────
    # If Miruro numbers episodes 0, 1, 2, 3… but the URL uses 1, 2, 3, 4…
    # then ep_number=2 won't find number=2 (which is ep 3).
    # Instead use ep_number as a 1-based position: index = ep_number - 1.
    if target_item is None:
        positional_idx = int(ep_num_float) - 1
        if 0 <= positional_idx < len(sorted_eps):
            target_item = sorted_eps[positional_idx]
            target_idx = positional_idx
            import logging

            logging.getLogger(__name__).warning(
                f"[Watch] Exact ep match failed for {ep_number}, "
                f"using positional fallback → idx {positional_idx}, "
                f"ep.number={target_item.get('number')}"
            )

    if target_item is None:
        return None

    provider_name = preferred_provider or default_provider
    if provider_name not in providers_map:
        provider_name = default_provider

    return {
        "episode_item": target_item,
        "episode_idx": target_idx,
        "episode_id": target_item.get("episodeId", ""),
        "provider_name": provider_name,
        "eps_list": sorted_eps,
    }


def _find_episode_id_for_provider(
    providers_map, provider_name, ep_number, category="sub"
):
    """Find the episode ID for a specific provider and episode number."""
    if not providers_map or provider_name not in providers_map:
        return None

    provider_data = providers_map[provider_name]
    episodes_data = provider_data.get("episodes", {})
    cat_episodes = episodes_data.get(category, [])

    ep_num_float = _parse_ep_number(ep_number)
    for ep in cat_episodes:
        if _parse_ep_number(ep.get("number")) == ep_num_float:
            return ep.get("id", "")

    return None


def _build_clean_url(anime_id, ep_number):
    """Build a clean episode URL."""
    return f"/watch/{anime_id}/ep-{ep_number}"


def _fetch_video_data(full_slug, lang, server, anilist_id):
    """Fetch video data from the scraper and return structured result."""
    raw = asyncio.run(current_app.ha_scraper.video(full_slug, lang, server, anilist_id))
    return _parse_video_raw(raw)


def _parse_video_raw(raw):
    """Parse raw scraper response into structured video data."""
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

        # Prefer HLS over embed when both are available
        if hls_sources:
            source_type = "hls"
        elif not source_type:
            if embed_sources:
                source_type = "embed"

        # When HLS is selected, ALWAYS use actual HLS URL (not embed URL from scraper)
        if source_type == "hls" and hls_sources:
            first_hls = hls_sources[0] if isinstance(hls_sources, list) else None
            if isinstance(first_hls, dict):
                video_link = first_hls.get("file") or first_hls.get("url") or video_link
            elif isinstance(first_hls, str):
                video_link = first_hls
        elif source_type == "hls" and not video_link:
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

    print(
        f"[_fetch_video_data] source_type={source_type}, video_link={str(video_link)[:80] if video_link else 'NONE'}"
    )

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


def _fetch_video_only(
    full_slug, lang, server, anilist_id, providers_map
):
    """
    Fetch video data for the selected provider ONLY.
    All providers are assumed available — no scanning/checking.
    Returns (video_data_dict, provider_capabilities_dict).
    """
    # Just fetch video from the selected provider
    try:
        raw = asyncio.run(
            current_app.ha_scraper.video(full_slug, lang, server, anilist_id)
        )
        video_data = _parse_video_raw(raw)
    except Exception as e:
        print(f"[FetchVideo] Error fetching video: {e}")
        video_data = _parse_video_raw(None)

    # Mark ALL providers as available (both HLS and embed) — no checking
    capabilities = {}
    if providers_map:
        for p_name in providers_map:
            capabilities[p_name] = {"hls": True, "embed": True}

    print(f"[FetchVideo] Final intro: {video_data.get('intro')}")
    print(f"[FetchVideo] Final outro: {video_data.get('outro')}")
    print(f"[FetchVideo] All {len(capabilities)} providers marked available")
    return video_data, capabilities


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
    Just redirects to episode 1 for now — the full watch route will handle
    episode resolution and clamping once it's loaded.
    """
    anime_id_clean = anime_id.split("?", 1)[0]
    target_ep = 1

    # Check user watchlist for progress if logged in (from DB only, no API calls)
    if "username" in session and "_id" in session:
        watched_count = 0
        try:
            from api.models.watchlist import get_watchlist_entry

            user_id = session.get("_id")
            watchlist_entry = get_watchlist_entry(user_id, anime_id_clean)
            if watchlist_entry:
                watched_count = watchlist_entry.get("watched_episodes", 0)

            if watched_count > 0:
                target_ep = watched_count + 1
        except Exception as e:
            current_app.logger.error(
                f"Error fetching watchlist entry in watch route: {e}"
            )

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
    # Prefer anime_id_clean (what's in the URL) so episode URLs stay consistent.
    # Only use anilist_id if anime_id_clean is NOT numeric (i.e. it's a real slug),
    # because Miruro only accepts numeric AniList IDs.
    try:
        fetch_id = (
            anime_id_clean
            if anime_id_clean.isdigit()
            else (str(anilist_id) if anilist_id else anime_id_clean)
        )
        
        # Try to get anime_slug for anidap provider discovery
        # Use anime_id_clean if it looks like a slug (non-numeric), otherwise construct from title
        anime_slug = None
        if not anime_id_clean.isdigit():
            anime_slug = anime_id_clean
        elif anime and isinstance(anime, dict):
            # Try to use title to construct slug
            title = anime.get("title") or anime.get("name")
            if title:
                # Simple slug: lowercase, replace spaces with hyphens, remove non-alphanumeric
                import re as regex
                anime_slug = regex.sub(r'[^\w\s-]', '', title.lower()).replace(' ', '-').strip('-')
        
        all_episodes = asyncio.run(current_app.ha_scraper.episodes(fetch_id, anime_slug))
    except Exception:
        all_episodes = None

    providers_map = all_episodes.get("providers_map", {}) if all_episodes else {}
    default_provider = (
        all_episodes.get("default_provider", "kiwi") if all_episodes else "kiwi"
    )

    # ── Resolve episode (returns sorted eps_list) ──
    resolved = _resolve_episode(all_episodes, ep_number, preferred_provider)
    if not resolved:
        # Episodes unavailable — render the watch page with a friendly message
        # instead of a 404 so the user can still see anime info and airing schedule

        # Resolve anime dict
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
            actual_title = anime_id_clean.replace("-", " ").title()

        # Fetch next episode schedule for upcoming info
        next_episode_schedule = anime.get("nextAiringEpisode") if isinstance(anime, dict) else None

        needs_fallback = False
        if not next_episode_schedule or not next_episode_schedule.get("airingTimestamp"):
            needs_fallback = True
        else:
            import time as _time
            airing_ts = next_episode_schedule.get("airingTimestamp")
            try:
                ts_secs = int(airing_ts)
                if ts_secs > 9_999_999_999:
                    ts_secs //= 1000
                if ts_secs < int(_time.time()):
                    needs_fallback = True
            except (ValueError, TypeError):
                needs_fallback = True

        if needs_fallback:
            al_id = anime.get("anilistId") or anime.get("alID") if isinstance(anime, dict) else None
            _mal_id = anime.get("malId") or anime.get("malID") if isinstance(anime, dict) else None
            _anime_title = anime.get("title") if isinstance(anime, dict) else None

            if al_id or _mal_id or _anime_title:
                try:
                    from api.utils.helpers import fetch_anilist_next_episode

                    async def fetch_fallback_schedule():
                        return await fetch_anilist_next_episode(
                            anilist_id=al_id,
                            mal_id=_mal_id,
                            search_title=_anime_title,
                        )

                    try:
                        loop = asyncio.get_running_loop()
                        fallback_schedule = loop.run_until_complete(fetch_fallback_schedule())
                    except RuntimeError:
                        fallback_schedule = asyncio.run(fetch_fallback_schedule())

                    if fallback_schedule and fallback_schedule.get("airingTimestamp"):
                        next_episode_schedule = fallback_schedule
                except Exception as e:
                    current_app.logger.error(
                        f"Failed to fetch fallback schedule from AniList: {e}"
                    )

        return render_template(
            "anime/watch.html",
            back_to_ep=anime_id_clean,
            anime_id=anime_id_clean,
            video_link=None,
            subtitles=[],
            intro=None,
            outro=None,
            Episode=str(ep_number),
            episode_number=ep_number,
            episode_title=None,
            prev_episode_url=None,
            next_episode_url=None,
            prev_episode_number=None,
            next_episode_number=None,
            eps_title=anime_id_clean,
            anime_title=actual_title,
            anime=anime,
            lang="sub",
            episodes=all_episodes,
            dub_available=False,
            selected_server=None,
            available_servers=[],
            next_episode_schedule=next_episode_schedule,
            video_sources=[],
            available_qualities=[],
            source_type=None,
            embed_sources=[],
            hls_sources=[],
            server_progress={},
            is_logged_in="username" in session and "_id" in session,
            provider_capabilities={},
            sorted_providers=[],
            mal_id=anime.get("malId") or anime.get("malID") if isinstance(anime, dict) else None,
            episodes_unavailable=True,
        )

    current_item = resolved["episode_item"]
    current_idx = resolved["episode_idx"]
    episode_id = resolved["episode_id"]
    provider_name = resolved["provider_name"]

    # ── IMPORTANT: use the sorted list for prev/next computation ────────────
    eps_list = resolved["eps_list"]

    # Find the episode ID for the chosen provider specifically
    provider_ep_id = _find_episode_id_for_provider(
        providers_map, provider_name, ep_number, lang
    )
    if provider_ep_id:
        episode_id = provider_ep_id

    # If provider episode ID format is watch/..., use it directly
    if episode_id.startswith("watch/"):
        parts = episode_id.split("/")
        if len(parts) >= 5:
            parts[3] = lang
        full_slug = "/".join(parts)
    else:
        full_slug = episode_id

    # ── Check dub availability ──
    dub_available = False
    try:
        if isinstance(all_episodes, dict):
            dub_ep_count = (
                all_episodes.get("total_dub_episodes")
                or all_episodes.get("totalDubEpisodes")
                or 0
            )
            if dub_ep_count > 0:
                dub_available = True
            elif all_episodes.get("episodes") and len(all_episodes["episodes"]) > 0:
                for pv_data in providers_map.values():
                    if (
                        isinstance(pv_data, dict)
                        and "episodes" in pv_data
                        and isinstance(pv_data["episodes"], dict)
                    ):
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

    # ── Fetch video data for selected provider only (no scanning) ──
    video_data, provider_capabilities = _fetch_video_only(
        full_slug, lang, selected_server, anilist_id, providers_map
    )

    from api.providers.miruro.episodes import PROVIDER_PRIORITY as _PP

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
        actual_title = anime_id_clean.replace("-", " ").title()

    # ── Fetch server progress if logged in ──
    server_progress_dict = {}
    is_logged_in = False
    if "username" in session and "_id" in session:
        is_logged_in = True

    # ── Extract mal_id for frontend ──
    mal_id = (
        anime.get("malId") or anime.get("malID") if isinstance(anime, dict) else None
    )

    # ── Fetch next episode schedule ──
    next_episode_schedule = anime.get("nextAiringEpisode")
    print(f"[Watch DEBUG] anime type: {type(anime)}, keys: {list(anime.keys()) if isinstance(anime, dict) else 'N/A'}")
    print(f"[Watch DEBUG] nextAiringEpisode from anime: {next_episode_schedule}")
    print(f"[Watch DEBUG] anime_info type: {type(anime_info)}, has 'info' key: {'info' in anime_info if isinstance(anime_info, dict) else 'N/A'}")

    needs_fallback = False
    if not next_episode_schedule or not next_episode_schedule.get("airingTimestamp"):
        needs_fallback = True
    else:
        import time as _time
        airing_ts = next_episode_schedule.get("airingTimestamp")
        try:
            ts_secs = int(airing_ts)
            if ts_secs > 9_999_999_999:  # milliseconds → seconds
                ts_secs //= 1000
            if ts_secs < int(_time.time()):
                needs_fallback = True
        except (ValueError, TypeError):
            needs_fallback = True

    if needs_fallback:
        al_id = (
            anime.get("anilistId") or anime.get("alID")
            if isinstance(anime, dict)
            else None
        )
        mal_id = (
            anime.get("malId") or anime.get("malID")
            if isinstance(anime, dict)
            else None
        )
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

    # ── Build prev/next episode info ──────────────────────────────────────────
    # CRITICAL: episode_number/Episode MUST reflect the URL ep_number,
    # not current_item.get("number"), because Miruro's internal numbering
    # can differ from the 1-based display numbering used in URLs.
    # The URL is the single source of truth for what the user is watching.
    episode_title = current_item.get("title")
    episode_number = ep_number  # ← always use URL value
    Episode = str(ep_number)  # ← always use URL value

    prev_episode_url = next_episode_url = None
    prev_episode_number = next_episode_number = None

    if current_idx > 0:
        prev_ep = eps_list[current_idx - 1]
        raw_prev_num = prev_ep.get("number")
        # Derive prev display number: if scraper uses 0-based, compute from URL position
        if _parse_ep_number(raw_prev_num) < _parse_ep_number(ep_number):
            # Scraper number is already less — use it directly
            prev_episode_number = raw_prev_num
        else:
            # Scraper number is >= current (0-based mismatch) — derive from URL
            prev_episode_number = ep_number - 1
            current_app.logger.warning(
                f"[Watch] prev ep raw number {raw_prev_num} >= current {ep_number}, "
                f"using derived prev={prev_episode_number}"
            )
        # Final guard: never link to same or higher episode
        if prev_episode_number is not None and _parse_ep_number(
            prev_episode_number
        ) < _parse_ep_number(ep_number):
            prev_episode_url = _build_clean_url(anime_id_clean, prev_episode_number)

    if current_idx < len(eps_list) - 1:
        next_ep = eps_list[current_idx + 1]
        raw_next_num = next_ep.get("number")
        if _parse_ep_number(raw_next_num) > _parse_ep_number(ep_number):
            next_episode_number = raw_next_num
        else:
            next_episode_number = ep_number + 1
            current_app.logger.warning(
                f"[Watch] next ep raw number {raw_next_num} <= current {ep_number}, "
                f"using derived next={next_episode_number}"
            )
        # Final guard: only link to ep with higher number and that actually exists in list
        max_ep_num = _parse_ep_number(eps_list[-1].get("number", 0))
        if (
            _parse_ep_number(next_episode_number) > _parse_ep_number(ep_number)
            and _parse_ep_number(next_episode_number) <= max_ep_num + 1
        ):
            next_episode_url = _build_clean_url(anime_id_clean, next_episode_number)

    # ── Render ──
    try:
        return render_template(
            "anime/watch.html",
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
            provider_capabilities=provider_capabilities,
            sorted_providers=sorted(
                (providers_map or {}).keys(),
                key=lambda p: _PP.index(p) if p in _PP else len(_PP),
            ),
            mal_id=mal_id,
        )
    except Exception as e:
        print("watch error:", e)
        return render_template(
            "shared/404.html", error_message="An error occurred while fetching the episode."
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
    anime_slug = data.get("anime_slug")  # May be passed from frontend

    if not anime_id or ep_number is None:
        return jsonify({"error": "Missing anime_id or episode_number"}), 400

    anime_id_clean = str(anime_id).split("?", 1)[0]

    # Resolve anilist_id and construct anime_slug for anidap discovery
    anilist_id = None
    anime_info = None
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

    # Construct anime_slug if not provided
    if not anime_slug:
        if not anime_id_clean.isdigit():
            anime_slug = anime_id_clean
        elif anime_info and isinstance(anime_info, dict):
            info = anime_info.get("info", anime_info)
            if isinstance(info, dict):
                title = info.get("title") or info.get("name")
                if title:
                    import re as regex
                    anime_slug = regex.sub(r'[^\w\s-]', '', title.lower()).replace(' ', '-').strip('-')

    # Fetch episodes with anime_slug for anidap provider discovery
    try:
        if anilist_id:
            all_episodes = asyncio.run(current_app.ha_scraper.episodes(str(anilist_id), anime_slug))
        else:
            all_episodes = asyncio.run(current_app.ha_scraper.episodes(anime_id_clean, anime_slug))
    except Exception:
        return jsonify({"error": "Failed to fetch episodes"}), 500

    providers_map = all_episodes.get("providers_map", {}) if all_episodes else {}
    default_provider = (
        all_episodes.get("default_provider", "kiwi") if all_episodes else "kiwi"
    )

    # Resolve provider
    provider_name = provider or default_provider
    if provider_name not in providers_map:
        provider_name = default_provider

    # Find episode ID for this provider (uses float comparison now)
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

    # Determine server
    selected_server = provider_name

    # Fetch available servers
    available_servers = []
    try:
        servers_data = asyncio.run(current_app.ha_scraper.episode_servers(full_slug))
        if servers_data:
            available_servers = servers_data.get(lang, [])
    except Exception:
        pass

    # Fetch video data for selected provider only (no scanning)
    video_data, provider_capabilities = _fetch_video_only(
        full_slug, lang, selected_server, anilist_id, providers_map
    )

    # Save preferences
    if selected_server:
        session["last_used_server"] = selected_server

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
        "provider_capabilities": provider_capabilities,
    }
    print(f"[API /sources] intro response: {response_data.get('intro')}")
    print(f"[API /sources] outro response: {response_data.get('outro')}")

    resp = make_response(jsonify(response_data))
    resp.set_cookie(
        "preferred_language", lang, max_age=365 * 24 * 60 * 60, samesite="Lax"
    )
    resp.set_cookie(
        "preferred_server", provider_name, max_age=365 * 24 * 60 * 60, samesite="Lax"
    )

    return resp
