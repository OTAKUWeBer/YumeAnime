from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app, session, flash, Response
from markupsafe import escape
from urllib.parse import parse_qs

from ..models.user import get_user_by_id

main_bp = Blueprint('main', __name__)

@main_bp.route('/', methods=["GET"])
async def index():
    return redirect("/home")

@main_bp.route("/home", methods=["GET"])
async def home():
    info = "Home"
    try:
        data = await current_app.ha_scraper.home()  # one call only
        current_app.logger.debug("home counts: %s", data.get("counts"))
        return render_template("index.html", suggestions=data, info=info)
    except Exception as e:
        current_app.logger.exception("Unhandled error in /home")
        empty = {k: [] for k in ["latestEpisodeAnimes","mostPopularAnimes","spotlightAnimes","trendingAnimes"]}
        return render_template(
            "index.html",
            suggestions={"success": False, "data": empty, "counts": {}},
            error=f"Error fetching home page data: {e}",
            info=info
        )

@main_bp.route('/search', methods=['GET'])
async def search():
    """Handle the search request and display results."""
    search_query = request.args.get('q', '').strip()
    if not search_query:
        # Redirect to home page if no query
        return redirect(url_for('main.home'))
    
    try:
        results = await current_app.ha_scraper.search(search_query)

        # Extract possible anime list
        animes = results.get("animes") or results.get("data") or []

        mapped = {}
        for anime in animes:
            name = anime.get("name") or anime.get("title") or anime.get("id")
            if not name:
                continue

            episodes = anime.get("episodes") or {}
            mapped[name] = {
                "link": f"/episodes/{anime.get('id')}",
                "image_url": anime.get("poster") or anime.get("image") or "",
                "episodes": {
                    "sub": episodes.get("sub") if episodes else None,
                    "dub": episodes.get("dub") if episodes else None,
                }
            }

        if not mapped:
            # No matches found
            return render_template('results.html', query=search_query, results={})
        
        return render_template('results.html', query=search_query, results=mapped)
    
    except Exception as e:
        print("Search error:", e)
        return redirect(url_for('main.home'))

@main_bp.route('/search/suggestions', methods=['GET'])
async def search_suggestions_route():
    """Return JSON suggestions for the query."""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({"suggestions": []})

    # Call your async scraper function
    suggestions = await current_app.ha_scraper.search_suggestions(query)

    # Ensure the format is suitable for frontend autocomplete
    return jsonify(suggestions)

@main_bp.route('/anime/<anime_id>', methods=['GET'])
async def anime_info(anime_id: str):
    """Fetch and display anime information."""
    current_path = request.path
    get_info_method = getattr(current_app.ha_scraper, "get_anime_info", None)
    if not get_info_method:
        return "Anime info function not found", 500
    anime_info = await get_info_method(anime_id)
    if not anime_info:
        return f"No info found for anime ID: {anime_id}", 404
    # Normalize: if the payload nests under "info", extract it
    if isinstance(anime_info, dict) and "info" in anime_info and isinstance(anime_info["info"], dict):
        anime = anime_info["info"]
    else:
        anime = anime_info # already top-level
    # safety: ensure an 'id' exists so template doesn't blow up
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
        current_season_id=anime_id  # Add this line
    )

@main_bp.route('/episodes/<anime_id>', methods=['GET'])
async def episodes(anime_id: str):
    """Fetch and display episodes for the selected anime."""
    info = "Episodes"
    suggestions = {"data": {"spotlightAnimes": []}}  # safe default

    try:
        # Fetch anime info
        anime_info = await current_app.ha_scraper.get_anime_info(anime_id)
        current_app.logger.debug("episodes() - got anime_info for %s: %s", anime_id, bool(anime_info))
        if not anime_info:
            return render_template(
                'index.html',
                error=f"Anime with ID {anime_id} not found.",
                suggestions=suggestions,
                info=info
            )

        # Fetch episodes
        ep_data = await current_app.ha_scraper.get_episodes(anime_id)
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
            suggestions=suggestions,      # <<--- PASS SUGGESTIONS HERE
            info=info
        )

    except Exception as e:
        # log full traceback so you can see the template error (BuildError / Jinja error) in the console
        current_app.logger.exception("Error in episodes(%s): %s", anime_id, e)
        # show error page (development helpful message)
        return render_template(
            'index.html',
            error=f"Error fetching episodes for {anime_id}: {e}",
            suggestions=suggestions,
            info=info
        )

