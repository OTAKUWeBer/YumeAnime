"""
Video scraper main interface
Provides high-level API for fetching video sources
"""
from typing import Dict, Any
from .megaplay_scraper import MegaplayScraper


def get_megaplay_url(ep_id: str, language: str = "sub") -> str:
    """
    Get the megaplay embed URL
    """
    language = language.lower()
    if language not in ("sub", "dub"):
        language = "sub"
        
    return f"https://megaplay.buzz/stream/s-2/{ep_id}/{language}"


def get_and_play_m3u8_and_vtt(ep_id: str, language: str = "sub") -> Dict[str, Any]:
    """
    Build megaplay URL and return proxied m3u8 + vtt info (synchronous)
    
    Args:
        ep_id: Episode ID
        language: 'sub' or 'dub'
        
    Returns:
        Dictionary with video sources and subtitle tracks
        
    Raises:
        ValueError: If language is not 'sub' or 'dub'
    """
    language = language.lower()
    if language not in ("sub", "dub"):
        raise ValueError("language must be 'sub' or 'dub'")

    megaplay_url = f"https://megaplay.buzz/stream/s-2/{ep_id}/{language}"
    
    scraper = MegaplayScraper()
    result = scraper.fetch_video_info(megaplay_url)
    return result


def main():
    """Example usage"""
    ep_id = "94597"  # Example episode ID
    language = "sub"  # or "dub"
    result = get_and_play_m3u8_and_vtt(ep_id, language)
    return result


if __name__ == "__main__":
    main()
