"""Image filters and watermark defense package."""

from footage_finder.filter.aspect_filter import (
    calculate_aspect_modifier,
    filter_by_min_width,
    is_archival_context,
)
from footage_finder.filter.dedupe import CandidateDeduplicator, normalize_image_url
from footage_finder.filter.watermark_defense import WatermarkDefenseFilter

__all__ = [
    "CandidateDeduplicator",
    "WatermarkDefenseFilter",
    "calculate_aspect_modifier",
    "filter_by_min_width",
    "is_archival_context",
    "normalize_image_url",
]
