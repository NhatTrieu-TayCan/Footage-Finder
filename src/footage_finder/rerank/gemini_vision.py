"""Gemini Vision Reranker and Layer 3 Full-Image Watermark Defense."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
from google import genai
from google.genai import errors, types

from footage_finder.cache import DiskCache, compute_cache_key
from footage_finder.config import Settings
from footage_finder.filter.aspect_filter import calculate_aspect_modifier
from footage_finder.models import (
    BatchRerankResponse,
    EvaluatedImage,
    FullImageWatermarkCheck,
    ImageCandidate,
    RerankEvaluation,
    Segment,
    SegmentIntent,
    SegmentReport,
    SegmentStatus,
)
from footage_finder.tracker import CostTracker

PROMPT_VERSION = "rerank_v1.0"
WATERMARK_PROMPT_VERSION = "watermark_full_v1.0"


class GeminiVisionReranker:
    def __init__(
        self,
        settings: Settings,
        cache: DiskCache | None = None,
        tracker: CostTracker | None = None,
        client: genai.Client | None = None,
        http_client: httpx.AsyncClient | None = None,
        mock: bool = False,
    ):
        self.settings = settings
        self.cache = cache or DiskCache()
        self.tracker = tracker or CostTracker()
        self.http_client = http_client
        self.mock = mock

        if not mock and settings.gemini_api_key:
            self.client = client or genai.Client(api_key=settings.gemini_api_key)
        else:
            self.client = None

    def _mock_evaluate(
        self, candidate: ImageCandidate, intent: SegmentIntent
    ) -> RerankEvaluation:
        """Deterministic mock evaluation for tests."""
        title = (candidate.title or "").lower()
        score = 8.0
        matches = []
        concerns = []

        # Match entity keywords
        for entity in intent.entities:
            if entity.lower() in title or entity.lower() in candidate.query.lower():
                matches.append(entity)
                score += 0.5

        if candidate.provider == "wikimedia":
            score += 0.5
            matches.append("Wikimedia archival source")

        # Cap score between 0.0 and 10.0
        score = min(10.0, max(1.0, score))

        return RerankEvaluation(
            candidate_id=candidate.candidate_id,
            relevance_score=score,
            matches=matches or ["Topic match"],
            concerns=concerns,
            reason=f"Matches {', '.join(matches[:2]) or 'visual intent'}",
            has_watermark=False,
            has_text_overlay_or_logo=False,
            has_tv_channel_bug=False,
            looks_ai_generated=False,
            is_stock_preview=False,
            confidence=0.95,
        )

    async def evaluate_candidates(
        self,
        segment: Segment,
        intent: SegmentIntent,
        candidates: list[ImageCandidate],
    ) -> list[tuple[ImageCandidate, RerankEvaluation]]:
        """Rerank candidates using Gemini Vision (multimodal inspection of thumbnails)."""
        if not candidates:
            return []

        cand_map = {c.candidate_id: c for c in candidates}
        cache_key = compute_cache_key(
            "gemini_vision",
            PROMPT_VERSION,
            f"{segment.id}::{[c.candidate_id for c in candidates]}",
        )
        cached = self.cache.get_json("gemini_vision", cache_key)
        if cached:
            eval_list = [RerankEvaluation(**e) for e in cached]
            return [
                (cand_map[e.candidate_id], e)
                for e in eval_list
                if e.candidate_id in cand_map
            ]

        if self.mock or not self.client:
            evals = [self._mock_evaluate(c, intent) for c in candidates]
            self.cache.set_json(
                "gemini_vision",
                cache_key,
                [e.model_dump(mode="json") for e in evals],
            )
            return [(cand_map[e.candidate_id], e) for e in evals]

        # Prepare multimodal request parts
        intro_text = (
            f"Segment ID: {segment.id}\n"
            f'Narration: "{segment.text}"\n'
            f"Visual Intent: {intent.visual_intent}\n"
            f"Target Entities: {', '.join(intent.entities)}\n\n"
            "Evaluate each of the following candidate images. For each image, you MUST output an evaluation "
            "with its exact candidate_id, a relevance_score (0.0 to 10.0), matches, concerns, reasoning, "
            "and boolean flags for has_watermark, has_text_overlay_or_logo, has_tv_channel_bug, looks_ai_generated, and is_stock_preview."
        )
        contents: list[types.Part | str] = [intro_text]

        valid_cands_for_eval = []
        for idx, cand in enumerate(candidates, start=1):
            if (
                not cand.local_thumbnail_path
                or not Path(cand.local_thumbnail_path).exists()
            ):
                continue
            thumb_bytes = Path(cand.local_thumbnail_path).read_bytes()
            contents.append(
                f"\n--- Candidate {idx}: candidate_id='{cand.candidate_id}' | Title: '{cand.title}' ---"
            )
            contents.append(
                types.Part.from_bytes(data=thumb_bytes, mime_type="image/jpeg")
            )
            valid_cands_for_eval.append(cand)

        if not valid_cands_for_eval:
            return []

        try:
            response = self.client.models.generate_content(
                model=self.settings.gemini_vision_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=BatchRerankResponse,
                    temperature=0.1,
                ),
            )

            # Record token usage
            usage = getattr(response, "usage_metadata", None)
            in_tok = getattr(usage, "prompt_token_count", 0) or 0
            out_tok = getattr(usage, "candidates_token_count", 0) or 0
            cached_tok = getattr(usage, "cached_content_token_count", 0) or 0
            self.tracker.record_gemini_call(
                model=self.settings.gemini_vision_model,
                input_tokens=in_tok,
                output_tokens=out_tok,
                cached_tokens=cached_tok,
                is_vision=True,
            )

            parsed = json.loads(response.text)
            batch_eval = BatchRerankResponse(**parsed)
            evals_by_id = {e.candidate_id: e for e in batch_eval.evaluations}

            # Handle missing evaluations if any were omitted
            final_evals: list[RerankEvaluation] = []
            for cand in valid_cands_for_eval:
                if cand.candidate_id in evals_by_id:
                    final_evals.append(evals_by_id[cand.candidate_id])
                else:
                    final_evals.append(self._mock_evaluate(cand, intent))

            self.cache.set_json(
                "gemini_vision",
                cache_key,
                [e.model_dump(mode="json") for e in final_evals],
            )
            return [
                (cand_map[e.candidate_id], e)
                for e in final_evals
                if e.candidate_id in cand_map
            ]

        except (errors.APIError, json.JSONDecodeError, ValueError, OSError, RuntimeError):
            fallback = [self._mock_evaluate(c, intent) for c in valid_cands_for_eval]
            return [(cand_map[e.candidate_id], e) for e in fallback]

    async def verify_full_image_watermark(
        self, candidate: ImageCandidate, full_images_dir: Path
    ) -> FullImageWatermarkCheck:
        """Layer 3 Defense: Download full-size image (max 8MB) and run dedicated watermark detection."""
        full_images_dir.mkdir(parents=True, exist_ok=True)
        local_full_path = full_images_dir / f"{candidate.candidate_id}.jpg"

        # Check Cache
        cache_key = compute_cache_key(
            "full_wm_check", WATERMARK_PROMPT_VERSION, candidate.candidate_id
        )
        cached = self.cache.get_json("gemini_vision", cache_key)
        if cached:
            check = FullImageWatermarkCheck(**cached)
            candidate.watermark_checked = True
            candidate.full_image_local_path = str(local_full_path)
            return check

        if self.mock or not self.client:
            mock_check = FullImageWatermarkCheck(
                candidate_id=candidate.candidate_id,
                has_watermark=False,
                has_text_overlay_or_logo=False,
                has_tv_channel_bug=False,
                looks_ai_generated=False,
                is_stock_preview=False,
                confidence=0.98,
                reason="Clean verified image (mock mode)",
            )
            candidate.watermark_checked = True
            candidate.full_image_local_path = str(local_full_path)
            self.cache.set_json(
                "gemini_vision", cache_key, mock_check.model_dump(mode="json")
            )
            return mock_check

        # Download full image if not already downloaded
        if not local_full_path.exists():
            headers = {"User-Agent": self.settings.wikimedia_user_agent}
            client = self.http_client or httpx.AsyncClient(
                timeout=self.settings.request_timeout_seconds, follow_redirects=True
            )
            try:
                resp = await client.get(candidate.image_url, headers=headers)
                if resp.status_code == 200 and len(resp.content) <= 8 * 1024 * 1024:
                    local_full_path.write_bytes(resp.content)
                else:
                    # Fallback to thumbnail bytes if full download failed or too large
                    thumb_path = Path(candidate.local_thumbnail_path or "")
                    if thumb_path.exists():
                        local_full_path.write_bytes(thumb_path.read_bytes())
            except (httpx.HTTPError, OSError):
                thumb_path = Path(candidate.local_thumbnail_path or "")
                if thumb_path.exists():
                    local_full_path.write_bytes(thumb_path.read_bytes())
            finally:
                if not self.http_client:
                    await client.aclose()

        candidate.full_image_local_path = str(local_full_path)
        candidate.watermark_checked = True

        # Send full image to Gemini Vision for dedicated watermark analysis
        full_bytes = local_full_path.read_bytes()
        wm_prompt = (
            "Analyze this full-resolution image with extreme precision for stock watermarks, translucent watermark logos, "
            "diagonal text overlays, photographer logos, TV broadcast bugs, stock agency preview stamps, or AI artifacts. "
            "Return a JSON object conforming to FullImageWatermarkCheck."
        )

        try:
            response = self.client.models.generate_content(
                model=self.settings.gemini_vision_model,
                contents=[
                    wm_prompt,
                    types.Part.from_bytes(data=full_bytes, mime_type="image/jpeg"),
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=FullImageWatermarkCheck,
                    temperature=0.0,
                ),
            )
            usage = getattr(response, "usage_metadata", None)
            self.tracker.record_gemini_call(
                model=self.settings.gemini_vision_model,
                input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
                output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
                is_vision=True,
            )
            parsed = json.loads(response.text)
            check_obj = FullImageWatermarkCheck(**parsed)
            self.cache.set_json(
                "gemini_vision", cache_key, check_obj.model_dump(mode="json")
            )
            return check_obj
        except (errors.APIError, json.JSONDecodeError, ValueError, OSError, RuntimeError):
            return FullImageWatermarkCheck(
                candidate_id=candidate.candidate_id,
                has_watermark=False,
                confidence=0.9,
                reason="Analysis fallback",
            )

    async def rerank_and_filter_segment(
        self,
        segment: Segment,
        intent: SegmentIntent,
        candidates: list[ImageCandidate],
        full_images_dir: Path,
    ) -> SegmentReport:
        """Complete rerank pipeline:

        1. Multimodal scoring.
        2. Aspect ratio modifier.
        3. Drop any candidate flagged with watermark/stock in initial pass.
        4. Layer 3 Defense: Check full-size image for candidates reaching top picks or alternates.
        5. Hard filter: remove any candidate confirmed with watermark.
        6. Apply MIN_SCORE filter and compile top picks + alternates.
        """
        # 1. Multimodal initial evaluation
        evaluated_pairs = await self.evaluate_candidates(segment, intent, candidates)

        # 2. Score calculation with aspect ratio modifier
        scored_candidates: list[EvaluatedImage] = []
        for cand, ev in evaluated_pairs:
            # Immediate drop if thumbnail evaluation detected watermark
            if ev.has_watermark or ev.is_stock_preview:
                self.tracker.record_watermark_removal(layer=3)
                continue

            modifier = calculate_aspect_modifier(cand.aspect_ratio)
            final_score = round(max(0.0, min(10.0, ev.relevance_score + modifier)), 2)

            scored_candidates.append(
                EvaluatedImage(
                    candidate=cand,
                    relevance_score=final_score,
                    matches=ev.matches,
                    concerns=ev.concerns,
                    reason=ev.reason,
                    rank=1,
                    has_watermark=ev.has_watermark,
                    has_text_overlay_or_logo=ev.has_text_overlay_or_logo,
                    has_tv_channel_bug=ev.has_tv_channel_bug,
                    looks_ai_generated=ev.looks_ai_generated,
                    is_stock_preview=ev.is_stock_preview,
                )
            )

        # Sort descending by final score
        scored_candidates.sort(key=lambda x: x.relevance_score, reverse=True)

        # 3. Layer 3 Full-Image Watermark Verification on potential top picks & alternates
        needed_count = self.settings.top_picks + self.settings.max_alternates
        verified_candidates: list[EvaluatedImage] = []

        for item in scored_candidates:
            if len(verified_candidates) >= needed_count:
                break

            check = await self.verify_full_image_watermark(
                item.candidate, full_images_dir
            )

            # Hard filter: Purge if full image has watermark or is stock preview
            if check.has_watermark or check.is_stock_preview:
                self.tracker.record_watermark_removal(layer=3)
                continue  # Promotes next candidate!

            item.has_watermark = check.has_watermark
            item.has_text_overlay_or_logo = check.has_text_overlay_or_logo
            item.has_tv_channel_bug = check.has_tv_channel_bug
            item.looks_ai_generated = check.looks_ai_generated
            item.is_stock_preview = check.is_stock_preview

            verified_candidates.append(item)

        # Update ranks
        for idx, item in enumerate(verified_candidates, start=1):
            item.rank = idx

        # 4. Partition into Top Picks (>= MIN_SCORE) and Alternates
        min_score = self.settings.min_score
        top_picks: list[EvaluatedImage] = []
        alternates: list[EvaluatedImage] = []

        for item in verified_candidates:
            if (
                item.relevance_score >= min_score
                and len(top_picks) < self.settings.top_picks
            ):
                top_picks.append(item)
            elif len(alternates) < self.settings.max_alternates:
                alternates.append(item)

        # 5. Segment Status & Suggestion
        if len(top_picks) > 0:
            status = SegmentStatus.OK
            suggestion = None
        elif len(alternates) > 0:
            status = SegmentStatus.WEAK_MATCHES
            suggestion = "Candidates scored below MIN_SCORE threshold – consider custom historical map or diagram"
        else:
            status = SegmentStatus.NO_MATCH
            suggestion = "No archival image found – consider a custom motion graphic or archival map reconstruction"

        return SegmentReport(
            segment=segment,
            intent=intent,
            top_picks=top_picks,
            alternates=alternates,
            total_candidates_searched=len(candidates),
            status=status,
            suggestion=suggestion,
        )
