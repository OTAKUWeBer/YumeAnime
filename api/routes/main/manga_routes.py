"""
Manga page routes — serves HTML templates for manga browsing and reading.
"""
import logging

from flask import Blueprint, render_template, request, abort

from api.providers.manga import MangaScraper, SOURCES

logger = logging.getLogger(__name__)

manga_routes_bp = Blueprint('manga_routes', __name__)


@manga_routes_bp.route('/manga', methods=['GET'])
def manga_home():
    """Manga home page with trending/popular/latest manga."""
    source = request.args.get('source', 'atsumaru')
    if source not in SOURCES:
        source = 'atsumaru'

    try:
        data = MangaScraper.home(source)
    except Exception as e:
        logger.error(f"Manga home error: {e}")
        data = {}

    sources = MangaScraper.get_sources()
    return render_template(
        'manga/home.html',
        manga_data=data,
        current_source=source,
        sources=sources,
        manga_referer=MangaScraper.get_referer(source),
        info="Manga"
    )


@manga_routes_bp.route('/manga/search', methods=['GET'])
def manga_search():
    """Manga search results page."""
    query = request.args.get('q', '').strip()
    source = request.args.get('source', 'atsumaru')
    if source not in SOURCES:
        source = 'atsumaru'

    results = {"entries": [], "found": 0}
    if query:
        try:
            results = MangaScraper.search(query, source)
        except Exception as e:
            logger.error(f"Manga search error: {e}")

    sources = MangaScraper.get_sources()
    return render_template(
        'manga/home.html',
        manga_data={},
        search_results=results,
        search_query=query,
        current_source=source,
        sources=sources,
        manga_referer=MangaScraper.get_referer(source),
        info="Manga Search"
    )


@manga_routes_bp.route('/manga/<source>/<path:manga_id>', methods=['GET'])
def manga_detail(source, manga_id):
    """Manga detail page — info + chapter list."""
    if source not in SOURCES:
        abort(404)

    try:
        details = MangaScraper.details(manga_id, source)
    except Exception as e:
        logger.error(f"Manga detail error: {e}")
        details = None

    if details is None:
        abort(404)

    return render_template(
        'manga/info.html',
        manga=details,
        source=source,
        source_name=SOURCES[source]["name"],
        manga_referer=MangaScraper.get_referer(source),
        info=details.get("title", "Manga")
    )


@manga_routes_bp.route('/manga/<source>/<path:manga_id>/read/<chapter_id>', methods=['GET'])
def manga_read(source, manga_id, chapter_id):
    """Manga reader page — displays chapter images."""
    if source not in SOURCES:
        abort(404)

    # Get chapter images
    try:
        images, referer = MangaScraper.chapter_images(manga_id, chapter_id, source)
    except Exception as e:
        logger.error(f"Manga reader error: {e}")
        images, referer = [], ""

    # Get manga details for navigation
    try:
        details = MangaScraper.details(manga_id, source)
    except Exception:
        details = None

    # Find current chapter index and prev/next
    prev_chapter = None
    next_chapter = None
    current_title = chapter_id
    if details and details.get("chapters"):
        chapters = details["chapters"]
        for i, ch in enumerate(chapters):
            if str(ch.get("id", "")) == str(chapter_id):
                current_title = ch.get("title", chapter_id)
                if i > 0:
                    next_chapter = chapters[i - 1]  # chapters usually desc order
                if i < len(chapters) - 1:
                    prev_chapter = chapters[i + 1]
                break

    return render_template(
        'manga/read.html',
        images=images,
        referer=referer,
        manga=details,
        source=source,
        source_name=SOURCES.get(source, {}).get("name", source),
        manga_id=manga_id,
        chapter_id=chapter_id,
        chapter_title=current_title,
        prev_chapter=prev_chapter,
        next_chapter=next_chapter,
        info=current_title
    )
