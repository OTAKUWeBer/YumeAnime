#!/usr/bin/env python3
"""
build_id_cache.py  –  Scrape ALL anime from HiAnime A-Z list and save
hianime_id ↔ anilist_id / mal_id mappings to MongoDB.

Usage:
    python build_id_cache.py              # scrape ALL anime (A-Z, all pages)
    python build_id_cache.py --update     # re-fetch entries with anilist_id == 0
    python build_id_cache.py --stats      # show cache statistics
    python build_id_cache.py --letter a   # only scrape letter 'a'

Run from the project root:
    cd /path/to/YumeAnime && python build_id_cache.py
"""
import os
import sys
import asyncio
import argparse
import logging
import time

# Ensure the project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from api.providers.hianime import HianimeScraper
from api.utils.id_cache import (
    save_id_mapping, get_missing_ids, get_cache_stats, get_ids_for_hianime,
    sync_local_from_mongodb,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

HA = HianimeScraper()

# Stats
GLOBAL_STATS = {
    "fetched": 0,
    "cached": 0,
    "failed": 0,
    "skipped": 0,
}


async def fetch_and_save_one(anime_id: str):
    """Fetch ONE anime's info, save to DB immediately, print result."""
    # Skip if already cached
    existing = get_ids_for_hianime(anime_id)
    if existing and existing.get("anilist_id", 0) > 0:
        GLOBAL_STATS["skipped"] += 1
        return

    try:
        info = await HA.get_anime_info(anime_id)
        if not info:
            GLOBAL_STATS["failed"] += 1
            logger.warning("  ✗ %s — no info returned", anime_id)
            return

        anilist_id = info.get("anilistId") or 0
        mal_id = info.get("malId") or 0
        title = info.get("title") or anime_id

        # Save IMMEDIATELY
        save_id_mapping(
            hianime_id=anime_id,
            anilist_id=anilist_id,
            mal_id=mal_id,
            title=title,
        )
        GLOBAL_STATS["cached"] += 1

        # Print right away
        logger.info(
            "  ✓ SAVED  %-45s  anilist=%-8s  mal=%-8s",
            title[:45], anilist_id or "—", mal_id or "—",
        )

    except Exception as e:
        GLOBAL_STATS["failed"] += 1
        logger.warning("  ✗ %s — %s", anime_id, e)


async def scrape_az_letter(letter: str):
    """Scrape all pages of a single A-Z letter/option."""
    page = 1
    total_for_letter = 0

    while True:
        logger.info("Fetching A-Z list: letter='%s' page=%d ...", letter, page)
        try:
            data = await HA.az_list(sort_option=letter, page=page)
            animes = data.get("animes", []) if isinstance(data, dict) else []

            if not animes:
                logger.info("No more results for letter='%s' at page=%d", letter, page)
                break

            anime_ids = [a.get("id") for a in animes if a.get("id")]
            total_for_letter += len(anime_ids)

            # Fetch and save ONE BY ONE — each saved immediately
            for aid in anime_ids:
                await fetch_and_save_one(aid)

            # Check if there are more pages
            total_pages = 1
            if isinstance(data, dict):
                total_pages = data.get("totalPages", 1) or 1
                # Also handle case where it's nested
                if isinstance(data.get("pagination"), dict):
                    total_pages = data["pagination"].get("totalPages", total_pages)

            if page >= total_pages:
                break

            page += 1
            await asyncio.sleep(0.2)

        except Exception as e:
            logger.error("Error fetching letter='%s' page=%d: %s", letter, page, e)
            break

    logger.info(
        "Letter '%s' done: %d anime found | Running total: cached=%d, skipped=%d, failed=%d",
        letter, total_for_letter,
        GLOBAL_STATS["cached"], GLOBAL_STATS["skipped"], GLOBAL_STATS["failed"],
    )


async def scrape_all(letter_filter: str = None):
    """Scrape ALL anime from HiAnime using the A-Z list endpoint."""
    # All sort options: 'all' gets everything, then individual letters
    sort_options = ["all"] + [chr(c) for c in range(ord("a"), ord("z") + 1)] + [
        "0-9",  # numbers
    ]

    if letter_filter:
        sort_options = [letter_filter]
        logger.info("Filtering to letter: %s", letter_filter)
    else:
        logger.info("Starting FULL A-Z scrape (%d categories)...", len(sort_options))

    start = time.time()

    for letter in sort_options:
        await scrape_az_letter(letter)

    elapsed = time.time() - start
    logger.info(
        "=== SCRAPE COMPLETE in %.1fs ===\n"
        "  Cached:  %d\n"
        "  Skipped: %d (already cached)\n"
        "  Failed:  %d",
        elapsed,
        GLOBAL_STATS["cached"],
        GLOBAL_STATS["skipped"],
        GLOBAL_STATS["failed"],
    )


async def update_missing():
    """Re-fetch entries that have anilist_id == 0."""
    missing = get_missing_ids(limit=5000)
    if not missing:
        logger.info("No entries with missing anilist_id. Cache is fully populated!")
        return

    logger.info("Found %d entries with missing anilist_id, re-fetching...", len(missing))

    for doc in missing:
        await fetch_and_save_one(doc["_id"])

    logger.info(
        "Update done: cached=%d, failed=%d",
        GLOBAL_STATS["cached"], GLOBAL_STATS["failed"],
    )


def show_stats():
    """Print cache statistics."""
    stats = get_cache_stats()
    print("\n=== ID Cache Statistics ===")
    print(f"  MongoDB entries:       {stats['total']}")
    print(f"  With AniList ID:       {stats['with_anilist_id']}")
    print(f"  With MAL ID:           {stats['with_mal_id']}")
    print(f"  Missing AniList ID:    {stats['missing_anilist_id']}")
    coverage = (stats['with_anilist_id'] / stats['total'] * 100) if stats['total'] > 0 else 0
    print(f"  Coverage:              {coverage:.1f}%")
    print(f"  Local JSON file:       {stats.get('local_file', '—')}")
    print(f"  Local entries:         {stats.get('local_entries', 0)}")
    print()


async def main():
    parser = argparse.ArgumentParser(description="Scrape ALL HiAnime anime and cache AniList/MAL IDs")
    parser.add_argument("--update", action="store_true",
                        help="Only re-fetch entries with anilist_id == 0")
    parser.add_argument("--stats", action="store_true",
                        help="Show cache statistics and exit")
    parser.add_argument("--download", action="store_true",
                        help="Download all entries from MongoDB to local JSON file")
    parser.add_argument("--letter", type=str, default=None,
                        help="Only scrape a specific letter (e.g. 'a', 'all', '0-9')")
    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    if args.download:
        count = sync_local_from_mongodb()
        print(f"\n✓ Downloaded {count} entries from MongoDB to local JSON file")
        show_stats()
        return

    start = time.time()

    if args.update:
        await update_missing()
    else:
        await scrape_all(letter_filter=args.letter)

    elapsed = time.time() - start
    logger.info("Total time: %.1fs", elapsed)
    show_stats()


if __name__ == "__main__":
    asyncio.run(main())
