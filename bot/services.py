from __future__ import annotations

import httpx


async def fetch_lyrics(song: str, genius_token: str | None) -> str:
    if not genius_token:
        return "GENIUS_API_TOKEN is not configured. Add it to `.env` to use /lyrics."

    headers = {"Authorization": f"Bearer {genius_token}"}
    async with httpx.AsyncClient(timeout=15) as client:
        search_resp = await client.get(
            "https://api.genius.com/search",
            params={"q": song},
            headers=headers,
        )
        search_resp.raise_for_status()
        data = search_resp.json()
        hits = data.get("response", {}).get("hits", [])
        if not hits:
            return "No lyrics result found."

        first = hits[0].get("result", {})
        title = first.get("full_title", "Unknown")
        url = first.get("url", "")
        return f"Top match: {title}\n{url}"
