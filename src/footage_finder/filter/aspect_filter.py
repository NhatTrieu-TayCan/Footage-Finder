"""Aspect ratio scoring and minimum width filtering."""

from __future__ import annotations

from footage_finder.models import ImageCandidate, ImageType


def is_archival_context(image_types: list[ImageType]) -> bool:
    """Check if the segment targets archival photos or historical maps."""
    return any(
        t in [ImageType.ARCHIVAL_PHOTO, ImageType.HISTORICAL_MAP] for t in image_types
    )


def filter_by_min_width(
    candidates: list[ImageCandidate],
    image_types: list[ImageType],
    min_width_general: int = 1280,
    min_width_archival: int = 600,
) -> tuple[list[ImageCandidate], int]:
    """Drop images that fall below the minimum width threshold when dimensions are known.

    Images with unknown width (None) are retained.
    """
    threshold = (
        min_width_archival if is_archival_context(image_types) else min_width_general
    )
    passed: list[ImageCandidate] = []
    dropped_count = 0

    for cand in candidates:
        if cand.width is not None and cand.width < threshold:
            dropped_count += 1
            continue
        passed.append(cand)

    return passed, dropped_count


def calculate_aspect_modifier(aspect_ratio: float | None) -> float:
    """Calculate relevance score modifier based on aspect ratio.

    Landscape images (~16:9, ~1.78) get a small boost.
    Portrait/vertical images (<1.0) are penalized, NOT dropped.
    """
    if aspect_ratio is None:
        return 0.0

    # Strong 16:9 landscape match (1.5 to 1.9)
    if 1.5 <= aspect_ratio <= 1.9:
        return 0.5
    # Standard landscape (1.2 to 2.2)
    elif 1.2 <= aspect_ratio <= 2.2:
        return 0.2
    # Square (0.9 to 1.1)
    elif 0.9 <= aspect_ratio <= 1.1:
        return -0.2
    # Portrait / vertical (< 0.9)
    elif aspect_ratio < 0.9:
        return -1.5
    # Extreme panoramic (> 2.3)
    else:
        return -0.5
