from typing import Dict, Any, Optional, Union, List
from ...providers.hianime.episodes import HianimeEpisodesService
from .video_utils import extract_episode_id, proxy_video_sources

class HianimeVideoService:
    """Service for fetching video streaming data from Hianime episodes"""

    def __init__(self, client):
        self.client = client
        self.episodes_service = HianimeEpisodesService(self.client)

    async def get_video(
        self,
        ep_id: Union[str, int],
        language: str = "sub",
        server: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get video streaming data for a given episode.

        Flow:
          1. Retrieve available servers
          2. Try requested server (if valid) or iterate available servers until one returns sources
          3. Fetch episode sources for chosen server
          4. Normalize, proxy, and return structured result
        """
        ep_id_str = str(ep_id)
        servers_resp = await self.episodes_service.episode_servers(ep_id_str)
        if not servers_resp:
            return {"error": "no_servers", "message": "No servers found for this episode."}

        # servers_resp format: { "episodeId": "...", "sub":[{serverName...}], "dub":[...], ... }
        available_servers: List[Dict[str, Any]] = servers_resp.get(language, []) or []
        if not available_servers:
            return {"error": "no_servers_for_language", "message": f"No {language} servers found."}

        # Build list of server names to try (requested first if valid)
        server_names = [s.get("serverName") for s in available_servers if s.get("serverName")]
        tried = []

        if server and server in server_names:
            order = [server] + [s for s in server_names if s != server]
        else:
            order = server_names

        sources_data = None
        selected_server = None
        for candidate in order:
            if not candidate:
                continue
            tried.append(candidate)
            selected_server = candidate
            try:
                sources_data = await self.episodes_service.episode_sources(
                    anime_episode_id=ep_id_str,
                    server=selected_server,
                    category=language,
                )
            except Exception as e:
                # log and try next
                print(f"[HianimeVideoService] error fetching sources from {selected_server}: {e}")
                sources_data = None

            # consider it successful if sources_data has non-empty 'sources' (list/dict) or tracks
            if sources_data:
                s = sources_data.get("sources")
                if s:
                    # success
                    break
                # sometimes sources_data may include direct file/url fields; treat non-empty dict as success
                if isinstance(sources_data, dict) and any(k in sources_data for k in ("file", "url", "tracks", "intro", "outro")):
                    break

            # otherwise continue to next server

        if not sources_data:
            return {
                "error": "no_sources",
                "message": "No sources could be fetched from any server.",
                "tried_servers": tried,
            }

        # assemble final result
        result: Dict[str, Any] = {
            "episodeId": ep_id_str,
            "language": language,
            "server": selected_server,
            "sources": sources_data.get("sources", sources_data.get("source") or []),
            "tracks": sources_data.get("tracks", []),
            "intro": sources_data.get("intro"),
            "outro": sources_data.get("outro"),
            "headers": sources_data.get("headers", {}),
            # keep raw payload for debugging if needed
            "_raw": sources_data,
        }
        
        print(f"------------------------------------\n{result}\n------------------------------------")

        # Try to set canonical episode_id (extract from payload or source URLs)
        ep_extracted = extract_episode_id(result) or extract_episode_id(sources_data) or extract_episode_id(servers_resp)
        if ep_extracted:
            result["episode_id"] = ep_extracted

        # Proxy all file/url fields and sort subtitles
        result = proxy_video_sources(result)

        # Choose canonical video_link (first source url/file)
        first_link = None
        s = result.get("sources")
        if isinstance(s, dict):
            first_link = s.get("file") or s.get("url")
        elif isinstance(s, list) and s:
            first = s[0]
            if isinstance(first, dict):
                first_link = first.get("file") or first.get("url")
            elif isinstance(first, str):
                first_link = first

        if first_link:
            result["video_link"] = first_link  # already proxied by proxy_video_sources

        # clean up internal raw if you don't want to send it to client, comment out if needed
        # del result["_raw"]

        # minimal debug log
        print(f"[HianimeVideoService] selected_server={selected_server}, episode_id={result.get('episode_id')}, video_link_present={bool(result.get('video_link'))}")

        return result
