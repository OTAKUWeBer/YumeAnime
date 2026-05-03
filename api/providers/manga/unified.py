"""
Unified MangaScraper — dispatches to per-source modules.
"""
import logging
from . import manga_atsumaru

logger = logging.getLogger(__name__)

SOURCES = {
    "atsumaru": {"module": manga_atsumaru, "name": "Atsumaru", "referer": manga_atsumaru.REFERER},
    # "comix": {"module": comix, "name": "Comix", "referer": comix.REFERER},
}
DEFAULT_SOURCE = "atsumaru"


def _src(source):
    return SOURCES.get(source or DEFAULT_SOURCE, SOURCES[DEFAULT_SOURCE])


class MangaScraper:
    """Unified manga scraper with multi-source support."""

    @staticmethod
    def get_sources():
        return {k: v["name"] for k, v in SOURCES.items()}

    @staticmethod
    def home(source=None):
        try:
            return _src(source)["module"].home()
        except Exception as e:
            logger.error("Manga home error (%s): %s", source, e)
            return {}

    @staticmethod
    def details(manga_id, source=None):
        try:
            return _src(source)["module"].details(manga_id)
        except Exception as e:
            logger.error("Manga details error (%s/%s): %s", source, manga_id, e)
            return None

    @staticmethod
    def chapter_images(manga_id, chapter_id, source=None):
        try:
            return _src(source)["module"].chapter_images(manga_id, chapter_id)
        except Exception as e:
            logger.error("Manga chapter error (%s/%s/%s): %s", source, manga_id, chapter_id, e)
            return [], _src(source).get("referer", "")

    @staticmethod
    def search(query, source=None):
        try:
            return _src(source)["module"].search(query)
        except Exception as e:
            logger.error("Manga search error (%s/%s): %s", source, query, e)
            return {"entries": [], "found": 0}

    @staticmethod
    def get_referer(source=None):
        return _src(source).get("referer", "")
