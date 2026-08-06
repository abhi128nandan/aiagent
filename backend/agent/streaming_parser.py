"""
Streaming Message Parser — character-by-character action detection.

Inspired by bolt.diy's StreamingMessageParser, adapted for myaiagent's
XML format (<write>, <run>, <search>, <finish>).

Emits events as actions are discovered in the streaming LLM output:
  - action_open:  a new action tag was detected (e.g. <write path="...">)
  - action_chunk: partial content inside an action body
  - action_close: closing tag detected, full content available
  - text_chunk:   plain text between actions
"""

from __future__ import annotations

import re
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Generator


class ParserState(Enum):
    IDLE = auto()       # Looking for '<' to start a tag
    TAG_OPEN = auto()   # Reading opening tag name
    TAG_ATTRS = auto()  # Reading tag attributes (e.g. path="...")
    TAG_BODY = auto()   # Accumulating content until closing tag
    TAG_CLOSE = auto()  # Detected '</' — reading closing tag name


# The set of action tag names we recognize
KNOWN_TAGS = frozenset({"write", "run", "search", "finish"})

# Regex to extract path from <write> tag attributes
_PATH_RE = re.compile(
    r"""path\s*=\s*(?:['"]([^'"]*?)['"]|(\S+))""",
    re.IGNORECASE,
)


@dataclass
class ParserEvent:
    """A single event emitted by the streaming parser."""
    kind: str           # "action_open", "action_chunk", "action_close", "text_chunk"
    action: str = ""    # "write", "run", "search", "finish", or "" for text_chunk
    path: str = ""      # file path (only for write actions)
    content: str = ""   # content payload
    command: str = ""   # command string (for run actions)
    query: str = ""     # search query (for search actions)
    message: str = ""   # finish message


