"""JSON Report Exporter for Web UI and REST API."""

from __future__ import annotations

import json
from pathlib import Path

from footage_finder.models import SegmentReport, UsageStats


def export_reports_to_json(
    reports: list[SegmentReport],
    output_json_path: Path,
    stats: UsageStats | None = None,
    script_name: str = "Script",
) -> Path:
    """Export segment reports and run stats to JSON format."""
    output_json_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "script_name": script_name,
        "total_segments": len(reports),
        "stats": stats.model_dump() if stats else None,
        "segments": [rep.model_dump() for rep in reports],
    }

    output_json_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return output_json_path
