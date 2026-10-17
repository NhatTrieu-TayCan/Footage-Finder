"""CSV Report Exporter and Downloader round-trip handler."""

from __future__ import annotations

import csv
from pathlib import Path

from footage_finder.models import SegmentReport

CSV_HEADERS = [
    "segment_id",
    "script_text",
    "rank",
    "image_url",
    "source_page_url",
    "source_domain",
    "width",
    "height",
    "score",
    "reason",
    "license",
    "author",
    "concerns",
    "attribution_text",
]


def export_reports_to_csv(reports: list[SegmentReport], output_csv_path: Path) -> Path:
    """Export segment reports (top picks and alternates) to CSV."""
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)

        for rep in reports:
            seg = rep.segment
            # Write top picks first, then alternates
            all_evals = rep.top_picks + rep.alternates
            for item in all_evals:
                cand = item.candidate
                writer.writerow(
                    [
                        seg.id,
                        seg.text.replace("\n", " "),
                        item.rank,
                        cand.image_url,
                        cand.source_page_url,
                        cand.source_domain,
                        cand.width or "",
                        cand.height or "",
                        f"{item.relevance_score:.1f}",
                        item.reason,
                        cand.license.value if hasattr(cand.license, "value") else str(cand.license),
                        cand.author or "",
                        "; ".join(item.concerns),
                        cand.attribution_text or "",
                    ]
                )

    return output_csv_path


def read_selected_csv(csv_path: Path) -> list[dict]:
    """Read a report CSV file (or user-edited selected CSV) into a list of row dicts."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    rows: list[dict] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("image_url"):
                rows.append(row)
    return rows
