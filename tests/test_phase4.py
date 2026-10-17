"""Unit tests for Phase 4: report HTML/CSV generation, round-trip, and downloader."""

from pathlib import Path

import pytest
import respx

from footage_finder.models import (
    EvaluatedImage,
    ImageCandidate,
    ImageType,
    LicenseType,
    Segment,
    SegmentIntent,
    SegmentReport,
    SegmentStatus,
)
from footage_finder.report.csv_generator import export_reports_to_csv, read_selected_csv
from footage_finder.report.downloader import AssetDownloader
from footage_finder.report.html_generator import generate_html_report
from footage_finder.tracker import CostTracker


def build_sample_report() -> SegmentReport:
    seg = Segment(id="S001", index=1, text="The Trinity test detonated the first atomic bomb.")
    intent = SegmentIntent(
        segment_id="S001",
        visual_intent="Archival explosion",
        entities=["Trinity test", "1945"],
        image_types=[ImageType.ARCHIVAL_PHOTO],
        queries=["Trinity test 1945"],
    )
    cand = ImageCandidate(
        candidate_id="trinity_1",
        query="Trinity test 1945",
        provider="wikimedia",
        image_url="https://upload.wikimedia.org/trinity_test.jpg",
        thumbnail_url="https://thumb.wikimedia.org/trinity_thumb.jpg",
        source_page_url="https://commons.wikimedia.org/wiki/File:Trinity_test.jpg",
        source_domain="commons.wikimedia.org",
        title="Trinity Test Explosion",
        width=1920,
        height=1080,
        aspect_ratio=1.78,
        license=LicenseType.PUBLIC_DOMAIN,
        license_name="Public Domain",
        author="U.S. Department of Energy",
        attribution_required=False,
        attribution_text='"Trinity Test Explosion" via Wikimedia Commons (Public Domain): https://commons.wikimedia.org/wiki/File:Trinity_test.jpg',
    )
    eval_img = EvaluatedImage(
        candidate=cand,
        relevance_score=9.4,
        matches=["Trinity test", "1945"],
        concerns=[],
        reason="Authentic historical archival explosion photograph",
        rank=1,
    )
    return SegmentReport(
        segment=seg,
        intent=intent,
        top_picks=[eval_img],
        alternates=[],
        total_candidates_searched=10,
        status=SegmentStatus.OK,
    )


def test_html_and_csv_report_generation(tmp_path: Path):
    report = build_sample_report()
    tracker = CostTracker()
    tracker.record_search_query("wikimedia", count=1)

    html_file = tmp_path / "report.html"
    csv_file = tmp_path / "report.csv"

    # Test HTML generation
    generate_html_report(
        reports=[report],
        output_html_path=html_file,
        script_name="Trinity_Script",
        tracker=tracker,
    )
    assert html_file.exists()
    html_content = html_file.read_text(encoding="utf-8")
    assert "Footage Finder Report" in html_content
    assert "S001" in html_content
    assert "Export Selected (CSV)" in html_content
    assert "commons.wikimedia.org" in html_content

    # Test CSV generation
    export_reports_to_csv([report], csv_file)
    assert csv_file.exists()
    rows = read_selected_csv(csv_file)
    assert len(rows) == 1
    assert rows[0]["segment_id"] == "S001"
    assert rows[0]["rank"] == "1"
    assert rows[0]["image_url"] == "https://upload.wikimedia.org/trinity_test.jpg"
    assert rows[0]["score"] == "9.4"


@pytest.mark.asyncio
@respx.mock
async def test_asset_downloader_with_sidecars(tmp_path: Path):
    dest_dir = tmp_path / "downloads"
    test_csv = tmp_path / "selected.csv"

    report = build_sample_report()
    export_reports_to_csv([report], test_csv)

    # Mock image response
    respx.get("https://upload.wikimedia.org/trinity_test.jpg").respond(
        content=b"FAKE_JPEG_IMAGE_CONTENT_BYTES",
        headers={"Content-Type": "image/jpeg"},
    )

    downloader = AssetDownloader(download_dir=dest_dir)
    out_dir = await downloader.download_from_csv(test_csv)

    assert out_dir.exists()
    seg_folder = out_dir / "S001"
    assert seg_folder.exists()

    # Image file check: S001_01_commons_wikimedia_org.jpg
    expected_img = seg_folder / "S001_01_commons_wikimedia_org.jpg"
    assert expected_img.exists()
    assert expected_img.read_bytes() == b"FAKE_JPEG_IMAGE_CONTENT_BYTES"

    # Sidecar check: S001_01_commons_wikimedia_org.credit.txt
    expected_sidecar = seg_folder / "S001_01_commons_wikimedia_org.credit.txt"
    assert expected_sidecar.exists()
    sidecar_text = expected_sidecar.read_text(encoding="utf-8")
    assert "Segment: S001" in sidecar_text
    assert "U.S. Department of Energy" in sidecar_text
    assert "Public Domain" in sidecar_text

    # Consolidated credits.txt check
    master_credits = out_dir / "credits.txt"
    assert master_credits.exists()
    assert "[S001]" in master_credits.read_text(encoding="utf-8")
