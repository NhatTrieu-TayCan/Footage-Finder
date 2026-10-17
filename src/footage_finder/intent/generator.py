"""Visual Intent Generator using Gemini structured JSON outputs."""

from __future__ import annotations

import json
import re

from google import genai
from google.genai import errors, types

from footage_finder.cache import DiskCache, compute_cache_key
from footage_finder.config import Settings
from footage_finder.models import (
    BatchIntentResponse,
    ImageType,
    Segment,
    SegmentIntent,
)
from footage_finder.tracker import CostTracker

PROMPT_VERSION = "intent_v1.0"


class IntentGenerator:
    def __init__(
        self,
        settings: Settings,
        cache: DiskCache | None = None,
        tracker: CostTracker | None = None,
        client: genai.Client | None = None,
        mock: bool = False,
    ):
        self.settings = settings
        self.cache = cache or DiskCache()
        self.tracker = tracker or CostTracker()
        self.mock = mock

        if not mock and settings.gemini_api_key:
            self.client = client or genai.Client(api_key=settings.gemini_api_key)
        else:
            self.client = None

    def _generate_mock_intent(self, segment: Segment) -> SegmentIntent:
        """Generate deterministic mock visual intent for offline testing."""
        text = segment.text
        entities = []
        queries = []

        # Heuristic extraction for common historical documentary entities
        if "Trinity" in text or "atomic" in text or "bomb" in text:
            entities.extend(
                ["Trinity test", "atomic bomb", "1945", "New Mexico desert"]
            )
            queries.extend(
                [
                    "Trinity test explosion 1945 archival photo",
                    "Manhattan Project Trinity site New Mexico 1945",
                    "first atomic bomb explosion July 1945",
                ]
            )
            img_types = [ImageType.ARCHIVAL_PHOTO, ImageType.REAL_LOCATION_PHOTO]
            visual = (
                "Black and white archival footage/photo of the Trinity atomic explosion"
            )
        elif "Oppenheimer" in text or "Groves" in text or "bunker" in text:
            entities.extend(
                ["J. Robert Oppenheimer", "Leslie Groves", "Los Alamos", "1940s"]
            )
            queries.extend(
                [
                    "J Robert Oppenheimer portrait 1940s archival",
                    "Oppenheimer Leslie Groves Los Alamos archival photo",
                    "Los Alamos control bunker 1945",
                ]
            )
            img_types = [ImageType.PORTRAIT, ImageType.ARCHIVAL_PHOTO]
            visual = "Archival portrait of J. Robert Oppenheimer during the Manhattan Project"
        elif "Enola Gay" in text or "Hiroshima" in text or "B-29" in text:
            entities.extend(
                ["Enola Gay B-29 bomber", "Tinian Island", "Hiroshima", "August 1945"]
            )
            queries.extend(
                [
                    "B-29 Enola Gay bomber Tinian Island 1945 archival",
                    "Enola Gay crew cockpit 1945",
                    "Hiroshima August 1945 historical map",
                ]
            )
            img_types = [ImageType.ARCHIVAL_PHOTO, ImageType.HISTORICAL_MAP]
            visual = "B-29 bomber Enola Gay parked on tarmac or taking off from Tinian Island"
        else:
            words = [w for w in re.findall(r"\b[A-Z][a-z]+\b", text) if len(w) > 3]
            entities = words[:4] or ["historical event", "documentary subject"]
            q_base = " ".join(entities)
            queries = [
                f"{q_base} historical photo",
                f"{q_base} archival",
                f"{q_base} map or diagram",
            ]
            img_types = [ImageType.ARCHIVAL_PHOTO, ImageType.GENERIC_BROLL]
            visual = f"Visual depiction matching narration: {text[:80]}..."

        return SegmentIntent(
            segment_id=segment.id,
            visual_intent=visual,
            entities=entities,
            image_types=img_types,
            queries=queries,
        )

    async def generate_intents_batch(
        self, segments: list[Segment], full_script: str
    ) -> list[SegmentIntent]:
        """Generate intents for a batch of segments."""
        if not segments:
            return []

        # Check Cache
        cache_key = compute_cache_key(
            "gemini_intent",
            PROMPT_VERSION,
            [s.model_dump() for s in segments],
        )
        cached = self.cache.get_json("gemini_text", cache_key)
        if cached:
            return [SegmentIntent(**item) for item in cached]

        if self.mock or not self.client:
            mocked = [self._generate_mock_intent(s) for s in segments]
            self.cache.set_json(
                "gemini_text", cache_key, [m.model_dump(mode="json") for m in mocked]
            )
            return mocked

        # Compose prompt with full script context
        system_instruction = (
            "You are an expert visual research archivist for high-end documentary films (history, finance, technology). "
            "Given the full script context and a batch of script segments, generate precise visual intents, entities, "
            "ranked image types, and 3-5 specific English image search queries for each segment. "
            "Include specific era, date, and historical terms in search queries to find real historical photos and maps."
        )

        segments_prompt = "\n\n".join(
            f'Segment ID: {s.id}\nNarration: "{s.text}"' for s in segments
        )

        user_content = (
            f"--- FULL DOCUMENTARY SCRIPT CONTEXT ---\n{full_script}\n\n"
            f"--- BATCH SEGMENTS TO ANALYZE ---\n{segments_prompt}\n\n"
            "Return a JSON object conforming to the BatchIntentResponse schema containing an intent for every Segment ID."
        )

        try:
            response = self.client.models.generate_content(
                model=self.settings.gemini_text_model,
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=BatchIntentResponse,
                    temperature=0.2,
                ),
            )

            # Record token usage
            usage = getattr(response, "usage_metadata", None)
            in_tok = getattr(usage, "prompt_token_count", 0) or 0
            out_tok = getattr(usage, "candidates_token_count", 0) or 0
            cached_tok = getattr(usage, "cached_content_token_count", 0) or 0
            self.tracker.record_gemini_call(
                model=self.settings.gemini_text_model,
                input_tokens=in_tok,
                output_tokens=out_tok,
                cached_tokens=cached_tok,
                is_vision=False,
            )

            parsed = json.loads(response.text)
            batch_resp = BatchIntentResponse(**parsed)
            intents = batch_resp.intents

            # Ensure all segments are accounted for
            intent_map = {i.segment_id: i for i in intents}
            final_intents: list[SegmentIntent] = []
            for s in segments:
                if s.id in intent_map:
                    final_intents.append(intent_map[s.id])
                else:
                    final_intents.append(self._generate_mock_intent(s))

            self.cache.set_json(
                "gemini_text",
                cache_key,
                [i.model_dump(mode="json") for i in final_intents],
            )
            return final_intents
        except (errors.APIError, json.JSONDecodeError, ValueError, OSError, RuntimeError) as e:
            # Fallback to deterministic mock if API error occurs (e.g. 429 quota exhaustion)
            print(f"Warning: Gemini intent generation error ({e}). Using heuristic visual intent fallback.")
            return [self._generate_mock_intent(s) for s in segments]

    async def generate_all_intents(
        self, segments: list[Segment], full_script: str, batch_size: int = 5
    ) -> list[SegmentIntent]:
        """Process all segments in batches."""
        all_intents: list[SegmentIntent] = []
        for i in range(0, len(segments), batch_size):
            batch = segments[i : i + batch_size]
            batch_intents = await self.generate_intents_batch(batch, full_script)
            all_intents.extend(batch_intents)
        return all_intents
