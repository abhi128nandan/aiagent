"""
Context Overflow Handling — strategies for extreme context overflow scenarios.

This module provides multiple strategies for handling situations where standard
message pruning cannot reduce context below the model's token budget. These are
last-resort mechanisms that activate when normal pruning fails.

Architecture:
  - Three-tiered strategy hierarchy: aggressive_prune → summarize_all → truncate_hard
  - Ultra-compact summarization that extracts only key facts (10-20% of original tokens)
  - Hard truncation that distributes budget evenly across messages
  - Preserves critical context (first + last messages) when possible

Usage:
    from agent.overflow_handler import handle_overflow, ContextOverflowError
    
    # When standard pruning fails
    try:
        pruned = handle_overflow(
            messages=long_message_list,
            budget=ctx_manager.budget.available_for_conversation,
            strategy="aggressive_prune"
        )
    except ContextOverflowError as e:
        logger.critical("context_overflow_unrecoverable", error=str(e))
"""
from __future__ import annotations

import re
from typing import List, Literal

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

from core.logger import get_logger
from agent.context_manager import count_tokens, count_message_tokens

logger = get_logger(__name__)


# ── Exception Definitions ──────────────────────────────────────────────

class ContextOverflowError(Exception):
    """
    Raised when context cannot be pruned enough to fit within budget.
    
    This indicates an unrecoverable overflow situation where even hard
    truncation strategies cannot reduce the context to fit the model's limits.
    """
    pass


# ── Strategy Type Definition ───────────────────────────────────────────

OverflowStrategy = Literal["aggressive_prune", "summarize_all", "truncate_hard"]


# ── Main Overflow Handler ──────────────────────────────────────────────

def handle_overflow(
    messages: List[BaseMessage],
    budget: int,
    *,
    strategy: OverflowStrategy = "aggressive_prune"
) -> List[BaseMessage]:
    """
    Handle context overflow with multiple fallback strategies.
    
    This function is called when standard pruning cannot reduce messages to fit
    within the token budget. It provides three increasingly aggressive strategies:
    
    1. **aggressive_prune**: Keep only first 1 + last 3 messages, summarize middle
       - Used when: Standard pruning fails but messages are separable
       - Preserves: First message (original request) + last 3 messages (recent context)
       - Reduces: Middle messages to ultra-compact summary
    
    2. **summarize_all**: Compress entire conversation to single summary message
       - Used when: Aggressive pruning still exceeds budget
       - Preserves: Key facts extracted from all messages
       - Reduces: Everything to one SystemMessage
    
    3. **truncate_hard**: Cut individual message content character by character
       - Used when: Even summary exceeds budget (extremely long individual messages)
       - Preserves: Message structure and types
       - Reduces: Each message content proportionally
    
    Args:
        messages: List of conversation messages to handle overflow for
        budget: Token budget that result must fit within
        strategy: Which overflow strategy to apply
    
    Returns:
        Pruned message list that fits within budget
    
    Raises:
        ContextOverflowError: If even hard truncation cannot fit within budget
                             (extremely rare, indicates budget is too small)
    
    Examples:
        >>> # Standard overflow handling
        >>> messages = [SystemMessage(...), HumanMessage(...), ...]  # 50 messages
        >>> pruned = handle_overflow(messages, budget=2000, strategy="aggressive_prune")
        >>> len(pruned)  # Will be 5: first + summary + last 3
        5
        
        >>> # Extreme case requiring hard truncation
        >>> large_messages = [HumanMessage(content="x" * 100000)]
        >>> pruned = handle_overflow(large_messages, budget=500, strategy="truncate_hard")
        >>> count_message_tokens(pruned) <= 500
        True
    """
    logger.warning(
        "overflow_handling_triggered",
        strategy=strategy,
        original_messages=len(messages),
        original_tokens=count_message_tokens(messages),
        budget=budget
    )
    
    if strategy == "aggressive_prune":
        return _aggressive_prune(messages, budget)
    
    elif strategy == "summarize_all":
        return _summarize_all(messages, budget)
    
    elif strategy == "truncate_hard":
        return _truncate_hard(messages, budget)
    
    else:
        raise ValueError(f"Unknown overflow strategy: {strategy}")


# ── Strategy Implementations ───────────────────────────────────────────

