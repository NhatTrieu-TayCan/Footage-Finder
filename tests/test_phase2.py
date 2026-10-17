"""Unit tests for Phase 2: search providers, watermark defenses, aspect filters, and deduplication."""

import pytest
import respx

from footage_finder.filter.aspect_filter import (
    calculate_aspect_modifier,
    filter_by_min_width,
)
from footage_finder.filter.dedupe import CandidateDeduplicator, normalize_image_url
from footage_finder.filter.watermark_defense import WatermarkDefenseFilter
from footage_finder.models import ImageCandidate, ImageType, LicenseType
from footage_finder.search.serper import SerperProvider
from footage_finder.search.wikimedia import WikimediaProvider
from footage_finder.search.youtube import YouTubeProvider


def test_layer1_domain_blocklist():
    blocklist = {"shutterstock.com", "alamy.com", "gettyimages.com", "stock.adobe.com"}
    defense = WatermarkDefenseFilter(domain_blocklist=blocklist)

    bad_cand1 = ImageCandidate(
        candidate_id="bad1",
        query="test",
        provider="serper",
        image_url="https://image.shutterstock.com/display_pic_with_logo/123/456.jpg",
        thumbnail_url="https://thumb.shutterstock.com/123.jpg",
        source_page_url="https://www.shutterstock.com/image-photo/test-123",
        source_domain="shutterstock.com",
    )
    bad_cand2 = ImageCandidate(
        candidate_id="bad2",
        query="test",
        provider="serper",
        image_url="https://cdn.example.com/photo.jpg",
        thumbnail_url="https://cdn.example.com/thumb.jpg",
        source_page_url="https://stock.adobe.com/images/123",
        source_domain="stock.adobe.com",
    )
    good_cand = ImageCandidate(
        candidate_id="good1",
        query="test",
        provider="wikimedia",
        image_url="https://upload.wikimedia.org/wikipedia/commons/a/a1/photo.jpg",
        thumbnail_url="https://thumb.wikimedia.org/thumb.jpg",
        source_page_url="https://commons.wikimedia.org/wiki/File:photo.jpg",
        source_domain="commons.wikimedia.org",
    )

    passed, l1_drops, l2_drops = defense.filter_candidates(
        [bad_cand1, bad_cand2, good_cand]
    )
    assert len(passed) == 1
    assert passed[0].candidate_id == "good1"
    assert l1_drops == 2
    assert l2_drops == 0


def test_layer2_url_heuristics():
    blocklist = set()
    defense = WatermarkDefenseFilter(domain_blocklist=blocklist)

    wm_cand1 = ImageCandidate(
        candidate_id="wm1",
        query="test",
        provider="serper",
        image_url="https://media.defense.gov/2020/watermark_sample.jpg",
        thumbnail_url="https://media.defense.gov/thumb.jpg",
        source_page_url="https://defense.gov/123",
        source_domain="defense.gov",
    )
    wm_cand2 = ImageCandidate(
        candidate_id="wm2",
        query="test",
        provider="serper",
        image_url="https://images.sample.org/comp/comp_1234.jpg",
        thumbnail_url="https://images.sample.org/thumb.jpg",
        source_page_url="https://sample.org/123",
        source_domain="sample.org",
    )
    clean_cand = ImageCandidate(
        candidate_id="clean1",
        query="test",
        provider="serper",
        image_url="https://nara.gov/photos/1945_trinity.jpg",
        thumbnail_url="https://nara.gov/photos/thumb.jpg",
        source_page_url="https://nara.gov/trinity",
        source_domain="nara.gov",
    )

    passed, _l1_drops, l2_drops = defense.filter_candidates(
        [wm_cand1, wm_cand2, clean_cand]
    )
    assert len(passed) == 1
    assert passed[0].candidate_id == "clean1"
    assert l2_drops == 2


def test_deduplication():
    dedup = CandidateDeduplicator()

    # URL normalization
    url1 = "https://example.com/photo.jpg?utm_source=twitter&utm_medium=cpc"
    url2 = "https://example.com/photo.jpg"
    assert normalize_image_url(url1) == normalize_image_url(url2)

    cands = [
        ImageCandidate(
            candidate_id="1",
            query="q",
            provider="serper",
            image_url=url1,
            thumbnail_url="t1",
            source_page_url="p1",
            source_domain="example.com",
        ),
        ImageCandidate(
            candidate_id="2",
            query="q",
            provider="serper",
            image_url=url2,
            thumbnail_url="t2",
            source_page_url="p2",
            source_domain="example.com",
        ),
    ]
    unique = dedup.dedupe_by_url(cands)
    assert len(unique) == 1


