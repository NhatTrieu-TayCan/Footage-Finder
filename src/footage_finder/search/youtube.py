"""YouTube Data API v3 search provider for video leads."""

from __future__ import annotations

import html

import httpx

from footage_finder.models import VideoLead


class YouTubeProvider:
    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None):
        self.api_key = api_key
        self.client = client
        self.endpoint = "https://www.googleapis.com/youtube/v3/search"

    @property
    def name(self) -> str:
        return "youtube"

    async def search(
        self, query: str, segment_id: str, limit: int = 5
    ) -> list[VideoLead]:
        if not self.api_key:
            return []

        params = {
            "part": "snippet",
            "type": "video",
            "q": query,
            "maxResults": limit,
            "key": self.api_key,
        }

        async def _make_request(cli: httpx.AsyncClient) -> list[VideoLead]:
            response = await cli.get(self.endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            leads: list[VideoLead] = []

            for item in data.get("items", []):
                vid_id = item.get("id", {}).get("videoId")
                if not vid_id:
                    continue

                snippet = item.get("snippet", {})
                title = html.unescape(snippet.get("title", ""))
                channel = html.unescape(snippet.get("channelTitle", ""))
                thumb = (
                    snippet.get("thumbnails", {}).get("medium", {}).get("url")
                    or snippet.get("thumbnails", {}).get("default", {}).get("url")
                    or ""
                )

                leads.append(
                    VideoLead(
                        lead_id=vid_id,
                        segment_id=segment_id,
                        title=title,
                        video_url=f"https://www.youtube.com/watch?v={vid_id}",
                        channel_title=channel,
                        thumbnail_url=thumb,
                        published_at=snippet.get("publishedAt"),
                        license_note="copyrighted – verify before use",
                    )
                )
            return leads

        if self.client:
            return await _make_request(self.client)
        else:
            async with httpx.AsyncClient(timeout=15.0) as cli:
                return await _make_request(cli)
