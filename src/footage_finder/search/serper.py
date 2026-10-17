"""Serper.dev Google Images search provider."""

from __future__ import annotations

import hashlib
import urllib.parse

import httpx

from footage_finder.models import ImageCandidate, LicenseType
from footage_finder.search.base import BaseSearchProvider


class SerperProvider(BaseSearchProvider):
    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None):
        self.api_key = api_key
        self.client = client
        self.endpoint = "https://google.serper.dev/images"

    @property
    def name(self) -> str:
        return "serper"

    async def search(self, query: str, limit: int = 15) -> list[ImageCandidate]:
        if not self.api_key:
            return []

        payload = {
            "q": query,
            "num": limit,
            "gl": "us",
            "hl": "en",
        }
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

        async def _make_request(cli: httpx.AsyncClient) -> list[ImageCandidate]:
            response = await cli.post(self.endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            candidates: list[ImageCandidate] = []

            for item in data.get("images", []):
                img_url = item.get("imageUrl")
                if not img_url:
                    continue

                thumb_url = item.get("thumbnailUrl") or img_url
                link = item.get("link") or ""
                domain = item.get("domain") or ""
                if not domain and link:
                    domain = urllib.parse.urlparse(link).netloc

                width = item.get("imageWidth")
                height = item.get("imageHeight")
                aspect = (
                    (round(width / height, 2))
                    if width and height and height > 0
                    else None
                )

                cand_id = hashlib.sha256(img_url.encode("utf-8")).hexdigest()[:16]

                candidates.append(
                    ImageCandidate(
                        candidate_id=cand_id,
                        query=query,
                        provider=self.name,
                        image_url=img_url,
                        thumbnail_url=thumb_url,
                        source_page_url=link,
                        source_domain=domain.lower(),
                        title=item.get("title"),
                        width=width,
                        height=height,
                        aspect_ratio=aspect,
                        license=LicenseType.UNKNOWN,
                        license_name=None,
                        author=None,
                        attribution_required=False,
                        attribution_text="",
                    )
                )
            return candidates

        if self.client:
            return await _make_request(self.client)
        else:
            async with httpx.AsyncClient(timeout=15.0) as cli:
                return await _make_request(cli)
