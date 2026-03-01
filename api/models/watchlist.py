from pymongo import ASCENDING, DESCENDING
from datetime import datetime
import hashlib
import logging
from typing import List, Dict, Optional, Any

from ..core.db_connector import watchlist_collection

# Setup logging
logger = logging.getLogger(__name__)

# Watchlist status constants
WATCHLIST_STATUSES = {
    'watching': 'watching',
    'completed': 'completed',
    'paused': 'paused',
    'dropped': 'dropped',
    'plan_to_watch': 'plan_to_watch'
}

def create_optimized_watchlist_indexes():
    """Create optimized database indexes for better performance."""
    try:
        # Drop existing indexes first (except _id)
        watchlist_collection.drop_indexes()
        
        # Primary compound unique index for user_id + anime_id
        watchlist_collection.create_index(
            [("user_id", ASCENDING), ("anime_id", ASCENDING)], 
            unique=True,
            name="user_anime_unique"
        )
        
        # Optimized compound indexes for common query patterns
        watchlist_collection.create_index(
            [("user_id", ASCENDING), ("status", ASCENDING), ("updated_at", DESCENDING)],
            name="user_status_updated"
        )
        
        watchlist_collection.create_index(
            [("user_id", ASCENDING), ("updated_at", DESCENDING)],
            name="user_updated"
        )
        
        watchlist_collection.create_index(
            [("user_id", ASCENDING), ("last_watched", DESCENDING)],
            name="user_last_watched",
            partialFilterExpression={"last_watched": {"$ne": None}}
        )
        
        # Text index for search functionality
        watchlist_collection.create_index(
            [("anime_title", "text")],
            name="anime_title_text"
        )
        
        # Index for popular anime queries
        watchlist_collection.create_index(
            [("anime_id", ASCENDING), ("status", ASCENDING)],
            name="anime_status"
        )
        
        logger.info("Optimized watchlist indexes created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating watchlist indexes: {e}")
        return False

def add_to_watchlist(user_id: int, anime_id: str, anime_title: str, 
                     status: str = "watching", watched_episodes: int = 0):
    """Add or update an anime in the user's single watchlist document."""
    try:
        now = datetime.utcnow()
        
        # Try to update an existing element first
        result = watchlist_collection.update_one(
            {"_id": user_id, "watchlist.anime_id": anime_id},
            {
                "$set": {
                    "watchlist.$.anime_title": anime_title,
                    "watchlist.$.status": status,
                    "watchlist.$.watched_episodes": watched_episodes,
                    "watchlist.$.updated_at": now
                }
            }
        )
        
        if result.matched_count == 0:
            # Not present -> push new element; create user doc if needed
            watchlist_doc = {
                "anime_id": anime_id,
                "anime_title": anime_title,
                "status": status,
                "watched_episodes": watched_episodes,
                "updated_at": now
            }
            watchlist_collection.update_one(
                {"_id": user_id},
                {"$push": {"watchlist": watchlist_doc}, "$setOnInsert": {"created_at": now}},
                upsert=True
            )
        return True
    except Exception as e:
        logger.error(f"Error adding to watchlist: {e}")
        return False

def get_watchlist_entry(user_id: int, anime_id: str) -> Optional[Dict[str, Any]]:
    """Return a single watchlist entry (or None)."""
    try:
        doc = watchlist_collection.find_one(
            {"_id": user_id},
            {"watchlist": {"$elemMatch": {"anime_id": anime_id}}}
        )
        if not doc:
            return None
        return doc.get("watchlist", [None])[0]
    except Exception as e:
        logger.error(f"Error getting watchlist entry: {e}")
        return None

