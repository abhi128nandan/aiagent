"""
Tests for Hybrid Retrieval — lexical search + RRF merge.

Verifies:
- Lexical search finds exact keyword matches
- RRF merge deduplicates and boosts co-occurring chunks
- Hybrid search outperforms semantic-only for domain-specific queries
- TF-IDF fallback works without rank_bm25
"""
import pytest
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.embedding_engine import EmbeddingEngine


class FakeChunk:
    """Minimal chunk object matching DocumentChunk interface."""
    def __init__(self, text, chunk_index=0, metadata=None):
        self.text = text
        self.chunk_index = chunk_index
        self.metadata = metadata or {}


@pytest.fixture
def engine():
    """Create an EmbeddingEngine with lexical index populated."""
    eng = EmbeddingEngine.__new__(EmbeddingEngine)
    eng.collection_name = "test"
    eng._collection = None
    eng._lexical_index = {}
    return eng


def test_tokenize():
    """Tokenizer splits on non-alphanumeric and filters short tokens."""
    tokens = EmbeddingEngine._tokenize("The ItsmTicketService handles POST /api/v1/tickets")
    assert "itsmticketservice" in tokens
    assert "handles" in tokens
    assert "post" in tokens
    assert "api" in tokens
    assert "v1" in tokens
    # Single-char tokens should be filtered
    assert all(len(t) > 1 for t in tokens)


def test_build_lexical_index(engine):
    """Building lexical index creates entries with term frequencies."""
    chunks = [
        FakeChunk("The ItsmTicketService handles ticket creation", chunk_index=0),
        FakeChunk("MVitals stores patient vital signs data", chunk_index=1),
    ]
    engine._build_lexical_index(chunks, "doc-1")

    assert "doc-1" in engine._lexical_index
    entries = engine._lexical_index["doc-1"]
    assert len(entries) == 2

    # Check term frequencies exist
    assert "itsmticketservice" in entries[0]["tf"]
    assert "mvitals" in entries[1]["tf"]


def test_lexical_search_exact_match(engine):
    """Query with exact domain term returns relevant chunk."""
    chunks = [
        FakeChunk("The ItsmTicketService handles ticket creation and validation", chunk_index=0),
        FakeChunk("The user authentication module uses JWT tokens", chunk_index=1),
        FakeChunk("Database migrations are managed by Alembic", chunk_index=2),
    ]
    engine._build_lexical_index(chunks, "doc-search")

    results = engine.lexical_search("ItsmTicketService validation", top_k=3, document_id="doc-search")
    assert len(results) > 0
    # The ticket service chunk should be ranked first
    assert "ItsmTicketService" in results[0]["text"]


def test_lexical_search_no_match(engine):
    """Query with no matching terms returns empty list."""
    chunks = [
        FakeChunk("Python Flask backend setup", chunk_index=0),
    ]
    engine._build_lexical_index(chunks, "doc-no-match")

    results = engine.lexical_search("ItsmTicketService", top_k=3, document_id="doc-no-match")
    assert len(results) == 0


def test_lexical_search_empty_index(engine):
    """Search on empty index returns empty list."""
    results = engine.lexical_search("anything", top_k=3, document_id="nonexistent")
    assert results == []


def test_lexical_search_across_documents(engine):
    """Search without document_id searches across all indexed documents."""
    chunks1 = [FakeChunk("React hooks guide", chunk_index=0)]
    chunks2 = [FakeChunk("React performance optimization", chunk_index=0)]
    engine._build_lexical_index(chunks1, "doc-a")
    engine._build_lexical_index(chunks2, "doc-b")

    results = engine.lexical_search("React", top_k=5, document_id=None)
    assert len(results) == 2


def test_rrf_merge_deduplicates():
    """Same chunk from both search paths appears once with boosted score."""
    semantic = [
        {"text": "The ItsmTicketService handles creation", "score": 0.85, "metadata": {"doc": "1"}},
        {"text": "JWT authentication flow", "score": 0.70, "metadata": {"doc": "1"}},
    ]
    lexical = [
        {"text": "The ItsmTicketService handles creation", "score": 3.5, "metadata": {"doc": "1"}},
        {"text": "Database migration scripts", "score": 1.2, "metadata": {"doc": "1"}},
    ]

    merged = EmbeddingEngine._rrf_merge(semantic, lexical, top_k=5)

    # ItsmTicketService appears in both → should have highest fused score
    assert "ItsmTicketService" in merged[0]["text"]

    # Should be deduplicated (3 unique texts, not 4)
    texts = [r["text"] for r in merged]
    assert len(texts) == len(set(t[:200] for t in texts))  # No duplicates


def test_rrf_merge_score_calculation():
    """RRF scores are correctly computed as 1/(k+rank) with k=60."""
    semantic = [{"text": "chunk A", "score": 0.9, "metadata": {}}]
    lexical = [{"text": "chunk A", "score": 3.0, "metadata": {}}]

    merged = EmbeddingEngine._rrf_merge(semantic, lexical, top_k=1, k=60)

    expected_score = (1.0 / (60 + 0)) + (1.0 / (60 + 0))  # Rank 0 in both
    assert abs(merged[0]["score"] - expected_score) < 0.001


def test_rrf_merge_empty_inputs():
    """RRF merge handles empty input lists gracefully."""
    assert EmbeddingEngine._rrf_merge([], [], top_k=5) == []
    assert len(EmbeddingEngine._rrf_merge(
        [{"text": "a", "score": 1, "metadata": {}}], [], top_k=5
    )) == 1


def test_fallback_without_bm25(engine):
    """When rank_bm25 is not installed, TF-IDF fallback works correctly."""
    chunks = [
        FakeChunk("ItsmTicketService handles ticket CRUD operations", chunk_index=0),
        FakeChunk("User profile management dashboard", chunk_index=1),
    ]
    engine._build_lexical_index(chunks, "doc-fallback")

    # Patch BM25 import to fail
    with patch.dict('sys.modules', {'rank_bm25': None}):
        # Force ImportError by removing the module
        import builtins
        original_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name == 'rank_bm25':
                raise ImportError("No module named 'rank_bm25'")
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            results = engine.lexical_search("ItsmTicketService", top_k=3, document_id="doc-fallback")

    assert len(results) > 0
    assert "ItsmTicketService" in results[0]["text"]


def test_hybrid_search_integration(engine):
    """
    Full hybrid search pipeline: semantic + lexical + RRF merge.
    Mocks the semantic search to test the integration.
    """
    chunks = [
        FakeChunk("ItsmTicketService handles ticket creation and priority assignment", chunk_index=0),
        FakeChunk("The authentication module validates JWT tokens for API access", chunk_index=1),
        FakeChunk("Database models use SQLAlchemy ORM for object mapping", chunk_index=2),
    ]
    engine._build_lexical_index(chunks, "doc-hybrid")

    # Mock _semantic_search to return results (avoids ChromaDB dependency)
    semantic_results = [
        {"text": "Database models use SQLAlchemy ORM for object mapping", "score": 0.92, "metadata": {"document_id": "doc-hybrid"}},
        {"text": "ItsmTicketService handles ticket creation and priority assignment", "score": 0.75, "metadata": {"document_id": "doc-hybrid"}},
    ]

    with patch.object(engine, '_semantic_search', return_value=semantic_results):
        results = engine.search("ItsmTicketService ticket priority", top_k=3, document_id="doc-hybrid")

    assert len(results) > 0
    # ItsmTicketService should be top-ranked because it matches both semantic AND lexical
    assert "ItsmTicketService" in results[0]["text"]
