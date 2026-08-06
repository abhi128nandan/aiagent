"""
Document Processor — PDF, DOCX, Markdown parsing with intelligent chunking.

Architecture (from AUTONOMOUS_AI_AGENT_ARCHITECTURE.md §2):
  - Multi-format parsing: PDF (pdfplumber/PyMuPDF), DOCX (docx2txt), MD/TXT
  - Text preprocessing: clean formatting artifacts, normalize whitespace
  - Intelligent chunking: semantic + structural splitting with overlap
  - Metadata preservation: section, page, chunk index
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DocumentChunk:
    """A single chunk from a parsed document."""
    text: str
    chunk_index: int
    metadata: Dict = field(default_factory=dict)

    @property
    def token_estimate(self) -> int:
        """Rough token count (1 token ≈ 4 chars)."""
        return max(1, len(self.text) // 4)


@dataclass
class ParsedDocument:
    """Result of parsing a document."""
    text: str
    sections: List[Dict] = field(default_factory=list)
    tables: List[List] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    chunks: List[DocumentChunk] = field(default_factory=list)
    source_file: str = ""
    file_type: str = ""


class DocumentParser:
    """
    Multi-format document parser.

    Supports:
      - PDF (via PyMuPDF / fitz — already in requirements)
      - DOCX (via docx2txt — already in requirements)
      - Markdown (.md)
      - Plain text (.txt)
    """

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".md", ".txt", ".markdown"}

    def parse(self, file_path: str) -> ParsedDocument:
        """
        Parse a document file and return structured content.

        Args:
            file_path: Path to the document file

        Returns:
            ParsedDocument with text, sections, tables, and metadata
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Document not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {ext}. "
                f"Supported: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}"
            )

        doc = ParsedDocument(text="", source_file=file_path, file_type=ext)

        if ext == ".pdf":
            self._parse_pdf(file_path, doc)
        elif ext in (".docx", ".doc"):
            self._parse_docx(file_path, doc)
        elif ext in (".md", ".markdown"):
            self._parse_markdown(file_path, doc)
        elif ext == ".txt":
            self._parse_text(file_path, doc)

        # Clean the text
        doc.text = self._clean_text(doc.text)

        # Extract sections from the text
        if not doc.sections:
            doc.sections = self._extract_sections(doc.text)

        logger.info(
            "document_parsed",
            file=os.path.basename(file_path),
            file_type=ext,
            text_length=len(doc.text),
            sections=len(doc.sections),
            tables=len(doc.tables),
        )

        return doc

    def _parse_pdf(self, file_path: str, doc: ParsedDocument) -> None:
        """Parse PDF using MarkItDown, with fallback to PyMuPDF (fitz) or pdfplumber."""
        try:
            from markitdown import MarkItDown

            md = MarkItDown()
            result = md.convert(file_path)
            doc.text = result.text_content
            doc.metadata = {"file_type": "pdf", "parser": "markitdown"}
            return

        except Exception as e:
            logger.warning("markitdown_parsing_failed", error=str(e), fallback="pymupdf")
            # Fallback to PyMuPDF
            try:
                import fitz  # PyMuPDF

                pdf = fitz.open(file_path)
                doc.metadata = {
                    "title": pdf.metadata.get("title", ""),
                    "author": pdf.metadata.get("author", ""),
                    "pages": len(pdf),
                    "parser": "pymupdf",
                }

                pages_text = []
                for page_num in range(1, len(pdf) + 1):
                    page = pdf[page_num - 1]
                    text = page.get_text("text")
                    pages_text.append(text)

                    # Extract tables (basic heuristic: detect tabular content)
                    blocks = page.get_text("blocks")
                    for block in blocks:
                        if block[6] == 0:  # Text block
                            text_block = block[4]
                            if "\t" in text_block or "  |  " in text_block:
                                rows = [
                                    [cell.strip() for cell in row.split("\t") if cell.strip()]
                                    for row in text_block.split("\n")
                                    if row.strip()
                                ]
                                if len(rows) > 1 and all(len(r) > 1 for r in rows):
                                    doc.tables.append(rows)

                doc.text = "\n\n".join(pages_text)
                pdf.close()

            except ImportError:
                logger.warning("pymupdf_not_installed", fallback="pdfplumber")
                # Fallback: try pdfplumber
                try:
                    import pdfplumber

                    with pdfplumber.open(file_path) as pdf:
                        pages_text = []
                        for page in pdf.pages:
                            text = page.extract_text() or ""
                            pages_text.append(text)

                            tables = page.extract_tables()
                            doc.tables.extend(tables)

                        doc.text = "\n\n".join(pages_text)
                        doc.metadata = {"pages": len(pdf.pages), "parser": "pdfplumber"}

                except ImportError:
                    raise ImportError(
                        "MarkItDown, PyMuPDF (fitz) and pdfplumber are not installed. "
                        "Install one: pip install markitdown pymupdf pdfplumber"
                    )

    def _parse_docx(self, file_path: str, doc: ParsedDocument) -> None:
        """Parse DOCX using docx2txt."""
        try:
            import docx2txt

            doc.text = docx2txt.process(file_path)
            doc.metadata = {"file_type": "docx"}

        except ImportError:
            raise ImportError("docx2txt is not installed. Install: pip install docx2txt")

    def _parse_markdown(self, file_path: str, doc: ParsedDocument) -> None:
        """Parse Markdown file preserving structure."""
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            doc.text = f.read()

        doc.metadata = {"file_type": "markdown"}

        # Extract sections from Markdown headers
        current_section = None
        for line in doc.text.split("\n"):
            header_match = re.match(r"^(#{1,6})\s+(.+)", line)
            if header_match:
                level = len(header_match.group(1))
                title = header_match.group(2).strip()
                current_section = {
                    "title": title,
                    "level": level,
                    "content": [],
                }
                doc.sections.append(current_section)
            elif current_section is not None:
                content_list = current_section["content"]
                if isinstance(content_list, list):
                    content_list.append(line)

    def _parse_text(self, file_path: str, doc: ParsedDocument) -> None:
        """Parse plain text file."""
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            doc.text = f.read()
        doc.metadata = {"file_type": "text"}

    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text."""
        # Remove excessive whitespace
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        # Remove page break artifacts
        text = re.sub(r"\f", "\n\n", text)
        # Normalize Unicode spaces
        text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
        # Remove very long runs of dashes/underscores (section separators)
        text = re.sub(r"[-_=]{20,}", "---", text)
        return text.strip()

    def _extract_sections(self, text: str) -> List[Dict]:
        """
        Extract sections from text using common header patterns.
        
        Works for both Markdown and plain-text documents.
        """
        sections = []
        # Match Markdown headers
        header_pattern = re.compile(r"^(#{1,6})\s+(.+)", re.MULTILINE)
        # Match numbered headers (1. Introduction, 2.1 Requirements, etc.)
        numbered_pattern = re.compile(r"^(\d+(?:\.\d+)*)\s+([A-Z].+)", re.MULTILINE)
        # Match ALL-CAPS headers
        caps_pattern = re.compile(r"^([A-Z][A-Z\s]{5,})$", re.MULTILINE)

        # Try Markdown headers first
        matches = list(header_pattern.finditer(text))
        if not matches:
            matches = list(numbered_pattern.finditer(text))
        if not matches:
            matches = list(caps_pattern.finditer(text))

        for i, match in enumerate(matches):
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()

            if hasattr(match, "group") and match.lastindex and match.lastindex >= 2:
                title = match.group(2).strip()
                level_str = match.group(1)
                level = level_str.count("#") if "#" in level_str else level_str.count(".")
            else:
                title = match.group(0).strip()
                level = 1

            sections.append({
                "title": title,
                "level": max(1, level),
                "content": content,  # Limit removed to prevent data loss
            })

        return sections


class SemanticChunker:
    """
    Intelligent text chunking with semantic boundaries.

    Strategy (from architecture §2.3):
      1. Section-based chunking (headers, paragraphs)
      2. Sentence boundary detection
      3. Token-aware splitting (configurable chunk size)
      4. Overlap strategy (configurable overlap)
      5. Metadata preservation (section, chunk_index, position)
    """

    # Separators ordered from strongest to weakest boundary
    SEPARATORS = [
        "\n\n\n",   # Triple newline (major section break)
        "\n\n",      # Double newline (paragraph break)
        "\n",        # Single newline
        ". ",        # Sentence boundary
        "; ",        # Clause boundary
        ", ",        # Minor boundary
        " ",         # Word boundary
    ]

    def __init__(self, chunk_size: int = 3000, chunk_overlap: int = 400):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(self, doc: ParsedDocument) -> List[DocumentChunk]:
        """
        Chunk a parsed document into semantically meaningful pieces.

        Uses LangChain's MarkdownHeaderTextSplitter to preserve hierarchy,
        followed by RecursiveCharacterTextSplitter to enforce chunk sizes.
        """
        chunks = []

        try:
            from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

            headers_to_split_on = [
                ("#", "Header 1"),
                ("##", "Header 2"),
                ("###", "Header 3"),
                ("####", "Header 4"),
                ("#####", "Header 5"),
                ("######", "Header 6"),
            ]

            # Split by headers to preserve metadata
            md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
            md_splits = md_splitter.split_text(doc.text)

            # Split large chunks using character rules
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=self.SEPARATORS,
            )

            langchain_chunks = text_splitter.split_documents(md_splits)

            for i, chunk in enumerate(langchain_chunks):
                metadata = chunk.metadata.copy()
                metadata["source"] = os.path.basename(doc.source_file)
                metadata["file_type"] = doc.file_type
                metadata["chunk_size"] = len(chunk.page_content)
                metadata["position"] = "start" if i == 0 else "end" if i == len(langchain_chunks) - 1 else "middle"

                doc_chunk = DocumentChunk(
                    text=chunk.page_content,
                    chunk_index=i,
                    metadata=metadata
                )
                chunks.append(doc_chunk)

            doc.chunks = chunks

        except ImportError:
            logger.warning("langchain_text_splitters_missing", fallback="custom_chunker")
            if doc.sections:
                chunks = self._chunk_by_sections(doc)
            else:
                chunks = self._chunk_text(
                    doc.text,
                    metadata={
                        "source": os.path.basename(doc.source_file),
                        "file_type": doc.file_type,
                    },
                )
            doc.chunks = chunks

        logger.info(
            "document_chunked",
            source=os.path.basename(doc.source_file),
            total_chunks=len(chunks),
            avg_chunk_size=sum(c.token_estimate for c in chunks) // max(1, len(chunks)),
        )

        return chunks

    def _chunk_by_sections(self, doc: ParsedDocument) -> List[DocumentChunk]:
        """Chunk document respecting section boundaries."""
        chunks = []
        global_idx = 0

        for section in doc.sections:
            section_text = section["title"] + "\n\n"
            if isinstance(section["content"], list):
                section_text += "\n".join(section["content"])
            else:
                section_text += str(section["content"])

            section_chunks = self._chunk_text(
                section_text,
                metadata={
                    "source": os.path.basename(doc.source_file),
                    "section": section["title"],
                    "level": section["level"],
                },
                start_index=global_idx,
            )

            chunks.extend(section_chunks)
            global_idx += len(section_chunks)

        return chunks

    def _chunk_text(
        self,
        text: str,
        metadata: Optional[Dict] = None,
        start_index: int = 0,
    ) -> List[DocumentChunk]:
        """
        Split text into chunks using recursive character splitting.

        Uses the strongest available separator at each split point.
        """
        if not text.strip():
            return []

        raw_chunks = self._recursive_split(text, self.SEPARATORS)
        result = []

        for i, chunk_text in enumerate(raw_chunks):
            chunk = DocumentChunk(
                text=chunk_text.strip(),
                chunk_index=start_index + i,
                metadata={
                    **(metadata or {}),
                    "chunk_size": len(chunk_text),
                    "position": (
                        "start" if i == 0
                        else "end" if i == len(raw_chunks) - 1
                        else "middle"
                    ),
                },
            )
            if chunk.text:  # Skip empty chunks
                result.append(chunk)

        return result

    def _recursive_split(self, text: str, separators: List[str]) -> List[str]:
        """
        Recursively split text using separators from strongest to weakest.

        Tries the strongest separator first. If chunks are still too large,
        recursively splits them with the next-strongest separator.
        """
        if len(text) <= self.chunk_size:
            return [text]

        if not separators:
            # Last resort: hard split at chunk_size
            chunks = []
            for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                chunks.append(text[i : i + self.chunk_size])
            return chunks

        separator = separators[0]
        remaining_separators = separators[1:]

        parts = text.split(separator)
        chunks = []
        current = ""

        for part in parts:
            candidate = current + separator + part if current else part

            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                    # Overlap: keep end of current chunk
                    overlap = current[-self.chunk_overlap:] if self.chunk_overlap else ""
                    current = overlap + part if overlap else part
                else:
                    # Part itself is too large — split recursively
                    sub_chunks = self._recursive_split(part, remaining_separators)
                    chunks.extend(sub_chunks[:-1])
                    current = sub_chunks[-1] if sub_chunks else ""

        if current:
            chunks.append(current)

        return chunks
