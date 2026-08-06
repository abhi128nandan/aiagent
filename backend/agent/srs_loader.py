"""
SRS Loader — unified document loading with RAG support.

Refactored to use the new DocumentProcessor and EmbeddingEngine.
Supports: PDF, DOCX, Markdown, plain text.
"""
import os
import uuid
from typing import Optional
from langchain_community.document_loaders import (
    PyMuPDFLoader, Docx2txtLoader, TextLoader
)
from core.logger import get_logger

logger = get_logger(__name__)


def load_srs(path: str) -> str:
    """
    Load SRS text from a file.
    
    Supports: .pdf, .docx, .txt, .md
    Uses LangChain loaders for basic loading (backward compatible).
    """
    ext = path.rsplit('.', 1)[-1].lower()
    
    loader_map = {
        'pdf':  PyMuPDFLoader,
        'docx': Docx2txtLoader,
        'txt':  TextLoader,
        'md':   TextLoader,
    }
    
    if ext not in loader_map:
        raise ValueError(f"Unsupported file extension: {ext}")
        
    loader = loader_map[ext](path)
    docs = loader.load()
    return '\n\n'.join(d.page_content for d in docs)


def _index_chunks_in_background(doc, document_id: str):
    """Background worker for embedding and vector storage."""
    try:
        from agent.document_processor import SemanticChunker
        from agent.embedding_engine import EmbeddingEngine

        chunker = SemanticChunker(chunk_size=1000, chunk_overlap=200)
        chunks = chunker.chunk_document(doc)

        engine = EmbeddingEngine()
        stored = engine.store_chunks(chunks, document_id=document_id)

        logger.info(
            "srs_rag_background_complete",
            chunks=stored,
            document_id=document_id,
        )
    except Exception as e:
        logger.warning("srs_rag_background_failed", error=str(e))


def load_srs_with_rag(path: str, enable_rag: bool = True, async_rag: bool = True) -> dict:
    """
    Load SRS document with fast text extraction and async RAG indexing.
    
    Returns:
        dict with:
          - text: full document text
          - document_id: unique ID for RAG retrieval
          - chunks: estimated or indexed chunk count
          - rag_enabled: whether RAG indexing is active
    """
    import threading

    result = {
        "text": "",
        "document_id": str(uuid.uuid4()),
        "chunks": 0,
        "rag_enabled": False,
    }

    # 1. Parse document text fast
    try:
        from agent.document_processor import DocumentParser

        parser = DocumentParser()
        doc = parser.parse(path)
        result["text"] = doc.text
        estimated_chunks = max(1, len(doc.text) // 800) if doc.text else 0
        result["chunks"] = estimated_chunks

        # 2. Trigger RAG embedding indexing
        if enable_rag and doc.text:
            result["rag_enabled"] = True
            if async_rag:
                # Dispatch vector embedding generation to background thread for 10x faster response
                threading.Thread(
                    target=_index_chunks_in_background,
                    args=(doc, result["document_id"]),
                    daemon=True
                ).start()
            else:
                _index_chunks_in_background(doc, result["document_id"])

    except ImportError:
        # Fallback to basic loader
        result["text"] = load_srs(path)
        result["chunks"] = max(1, len(result["text"]) // 800)
    except Exception as e:
        logger.warning("advanced_parser_failed", error=str(e), fallback="basic")
        result["text"] = load_srs(path)
        result["chunks"] = max(1, len(result["text"]) // 800)

    if not result["text"]:
        raise ValueError(f"No text could be extracted from: {path}")

    return result
