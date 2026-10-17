"""Deduplication by normalized URL and perceptual image hashing."""

from __future__ import annotations

import io
import urllib.parse

import imagehash
from PIL import Image

from footage_finder.models import ImageCandidate


def normalize_image_url(url: str) -> str:
    """Normalize URL by stripping anchors and common tracking query parameters."""
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    # Strip tracking parameters
    query_params = urllib.parse.parse_qsl(parsed.query)
    filtered_params = [
        (k, v)
        for k, v in query_params
        if not k.lower().startswith(("utm_", "fbclid", "gclid", "ref"))
    ]
    new_query = urllib.parse.urlencode(filtered_params)
    normalized = urllib.parse.urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            new_query,
            "",  # fragment
        )
    )
    return normalized


class CandidateDeduplicator:
    def __init__(self, phash_distance_threshold: int = 4):
        self.phash_distance_threshold = phash_distance_threshold

    def dedupe_by_url(self, candidates: list[ImageCandidate]) -> list[ImageCandidate]:
        """Deduplicate candidates by normalized image URL."""
        seen_urls: set[str] = set()
        unique: list[ImageCandidate] = []
        for cand in candidates:
            norm_url = normalize_image_url(cand.image_url)
            if norm_url in seen_urls:
                continue
            seen_urls.add(norm_url)
            unique.append(cand)
        return unique

    def compute_image_phash(self, image_bytes: bytes) -> str | None:
        """Compute perceptual hash (pHash) from image bytes."""
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                converted = img.convert("RGB")
                h = imagehash.phash(converted)
                return str(h)
        except (OSError, ValueError, TypeError):
            return None

    def dedupe_by_phash(self, candidates: list[ImageCandidate]) -> list[ImageCandidate]:
        """Filter out perceptual duplicates when perceptual hashes are present."""
        unique: list[ImageCandidate] = []
        existing_hashes: list[imagehash.ImageHash] = []

        for cand in candidates:
            if not cand.perceptual_hash:
                unique.append(cand)
                continue

            try:
                cand_hash = imagehash.hex_to_hash(cand.perceptual_hash)
            except (ValueError, TypeError):
                unique.append(cand)
                continue

            is_duplicate = False
            for prev_h in existing_hashes:
                if (cand_hash - prev_h) <= self.phash_distance_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                existing_hashes.append(cand_hash)
                unique.append(cand)

        return unique
