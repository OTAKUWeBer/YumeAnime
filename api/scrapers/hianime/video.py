#!/usr/bin/env python3
"""Minimal cleaned version of your megaplay scraper (keeps curl_cffi.requests)."""

import base64
import json
import re
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup
from curl_cffi import requests


def encode_proxy(url: str) -> str:
    """Return proxied URL through Vercel http-proxy-zai (base64-encoded)."""
    encoded = base64.b64encode(url.encode()).decode()
    return f"https://http-proxy-zai.vercel.app/proxy/{encoded}"


def extract_episode_id(html: str, soup: BeautifulSoup) -> Optional[str]:
    """Try a few ways to extract a numeric episode id from the page."""
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


def megaplay_infos(megaplay_url: str) -> Dict[str, Any]:
    """
    Fetch the megaplay page, extract the episode ID, call getSources,
    and proxy any 'file' URLs in sources/tracks via encode_proxy.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://megaplay.buzz/",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Dest": "empty",
    }

    # first request to get ID
    resp = requests.get(megaplay_url, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    ep_id = extract_episode_id(resp.text, soup)
    if not ep_id:
        # fallback to original naive approach (if present), but raise if still missing
        try:
            ep_id = soup.title.string.split()[1].strip()
        except Exception:
            raise RuntimeError("Could not determine episode ID from the page")

    # second request to get sources/subs
    url = f"https://megaplay.buzz/stream/getSources?id={ep_id}"
    ajax_resp = requests.get(url, headers={"X-Requested-With": "XMLHttpRequest", "Referer": megaplay_url})
    ajax_resp.raise_for_status()
    data = ajax_resp.json()

    # patch all file links to go through proxy
    if isinstance(data, dict):
        sources = data.get("sources")
        if isinstance(sources, dict) and "file" in sources:
            sources["file"] = encode_proxy(sources["file"])
        elif isinstance(sources, list):
            for s in sources:
                if isinstance(s, dict) and s.get("file"):
                    s["file"] = encode_proxy(s["file"])

        if "tracks" in data and isinstance(data["tracks"], list):
            for track in data["tracks"]:
                if isinstance(track, dict) and "file" in track:
                    track["file"] = encode_proxy(track["file"])
            
            def sort_subtitle_priority(track):
                """Sort function to prioritize English subtitles"""
                if not isinstance(track, dict):
                    return 2
                
                # Check language field
                lang = track.get("lang", "").lower()
                if lang == "en" or lang == "eng" or lang == "english":
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
            
            # Sort tracks with English first
            data["tracks"].sort(key=sort_subtitle_priority)

    return data


def get_and_play_m3u8_and_vtt(ep_id: str, language: str = "sub") -> Dict[str, Any]:
    """Build megaplay URL and return proxied m3u8 + vtt info (synchronous)."""
    language = language.lower()
    if language not in ("sub", "dub"):
        raise ValueError("language must be 'sub' or 'dub'")

    megaplay_url = f"https://megaplay.buzz/stream/s-2/{ep_id}/{language}"
    result = megaplay_infos(megaplay_url)
    return result


def main():
    # Example usage — change ep_id / language as needed
    ep_id = "94597"  # Example episode ID
    language = "sub"  # or "dub"
    result = get_and_play_m3u8_and_vtt(ep_id, language)
    # (result already printed; return for possible further use)
    return result


if __name__ == "__main__":
    main()
