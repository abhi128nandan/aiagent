"""
Web Search Engine — gives the AI agent access to real-time web knowledge.

Uses DuckDuckGo (free, no API key) for searching, and httpx + html2text
for extracting clean markdown from documentation pages.

This module powers the Research node so the agent knows:
  - Latest scaffolding commands (e.g., npm create vite@latest)
  - Current package versions and best practices
  - Framework-specific project structures
  - How to fix errors it hasn't seen in training data
"""
import asyncio
import hashlib
import re
import time
from typing import Optional
from dataclasses import dataclass, field

from core.logger import get_logger

logger = get_logger(__name__)

# Rate limiting: max 1 search per second to avoid bans
_last_search_time: float = 0
_SEARCH_COOLDOWN = 1.0  # seconds

# ── Search result cache (survives across node calls within a process) ──
_search_cache: dict[str, tuple[float, 'SearchResponse']] = {}
_CACHE_TTL = 600  # 10 minutes — tech docs don't change that fast


@dataclass
class SearchResult:
    """A single search result with optional page content."""
    title: str
    url: str
    snippet: str
    content: str = ""  # Full page content (markdown), filled by fetch_page_content


@dataclass
class SearchResponse:
    """Collection of search results for a query."""
    query: str
    results: list[SearchResult] = field(default_factory=list)
    error: str = ""


async def search_web(query: str, max_results: int = 5) -> SearchResponse:
    """
    Search the web using DuckDuckGo (no API key needed).

    Args:
        query: The search query string
        max_results: Maximum number of results to return

    Returns:
        SearchResponse with results and optional error
    """
    global _last_search_time

    # Rate limiting
    now = asyncio.get_event_loop().time()
    elapsed = now - _last_search_time
    if elapsed < _SEARCH_COOLDOWN:
        await asyncio.sleep(_SEARCH_COOLDOWN - elapsed)
    _last_search_time = asyncio.get_event_loop().time()

    try:
        from ddgs import DDGS

        loop = asyncio.get_event_loop()

        def _search():
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(query, max_results=max_results))
                return raw_results

        raw_results = await loop.run_in_executor(None, _search)

        results = []
        for r in raw_results:
            results.append(SearchResult(
                title=r.get("title", ""),
                url=r.get("href", r.get("link", "")),
                snippet=r.get("body", r.get("snippet", "")),
            ))

        logger.info("web_search_ok", query=query, results=len(results))
        return SearchResponse(query=query, results=results)

    except ImportError:
        logger.error("web_search_import_error", detail="duckduckgo-search not installed")
        return SearchResponse(
            query=query,
            error="duckduckgo-search package not installed. Run: pip install duckduckgo-search"
        )
    except Exception as e:
        logger.error("web_search_failed", query=query, error=str(e))
        return SearchResponse(query=query, error=str(e))


async def search_web_cached(query: str, max_results: int = 5) -> SearchResponse:
    """
    Cached wrapper around search_web. Avoids redundant network calls
    when the same query is issued within the TTL window (e.g. on re-plan).
    """
    cache_key = hashlib.md5(f"{query.lower().strip()}:{max_results}".encode()).hexdigest()
    now = time.time()

    if cache_key in _search_cache:
        cached_time, cached_response = _search_cache[cache_key]
        if now - cached_time < _CACHE_TTL:
            logger.info("search_cache_hit", query=query[:80])
            return cached_response

    result = await search_web(query, max_results)
    if not result.error:
        _search_cache[cache_key] = (now, result)
    return result


async def fetch_page_content(url: str, max_chars: int = 8000) -> str:
    """
    Fetch a web page and convert to clean markdown.

    Args:
        url: The URL to fetch
        max_chars: Maximum characters to return (to fit in LLM context)

    Returns:
        Clean markdown text of the page content
    """
    try:
        import httpx
        import html2text

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AIAgent/1.0)"}
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text

        # Convert HTML to clean markdown
        converter = html2text.HTML2Text()
        converter.ignore_links = False
        converter.ignore_images = True
        converter.ignore_emphasis = False
        converter.body_width = 0  # Don't wrap lines
        converter.skip_internal_links = True

        markdown = converter.handle(html)

        # Clean up excessive whitespace
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)
        markdown = markdown.strip()

        # Truncate to max_chars
        if len(markdown) > max_chars:
            markdown = markdown[:max_chars] + "\n\n... [truncated]"

        logger.info("page_fetch_ok", url=url, chars=len(markdown))
        return markdown

    except ImportError as e:
        logger.error("page_fetch_import_error", url=url, detail=str(e))
        return f"[Error: Missing dependency — {e}]"
    except Exception as e:
        logger.error("page_fetch_failed", url=url, error=str(e))
        return f"[Error fetching {url}: {e}]"


