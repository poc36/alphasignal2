from __future__ import annotations

import hashlib
import math

from config import settings


class Embedder:
    def __init__(self) -> None:
        self.openai_api_key = settings.openai_api_key
        self.embedding_model = settings.embedding_model
        self._sentence_transformer = None

        if settings.use_sentence_transformers:
            try:
                from sentence_transformers import SentenceTransformer

                self._sentence_transformer = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
            except Exception:
                self._sentence_transformer = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._sentence_transformer:
            vectors = self._sentence_transformer.encode(texts)
            return [list(map(float, row)) for row in vectors]
        return [self._hash_embed(text) for text in texts]

    def _hash_embed(self, text: str, dims: int = 64) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = []
        for i in range(dims):
            byte = digest[i % len(digest)]
            values.append((byte / 255.0) * 2 - 1)
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]