@main_bp.route('/watch/<eps_title>', methods=['GET', 'POST'])
async def watch(eps_title):
    ep_param = request.args.get("ep")  # e.g. "141637" or "141637-sub"
    
    # Check user's preferred language setting
    preferred_lang = "sub"  # default
    if 'username' in session and '_id' in session:
        try:
            # Try to get from user settings (stored in localStorage on frontend)
            # For now, we'll use the URL parameter or default to sub
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
    
    # If no language specified in URL, check if dub is available and user prefers it
    if ep_param and "-" not in ep_param:
        # No language specified, check user preference and availability
        try:
            dub_available = await current_app.ha_scraper.is_dub_available(eps_title, ep_number)
            # For now, we'll default to sub unless explicitly requested
            # The frontend will handle language preference via localStorage
        except Exception:
            pass

    # Check if dub is available
    try:
        dub_available = await current_app.ha_scraper.is_dub_available(eps_title, ep_number)
    except Exception:
        dub_available = False

    # Redirect to sub if dub requested but not available
    if lang == "dub" and not dub_available:
        return redirect(url_for('main.watch', eps_title=eps_title, ep=f"{ep_number}-sub"))

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
            return url_for('main.watch', eps_title=slug, ep=f"{ep_val}-{lang}") if ep_val else None

        if current_idx > 0:
            prev_episode_url = build_episode_url(current_idx - 1)
            prev_episode_number = eps_list[current_idx - 1].get("number")
        if current_idx < len(eps_list) - 1:
            next_episode_url = build_episode_url(current_idx + 1)
            next_episode_number = eps_list[current_idx + 1].get("number")

    # Language switch URLs
    sub_url = url_for('main.watch', eps_title=eps_title_clean, ep=f"{ep_number}-sub") if ep_number else None
    dub_url = url_for('main.watch', eps_title=eps_title_clean, ep=f"{ep_number}-dub") if ep_number and dub_available else None

    # Render watch page with organized data
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


@main_bp.route('/genre/<genre_name>', methods=['GET'])
async def genre(genre_name):
    """Display anime list for a specific genre."""
    genre_name = escape(genre_name)
    
    try:
        data = await current_app.ha_scraper.genre(genre_name)
        animes = data.get("animes", [])
        if not animes:
            return render_template('404.html', error_message=f"No animes found for genre: {genre_name}"), 404
        
        genre_data = {
            'genreName': f"{genre_name.title()} Anime",
            'animes': []
        }
        
        for anime in animes:
            anime_id = anime.get("id")
            if not anime_id:
                continue
                
            # Map all required fields for the template
            mapped_anime = {
                "id": anime_id,
                "name": anime.get("name") or anime.get("title") or anime_id,
                "jname": anime.get("jname") or anime.get("japanese_name") or "",
                "poster": anime.get("poster") or anime.get("image") or "",
                "duration": anime.get("duration") or "N/A",
                "type": anime.get("type") or "Unknown",
                "rating": anime.get("rating"),  # Can be None
                "episodes": {
                    "sub": anime.get("episodes", {}).get("sub") if anime.get("episodes") else None,
                    "dub": anime.get("episodes", {}).get("dub") if anime.get("episodes") else None
                }
            }
            genre_data['animes'].append(mapped_anime)
        
        return render_template('genre.html', **genre_data)
    
    except Exception as e:
        current_app.logger.exception(f"Error fetching genre {genre_name}")
        return render_template('404.html', error_message=f"Error fetching genre: {e}"), 500
    
@main_bp.route('/profile', methods=['GET'])
def profile():
    """Display user profile page."""
    # Check if user is logged in
    username = session.get('username')
    user_id = session.get('_id')
    
    if not username or not user_id:
        # Redirect to home if not logged in
        flash('Please log in to view your profile.', 'warning')
        return redirect(url_for('main.home'))
    
    try:
        # Get user data from database
        user = get_user_by_id(user_id)
        if not user:
            # User not found in database
            session.clear()
            flash('User session expired. Please log in again.', 'error')
            return redirect(url_for('main.home'))
        
        # Prepare user data for template
        created = user.get('created_at')
        user_data = {
            'email': user.get('email', ''),
            'joined_date': created.strftime('%B %d, %Y') if created else 'Unknown',
            'avatar': user.get('avatar'),
            'anilist_authenticated': bool(user.get('anilist_id')),
            'anilist_id': user.get('anilist_id'),
            'anilist_stats': user.get('anilist_stats', {})
        }
        
        return render_template('profile.html', 
                             user=user_data, 
                             username=username, 
                             user_id=str(user_id))
        
    except Exception as e:
        current_app.logger.error(f"Error loading profile for user {username}: {e}")
        # Render minimal profile with error
        user_data = {
            'email': 'Error loading data',
            'joined_date': 'Error loading data',
            'avatar': None,
            'anilist_authenticated': False
        }
        return render_template('profile.html',
                               user=user_data,
                               username=username,
                               user_id=str(user_id),
                               error="Error loading profile data")
        
@main_bp.route('/settings', methods=['GET'])
def settings():
    """Display user settings page."""
    # Check if user is logged in
    username = session.get('username')
    user_id = session.get('_id')
    
    if not username or not user_id:
        # Redirect to home if not logged in
        flash('Please log in to access settings.', 'warning')
        return redirect(url_for('main.home'))
    
    try:
        # Get user data from database
        user = get_user_by_id(user_id)
        if not user:
            # User not found in database
            session.clear()
            flash('User session expired. Please log in again.', 'error')
            return redirect(url_for('main.home'))
        
        # Prepare user data for template
        user_data = {
            'username': username,
            'email': user.get('email', ''),
            'anilist_authenticated': bool(user.get('anilist_id')),
            'anilist_id': user.get('anilist_id'),
            'avatar': user.get('avatar'),
            'created_at': user.get('created_at')
        }
        
        return render_template('settings.html', user=user_data)
        
    except Exception as e:
        current_app.logger.error(f"Error loading settings for user {username}: {e}")
        flash('Error loading settings. Please try again.', 'error')
        return redirect(url_for('main.home'))
