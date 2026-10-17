"""Unit tests for Phase 1 components: config, models, cache, tracker, segmenter."""

from pathlib import Path

from footage_finder.cache import DiskCache, compute_cache_key
from footage_finder.config import Settings, load_domain_blocklist, load_pricing
from footage_finder.models import (
    ImageCandidate,
    ImageType,
    LicenseType,
    RerankEvaluation,
    Segment,
    SegmentIntent,
)
from footage_finder.segmenter.chunker import chunk_script, filter_segments_range
from footage_finder.segmenter.parser import parse_script_file
from footage_finder.tracker import CostTracker


def test_config_and_blocklist():
    settings = Settings()
    assert settings.gemini_text_model is not None
    assert settings.min_width_general == 1280
    assert settings.min_width_archival == 600

    blocklist = load_domain_blocklist()
    assert "shutterstock.com" in blocklist
    assert "alamy.com" in blocklist
    assert "gettyimages.com" in blocklist
    assert "pinterest.com" in blocklist

    pricing = load_pricing()
    assert "gemini" in pricing
    assert "serper" in pricing


def test_models_validation():
    seg = Segment(
        id="S001",
        index=1,
        text="In 1942, General Leslie Groves selected Robert Oppenheimer.",
    )
    assert seg.id == "S001"

    intent = SegmentIntent(
        segment_id="S001",
        visual_intent="Oppenheimer and Groves reviewing plans in Los Alamos",
        entities=["J. Robert Oppenheimer", "Leslie Groves", "Los Alamos", "1942"],
        image_types=[ImageType.ARCHIVAL_PHOTO, ImageType.PORTRAIT],
        queries=["Oppenheimer Groves 1942 Los Alamos archival"],
    )
    assert intent.image_types[0] == ImageType.ARCHIVAL_PHOTO

    candidate = ImageCandidate(
        candidate_id="abc123hash",
        query="Oppenheimer",
        provider="wikimedia",
        image_url="https://upload.wikimedia.org/test.jpg",
        thumbnail_url="https://thumb.wikimedia.org/test.jpg",
        source_page_url="https://commons.wikimedia.org/wiki/File:Test.jpg",
        source_domain="commons.wikimedia.org",
        width=2000,
        height=1500,
        license=LicenseType.PUBLIC_DOMAIN,
        license_name="Public Domain",
        author="Unknown",
        attribution_required=False,
    )
    assert candidate.license == LicenseType.PUBLIC_DOMAIN

    rerank = RerankEvaluation(
        candidate_id="abc123hash",
        relevance_score=9.5,
        matches=["Oppenheimer", "1942"],
        concerns=[],
        reason="Authentic historical archival photo",
        has_watermark=False,
    )
    assert rerank.relevance_score == 9.5
    assert not rerank.has_watermark


def test_cache_key_and_disk_cache(tmp_path: Path):
    key1 = compute_cache_key("gemini_text", "v1.0", {"query": "test"})
    key2 = compute_cache_key("gemini_text", "v1.0", {"query": "test"})
    key3 = compute_cache_key("gemini_text", "v1.1", {"query": "test"})
    assert key1 == key2
    assert key1 != key3

    cache = DiskCache(base_dir=tmp_path / "cache")
    cache.set_json("test_cat", "item1", {"score": 42})
    val = cache.get_json("test_cat", "item1")
    assert val == {"score": 42}

    # TTL test
    cache.set_json("ttl_cat", "item2", {"msg": "hello"})
    # Within 10s age -> returns value
    assert cache.get_json("ttl_cat", "item2", max_age_seconds=10) == {"msg": "hello"}
    # Expired with negative/zero max age -> returns None
    assert cache.get_json("ttl_cat", "item2", max_age_seconds=-1) is None

    # Binary file
    saved_path = cache.save_file("thumbs", "thumb1", b"fake_jpeg_bytes", ext=".jpg")
    assert saved_path.exists()
    assert cache.get_file("thumbs", "thumb1") == saved_path


def test_cost_tracker():
    tracker = CostTracker()
    tracker.record_gemini_call(
        model="gemini-2.5-flash",
        input_tokens=100_000,
        output_tokens=10_000,
        is_vision=False,
    )
    tracker.record_search_query("serper", count=5)
    tracker.record_watermark_removal(layer=1, count=3)
    tracker.record_watermark_removal(layer=2, count=2)
    tracker.record_watermark_removal(layer=3, count=1)

    stats = tracker.get_summary()
    assert stats.gemini_text_calls == 1
    assert stats.serper_queries == 5
    assert stats.watermark_removed_layer1 == 3
    assert stats.watermark_removed_layer2 == 2
    assert stats.watermark_removed_layer3 == 1
    assert stats.estimated_cost_usd > 0.0


def test_segmenter(tmp_path: Path):
    script = (
        "In July 1945, the Trinity test detonated the first atomic bomb in the New Mexico desert. "
        "A blinding flash illuminated the Jornada del Muerto valley for miles.\n\n"
        "Dr. J. Robert Oppenheimer watched from a control bunker ten thousand yards away. "
        "He later recalled the Hindu scripture line: Now I am become Death, the destroyer of worlds.\n\n"
        "Within weeks, the B-29 bomber Enola Gay took off from Tinian Island. "
        "Its target was Hiroshima."
    )
    txt_file = tmp_path / "test_script.txt"
    txt_file.write_text(script, encoding="utf-8")

    parsed = parse_script_file(txt_file)
    assert "Trinity test" in parsed

    segments = chunk_script(parsed, max_sentences_per_beat=2)
    assert len(segments) >= 3
    assert segments[0].id == "S001"
    assert segments[1].id == "S002"

    filtered = filter_segments_range(segments, "S002-S003")
    assert len(filtered) == 2
    assert filtered[0].id == "S002"
    assert filtered[1].id == "S003"
