"""
Video scraper utility functions
Handles URL encoding, episode ID extraction, subtitle sorting, and proxying.
"""
import base64
import re
from typing import Optional, List, Dict, Any, Union
import os
import dotenv
from bs4 import BeautifulSoup

dotenv.load_dotenv()
proxy_url = os.getenv("PROXY_URL")

# Enforce HTTPS on proxy URL to prevent mixed content blocking
if proxy_url and proxy_url.startswith("http://"):
    proxy_url = proxy_url.replace("http://", "https://", 1)

def encode_proxy(url: Optional[str]) -> Optional[str]:
    """
    Return proxied URL through Vercel http-proxy-zai (base64-encoded).
    If url is falsy, returns it unchanged.
    Always ensures the proxy URL uses HTTPS to avoid mixed content blocking.
    """
    if not url:
        return url
    try:
        encoded = base64.b64encode(url.encode()).decode()
        result = f'{proxy_url}{encoded}'
        if result.startswith("http://"):
            result = result.replace("http://", "https://", 1)
        return result
    except Exception:
        # If encoding fails, return original URL rather than crash
        return url


def extract_episode_id(data: Union[str, Dict[str, Any], BeautifulSoup]) -> Optional[str]:
    """
    Try multiple methods to extract numeric episode ID.

    Accepts:
      - dict (the `result` from episode_sources)
      - raw HTML string
      - BeautifulSoup object

    If a dict is passed, will set data['episode_id'] when found.

    Returns episode id string or None.
    """
    def find_in_text(text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        # try query param style ?ep=12345 or &ep=12345
        m = re.search(r"[?&]ep=(\d+)", text)
        if m:
            return m.group(1)
        # /ep/12345 or /episode/12345
        m = re.search(r"/(?:ep|episode)/(\d+)", text)
        if m:
            return m.group(1)
        # look for long numeric tokens (5+ digits)
        m = re.search(r"(\d{5,})", text)
        if m:
            return m.group(1)
        return None

    # If dict: inspect known fields first
    if isinstance(data, dict):
        # 1) direct episode id fields (prefer ep param in episodeId)
        for key in ("episodeId", "episode_id", "ep_id", "id"):
            if key in data and data[key]:
                val = str(data[key])
                ep = find_in_text(val)
                if ep:
                    data["episode_id"] = ep
                    return ep
                # if value itself is numeric-ish, use it
                m = re.search(r"^\d+$", val)
                if m:
                    data["episode_id"] = val
                    return val

        # 2) inspect sources & tracks for urls that contain ?ep=
        candidates: List[str] = []
        sources = data.get("sources")
        if isinstance(sources, dict):
            candidates.extend([str(sources.get(k)) for k in ("url", "file") if sources.get(k)])
        elif isinstance(sources, list):
            for s in sources:
                if isinstance(s, dict):
                    candidates.extend([str(s.get(k)) for k in ("url", "file") if s.get(k)])
                elif isinstance(s, str):
                    candidates.append(s)

        tracks = data.get("tracks", [])
        if isinstance(tracks, list):
            for t in tracks:
                if isinstance(t, dict):
                    candidates.extend([str(t.get(k)) for k in ("url", "file") if t.get(k)])
                elif isinstance(t, str):
                    candidates.append(t)

        for c in candidates:
            ep = find_in_text(c)
            if ep:
                data["episode_id"] = ep
                return ep

        # 3) fallback to IDs like anilistID/malID if nothing else found (less ideal but useful)
        for key in ("anilistID", "anilistId", "malID", "malId"):
            if key in data and data[key]:
                val = str(data[key])
                data["episode_id"] = val
                return val

        return None

    # If BeautifulSoup or HTML string, search the markup/text
    html_text = ""
    if isinstance(data, BeautifulSoup):
        html_text = str(data)
    elif isinstance(data, str):
        html_text = data

    # patterns to try
    patterns = [
        r"[?&]ep=(\d+)",
        r"getSources\?id=(\d+)",
        r'["\']ep["\']\s*[:=]\s*["\']?(\d+)["\']?',
        r'["\']id["\']\s*[:=]\s*["\']?(\d{3,})["\']?',
        r"/(?:ep|episode)/(\d+)"
    ]
    for patt in patterns:
        m = re.search(patt, html_text)
        if m:
            return m.group(1)

    # fallback: any long numeric token
    m = re.search(r"(\d{5,})", html_text)
    if m:
        return m.group(1)

    return None


def sort_subtitle_priority(track: Dict[str, Any]) -> int:
    """
    Sort function to prioritize English subtitles and deprioritize thumbnails.
    Lower return value = higher priority.
    """
    if not isinstance(track, dict):
        return 50

    lang_label = (track.get("lang") or track.get("label") or "").lower()

    # thumbnails last
    if "thumbnail" in lang_label or "thumbnails" in lang_label:
        return 100

    # English first
    if any(k in lang_label for k in ("english", "eng", "en")):
        return 0

    # explicit default
    if track.get("default") is True:
        return 1

    # others
    return 10


def proxy_video_sources(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Patch all file/url links in video data to go through proxy.
    Handles both 'file' and 'url' keys for sources and tracks.
    Also sorts subtitle tracks by priority.
    """
    if not isinstance(data, dict):
        return data

    # Proxy sources (dict or list)
    sources = data.get("sources")
    if isinstance(sources, dict):
        for k in ("file", "url"):
            if sources.get(k):
                sources[k] = encode_proxy(sources[k])
    elif isinstance(sources, list):
        for s in sources:
            if isinstance(s, dict):
                for k in ("file", "url"):
                    if s.get(k):
                        s[k] = encode_proxy(s[k])

# Proxy tracks
    if "tracks" in data and isinstance(data["tracks"], list):
        print(f"[Proxy] Processing {len(data['tracks'])} subtitle tracks")
        for idx, track in enumerate(data["tracks"]):
            if not isinstance(track, dict):
                continue

            original_file = track.get("file")
            original_url = track.get("url")

            # Ensure 'label' field exists for frontend compatibility
            # If track has 'lang' but not 'label', copy lang to label
            if track.get("lang") and not track.get("label"):
                track["label"] = track["lang"]
                print(f"[Proxy] Track {idx}: Added label from lang: {track['label']}")
            
            # Also ensure 'kind' is set for subtitle tracks
            if not track.get("kind"):
                # Check if this is a thumbnail track
                lang_or_label = (track.get("lang") or track.get("label") or "").lower()
                if "thumbnail" in lang_or_label or "thumbnails" in lang_or_label:
                    track["kind"] = "metadata"
                else:
                    track["kind"] = "subtitles"

            for k in ("file", "url"):
                if track.get(k):
                    proxied = encode_proxy(track[k])
                    track[k] = proxied
                    print(f"[Proxy] Track {idx} ({track.get('label', 'unknown')}): {k} proxied")

            if not original_file and not original_url:
                print(f"[Proxy] Warning: Track {idx} has no file or url: {track}")

        # Sort tracks: english first, thumbnails last
        try:
            data["tracks"].sort(key=sort_subtitle_priority)
            print(f"[Proxy] Sorted {len(data['tracks'])} tracks by priority")
            
            # Log final track order
            for idx, track in enumerate(data["tracks"]):
                print(f"[Proxy] Final track {idx}: label={track.get('label')}, kind={track.get('kind')}")
        except Exception as e:
            print(f"[Proxy] Error sorting tracks: {e}")
            pass
    return data
