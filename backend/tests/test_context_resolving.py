import pytest
from agent.context_manager import ContextManager

# llama-3.3-70b's true window is 128k, but Groq's free tier allows only
# 12k tokens/minute — requests above that fail with 413, so the budget
# is capped at the effective per-request limit.
def test_resolve_limit_exact():
    cm = ContextManager(model="groq/llama-3.3-70b-versatile")
    assert cm.budget.max_tokens == 12_000

def test_resolve_limit_clean():
    cm = ContextManager(model="llama-3.3-70b-versatile")
    assert cm.budget.max_tokens == 12_000

def test_resolve_limit_substring():
    # "llama-4-scout" is clean, "meta-llama/llama-4-scout-17b-16e-instruct" contains it
    cm = ContextManager(model="groq/llama-4-scout")
    assert cm.budget.max_tokens == 128_000

def test_resolve_limit_unknown():
    cm = ContextManager(model="unknown-model-name")
    assert cm.budget.max_tokens == 8_192

def test_resolve_limit_gemini():
    cm = ContextManager(model="gemini/gemini-2.5-flash")
    assert cm.budget.max_tokens == 128_000