def _aggressive_prune(messages: List[BaseMessage], budget: int) -> List[BaseMessage]:
    """
    Aggressive pruning: Keep only first 1 + last 3 messages, summarize middle.
    
    This strategy preserves the most critical context while drastically reducing
    token count. The first message typically contains the original user request
    or system prompt, and the last 3 messages contain the most recent context.
    
    Strategy:
        1. Check if we can split into first/middle/last (need at least 5 messages)
        2. Extract first message and last 3 messages
        3. Create ultra-compact summary of middle messages
        4. Combine: [first, summary, last_3]
        5. If still too large, fall back to hard truncation
    
    Args:
        messages: List of messages to prune
        budget: Token budget to fit within
    
    Returns:
        Pruned message list with first + summary + last 3
    """
    if len(messages) <= 4:
        # Can't split into first/middle/last with fewer than 5 messages
        logger.info(
            "aggressive_prune_insufficient_messages",
            message_count=len(messages),
            fallback="truncate_hard"
        )
        return _truncate_hard(messages, budget)
    
    # Split messages
    first = messages[0]
    last_three = messages[-3:]
    omitted = messages[1:-3]
    
    # Create ultra-compact summary
    summary_text = _create_ultra_compact_summary(omitted)
    summary_msg = SystemMessage(
        content=f"[OVERFLOW HANDLING: {len(omitted)} messages compressed]\n{summary_text}"
    )
    
    # Construct pruned list
    result = [first, summary_msg] + last_three
    
    # Verify it fits
    result_tokens = count_message_tokens(result)
    if result_tokens <= budget:
        logger.info(
            "aggressive_prune_success",
            original_messages=len(messages),
            pruned_messages=len(result),
            original_tokens=count_message_tokens(messages),
            pruned_tokens=result_tokens,
            reduction_pct=round((1 - result_tokens/count_message_tokens(messages)) * 100, 1)
        )
        return result
    else:
        # Still too large — fall back to hard truncation
        logger.warning(
            "aggressive_prune_still_over_budget",
            result_tokens=result_tokens,
            budget=budget,
            fallback="truncate_hard"
        )
        return _truncate_hard(result, budget)


def _summarize_all(messages: List[BaseMessage], budget: int) -> List[BaseMessage]:
    """
    Summarize entire conversation to single SystemMessage.
    
    This is a middle-ground strategy that compresses all messages into a single
    ultra-compact summary. Used when aggressive pruning doesn't reduce enough
    but we still want to preserve some context information.
    
    Args:
        messages: List of messages to summarize
        budget: Token budget to fit within
    
    Returns:
        Single SystemMessage with ultra-compact summary
    """
    summary_text = _create_ultra_compact_summary(messages)
    summary_msg = SystemMessage(
        content=f"[OVERFLOW HANDLING: All {len(messages)} messages summarized]\n{summary_text}"
    )
    
    result = [summary_msg]
    result_tokens = count_message_tokens(result)
    
    if result_tokens <= budget:
        logger.info(
            "summarize_all_success",
            original_messages=len(messages),
            original_tokens=count_message_tokens(messages),
            summary_tokens=result_tokens,
            reduction_pct=round((1 - result_tokens/count_message_tokens(messages)) * 100, 1)
        )
        return result
    else:
        # Even summary is too large — truncate it
        logger.warning(
            "summarize_all_still_over_budget",
            summary_tokens=result_tokens,
            budget=budget,
            fallback="truncate_hard"
        )
        return _truncate_hard(result, budget)


def _truncate_hard(messages: List[BaseMessage], budget: int) -> List[BaseMessage]:
    """
    Last resort: Truncate individual message content to fit budget.
    
    This strategy distributes the available token budget evenly across all messages
    and truncates each message's content to fit within its allocation. This is the
    most aggressive strategy and may result in incomplete information, but ensures
    the context fits within the model's limits.
    
    Strategy:
        1. Distribute budget evenly: tokens_per_message = budget / message_count
        2. Convert to characters: max_chars = tokens_per_message * 4
        3. Truncate each message to max_chars
        4. Preserve message types (Human, AI, System)
        5. Add truncation indicator to truncated messages
    
    Args:
        messages: List of messages to truncate
        budget: Token budget to fit within
    
    Returns:
        List of truncated messages that fit within budget
    
    Note:
        This strategy should rarely be needed. If it's being called frequently,
        consider increasing the model's context window or implementing better
        conversation management (e.g., session splitting).
    """
    if not messages:
        return []
    
    # Calculate budget per message
    tokens_per_msg = budget // len(messages)
    max_chars = max(100, tokens_per_msg * 4)  # At least 100 chars per message, ~4 chars per token
    
    truncated = []
    for msg in messages:
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        
        if len(content) > max_chars:
            content = content[:max_chars] + "\n...[truncated due to context limit]"
        
        # Preserve message type
        if isinstance(msg, HumanMessage):
            truncated.append(HumanMessage(content=content))
        elif isinstance(msg, AIMessage):
            truncated.append(AIMessage(content=content))
        elif isinstance(msg, SystemMessage):
            truncated.append(SystemMessage(content=content))
        else:
            # Unknown message type — preserve as-is but with truncated content
            truncated.append(msg.__class__(content=content))
    
    result_tokens = count_message_tokens(truncated)
    
    logger.info(
        "truncate_hard_complete",
        original_messages=len(messages),
        original_tokens=count_message_tokens(messages),
        truncated_tokens=result_tokens,
        max_chars_per_message=max_chars,
        reduction_pct=round((1 - result_tokens/count_message_tokens(messages)) * 100, 1)
    )
    
    # Verify we actually fit (should always be true with hard truncation)
    if result_tokens > budget:
        logger.critical(
            "truncate_hard_still_exceeds_budget",
            result_tokens=result_tokens,
            budget=budget,
            error_msg="This should not happen — hard truncation failed"
        )
        raise ContextOverflowError(
            f"Cannot fit messages within budget even after hard truncation. "
            f"Result: {result_tokens} tokens, Budget: {budget} tokens. "
            f"Consider increasing model context window or reducing message count."
        )
    
    return truncated