@dataclass
class StreamingMessageParser:
    """
    Character-by-character streaming parser for LLM action tags.

    Usage:
        parser = StreamingMessageParser()
        for chunk in llm_stream:
            for event in parser.feed(chunk):
                handle(event)
        # Flush any remaining content
        for event in parser.flush():
            handle(event)
    """
    state: ParserState = field(default=ParserState.IDLE)
    
    # Buffers
    _tag_buffer: str = ""         # Accumulates tag name being read
    _attr_buffer: str = ""        # Accumulates attributes being read
    _body_buffer: str = ""        # Accumulates action body content
    _close_buffer: str = ""       # Accumulates closing tag name
    _text_buffer: str = ""        # Accumulates plain text between actions
    _lt_pending: bool = False     # We saw '<' but don't know if it's a tag yet
    
    # Current action context
    _current_tag: str = ""        # Name of the currently open action tag
    _current_path: str = ""       # Path attribute (for write tags)
    
    # Chunk batching for performance
    _chunk_size: int = 0          # Chars accumulated since last action_chunk emit
    _chunk_threshold: int = 20    # Emit action_chunk every N chars (tunable)

    def feed(self, text: str) -> Generator[ParserEvent, None, None]:
        """
        Feed a chunk of text into the parser.
        Yields ParserEvent objects as actions are discovered.
        """
        for char in text:
            yield from self._process_char(char)

    def flush(self) -> Generator[ParserEvent, None, None]:
        """Flush any remaining buffered content at end of stream."""
        if self.state == ParserState.TAG_BODY and self._current_tag:
            # Unclosed tag — emit what we have as a complete action
            yield self._make_action_close()
        elif self._text_buffer:
            yield ParserEvent(kind="text_chunk", content=self._text_buffer)
            self._text_buffer = ""
        
        # Handle any pending lt
        if self._lt_pending:
            self._text_buffer += "<"
            self._lt_pending = False
            if self._text_buffer:
                yield ParserEvent(kind="text_chunk", content=self._text_buffer)
                self._text_buffer = ""

    def reset(self):
        """Reset parser to initial state."""
        self.state = ParserState.IDLE
        self._tag_buffer = ""
        self._attr_buffer = ""
        self._body_buffer = ""
        self._close_buffer = ""
        self._text_buffer = ""
        self._lt_pending = False
        self._current_tag = ""
        self._current_path = ""
        self._chunk_size = 0

    def _process_char(self, char: str) -> Generator[ParserEvent, None, None]:
        """Process a single character through the state machine."""

        if self.state == ParserState.IDLE:
            yield from self._handle_idle(char)

        elif self.state == ParserState.TAG_OPEN:
            yield from self._handle_tag_open(char)

        elif self.state == ParserState.TAG_ATTRS:
            yield from self._handle_tag_attrs(char)

        elif self.state == ParserState.TAG_BODY:
            yield from self._handle_tag_body(char)

        elif self.state == ParserState.TAG_CLOSE:
            yield from self._handle_tag_close(char)

    # ── State handlers ──────────────────────────────────────────────────

    def _handle_idle(self, char: str) -> Generator[ParserEvent, None, None]:
        """IDLE state — looking for '<' to start a potential tag."""
        if char == "<":
            self._lt_pending = True
            self._tag_buffer = ""
            self.state = ParserState.TAG_OPEN
        else:
            self._text_buffer += char
        return
        yield  # make this a generator

    def _handle_tag_open(self, char: str) -> Generator[ParserEvent, None, None]:
        """TAG_OPEN — reading the tag name after '<'."""
        if char == " " or char == "\t":
            # Space after tag name — check if it's a known tag
            tag_name = self._tag_buffer.strip().lower()
            if tag_name in KNOWN_TAGS:
                self._current_tag = tag_name
                self._attr_buffer = ""
                self.state = ParserState.TAG_ATTRS
                # Flush any pending text
                if self._text_buffer:
                    yield ParserEvent(kind="text_chunk", content=self._text_buffer)
                    self._text_buffer = ""
                self._lt_pending = False
            else:
                # Not a known tag — dump everything as text
                self._text_buffer += "<" + self._tag_buffer + char
                self._lt_pending = False
                self._tag_buffer = ""
                self.state = ParserState.IDLE
        elif char == ">":
            # Tag closed immediately (e.g. <run>)
            tag_name = self._tag_buffer.strip().lower()
            if tag_name in KNOWN_TAGS:
                self._current_tag = tag_name
                self._current_path = ""
                # Flush text
                if self._text_buffer:
                    yield ParserEvent(kind="text_chunk", content=self._text_buffer)
                    self._text_buffer = ""
                self._lt_pending = False
                yield self._make_action_open()
                self._body_buffer = ""
                self._chunk_size = 0
                self.state = ParserState.TAG_BODY
            else:
                # Not a known tag — treat as text
                self._text_buffer += "<" + self._tag_buffer + ">"
                self._lt_pending = False
                self._tag_buffer = ""
                self.state = ParserState.IDLE
        elif char == "/" and not self._tag_buffer:
            # This is a closing tag like </write> — not an opening tag.
            # Push everything back as text
            self._text_buffer += "</"
            self._lt_pending = False
            self._tag_buffer = ""
            self.state = ParserState.IDLE
        elif char.isalnum() or char == "_":
            self._tag_buffer += char
        else:
            # Unexpected character — not a valid tag
            self._text_buffer += "<" + self._tag_buffer + char
            self._lt_pending = False
            self._tag_buffer = ""
            self.state = ParserState.IDLE
        return
        yield  # make this a generator

    def _handle_tag_attrs(self, char: str) -> Generator[ParserEvent, None, None]:
        """TAG_ATTRS — reading attributes until '>'."""
        if char == ">":
            # Parse attributes to extract path (for write tags)
            self._current_path = ""
            if self._current_tag == "write":
                path_match = _PATH_RE.search(self._attr_buffer)
                if path_match:
                    self._current_path = (path_match.group(1) or path_match.group(2) or "").strip()
            
            yield self._make_action_open()
            self._body_buffer = ""
            self._chunk_size = 0
            self.state = ParserState.TAG_BODY
        else:
            self._attr_buffer += char
        return
        yield  # make this a generator

    def _handle_tag_body(self, char: str) -> Generator[ParserEvent, None, None]:
        """TAG_BODY — accumulating content until we see '</'."""
        if char == "<":
            # Might be start of closing tag
            self._lt_pending = True
            self._close_buffer = ""
            self.state = ParserState.TAG_CLOSE
        else:
            self._body_buffer += char
            self._chunk_size += 1
            
            # Emit periodic action_chunk events for streaming preview
            if self._chunk_size >= self._chunk_threshold:
                yield self._make_action_chunk()
                self._chunk_size = 0
        return
        yield  # make this a generator

    def _handle_tag_close(self, char: str) -> Generator[ParserEvent, None, None]:
        """TAG_CLOSE — we saw '<' inside a body, checking if it's '</tagname>'."""
        if char == "/":
            if not self._close_buffer:
                # This is '</' — legitimate start of closing tag
                self._close_buffer = "/"
            else:
                # Weird — not a closing tag, push back
                self._body_buffer += "<" + self._close_buffer + char
                self._chunk_size += len(self._close_buffer) + 2
                self._lt_pending = False
                self._close_buffer = ""
                self.state = ParserState.TAG_BODY
        elif char == ">":
            # End of potential closing tag
            close_tag = self._close_buffer.lstrip("/").strip().lower()
            if close_tag == self._current_tag:
                # Valid closing tag! Emit remaining chunk + action_close
                self._lt_pending = False
                if self._chunk_size > 0:
                    yield self._make_action_chunk()
                yield self._make_action_close()
                self._current_tag = ""
                self._current_path = ""
                self._body_buffer = ""
                self._close_buffer = ""
                self.state = ParserState.IDLE
            else:
                # Not our closing tag — this '<...>' is part of body content
                # (e.g. JSX <div> inside a <write> body)
                self._body_buffer += "<" + self._close_buffer + ">"
                self._chunk_size += len(self._close_buffer) + 2
                self._lt_pending = False
                self._close_buffer = ""
                self.state = ParserState.TAG_BODY
        elif char == " " and self._close_buffer == "/":
            # Whitespace after '/' in closing tag — '</  write>'
            self._close_buffer += char
        elif char.isalnum() or char == "_":
            self._close_buffer += char
        else:
            # Not a valid closing tag char — push everything back to body
            self._body_buffer += "<" + self._close_buffer + char
            self._chunk_size += len(self._close_buffer) + 2
            self._lt_pending = False
            self._close_buffer = ""
            self.state = ParserState.TAG_BODY
        return
        yield  # make this a generator

    # ── Event constructors ──────────────────────────────────────────────

    def _make_action_open(self) -> ParserEvent:
        """Create an action_open event."""
        return ParserEvent(
            kind="action_open",
            action=self._current_tag,
            path=self._current_path,
        )

    def _make_action_chunk(self) -> ParserEvent:
        """Create an action_chunk event with current body content."""
        return ParserEvent(
            kind="action_chunk",
            action=self._current_tag,
            path=self._current_path,
            content=self._body_buffer,
        )

    def _make_action_close(self) -> ParserEvent:
        """Create an action_close event with full body content."""
        content = self._body_buffer.strip()
        event = ParserEvent(
            kind="action_close",
            action=self._current_tag,
            path=self._current_path,
            content=content,
        )
        
        # Set convenience fields based on action type
        if self._current_tag == "run":
            event.command = content
        elif self._current_tag == "search":
            event.query = content
        elif self._current_tag == "finish":
            event.message = content
        
        return event
