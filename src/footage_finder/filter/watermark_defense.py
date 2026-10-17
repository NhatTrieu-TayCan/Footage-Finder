"""Watermark Defense: Layer 1 (Domain Blocklist) and Layer 2 (URL Heuristics)."""

from __future__ import annotations

import re
import urllib.parse

from footage_finder.models import ImageCandidate

# Default Layer 2 URL regex patterns indicating stock previews, comps, or watermarks
DEFAULT_URL_WATERMARK_PATTERNS = [
    r"watermark",
    r"wm[_\-\.]",
    r"[/_]comp[/_]",
    r"[/_]previews?[/_]",
    r"preview[_\-\.0-9a-f]{4,}",
    r"stock[-_]photo",
    r"shutter",
    r"getty[-_]preview",
    r"alamy[-_]preview",
    r"thumb[_\-]preview",
]


class WatermarkDefenseFilter:
    def __init__(
        self,
        domain_blocklist: set[str],
        url_patterns: list[str] | None = None,
    ):
        self.domain_blocklist = {d.lower().strip() for d in domain_blocklist}
        self.url_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in (url_patterns or DEFAULT_URL_WATERMARK_PATTERNS)
        ]

    def _domain_matches(self, domain_to_check: str) -> bool:
        dom = domain_to_check.lower().strip()
        if not dom:
            return False
        for blocked in self.domain_blocklist:
            if dom == blocked or dom.endswith("." + blocked):
                return True
        return False

    def is_layer1_domain_blocked(self, candidate: ImageCandidate) -> bool:
        """Check if source domain or image URL hostname matches blocked domains."""
        # 1. Check candidate.source_domain
        if self._domain_matches(candidate.source_domain):
            return True

        # 2. Check image URL netloc
        img_parsed = urllib.parse.urlparse(candidate.image_url)
        if self._domain_matches(img_parsed.netloc):
            return True

        # 3. Check source page URL netloc
        page_parsed = urllib.parse.urlparse(candidate.source_page_url)
        return bool(self._domain_matches(page_parsed.netloc))

    def is_layer2_url_heuristic_blocked(self, candidate: ImageCandidate) -> bool:
        """Check if candidate URLs contain known watermark or stock comp substrings."""
        for pattern in self.url_patterns:
            if pattern.search(candidate.image_url):
                return True
            if pattern.search(candidate.thumbnail_url):
                return True
        return False

    def filter_candidates(
        self, candidates: list[ImageCandidate]
    ) -> tuple[list[ImageCandidate], int, int]:
        """Apply Layer 1 and Layer 2 filters.

        Returns: (passed_candidates, dropped_layer1_count, dropped_layer2_count)
        """
        passed: list[ImageCandidate] = []
        dropped_layer1 = 0
        dropped_layer2 = 0

        for cand in candidates:
            if self.is_layer1_domain_blocked(cand):
                dropped_layer1 += 1
                continue
            if self.is_layer2_url_heuristic_blocked(cand):
                dropped_layer2 += 1
                continue
            passed.append(cand)

        return passed, dropped_layer1, dropped_layer2
