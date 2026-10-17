"""Wikimedia Commons API search provider."""

from __future__ import annotations

import hashlib
import html
import re

import httpx

from footage_finder.models import ImageCandidate, LicenseType
from footage_finder.search.base import BaseSearchProvider


def clean_html(raw_html: str | None) -> str:
    """Remove HTML tags and decode HTML entities."""
    if not raw_html:
        return ""
    clean = re.sub(r"<[^<]+?>", "", raw_html)
    return html.unescape(clean).strip()


class WikimediaProvider(BaseSearchProvider):
    def __init__(self, user_agent: str, client: httpx.AsyncClient | None = None):
        self.user_agent = user_agent
        self.client = client
        self.endpoint = "https://commons.wikimedia.org/w/api.php"

    @property
    def name(self) -> str:
        return "wikimedia"

    async def search(self, query: str, limit: int = 15) -> list[ImageCandidate]:
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,  # File namespace
            "gsrlimit": limit,
            "prop": "imageinfo",
            "iiprop": "url|size|extmetadata|mime",
            "iiurlwidth": 400,
            "format": "json",
        }
        headers = {
            "User-Agent": self.user_agent,
        }

        async def _make_request(cli: httpx.AsyncClient) -> list[ImageCandidate]:
            response = await cli.get(self.endpoint, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            pages = data.get("query", {}).get("pages", {})
            candidates: list[ImageCandidate] = []

            for page in pages.values():
                imageinfo_list = page.get("imageinfo", [])
                if not imageinfo_list:
                    continue

                info = imageinfo_list[0]
                mime = info.get("mime", "")
                # Only accept image formats
                if not mime.startswith("image/"):
                    continue

                img_url = info.get("url")
                if not img_url:
                    continue

                thumb_url = info.get("thumburl") or img_url
                desc_url = (
                    info.get("descriptionurl")
                    or f"https://commons.wikimedia.org/wiki/{page.get('title', '')}"
                )
                title = clean_html(page.get("title", "").replace("File:", ""))

                width = info.get("width")
                height = info.get("height")
                aspect = (
                    (round(width / height, 2))
                    if width and height and height > 0
                    else None
                )

                extmeta = info.get("extmetadata", {})
                raw_lic = extmeta.get("LicenseShortName", {}).get("value", "")
                raw_usage = extmeta.get("UsageTerms", {}).get("value", "")
                raw_artist = extmeta.get("Artist", {}).get("value", "")
                artist = clean_html(raw_artist) or "Unknown / Uncredited"
                lic_name = clean_html(raw_lic) or clean_html(raw_usage) or "Unknown"

                # Classify license
                lowered_lic = (raw_lic + " " + raw_usage).lower()
                if any(
                    x in lowered_lic for x in ["public domain", "pd-", "cc-zero", "cc0"]
                ):
                    license_type = LicenseType.PUBLIC_DOMAIN
                    attribution_required = False
                elif "cc" in lowered_lic or "creative commons" in lowered_lic:
                    license_type = LicenseType.CREATIVE_COMMONS
                    attribution_required = True
                else:
                    license_type = LicenseType.UNKNOWN
                    attribution_required = True

                cand_id = hashlib.sha256(img_url.encode("utf-8")).hexdigest()[:16]

                # Compose clean YouTube ready attribution
                if license_type == LicenseType.PUBLIC_DOMAIN:
                    attr_text = (
                        f'"{title}" via Wikimedia Commons (Public Domain): {desc_url}'
                    )
                else:
                    attr_text = f'"{title}" by {artist} ({lic_name}) via Wikimedia Commons: {desc_url}'

                candidates.append(
                    ImageCandidate(
                        candidate_id=cand_id,
                        query=query,
                        provider=self.name,
                        image_url=img_url,
                        thumbnail_url=thumb_url,
                        source_page_url=desc_url,
                        source_domain="commons.wikimedia.org",
                        title=title,
                        width=width,
                        height=height,
                        aspect_ratio=aspect,
                        license=license_type,
                        license_name=lic_name,
                        author=artist,
                        attribution_required=attribution_required,
                        attribution_text=attr_text,
                    )
                )
            return candidates

        if self.client:
            return await _make_request(self.client)
        else:
            async with httpx.AsyncClient(timeout=15.0) as cli:
                return await _make_request(cli)
