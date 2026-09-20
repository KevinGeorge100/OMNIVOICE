"""Real local model validation and synthetic microbenchmark, no provider API calls."""

import asyncio
import json
import tempfile
import time
from pathlib import Path

import numpy as np

from omnivoice.config import Settings
from omnivoice.rag import Embedder, Knowledge
from omnivoice.store import Store
from omnivoice.vad import SileroFactory


async def main():
    settings = Settings()
    vad = SileroFactory(settings.silero_model).session()
    probabilities = vad.process(b"\0" * 32000)
    assert probabilities and max(probabilities) < 0.6
    embedder = Embedder(settings.embedding_model, settings.embedding_cache)
    with tempfile.TemporaryDirectory() as directory:
        store = Store(Path(directory) / "models.db")
        await store.open()
        try:
            tenant = await store.create_tenant({"name": "Synthetic model verification"})
            tenant_id = tenant["id"]
            await store.add_knowledge(
                tenant_id, "faq", "When does the test office open?", "Synthetic test answer: nine.", True
            )
            await store.add_knowledge(
                tenant_id,
                "faq",
                "How do I cancel a test reservation?",
                "Synthetic test cancellation instructions.",
                True,
            )
            rag = Knowledge(store, embedder)
            await rag.refresh(tenant_id)
            await rag.warm(tenant_id, ["test office opening", "test reservation cancellation"])
            assert rag.caches[tenant_id].index.ntotal == 2
            rows = await rag.retrieve(tenant_id, "What time does the test office open?")
            assert rows[0]["title"] == "When does the test office open?"
            timings = []
            for _ in range(25):
                began = time.perf_counter()
                answer, kind, elapsed = await rag.fast_answer(tenant_id, "When does the test office open?")
                assert answer == "Synthetic test answer: nine." and kind == "exact"
                timings.append((time.perf_counter() - began) * 1000)
            index = rag.caches[tenant_id].index
            query = embedder.encode(["What time does the test office open?"])
            search = []
            for _ in range(25):
                began = time.perf_counter()
                index.search(query, 1)
                search.append((time.perf_counter() - began) * 1000)
            report = {
                "silero_silence_check": "passed",
                "multilingual_embedding_model": settings.embedding_model,
                "faiss_retrieval_check": "passed",
                "synthetic_faq_count": 2,
                "samples": 25,
                "exact_faq_p95_ms": float(np.percentile(timings, 95)),
                "faiss_search_only_p95_ms": float(np.percentile(search, 95)),
                "scope": "Two synthetic FAQs, local single-process microbenchmark. Excludes query embedding, network, STT, TTS, PSTN. Not Fisher/FD-Bench results or an end-to-end latency claim.",
            }
            Path("artifacts").mkdir(exist_ok=True)
            Path("artifacts/model-check.json").write_text(json.dumps(report, indent=2))
            print(json.dumps(report))
        finally:
            await store.close()


if __name__ == "__main__":
    asyncio.run(main())
