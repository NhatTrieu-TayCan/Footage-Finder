"""HTML Report Generator using Jinja2 with embedded styles."""

from __future__ import annotations

import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from footage_finder.models import SegmentReport
from footage_finder.tracker import CostTracker


def relative_path_filter(target_path_str: str | None, base_dir: Path) -> str:
    """Jinja filter: compute relative path from output directory to target file."""
    if not target_path_str:
        return ""
    try:
        target = Path(target_path_str)
        return str(target.relative_to(base_dir))
    except ValueError:
        # If not relative, return basename prefixed by thumbs/
        return f"thumbs/{Path(target_path_str).name}"


def generate_html_report(
    reports: list[SegmentReport],
    output_html_path: Path,
    script_name: str = "Script",
    tracker: CostTracker | None = None,
) -> Path:
    """Generate self-contained interactive HTML report."""
    output_html_path.parent.mkdir(parents=True, exist_ok=True)
    template_dir = Path(__file__).parent.parent / "templates"

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=True,
    )
    env.filters["relative_path"] = relative_path_filter

    template = env.get_template("report.html.jinja")

    # Aggregate stats
    stats_summary = tracker.get_summary() if tracker else None
    total_candidates = sum(rep.total_candidates_searched for rep in reports)
    total_wm = (
        (stats_summary.watermark_removed_layer1 + stats_summary.watermark_removed_layer2 + stats_summary.watermark_removed_layer3)
        if stats_summary
        else 0
    )
    cost = stats_summary.estimated_cost_usd if stats_summary else 0.0

    rendered = template.render(
        script_name=script_name,
        timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        reports=reports,
        stats={
            "total_segments": len(reports),
            "total_candidates": total_candidates,
            "total_watermark_removed": total_wm,
            "estimated_cost_usd": cost,
        },
        output_dir=output_html_path.parent,
    )

    output_html_path.write_text(rendered, encoding="utf-8")
    return output_html_path
