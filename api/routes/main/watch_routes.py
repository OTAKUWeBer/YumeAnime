"""
Watch episode routes
"""
from flask import Blueprint, request, session, redirect, url_for, render_template, current_app
from urllib.parse import parse_qs

watch_routes_bp = Blueprint('watch_routes', __name__)


@watch_routes_bp.route('/watch/<eps_title>', methods=['GET', 'POST'])
async def watch(eps_title):
    """Watch episode page with video player"""
    ep_param = request.args.get("ep")  # e.g. "141637" or "141637-sub"
    
    # Check user's preferred language setting
    preferred_lang = "sub"  # default
    if 'username' in session and '_id' in session:
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
    
    # If no language specified in URL, check if dub is available
    if ep_param and "-" not in ep_param:
        try:
            dub_available = await current_app.ha_scraper.is_dub_available(eps_title, ep_number)
        except Exception:
            pass

    # Check if dub is available
    try:
        dub_available = await current_app.ha_scraper.is_dub_available(eps_title, ep_number)
    except Exception:
        dub_available = False

    # Redirect to sub if dub requested but not available
    if lang == "dub" and not dub_available:
        return redirect(url_for('main.watch_routes.watch', eps_title=eps_title, ep=f"{ep_number}-sub"))

    # Get video data
    raw = await current_app.ha_scraper.video(ep_number, lang)

    video_link = None
    subtitle_tracks = []
    intro = outro = None

    if isinstance(raw, dict):
        # Video source
        sources = raw.get("sources")
        if isinstance(sources, dict):
            video_link = sources.get("file")

        # Subtitles
        subtitle_tracks = raw.get("tracks", [])

        # Intro/outro markers
        intro = raw.get("intro")
        outro = raw.get("outro")

    # Fetch episodes list
    eps_title_clean = eps_title.split('?', 1)[0]
    try:
        all_episodes = await current_app.ha_scraper.episodes(eps_title_clean)
    except Exception:
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
            return url_for('main.watch_routes.watch', eps_title=slug, ep=f"{ep_val}-{lang}") if ep_val else None

        if current_idx > 0:
            prev_episode_url = build_episode_url(current_idx - 1)
            prev_episode_number = eps_list[current_idx - 1].get("number")
        if current_idx < len(eps_list) - 1:
            next_episode_url = build_episode_url(current_idx + 1)
            next_episode_number = eps_list[current_idx + 1].get("number")

    # Language switch URLs
    sub_url = url_for('main.watch_routes.watch', eps_title=eps_title_clean, ep=f"{ep_number}-sub") if ep_number else None
    dub_url = url_for('main.watch_routes.watch', eps_title=eps_title_clean, ep=f"{ep_number}-dub") if ep_number and dub_available else None

    # Render watch page
    try:
        return render_template(
            'watch.html',
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
        )
    except Exception as e:
        print("watch error:", e)
        return render_template('404.html', error_message="An error occurred while fetching the episode.")
