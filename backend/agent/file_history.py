"""
File Version Control — tracks every version of every file the AI modifies.

Inspired by bolt.diy's getFileHistory() / saveFileHistory() in action-runner.ts.

Before any file write or replace operation, the current version of the file
is saved to a .history/ directory inside the Docker container. This enables:
  - Viewing previous versions of any file
  - Restoring a file to a previous version ("undo")
  - Comparing diffs between AI-generated versions
"""
import time
from typing import Optional
from dataclasses import dataclass, field

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FileVersion:
    """A single saved version of a file."""
    path: str
    timestamp: int
    content: str
    size: int


class FileHistoryManager:
    """
    Tracks every version of every file the AI modifies.
    Stored inside the Docker container at /workspace/.history/
    """

    HISTORY_DIR = ".history"

    async def save_snapshot(self, runtime, file_path: str, content: str) -> bool:
        """
        Save the current file content before the AI overwrites it.

        Args:
            runtime: DockerRuntime instance
            file_path: Path of the file being modified (relative to /workspace)
            content: Current content of the file (before modification)

        Returns:
            True if snapshot was saved successfully
        """
        if not content or not content.strip():
            return False

        timestamp = int(time.time() * 1000)  # Millisecond precision
        history_path = f"{self.HISTORY_DIR}/{file_path}/{timestamp}.txt"

        try:
            from agent.schema import CmdRunAction
            import os

            # Create the history directory for this file
            history_dir = f"{self.HISTORY_DIR}/{file_path}"
            await runtime.execute(CmdRunAction(
                command=f'mkdir -p /workspace/{history_dir}'
            ))

            # Write the snapshot using the runtime's file write mechanism
            from agent.schema import FileWriteAction
            await runtime.execute(FileWriteAction(
                path=history_path,
                content=content
            ))

            logger.info(
                "file_history_saved",
                path=file_path,
                history_path=history_path,
                size=len(content),
            )
            return True

        except Exception as e:
            logger.warning("file_history_save_failed", path=file_path, error=str(e))
            return False

    async def get_versions(self, runtime, file_path: str) -> list[dict]:
        """
        List all saved versions of a file.

        Returns:
            List of dicts with 'timestamp' and 'size' keys, sorted newest first
        """
        try:
            from agent.schema import CmdRunAction

            history_dir = f"{self.HISTORY_DIR}/{file_path}"
            result = await runtime.execute(CmdRunAction(
                command=f'ls -1 /workspace/{history_dir}/ 2>/dev/null | sort -r'
            ))

            if result.get('exit_code') != 0:
                return []

            output = result.get('output', '').strip()
            if not output:
                return []

            versions = []
            for filename in output.splitlines():
                filename = filename.strip()
                if filename.endswith('.txt'):
                    try:
                        ts = int(filename.replace('.txt', ''))
                        versions.append({
                            'timestamp': ts,
                            'filename': filename,
                            'path': f"{history_dir}/{filename}",
                        })
                    except ValueError:
                        continue

            return versions

        except Exception as e:
            logger.warning("file_history_list_failed", path=file_path, error=str(e))
            return []

    async def get_version_content(self, runtime, file_path: str, timestamp: int) -> Optional[str]:
        """
        Get the content of a specific saved version.

        Args:
            runtime: DockerRuntime instance
            file_path: Original file path
            timestamp: Timestamp of the version to retrieve

        Returns:
            File content as string, or None if not found
        """
        try:
            history_path = f"{self.HISTORY_DIR}/{file_path}/{timestamp}.txt"
            content = runtime.read_file(history_path)
            return content
        except Exception as e:
            logger.warning("file_history_read_failed", path=file_path, timestamp=timestamp, error=str(e))
            return None

    async def restore_version(self, runtime, file_path: str, timestamp: int) -> bool:
        """
        Restore a specific version of a file.

        This saves the current version first (so restore is also undoable),
        then writes the historical version back to the original path.

        Args:
            runtime: DockerRuntime instance
            file_path: Original file path
            timestamp: Timestamp of the version to restore

        Returns:
            True if restoration was successful
        """
        try:
            # First, save the current version (so restore is undoable)
            try:
                current_content = runtime.read_file(file_path)
                await self.save_snapshot(runtime, file_path, current_content)
            except Exception:
                pass  # File might not exist currently

            # Get the historical version
            content = await self.get_version_content(runtime, file_path, timestamp)
            if content is None:
                logger.warning("file_history_restore_not_found", path=file_path, timestamp=timestamp)
                return False

            # Write it back to the original path
            from agent.schema import FileWriteAction
            await runtime.execute(FileWriteAction(
                path=file_path,
                content=content
            ))

            logger.info("file_history_restored", path=file_path, timestamp=timestamp)
            return True

        except Exception as e:
            logger.error("file_history_restore_failed", path=file_path, error=str(e))
            return False
