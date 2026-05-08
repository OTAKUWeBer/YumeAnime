"""
Video scraper utility functions
Handles URL encoding, episode ID extraction, subtitle sorting, and proxying.
"""
import re
from typing import Optional, List, Dict, Any, Union
import os
import json
from urllib.parse import quote
import dotenv
from bs4 import BeautifulSoup

dotenv.load_dotenv()
proxy_url = os.getenv("PROXY_URL", "https://cdn-eu.1ani.me/proxy/m3u8")
kiwi_proxy_url = os.getenv("KIWI_PROXY_URL", "https://")

# Enforce HTTPS on proxy URLs to prevent mixed content blocking
if proxy_url and proxy_url.startswith("http://"):
    proxy_url = proxy_url.replace("http://", "https://", 1)
if kiwi_proxy_url and kiwi_proxy_url.startswith("http://"):
    kiwi_proxy_url = kiwi_proxy_url.replace("http://", "https://", 1)


def encode_kiwi_proxy(url: Optional[str], referer: str = "https://kwik.cx/") -> Optional[str]:
    """
    Return proxied URL through the dedicated Kiwi worker.
    The worker handles all headers (referer, origin, UA) internally.
    """
    if not url:
        return url
    try:
        # Guard: if caller accidentally passes a dict, ignore it
        # (Worker only needs the raw vault URL)
        encoded_url = quote(url, safe='')
        return f"{kiwi_proxy_url}/?url={encoded_url}"
    except Exception:
        return url


def encode_proxy(url: Optional[str], headers: Optional[Dict[str, str]] = None) -> Optional[str]:
    """
    Return proxied URL through proxy using query parameters format.
    Format: {proxy_url}?url={url_encoded}&headers={headers_encoded}
    """
    if not url:
        return url
    try:
        # URL-encode the target URL
        encoded_url = quote(url, safe='')

        # Build query parameters
        query_params = f"?url={encoded_url}"

        # Add headers if provided
        if headers:
            headers_json = json.dumps(headers)
            encoded_headers = quote(headers_json, safe='')
            query_params += f"&headers={encoded_headers}"

        result = f'{proxy_url}{query_params}'
        if result.startswith("http://"):
            result = result.replace("http://", "https://", 1)
        return result
    except Exception:
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

        # 3) fallback to IDs like anilistID/malID if nothing else found
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


def _is_already_proxied(url: str) -> bool:
    """True if the URL already routes through one of our proxies."""
    if not url:
        return False
    return proxy_url in url or kiwi_proxy_url in url


def proxy_video_sources(data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, provider: Optional[str] = None) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return data

    if headers is None:
        headers = {"referer": "https://kwik.cx/"}

    def _pick_proxy(url: str, for_subtitles: bool = False) -> str:
        """Route through the correct proxy. Subtitles always use cdn-eu.1ani."""
        if not url or _is_already_proxied(url):
            return url
        if provider == "kiwi" and not for_subtitles:
            referer = headers.get("referer", "https://kwik.cx/")
            return encode_kiwi_proxy(url, referer) or url
        return encode_proxy(url, headers) or url

    # Proxy sources
    sources = data.get("sources")
    if isinstance(sources, dict):
        for k in ("file", "url"):
            if sources.get(k):
                sources[k] = _pick_proxy(sources[k])
    elif isinstance(sources, list):
        for s in sources:
            if isinstance(s, dict):
                for k in ("file", "url"):
                    if s.get(k):
                        s[k] = _pick_proxy(s[k])

    # Proxy tracks — subtitles always via cdn-eu.1ani, never kiwi worker
    if "tracks" in data and isinstance(data["tracks"], list):
        for idx, track in enumerate(data["tracks"]):
            if not isinstance(track, dict):
                continue
            if track.get("lang") and not track.get("label"):
                track["label"] = track["lang"]
            if not track.get("kind"):
                lang_or_label = (track.get("lang") or track.get("label") or "").lower()
                track["kind"] = "metadata" if "thumbnail" in lang_or_label else "subtitles"
            for k in ("file", "url"):
                if track.get(k):
                    track[k] = _pick_proxy(track[k], for_subtitles=True)

        try:
            data["tracks"].sort(key=sort_subtitle_priority)
        except Exception:
            pass

    return data