async def search_and_extract(
    query: str,
    max_results: int = 3,
    max_content_chars: int = 4000,
    fetch_content: bool = True,
) -> SearchResponse:
    """
    Search the web AND extract content from top results.

    This is the main entry point for the research node. It:
    1. Searches DuckDuckGo for the query
    2. Fetches full page content from the top results
    3. Returns everything in a structured format

    Args:
        query: Search query
        max_results: Number of results to return
        max_content_chars: Max chars per page content
        fetch_content: Whether to also fetch full page content

    Returns:
        SearchResponse with results (including page content if fetch_content=True)
    """
    response = await search_web(query, max_results=max_results)

    if response.error or not response.results:
        return response

    if not fetch_content:
        return response

    # Fetch content from top results in parallel
    tasks = []
    for result in response.results[:max_results]:
        if result.url:
            tasks.append(fetch_page_content(result.url, max_chars=max_content_chars))
        else:
            async def _empty(): return ""
            tasks.append(_empty())

    contents = await asyncio.gather(*tasks, return_exceptions=True)

    for result, content in zip(response.results, contents):
        if isinstance(content, str):
            result.content = content
        else:
            result.content = f"[Error: {content}]"

    return response


def generate_research_queries(plan_json: dict) -> list[str]:
    """
    Generate targeted search queries based on the project plan.

    Analyzes the tech stack, project type, and file list to produce
    queries that will return the most useful scaffolding and coding info.

    Args:
        plan_json: The parsed project plan dict

    Returns:
        List of search query strings (typically 3-5 queries)
    """
    queries = []

    tech_stack = plan_json.get("tech_stack", {})
    frontend = tech_stack.get("frontend", "none")
    backend = tech_stack.get("backend", "none")
    database = tech_stack.get("database", "none")
    language = tech_stack.get("language", "javascript")
    project_name = plan_json.get("project", "")
    description = plan_json.get("description", "")

    # ── 1. Scaffolding / project creation query ────────────────────────
    scaffold_parts = []
    if frontend == "react":
        scaffold_parts.append("npm create vite react")
        if language == "typescript":
            scaffold_parts.append("typescript template")
        queries.append(f"npm create vite@latest react {language} project setup 2026")
    elif frontend == "vue":
        queries.append(f"npm create vite@latest vue {language} project setup 2026")
    elif frontend == "angular":
        queries.append(f"npx @angular/cli new project setup 2026")
    elif frontend == "svelte":
        queries.append(f"npm create vite@latest svelte {language} setup 2026")
    elif frontend == "next":
        queries.append(f"npx create-next-app@latest {language} setup 2026")

    # ── 2. Backend framework setup ────────────────────────────────────
    if backend == "express":
        queries.append(f"express.js {language} project structure best practices 2026")
    elif backend == "fastapi":
        queries.append("fastapi project structure with uvicorn setup 2026")
    elif backend == "flask":
        queries.append("flask python project structure setup 2026")
    elif backend == "spring_boot":
        queries.append("spring boot project setup gradle maven 2026")
    elif backend == "django":
        queries.append("django project setup structure 2026")

    # ── 3. Database integration ───────────────────────────────────────
    if database != "none":
        if frontend != "none" and backend != "none":
            queries.append(f"{backend} {database} integration setup {language}")
        elif backend != "none":
            queries.append(f"{backend} {database} connection setup")

    # ── 4. Full-stack combination (if both frontend + backend) ────────
    if frontend != "none" and backend != "none":
        queries.append(
            f"{frontend} {backend} full-stack project structure {language} 2026"
        )

    # ── 5. Project-specific query based on description ────────────────
    if description and len(description) > 10:
        # Extract key terms from description
        desc_query = f"{frontend if frontend != 'none' else ''} {description[:60]} tutorial"
        queries.append(desc_query.strip())

    # ── 6. Fallback: If no framework was detected, search generically ─
    if not queries:
        if language:
            queries.append(f"{language} web application project setup 2026")
        else:
            queries.append("web application project setup best practices 2026")

    # Deduplicate and limit
    seen = set()
    unique_queries = []
    for q in queries:
        q_normalized = q.strip().lower()
        if q_normalized not in seen:
            seen.add(q_normalized)
            unique_queries.append(q.strip())

    return unique_queries[:3]  # Max 3 targeted queries — less is more, saves tokens
