"""Unit tests for Phase 3: intent generation, vision reranking, and Layer 3 watermark defense."""

from pathlib import Path
from unittest.mock import patch

import pytest

from footage_finder.config import Settings
from footage_finder.intent.generator import IntentGenerator
from footage_finder.models import (
    FullImageWatermarkCheck,
    ImageCandidate,
    ImageType,
    Segment,
    SegmentIntent,
    SegmentStatus,
)
from footage_finder.rerank.gemini_vision import GeminiVisionReranker


@pytest.mark.asyncio
async def test_intent_generation_mock():
    settings = Settings()
    gen = IntentGenerator(settings=settings, mock=True)

    segments = [
        Segment(
            id="S001",
            index=1,
            text="In 1945, the Trinity test detonated the first atomic bomb.",
        ),
        Segment(
            id="S002",
            index=2,
            text="Dr. Oppenheimer recalled the Hindu scripture line: Now I am become Death.",
        ),
    ]
    full_script = "\n\n".join(s.text for s in segments)

    intents = await gen.generate_all_intents(segments, full_script, batch_size=2)
    assert len(intents) == 2
    assert intents[0].segment_id == "S001"
    assert "Trinity" in intents[0].entities[0]
    assert len(intents[0].queries) >= 3


@pytest.mark.asyncio
async def test_reranker_and_min_score(tmp_path: Path):
    settings = Settings()
    settings.min_score = 6.0
    settings.top_picks = 2
    reranker = GeminiVisionReranker(settings=settings, mock=True)

    segment = Segment(id="S001", index=1, text="The Trinity test explosion.")
    intent = SegmentIntent(
        segment_id="S001",
        visual_intent="Archival explosion",
        entities=["Trinity test"],
        image_types=[ImageType.ARCHIVAL_PHOTO],
        queries=["Trinity test"],
    )

    # Candidate 1: 16:9 landscape (gets +0.5 aspect boost)
    cand1 = ImageCandidate(
        candidate_id="c1",
        query="Trinity",
        provider="wikimedia",
        image_url="https://example.com/1.jpg",
        thumbnail_url="https://example.com/t1.jpg",
        source_page_url="https://example.com/p1",
        source_domain="wikimedia.org",
        title="Trinity test photo 1945",
        width=1920,
        height=1080,
        aspect_ratio=1.78,
    )
    # Candidate 2: vertical portrait (gets -1.5 aspect penalty)
    cand2 = ImageCandidate(
        candidate_id="c2",
        query="Trinity",
        provider="wikimedia",
        image_url="https://example.com/2.jpg",
        thumbnail_url="https://example.com/t2.jpg",
        source_page_url="https://example.com/p2",
        source_domain="wikimedia.org",
        title="Trinity test tower vertical",
        width=1000,
        height=1600,
        aspect_ratio=0.62,
    )

    report = await reranker.rerank_and_filter_segment(
        segment=segment,
        intent=intent,
        candidates=[cand1, cand2],
        full_images_dir=tmp_path / "full_images",
    )

    assert report.status == SegmentStatus.OK
    assert len(report.top_picks) >= 1
    # Candidate 1 should have higher score than Candidate 2
    assert report.top_picks[0].candidate.candidate_id == "c1"
    assert report.top_picks[0].relevance_score > 8.0


@pytest.mark.asyncio
async def test_layer3_full_image_watermark_hard_filter(tmp_path: Path):
    """Critical Non-Negotiable Test: Watermarked candidate in Layer 3 must NEVER reach output."""
    settings = Settings()
    reranker = GeminiVisionReranker(settings=settings, mock=True)

    segment = Segment(id="S001", index=1, text="Test narration")
    intent = SegmentIntent(
        segment_id="S001",
        visual_intent="Test visual",
        entities=["Test"],
        queries=["Test"],
    )

    # Candidate A: high initial score, but has full image watermark
    cand_watermarked = ImageCandidate(
        candidate_id="cand_wm",
        query="Test",
        provider="wikimedia",
        image_url="https://example.com/wm.jpg",
        thumbnail_url="https://example.com/wm_t.jpg",
        source_page_url="https://example.com/wm",
        source_domain="wikimedia.org",
        title="High scoring but watermarked",
    )
    # Candidate B: clean
    cand_clean = ImageCandidate(
        candidate_id="cand_clean",
        query="Test",
        provider="wikimedia",
        image_url="https://example.com/clean.jpg",
        thumbnail_url="https://example.com/clean_t.jpg",
        source_page_url="https://example.com/clean",
        source_domain="wikimedia.org",
        title="Clean image",
    )

    # Mock verify_full_image_watermark so cand_wm returns has_watermark=True
    async def mock_wm_check(cand: ImageCandidate, _dir: Path):
        if cand.candidate_id == "cand_wm":
            return FullImageWatermarkCheck(
                candidate_id=cand.candidate_id,
                has_watermark=True,
                is_stock_preview=True,
                reason="Alamy translucent watermark overlay detected",
            )
        return FullImageWatermarkCheck(
            candidate_id=cand.candidate_id,
            has_watermark=False,
            is_stock_preview=False,
            reason="Clean verified",
        )

    with patch.object(
        reranker, "verify_full_image_watermark", side_effect=mock_wm_check
    ):
        report = await reranker.rerank_and_filter_segment(
            segment=segment,
            intent=intent,
            candidates=[cand_watermarked, cand_clean],
            full_images_dir=tmp_path / "full_images",
        )

    # Watermarked candidate must NEVER be in top picks or alternates
    all_output_ids = [p.candidate.candidate_id for p in report.top_picks] + [
        a.candidate.candidate_id for a in report.alternates
    ]
    assert "cand_wm" not in all_output_ids
    assert "cand_clean" in all_output_ids
