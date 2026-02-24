"""
Persistent ID Cache: maps hianime_id <-> anilist_id / mal_id.

Dual storage:
  1. MongoDB collection `yume-id-cache` (for production / Vercel)
  2. Local JSON file `data/id_cache.json` (for offline / local dev)

Both are kept in sync. Reads check local JSON first (fast), falls back to MongoDB.
Writes go to BOTH simultaneously.

JSON format:
{
    "one-piece-100": {"anilist_id": 21, "mal_id": 21, "title": "One Piece"},
    ...
}
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from pathlib import Path
import threading

from ..core.db_connector import db

logger = logging.getLogger(__name__)

# ----- Local JSON file -----
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOCAL_CACHE_PATH = _PROJECT_ROOT / "data" / "id_cache.json"
_local_cache: Dict[str, Dict[str, Any]] = {}
_local_lock = threading.Lock()


def _load_local_cache():
    """Load the local JSON cache into memory."""
    global _local_cache
    try:
        if LOCAL_CACHE_PATH.exists():
            with open(LOCAL_CACHE_PATH, "r") as f:
                _local_cache = json.load(f)
            logger.info("Loaded %d entries from local cache %s", len(_local_cache), LOCAL_CACHE_PATH)
        else:
            _local_cache = {}
    except Exception as e:
        logger.warning("Failed to load local cache: %s", e)
        _local_cache = {}


def _save_local_cache():
    """Write the in-memory cache to the local JSON file."""
    try:
        LOCAL_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOCAL_CACHE_PATH, "w") as f:
            json.dump(_local_cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning("Failed to save local cache: %s", e)


def _save_one_local(hianime_id: str, anilist_id: int, mal_id: int, title: str):
    """Update one entry in the local cache and flush to disk."""
    with _local_lock:
        existing = _local_cache.get(hianime_id, {})
        # Don't overwrite good values with 0
        _local_cache[hianime_id] = {
            "anilist_id": anilist_id if anilist_id else existing.get("anilist_id", 0),
            "mal_id": mal_id if mal_id else existing.get("mal_id", 0),
            "title": title if title else existing.get("title", ""),
        }
        _save_local_cache()


# Load local cache on import
_load_local_cache()


# ----- MongoDB collection -----
ID_CACHE_COLLECTION = "yume-id-cache"
_col = db[ID_CACHE_COLLECTION]

try:
    _col.create_index("anilist_id", sparse=True)
    _col.create_index("mal_id", sparse=True)
except Exception:
    pass


# ---------- Read helpers ----------

def get_hianime_id_by_anilist(anilist_id: int) -> Optional[str]:
    """Return the hianime_id mapped to an AniList ID, or None."""
    if not anilist_id:
        return None
    # Check local first
    with _local_lock:
        for hid, data in _local_cache.items():
            if data.get("anilist_id") == anilist_id:
                return hid
    # Fallback to MongoDB
    doc = _col.find_one({"anilist_id": anilist_id}, {"_id": 1})
    return doc["_id"] if doc else None


def get_hianime_id_by_mal(mal_id: int) -> Optional[str]:
    """Return the hianime_id mapped to a MAL ID, or None."""
    if not mal_id:
        return None
    with _local_lock:
        for hid, data in _local_cache.items():
            if data.get("mal_id") == mal_id:
                return hid
    doc = _col.find_one({"mal_id": mal_id}, {"_id": 1})
    return doc["_id"] if doc else None


def get_ids_for_hianime(hianime_id: str) -> Optional[Dict[str, Any]]:
    """Return {anilist_id, mal_id, title} for a hianime_id, or None."""
    # Check local first
    with _local_lock:
        if hianime_id in _local_cache:
            return _local_cache[hianime_id]
    # Fallback to MongoDB
    return _col.find_one({"_id": hianime_id})


def lookup_hianime_id(anilist_id: int = 0, mal_id: int = 0) -> Optional[str]:
    """Find the hianime_id using anilist_id first, then mal_id fallback."""
    if anilist_id:
        hid = get_hianime_id_by_anilist(anilist_id)
        if hid:
            return hid
    if mal_id:
        hid = get_hianime_id_by_mal(mal_id)
        if hid:
            return hid
    return None


# ---------- Write helpers ----------

def save_id_mapping(
    hianime_id: str,
    anilist_id: int = 0,
    mal_id: int = 0,
    title: str = "",
) -> bool:
    """Upsert one mapping to BOTH MongoDB and local JSON."""
    # 1) Save to local JSON immediately
    _save_one_local(hianime_id, anilist_id, mal_id, title)

    # 2) Save to MongoDB
    try:
        now = datetime.utcnow()
        set_fields: Dict[str, Any] = {"updated_at": now}
        if anilist_id:
            set_fields["anilist_id"] = anilist_id
        if mal_id:
            set_fields["mal_id"] = mal_id
        if title:
            set_fields["title"] = title

        set_on_insert: Dict[str, Any] = {"created_at": now}
        if not anilist_id:
            set_on_insert["anilist_id"] = 0
        if not mal_id:
            set_on_insert["mal_id"] = 0
        if not title:
            set_on_insert["title"] = ""

        _col.update_one(
            {"_id": hianime_id},
            {
                "$set": set_fields,
                "$setOnInsert": set_on_insert,
            },
            upsert=True,
        )
        return True
    except Exception as e:
        logger.error("save_id_mapping error for %s: %s", hianime_id, e)
        return False


# ---------- Query helpers ----------

def get_missing_ids(limit: int = 500) -> list:
    """Return hianime_ids that have anilist_id == 0 (need re-fetching)."""
    docs = _col.find(
        {"$or": [{"anilist_id": 0}, {"anilist_id": {"$exists": False}}]},
        {"_id": 1, "title": 1},
    ).limit(limit)
    return list(docs)


def get_cache_stats() -> Dict[str, Any]:
    """Return stats about both MongoDB and local caches."""
    total = _col.count_documents({})
    with_anilist = _col.count_documents({"anilist_id": {"$gt": 0}})
    with_mal = _col.count_documents({"mal_id": {"$gt": 0}})
    missing = _col.count_documents(
        {"$or": [{"anilist_id": 0}, {"anilist_id": {"$exists": False}}]}
    )
    with _local_lock:
        local_count = len(_local_cache)
    return {
        "total": total,
        "with_anilist_id": with_anilist,
        "with_mal_id": with_mal,
        "missing_anilist_id": missing,
        "local_file": str(LOCAL_CACHE_PATH),
        "local_entries": local_count,
    }


def preload_to_memory() -> tuple:
    """Load all anilist_id -> hianime_id AND mal_id -> hianime_id mappings.
    Returns (anilist_mapping, mal_mapping) dicts."""
    anilist_map: Dict[int, str] = {}
    mal_map: Dict[int, str] = {}
    
    # Load from local first (fast, no network)
    with _local_lock:
        for hid, data in _local_cache.items():
            aid = data.get("anilist_id", 0)
            mid = data.get("mal_id", 0)
            if aid and aid > 0:
                anilist_map[aid] = hid
            if mid and mid > 0:
                mal_map[mid] = hid
    
    # Then fill gaps from MongoDB
    for doc in _col.find({}, {"_id": 1, "anilist_id": 1, "mal_id": 1}):
        aid = doc.get("anilist_id", 0)
        mid = doc.get("mal_id", 0)
        if aid and aid > 0 and aid not in anilist_map:
            anilist_map[aid] = doc["_id"]
        if mid and mid > 0 and mid not in mal_map:
            mal_map[mid] = doc["_id"]
    
    return anilist_map, mal_map


def sync_local_from_mongodb():
    """Download ALL entries from MongoDB and save to local JSON file."""
    global _local_cache
    count = 0
    with _local_lock:
        for doc in _col.find({}, {"_id": 1, "anilist_id": 1, "mal_id": 1, "title": 1}):
            _local_cache[doc["_id"]] = {
                "anilist_id": doc.get("anilist_id", 0),
                "mal_id": doc.get("mal_id", 0),
                "title": doc.get("title", ""),
            }
            count += 1
        _save_local_cache()
    logger.info("Synced %d entries from MongoDB to local file %s", count, LOCAL_CACHE_PATH)
    return count


def auto_cache_from_info(hianime_id: str, info: dict):
    """Auto-save IDs to cache when a user views an anime page.
    Call this after get_anime_info() returns — completely safe, never throws."""
    try:
        if not info or not isinstance(info, dict):
            return
        anilist_id = info.get("anilistId") or info.get("alID") or 0
        mal_id = info.get("malId") or info.get("malID") or 0
        title = info.get("title") or info.get("name") or ""
        if anilist_id or mal_id:
            save_id_mapping(hianime_id, anilist_id, mal_id, title)
    except Exception:
        pass  # never break the page

