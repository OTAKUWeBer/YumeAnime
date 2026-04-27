"""
Search routes
"""
import asyncio
from flask import Blueprint, request, redirect, url_for, render_template, jsonify, current_app

search_routes_bp = Blueprint('search_routes', __name__)


@search_routes_bp.route('/search', methods=['GET'], strict_slashes=False)
def search():
    """Handle search request"""

    search_query = request.args.get('q', '').strip()

    if not search_query:
        return redirect(url_for('home_routes.home'))

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(
            current_app.ha_scraper.search(search_query)
        )
        loop.close()

        animes = results.get("animes") or results.get("data") or []

        mapped = []
        for anime in animes:
            name = anime.get("name") or anime.get("title") or anime.get("id")
            if not name:
                continue

            poster = anime.get("poster") or anime.get("image") or ""
            episodes = anime.get("episodes") or {}
            sub = episodes.get("sub") if episodes else None
            dub = episodes.get("dub") if episodes else None

            if not poster and not sub and not dub:
                continue

            mapped.append(anime)

        return render_template(
            'anime/results.html',
            query=search_query,
            animes=mapped
        )

    except Exception as e:
        print("Search error:", e)
        return redirect(url_for('home_routes.home'))


# Suggestions
@search_routes_bp.route('/search/suggestions', methods=['GET'], strict_slashes=False)
def search_suggestions_route():
    query = request.args.get('q', '').strip()

    if not query:
        return jsonify({"suggestions": []})

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        suggestions = loop.run_until_complete(
            current_app.ha_scraper.search_suggestions(query)
        )
        loop.close()

        return jsonify(suggestions)

    except Exception as e:
        print("Suggestion error:", e)
        return jsonify({"suggestions": []})