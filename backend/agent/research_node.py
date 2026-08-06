"""
Research Node — the "brain" that learns HOW to code before coding begins.

This LangGraph node sits between PLAN and SETUP_ENVIRONMENT. It:
  1. Reads the project plan (tech stack, file list)
  2. Generates targeted web search queries
  3. Fetches real-time documentation and tutorials
  4. Synthesizes everything into a compact "coding guide"
  5. Passes the guide to the implement node via state

The result: the agent knows the EXACT scaffolding commands, project
structure, dependency versions, and best practices — not just what
its training data remembers.
"""
import json as _json
import asyncio

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

from .web_search import search_and_extract, generate_research_queries, search_web_cached
from .llm import LLMFactory
from .state import AgentState
from .context_manager import ContextManager, count_tokens
from core.logger import get_logger
from models.llm_profile import LLMProfile

logger = get_logger(__name__)



# ── Research synthesis prompt ──────────────────────────────────────────────

RESEARCH_SYNTHESIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a senior software architect. You've just searched the web
for the latest documentation on how to build a project. Your job is to
synthesize the search results into a CONCISE, ACTIONABLE coding guide.

CRITICAL: The coding guide MUST strictly align with the tech stack specified in the PROJECT PLAN.
- If the project plan specifies "html_css_js" or Vanilla JavaScript (no framework), DO NOT suggest React, Vue, TypeScript, or Vite. Provide instructions for a vanilla HTML/CSS/JS setup using a simple web server (e.g. `python3 -m http.server 3000`).
- If the project plan specifies a specific framework (React, Express, FastAPI, etc.), provide the exact scaffolding and dependencies for THAT stack.

Focus ONLY on:
1. EXACT scaffolding commands (if applicable)
2. Correct modern project file structure
3. Latest stable package versions and important dependencies
4. Configuration gotchas and known breaking changes (especially in 2026)
5. Dev server startup command and expected port
6. Quick code snippets for common errors mentioned in the search results

DO NOT include:
- General explanations of what React/Vue/etc. is
- Marketing language
- Deployment instructions
- Testing setup (unless asked)

Format your output as a structured reference sheet, not prose."""),

    ("human", """PROJECT PLAN:
{plan}

WEB SEARCH RESULTS:
{search_results}

