"""
Anime information fetching
Handles detailed anime data, seasons, related, and recommended anime
"""
from typing import Dict, Any, List
from .base import HianimeBaseClient


class HianimeAnimeInfoService:
    """Service for fetching anime information"""
    
    def __init__(self, client: HianimeBaseClient):
        self.client = client
    
    async def get_anime_info(self, anime_id: str) -> dict:
        """
        Fetch detailed anime info including seasons, related, recommended, 
        prequels, sequels, and characters.
        """
        resp = await self.client._get(f"anime/{anime_id}")
        if not resp:
            return {}

        # Helpful aliases
        data = resp.get("data", {}) if isinstance(resp, dict) else {}
        anime_data = (
            (data.get("anime") if isinstance(data, dict) else None) or 
            (resp.get("anime") if isinstance(resp, dict) else None) or 
            {}
        )

        def find_list(key: str):
            """Look for list in several places"""
            for src in (anime_data, data, resp):
                if isinstance(src, dict):
                    val = src.get(key)
                    if isinstance(val, list):
                        return val
            return []

        def safe_int(val):
            try:
                return int(val)
            except (TypeError, ValueError):
                return 0

        info = anime_data.get("info", {}) if isinstance(anime_data, dict) else {}
        stats = info.get("stats", {}) if isinstance(info, dict) else {}
        episodes = stats.get("episodes", {}) if isinstance(stats, dict) else {}
        more_info = anime_data.get("moreInfo", {}) if isinstance(anime_data, dict) else {}

        # Collect seasons, related, recommended
        raw_seasons = find_list("seasons")
        raw_related = find_list("relatedAnimes") or find_list("related")
        raw_recommended = find_list("recommendedAnimes") or find_list("recommended")

        # Normalize seasons
        seasons = self._normalize_seasons(raw_seasons, info)
        
        # Related + prequel/sequel detection
        related, prequels, sequels = self._normalize_related(raw_related)
        
        # Recommended
        recommended = self._normalize_recommended(raw_recommended)
        
        # Characters and voice actors
        characters = self._normalize_characters(info)

        return {
            "anilistId": info.get("anilistId"),
            "malId": info.get("malId"),
            "title": info.get("name") or anime_data.get("name") or "Unknown Title",
            "poster": info.get("poster") or anime_data.get("poster"),
            "description": info.get("description", ""),
            "status": more_info.get("status", "") or anime_data.get("status", ""),
            "genres": more_info.get("genres", []) or anime_data.get("genres", []),
            "duration": stats.get("duration", "") or more_info.get("duration", ""),
            "type": stats.get("type", "") or anime_data.get("type", ""),
            "rating": stats.get("rating", ""),
            "quality": stats.get("quality", ""),
            "total_sub_episodes": safe_int((episodes or {}).get("sub")),
            "total_dub_episodes": safe_int((episodes or {}).get("dub")),
            "japanese": more_info.get("japanese"),
            "synonyms": more_info.get("synonyms"),
            "aired": more_info.get("aired"),
            "premiered": more_info.get("premiered"),
            "studios": more_info.get("studios"),
            "producers": more_info.get("producers", []),
            "malScore": more_info.get("malscore"),
            "promotionalVideos": info.get("promotionalVideos", []),
            "charactersVoiceActors": info.get("charactersVoiceActors", []),
            "characters": characters,
            "seasons": seasons,
            "relatedAnimes": related,
            "recommendedAnimes": recommended,
            "prequels": prequels,
            "sequels": sequels,
        }
    
    def _normalize_seasons(self, raw_seasons: List, info: Dict) -> List[Dict]:
        """Normalize season data"""
        return [
            {
                "id": s.get("id"),
                "anilistId": s.get("anilistId") or info.get("anilistId"),
                "malId": s.get("malId"),
                "title": s.get("title") or s.get("name"),
                "name": s.get("name"),
                "poster": s.get("poster"),
                "isCurrent": bool(s.get("isCurrent", False)),
            }
            for s in raw_seasons
            if isinstance(s, dict)
        ]
    
    def _normalize_related(self, raw_related: List) -> tuple:
        """Normalize related anime and extract prequels/sequels"""
        related = []
        prequels = []
        sequels = []

        def safe_int(val):
            try:
                return int(val)
            except (TypeError, ValueError):
                return 0

        for r in raw_related:
            if not isinstance(r, dict):
                continue
            entry = {
                "id": r.get("id"),
                "name": r.get("name"),
                "anilistId": r.get("anilistId"),
                "malId": r.get("malId"),
                "jname": r.get("jname"),
                "poster": r.get("poster"),
                "type": r.get("type"),
                "rating": r.get("rating"),
                "episodes_sub": safe_int((r.get("episodes") or {}).get("sub")),
                "episodes_dub": safe_int((r.get("episodes") or {}).get("dub")),
                "relation": r.get("relation") or r.get("relationType") or r.get("relation_name") or ""
            }
            related.append(entry)

            rel = (entry["relation"] or "").strip().lower()
            if "prequel" in rel:
                prequels.append(entry)
            elif "sequel" in rel:
                sequels.append(entry)

        return related, prequels, sequels
    
    def _normalize_recommended(self, raw_recommended: List) -> List[Dict]:
        """Normalize recommended anime"""
        def safe_int(val):
            try:
                return int(val)
            except (TypeError, ValueError):
                return 0

        recommended = []
        for r in raw_recommended:
            if not isinstance(r, dict):
                continue
            recommended.append({
                "id": r.get("id"),
                "name": r.get("name"),
                "jname": r.get("jname"),
                "poster": r.get("poster"),
                "type": r.get("type"),
                "duration": r.get("duration"),
                "rating": r.get("rating"),
                "episodes_sub": safe_int((r.get("episodes") or {}).get("sub")),
                "episodes_dub": safe_int((r.get("episodes") or {}).get("dub")),
            })
        return recommended
    
    def _normalize_characters(self, info: Dict) -> List[Dict]:
        """Normalize character and voice actor data"""
        raw_characters = info.get("charactersVoiceActors", []) if isinstance(info, dict) else []
        characters = []
        for cva in raw_characters:
            character = cva.get("character", {})
            voice_actor = cva.get("voiceActor", {})
            if not character or not voice_actor:
                continue

            characters.append({
                "character": {
                    "id": character.get("id"),
                    "name": character.get("name"),
                    "poster": character.get("poster"),
                    "cast": character.get("cast", "Unknown"),
                },
                "voiceActor": {
                    "id": voice_actor.get("id"),
                    "name": voice_actor.get("name"),
                    "poster": voice_actor.get("poster"),
                    "cast": voice_actor.get("cast", "Unknown"),
                }
            })
        return characters
