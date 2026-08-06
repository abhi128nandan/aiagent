"""Sandbox service wrapper around DockerRuntime."""
from __future__ import annotations

import asyncio
import uuid
from typing import Optional
from collections import deque

from core.logger import get_logger
from core.config import get_settings
from runtime import DockerRuntime, SandboxInfo

logger = get_logger(__name__)
settings = get_settings()


class SandboxService:
    """
    Provides a service layer for sandbox operations with container pooling.
    
    Features:
    - Container pooling for faster session startup
    - Automatic cleanup of old containers
    - Retry logic with exponential backoff
    """

    # Class-level pool for pre-initialized containers
    _pool: deque[str] = deque(maxlen=5)
    _pool_lock = asyncio.Lock()
    _pool_initialized = False

    def __init__(self, max_retries: int = 3, cleanup_age_seconds: int = 86400) -> None:
        self.max_retries = max_retries
        self.cleanup_age_seconds = cleanup_age_seconds

    @classmethod
    async def initialize_pool(cls, pool_size: int = 2) -> None:
        """Initialize the container pool with pre-created containers."""
        async with cls._pool_lock:
            if cls._pool_initialized:
                return
            
            logger.info("sandbox_pool_init", pool_size=pool_size)
            for i in range(pool_size):
                try:
                    # Create a container with a temporary session ID
                    temp_session_id = f"pool-{uuid.uuid4()}"
                    runtime = DockerRuntime(temp_session_id)
                    cls._pool.append(temp_session_id)
                    logger.info("sandbox_pool_container_created", session_id=temp_session_id, index=i)
                except Exception as exc:
                    logger.warning("sandbox_pool_container_failed", index=i, error=str(exc))
            
            cls._pool_initialized = True
            logger.info("sandbox_pool_ready", available=len(cls._pool))

    @classmethod
    async def get_from_pool(cls) -> Optional[str]:
        """Get a pre-initialized container from the pool."""
        async with cls._pool_lock:
            if cls._pool:
                session_id = cls._pool.popleft()
                logger.info("sandbox_pool_reuse", session_id=session_id, remaining=len(cls._pool))
                return session_id
        return None

    @classmethod
    async def replenish_pool(cls) -> None:
        """Replenish the pool with a new container (async background task)."""
        async with cls._pool_lock:
            if len(cls._pool) >= cls._pool.maxlen:
                return
            
            try:
                temp_session_id = f"pool-{uuid.uuid4()}"
                runtime = DockerRuntime(temp_session_id)
                cls._pool.append(temp_session_id)
                logger.info("sandbox_pool_replenished", session_id=temp_session_id, available=len(cls._pool))
            except Exception as exc:
                logger.warning("sandbox_pool_replenish_failed", error=str(exc))

    async def get_runtime(self, session_id: str) -> DockerRuntime:
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                DockerRuntime.cleanup_old(self.cleanup_age_seconds)
                return DockerRuntime.get(session_id)
            except Exception as exc:
                last_error = exc
                backoff = 2 ** attempt
                logger.warning("sandbox_get_retry", session_id=session_id, attempt=attempt + 1, error=str(exc))
                await asyncio.sleep(backoff)
        raise RuntimeError(f"Failed to start sandbox: {last_error}")

    async def get_status(self, session_id: str) -> SandboxInfo:
        runtime = await self.get_runtime(session_id)
        return runtime.get_status()

    async def health(self, session_id: str, port: int = 3000) -> dict:
        runtime = await self.get_runtime(session_id)
        return await runtime.health_check(port=port)

    async def list_files(self, session_id: str) -> list[str]:
        runtime = await self.get_runtime(session_id)
        return runtime.list_files()

    async def read_file(self, session_id: str, path: str) -> str:
        runtime = await self.get_runtime(session_id)
        return runtime.read_file(path)

    async def write_file(self, session_id: str, path: str, content: str) -> None:
        runtime = await self.get_runtime(session_id)
        runtime.write_file(path, content)


    async def download_workspace(self, session_id: str) -> bytes:
        runtime = await self.get_runtime(session_id)
        return runtime.download_workspace_zip()

    async def pause(self, session_id: str) -> bool:
        runtime = await self.get_runtime(session_id)
        return runtime.pause()

    async def resume(self, session_id: str) -> bool:
        runtime = await self.get_runtime(session_id)
        return runtime.resume()

    async def delete(self, session_id: str) -> None:
        runtime = await self.get_runtime(session_id)
        runtime.cleanup()

    async def usage(self, session_id: str) -> dict:
        runtime = await self.get_runtime(session_id)
        return runtime.get_resource_usage()

    @classmethod
    async def list_all(cls) -> list[SandboxInfo]:
        """List all tracked sandboxes across all sessions."""
        return DockerRuntime.list_all()

    @classmethod
    async def cleanup_old_containers(cls, max_age_seconds: int = 86400) -> int:
        """
        Clean up containers older than max_age_seconds.
        This should be called periodically (e.g., every hour).
        """
        try:
            removed = DockerRuntime.cleanup_old(max_age_seconds)
            if removed > 0:
                logger.info("sandbox_cleanup_completed", removed=removed)
            return removed
        except Exception as exc:
            logger.error("sandbox_cleanup_failed", error=str(exc))
            return 0

    @classmethod
    async def start_cleanup_task(cls, interval_seconds: int = 3600, max_age_seconds: int = 86400) -> None:
        """
        Start a background task that periodically cleans up old containers.
        
        Args:
            interval_seconds: How often to run cleanup (default: 1 hour)
            max_age_seconds: Maximum age of containers before cleanup (default: 24 hours)
        """
        logger.info("sandbox_cleanup_task_started", interval=interval_seconds, max_age=max_age_seconds)
        while True:
            await asyncio.sleep(interval_seconds)
            await cls.cleanup_old_containers(max_age_seconds)
