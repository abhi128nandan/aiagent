"""
Docker Sandbox Runtime — inspired by OpenHands' DockerSandboxService.

Features ported from OpenHands:
  - Health checks (ping the container to verify the app is alive)
  - Exposed port management (dynamic port mapping for frontend preview)
  - Container lifecycle (pause / resume / delete)
  - Max sandbox limits (auto-cleans old sandboxes)
  - Init process (proper signal handling and zombie process reaping)
  - Status tracking (STARTING → RUNNING → PAUSED → ERROR → MISSING)
"""
import docker
import tarfile
import zipfile
import io
import time
import json
import socket
import re as re_mod
import pexpect
import asyncio
import redis
import httpx
from enum import Enum
from typing import Dict, Any, Optional, List, cast
from pydantic import BaseModel

from agent.schema import CmdRunAction, FileWriteAction, FileReplaceAction, FileReadAction, BrowserAction, ActionType
from browser import PlaywrightManager
from core.config import get_settings
from core.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


# ── Interactive input queues (for bidirectional terminal proxy) ──────────
# Maps session_id -> asyncio.Queue that receives user keystrokes from the
# frontend WebSocket and feeds them into the running pexpect shell.

_interactive_input_queues: Dict[str, asyncio.Queue] = {}


def get_interactive_queue(session_id: str) -> asyncio.Queue:
    """Get or create the interactive input queue for a session."""
    if session_id not in _interactive_input_queues:
        _interactive_input_queues[session_id] = asyncio.Queue()
    return _interactive_input_queues[session_id]


def send_interactive_input(session_id: str, data: str) -> None:
    """Push user input into the interactive queue (called from WebSocket handler)."""
    q = get_interactive_queue(session_id)
    q.put_nowait(data)
    logger.debug("interactive_input_queued", session_id=session_id, data_len=len(data))


def cleanup_interactive_queue(session_id: str) -> None:
    """Remove the interactive queue for a session."""
    _interactive_input_queues.pop(session_id, None)


# ── Redis singleton ─────────────────────────────────────────────────────

_redis: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
        )
    return _redis


# ── Sandbox models (inspired by OpenHands SandboxInfo) ──────────────────