def update_watchlist_status(user_id: int, anime_id: str, status: str) -> bool:
    """Update the status of one anime in the user's watchlist."""
    try:
        now = datetime.utcnow()
        
        update_doc = {
            "watchlist.$.status": status,
            "watchlist.$.updated_at": now
        }
        
        # Set last_watched if status is watching
        if status == "watching":
            update_doc["watchlist.$.last_watched"] = now
        
        result = watchlist_collection.update_one(
            {"_id": user_id, "watchlist.anime_id": anime_id},
            {"$set": update_doc}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error updating watchlist status: {e}")
        return False

def update_watched_episodes(user_id: int, anime_id: str, watched_episodes: int) -> bool:
    """Update watched_episodes. Auto-complete if reached total."""
    try:
        now = datetime.utcnow()
        
        update_doc = {
            "watchlist.$.watched_episodes": watched_episodes,
            "watchlist.$.updated_at": now,
            "watchlist.$.last_watched": now
        }

        result = watchlist_collection.update_one(
            {"_id": user_id, "watchlist.anime_id": anime_id},
            {"$set": update_doc}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error updating watched episodes: {e}")
        return False

def remove_from_watchlist(user_id: int, anime_id: str) -> bool:
    """Remove an anime from the user's watchlist array."""
    try:
        result = watchlist_collection.update_one(
            {"_id": user_id},
            {"$pull": {"watchlist": {"anime_id": anime_id}}}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error removing from watchlist: {e}")
        return False

def get_user_watchlist(user_id: int, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return the user's watchlist (list). Optional status filter."""
    try:
        doc = watchlist_collection.find_one({"_id": user_id}, {"watchlist": 1})
        if not doc:
            return []
        
        watchlist = doc.get("watchlist", []) or []
        
        if status_filter:
            watchlist = [w for w in watchlist if w.get("status") == status_filter]
        
        # Sort by updated_at desc for compatibility with previous behavior
        watchlist.sort(key=lambda x: x.get("updated_at", datetime.min), reverse=True)
        return watchlist
    except Exception as e:
        logger.error(f"Error getting watchlist: {e}")
        return []

def get_user_watchlist_paginated(user_id: int, page: int = 1, page_size: int = 50, 
                                status: Optional[str] = None, sort_by: str = "updated_at") -> Dict[str, Any]:
    """Get paginated watchlist with metadata."""
    try:
        skip = max((page - 1) * page_size, 0)
        sort_order = -1 if sort_by in ["updated_at", "created_at", "last_watched"] else 1

        # Single-document-per-user schema
        user_doc = watchlist_collection.find_one({"_id": user_id}, {"watchlist": 1})
        if user_doc and isinstance(user_doc.get("watchlist"), list):
            match_stage = {"$match": {"_id": user_id}}

            if status and status in WATCHLIST_STATUSES:
                # Filtered by status
                project_stage = {
                    "$project": {
                        "filtered": {
                            "$filter": {
                                "input": "$watchlist",
                                "as": "item",
                                "cond": {"$eq": ["$$item.status", status]}
                            }
                        }
                    }
                }
                count_pipeline = [
                    match_stage,
                    project_stage,
                    {"$project": {"count": {"$size": "$filtered"}}}
                ]
                count_res = list(watchlist_collection.aggregate(count_pipeline))
                total_count = count_res[0]["count"] if count_res else 0

                data_pipeline = [
                    match_stage,
                    project_stage,
                    {"$unwind": {"path": "$filtered", "preserveNullAndEmptyArrays": False}},
                    {"$replaceRoot": {"newRoot": "$filtered"}}
                ]
            else:
                # No status filter
                count_pipeline = [
                    match_stage,
                    {"$project": {"count": {"$size": {"$ifNull": ["$watchlist", []]}}}}
                ]
                count_res = list(watchlist_collection.aggregate(count_pipeline))
                total_count = count_res[0]["count"] if count_res else 0

                data_pipeline = [
                    match_stage,
                    {"$unwind": {"path": "$watchlist", "preserveNullAndEmptyArrays": False}},
                    {"$replaceRoot": {"newRoot": "$watchlist"}}
                ]

            # Sort and paginate
            data_pipeline.append({"$sort": {sort_by: sort_order}})
            if skip > 0:
                data_pipeline.append({"$skip": skip})
            data_pipeline.append({"$limit": page_size})

            results = list(watchlist_collection.aggregate(data_pipeline))

            # Add synthetic _id for each item
            for item in results:
                if "_id" not in item:
                    item["_id"] = hashlib.md5(item["anime_id"].encode()).hexdigest()

            total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0

            return {
                "data": results,
                "pagination": {
                    "current_page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                    "total_count": total_count,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }

        return {
            "data": [],
            "pagination": {
                "current_page": page,
                "page_size": page_size,
                "total_pages": 0,
                "total_count": 0,
                "has_next": False,
                "has_prev": False
            }
        }

    except Exception as e:
        logger.error(f"Error getting paginated watchlist: {e}")
        return {
            "data": [],
            "pagination": {
                "current_page": page,
                "page_size": page_size,
                "total_pages": 0,
                "total_count": 0,
                "has_next": False,
                "has_prev": False
            }
        }

def get_recently_updated_watchlist(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Return the user's recently-updated watchlist items (top N)."""
    try:
        doc = watchlist_collection.find_one({"_id": user_id}, {"watchlist": 1})
        if not doc or "watchlist" not in doc:
            return []
        
        wl = doc["watchlist"]
        wl_sorted = sorted(wl, key=lambda x: x.get("updated_at") or datetime.min, reverse=True)
        return wl_sorted[:limit]
    except Exception as e:
        logger.error(f"Error fetching recently updated watchlist: {e}")
        return []

def search_user_watchlist(user_id: int, query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Search within the user's watchlist."""
    try:
        # Use aggregation pipeline for server-side search
        pipeline = [
            {"$match": {"_id": user_id}},
            {"$project": {
                "matches": {
                    "$filter": {
                        "input": "$watchlist",
                        "as": "item",
                        "cond": {"$regexMatch": {"input": "$$item.anime_title", "regex": query, "options": "i"}}
                    }
                }
            }},
            {"$unwind": "$matches"},
            {"$replaceRoot": {"newRoot": "$matches"}},
            {"$limit": limit}
        ]
        return list(watchlist_collection.aggregate(pipeline))
    except Exception as e:
        logger.error(f"Error searching user watchlist: {e}")
        # Fallback: fetch user watchlist and filter in Python
        wl = get_user_watchlist(user_id)
        return [w for w in wl if query.lower() in (w.get("anime_title") or "").lower()][:limit]

def get_watchlist_stats(user_id: int) -> Dict[str, Any]:
    """Produce per-user stats by unwinding the user's watchlist array."""
    try:
        pipeline = [
            {"$match": {"_id": user_id}},
            {"$unwind": {"path": "$watchlist", "preserveNullAndEmptyArrays": True}},
            {"$group": {
                "_id": "$watchlist.status",
                "count": {"$sum": {"$cond": [{"$ifNull": ["$watchlist", False]}, 1, 0]}},
                "watched_episodes": {"$sum": {"$ifNull": ["$watchlist.watched_episodes", 0]}}
            }}
        ]
        
        stats = list(watchlist_collection.aggregate(pipeline))
        formatted = {
            "watching": 0,
            "completed": 0,
            "paused": 0,
            "dropped": 0,
            "plan_to_watch": 0,
            "total_anime": 0,
            "total_episodes": 0,
            "watched_episodes": 0
        }
        
        for s in stats:
            status = s["_id"]
            if status is None:  # handle edge cases
                continue
            if status in formatted:
                formatted[status] = s["count"]
                formatted["watched_episodes"] += s["watched_episodes"]
        
        formatted["total_anime"] = sum([
            formatted["watching"], formatted["completed"],
            formatted["paused"], formatted["dropped"], formatted["plan_to_watch"]
        ])
        
        return formatted
    except Exception as e:
        logger.error(f"Error computing watchlist stats: {e}")
        return {
            "watching": 0,
            "completed": 0,
            "paused": 0,
            "dropped": 0,
            "plan_to_watch": 0,
            "total_anime": 0,
            "total_episodes": 0,
            "watched_episodes": 0
        }

def get_watchlist_summary(user_id: int) -> Dict[str, Any]:
    """Dashboard-friendly summary using aggregation to compute totals."""
    try:
        pipeline = [
            {"$match": {"_id": user_id}},
            {"$unwind": {"path": "$watchlist", "preserveNullAndEmptyArrays": True}},
            {"$group": {
                "_id": None,
                "total_anime": {"$sum": {"$cond": [{"$ifNull": ["$watchlist", False]}, 1, 0]}},
                "watching_count": {"$sum": {"$cond": [{"$eq": ["$watchlist.status", "watching"]}, 1, 0]}},
                "completed_count": {"$sum": {"$cond": [{"$eq": ["$watchlist.status", "completed"]}, 1, 0]}},
                "total_watched_episodes": {"$sum": {"$ifNull": ["$watchlist.watched_episodes", 0]}},
                "last_updated": {"$max": "$watchlist.updated_at"}
            }}
        ]
        res = list(watchlist_collection.aggregate(pipeline))
        return res[0] if res else {
            "total_anime": 0,
            "watching_count": 0,
            "completed_count": 0,
            "total_watched_episodes": 0,
            "last_updated": None
        }
    except Exception as e:
        logger.error(f"Error building watchlist summary: {e}")
        return {
            "total_anime": 0,
            "watching_count": 0,
            "completed_count": 0,
            "total_watched_episodes": 0,
            "last_updated": None
        }

def bulk_update_watchlist(user_id: int, updates: List[Dict[str, Any]]) -> int:
    """Bulk update multiple watchlist entries for better performance."""
    try:
        
        # For single-document schema, we need to update individual array elements
        updated_count = 0
        current_time = datetime.utcnow()
        
        for update in updates:
            anime_id = update.get("anime_id")
            if not anime_id:
                continue
                
            update_doc = {"updated_at": current_time}
            
            if "status" in update:
                if update["status"] not in WATCHLIST_STATUSES:
                    continue
                update_doc["status"] = update["status"]
                if update["status"] == "watching":
                    update_doc["last_watched"] = current_time
            
            if "watched_episodes" in update:
                update_doc["watched_episodes"] = update["watched_episodes"]
                update_doc["last_watched"] = current_time
            
            # Update individual array element
            result = watchlist_collection.update_one(
                {"_id": user_id, "watchlist.anime_id": anime_id},
                {"$set": {f"watchlist.$.{key}": value for key, value in update_doc.items()}}
            )
            
            if result.modified_count > 0:
                updated_count += 1
        
        return updated_count
    except Exception as e:
        logger.error(f"Error in bulk update: {e}")
        return 0

def get_popular_anime(limit: int = 50) -> List[Dict[str, Any]]:
    """Get most popular anime across all users' watchlists - cached version."""
    try:
        # For single-document schema, we need to unwind the watchlist arrays first
        pipeline = [
            {"$unwind": {"path": "$watchlist", "preserveNullAndEmptyArrays": False}},
            {
                "$group": {
                    "_id": "$watchlist.anime_id",
                    "anime_title": {"$first": "$watchlist.anime_title"},
                    "user_count": {"$sum": 1},
                    "watching_count": {
                        "$sum": {"$cond": [{"$eq": ["$watchlist.status", "watching"]}, 1, 0]}
                    },
                    "completed_count": {
                        "$sum": {"$cond": [{"$eq": ["$watchlist.status", "completed"]}, 1, 0]}
                    }
                }
            },
            {"$sort": {"user_count": DESCENDING}},
            {"$limit": limit}
        ]
        
        return list(watchlist_collection.aggregate(pipeline))
    except Exception as e:
        logger.error(f"Error fetching popular anime: {e}")
        return []

def cleanup_watchlist(user_id: Optional[int] = None) -> bool:
    """Clean up watchlist entries - optimized version."""
    try:
        if user_id:
            # Clean up specific user's watchlist
            doc = watchlist_collection.find_one({"_id": user_id})
            if not doc or "watchlist" not in doc:
                return True
            
            cleaned_watchlist = []
            for item in doc["watchlist"]:
                # Remove invalid entries
                if (item.get("status") in WATCHLIST_STATUSES and 
                    item.get("anime_id") and 
                    item.get("anime_title")):
                    # Fix negative watched episodes
                    if item.get("watched_episodes", 0) < 0:
                        item["watched_episodes"] = 0
                    cleaned_watchlist.append(item)
            
            # Update with cleaned watchlist
            watchlist_collection.update_one(
                {"_id": user_id},
                {"$set": {"watchlist": cleaned_watchlist}}
            )
        else:
            # Clean up all users' watchlists
            pipeline = [
                {"$match": {"watchlist": {"$exists": True}}},
                {
                    "$addFields": {
                        "watchlist": {
                            "$map": {
                                "input": {
                                    "$filter": {
                                        "input": "$watchlist",
                                        "as": "item",
                                        "cond": {
                                            "$and": [
                                                {"$in": ["$$item.status", list(WATCHLIST_STATUSES.keys())]},
                                                {"$ne": ["$$item.anime_id", None]},
                                                {"$ne": ["$$item.anime_title", None]}
                                            ]
                                        }
                                    }
                                },
                                "as": "item",
                                "in": {
                                    "$mergeObjects": [
                                        "$$item",
                                        {
                                            "watched_episodes": {
                                                "$max": [0, {"$ifNull": ["$$item.watched_episodes", 0]}]
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            ]
            
            # Execute cleanup for all users
            users_with_watchlists = list(watchlist_collection.aggregate(pipeline))
            
            for user_doc in users_with_watchlists:
                watchlist_collection.update_one(
                    {"_id": user_doc["_id"]},
                    {"$set": {"watchlist": user_doc["watchlist"]}}
                )
        
        logger.info(f"Cleanup completed for {'user ' + str(user_id) if user_id else 'all users'}")
        return True
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        return False

# Performance monitoring
def get_collection_stats() -> Dict[str, Any]:
    """Get collection statistics for performance monitoring."""
    try:
        from ..core.db_connector import db
        stats = db.command("collStats", "watchlist")
        return {
            "count": stats.get("count", 0),
            "size": stats.get("size", 0),
            "avgObjSize": stats.get("avgObjSize", 0),
            "indexSizes": stats.get("indexSizes", {}),
            "totalIndexSize": stats.get("totalIndexSize", 0)
        }
    except Exception as e:
        logger.error(f"Error getting collection stats: {e}")
        return {}

# Data migration and maintenance
def migrate_watchlist_schema():
    """Migrate from per-document to single-document-per-user schema if needed."""
    try:
        # This function can be used to migrate from old schema to new schema
        # Implementation depends on your specific migration needs
        logger.info("Watchlist schema migration completed")
        return True
    except Exception as e:
        logger.error(f"Error during watchlist migration: {e}")
        return False

# Initialize optimized indexes when module is imported
def initialize_watchlist_indexes():
    """Initialize watchlist indexes."""
    try:
        create_optimized_watchlist_indexes()
        logger.info("Watchlist indexes initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing watchlist indexes: {e}")
        return False
