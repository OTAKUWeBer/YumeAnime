"""
Video scraper utility functions
Handles URL encoding, episode ID extraction, and subtitle sorting
"""
import base64
import re
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup


def encode_proxy(url: str) -> str:
    """
    Return proxied URL through Vercel http-proxy-zai (base64-encoded)
    
    Args:
        url: Original URL to proxy
        
    Returns:
        Proxied URL
    """
    encoded = base64.b64encode(url.encode()).decode()
    return f"https://http-proxy-zai.vercel.app/proxy/{encoded}"


def extract_episode_id(html: str, soup: BeautifulSoup) -> Optional[str]:
    """
    Try multiple methods to extract numeric episode ID from the page
    
    Args:
        html: Raw HTML content
        soup: BeautifulSoup parsed HTML
        
    Returns:
        Episode ID string or None if not found
    """
    # Method A: title contains a numeric token
    if soup.title and soup.title.string:
        title_text = soup.title.string.strip()
        m = re.search(r"\d{3,}", title_text)
        if m:
            return m.group(0)

    # Method B: search for getSources?id= in page/JS
    m2 = re.search(r"getSources\?id=(\d+)", html)
    if m2:
        return m2.group(1)

    # Method C: look for patterns like id: 12345 or "id" = "12345"
    m3 = re.search(r"['\" ]id['\"]\s*[:=]\s*['\"]?(\d{3,})['\"]?", html)
    if m3:
        return m3.group(1)

    return None


def sort_subtitle_priority(track: Dict[str, Any]) -> int:
    """
    Sort function to prioritize English subtitles
    
    Args:
        track: Subtitle track dictionary
        
    Returns:
        Priority value (0=highest, 2=lowest)
    """
    if not isinstance(track, dict):
        return 2
    
    # Check language field
    lang = track.get("lang", "").lower()
    if lang in ("en", "eng", "english"):
        return 0
    
    # Check label field
    label = track.get("label", "").lower()
    if "english" in label or "eng" in label:
        return 0
    
    # Check if explicitly marked as default
    if track.get("default") is True:
        return 1
    
    # All other languages come last
    return 2


def proxy_video_sources(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Patch all file links in video data to go through proxy
    
    Args:
        data: Video data dictionary with sources and tracks
        
    Returns:
        Modified data with proxied URLs
    """
    if not isinstance(data, dict):
        return data
    
    # Proxy video sources
    sources = data.get("sources")
    if isinstance(sources, dict) and "file" in sources:
        sources["file"] = encode_proxy(sources["file"])
    elif isinstance(sources, list):
        for s in sources:
            if isinstance(s, dict) and s.get("file"):
                s["file"] = encode_proxy(s["file"])

    # Proxy subtitle tracks
    if "tracks" in data and isinstance(data["tracks"], list):
        for track in data["tracks"]:
            if isinstance(track, dict) and "file" in track:
                track["file"] = encode_proxy(track["file"])
        
        # Sort tracks with English first
        data["tracks"].sort(key=sort_subtitle_priority)

    return data