def test_aspect_filter_and_scoring():
    # Min width
    archival_cand = ImageCandidate(
        candidate_id="c1",
        query="q",
        provider="wikimedia",
        image_url="u1",
        thumbnail_url="t1",
        source_page_url="p1",
        source_domain="d",
        width=800,  # Below 1280, but above 600
    )
    passed_archival, _drops = filter_by_min_width(
        [archival_cand],
        [ImageType.ARCHIVAL_PHOTO],
        min_width_general=1280,
        min_width_archival=600,
    )
    assert len(passed_archival) == 1

    passed_general, drops_gen = filter_by_min_width(
        [archival_cand],
        [ImageType.REAL_LOCATION_PHOTO],
        min_width_general=1280,
        min_width_archival=600,
    )
    assert len(passed_general) == 0
    assert drops_gen == 1

    # Aspect modifier
    assert calculate_aspect_modifier(1.78) > 0.4  # 16:9 landscape bonus
    assert calculate_aspect_modifier(0.6) < -1.0  # Portrait penalty


@pytest.mark.asyncio
@respx.mock
async def test_serper_provider_mocked():
    mock_response = {
        "images": [
            {
                "title": "Trinity test explosion 1945",
                "imageUrl": "https://example.org/trinity.jpg",
                "thumbnailUrl": "https://example.org/trinity_thumb.jpg",
                "imageWidth": 1920,
                "imageHeight": 1080,
                "link": "https://example.org/page",
                "domain": "example.org",
            }
        ]
    }
    respx.post("https://google.serper.dev/images").respond(json=mock_response)

    provider = SerperProvider(api_key="test_serper_key")
    results = await provider.search("Trinity test")
    assert len(results) == 1
    assert results[0].width == 1920
    assert results[0].aspect_ratio == 1.78
    assert results[0].provider == "serper"


@pytest.mark.asyncio
@respx.mock
async def test_wikimedia_provider_mocked():
    mock_response = {
        "query": {
            "pages": {
                "123": {
                    "title": "File:Oppenheimer 1944.jpg",
                    "imageinfo": [
                        {
                            "url": "https://upload.wikimedia.org/oppenheimer.jpg",
                            "thumburl": "https://thumb.wikimedia.org/oppenheimer.jpg",
                            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Oppenheimer_1944.jpg",
                            "width": 1600,
                            "height": 1200,
                            "mime": "image/jpeg",
                            "extmetadata": {
                                "LicenseShortName": {"value": "Public domain"},
                                "UsageTerms": {"value": "Public domain"},
                                "Artist": {"value": "DOE / Los Alamos"},
                            },
                        }
                    ],
                }
            }
        }
    }
    respx.get("https://commons.wikimedia.org/w/api.php").respond(json=mock_response)

    provider = WikimediaProvider(user_agent="TestAgent/1.0 (test@example.com)")
    results = await provider.search("Oppenheimer")
    assert len(results) == 1
    assert results[0].license == LicenseType.PUBLIC_DOMAIN
    assert "Public Domain" in results[0].attribution_text


@pytest.mark.asyncio
@respx.mock
async def test_youtube_provider_mocked():
    mock_response = {
        "items": [
            {
                "id": {"videoId": "dQw4w9WgXcQ"},
                "snippet": {
                    "title": "The Manhattan Project Documentary",
                    "channelTitle": "History Channel",
                    "thumbnails": {
                        "medium": {"url": "https://i.ytimg.com/vi/thumb.jpg"}
                    },
                    "publishedAt": "2023-01-01T00:00:00Z",
                },
            }
        ]
    }
    respx.get("https://www.googleapis.com/youtube/v3/search").respond(
        json=mock_response
    )

    provider = YouTubeProvider(api_key="test_yt_key")
    leads = await provider.search("Manhattan Project", segment_id="S001")
    assert len(leads) == 1
    assert leads[0].video_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert "copyrighted" in leads[0].license_note