# ── Summary Creation ───────────────────────────────────────────────────

def _create_ultra_compact_summary(messages: List[BaseMessage]) -> str:
    """
    Create a very compact summary focusing on key facts only.
    
    This function extracts structural information from messages without calling
    an LLM. It identifies key operations, decisions, and errors to preserve the
    most critical context information.
    
    Target: 10-20% of original token count
    
    Extraction Patterns:
        - File operations: Created, modified, or deleted files
        - Command executions: Shell commands that were run
        - Errors: Error messages and failures
        - Key decisions: First line of substantial AI responses
    
    Args:
        messages: List of messages to summarize
    
    Returns:
        Ultra-compact text summary with key facts
    
    Examples:
        >>> messages = [
        ...     AIMessage(content="Creating auth module..."),
        ...     HumanMessage(content="<write path='auth.py'>..."),
        ...     AIMessage(content="Error: Module not found")
        ... ]
        >>> summary = _create_ultra_compact_summary(messages)
        >>> "auth.py" in summary
        True
        >>> "Error" in summary
        True
    """
    facts = []
    files_modified = set()
    commands_run = []
    errors = []
    key_actions = []
    
    for msg in messages:
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        
        # Extract file operations
        # Pattern: <write path="file.py"> or "Created file: file.py"
        write_patterns = [
            r'<write\s+path=[\'"]([^\'"]+)[\'"]>',
            r'path=[\'"]([^\'"]+)[\'"]',
            r'Created file[:\s]+([^\s,]+)',
            r'Modified[:\s]+([^\s,]+)',
        ]
        for pattern in write_patterns:
            matches = re.findall(pattern, content)
            files_modified.update(matches)
        
        # Extract command executions
        # Pattern: <run>command</run> or similar
        cmd_matches = re.findall(r'<run>(.*?)</run>', content, re.DOTALL)
        for cmd in cmd_matches:
            clean_cmd = cmd.strip()[:80]  # Limit command length
            if clean_cmd:
                commands_run.append(clean_cmd)
        
        # Extract errors (high priority)
        if 'error' in content.lower() or 'Error' in content or 'failed' in content.lower():
            # Extract first line with error or first 120 chars
            lines = content.split('\n')
            for line in lines:
                if 'error' in line.lower() or 'Error' in line or 'failed' in line.lower():
                    error_snippet = line.strip()[:120]
                    if error_snippet:
                        errors.append(error_snippet)
                    break
        
        # Extract key decisions from AI messages
        if isinstance(msg, AIMessage) and len(content) > 50:
            first_line = content.split('\n')[0].strip()
            # Skip XML tags and very short lines
            if not first_line.startswith('<') and len(first_line) > 20:
                key_actions.append(first_line[:100])
    
    # Build compact summary
    parts = []
    
    if files_modified:
        file_list = ', '.join(sorted(files_modified)[:5])  # Max 5 files
        if len(files_modified) > 5:
            file_list += f' +{len(files_modified) - 5} more'
        parts.append(f"Files: {file_list}")
    
    if commands_run:
        cmd_list = '; '.join(commands_run[:3])  # Max 3 commands
        if len(commands_run) > 3:
            cmd_list += f' +{len(commands_run) - 3} more'
        parts.append(f"Commands: {cmd_list}")
    
    if errors:
        error_list = ' | '.join(errors[:3])  # Max 3 errors
        if len(errors) > 3:
            error_list += f' +{len(errors) - 3} more'
        parts.append(f"Errors: {error_list}")
    
    if key_actions:
        action_list = ' | '.join(key_actions[:5])  # Max 5 actions
        if len(key_actions) > 5:
            action_list += f' +{len(key_actions) - 5} more'
        parts.append(f"Actions: {action_list}")
    
    if not parts:
        return f"Processed {len(messages)} messages of general implementation work."
    
    return ' || '.join(parts)


# ── Utility Functions ──────────────────────────────────────────────────

def _truncate_to_fit(messages: List[BaseMessage], budget: int) -> List[BaseMessage]:
    """
    Alias for _truncate_hard for backward compatibility.
    
    This function exists to match the design document's interface but delegates
    to _truncate_hard which is the implementation.
    """
    return _truncate_hard(messages, budget)
