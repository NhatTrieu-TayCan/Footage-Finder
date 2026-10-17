"""Narration chunker that segments script text into stable visual beats."""

from __future__ import annotations

import re

from footage_finder.models import Segment


def split_sentences(text: str) -> list[str]:
    """Split text into sentences while respecting common abbreviations."""
    # Simple regex-based sentence splitting that handles punctuation
    # Normalize internal whitespaces
    cleaned = re.sub(r"[ \t]+", " ", text).strip()
    # Protect common honorifics/abbreviations
    cleaned = re.sub(
        r"\b(Dr|Mr|Mrs|Ms|Prof|Gen|Col|Lt|vs|etc|i\.e|e\.g)\.",
        r"\1<DOT>",
        cleaned,
        flags=re.IGNORECASE,
    )

    # Split on sentence boundaries: period, exclamation mark, question mark followed by space or end
    raw_sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    sentences = []
    for s in raw_sentences:
        s = s.replace("<DOT>", ".").strip()
        if s:
            sentences.append(s)
    return sentences


def chunk_script(script_text: str, max_sentences_per_beat: int = 2) -> list[Segment]:
    """Segment script text into visual beats (1–3 sentences) with stable IDs S001, S002..."""
    # First check if the text is structured in paragraphs
    paragraphs = [p.strip() for p in script_text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [p.strip() for p in script_text.split("\n") if p.strip()]

    beat_texts: list[str] = []

    for para in paragraphs:
        # Check if paragraph has explicit numbering like "1.", "S001:", etc.
        cleaned_para = re.sub(r"^(?:S\d+[:.]|\d+[:.]|\-|\*)\s*", "", para).strip()
        sentences = split_sentences(cleaned_para)
        if not sentences:
            continue

        # Group sentences into chunks of 1 to max_sentences_per_beat
        current_chunk: list[str] = []
        for sentence in sentences:
            current_chunk.append(sentence)
            # If current chunk has enough sentences or is sufficiently long (>= 25 words)
            total_words = sum(len(s.split()) for s in current_chunk)
            if len(current_chunk) >= max_sentences_per_beat or total_words >= 30:
                beat_texts.append(" ".join(current_chunk))
                current_chunk = []

        if current_chunk:
            beat_texts.append(" ".join(current_chunk))

    # Build Segment objects with stable IDs
    segments: list[Segment] = []
    for idx, beat in enumerate(beat_texts, start=1):
        seg_id = f"S{idx:03d}"
        segments.append(Segment(id=seg_id, index=idx, text=beat))

    return segments


def filter_segments_range(segments: list[Segment], range_spec: str) -> list[Segment]:
    """Filter segments by range string, e.g. 'S002-S005' or 'S003' or '2-5'."""
    spec = range_spec.strip().upper()
    if "-" in spec:
        start_str, end_str = spec.split("-", 1)
        start_num = int(re.sub(r"[^\d]", "", start_str))
        end_num = int(re.sub(r"[^\d]", "", end_str))
        return [s for s in segments if start_num <= s.index <= end_num]
    else:
        target_num = int(re.sub(r"[^\d]", "", spec))
        return [s for s in segments if s.index == target_num]
