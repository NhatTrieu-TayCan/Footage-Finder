"""Configuration and settings management for Footage Finder."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    serper_api_key: str | None = Field(default=None, alias="SERPER_API_KEY")
    youtube_api_key: str | None = Field(default=None, alias="YOUTUBE_API_KEY")

    # Gemini Models
    gemini_text_model: str = Field(
        default="gemini-3.8-flash", alias="GEMINI_TEXT_MODEL"
    )
    gemini_vision_model: str = Field(
        default="gemini-3.8-flash", alias="GEMINI_VISION_MODEL"
    )

    # Tunables
    candidates_per_segment: int = Field(default=15, alias="CANDIDATES_PER_SEGMENT")
    top_picks: int = Field(default=3, alias="TOP_PICKS")
    max_alternates: int = Field(default=5, alias="MAX_ALTERNATES")
    min_width_general: int = Field(default=1280, alias="MIN_WIDTH_GENERAL")
    min_width_archival: int = Field(default=600, alias="MIN_WIDTH_ARCHIVAL")
    prefer_aspect: str = Field(default="16:9", alias="PREFER_ASPECT")
    min_score: float = Field(default=6.0, alias="MIN_SCORE")

    # Networking & Rate limits
    concurrent_search_limit: int = Field(default=4, alias="CONCURRENT_SEARCH_LIMIT")
    concurrent_download_limit: int = Field(default=6, alias="CONCURRENT_DOWNLOAD_LIMIT")
    request_timeout_seconds: float = Field(
        default=15.0, alias="REQUEST_TIMEOUT_SECONDS"
    )
    wikimedia_user_agent: str = Field(
        default="FootageFinder/1.0 (https://github.com/nhattrieu/Footage-Finder; contact@footagefinder.app)",
        alias="WIKIMEDIA_USER_AGENT",
    )
    search_cache_ttl_hours: int = Field(default=72, alias="SEARCH_CACHE_TTL_HOURS")

    # Paths
    pricing_file: Path = Path("config/pricing.toml")
    blocklist_file: Path = Path("config/blocklist.txt")


def load_domain_blocklist(blocklist_path: Path | None = None) -> set[str]:
    """Load blocked domain names from config/blocklist.txt."""
    path = blocklist_path or Path("config/blocklist.txt")
    if not path.exists():
        return {
            "shutterstock.com",
            "alamy.com",
            "gettyimages.com",
            "istockphoto.com",
            "dreamstime.com",
            "depositphotos.com",
            "123rf.com",
            "stock.adobe.com",
            "adobestock.com",
            "bigstockphoto.com",
            "canstockphoto.com",
            "agefotostock.com",
            "pond5.com",
            "storyblocks.com",
            "vectorstock.com",
            "freepik.com",
            "pinterest.com",
        }
    domains = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            cleaned = line.strip().lower()
            if cleaned and not cleaned.startswith("#"):
                domains.add(cleaned)
    return domains


def load_pricing(pricing_path: Path | None = None) -> dict[str, Any]:
    """Load pricing tables from config/pricing.toml."""
    path = pricing_path or Path("config/pricing.toml")
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def validate_gemini_models_or_fail(
    client: Any, text_model: str, vision_model: str
) -> None:
    """Validate configured Gemini models against available models in API."""
    try:
        available_models = [m.name for m in client.models.list()]
    except Exception as e:
        raise RuntimeError(f"Failed to query Gemini API models: {e}") from e

    # Normalization: API models usually start with 'models/'
    normalized_available = {
        m.replace("models/", "").lower(): m for m in available_models
    }

    req_text = text_model.replace("models/", "").lower()
    req_vision = vision_model.replace("models/", "").lower()

    if req_text not in normalized_available:
        available_flash = [m for m in normalized_available if "flash" in m]
        raise ValueError(
            f"Configured GEMINI_TEXT_MODEL '{text_model}' was not found in available models! "
            f"Available flash models include: {available_flash[:5]}"
        )

    if req_vision not in normalized_available:
        available_flash = [m for m in normalized_available if "flash" in m]
        raise ValueError(
            f"Configured GEMINI_VISION_MODEL '{vision_model}' was not found in available models! "
            f"Available flash models include: {available_flash[:5]}"
        )