Synthesize these into a compact coding guide. Include EXACT commands and file paths."""),
])


def _resolve_research_llm(state: AgentState):
    """Use a fast, cheap model for research synthesis."""
    factory = LLMFactory()
    profile_data = state.get("llm_profile")
    
    provider = None
    model_name = None
    if isinstance(profile_data, LLMProfile):
        provider = profile_data.provider
        model_name = profile_data.model
    elif isinstance(profile_data, dict):
        provider = profile_data.get("provider")
        model_name = profile_data.get("model")
        
    return factory.create(provider=provider, model_name=model_name, role="validator")  # Fast model for summarization


async def research_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Research how to build the project.

    Reads the plan, searches the web for latest docs, and produces
    a structured coding guide for the implement node.
    
    On re-plan (judge rejection), skips research if context already exists
    since the tech stack doesn't change between plan revisions.
    
    Phase 1.1 Updates:
    - Uses state_manager for safe state updates
    - Tracks research_findings
    - Logs state transitions
    - Token management integration (Task 1.2)
    """
    from .state_manager import merge_state_updates, log_state_transition
    
    old_status = state.get('status', 'research')
    session_id = state.get("session_id", "")
    
    # ── Token Management Initialization ─────────────────────────────────
    # llm_profile may be an LLMProfile object OR a dict — pydantic models
    # have no .get(), so the isinstance check MUST come first.
    profile_data = state.get('llm_profile')
    if isinstance(profile_data, LLMProfile):
        model_name = profile_data.model or 'unknown'
    elif isinstance(profile_data, dict):
        model_name = profile_data.get('model', 'unknown')
    else:
        model_name = 'unknown'
    
    ctx_manager = ContextManager(model=model_name)
    
    if state.get('chat_mode') == 'discuss':
        updates = {
            "research_context": "",
            "status": "setup_env",
            "messages": [],
            "token_count": 0,
            "context_budget": ctx_manager.budget.to_dict(),
            # Metrics: no tokens processed in discuss mode
            "total_tokens_processed": state.get('total_tokens_processed', 0),
            "max_token_count_reached": state.get('max_token_count_reached', 0),
        }
        new_state = merge_state_updates(state, updates)
        log_state_transition(session_id, old_status, 'setup_env', {'reason': 'discuss_mode'})
        return new_state

    plan_str = state.get("plan", "{}")

    # ── Skip research on re-plan if we already have context ────────────
    existing_research = state.get("research_context", "")
    if existing_research and len(existing_research) > 50:
        research_tokens = count_tokens(existing_research, model_name)
        logger.info(
            "research_skipped_replan",
            session_id=session_id,
            context_length=len(existing_research),
            context_tokens=research_tokens,
        )
        updates = {
            "research_context": existing_research,  # Reuse existing
            "status": "setup_env",
            "messages": [AIMessage(content="[Research] Reusing existing research (re-plan cycle).")],
            "token_count": research_tokens,
            "context_budget": ctx_manager.budget.to_dict(),
            # Metrics: reusing existing tokens, don't double-count
            "total_tokens_processed": state.get('total_tokens_processed', 0),
            "max_token_count_reached": max(
                state.get('max_token_count_reached', 0),
                research_tokens
            ),
        }
        new_state = merge_state_updates(state, updates)
        log_state_transition(session_id, old_status, 'setup_env', {'reason': 'reuse_existing'})
        return new_state

    # Parse the plan
    try:
        plan = _json.loads(plan_str)
    except _json.JSONDecodeError:
        logger.warning("research_plan_parse_failed", session_id=session_id)
        plan = {}

    # ── Step 1: Generate search queries ────────────────────────────────
    queries = generate_research_queries(plan)

    if not queries:
        logger.info("research_no_queries", session_id=session_id)
        fallback_msg = "No specific tech stack detected. Using general best practices."
        fallback_tokens = count_tokens(fallback_msg, model_name)
        updates = {
            "research_context": fallback_msg,
            "status": "setup_env",
            "messages": [AIMessage(content="[Research] No specific framework detected — using general practices.")],
            "token_count": fallback_tokens,
            "context_budget": ctx_manager.budget.to_dict(),
            # Metrics tracking
            "total_tokens_processed": state.get('total_tokens_processed', 0) + fallback_tokens,
            "max_token_count_reached": max(
                state.get('max_token_count_reached', 0),
                fallback_tokens
            ),
        }
        new_state = merge_state_updates(state, updates)
        log_state_transition(session_id, old_status, 'setup_env', {'reason': 'no_queries'})
        return new_state

    logger.info(
        "research_start",
        session_id=session_id,
        num_queries=len(queries),
        queries=queries,
    )

    # ── Step 2: Execute web searches (parallel for speed) ────────────────
    all_results = []

    async def _run_single_query(query: str) -> list[dict]:
        """Search + extract for one query, with fallback to cached search."""
        results = []
        try:
            response = await search_and_extract(
                query=query,
                max_results=2,
                max_content_chars=1500,
                fetch_content=True,
            )

            if response.error:
                logger.warning(
                    "research_search_error",
                    session_id=session_id,
                    query=query,
                    error=response.error,
                )
                # Fallback: try cached search without content extraction
                response = await search_web_cached(query, max_results=2)

            for result in response.results:
                results.append({
                    "query": query,
                    "title": result.title,
                    "url": result.url,
                    "snippet": result.snippet,
                    "content": result.content[:1000] if result.content else "",
                })

        except Exception as e:
            logger.error(
                "research_query_failed",
                session_id=session_id,
                query=query,
                error=str(e),
            )
        return results

    # Run all queries in parallel (3-5x faster than sequential)
    query_tasks = [_run_single_query(q) for q in queries]
    query_results = await asyncio.gather(*query_tasks, return_exceptions=True)
    for batch in query_results:
        if isinstance(batch, list):
            all_results.extend(batch)

    if not all_results:
        logger.warning("research_no_results", session_id=session_id)
        fallback_context = "Web search returned no results. Using LLM training knowledge."
        fallback_tokens = count_tokens(fallback_context, model_name)
        updates = {
            "research_context": fallback_context,
            "status": "setup_env",
            "messages": [AIMessage(content="[Research] Web search unavailable — using training knowledge.")],
            "token_count": fallback_tokens,
            "context_budget": ctx_manager.budget.to_dict(),
            # Metrics tracking
            "total_tokens_processed": state.get('total_tokens_processed', 0) + fallback_tokens,
            "max_token_count_reached": max(
                state.get('max_token_count_reached', 0),
                fallback_tokens
            ),
        }
        new_state = merge_state_updates(state, updates)
        log_state_transition(session_id, old_status, 'setup_env', {'reason': 'no_results'})
        return new_state

    # ── Step 3: Format search results for LLM ─────────────────────────
    formatted_results = []
    for i, r in enumerate(all_results, 1):
        entry = f"### Result {i}: {r['title']}\n"
        entry += f"URL: {r['url']}\n"
        entry += f"Query: {r['query']}\n"
        entry += f"Snippet: {r['snippet']}\n"
        if r["content"]:
            entry += f"Page Content:\n{r['content'][:1000]}\n"
        formatted_results.append(entry)

    search_text = "\n---\n".join(formatted_results)

    # ── Token Management: Truncate search text if too long ─────────────
    # Check if search text exceeds workspace context budget
    max_chars = ctx_manager.budget.workspace_context * 4  # ~4 chars per token
    if len(search_text) > max_chars:
        original_len = len(search_text)
        search_text = search_text[:max_chars]
        logger.info(
            "research_text_truncated",
            session_id=session_id,
            original_chars=original_len,
            truncated_to=max_chars,
        )
    
    # Count tokens in search text
    search_tokens = count_tokens(search_text, model_name)

    # ── Step 4: Synthesize with LLM ────────────────────────────────────
    try:
        llm = _resolve_research_llm(state)
        chain = RESEARCH_SYNTHESIS_PROMPT | llm

        # Small delay for rate limiting
        await asyncio.sleep(0.5)

        response = await chain.ainvoke({
            "plan": plan_str,
            "search_results": search_text,
        })

        research_context = response.content if isinstance(response.content, str) else str(response.content)

        # Count tokens in synthesized research context
        research_context_tokens = count_tokens(research_context, model_name)

        logger.info(
            "research_complete",
            session_id=session_id,
            context_length=len(research_context),
            context_tokens=research_context_tokens,
            search_tokens=search_tokens,
            num_results=len(all_results),
        )

    except Exception as e:
        # If LLM synthesis fails, use raw search results as fallback
        logger.error("research_synthesis_failed", session_id=session_id, error=str(e))
        research_context = f"Raw search findings:\n\n"
        for r in all_results[:5]:
            research_context += f"- {r['title']}: {r['snippet']}\n"
        
        # Count tokens for fallback context
        research_context_tokens = count_tokens(research_context, model_name)

    # Build research findings list
    research_findings = []
    for r in all_results[:10]:
        research_findings.append({
            'title': r['title'],
            'url': r['url'],
            'query': r['query']
        })

    # Calculate total token count (search + research context)
    total_tokens = search_tokens + research_context_tokens

    # ── Task 3.3: Track token metrics ──────────────────────────────────
    updates = {
        "research_context": research_context,
        "status": "setup_env",
        "messages": [AIMessage(content=f"[Research Complete]\n{research_context}")],
        "research_findings": research_findings,
        "needs_research": False,
        "token_count": total_tokens,
        "context_budget": ctx_manager.budget.to_dict(),
        # Metrics tracking (Requirements 5.1, 5.4, 5.5)
        "total_tokens_processed": state.get('total_tokens_processed', 0) + total_tokens,
        "max_token_count_reached": max(
            state.get('max_token_count_reached', 0),
            total_tokens
        ),
    }
    
    # Note: research_node doesn't use message pruning, so no pruning events to track
    # Note: research_node truncates search text but doesn't trigger overflow handling
    
    new_state = merge_state_updates(state, updates)
    log_state_transition(session_id, old_status, 'setup_env', {
        'num_queries': len(queries),
        'num_results': len(all_results),
        'total_tokens': total_tokens,
    })
    return new_state


