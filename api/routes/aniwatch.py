from flask import Blueprint, jsonify, request
from api.scrapers.aniwatch import AniwatchScraper

aniwatch_bp = Blueprint('aniwatch', __name__, url_prefix='/api/aniwatch')

# Initialize scraper
scraper = AniwatchScraper()


@aniwatch_bp.route('/search', methods=['GET'])
def search():
    """
    Search for anime on aniwatch.to
    Query params:
        - q: search query (required)
        - page: page number (optional, default: 1)
    """
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({
            'success': False,
            'error': 'Search query is required'
        }), 400
    
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
    
    results = scraper.search(query, page)
    return jsonify(results)


@aniwatch_bp.route('/info/<anime_id>', methods=['GET'])
def get_info(anime_id):
    """
    Get detailed information about an anime
    Path params:
        - anime_id: the anime ID from aniwatch.to
    """
    if not anime_id:
        return jsonify({
            'success': False,
            'error': 'Anime ID is required'
        }), 400
    
    info = scraper.get_anime_info(anime_id)
    return jsonify(info)


@aniwatch_bp.route('/episode/servers', methods=['GET'])
def get_episode_servers():
    """
    Get available streaming servers for an episode
    Query params:
        - anime_id: the anime ID (required)
        - episode_id: the episode ID (required)
    """
    anime_id = request.args.get('anime_id', '').strip()
    episode_id = request.args.get('episode_id', '').strip()
    
    if not anime_id or not episode_id:
        return jsonify({
            'success': False,
            'error': 'Both anime_id and episode_id are required'
        }), 400
    
    servers = scraper.get_episode_servers(anime_id, episode_id)
    return jsonify(servers)


@aniwatch_bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint for aniwatch scraper"""
    return jsonify({
        'success': True,
        'scraper': 'aniwatch',
        'status': 'operational'
    })
