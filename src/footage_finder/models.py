"""Core data models for Footage Finder using Pydantic v2."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

# ----------------- Script & Segmentation -----------------


class Segment(BaseModel):
    id: str  # e.g. "S001"
    index: int  # 1-based order
    text: str  # Narration text for beat


class ImageType(str, Enum):
    REAL_LOCATION_PHOTO = "real_location_photo"
    ARCHIVAL_PHOTO = "archival_photo"
    HISTORICAL_MAP = "historical_map"
    DIAGRAM_OR_CHART = "diagram_or_chart"
    PORTRAIT = "portrait"
    OBJECT_CLOSEUP = "object_closeup"
    GENERIC_BROLL = "generic_broll"


class SegmentIntent(BaseModel):
    segment_id: str
    visual_intent: str  # What viewer should see
    entities: list[str] = Field(
        default_factory=list
    )  # People, places, objects, events, era
    image_types: list[ImageType] = Field(default_factory=list)  # Preferred visual types
    queries: list[str] = Field(
        default_factory=list
    )  # 3-5 search queries with era/date terms


class BatchIntentResponse(BaseModel):
    intents: list[SegmentIntent]


# ----------------- Image & Candidate Models -----------------


class LicenseType(str, Enum):
    PUBLIC_DOMAIN = "public_domain"
    CREATIVE_COMMONS = "creative_commons"
    UNKNOWN = "unknown – verify"


class ImageCandidate(BaseModel):
    candidate_id: str  # SHA-256 or MD5 hex digest of URL
    query: str
    provider: str  # "serper" | "wikimedia"
    image_url: str
    thumbnail_url: str
    source_page_url: str
    source_domain: str
    title: str | None = None
    width: int | None = None
    height: int | None = None
    aspect_ratio: float | None = None  # width / height
    license: LicenseType = LicenseType.UNKNOWN
    license_name: str | None = None  # e.g. "Public domain", "CC BY-SA 4.0"
    author: str | None = None
    attribution_required: bool = False
    attribution_text: str = ""  # Ready to paste into YouTube description
    local_thumbnail_path: str | None = None
    full_image_local_path: str | None = None
    perceptual_hash: str | None = None
    watermark_checked: bool = False
    http_status: int | None = None


class VideoLead(BaseModel):
    lead_id: str
    segment_id: str
    title: str
    video_url: str
    channel_title: str
    thumbnail_url: str
    published_at: str | None = None
    license_note: str = "copyrighted – verify before use"


# ----------------- Evaluation & Watermark Defense -----------------


class RerankEvaluation(BaseModel):
    candidate_id: str
    relevance_score: float = Field(ge=0.0, le=10.0)
    matches: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    reason: str
    has_watermark: bool = False
    has_text_overlay_or_logo: bool = False
    has_tv_channel_bug: bool = False
    looks_ai_generated: bool = False
    is_stock_preview: bool = False
    confidence: float = 1.0


class BatchRerankResponse(BaseModel):
    evaluations: list[RerankEvaluation]


class FullImageWatermarkCheck(BaseModel):
    candidate_id: str
    has_watermark: bool = False
    has_text_overlay_or_logo: bool = False
    has_tv_channel_bug: bool = False
    looks_ai_generated: bool = False
    is_stock_preview: bool = False
    confidence: float = 1.0
    reason: str = ""


class EvaluatedImage(BaseModel):
    candidate: ImageCandidate
    relevance_score: float
    matches: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    reason: str
    rank: int
    has_watermark: bool = False
    has_text_overlay_or_logo: bool = False
    has_tv_channel_bug: bool = False
    looks_ai_generated: bool = False
    is_stock_preview: bool = False


# ----------------- Segment Report Models -----------------


class SegmentStatus(str, Enum):
    OK = "ok"
    WEAK_MATCHES = "weak_matches"
    NO_MATCH = "no_match"


class SegmentReport(BaseModel):
    segment: Segment
    intent: SegmentIntent
    top_picks: list[EvaluatedImage] = Field(default_factory=list)
    alternates: list[EvaluatedImage] = Field(default_factory=list)
    video_leads: list[VideoLead] = Field(default_factory=list)
    total_candidates_searched: int = 0
    status: SegmentStatus = SegmentStatus.OK
    suggestion: str | None = None


# ----------------- Usage & Tracking -----------------


class UsageStats(BaseModel):
    gemini_text_calls: int = 0
    gemini_vision_calls: int = 0
    serper_queries: int = 0
    wikimedia_queries: int = 0
    youtube_queries: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    estimated_cost_usd: float = 0.0
    watermark_removed_layer1: int = 0  # Domain blocklist
    watermark_removed_layer2: int = 0  # URL heuristics
    watermark_removed_layer3: int = 0  # Full-image Gemini Vision
