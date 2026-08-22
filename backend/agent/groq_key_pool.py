"""
Groq API Key Pool — smart multi-key rotation with rate-limit tracking.

Free-tier Groq limits (as of 2026):
  ┌──────────────────────────────┬───────┬────────┬───────┐
  │ Model                        │ RPM   │ TPM    │ TPD   │
  ├──────────────────────────────┼───────┼────────┼───────┤
  │ llama-3.1-8b-instant         │ 30    │ 6,000  │ 500K  │
  │ llama-3.3-70b-versatile      │ 30    │ 12,000 │ 100K  │
  │ llama-4-scout                │ 30    │ 30,000 │ 500K  │
  └──────────────────────────────┴───────┴────────┴───────┘

Strategy:
  1. Round-robin across keys
  2. Track per-key request counts and token usage per minute/day
  3. On 429, mark the key as "cooling down" and try the next one
  4. Exponential backoff when ALL keys are exhausted
"""
from __future__ import annotations

import asyncio
import time
import threading
from dataclasses import dataclass, field
from typing import Optional

from core.logger import get_logger

logger = get_logger(__name__)

# ── Per-model rate limits (free tier) ───────────────────────────────────

MODEL_LIMITS: dict[str, dict[str, int]] = {
    "llama-3.1-8b-instant": {"rpm": 30, "tpm": 6_000, "tpd": 500_000},
    "llama-3.3-70b-versatile": {"rpm": 30, "tpm": 12_000, "tpd": 100_000},
    "llama-4-scout": {"rpm": 30, "tpm": 30_000, "tpd": 500_000},
    "meta-llama/llama-4-scout-17b-16e-instruct": {"rpm": 30, "tpm": 30_000, "tpd": 500_000},
    "llama-4-maverick": {"rpm": 30, "tpm": 6_000, "tpd": 500_000},
    "gemma2-9b-it": {"rpm": 30, "tpm": 15_000, "tpd": 500_000},
    "mixtral-8x7b-32768": {"rpm": 30, "tpm": 5_000, "tpd": 500_000},
    # Fallback for unknown models
    "_default": {"rpm": 30, "tpm": 6_000, "tpd": 100_000},
}


def _get_model_limits(model: str) -> dict[str, int]:
    """Get rate limits for a specific model."""
    # Strip 'groq/' prefix if present
    clean = model.replace("groq/", "")
    return MODEL_LIMITS.get(clean, MODEL_LIMITS["_default"])


@dataclass
class _KeyState:
    """Tracks rate-limit state for a single API key."""

    key: str
    # ── Minute window ──
    minute_requests: int = 0
    minute_tokens: int = 0
    minute_window_start: float = field(default_factory=time.time)
    # ── Day window ──
    day_tokens: int = 0
    day_window_start: float = field(default_factory=time.time)
    # ── Cooldown ──
    cooldown_until: float = 0.0  # epoch timestamp
    # ── Stats ──
    total_requests: int = 0
    total_errors: int = 0
    consecutive_errors: int = 0

    def _reset_minute_window_if_needed(self) -> None:
        now = time.time()
        if now - self.minute_window_start >= 60:
            self.minute_requests = 0
            self.minute_tokens = 0
            self.minute_window_start = now

    def _reset_day_window_if_needed(self) -> None:
        now = time.time()
        if now - self.day_window_start >= 86_400:
            self.day_tokens = 0
            self.day_window_start = now

    def is_available(self, model: str) -> bool:
        """Check if this key can accept a request right now."""
        now = time.time()
        if now < self.cooldown_until:
            return False

        self._reset_minute_window_if_needed()
        self._reset_day_window_if_needed()

        limits = _get_model_limits(model)
        if self.minute_requests >= limits["rpm"]:
            return False
        if self.day_tokens >= limits["tpd"]:
            return False
        return True

    def seconds_until_available(self, model: str) -> float:
        """Estimate how many seconds until this key might be usable."""
        now = time.time()
        if now < self.cooldown_until:
            return self.cooldown_until - now

        self._reset_minute_window_if_needed()
        self._reset_day_window_if_needed()

        limits = _get_model_limits(model)
        if self.minute_requests >= limits["rpm"]:
            return max(0, 60 - (now - self.minute_window_start))
        if self.day_tokens >= limits["tpd"]:
            return max(0, 86_400 - (now - self.day_window_start))
        return 0

    def record_request(self, tokens_used: int = 0) -> None:
        """Record a successful request."""
        self._reset_minute_window_if_needed()
        self._reset_day_window_if_needed()
        self.minute_requests += 1
        self.minute_tokens += tokens_used
        self.day_tokens += tokens_used
        self.total_requests += 1
        self.consecutive_errors = 0

    def record_rate_limit(self, retry_after: float = 60.0) -> None:
        """Mark key as rate-limited (429 received)."""
        self.cooldown_until = time.time() + retry_after
        self.total_errors += 1
        self.consecutive_errors += 1
        logger.warning(
            "groq_key_rate_limited",
            key_suffix=self.key[-4:],
            cooldown_seconds=retry_after,
            consecutive_errors=self.consecutive_errors,
        )

    def record_error(self) -> None:
        """Record a non-rate-limit error."""
        self.total_errors += 1
        self.consecutive_errors += 1

    @property
    def masked(self) -> str:
        return f"...{self.key[-4:]}"


