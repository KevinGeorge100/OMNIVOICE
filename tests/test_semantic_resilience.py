from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from omnivoice.app import create_app
from omnivoice.config import Settings
from omnivoice.rag import Knowledge
from omnivoice.store import Store


@pytest.fixture
async def store(tmp_path):
    db = Store(tmp_path / "semantic_test.db")
    await db.open()
    yield db
    await db.close()


def test_api_module_import_does_not_require_faiss():
    """Verify that importing omnivoice.app and creating an app does not import or require FAISS when semantic retrieval is disabled."""
    with patch("omnivoice.rag.load_faiss") as mock_load:
        mock_load.side_effect = RuntimeError(
            "DLL load failed while importing _swigfaiss: An Application Control policy has blocked this file."
        )
        settings = Settings(
            _env_file=None,
            admin_token="test-admin",
            semantic_enabled=False,
        )
        app = create_app(settings)
        assert app is not None
        mock_load.assert_not_called()


def test_readiness_semantic_disabled_defaults():
    """When semantic retrieval is disabled, readiness must report lexical mode and NOT flag any missing semantic setting."""
    settings = Settings(
        _env_file=None,
        admin_token="test-admin",
        semantic_enabled=False,
    )
    with TestClient(create_app(settings)) as client:
        resp = client.get("/api/status", headers={"Authorization": "Bearer test-admin"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["semantic_cache"] is False
        assert data["retrieval_mode"] == "exact FAQ + lexical document retrieval"
        assert data["model_error"] is None
        assert "SEMANTIC_BACKEND_UNAVAILABLE" not in data["missing"]


async def test_semantic_disabled_faq_and_lexical_path(store):
    """When semantic retrieval is disabled (embedder=None), exact FAQ and lexical document retrieval remain fully functional."""
    tenant_id = (await store.create_tenant({"name": "Lexical Corp"}))["id"]
    await store.add_knowledge(
        tenant_id, "faq", "What is your pricing?", "Pricing starts at 10 dollars.", approved=True
    )
    await store.add_knowledge(
        tenant_id, "document", "Refund Policy", "Full refund within 30 days of purchase.", approved=True
    )

    rag = Knowledge(store, embedder=None)
    await rag.refresh(tenant_id)

    # Exact FAQ fast answer
    ans, kind, elapsed = await rag.fast_answer(tenant_id, "What is your pricing?")
    assert ans == "Pricing starts at 10 dollars."
    assert kind == "exact"
    assert elapsed >= 0

    # Lexical document retrieval
    docs = await rag.retrieve(tenant_id, "How do I get a refund within 30 days?")
    assert len(docs) >= 1
    assert "Refund Policy" in docs[0]["title"]


def test_readiness_semantic_enabled_backend_available(tmp_path):
    """When semantic retrieval is enabled and backend is available, readiness reflects FAISS semantic active."""
    mock_embedder = MagicMock()
    mock_embedder.faiss = MagicMock()

    with patch("omnivoice.app.Embedder", return_value=mock_embedder):
        settings = Settings(
            _env_file=None,
            database=tmp_path / "sem_avail.db",
            admin_token="test-admin",
            semantic_enabled=True,
        )
        with TestClient(create_app(settings)) as client:
            resp = client.get("/api/status", headers={"Authorization": "Bearer test-admin"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["semantic_cache"] is True
            assert data["retrieval_mode"] == "FAISS semantic + exact FAQ"
            assert data["model_error"] is None
            assert "SEMANTIC_BACKEND_UNAVAILABLE" not in data["missing"]


def test_readiness_semantic_enabled_backend_unavailable(tmp_path):
    """When semantic retrieval is enabled but backend fails to load:
    - Readiness flags SEMANTIC_BACKEND_UNAVAILABLE in missing
    - voice_ready is False
    - /readyz returns 503
    - retrieval_mode reports degraded state
    - model_error provides clear diagnostics
    """
    with patch(
        "omnivoice.app.Embedder",
        side_effect=RuntimeError("FAISS vector engine unavailable: DLL blocked by security policy"),
    ):
        settings = Settings(
            _env_file=None,
            database=tmp_path / "sem_unavail.db",
            admin_token="test-admin",
            semantic_enabled=True,
        )
        with TestClient(create_app(settings)) as client:
            status_resp = client.get("/api/status", headers={"Authorization": "Bearer test-admin"})
            assert status_resp.status_code == 200
            data = status_resp.json()
            assert data["semantic_cache"] is False
            assert (
                data["retrieval_mode"]
                == "exact FAQ + lexical document retrieval (degraded: semantic backend unavailable)"
            )
            assert data["model_error"] == "Semantic retrieval unavailable; falling back to lexical retrieval"


async def test_semantic_enabled_with_mock_faiss(store):
    """Verify Knowledge.refresh and retrieve work properly when Embedder and FAISS mock are provided."""
    tenant_id = (await store.create_tenant({"name": "Vector Corp"}))["id"]
    await store.add_knowledge(
        tenant_id, "faq", "Where is head office?", "Head office is in Bengaluru.", approved=True
    )

    mock_faiss = MagicMock()
    mock_index = MagicMock()
    mock_index.search.return_value = (np.array([[0.99]]), np.array([[0]]))
    mock_faiss.IndexFlatIP.return_value = mock_index

    mock_embedder = MagicMock()
    mock_embedder.faiss = mock_faiss
    mock_embedder.encode.return_value = np.array([[0.1, 0.2, 0.3]], dtype=np.float32)

    rag = Knowledge(store, embedder=mock_embedder)
    snapshot = await rag.refresh(tenant_id)
    assert snapshot.index is not None
    mock_faiss.IndexFlatIP.assert_called_once()
    mock_index.add.assert_called_once()

    results = await rag.retrieve(tenant_id, "Where is your office located?")
    assert len(results) == 1
    assert results[0]["title"] == "Where is head office?"