async def search_for_error(error_message: str, tech_context: str = "") -> str:
    """
    Mini-research function: search the web for how to fix a specific error.

    Called from the implement node when it encounters an unknown error
    and emits a <search> action.

    Args:
        error_message: The error message to research
        tech_context: Optional tech stack context (e.g., "react vite typescript")

    Returns:
        Compact fix instructions as a string
    """
    # Clean up the error message for a better search query
    clean_error = error_message.strip()
    # Remove file paths and line numbers for a more generic search
    clean_error = clean_error.split("\n")[0][:150]

    query = f"{tech_context} fix error: {clean_error}".strip()

    try:
        response = await search_and_extract(
            query=query,
            max_results=3,
            max_content_chars=2000,
            fetch_content=True,
        )

        if not response.results:
            return f"No search results found for: {clean_error}"

        # Build a compact fix guide from results
        fix_guide = f"Web search results for error: {clean_error}\n\n"
        for r in response.results:
            fix_guide += f"**{r.title}** ({r.url})\n"
            fix_guide += f"{r.snippet}\n"
            if r.content:
                # Extract just the most relevant part
                fix_guide += f"Details: {r.content[:500]}\n"
            fix_guide += "\n"

        return fix_guide[:3000]

    except Exception as e:
        logger.error("search_for_error_failed", error=str(e))
        return f"Error search failed: {e}"
