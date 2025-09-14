import httpx

async def get_megaplay_embed(ep_id, language="sub", fetch_url=False):
    lang = language.lower()
    if lang not in ("sub","dub"):
        raise ValueError("language must be 'sub' or 'dub'")

    base = "https://megaplay.buzz/stream/s-2"
    embed_url = f"{base}/{ep_id}/{lang}"
    result = {"embed_url": embed_url}

    if fetch_url:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://hianime.to/"
        }
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            resp = await client.get(embed_url, headers=headers)

            # detect unwanted redirects
            final_url = str(resp.url)
            if not final_url.startswith("https://megaplay.buzz"):
                result.update({
                    "status_code": resp.status_code,
                    "redirected_to": final_url,
                    "is_ad": True
                })
                return result

            result.update({
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "content": resp.text,
                "is_ad": False
            })

    return result["embed_url"] if not fetch_url else result
