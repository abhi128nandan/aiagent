"""
Embedding Engine & RAG — vector storage and retrieval-augmented generation.

Architecture (from AUTONOMOUS_AI_AGENT_ARCHITECTURE.md §2.4-2.5):
  - Embedding generation using sentence-transformers (local, no API needed)
  - Vector storage using ChromaDB (local, zero-infra)
  - RAG retrieval: query → embed → similarity search → top-k → context
  - Requirement extraction from retrieved chunks
"""
from __future__ import annotations

import os
import uuid
from typing import Dict, List, Optional

from core.logger import get_logger

logger = get_logger(__name__)


# ── Lazy-loaded embedding model ────────────────────────────────────────

_embedding_model = None
_chroma_client = None

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"  # 384 dimensions, fast, runs on CPU
EMBEDDING_DIM = 384
COLLECTION_NAME = "srs_documents"


def _get_embedding_model():
    """Lazy-load the sentence-transformer model."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
            logger.info("embedding_model_loaded", model=EMBEDDING_MODEL_NAME)
        except ImportError:
            logger.error(
                "sentence_transformers_not_installed",
                hint="pip install sentence-transformers",
            )
            raise ImportError(
                "sentence-transformers is not installed. "
                "Install: pip install sentence-transformers"
            )
    return _embedding_model


def _get_chroma_client():
    """Lazy-load ChromaDB client with persistent storage."""
    global _chroma_client
    if _chroma_client is None:
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            persist_dir = os.environ.get(
                "CHROMA_PERSIST_DIR",
                os.path.join(os.path.dirname(__file__), "..", ".chroma_db"),
            )
            os.makedirs(persist_dir, exist_ok=True)

            _chroma_client = chromadb.Client(ChromaSettings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=persist_dir,
                anonymized_telemetry=False,
            ))
            logger.info("chroma_client_initialized", persist_dir=persist_dir)

        except ImportError:
            logger.error(
                "chromadb_not_installed",
                hint="pip install chromadb",
            )
            raise ImportError(
                "ChromaDB is not installed. Install: pip install chromadb"
            )
        except Exception:
            # Newer ChromaDB versions use different initialization
            import chromadb
            persist_dir = os.environ.get(
                "CHROMA_PERSIST_DIR",
                os.path.join(os.path.dirname(__file__), "..", ".chroma_db"),
            )
            os.makedirs(persist_dir, exist_ok=True)
            _chroma_client = chromadb.PersistentClient(path=persist_dir)
            logger.info("chroma_client_initialized_v2", persist_dir=persist_dir)

    return _chroma_client


class EmbeddingEngine:
    """
    Generates embeddings and manages vector storage for RAG.

    Usage:
        engine = EmbeddingEngine()
        engine.store_chunks(chunks, document_id="doc_123")
        results = engine.search("authentication requirements", top_k=5)
    """

    def __init__(self, collection_name: str = COLLECTION_NAME):
        self.collection_name = collection_name
        self._collection = None
        # Lexical index for hybrid retrieval: document_id -> [{text, metadata, tokens}]
        self._lexical_index: Dict[str, List[Dict]] = {}

    @property
    def collection(self):
        """Lazy-load the ChromaDB collection."""
        if self._collection is None:
            client = _get_chroma_client()
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (384-dim each)
        """
        model = _get_embedding_model()
        embeddings = model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()

    def store_chunks(
        self,
        chunks: List,  # List[DocumentChunk] — avoid circular import
        document_id: str,
    ) -> int:
        """
        Store document chunks with their embeddings in the vector database.

        Args:
            chunks: List of DocumentChunk objects
            document_id: Unique identifier for the source document

        Returns:
            Number of chunks stored
        """
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        embeddings = self.embed(texts)

        ids = [f"{document_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "document_id": document_id,
                "chunk_index": c.chunk_index,
                "text": c.text[:500],  # Store preview in metadata
                **{k: str(v) for k, v in c.metadata.items()},
            }
            for c in chunks
        ]

        # ChromaDB batch upsert
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        # Build lexical index for hybrid retrieval
        self._build_lexical_index(chunks, document_id)

        logger.info(
            "chunks_stored",
            document_id=document_id,
            count=len(chunks),
            collection=self.collection_name,
        )

        return len(chunks)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Simple whitespace + punctuation tokenizer for lexical search."""
        import re
        # Lowercase, split on non-alphanumeric, filter short tokens
        tokens = re.findall(r'[a-zA-Z0-9_]+', text.lower())
        return [t for t in tokens if len(t) > 1]

    def _build_lexical_index(self, chunks: List, document_id: str) -> None:
        """Build an in-memory term-frequency index for lexical search."""
        entries = []
        for chunk in chunks:
            tokens = self._tokenize(chunk.text)
            # Compute term frequencies
            tf: Dict[str, int] = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            entries.append({
                "text": chunk.text,
                "tokens": tokens,
                "tf": tf,
                "metadata": {
                    "document_id": document_id,
                    "chunk_index": chunk.chunk_index,
                    **{k: str(v) for k, v in chunk.metadata.items()},
                },
            })
        self._lexical_index[document_id] = entries
        logger.info("lexical_index_built", document_id=document_id, entries=len(entries))

    def _semantic_search(
        self,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Pure semantic (vector) search via ChromaDB.
        Internal method — use search() for hybrid results.
        """
        query_embedding = self.embed([query])[0]

        where_filter = None
        if document_id:
            where_filter = {"document_id": document_id}

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        # Flatten ChromaDB results format
        search_results = []
        if results["documents"] and results["documents"][0]:
            for i in range(len(results["documents"][0])):
                search_results.append({
                    "text": results["documents"][0][i],
                    "score": 1 - results["distances"][0][i],  # Convert distance to similarity
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                })

        return search_results

    def lexical_search(
        self,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Keyword/lexical search over stored chunks.

        Uses BM25 if rank_bm25 is installed, otherwise falls back to
        a pure-Python TF-IDF keyword overlap scorer.

        Returns:
            List of dicts with {text, score, metadata} — same format as semantic search.
        """
        # Collect all indexed entries for the target document(s)
        entries = []
        if document_id and document_id in self._lexical_index:
            entries = self._lexical_index[document_id]
        elif not document_id:
            for doc_entries in self._lexical_index.values():
                entries.extend(doc_entries)

        if not entries:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Try BM25 if available
        try:
            from rank_bm25 import BM25Okapi
            corpus = [e["tokens"] for e in entries]
            bm25 = BM25Okapi(corpus)
            scores = bm25.get_scores(query_tokens)
            scored = list(zip(scores, entries))
            scored.sort(key=lambda x: x[0], reverse=True)
            results = []
            for score, entry in scored[:top_k]:
                if score > 0:
                    results.append({
                        "text": entry["text"],
                        "score": float(score),
                        "metadata": entry["metadata"],
                    })
            return results
        except ImportError:
            pass

        # Fallback: TF-IDF-style keyword overlap scoring
        query_token_set = set(query_tokens)
        scored = []
        for entry in entries:
            tf = entry["tf"]
            # Score = sum of TF for matching query tokens, normalized by doc length
            match_score = sum(tf.get(qt, 0) for qt in query_token_set)
            if match_score > 0 and entry["tokens"]:
                normalized = match_score / len(entry["tokens"])
                scored.append((normalized, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "text": entry["text"],
                "score": float(score),
                "metadata": entry["metadata"],
            }
            for score, entry in scored[:top_k]
        ]

    @staticmethod
    def _rrf_merge(
        semantic_results: List[Dict],
        lexical_results: List[Dict],
        top_k: int = 5,
        k: int = 60,
    ) -> List[Dict]:
        """
        Reciprocal Rank Fusion (RRF) merge of two ranked result sets.

        RRF_score = Σ 1/(k + rank)  where k=60 is the standard constant.

        Deduplicates by text[:200] to avoid counting the same chunk twice.
        """
        # Map text_key -> {text, score, metadata}
        merged: Dict[str, Dict] = {}

        for rank, result in enumerate(semantic_results):
            text_key = result["text"][:200]
            if text_key not in merged:
                merged[text_key] = {
                    "text": result["text"],
                    "score": 0.0,
                    "metadata": result["metadata"],
                }
            merged[text_key]["score"] += 1.0 / (k + rank)

        for rank, result in enumerate(lexical_results):
            text_key = result["text"][:200]
            if text_key not in merged:
                merged[text_key] = {
                    "text": result["text"],
                    "score": 0.0,
                    "metadata": result["metadata"],
                }
            merged[text_key]["score"] += 1.0 / (k + rank)

        # Sort by fused score, return top_k
        ranked = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
        return ranked[:top_k]

    def search(
        self,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Hybrid search: semantic (ChromaDB vector) + lexical (keyword/BM25),
        merged via Reciprocal Rank Fusion (RRF).

        Falls back to semantic-only if the lexical index is empty.

        Args:
            query: Search query string
            top_k: Number of results to return
            document_id: Optional filter by document ID

        Returns:
            List of dicts with {text, score, metadata}
        """
        # Semantic pass
        semantic_results = self._semantic_search(query, top_k=top_k, document_id=document_id)

        # Lexical pass
        lexical_results = self.lexical_search(query, top_k=top_k, document_id=document_id)

        # If no lexical results, return semantic-only (backward compat)
        if not lexical_results:
            logger.info(
                "rag_search",
                query=query[:80],
                results=len(semantic_results),
                mode="semantic_only",
                top_score=round(semantic_results[0]["score"], 3) if semantic_results else 0,
            )
            return semantic_results

        # RRF merge
        merged = self._rrf_merge(semantic_results, lexical_results, top_k=top_k)

        logger.info(
            "rag_search",
            query=query[:80],
            results=len(merged),
            mode="hybrid_rrf",
            semantic_count=len(semantic_results),
            lexical_count=len(lexical_results),
            top_score=round(merged[0]["score"], 3) if merged else 0,
        )

        return merged

    def search_multiple(
        self,
        queries: List[str],
        top_k: int = 3,
        document_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Search with multiple queries and deduplicate results.

        Useful for requirement extraction where we search for different
        aspects (functional, non-functional, technical, etc.)
        """
        all_results = []
        seen_texts = set()

        for query in queries:
            results = self.search(query, top_k=top_k, document_id=document_id)
            for result in results:
                text_key = result["text"][:100]
                if text_key not in seen_texts:
                    seen_texts.add(text_key)
                    all_results.append(result)

        # Sort by score
        all_results.sort(key=lambda r: r["score"], reverse=True)

        return all_results

    def delete_document(self, document_id: str) -> None:
        """Delete all chunks for a document."""
        try:
            self.collection.delete(where={"document_id": document_id})
            logger.info("document_deleted", document_id=document_id)
        except Exception as e:
            logger.error("document_delete_failed", document_id=document_id, error=str(e))

    def get_stats(self) -> Dict:
        """Get collection statistics."""
        return {
            "collection": self.collection_name,
            "count": self.collection.count(),
        }


class RAGRetriever:
    """
    Retrieval-Augmented Generation — retrieves relevant context for the LLM.

    This is the bridge between the vector store and the agent's prompt.
    When the agent needs to understand requirements from an SRS document,
    the RAGRetriever fetches the most relevant chunks and formats them
    as context for the LLM.
    """

    def __init__(self, engine: Optional[EmbeddingEngine] = None):
        self.engine = engine or EmbeddingEngine()

    def retrieve_context(
        self,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None,
        max_chars: int = 4000,
    ) -> str:
        """
        Retrieve relevant context for a query.

        Returns formatted text suitable for injection into the LLM prompt.

        Args:
            query: The query or task description
            top_k: Number of chunks to retrieve
            document_id: Optional filter
            max_chars: Maximum characters in the output

        Returns:
            Formatted context string
        """
        results = self.engine.search(query, top_k=top_k, document_id=document_id)

        if not results:
            return ""

        parts = ["RELEVANT REQUIREMENTS (from SRS):"]
        current_chars = 0

        for result in results:
            chunk_text = result["text"]
            score = result["score"]
            section = result.get("metadata", {}).get("section", "")

            header = f"\n[Relevance: {score:.2f}]"
            if section:
                header += f" [Section: {section}]"

            entry = f"{header}\n{chunk_text}"

            if current_chars + len(entry) > max_chars:
                break

            parts.append(entry)
            current_chars += len(entry)

        return "\n".join(parts)

    def extract_requirements(
        self,
        document_id: str,
    ) -> str:
        """
        Extract structured requirements by searching for common requirement categories.

        Returns a formatted string with all discovered requirements.
        """
        queries = [
            "functional requirements",
            "non-functional requirements",
            "system requirements specifications",
            "user stories and acceptance criteria",
            "technical requirements and constraints",
            "API endpoints and interfaces",
            "database schema and data model",
            "authentication and authorization",
            "performance requirements",
            "security requirements",
        ]

        results = self.engine.search_multiple(
            queries, top_k=3, document_id=document_id
        )

        if not results:
            return "No requirements found in the document."

        parts = ["EXTRACTED REQUIREMENTS:"]
        for i, result in enumerate(results[:15], 1):
            section = result.get("metadata", {}).get("section", "General")
            parts.append(f"\n--- Requirement Block {i} (Section: {section}) ---")
            parts.append(result["text"][:1000])

        return "\n".join(parts)
