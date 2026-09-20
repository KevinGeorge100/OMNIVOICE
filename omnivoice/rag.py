import asyncio
import time
from dataclasses import dataclass

import faiss
import numpy as np

from .duplex import normalize


class Embedder:
    def __init__(self, name, cache_dir):
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model_name=name, cache_dir=cache_dir, threads=1, local_files_only=True)

    def encode(self, texts):
        vectors = np.asarray(list(self.model.embed(texts)), dtype=np.float32)
        faiss.normalize_L2(vectors)
        return vectors


@dataclass
class Snapshot:
    revision: int
    rows: list[dict]
    index: object | None
    vectors: np.ndarray | None
    expires: float


class Knowledge:
    """Immutable per-tenant corpus and bounded speculative cache snapshots."""

    def __init__(self, store, embedder=None, threshold=0.93, ttl=300):
        self.store, self.embedder = store, embedder
        self.threshold, self.ttl = threshold, ttl
        self.corpora = {}
        self.caches = {}
        self.locks = {}

    def invalidate(self, tenant_id):
        self.corpora.pop(tenant_id, None)
        self.caches.pop(tenant_id, None)

    async def refresh(self, tenant_id):
        async with self.locks.setdefault(tenant_id, asyncio.Lock()):
            tenant = await self.store.tenant(tenant_id)
            revision = tenant["revision"]
            existing = self.corpora.get(tenant_id)
            if existing and existing.revision == revision:
                return existing
            records = await self.store.rows("SELECT * FROM knowledge WHERE tenant_id=?", (tenant_id,))
            rows = []
            for record in records:
                if record["kind"] == "faq":
                    rows.append(record)
                else:
                    # Small overlapping chunks; a schema is context, never executable SQL.
                    for i in range(0, len(record["text"]), 1000):
                        rows.append({**record, "text": record["text"][i : i + 1200]})
            index, vectors = None, None
            if self.embedder and rows:

                def build():
                    matrix = self.embedder.encode(
                        [r["title"] if r["kind"] == "faq" else r["text"] for r in rows]
                    )
                    idx = faiss.IndexFlatIP(matrix.shape[1])
                    idx.add(matrix)
                    return idx, matrix

                index, vectors = await asyncio.to_thread(build)
            snapshot = Snapshot(revision, rows, index, vectors, float("inf"))
            # An ingestion during embedding must not publish an obsolete snapshot.
            if (await self.store.tenant(tenant_id))["revision"] == revision:
                self.corpora[tenant_id] = snapshot
            return snapshot

    async def retrieve(self, tenant_id, text, limit=5):
        corpus = await self.refresh(tenant_id)
        if corpus.index is None:
            words = set(normalize(text).split())
            ranked = sorted(
                corpus.rows,
                key=lambda r: len(words & set(normalize(r["title"] + " " + r["text"]).split())),
                reverse=True,
            )
            return [r for r in ranked[:limit] if words & set(normalize(r["title"] + " " + r["text"]).split())]
        vector = await asyncio.to_thread(self.embedder.encode, [text])
        _, indices = await asyncio.to_thread(corpus.index.search, vector, min(limit, len(corpus.rows)))
        return [corpus.rows[i] for i in indices[0] if i >= 0]

    async def warm(self, tenant_id, topics):
        corpus = await self.refresh(tenant_id)
        chosen = {}
        for topic in topics[:5]:
            for row in await self.retrieve(tenant_id, topic):
                if row["kind"] == "faq" and row["approved"]:
                    chosen[row["id"]] = row
        rows = list(chosen.values())[:64]
        index, vectors = None, None
        if self.embedder and rows:
            vectors = await asyncio.to_thread(self.embedder.encode, [r["title"] for r in rows])

            def build():
                idx = faiss.IndexFlatIP(vectors.shape[1])
                idx.add(vectors)
                return idx

            index = await asyncio.to_thread(build)
        if (await self.store.tenant(tenant_id))["revision"] == corpus.revision:
            self.caches[tenant_id] = Snapshot(
                corpus.revision, rows, index, vectors, time.monotonic() + self.ttl
            )

    async def fast_answer(self, tenant_id, text):
        start = time.perf_counter()
        corpus = self.corpora.get(tenant_id)
        cache = self.caches.get(tenant_id)
        # Exact approved FAQs are safe without embedding inference.
        for row in corpus.rows if corpus else []:
            if row["kind"] == "faq" and row["approved"] and normalize(row["title"]) == normalize(text):
                return row["text"], "exact", (time.perf_counter() - start) * 1000
        if not cache or cache.expires < time.monotonic() or not corpus or cache.revision != corpus.revision:
            return None, "miss", (time.perf_counter() - start) * 1000
        if cache.index is not None:
            vector = await asyncio.to_thread(self.embedder.encode, [text])
            scores, indices = await asyncio.to_thread(cache.index.search, vector, min(2, len(cache.rows)))
            # An ambiguity margin avoids choosing near-tied business answers.
            if scores[0][0] >= self.threshold and (
                len(scores[0]) == 1 or scores[0][0] - scores[0][1] >= 0.04
            ):
                return cache.rows[indices[0][0]]["text"], "semantic", (time.perf_counter() - start) * 1000
        return None, "miss", (time.perf_counter() - start) * 1000
