from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Chunk:
    index: int
    text: str


class TextChunker:
    def __init__(self, chunk_size: int = 512, overlap: int = 50) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[Chunk]:
        words = text.split()
        if not words:
            return []

        chunks: list[Chunk] = []
        start = 0
        index = 0
        while start < len(words):
            end = min(start + self.chunk_size, len(words))
            chunk_text = " ".join(words[start:end]).strip()
            if chunk_text:
                chunks.append(Chunk(index=index, text=chunk_text))
                index += 1
            if end >= len(words):
                break
            start = max(end - self.overlap, start + 1)
        return chunks
