"""
Anime information fetching for Miruro API
Handles detailed anime data including relations and characters
"""
import logging
from typing import Dict, Any, List, Optional
from .base import MiruroBaseClient

logger = logging.getLogger(__name__)


class MiruroAnimeInfoService:
    """Service for fetching anime information from Miruro API"""

    def __init__(self, client: MiruroBaseClient):
        self.client = client

    async def get_anime_info(self, anilist_id) -> dict:
        """
        Fetch detailed anime info from Miruro /info/{anilist_id}
        Normalizes response to HiAnime-compatible shape
        """
        resp = await self.client._get(f"info/{anilist_id}")
        if not resp:
            return {}

        title = resp.get("title", {}) or {}
        cover = resp.get("coverImage", {}) or {}
        studios_nodes = (resp.get("studios", {}) or {}).get("nodes", [])
        next_airing = resp.get("nextAiringEpisode") or {}

        english_title = title.get("english") or title.get("romaji") or "Unknown"

        # Extract studios list
        studios_list = [
            s.get("name") for s in studios_nodes 
            if s.get("isAnimationStudio", True)
        ]

        # Build genres list
        genres = resp.get("genres", []) or []

        # Build start/end date strings
        start_date = resp.get("startDate", {}) or {}
        end_date = resp.get("endDate", {}) or {}
        aired = self._format_date_range(start_date, end_date)

        # Season info
        season = resp.get("season") or ""
        season_year = resp.get("seasonYear") or ""
        premiered = f"{season} {season_year}".strip() if season else ""

        # Relations
        raw_relations = resp.get("relations", {}) or {}
        raw_edges = raw_relations.get("edges", []) if isinstance(raw_relations, dict) else []
        related, prequels, sequels = self._normalize_relations(raw_edges)

        # Recommendations
        raw_recs = resp.get("recommendations", {}) or {}
        raw_rec_nodes = raw_recs.get("nodes", []) if isinstance(raw_recs, dict) else []
        recommended = self._normalize_recommendations(raw_rec_nodes)

        # Characters
        raw_chars = resp.get("characters", {}) or {}
        raw_char_edges = raw_chars.get("edges", []) if isinstance(raw_chars, dict) else []
        characters = self._normalize_characters(raw_char_edges)

        # Status mapping
        status_map = {
            "FINISHED": "Finished Airing",
            "RELEASING": "Currently Airing",
            "NOT_YET_RELEASED": "Not yet aired",
            "CANCELLED": "Cancelled",
            "HIATUS": "Hiatus",
        }
        status = status_map.get(resp.get("status", ""), resp.get("status", ""))

        return {
            "anilistId": resp.get("id"),
            "malId": resp.get("idMal"),
            "title": english_title,
            "poster": cover.get("extraLarge") or cover.get("large") or "",
            "description": (resp.get("description") or "").replace("<br>", "\n").replace("<i>", "").replace("</i>", ""),
            "status": status,
            "genres": genres,
            "duration": f"{resp.get('duration', '')} min" if resp.get("duration") else "",
            "type": resp.get("format") or "",
            "rating": str(resp.get("averageScore") or "") if resp.get("averageScore") else "",
            "quality": "",
            "total_sub_episodes": resp.get("episodes") or 0,
            "total_dub_episodes": 0,
            "japanese": title.get("native") or "",
            "synonyms": ", ".join(resp.get("synonyms", []) or []),
            "aired": aired,
            "premiered": premiered,
            "studios": ", ".join(studios_list) if studios_list else None,
            "producers": [],
            "malScore": str(resp.get("meanScore") or "") if resp.get("meanScore") else None,
            "promotionalVideos": self._extract_trailer(resp),
            "charactersVoiceActors": [],  # raw format not used by templates
            "characters": characters,
            "seasons": [],  # Miruro doesn't provide season navigation in same format
            "relatedAnimes": related,
            "recommendedAnimes": recommended,
            "prequels": prequels,
            "sequels": sequels,
            # Extra fields from Miruro
            "bannerImage": resp.get("bannerImage") or "",
            "nextAiringEpisode": {
                "airingTimestamp": next_airing.get("airingAt"),
                "timeUntilAiring": next_airing.get("timeUntilAiring"),
                "episode": next_airing.get("episode"),
            } if next_airing else None,
        }

    def _format_date_range(self, start: dict, end: dict) -> str:
        """Format start/end date dicts into readable range string"""
        def fmt(d):
            if not d or not d.get("year"):
                return "?"
            parts = []
            months = [
                "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
            ]
            if d.get("month") and 1 <= d["month"] <= 12:
                parts.append(months[d["month"]])
            if d.get("day"):
                parts.append(str(d["day"]) + ",")
            parts.append(str(d["year"]))
            return " ".join(parts)

        s = fmt(start)
        e = fmt(end)
        if s == "?" and e == "?":
            return ""
        if e == "?":
            return f"{s} to ?"
        return f"{s} to {e}"

    def _normalize_relations(self, edges: List[Dict]) -> tuple:
        """Normalize relation edges from AniList format"""
        related = []
        prequels = []
        sequels = []

        for edge in edges:
            if not isinstance(edge, dict):
                continue
            node = edge.get("node") or {}
            rel_type = edge.get("relationType") or ""
            node_title = node.get("title", {}) or {}
            node_cover = node.get("coverImage", {}) or {}

            entry = {
                "id": str(node.get("id", "")),
                "anilistId": node.get("id"),
                "malId": node.get("idMal"),
                "name": node_title.get("english") or node_title.get("romaji") or "",
                "jname": node_title.get("native") or "",
                "poster": node_cover.get("large") or node_cover.get("extraLarge") or "",
                "type": node.get("format") or "",
                "rating": node.get("averageScore"),
                "episodes_sub": node.get("episodes") or 0,
                "episodes_dub": 0,
                "relation": rel_type.replace("_", " ").title(),
            }
            related.append(entry)

            rel_lower = rel_type.lower()
            if "prequel" in rel_lower:
                prequels.append(entry)
            elif "sequel" in rel_lower:
                sequels.append(entry)

        return related, prequels, sequels

    def _normalize_recommendations(self, nodes: List[Dict]) -> List[Dict]:
        """Normalize recommendation nodes"""
        recommended = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            media = node.get("mediaRecommendation") or {}
            if not media:
                continue
            media_title = media.get("title", {}) or {}
            media_cover = media.get("coverImage", {}) or {}

            recommended.append({
                "id": str(media.get("id", "")),
                "anilistId": media.get("id"),
                "name": media_title.get("english") or media_title.get("romaji") or "",
                "jname": media_title.get("native") or "",
                "poster": media_cover.get("large") or media_cover.get("extraLarge") or "",
                "type": media.get("format") or "",
                "duration": f"{media.get('duration', '')} min" if media.get("duration") else "",
                "rating": media.get("averageScore"),
                "episodes_sub": media.get("episodes") or 0,
                "episodes_dub": 0,
            })
        return recommended

    def _normalize_characters(self, edges: List[Dict]) -> List[Dict]:
        """Normalize character edges from AniList format"""
        characters = []
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            char_node = edge.get("node") or {}
            char_name = char_node.get("name", {}) or {}
            char_image = char_node.get("image", {}) or {}
            role = edge.get("role") or "SUPPORTING"

            voice_actors = edge.get("voiceActors", []) or []
            # Pick first Japanese VA if available
            va = None
            for actor in voice_actors:
                if isinstance(actor, dict):
                    if actor.get("language", "").upper() == "JAPANESE":
                        va = actor
                        break
            if not va and voice_actors:
                va = voice_actors[0] if isinstance(voice_actors[0], dict) else None

            va_name = (va or {}).get("name", {}) or {}
            va_image = (va or {}).get("image", {}) or {}

            char_full_name = char_name.get("full") or f"{char_name.get('first', '')} {char_name.get('last', '')}".strip()
            va_full_name = va_name.get("full") or f"{va_name.get('first', '')} {va_name.get('last', '')}".strip() if va else ""

            characters.append({
                "character": {
                    "id": str(char_node.get("id", "")),
                    "name": char_full_name,
                    "poster": char_image.get("large") or char_image.get("medium") or "",
                    "cast": role.title(),
                },
                "voiceActor": {
                    "id": str((va or {}).get("id", "")),
                    "name": va_full_name,
                    "poster": va_image.get("large") or va_image.get("medium") or "",
                    "cast": (va or {}).get("language", "Japanese"),
                } if va else None,
            })
        return characters

    def _extract_trailer(self, resp: Dict) -> List[Dict]:
        """Extract trailer/promotional video from Miruro response"""
        trailer = resp.get("trailer") or {}
        if not trailer or not trailer.get("id"):
            return []
        
        site = trailer.get("site", "youtube").lower()
        video_id = trailer.get("id")
        
        if site == "youtube":
            url = f"https://www.youtube.com/watch?v={video_id}"
        elif site == "dailymotion":
            url = f"https://www.dailymotion.com/video/{video_id}"
        else:
            url = video_id
        
        return [{
            "title": "Trailer",
            "source": url,
            "thumbnail": trailer.get("thumbnail") or "",
        }]

    async def next_episode_schedule(self, anilist_id) -> Dict[str, Any]:
        """Get next episode schedule from Miruro /info endpoint"""
        resp = await self.client._get(f"info/{anilist_id}")
        if not resp:
            return {}

        next_ep = resp.get("nextAiringEpisode") or {}
        if not next_ep or not next_ep.get("airingAt"):
            return {}

        return {
            "airingTimestamp": next_ep.get("airingAt"),
            "timeUntilAiring": next_ep.get("timeUntilAiring"),
            "episode": next_ep.get("episode"),
        }
