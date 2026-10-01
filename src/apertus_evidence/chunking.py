from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    text: str
    start_offset: int
    end_offset: int


def chunk_text(text: str, *, max_chars: int = 1200, overlap: int = 180) -> list[Chunk]:
    """Split text deterministically while preserving character offsets."""
    if max_chars < 200:
        raise ValueError("max_chars must be >= 200")
    if overlap < 0 or overlap >= max_chars:
        raise ValueError("overlap must satisfy 0 <= overlap < max_chars")

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        return []

    chunks: list[Chunk] = []
    start = 0
    ordinal = 0
    length = len(normalized)

    while start < length:
        hard_end = min(start + max_chars, length)
        end = hard_end

        if hard_end < length:
            min_break = start + max_chars // 2
            newline = normalized.rfind("\n", min_break, hard_end)
            space = normalized.rfind(" ", min_break, hard_end)
            preferred = max(newline, space)
            if preferred > start:
                end = preferred + 1

        segment = normalized[start:end]
        if segment.strip():
            chunks.append(
                Chunk(
                    ordinal=ordinal,
                    text=segment,
                    start_offset=start,
                    end_offset=end,
                )
            )
            ordinal += 1

        if end >= length:
            break

        next_start = max(0, end - overlap)
        if next_start <= start:
            next_start = end
        start = next_start

    return chunks
