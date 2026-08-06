"""
Command Pre-Validation — prevents common shell command failures.

Inspired by bolt.diy's #validateShellCommand() in action-runner.ts.

This module intercepts shell commands before they are sent to the Docker
sandbox and auto-fixes known failure patterns. For example:
  - `rm file` without -f → auto-add -f to prevent "No such file" errors
  - `cd nonexistent/` → auto-prepend `mkdir -p` to create the directory
  - `lsof -ti:PORT` → replace with `fuser` (lsof isn't in minimal containers)
  - `pip install X` → add --break-system-packages flag for system Python

This saves an entire LLM round-trip for each prevented failure.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ValidatedCommand:
    """Result of command validation."""
    command: str
    modified: bool = False
    warning: Optional[str] = None
    blocked: bool = False  # If True, command should not be executed


class CommandValidator:
    """
    Validates and auto-fixes shell commands before Docker execution.

    Each rule is a small, focused method that checks for one failure pattern.
    Rules are applied in order; the first match wins.
    """

    async def validate(self, command: str, runtime=None) -> ValidatedCommand:
        """
        Validate a command and return a (possibly modified) version.

        Args:
            command: The raw shell command string
            runtime: Optional DockerRuntime for filesystem checks

        Returns:
            ValidatedCommand with the (possibly fixed) command
        """
        original = command.strip()
        if not original:
            return ValidatedCommand(command=original)

        # Apply rules in priority order
        rules = [
            self._fix_interactive_commands,
            self._fix_rm_without_force,
            self._fix_cd_nonexistent,
            self._fix_lsof_unavailable,
            self._fix_pip_system_packages,
            self._fix_kill_port_fallback,
            self._fix_npm_global_install,
            self._fix_curl_wget_fallback,
        ]

        for rule in rules:
            result = await rule(original, runtime)
            if result is not None:
                return result

        return ValidatedCommand(command=original)

    # ── Rule 1: rm without -f ──────────────────────────────────────────

    async def _fix_rm_without_force(self, cmd: str, runtime) -> Optional[ValidatedCommand]:
        """Add -f flag to rm commands to prevent 'No such file' errors."""
        if not cmd.startswith('rm '):
            return None
        if '-f' in cmd or '-rf' in cmd:
            return None  # Already has force flag

        # Add -f flag
        fixed = cmd.replace('rm ', 'rm -f ', 1)
        return ValidatedCommand(
            command=fixed,
            modified=True,
            warning="Added -f flag to rm command to prevent 'No such file' errors"
        )

    # ── Rule 2: cd to non-existent directory ───────────────────────────

    async def _fix_cd_nonexistent(self, cmd: str, runtime) -> Optional[ValidatedCommand]:
        """Auto-create directories when cd target doesn't exist."""
        # Match standalone cd or cd at the start of a chain
        cd_match = re.match(r'^cd\s+([^\s;&|]+)', cmd)
        if not cd_match:
            return None

        target_dir = cd_match.group(1).strip('"\'')

        # Skip special dirs
        if target_dir in ('.', '..', '~', '/', '-'):
            return None

        if runtime:
            try:
                from agent.schema import CmdRunAction
                check = await runtime.execute(CmdRunAction(command=f'test -d /workspace/{target_dir}'))
                if check.get('exit_code') == 0:
                    return None  # Directory exists, no fix needed
            except Exception:
                pass  # Can't check, apply the fix anyway

        # Prepend mkdir -p
        fixed = f'mkdir -p {target_dir} && {cmd}'
        return ValidatedCommand(
            command=fixed,
            modified=True,
            warning=f"Auto-creating directory '{target_dir}' before cd"
        )

    # ── Rule 3: lsof replacement ───────────────────────────────────────

    async def _fix_lsof_unavailable(self, cmd: str, runtime) -> Optional[ValidatedCommand]:
        """Replace lsof with fuser/kill for minimal containers without lsof."""
        if 'lsof' not in cmd:
            return None

        # Pattern: lsof -ti:PORT | xargs kill -9
        lsof_kill = re.match(r'lsof\s+-ti[:\s]*(\d+)\s*\|\s*xargs\s+kill\s+(-\d+)?', cmd)
        if lsof_kill:
            port = lsof_kill.group(1)
            fixed = f'fuser -k {port}/tcp 2>/dev/null; true'
            return ValidatedCommand(
                command=fixed,
                modified=True,
                warning=f"Replaced lsof with fuser (lsof not available in sandbox)"
            )

        # Pattern: lsof -ti:PORT (just finding the PID)
        lsof_find = re.match(r'lsof\s+-ti[:\s]*(\d+)', cmd)
        if lsof_find:
            port = lsof_find.group(1)
            fixed = f'fuser {port}/tcp 2>/dev/null'
            return ValidatedCommand(
                command=fixed,
                modified=True,
                warning=f"Replaced lsof with fuser (lsof not available in sandbox)"
            )

        return None

    # ── Rule 4: pip system packages ────────────────────────────────────

    async def _fix_pip_system_packages(self, cmd: str, runtime) -> Optional[ValidatedCommand]:
        """Add --break-system-packages to pip install commands."""
        if not re.match(r'pip3?\s+install', cmd):
            return None
        if '--break-system-packages' in cmd:
            return None  # Already present
        if '--user' in cmd or '-e' in cmd:
            return None  # User install or editable mode, skip

        fixed = cmd.replace('pip install', 'pip install --break-system-packages', 1)
        fixed = fixed.replace('pip3 install', 'pip3 install --break-system-packages', 1)
        return ValidatedCommand(
            command=fixed,
            modified=True,
            warning="Added --break-system-packages for container Python"
        )

    # ── Rule 5: kill-port npx fallback ─────────────────────────────────

    async def _fix_kill_port_fallback(self, cmd: str, runtime) -> Optional[ValidatedCommand]:
        """Replace npx kill-port with fuser when npx may not be available."""
        kill_port_match = re.match(r'npx\s+(?:-y\s+)?kill-port\s+(\d+)', cmd)
        if not kill_port_match:
            return None

        port = kill_port_match.group(1)

        # Check if npx is available
        if runtime:
            try:
                from agent.schema import CmdRunAction
                check = await runtime.execute(CmdRunAction(command='command -v npx'))
                if check.get('exit_code') == 0:
                    return None  # npx is available, use original command
            except Exception:
                pass

        fixed = f'fuser -k {port}/tcp 2>/dev/null; true'
        return ValidatedCommand(
            command=fixed,
            modified=True,
            warning=f"Replaced npx kill-port with fuser (npx not available)"
        )

    # ── Rule 6: npm global install ─────────────────────────────────────

    async def _fix_npm_global_install(self, cmd: str, runtime) -> Optional[ValidatedCommand]:
        """Add --unsafe-perm to global npm installs in containers."""
        if 'npm install -g' not in cmd and 'npm i -g' not in cmd:
            return None
        if '--unsafe-perm' in cmd:
            return None

        fixed = cmd.replace('npm install -g', 'npm install -g --unsafe-perm', 1)
        fixed = fixed.replace('npm i -g', 'npm i -g --unsafe-perm', 1)
        return ValidatedCommand(
            command=fixed,
            modified=True,
            warning="Added --unsafe-perm for global npm install in container"
        )

    # ── Rule 7: curl/wget fallback ─────────────────────────────────────

    async def _fix_curl_wget_fallback(self, cmd: str, runtime) -> Optional[ValidatedCommand]:
        """If curl is used but not available, try wget instead."""
        if not cmd.startswith('curl '):
            return None

        if runtime:
            try:
                from agent.schema import CmdRunAction
                check = await runtime.execute(CmdRunAction(command='command -v curl'))
                if check.get('exit_code') == 0:
                    return None  # curl is available
            except Exception:
                pass
        else:
            return None  # Can't check without runtime

        # Simple curl -o URL → wget -O URL conversion
        curl_download = re.match(r'curl\s+(?:-[sLfSo]+\s+)*-o\s+(\S+)\s+(\S+)', cmd)
        if curl_download:
            output_file = curl_download.group(1)
            url = curl_download.group(2)
            fixed = f'wget -O {output_file} {url}'
            return ValidatedCommand(
                command=fixed,
                modified=True,
                warning="Replaced curl with wget (curl not available)"
            )

        return None

    # ── Rule 8: Force non-interactive mode ──────────────────────────────

    async def _fix_interactive_commands(self, cmd: str, runtime) -> Optional[ValidatedCommand]:
        """Pre-add non-interactive flags to scaffolding/package commands.

        This prevents CLI prompts from ever appearing, complementing the
        runtime auto-responder as a defense-in-depth measure.
        """
        # npm init without --yes
        if re.match(r'^npm\s+init\b', cmd) and '--yes' not in cmd and '-y' not in cmd:
            fixed = cmd.replace('npm init', 'npm init --yes', 1)
            return ValidatedCommand(
                command=fixed,
                modified=True,
                warning="Added --yes to npm init for non-interactive mode"
            )

        # yarn init without --yes
        if re.match(r'^yarn\s+init\b', cmd) and '--yes' not in cmd and '-y' not in cmd:
            fixed = cmd.replace('yarn init', 'yarn init --yes', 1)
            return ValidatedCommand(
                command=fixed,
                modified=True,
                warning="Added --yes to yarn init for non-interactive mode"
            )

        # npx without -y (e.g. npx create-vite → npx -y create-vite)
        if cmd.startswith('npx ') and '-y' not in cmd and '--yes' not in cmd:
            fixed = cmd.replace('npx ', 'npx -y ', 1)
            return ValidatedCommand(
                command=fixed,
                modified=True,
                warning="Added -y to npx for auto-install approval"
            )

        # Pipe 'yes' into commands that have no non-interactive flag
        # e.g. 'npx create-react-app' that still prompts
        interactive_scaffolds = [
            'create-react-app',
            'create-next-app',
            'create-expo-app',
        ]
        for scaffold in interactive_scaffolds:
            if scaffold in cmd and not cmd.startswith('yes |'):
                fixed = f'yes | {cmd}'
                return ValidatedCommand(
                    command=fixed,
                    modified=True,
                    warning=f"Piped 'yes' into {scaffold} for non-interactive mode"
                )

        return None