class SandboxStatus(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    MISSING = "missing"


class ExposedPort(BaseModel):
    name: str
    container_port: int
    host_port: int = 0  # 0 = auto-assigned


class SandboxInfo(BaseModel):
    session_id: str
    container_name: str
    container_ip: str = "127.0.0.1"
    status: SandboxStatus = SandboxStatus.STARTING
    exposed_ports: List[ExposedPort] = []
    created_at: float = 0.0


# ── Port helper ─────────────────────────────────────────────────────────

def _find_unused_port() -> int:
    """Find an unused port on the host machine (same approach as OpenHands)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        return s.getsockname()[1]


# ── Docker status mapping (from OpenHands) ──────────────────────────────

_DOCKER_STATUS_MAP = {
    'running': SandboxStatus.RUNNING,
    'paused': SandboxStatus.PAUSED,
    'exited': SandboxStatus.PAUSED,
    'created': SandboxStatus.STARTING,
    'restarting': SandboxStatus.STARTING,
    'removing': SandboxStatus.MISSING,
    'dead': SandboxStatus.ERROR,
}

# ── CLI prompt auto-responder ───────────────────────────────────────────

# Selection-menu markers used by prompts/clack/inquirer-style CLIs
_MENU_MARKER_RE = re_mod.compile(r'^([●○◯❯›▸])\s*(.+)$')
# Box-drawing characters clack/prompts draw before each option line,
# e.g. "│  ● Cancel operation"
_MENU_BOX_PREFIX = '│┃|◆◇┌└├─ \t'
# Safe choices, in preference order, for unattended scaffolding
_MENU_PREFERRED_OPTIONS = (
    'ignore files and continue',
    'remove existing files and continue',
    'yes',
    'continue',
    'proceed',
)


def _parse_menu_options(text: str) -> list[dict]:
    """
    Extract selection-menu options from CLI output.

    Returns [{'label': str, 'selected': bool}, ...] in display order.
    Handles clack-style box prefixes ("│  ● Cancel operation").

    TUIs REDRAW the menu on every keypress, so the output buffer contains
    multiple stale frames stacked on top of each other. Walk backwards from
    the end and stop at the first repeated label — that isolates the LAST
    (current) frame, whose highlighted option reflects the real cursor.
    """
    options_rev: list[dict] = []
    seen: set[str] = set()
    for raw_line in reversed(text.splitlines()):
        line = raw_line.strip().lstrip(_MENU_BOX_PREFIX).strip()
        m = _MENU_MARKER_RE.match(line)
        if m:
            label = m.group(2).strip()
            if label.lower() in seen:
                break  # reached a stale frame above
            seen.add(label.lower())
            options_rev.append({
                'label': label,
                'selected': m.group(1) in ('●', '❯', '›', '▸'),
            })
        elif options_rev and line:
            break  # non-option line above the option block
    return list(reversed(options_rev))


def _menu_answer_for_index(options: list[dict], target_idx: int) -> str:
    """
    Arrow-key sequence that moves from the highlighted option to target_idx.

    NOTE: Enter must be '\\r' (carriage return) — raw-mode TUIs (clack,
    inquirer, prompts) do NOT recognize '\\n' as Enter; sending '\\n' just
    makes them redraw the menu forever.
    """
    selected_idx = next((i for i, o in enumerate(options) if o['selected']), 0)
    delta = target_idx - selected_idx
    if delta >= 0:
        return '\x1b[B' * delta + '\r'   # arrow down × delta, then Enter
    return '\x1b[A' * (-delta) + '\r'    # arrow up × |delta|, then Enter


def _detect_menu_answer(text: str) -> Optional[str]:
    """
    Handle radio/arrow-key selection menus (e.g. create-vite's
    "Current directory is not empty" menu).

    Typing 'y' does NOTHING in these menus, and plain Enter selects the
    highlighted option — which for create-vite is "Cancel operation".
    Instead, parse the options, find a safe one, and navigate to it
    with arrow-key escapes.

    Returns the key sequence, or None if no recognizably safe option
    exists (→ ask the user).
    """
    options = _parse_menu_options(text)
    if len(options) < 2:
        return None  # not a multi-option menu

    for preferred in _MENU_PREFERRED_OPTIONS:
        for i, option in enumerate(options):
            if preferred in option['label'].lower():
                return _menu_answer_for_index(options, i)

    return None  # unknown menu → let the user decide


def _detect_cli_prompt(text: str) -> Optional[str]:
    """
    Detect common CLI prompts and return the auto-answer.

    Returns the string to send (e.g. '\\n' for Enter, 'y\\n' for yes),
    or None if the prompt is unknown and the user should be asked.

    Covers:
    - y/N and Y/n confirmation prompts
    - "Ok to proceed? (y)" (npx)
    - "Need to install ... proceed?" (npx)
    - "Select a framework" / arrow-key menus (navigate to safe option)
    - "Project name:" / "Package name:" (send Enter for default)
    - "Overwrite?" / "Directory already contains files" (send Enter/y)
    - "Do you want to continue? [Y/n]" (apt-get)
    """
    lower = text.lower()
    last_line = text.strip().rsplit('\n', 1)[-1].strip()
    last_lower = last_line.lower()

    # ── Pattern 0: Radio/arrow-key menus MUST be handled first ───────
    # ('y\n' answers are wrong for menus: Enter picks the highlighted
    # option, which is often "Cancel operation".)
    has_menu = any(marker in text[-600:] for marker in ('●', '○', '◯', '❯'))
    if has_menu:
        menu_answer = _detect_menu_answer(text[-600:])
        if menu_answer is not None:
            return menu_answer
        # Framework/variant pickers: the highlighted default is fine
        if re_mod.search(r'select\s+a\s+(?:framework|variant|template|preset)', lower):
            return '\r'
        return None  # unknown menu — never blind-'y' it; ask the user

    # ── Pattern 1: npx "Ok to proceed?" / "Need to install" ──────────
    if 'ok to proceed' in lower or 'need to install' in lower:
        return 'y\r'

    # ── Pattern 2: Explicit (y/N) or (Y/n) at end of line ────────────
    if re_mod.search(r'\(y/n\)|\(Y/n\)|\(y/N\)|\[y/N\]|\[Y/n\]|\[yes/no\]', last_line):
        # Default to "yes" for most CI-style prompts
        return 'y\r'

    # ── Pattern 3: "? ... (Y/n)" or "? ... (y)" ─────────────────────
    if last_lower.rstrip().endswith('(y)') or last_lower.rstrip().endswith('[y]'):
        return '\r'  # Just press Enter for default=yes

    # ── Pattern 4: "Do you want to continue?" (apt-get, npm) ─────────
    if 'do you want to continue' in lower or 'do you wish to continue' in lower:
        return 'y\r'

    # ── Pattern 5: "Overwrite?" / "already exists" ───────────────────
    if 'overwrite' in lower or 'already exists' in lower or 'directory is not empty' in lower:
        return 'y\r'

    # ── Pattern 6: "Project name:" / "Package name:" (Enter=default) ─
    if re_mod.search(r'(?:project|package|app)\s*name\s*[:?›»]', last_lower):
        return '\r'

    # ── Pattern 7: "Select a framework:" / "Select a variant:" ───────
    if re_mod.search(r'select\s+a\s+(?:framework|variant|template|preset)', last_lower):
        return '\r'  # Accept the default (first option)

    # ── Pattern 8: Arrow-key selection menus (❯, ›, ▸, >) ────────────
    if re_mod.search(r'[❯›▸>]\s+\S+', last_line) and '?' in text[-200:]:
        return '\r'  # Accept highlighted default

    # ── Pattern 9: "Would you like to ...?" generic ──────────────────
    if 'would you like to' in lower and '?' in last_line:
        return '\r'

    # ── Pattern 10: "Press enter to continue" ────────────────────────
    if 'press enter' in lower or 'press return' in lower:
        return '\r'

    # ── Pattern 11: "Use TypeScript?" / "Use ESLint?" (Vite/CRA) ─────
    if re_mod.search(r'use\s+\w+\s*\?', last_lower):
        return '\r'  # Accept default

    # ── Pattern 12: "Are you sure" ───────────────────────────────────
    if 'are you sure' in lower:
        return 'y\r'

    # ── No match — let the user answer ───────────────────────────────
    return None


class DockerRuntime:
    """
    Manages a sandboxed Docker container with a persistent bash shell.

    Inspired by OpenHands' DockerSandboxService, this class adds:
    - Health checks for the running app
    - Dynamic port exposure for frontend previews
    - Pause / resume / delete lifecycle management
    - Max sandbox limits with automatic cleanup
    - `init=True` for proper signal handling
    """

    _local_cache: Dict[str, 'DockerRuntime'] = {}
    REDIS_KEY_PREFIX = "agent:sandbox:"
    MAX_SANDBOXES = 5
    HEALTH_CHECK_TIMEOUT = 5  # seconds

    # Default ports exposed from the sandbox container
    DEFAULT_EXPOSED_PORTS = [
        ExposedPort(name="app_server", container_port=3000),
        ExposedPort(name="dev_server", container_port=5173),
        ExposedPort(name="backend", container_port=8000),
    ]

    # ── Factory ─────────────────────────────────────────────────────────

    @classmethod
    def get(cls, session_id: str) -> 'DockerRuntime':
        # 1. In-process cache
        if session_id in cls._local_cache:
            rt = cls._local_cache[session_id]
            try:
                rt.container.reload()
                if rt.container.status == 'running':
                    return rt
            except Exception:
                logger.warning("container_stale", session_id=session_id)
                cls._local_cache.pop(session_id, None)

        # 2. Redis lookup
        r = _get_redis()
        stored = cast(str, r.get(f"{cls.REDIS_KEY_PREFIX}{session_id}"))
        if stored:
            meta = json.loads(stored)
            container_name = meta.get("container_name")
            try:
                client = docker.from_env()
                container = client.containers.get(container_name)
                if container.status in ('running', 'paused'):
                    # Resume if paused
                    if container.status == 'paused':
                        container.unpause()
                        logger.info("container_resumed", session_id=session_id)

                    logger.info("container_reattach", session_id=session_id, container=container_name)
                    rt = cls.__new__(cls)
                    rt.session_id = session_id
                    rt.client = client
                    rt.container = container
                    rt.container_name = container_name
                    rt.container_ip = meta.get("container_ip", "127.0.0.1")
                    rt.exposed_ports = [ExposedPort(**p) for p in meta.get("exposed_ports", [])]
                    rt._init_shell()
                    cls._local_cache[session_id] = rt
                    return rt
            except docker.errors.NotFound:
                logger.warning("container_gone", session_id=session_id, container=container_name)
                r.delete(f"{cls.REDIS_KEY_PREFIX}{session_id}")

        # 3. Enforce max sandbox limit before creating new one
        cls._enforce_sandbox_limit()

        # 4. Create brand-new sandbox
        rt = cls(session_id)
        cls._local_cache[session_id] = rt
        return rt

    # ── Sandbox limit enforcement (from OpenHands) ──────────────────────

    @classmethod
    def _enforce_sandbox_limit(cls):
        """Pause oldest sandboxes if we've hit the limit."""
        r = _get_redis()
        keys = cast(List[str], r.keys(f"{cls.REDIS_KEY_PREFIX}*"))
        if len(keys) < cls.MAX_SANDBOXES:
            return

        entries = []
        for key in keys:
            raw = cast(str, r.get(key))
            if raw:
                meta = json.loads(raw)
                entries.append((key, meta))

        entries.sort(key=lambda e: e[1].get("created_at", 0))

        to_pause = len(entries) - (cls.MAX_SANDBOXES - 1)
        client = docker.from_env()
        for key, meta in entries[:to_pause]:
            try:
                container = client.containers.get(meta["container_name"])
                if container.status == 'running':
                    container.pause()
                    logger.info("container_auto_paused", container=meta["container_name"])
            except Exception:
                pass

    @classmethod
    def cleanup_old(cls, max_age_seconds: int = 86400) -> int:
        """Remove sandboxes older than the max age."""
        r = _get_redis()
        keys = cast(List[str], r.keys(f"{cls.REDIS_KEY_PREFIX}*"))
        if not keys:
            return 0

        now = time.time()
        client = docker.from_env()
        removed = 0
        for key in keys:
            raw = cast(str, r.get(key))
            if not raw:
                continue
            meta = json.loads(raw)
            created_at = meta.get("created_at", 0)
            if not created_at or (now - created_at) < max_age_seconds:
                continue
            container_name = meta.get("container_name")
            try:
                container = client.containers.get(container_name)
                container.stop(timeout=10)
                container.remove()
                removed += 1
                logger.info("container_auto_removed", container=container_name)
            except docker.errors.NotFound:
                pass
            except Exception as e:
                logger.warning("container_cleanup_failed", container=container_name, error=str(e))
            r.delete(key)
        return removed

    @classmethod
    def list_all(cls) -> List[SandboxInfo]:
        """List all tracked sandboxes from Redis and Docker."""
        r = _get_redis()
        keys = cast(List[str], r.keys(f"{cls.REDIS_KEY_PREFIX}*"))
        sandboxes = []
        if not keys:
            return sandboxes
            
        client = docker.from_env()
        for key in keys:
            raw = cast(str, r.get(key))
            if not raw:
                continue
            meta = json.loads(raw)
            session_id = key[len(cls.REDIS_KEY_PREFIX):]
            container_name = meta.get("container_name")
            
            try:
                container = client.containers.get(container_name)
                docker_status = container.status
                status = _DOCKER_STATUS_MAP.get(docker_status, SandboxStatus.ERROR)
            except Exception:
                status = SandboxStatus.MISSING
                
            sandboxes.append(SandboxInfo(
                session_id=session_id,
                container_name=container_name or "unknown",
                container_ip=meta.get("container_ip", "127.0.0.1"),
                status=status,
                exposed_ports=[ExposedPort(**p) for p in meta.get("exposed_ports", [])],
                created_at=meta.get("created_at", 0)
            ))
            
        # Sort by most recently created
        sandboxes.sort(key=lambda s: s.created_at, reverse=True)
        return sandboxes

    # ── Constructor ─────────────────────────────────────────────────────

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.client = docker.from_env()

        try:
            self.client.images.get(settings.SANDBOX_IMAGE)
        except docker.errors.ImageNotFound:
            logger.error("sandbox_image_missing", image=settings.SANDBOX_IMAGE)
            raise RuntimeError(f"Docker image '{settings.SANDBOX_IMAGE}' not found. Build it first.")

        self.container_name = f"agent-sandbox-{session_id[:8]}-{int(time.time())}"
        logger.info("container_start", session_id=session_id, container=self.container_name)

        # Assign host ports for each exposed port (like OpenHands)
        self.exposed_ports = []
        port_bindings = {}
        for ep in self.DEFAULT_EXPOSED_PORTS:
            host_port = _find_unused_port()
            self.exposed_ports.append(ExposedPort(
                name=ep.name,
                container_port=ep.container_port,
                host_port=host_port,
            ))
            port_bindings[f"{ep.container_port}/tcp"] = host_port

        import os
        # Create a workspace directory on the host for this session
        host_workspace_dir = os.path.abspath(
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "workspaces", session_id)
        )
        os.makedirs(host_workspace_dir, exist_ok=True)

        self.container = self.client.containers.run(
            settings.SANDBOX_IMAGE,
            command='sleep infinity',
            detach=True,
            working_dir='/workspace',
            mem_limit=settings.SANDBOX_MEM_LIMIT,
            cpu_period=100000,
            cpu_quota=settings.SANDBOX_CPU_QUOTA,
            name=self.container_name,
            # OpenHands key features:
            init=True,       # proper signal handling & zombie reaping
            remove=False,    # allow pause/resume (can't pause auto-remove containers)
            ports=port_bindings,
            extra_hosts={"host.docker.internal": "host-gateway"},
            volumes={
                host_workspace_dir: {
                    'bind': '/workspace',
                    'mode': 'rw'
                }
            }
        )

        time.sleep(1)
        self.container.reload()
        self.container_ip = (
            self.container.attrs
            .get('NetworkSettings', {})
            .get('IPAddress', '127.0.0.1')
        )

        # Persist to Redis
        r = _get_redis()
        r.set(
            f"{self.REDIS_KEY_PREFIX}{session_id}",
            json.dumps({
                "container_name": self.container_name,
                "container_ip": self.container_ip,
                "exposed_ports": [ep.model_dump() for ep in self.exposed_ports],
                "created_at": time.time(),
            }),
            ex=86400,
        )

        self._init_shell()

    # ── Shell ───────────────────────────────────────────────────────────

    def _init_shell(self):
        """Spawn a persistent interactive bash session inside the container."""
        self.shell = pexpect.spawn(
            f'docker exec -it {self.container_name} /bin/bash',
            encoding='utf-8',
        )
        self.shell_pid = None
        try:
            self.shell.sendline('export PS1="[PROMPT_END]# "')
            self.shell.expect('\\[PROMPT_END\\]# ', timeout=5)
            self.shell.sendline('cd /workspace')
            self.shell.expect('\\[PROMPT_END\\]# ', timeout=5)
            # Retrieve shell PID
            self.shell.sendline('echo $$')
            self.shell.expect('\\[PROMPT_END\\]# ', timeout=5)
            lines = (self.shell.before or '').splitlines()
            for line in lines:
                cleaned = line.strip()
                if cleaned.isdigit():
                    self.shell_pid = int(cleaned)
                    break
        except (pexpect.TIMEOUT, pexpect.EOF) as e:
            # A slow/stuck container shouldn't hard-fail session reattach —
            # PS1 was still sent; command execution can usually proceed.
            logger.warning(
                "init_shell_prompt_timeout",
                session_id=self.session_id,
                error=type(e).__name__,
            )

    async def get_active_processes(self) -> List[Dict[str, Any]]:
        loop = asyncio.get_event_loop()
        def _get_ps():
            try:
                # 1) Try running ps command
                res = self.container.exec_run("ps -eo pid,ppid,stat,args --no-headers")
                if res.exit_code == 0:
                    output = res.output.decode('utf-8', errors='ignore')
                    processes = []
                    for line in output.strip().splitlines():
                        parts = line.strip().split(None, 3)
                        if len(parts) >= 4:
                            pid, ppid, stat, args = parts
                            # Filter out system and ps processes
                            if pid in ("1", "0") or "ps -eo" in args or "sleep infinity" in args:
                                continue
                            processes.append({
                                "pid": int(pid),
                                "ppid": int(ppid),
                                "status": "Running" if "Z" not in stat else "Zombie",
                                "command": args.strip()
                            })
                    return processes
            except Exception as e:
                logger.warning("ps_command_failed_falling_back_to_proc", session_id=self.session_id, error=str(e))

            # 2) Fallback: run pure python script to parse /proc
            try:
                python_script = (
                    "import os, json\n"
                    "procs = []\n"
                    "for name in os.listdir('/proc'):\n"
                    "    if name.isdigit():\n"
                    "        try:\n"
                    "            pid = int(name)\n"
                    "            with open(f'/proc/{pid}/stat', 'r') as f:\n"
                    "                stat = f.read().split()\n"
                    "            ppid = int(stat[3])\n"
                    "            state = stat[2]\n"
                    "            with open(f'/proc/{pid}/cmdline', 'r') as f:\n"
                    "                cmdline = f.read().replace(\"\\x00\", \" \").strip()\n"
                    "            if not cmdline:\n"
                    "                cmdline = stat[1].strip('()')\n"
                    "            if pid in (1, 0) or 'sleep infinity' in cmdline or 'python -c' in cmdline or 'python3 -c' in cmdline:\n"
                    "                continue\n"
                    "            procs.append({\n"
                    "                'pid': pid,\n"
                    "                'ppid': ppid,\n"
                    "                'status': 'Zombie' if state == 'Z' else 'Running',\n"
                    "                'command': cmdline\n"
                    "            })\n"
                    "        except Exception:\n"
                    "            pass\n"
                    "print(json.dumps(procs))"
                )
                res = self.container.exec_run(["python3", "-c", python_script])
                if res.exit_code == 0:
                    import json
                    output = res.output.decode('utf-8', errors='ignore')
                    return json.loads(output.strip())
            except Exception as e:
                logger.warning("get_active_processes_fallback_failed", session_id=self.session_id, error=str(e))

            return []
        return await loop.run_in_executor(None, _get_ps)

    def get_foreground_process(self, processes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not getattr(self, 'shell_pid', None):
            return None
        # Find process whose PPID is self.shell_pid
        for p in processes:
            if p["ppid"] == self.shell_pid:
                return p
        return None

    async def kill_process(self, pid: Optional[int], signal: int = 15) -> bool:
        if not pid:
            # If pid is missing/None, send control sequences to shell
            # SIGINT (2) -> \x03, SIGTSTP (20) -> \x1a
            if signal == 2:
                self.shell.send('\x03')
                return True
            elif signal == 20:
                self.shell.send('\x1a')
                return True
            elif signal == 9:
                # Force kill without PID: close the shell itself!
                if hasattr(self, 'shell') and self.shell.isalive():
                    self.shell.close(force=True)
                return True
            return False

        # Get active processes to find descendants
        processes = await self.get_active_processes()
        
        # Build ppid map
        from collections import defaultdict
        ppid_to_pids = defaultdict(list)
        for p in processes:
            ppid_to_pids[p["ppid"]].append(p["pid"])
            
        # Find all descendants using DFS/BFS
        to_kill = []
        queue = [pid]
        visited = set()
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            # Add all children
            children = ppid_to_pids.get(curr, [])
            to_kill.extend(children)
            queue.extend(children)
            
        # Reverse the order so we kill descendants from deepest first (leaf to root)
        to_kill.reverse()
        
        # Also include the target pid itself
        to_kill.append(pid)
        
        # Kill each PID
        loop = asyncio.get_event_loop()
        success = True
        for p_id in to_kill:
            def _kill_single(p=p_id):
                try:
                    res = self.container.exec_run(f"kill -{signal} {p}")
                    return res.exit_code == 0
                except Exception as e:
                    logger.warning("kill_process_failed", session_id=self.session_id, pid=p, error=str(e))
                    return False
            ok = await loop.run_in_executor(None, _kill_single)
            if p_id == pid:
                success = ok
        return success

    async def _execute_cmd_interactive(self, action: CmdRunAction) -> dict:
        """
        Execute a shell command with bidirectional interactive streaming.

        Instead of blocking on pexpect.expect(), this method:
        1. Runs the command via shell.sendline()
        2. Polls for output in a background thread, pushing chunks to an asyncio.Queue
        3. An async loop reads those chunks, broadcasts them to the frontend via
           WEBSOCKET_BROADCASTERS, and accumulates the full output
        4. Simultaneously drains the interactive input queue (user keystrokes from
           the frontend) and forwards them to the pexpect shell
        5. Exits when [PROMPT_END]# is detected or timeout is reached
        """
        from agent.observability import WEBSOCKET_BROADCASTERS

        loop = asyncio.get_event_loop()
        ansi_escape = re_mod.compile(r'(?:\x1B[@-Z\\-_]|\x1B\[[0-?]*[ -/]*[@-~])')

        # ── Async broadcast helper ──────────────────────────────────────
        async def _broadcast(payload: dict):
            callbacks = WEBSOCKET_BROADCASTERS.get(self.session_id, [])
            for cb in callbacks:
                try:
                    await cb(payload)
                except Exception:
                    pass

        self.should_restart_current = False

        while True:
            self.current_command = action.command
            self.current_command_start = time.time()
            self.current_command_pid = None

            output_queue: asyncio.Queue = asyncio.Queue()
            prompt_marker = '[PROMPT_END]# '

            # ── Drain stale output from previous command ────────────────────
            def _drain_stale():
                try:
                    while True:
                        self.shell.read_nonblocking(size=4096, timeout=0.1)
                except (pexpect.TIMEOUT, pexpect.EOF):
                    pass

            await loop.run_in_executor(None, _drain_stale)

            # ── Drain any stale interactive input from a previous command ───
            input_q = get_interactive_queue(self.session_id)
            while not input_q.empty():
                try:
                    input_q.get_nowait()
                except asyncio.QueueEmpty:
                    break

            # ── Send the command ────────────────────────────────────────────
            def _send_command():
                self.shell.sendline(action.command)

            await loop.run_in_executor(None, _send_command)

            # ── Create log files in sandbox ─────────────────────────────────
            def _ensure_logs_dir():
                try:
                    self.container.exec_run('mkdir -p /workspace/logs', workdir='/workspace')
                except Exception:
                    pass
            await loop.run_in_executor(None, _ensure_logs_dir)

            # ── Broadcast command start to Agent Terminal ───────────────────
            ts = time.strftime('%H:%M:%S')
            await _broadcast({
                'type': 'agent_log',
                'data': f'\x1b[90m[{ts}]\x1b[0m \x1b[33m▶ Running:\x1b[0m {action.command}\r\n',
                'session_id': self.session_id,
            })
            await _broadcast({
                'type': 'process_start',
                'command': action.command,
                'session_id': self.session_id,
            })

            # ── Background thread: poll pexpect for output ──────────────────
            finished_event = asyncio.Event()
            accumulated_output: list[str] = []

            # Wait a moment for process to spawn, then detect its PID
            await asyncio.sleep(0.5)
            processes = await self.get_active_processes()
            fg_proc = self.get_foreground_process(processes)
            if fg_proc:
                self.current_command_pid = fg_proc["pid"]
                await _broadcast({
                    'type': 'foreground_pid',
                    'pid': fg_proc["pid"],
                    'session_id': self.session_id,
                })

            def _poll_output():
                """Runs in a thread — reads pexpect output and pushes to queue."""
                deadline = time.time() + settings.SANDBOX_TIMEOUT
                idle_start = None
                IDLE_THRESHOLD = 3.0  # seconds of no output → might be waiting
                buffer = ""

                while time.time() < deadline:
                    if getattr(self, 'should_restart_current', False):
                        loop.call_soon_threadsafe(output_queue.put_nowait, ('restart_requested', ''))
                        return
                    try:
                        chunk = self.shell.read_nonblocking(size=4096, timeout=0.5)
                        if isinstance(chunk, bytes):
                            chunk = chunk.decode('utf-8', errors='ignore')
                        if chunk:
                            idle_start = None  # Reset idle timer
                            loop.call_soon_threadsafe(output_queue.put_nowait, ('data', chunk))
                            # Check for prompt end in rolling buffer
                            buffer = (buffer + chunk)[-1000:]
                            if prompt_marker in buffer:
                                loop.call_soon_threadsafe(output_queue.put_nowait, ('done', ''))
                                return
                    except pexpect.TIMEOUT:
                        # No output for 0.5s — check if idle
                        if idle_start is None:
                            idle_start = time.time()
                        elif time.time() - idle_start >= IDLE_THRESHOLD:
                            # Stalled for 3s — notify main loop to check if we are waiting for user input
                            loop.call_soon_threadsafe(
                                output_queue.put_nowait,
                                ('waiting', '')
                            )
                            idle_start = None  # Reset so we don't spam
                        continue
                    except pexpect.EOF:
                        loop.call_soon_threadsafe(output_queue.put_nowait, ('eof', ''))
                        return

                # Timeout reached
                try:
                    self.shell.sendcontrol('c')
                    time.sleep(0.3)
                    try:
                        self.shell.read_nonblocking(size=4096, timeout=1)
                    except (pexpect.TIMEOUT, pexpect.EOF):
                        pass
                except Exception:
                    pass
                loop.call_soon_threadsafe(output_queue.put_nowait, ('timeout', ''))

            poll_future = loop.run_in_executor(None, _poll_output)

            # ── Main async loop: read output + relay user input ─────────────
            command_done = False
            timed_out = False
            first_line_skipped = False
            consecutive_waits = 0          # idle ticks with no auto-answer
            last_prompt_broadcast = ''     # dedup repeated interactive_waiting
            last_auto_answer = ''          # loop guard: same auto-answer repeating
            same_auto_streak = 0           # → escalate to the user instead
            restart_triggered = False

            while not command_done:
                # 1) Check for user input (non-blocking)
                try:
                    user_data = input_q.get_nowait()
                    if user_data:
                        # Enter must reach the pty as '\r' (what real terminals
                        # send): raw-mode TUIs ignore '\n', while canonical-mode
                        # programs translate '\r' to '\n' via ICRNL. So '\r'
                        # works everywhere — normalize all newlines to it.
                        user_data = user_data.replace('\r\n', '\r').replace('\n', '\r')

                        def _send_input(data=user_data):
                            self.shell.send(data)
                        await loop.run_in_executor(None, _send_input)

                        # Confirm delivery in the Agent Terminal + reset waiting state
                        shown = user_data.strip() or '⏎'
                        await _broadcast({
                            'type': 'agent_log',
                            'data': f'\x1b[32m⌨ Your answer was sent to the command:\x1b[0m {shown}\r\n',
                            'session_id': self.session_id,
                        })
                        last_prompt_broadcast = ''
                        consecutive_waits = 0
                except asyncio.QueueEmpty:
                    pass

                # 2) Read output chunks (with short timeout to keep input responsive)
                try:
                    msg_type, chunk = await asyncio.wait_for(
                        output_queue.get(), timeout=0.2
                    )
                except asyncio.TimeoutError:
                    continue

                if msg_type == 'restart_requested':
                    command_done = True
                    restart_triggered = True

                elif msg_type == 'data':
                    consecutive_waits = 0  # output resumed — not stalled
                    # Clean ANSI codes for storage, but send raw for terminal display
                    clean_chunk = ansi_escape.sub('', chunk)

                    # Skip the echo of the command itself (first line)
                    if not first_line_skipped:
                        lines = clean_chunk.split('\n', 1)
                        if action.command.strip() in lines[0]:
                            clean_chunk = lines[1] if len(lines) > 1 else ''
                        first_line_skipped = True

                    # Remove prompt marker from display
                    display_chunk = chunk.replace(prompt_marker, '')

                    if display_chunk:
                        if clean_chunk:
                            accumulated_output.append(clean_chunk)
                        # Broadcast raw terminal output to frontend
                        await _broadcast({
                            'type': 'interactive_output',
                            'data': display_chunk,
                            'session_id': self.session_id,
                        })

                elif msg_type == 'waiting':
                    # Command appears stalled — check if we can auto-answer
                    recent = ''.join(accumulated_output[-3:]) if accumulated_output else ''
                    recent_stripped = recent.strip()

                    if not recent_stripped:
                        continue

                    # ── Auto-responder: detect common CLI prompts and answer them ──
                    auto_answer = _detect_cli_prompt(recent_stripped)

                    # Loop guard: if the SAME auto-answer fires repeatedly the
                    # prompt isn't accepting it — stop guessing, ask the user.
                    if auto_answer is not None:
                        if auto_answer == last_auto_answer:
                            same_auto_streak += 1
                        else:
                            last_auto_answer = auto_answer
                            same_auto_streak = 1
                        if same_auto_streak > 2:
                            logger.warning(
                                "auto_answer_loop_detected",
                                session_id=self.session_id,
                                answer=repr(auto_answer),
                                streak=same_auto_streak,
                            )
                            auto_answer = None  # escalate to the user below

                    if auto_answer is not None:
                        consecutive_waits = 0
                        # Human-readable form: arrow escapes → ↓/↑, newline → ⏎
                        answer_display = (
                            auto_answer.replace('\x1b[B', '↓').replace('\x1b[A', '↑')
                            .replace('\r', '⏎').replace('\n', '⏎')
                        )
                        logger.info(
                            "interactive_auto_answer",
                            session_id=self.session_id,
                            prompt=recent_stripped[-100:],
                            answer=answer_display,
                        )
                        # Broadcast to frontend so user sees what happened
                        await _broadcast({
                            'type': 'interactive_output',
                            'data': f'\x1b[33m[auto-answer: {answer_display}]\x1b[0m\r\n',
                            'session_id': self.session_id,
                        })
                        # Send the answer to pexpect
                        def _send_auto(ans=auto_answer):
                            self.shell.send(ans)
                        await loop.run_in_executor(None, _send_auto)
                    else:
                        consecutive_waits += 1
                        # Parse selection-menu options so the frontend can render
                        # them as clickable choices instead of a free-text box.
                        menu_options = _parse_menu_options(recent_stripped[-600:])
                        # The question is the last non-empty line of output —
                        # except for selection menus, where the user needs to
                        # see ALL the options to answer.
                        if menu_options:
                            menu_lines = [ln.rstrip() for ln in recent_stripped.splitlines() if ln.strip()]
                            question = '\n'.join(menu_lines[-8:])
                        else:
                            question = next(
                                (ln.strip() for ln in reversed(recent_stripped.splitlines()) if ln.strip()),
                                '',
                            )
                        looks_like_prompt = (
                            recent[-1] in (' ', '?', ':', '>', '$', '#', '-', ']')
                            or '?' in question
                            # Selection menus the auto-responder declined to answer
                            or any(m in recent_stripped[-600:] for m in ('●', '○', '◯', '❯'))
                        )
                        # Unknown prompt-shaped stall → ask immediately.
                        # Any other stall → ask after ~3 idle ticks (could just be slow).
                        if (looks_like_prompt or consecutive_waits >= 3) and question != last_prompt_broadcast:
                            last_prompt_broadcast = question
                            await _broadcast({
                                'type': 'interactive_waiting',
                                'prompt': question[:600],
                                'context': recent_stripped[-400:],
                                'certain': looks_like_prompt,
                                'command': action.command[:200],
                                'input_type': 'select' if len(menu_options) >= 2 else 'text',
                                'options': menu_options[:10],
                                'session_id': self.session_id,
                            })

                elif msg_type == 'done':
                    command_done = True

                elif msg_type == 'timeout':
                    command_done = True
                    timed_out = True

                elif msg_type == 'eof':
                    command_done = True

            # ── Wait for poll thread to finish ──────────────────────────────
            await poll_future

            if restart_triggered:
                if self.current_command_pid:
                    await self.kill_process(self.current_command_pid, signal=9)
                await _broadcast({
                    'type': 'agent_log',
                    'data': f'\x1b[33m↻ Restarting command:\x1b[0m {action.command}\r\n',
                    'session_id': self.session_id,
                })
                self.should_restart_current = False
                await asyncio.sleep(1)
                continue

            break

        # ── Wait for poll thread to finish ──────────────────────────────
        await poll_future

        # ── Notify frontend that interactive mode is over ───────────────
        await _broadcast({
            'type': 'interactive_done',
            'session_id': self.session_id,
        })
        await _broadcast({
            'type': 'process_end',
            'session_id': self.session_id,
        })

        if timed_out:
            return {
                'output': f'Command timed out after {settings.SANDBOX_TIMEOUT}s (SIGINT sent).',
                'exit_code': 124,
            }

        # ── Get exit code ───────────────────────────────────────────────
        def _get_exit_code():
            try:
                self.shell.sendline('echo $?')
                self.shell.expect('\\[PROMPT_END\\]# ', timeout=5)
                raw = self.shell.before or ''
                if isinstance(raw, bytes):
                    raw = raw.decode('utf-8', errors='ignore')
                cleaned = ansi_escape.sub('', raw)
                code_str = cleaned.strip().split('\n')[-1].strip()
                return int(code_str)
            except (pexpect.TIMEOUT, pexpect.EOF, ValueError) as e:
                # Don't fail silently — the reported exit code is a GUESS here
                logger.warning(
                    "exit_code_retrieval_failed",
                    session_id=self.session_id,
                    error=type(e).__name__,
                    assumed_exit_code=1,
                )
                return 1

        exit_code = await loop.run_in_executor(None, _get_exit_code)

        full_output = ''.join(accumulated_output)
        # Remove any trailing prompt marker remnants
        full_output = full_output.replace(prompt_marker, '').strip()
        cleaned_output = ansi_escape.sub('', full_output).strip()

        # ── Broadcast command completion summary to Agent Terminal ───────
        ts = time.strftime('%H:%M:%S')
        if exit_code == 0:
            await _broadcast({
                'type': 'agent_log',
                'data': f'\x1b[90m[{ts}]\x1b[0m \x1b[32m✓ Command succeeded\x1b[0m (exit 0)\r\n',
                'session_id': self.session_id,
            })
        else:
            # Short error summary for Agent Terminal
            error_lines = cleaned_output.strip().split('\n')
            short_error = error_lines[-1][:120] if error_lines else 'Unknown error'
            await _broadcast({
                'type': 'agent_log',
                'data': f'\x1b[90m[{ts}]\x1b[0m \x1b[31m✗ Command failed\x1b[0m (exit {exit_code}): {short_error}\r\n'
                        f'\x1b[90m  → Full stack trace in App Logs tab\x1b[0m\r\n',
                'session_id': self.session_id,
            })

        # ── Write to log files inside sandbox ───────────────────────────
        def _write_logs():
            try:
                import datetime
                ts_full = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                log_entry = f"[{ts_full}] CMD: {action.command}\n{'='*60}\n{cleaned_output}\n{'='*60}\n\n"
                # Append to app.log
                self.container.exec_run(
                    ['sh', '-c', f'echo {repr(log_entry)} >> /workspace/logs/app.log'],
                    workdir='/workspace'
                )
                # If error, also append to error.log
                if exit_code != 0:
                    self.container.exec_run(
                        ['sh', '-c', f'echo {repr(log_entry)} >> /workspace/logs/error.log'],
                        workdir='/workspace'
                    )
                # Agent log entry (concise)
                agent_entry = f"[{ts_full}] {'OK' if exit_code == 0 else 'FAIL'} ({exit_code}): {action.command}\n"
                self.container.exec_run(
                    ['sh', '-c', f'echo {repr(agent_entry)} >> /workspace/logs/agent.log'],
                    workdir='/workspace'
                )
            except Exception:
                pass
        await loop.run_in_executor(None, _write_logs)

        return {'output': cleaned_output, 'exit_code': exit_code}

    # ── Health check (from OpenHands) ───────────────────────────────────

    async def health_check(self, port: int = 3000) -> dict:
        """
        Check if an app is running on the given port inside the sandbox.
        Returns status and HTTP response code.
        """
        host_port = None
        for ep in self.exposed_ports:
            if ep.container_port == port:
                host_port = ep.host_port
                break

        if host_port is None:
            return {"healthy": False, "error": f"Port {port} not exposed"}

        try:
            async with httpx.AsyncClient(timeout=self.HEALTH_CHECK_TIMEOUT) as client:
                resp = await client.get(f"http://localhost:{host_port}/")
                return {
                    "healthy": resp.status_code < 500,
                    "status_code": resp.status_code,
                    "url": f"http://localhost:{host_port}",
                }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    # ── Status (from OpenHands) ─────────────────────────────────────────

    def get_status(self) -> SandboxInfo:
        """Get the current sandbox status."""
        try:
            self.container.reload()
            docker_status = self.container.status
            status = _DOCKER_STATUS_MAP.get(docker_status, SandboxStatus.ERROR)
        except Exception:
            status = SandboxStatus.MISSING

        return SandboxInfo(
            session_id=self.session_id,
            container_name=self.container_name,
            container_ip=self.container_ip,
            status=status,
            exposed_ports=self.exposed_ports,
        )

    def get_resource_usage(self) -> dict:
        """Return container CPU and memory usage."""
        try:
            stats_data = self.container.stats(stream=False)
            stats = cast(dict, stats_data)
            cpu_total = stats.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
            cpu_prev = stats.get("precpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
            sys_total = stats.get("cpu_stats", {}).get("system_cpu_usage", 0)
            sys_prev = stats.get("precpu_stats", {}).get("system_cpu_usage", 0)
            cpu_delta = cpu_total - cpu_prev
            sys_delta = sys_total - sys_prev
            percpu = stats.get("cpu_stats", {}).get("cpu_usage", {}).get("percpu_usage") or []
            cpu_count = max(len(percpu), 1)
            cpu_percent = (cpu_delta / sys_delta) * cpu_count * 100 if sys_delta > 0 else 0.0

            mem_usage = stats.get("memory_stats", {}).get("usage", 0)
            mem_limit = stats.get("memory_stats", {}).get("limit", 0)
            mem_percent = (mem_usage / mem_limit) * 100 if mem_limit else 0.0

            return {
                "cpu_percent": round(cpu_percent, 2),
                "mem_usage": mem_usage,
                "mem_limit": mem_limit,
                "mem_percent": round(mem_percent, 2),
            }
        except Exception as e:
            logger.error("container_stats_error", session_id=self.session_id, error=str(e))
            return {"error": "Unable to read container stats"}

    def list_files(self, max_depth: int = 5) -> list[str]:
        """List workspace files inside the sandbox."""
        result = self.container.exec_run(
            [
                "find",
                "/workspace",
                "-maxdepth",
                str(max_depth),
                "(",
                "-name", "node_modules",
                "-o", "-name", ".git",
                "-o", "-name", "venv",
                "-o", "-name", ".venv",
                "-o", "-name", ".agents",
                "-o", "-name", ".codex",
                ")",
                "-prune",
                "-o",
                "-type",
                "f",
                "-printf",
                "%P\n",
            ]
        )
        if result.exit_code != 0:
            output = result.output.decode("utf-8", errors="replace")
            raise RuntimeError(output.strip() or "Failed to list workspace files")
        output = result.output.decode("utf-8", errors="replace")
        return sorted(path for path in output.splitlines() if path.strip())

    def read_file(self, path: str) -> str:
        """Read one UTF-8 text file from the sandbox workspace. Returns a placeholder for binary files."""
        safe_path = path.strip().lstrip("/")
        if not safe_path or ".." in safe_path.split("/"):
            raise ValueError("Invalid workspace path")

        bits, _ = self.container.get_archive(f"/workspace/{safe_path}")
        tf = tarfile.open(fileobj=io.BytesIO(b"".join(bits)))
        member = tf.getmembers()[0]
        extracted = tf.extractfile(member)
        if extracted is None:
            raise ValueError(f"{safe_path} is not a file")
        
        raw_bytes = extracted.read()
        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return f"[Binary file: {len(raw_bytes)} bytes. Cannot be displayed in text editor.]"

    def write_file(self, path: str, content: str) -> None:
        """Write one UTF-8 text file to the sandbox workspace."""
        safe_path = path.strip().lstrip("/")
        if not safe_path or ".." in safe_path.split("/"):
            raise ValueError("Invalid workspace path")

        # Create tar file in memory
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            content_bytes = content.encode("utf-8")
            tarinfo = tarfile.TarInfo(name=safe_path)
            tarinfo.size = len(content_bytes)
            tar.addfile(tarinfo, io.BytesIO(content_bytes))
        
        tar_stream.seek(0)
        self.container.put_archive("/workspace", tar_stream.read())


    def download_workspace_zip(self) -> bytes:
        """Download the workspace as a zip archive."""
        bits, _ = self.container.get_archive('/workspace')
        
        tar_buf = io.BytesIO(b"".join(bits))
        zip_buf = io.BytesIO()
        
        with tarfile.open(fileobj=tar_buf) as tar:
            with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for member in tar.getmembers():
                    if member.isfile():
                        f = tar.extractfile(member)
                        if f:
                            name = member.name
                            if name.startswith('workspace/'):
                                name = name[len('workspace/'):]
                            if name:
                                zipf.writestr(name, f.read())
                                
        return zip_buf.getvalue()

    # ── Lifecycle (from OpenHands) ──────────────────────────────────────

    def pause(self) -> bool:
        """Pause the container (preserves state, frees CPU)."""
        try:
            self.container.reload()
            if self.container.status == 'running':
                if hasattr(self, 'shell') and self.shell.isalive():
                    self.shell.close()
                self.container.pause()
                logger.info("container_paused", session_id=self.session_id)
                return True
        except Exception as e:
            logger.error("container_pause_error", session_id=self.session_id, error=str(e))
        return False

    def resume(self) -> bool:
        """Resume a paused container."""
        try:
            self.container.reload()
            if self.container.status == 'paused':
                self.container.unpause()
                self._init_shell()
                logger.info("container_resumed", session_id=self.session_id)
                return True
            elif self.container.status == 'exited':
                self.container.start()
                self._init_shell()
                logger.info("container_restarted", session_id=self.session_id)
                return True
        except Exception as e:
            logger.error("container_resume_error", session_id=self.session_id, error=str(e))
        return False

    # ── Action execution ────────────────────────────────────────────────

    async def execute(self, action: ActionType) -> dict:
        import time
        from agent.observability import ObservabilityManager
        start_time = time.time()
        
        # Capture file content before modification
        prev_content = ""
        if isinstance(action, (FileWriteAction, FileReplaceAction)):
            try:
                prev_content = self.read_file(action.path)
                # Save a version snapshot before the AI overwrites this file
                from agent.file_history import FileHistoryManager
                history = FileHistoryManager()
                await history.save_snapshot(self, action.path, prev_content)
            except Exception:
                pass  # New file or history save failed — not critical

        # Execute inner action logic
        result = await self._execute_inner(action)
        
        # Calculate duration
        duration = round(time.time() - start_time, 2)
        exit_code = result.get('exit_code', 0)
        output = result.get('output', '')
        
        # Log event based on type
        try:
            if isinstance(action, FileReadAction):
                content = result.get('content', '')
                ObservabilityManager().log(
                    session_id=self.session_id,
                    agent_name="Coder Agent",
                    event_type="file_read",
                    description=f"Read file: {action.path}",
                    status="success" if exit_code == 0 else "failed",
                    duration=duration,
                    metadata={
                        "file_path": action.path,
                        "file_size": len(content),
                        "reason": "Inspecting file structure and contents before editing"
                    }
                )
            elif isinstance(action, FileWriteAction):
                import difflib
                if prev_content:
                    old_lines = prev_content.splitlines(keepends=True)
                    new_lines = action.content.splitlines(keepends=True)
                    diff = difflib.unified_diff(
                        old_lines,
                        new_lines,
                        fromfile=f"a/{action.path}",
                        tofile=f"b/{action.path}"
                    )
                    diff_str = "".join(diff)
                    
                    ObservabilityManager().log(
                        session_id=self.session_id,
                        agent_name="Coder Agent",
                        event_type="file_modify",
                        description=f"Modified file: {action.path}",
                        status="success",
                        duration=duration,
                        metadata={
                            "file_path": action.path,
                            "prev_content": prev_content,
                            "new_content": action.content,
                            "diff": diff_str
                        }
                    )
                else:
                    ObservabilityManager().log(
                        session_id=self.session_id,
                        agent_name="Coder Agent",
                        event_type="file_create",
                        description=f"Created file: {action.path}",
                        status="success",
                        duration=duration,
                        metadata={
                            "file_path": action.path,
                            "content_preview": action.content[:400]
                        }
                    )
            elif isinstance(action, FileReplaceAction):
                import difflib
                old_lines = action.target_content.splitlines(keepends=True)
                new_lines = action.replacement_content.splitlines(keepends=True)
                diff = difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=f"a/{action.path}",
                    tofile=f"b/{action.path}"
                )
                diff_str = "".join(diff)
                
                ObservabilityManager().log(
                    session_id=self.session_id,
                    agent_name="Coder Agent",
                    event_type="file_modify",
                    description=f"Patched file: {action.path}",
                    status="success" if exit_code == 0 else "failed",
                    duration=duration,
                    metadata={
                        "file_path": action.path,
                        "diff": diff_str
                    }
                )
            elif isinstance(action, BrowserAction):
                ObservabilityManager().log(
                    session_id=self.session_id,
                    agent_name="Coder Agent",
                    event_type="tool_execution",
                    description=f"Browser action: {action.command} {action.target}",
                    status="success" if exit_code == 0 else "failed",
                    duration=duration,
                    metadata={
                        "tool_name": "browser",
                        "parameters": {"command": action.command, "target": action.target},
                        "input": action.target,
                        "output": output
                    }
                )
            elif isinstance(action, CmdRunAction) and not getattr(action, 'is_hidden', False):
                cmd_lower = action.command.lower()
                is_dependency = any(k in cmd_lower for k in ["npm install", "pip install", "yarn add", "pnpm add", "apt-get install"])
                is_test = any(k in cmd_lower for k in ["npm test", "pytest", "npm run test", "vitest"])
                is_build = any(k in cmd_lower for k in ["npm run build", "vite build", "tsc", "python -m compileall"])
                
                if is_dependency:
                    pkg_name = "unknown"
                    words = action.command.split()
                    for i, word in enumerate(words):
                        if word in ("install", "add") and i + 1 < len(words):
                            pkg_name = words[i+1]
                            break
                    ObservabilityManager().log(
                        session_id=self.session_id,
                        agent_name="Coder Agent",
                        event_type="dependency",
                        description=f"Dependency action: {action.command}",
                        status="success" if exit_code == 0 else "failed",
                        duration=duration,
                        metadata={
                            "package_name": pkg_name,
                            "action": "installed" if "install" in cmd_lower or "add" in cmd_lower else "removed",
                            "version": "latest",
                            "full_command": action.command
                        }
                    )
                elif is_test:
                    passed = 0
                    failed = 0
                    tests_run = 0
                    if "passed" in output or "failed" in output:
                        import re
                        p_match = re.search(r'(\d+)\s+passed', output)
                        f_match = re.search(r'(\d+)\s+failed', output)
                        passed = int(p_match.group(1)) if p_match else 0
                        failed = int(f_match.group(1)) if f_match else 0
                        tests_run = passed + failed
                    ObservabilityManager().log(
                        session_id=self.session_id,
                        agent_name="Validator Agent",
                        event_type="testing",
                        description=f"Executed tests: {action.command}",
                        status="success" if exit_code == 0 else "failed",
                        duration=duration,
                        metadata={
                            "tests_run": tests_run or (1 if exit_code == 0 else 0),
                            "passed": passed or (1 if exit_code == 0 else 0),
                            "failed": failed or (1 if exit_code != 0 else 0),
                            "coverage": 100 if exit_code == 0 else 0,
                            "failure_details": output if exit_code != 0 else ""
                        }
                    )
                elif is_build:
                    ObservabilityManager().log(
                        session_id=self.session_id,
                        agent_name="Coder Agent",
                        event_type="build",
                        description=f"Compilation/build: {action.command}",
                        status="success" if exit_code == 0 else "failed",
                        duration=duration,
                        metadata={
                            "stage": "Compilation / Bundling",
                            "output": output,
                            "exit_code": exit_code
                        }
                    )
                else:
                    ObservabilityManager().log(
                        session_id=self.session_id,
                        agent_name="Coder Agent",
                        event_type="terminal",
                        description=f"Terminal command: {action.command}",
                        status="success" if exit_code == 0 else "failed",
                        duration=duration,
                        metadata={
                            "command": action.command,
                            "output": output,
                            "exit_code": exit_code
                        }
                    )
                
                if exit_code != 0:
                    ObservabilityManager().log(
                        session_id=self.session_id,
                        agent_name="Coder Agent",
                        event_type="error",
                        description="Terminal command failed",
                        status="failed",
                        duration=duration,
                        metadata={
                            "error_type": "CommandExecutionError",
                            "file_name": "Terminal",
                            "line_number": 1,
                            "stack_trace": output,
                            "error_message": f"Command '{action.command}' failed with exit code {exit_code}"
                        }
                    )
        except Exception as exc:
            logger.warning("obs_log_execution_failed", error=str(exc))

        return result

    async def _execute_inner(self, action: ActionType) -> dict:
        if isinstance(action, CmdRunAction):
            return await self._execute_cmd_interactive(action)

        elif isinstance(action, BrowserAction):
            browser = await PlaywrightManager.get_instance()
            target = action.target
            # Replace localhost with host-mapped port (more reliable than container IP)
            if 'localhost' in target or '127.0.0.1' in target:
                port_match = re_mod.search(r':(\d+)', target)
                if port_match:
                    container_port = int(port_match.group(1))
                    for ep in self.exposed_ports:
                        if ep.container_port == container_port:
                            target = re_mod.sub(
                                r'(localhost|127\.0\.0\.1):\d+',
                                f'localhost:{ep.host_port}',
                                target,
                            )
                            break
                else:
                    target = (
                        target
                        .replace('localhost', self.container_ip)
                        .replace('127.0.0.1', self.container_ip)
                    )
            return await browser.execute_action(action.command, target)

        elif isinstance(action, FileWriteAction):
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode='w') as tar:
                data = action.content.encode('utf-8')
                info = tarfile.TarInfo(name=action.path)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            buf.seek(0)
            self.container.put_archive('/workspace', buf)
            return {'status': 'written', 'path': action.path, 'exit_code': 0, 'output': f"Created {action.path}"}

        elif isinstance(action, FileReplaceAction):
            try:
                content = self.read_file(action.path)
                if action.target_content in content:
                    new_content = content.replace(action.target_content, action.replacement_content)
                    
                    buf = io.BytesIO()
                    with tarfile.open(fileobj=buf, mode='w') as tar:
                        data = new_content.encode('utf-8')
                        info = tarfile.TarInfo(name=action.path)
                        info.size = len(data)
                        tar.addfile(info, io.BytesIO(data))
                    buf.seek(0)
                    self.container.put_archive('/workspace', buf)
                    return {'status': 'replaced', 'path': action.path, 'exit_code': 0, 'output': f"Patched {action.path}"}
                else:
                    return {'error': 'Target content not found in file', 'exit_code': 1, 'output': f"Target block not found in {action.path}"}
            except Exception as e:
                return {'error': str(e), 'exit_code': 1, 'output': f"Failed to patch {action.path}: {str(e)}"}

        elif isinstance(action, FileReadAction):
            try:
                content = self.read_file(action.path)
                return {'content': content, 'exit_code': 0, 'output': f"Read {action.path}"}
            except Exception as e:
                return {'error': str(e), 'exit_code': 1, 'output': f"Failed to read {action.path}: {str(e)}"}

        return {'output': 'Unsupported action', 'exit_code': 1}

    # ── Cleanup ─────────────────────────────────────────────────────────

    def cleanup(self):
        """Stop and remove the container."""
        logger.info("container_cleanup", session_id=self.session_id)
        try:
            if hasattr(self, 'shell') and self.shell.isalive():
                self.shell.close()
            self.container.stop(timeout=10)
            try:
                self.container.remove()
            except Exception:
                pass
        except Exception as e:
            logger.error("container_cleanup_error", session_id=self.session_id, error=str(e))

        self._local_cache.pop(self.session_id, None)
        cleanup_interactive_queue(self.session_id)
        try:
            r = _get_redis()
            r.delete(f"{self.REDIS_KEY_PREFIX}{self.session_id}")
        except Exception:
            pass
