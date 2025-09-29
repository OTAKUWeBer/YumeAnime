"""
Megaplay video source scraper
Fetches video sources and subtitles from megaplay.buzz
"""
from typing import Dict, Any
from bs4 import BeautifulSoup
from curl_cffi import requests

from .video_utils import extract_episode_id, proxy_video_sources


class MegaplayScraper:
    """Scraper for megaplay.buzz video sources"""
    
    BASE_URL = "https://megaplay.buzz"
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": f"{self.BASE_URL}/",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Dest": "empty",
        }
    
    def fetch_video_info(self, megaplay_url: str) -> Dict[str, Any]:
        """
        Fetch the megaplay page, extract episode ID, call getSources,
        and proxy all file URLs
        
        Args:
            megaplay_url: Full megaplay URL for the episode
            
        Returns:
            Dictionary with video sources and subtitle tracks
        """
        # First request to get episode ID
        resp = requests.get(megaplay_url, headers=self.headers)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        ep_id = extract_episode_id(resp.text, soup)
        if not ep_id:
            # Fallback to original naive approach
            try:
                ep_id = soup.title.string.split()[1].strip()
            except Exception:
                raise RuntimeError("Could not determine episode ID from the page")

        # Second request to get sources/subs
        sources_url = f"{self.BASE_URL}/stream/getSources?id={ep_id}"
        ajax_resp = requests.get(
            sources_url, 
            headers={
                "X-Requested-With": "XMLHttpRequest", 
                "Referer": megaplay_url
            }
        )
        ajax_resp.raise_for_status()
        data = ajax_resp.json()

        # Proxy all file links and sort subtitles
        return proxy_video_sources(data)