class GroqKeyPool:
    """
    Thread-safe pool of Groq API keys with intelligent rotation.

    Usage:
        pool = GroqKeyPool(["gsk_key1", "gsk_key2", "gsk_key3"])
        key = await pool.acquire("llama-3.3-70b-versatile")
        # ... make API call ...
        pool.release(key, tokens_used=500)       # on success
        pool.report_rate_limit(key, retry_after=60)  # on 429
    """

    def __init__(self, keys: list[str]) -> None:
        if not keys:
            raise ValueError(
                "At least one Groq API key is required. "
                "Set GROQ_API_KEYS in .env (comma-separated)."
            )

        # Deduplicate while preserving order
        seen = set()
        unique_keys = []
        for k in keys:
            k = k.strip()
            if k and k not in seen:
                seen.add(k)
                unique_keys.append(k)

        self._states: list[_KeyState] = [_KeyState(key=k) for k in unique_keys]
        self._lock = threading.Lock()
        self._async_lock = asyncio.Lock()
        self._index = 0  # round-robin pointer

        logger.info(
            "groq_key_pool_initialized",
            num_keys=len(self._states),
            key_suffixes=[s.masked for s in self._states],
        )

    @property
    def size(self) -> int:
        return len(self._states)

    def _next_available_key(self, model: str) -> Optional[_KeyState]:
        """Find the next available key using round-robin."""
        n = len(self._states)
        for _ in range(n):
            state = self._states[self._index % n]
            self._index = (self._index + 1) % n
            if state.is_available(model):
                return state
        return None

    def _min_wait_time(self, model: str) -> float:
        """Find the minimum wait time across all keys."""
        return min(s.seconds_until_available(model) for s in self._states)

    async def acquire(
        self,
        model: str = "groq/openai/gpt-oss-120b",
        max_wait: float = 300.0,
    ) -> str:
        """
        Get an available API key. Waits if all keys are rate-limited.

        Raises TimeoutError if no key becomes available within max_wait seconds.
        """
        start = time.time()

        while True:
            async with self._async_lock:
                state = self._next_available_key(model)
                if state is not None:
                    logger.debug(
                        "groq_key_acquired",
                        key_suffix=state.masked,
                        minute_requests=state.minute_requests,
                    )
                    return state.key

            # All keys exhausted — wait for the shortest cooldown
            elapsed = time.time() - start
            if elapsed >= max_wait:
                raise TimeoutError(
                    f"All {len(self._states)} Groq API keys are rate-limited. "
                    f"Waited {elapsed:.0f}s. Add more keys or upgrade your plan."
                )

            wait_time = self._min_wait_time(model)
            wait_time = min(wait_time, max_wait - elapsed)
            wait_time = max(wait_time, 1.0)  # At least 1 second

            logger.info(
                "groq_all_keys_exhausted_waiting",
                wait_seconds=round(wait_time, 1),
                pool_size=len(self._states),
                model=model,
            )
            await asyncio.sleep(wait_time)

    def release(self, key: str, tokens_used: int = 0) -> None:
        """Record a successful request for the given key."""
        with self._lock:
            for state in self._states:
                if state.key == key:
                    state.record_request(tokens_used)
                    return

    def report_rate_limit(self, key: str, retry_after: float = 60.0) -> None:
        """Mark a key as rate-limited after receiving a 429."""
        with self._lock:
            for state in self._states:
                if state.key == key:
                    state.record_rate_limit(retry_after)
                    return

    def report_error(self, key: str) -> None:
        """Record a non-rate-limit error for a key."""
        with self._lock:
            for state in self._states:
                if state.key == key:
                    state.record_error()
                    return

    def get_stats(self) -> list[dict]:
        """Return per-key statistics for debugging/monitoring."""
        with self._lock:
            return [
                {
                    "key_suffix": s.masked,
                    "total_requests": s.total_requests,
                    "total_errors": s.total_errors,
                    "minute_requests": s.minute_requests,
                    "minute_tokens": s.minute_tokens,
                    "day_tokens": s.day_tokens,
                    "is_cooling": time.time() < s.cooldown_until,
                    "cooldown_remaining": max(0, s.cooldown_until - time.time()),
                }
                for s in self._states
            ]


# ── Module-level singleton ──────────────────────────────────────────────

_pool: Optional[GroqKeyPool] = None


def get_groq_pool() -> GroqKeyPool:
    """Get or create the global GroqKeyPool singleton."""
    global _pool
    if _pool is None:
        from core.config import get_settings
        settings = get_settings()
        keys = settings.get_groq_keys()
        _pool = GroqKeyPool(keys)
    return _pool


def reset_groq_pool() -> None:
    """Reset the pool (e.g., after adding new keys)."""
    global _pool
    _pool = None
