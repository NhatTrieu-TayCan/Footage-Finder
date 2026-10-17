"""Search manager with rate limiting, retries, caching, and thumbnail downloading."""

from __future__ import annotations

import asyncio
import io
from pathlib import Path

import httpx
from PIL import Image

from footage_finder.cache import DiskCache, compute_cache_key
from footage_finder.config import Settings, load_domain_blocklist
from footage_finder.filter.aspect_filter import filter_by_min_width
from footage_finder.filter.dedupe import CandidateDeduplicator
from footage_finder.filter.watermark_defense import WatermarkDefenseFilter
from footage_finder.models import ImageCandidate, ImageType, VideoLead
from footage_finder.search.serper import SerperProvider
from footage_finder.search.wikimedia import WikimediaProvider
from footage_finder.search.youtube import YouTubeProvider
from footage_finder.tracker import CostTracker


class SearchManager:
    def __init__(
        self,
        settings: Settings,
        cache: DiskCache | None = None,
        tracker: CostTracker | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.settings = settings
        self.cache = cache or DiskCache()
        self.tracker = tracker or CostTracker()
        self.client = http_client

        # Providers
        self.serper = (
            SerperProvider(settings.serper_api_key, client=self.client)
            if settings.serper_api_key
            else None
        )
        self.wikimedia = WikimediaProvider(
            settings.wikimedia_user_agent, client=self.client
        )
        self.youtube = (
            YouTubeProvider(settings.youtube_api_key, client=self.client)
            if settings.youtube_api_key
            else None
        )

        # Filters
        blocklist = load_domain_blocklist(settings.blocklist_file)
        self.watermark_defense = WatermarkDefenseFilter(domain_blocklist=blocklist)
        self.deduplicator = CandidateDeduplicator(phash_distance_threshold=4)
        self.search_sem = asyncio.Semaphore(settings.concurrent_search_limit)
        self.download_sem = asyncio.Semaphore(settings.concurrent_download_limit)

    async def _fetch_with_retry(
        self, provider_func, query: str, limit: int
    ) -> list[ImageCandidate]:
        """Fetch search results with exponential backoff on 429/5xx errors."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with self.search_sem:
                    return await provider_func(query=query, limit=limit)
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                    await asyncio.sleep(1.5 * (2**attempt))
                    continue
                raise
            except httpx.RequestError:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.5 * (2**attempt))
                    continue
                return []
        return []

    async def search_query(self, query: str, limit: int = 15) -> list[ImageCandidate]:
        """Search query across providers with disk caching."""
        cache_key = compute_cache_key("search_query", "v1.0", f"{query}::{limit}")
        ttl_seconds = self.settings.search_cache_ttl_hours * 3600

        cached_data = self.cache.get_json(
            "search", cache_key, max_age_seconds=ttl_seconds
        )
        if cached_data is not None:
            return [ImageCandidate(**item) for item in cached_data]

        tasks = []
        if self.serper:
            tasks.append(self._fetch_with_retry(self.serper.search, query, limit))
            self.tracker.record_search_query(self.serper.name)

        tasks.append(self._fetch_with_retry(self.wikimedia.search, query, limit))
        self.tracker.record_search_query(self.wikimedia.name)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        combined: list[ImageCandidate] = []
        for res in results:
            if isinstance(res, list):
                combined.extend(res)

        # Cache raw search candidates
        self.cache.set_json(
            "search",
            cache_key,
            [c.model_dump(mode="json") for c in combined],
        )
        return combined

    async def search_youtube_leads(
        self, query: str, segment_id: str, limit: int = 3
    ) -> list[VideoLead]:
        """Search YouTube for video leads (if enabled)."""
        if not self.youtube:
            return []

        cache_key = compute_cache_key("youtube", "v1.0", f"{query}::{segment_id}")
        cached_data = self.cache.get_json("youtube", cache_key, max_age_seconds=86400)
        if cached_data is not None:
            return [VideoLead(**item) for item in cached_data]

        try:
            leads = await self.youtube.search(
                query=query, segment_id=segment_id, limit=limit
            )
            self.tracker.record_search_query("youtube")
            self.cache.set_json(
                "youtube", cache_key, [l.model_dump(mode="json") for l in leads]
            )
            return leads
        except (httpx.HTTPError, OSError, ValueError, KeyError):
            return []

    async def download_thumbnail(
        self, candidate: ImageCandidate, thumbs_dir: Path
    ) -> bool:
        """Download thumbnail, compute pHash, and store locally.

        Returns True on success, False if download failed (drops broken URLs).
        """
        thumbs_dir.mkdir(parents=True, exist_ok=True)
        local_thumb_path = thumbs_dir / f"{candidate.candidate_id}.jpg"

        # Check existing cache
        if local_thumb_path.exists() and local_thumb_path.stat().st_size > 0:
            candidate.local_thumbnail_path = str(local_thumb_path)
            if not candidate.perceptual_hash:
                try:
                    data = local_thumb_path.read_bytes()
                    candidate.perceptual_hash = self.deduplicator.compute_image_phash(
                        data
                    )
                except OSError:
                    pass
            return True

        # Fetch thumbnail
        headers = {"User-Agent": self.settings.wikimedia_user_agent}
        target_url = candidate.thumbnail_url or candidate.image_url

        try:
            async with self.download_sem:
                client = self.client or httpx.AsyncClient(
                    timeout=self.settings.request_timeout_seconds,
                    follow_redirects=True,
                )
                try:
                    resp = await client.get(target_url, headers=headers)
                    candidate.http_status = resp.status_code
                    if resp.status_code != 200:
                        return False
                    data = resp.content
                finally:
                    if not self.client:
                        await client.aclose()

            # Validate and resize to thumbnail
            with Image.open(io.BytesIO(data)) as img:
                img_rgb = img.convert("RGB")
                img_rgb.thumbnail((480, 270))
                img_rgb.save(local_thumb_path, "JPEG", quality=85)

            candidate.local_thumbnail_path = str(local_thumb_path)
            candidate.perceptual_hash = self.deduplicator.compute_image_phash(data)
            return True
        except (httpx.HTTPError, OSError, ValueError):
            return False

    async def gather_and_filter_candidates(
        self,
        queries: list[str],
        image_types: list[ImageType],
        thumbs_dir: Path,
        max_candidates: int = 15,
    ) -> tuple[list[ImageCandidate], int, int, int]:
        """Collect candidates across all queries, apply Watermark Layers 1 & 2,

        drop broken thumbnails, dedupe by URL & pHash, and enforce minimum width.
        Returns: (filtered_candidates, dropped_layer1, dropped_layer2, dropped_phash)
        """
        all_candidates: list[ImageCandidate] = []
        for q in queries:
            cands = await self.search_query(q, limit=max_candidates)
            all_candidates.extend(cands)

        # 1. URL Deduplication
        deduped = self.deduplicator.dedupe_by_url(all_candidates)

        # 2. Watermark Defense: Layer 1 (Domain Blocklist) & Layer 2 (URL Heuristics)
        clean_cands, dropped_l1, dropped_l2 = self.watermark_defense.filter_candidates(
            deduped
        )
        self.tracker.record_watermark_removal(layer=1, count=dropped_l1)
        self.tracker.record_watermark_removal(layer=2, count=dropped_l2)

        # 3. Minimum width filter (when width is known)
        width_filtered, _ = filter_by_min_width(
            clean_cands,
            image_types,
            min_width_general=self.settings.min_width_general,
            min_width_archival=self.settings.min_width_archival,
        )

        # 4. Download thumbnails concurrently & drop broken URLs
        download_tasks = [
            self.download_thumbnail(c, thumbs_dir) for c in width_filtered
        ]
        results = await asyncio.gather(*download_tasks)
        valid_candidates = [c for c, ok in zip(width_filtered, results) if ok]

        # 5. Deduplication by perceptual hash (pHash)
        phash_filtered = self.deduplicator.dedupe_by_phash(valid_candidates)
        dropped_phash = len(valid_candidates) - len(phash_filtered)

        return phash_filtered[:max_candidates], dropped_l1, dropped_l2, dropped_phash
