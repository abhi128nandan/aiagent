# Feature: Web Research Engine

## Status
complete

## Goal
Empower the agent to autonomously search the web for documentation, tutorials, and recent framework updates before attempting to write code for unfamiliar stacks.

## Components
- `backend/agent/web_search.py` — DuckDuckGo / Google Search API integration.
- `backend/agent/research_node.py` — LangGraph node that decides if a search is needed based on the plan.

## Architecture Flow
```mermaid
sequenceDiagram
    participant Planner
    participant ResearchNode
    participant WebSearch
    
    Planner->>ResearchNode: Pass Plan & Context
    ResearchNode->>ResearchNode: Does context cover the required tech stack?
    alt Context is insufficient
        ResearchNode->>WebSearch: Generate 2-3 specific search queries
        WebSearch-->>ResearchNode: Return top URLs
        ResearchNode->>WebSearch: Scrape contents of top URLs
        WebSearch-->>ResearchNode: Return markdown content
        ResearchNode->>Planner: Inject researched knowledge into environment
    else Context is sufficient
        ResearchNode->>Planner: Skip search (Save tokens)
    end
```

## Features
- **Auto-Skipping:** Analyzes existing workspace context. If the project already has boilerplate or known tech, it skips web searches to save time and tokens.
- **Concurrent Fetching:** Uses `asyncio.gather` to scrape multiple URLs simultaneously.
- **Markdown Conversion:** Uses `BeautifulSoup` to strip raw HTML and extract readable text from documentation sites.

## Change Log
- 2026-06-10: Retrospectively documented.
