"""
Search routes
"""
import asyncio
from flask import Blueprint, request, redirect, url_for, render_template, jsonify, current_app

search_routes_bp = Blueprint('search_routes', __name__)


@search_routes_bp.route('/search', methods=['GET'])
def search():
    """Handle search request and display results"""
    search_query = request.args.get('q', '').strip()
    if not search_query:
        return redirect(url_for('main.home_routes.home'))
    
    try:
        results = asyncio.run(current_app.ha_scraper.search(search_query))

        # Extract anime list
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

            # Skip entries with no poster and no episodes (empty/useless entries)
            if not poster and not sub and not dub:
                continue

            mapped.append(anime)

        if not mapped:
            return render_template('results.html', query=search_query, animes=[])
        
        return render_template('results.html', query=search_query, animes=mapped)
    
    except Exception as e:
        print("Search error:", e)
        return redirect(url_for('main.home_routes.home'))


@search_routes_bp.route('/search/suggestions', methods=['GET'])
def search_suggestions_route():
    """Return JSON suggestions for the query"""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({"suggestions": []})

    suggestions = asyncio.run(current_app.ha_scraper.search_suggestions(query))
    return jsonify(suggestions)
