from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path

from config import settings


class Retriever:
    def __init__(self, store_path: str | None = None) -> None:
        self.store_path = Path(store_path or settings.vector_store_path)
        self.records: list[dict] = []
        self.use_chromadb = settings.use_chromadb
        self._collection = None
        self._init_backend()

    def upsert(self, items: list[dict]) -> None:
        if self._collection is not None:
            ids = [f"{item['article_id']}::{item['chunk_index']}" for item in items]
            documents = [item["content"] for item in items]
            metadatas = [
                {
                    "article_id": item["article_id"],
                    "chunk_index": item["chunk_index"],
                    "ticker": item["ticker"],
                    "source_url": item["source_url"] or "",
                    "source_name": item["source_name"] or "",
                }
                for item in items
            ]
            embeddings = [item["embedding"] for item in items]
            self._collection.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
            return

        existing = {(record["article_id"], record["chunk_index"]): record for record in self.records}
        for item in items:
            existing[(item["article_id"], item["chunk_index"])] = item
        self.records = list(existing.values())
        self._persist()

    def search(self, query_vector: list[float], ticker: str | None = None, top_k: int = 5) -> list[dict]:
        if self._collection is not None:
            where = {"ticker": ticker.upper()} if ticker else None
            result = self._collection.query(query_embeddings=[query_vector], n_results=top_k, where=where)
            documents = result.get("documents", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            records = []
            for document, metadata in zip(documents, metadatas):
                records.append(
                    {
                        "article_id": metadata.get("article_id"),
                        "chunk_index": metadata.get("chunk_index"),
                        "ticker": metadata.get("ticker"),
                        "content": document,
                        "source_url": metadata.get("source_url"),
                        "source_name": metadata.get("source_name"),
                    }
                )
            return records

        candidates = self.records
        if ticker:
            candidates = [record for record in candidates if record["ticker"].upper() == ticker.upper()]

        scored = []
        for record in candidates:
            score = self._cosine(query_vector, record["embedding"])
            scored.append((score, record))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [record for _, record in scored[:top_k]]

    def _persist(self) -> None:
        self.store_path.write_text(json.dumps(self.records, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load(self) -> None:
        if self.store_path.exists():
            try:
                self.records = json.loads(self.store_path.read_text(encoding="utf-8"))
            except Exception:
                self.records = []

    def _init_backend(self) -> None:
        if self.use_chromadb:
            try:
                import chromadb
                from chromadb.config import Settings as ChromaSettings

                os.environ.setdefault("ANONYMIZED_TELEMETRY", "FALSE")
                logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)
                client = chromadb.PersistentClient(
                    path=settings.chroma_path,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
                self._collection = client.get_or_create_collection(name="alphasignal_chunks")
                return
            except Exception:
                self._collection = None
        self._load()

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        numerator = sum(x * y for x, y in zip(a, b))
        denominator_a = math.sqrt(sum(x * x for x in a)) or 1.0
        denominator_b = math.sqrt(sum(y * y for y in b)) or 1.0
        return numerator / (denominator_a * denominator_b)
