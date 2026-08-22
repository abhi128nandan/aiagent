"""
Agent graph nodes — plan, implement, execute, validate.

Integrates:
  - Context Manager (Phase 1): token counting and message pruning
  - Error Analyzer (Phase 2): intelligent error classification and suggestions
  - Workspace Indexer (Phase 3): project structure awareness
  - Memory Manager (Phase 1): long-term memory compression
"""
import re
import asyncio
from langchain_core.messages import HumanMessage, AIMessage
from .llm import LLMFactory
from .prompts import plan_bootstrap_prompt, plan_refine_prompt, implement_prompt
from .state import AgentState
from runtime import DockerRuntime
from .schema import (
    CmdRunAction, FileWriteAction, FileReplaceAction, FinishAction, BrowserAction, WebSearchAction,
    UnknownAction, ActionType, CmdOutputObservation, BrowserObservation,
    ErrorObservation, ValidatedObservation,
)
from .context_manager import ContextManager, count_message_tokens
from .error_analyzer import ErrorAnalyzer
from .workspace_indexer import WorkspaceIndexer
from .memory import MemoryManager
from .static_validator import StaticValidator
from .workspace_context import get_architectural_constraints
from core.config import get_settings
from core.logger import get_logger
from models.llm_profile import LLMProfile

settings = get_settings()
logger = get_logger(__name__)

DYNAMIC_SCAFFOLD_TEMPLATES = {
    "vue":         {"command": "npm create vite@latest . -- --template vue", "run_command": "npm run dev -- --host 0.0.0.0 > app.log 2>&1 &"},
    "angular":     {"command": "npx -y @angular/cli new . --skip-git --defaults", "run_command": "ng serve --host 0.0.0.0 > app.log 2>&1 &"},
    "nextjs":      {"command": "npx -y create-next-app@latest . --ts --app --no-git --yes", "run_command": "npm run dev -- --hostname 0.0.0.0 > app.log 2>&1 &"},
    "fastapi":     {"command": "pip install fastapi uvicorn --break-system-packages", "run_command": "uvicorn main:app --host 0.0.0.0 --port 8000 > app.log 2>&1 &"},
    "flask":       {"command": "pip install flask --break-system-packages", "run_command": "python3 app.py > app.log 2>&1 &"},
    "django":      {"command": "pip install django --break-system-packages && django-admin startproject core .", "run_command": "python3 manage.py runserver 0.0.0.0:8000 > app.log 2>&1 &"},
    "spring_boot": {"command": "curl -s https://start.spring.io/starter.zip -d dependencies=web -o project.zip && unzip -o project.zip && rm project.zip", "run_command": "./mvnw spring-boot:run > app.log 2>&1 &"},
}

# ── Module-level singletons ────────────────────────────────────────────

_error_analyzer = ErrorAnalyzer()
_static_validator = StaticValidator()
_memory_managers: dict[str, MemoryManager] = {}
_session_paused_events: dict[str, asyncio.Event] = {}


def get_session_resume_event(session_id: str) -> asyncio.Event:
    if session_id not in _session_paused_events:
        event = asyncio.Event()
        event.set()
        _session_paused_events[session_id] = event
    return _session_paused_events[session_id]


async def check_paused(session_id: str | None):
    if not session_id:
        return
    event = get_session_resume_event(session_id)
    if not event.is_set():
        logger.info("agent_paused_waiting_for_resume", session_id=session_id)
        await event.wait()
        logger.info("agent_resumed_from_pause", session_id=session_id)


def _get_memory_manager(session_id: str) -> MemoryManager:
    """Get or create a MemoryManager for a session."""
    if session_id not in _memory_managers:
        _memory_managers[session_id] = MemoryManager()
    return _memory_managers[session_id]


def _resolve_llm(state: AgentState, role: str | None = None):
    # Dynamic role resolution based on subagent state
    status = state.get("status")
    if role == "coder":
        if status == "backend_subagent":
            role = "backend"
        elif status == "frontend_subagent":
            role = "frontend"

    from services.settings_service import SettingsService
    try:
        settings_svc = SettingsService()
        app_settings = settings_svc.get_settings()
        
        # Check if there's a specific profile mapped to this role
        if role:
            role_profile_id = app_settings.get(f"role_profile_{role}")
            if role_profile_id:
                profile = settings_svc.get_profile(role_profile_id)
                if profile:
                    factory = LLMFactory()
                    return factory.create(provider=profile.provider, model_name=profile.model, role=role)
    except Exception as e:
        logger.warning("failed_to_load_role_profile", error=str(e))

    # Fallback to session default
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
        
    return factory.create(provider=provider, model_name=model_name, role=role)


def _get_model_name(state: AgentState, role: str | None = None) -> str:
    """Extract the model name from state for context management."""
    status = state.get("status")
    if role == "coder":
        if status == "backend_subagent":
            role = "backend"
        elif status == "frontend_subagent":
            role = "frontend"
            
    from services.settings_service import SettingsService
    try:
        settings_svc = SettingsService()
        app_settings = settings_svc.get_settings()
        if role:
            role_profile_id = app_settings.get(f"role_profile_{role}")
            if role_profile_id:
                profile = settings_svc.get_profile(role_profile_id)
                if profile and profile.model:
                    return profile.model
    except Exception:
        pass
        
    profile_data = state.get("llm_profile")
    if isinstance(profile_data, LLMProfile):
        return profile_data.model or ""
    if isinstance(profile_data, dict):
        return profile_data.get("model", "")
    return settings.DEFAULT_LLM_MODEL or ""


def extract_plan_json(content: str) -> str:
    """Keep planner output to the first valid JSON block."""
    import json as _json
    import re

    def sanitize_json_string(s: str) -> str:
        # Strip backtick blocks assigned to content/code/diff/implementation
        s = re.sub(r'"(?:content|code|diff|implementation)"\s*:\s*`[\s\S]*?`\s*,?', '', s)
        
        # Strip double-quoted blocks assigned to content/code/diff/implementation
        schema_keys = ["file", "action", "description", "steps", "api_contract", "project", "tech_stack", "environment", "template_selected", "run_command"]
        keys_pattern = "|".join(schema_keys)
        pattern = r'"(?:content|code|diff|implementation)"\s*:\s*[\s\S]*?(?=\s*,\s*"(?:' + keys_pattern + r')"\s*:|\s*,\s*\}|\s*\})'
        s = re.sub(pattern, '', s)
        
        # Remove trailing commas inside objects and arrays
        s = re.sub(r',\s*\}', '}', s)
        s = re.sub(r',\s*\]', ']', s)
        return s

    fenced = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
    candidate = fenced.group(1).strip() if fenced else content.strip()

    # Fast path: try parsing the whole candidate
    try:
        if candidate.startswith('{') or candidate.startswith('['):
            _json.loads(candidate)
            return candidate
    except _json.JSONDecodeError:
        pass

    # Try sanitizing the candidate
    sanitized = sanitize_json_string(candidate)
    try:
        if sanitized.startswith('{') or sanitized.startswith('['):
            _json.loads(sanitized)
            return sanitized
    except _json.JSONDecodeError:
        pass

    # Fallback path: find the first { and the last }
    start = candidate.find('{')
    end = candidate.rfind('}')
    if start >= 0 and end > start:
        sliced = candidate[start:end+1]
        try:
            _json.loads(sliced)
            return sliced
        except _json.JSONDecodeError:
            pass

        # Try sanitizing the sliced candidate
        sanitized_sliced = sanitize_json_string(sliced)
        try:
            _json.loads(sanitized_sliced)
            return sanitized_sliced
        except _json.JSONDecodeError:
            pass

    return candidate


def infer_path_from_text(text: str) -> str | None:
    # Look for paths or files in backticks or quotes
    quoted_paths = re.findall(r'[`\'"]([\w\-./]+\.[a-zA-Z0-9]{2,4})[`\'"]', text)
    if quoted_paths:
        return quoted_paths[-1]
    
    # Otherwise, look for raw paths
    raw_paths = re.findall(r'[\w\-./]+\.[a-zA-Z0-9]{2,4}', text)
    if raw_paths:
        for p in reversed(raw_paths):
            p_clean = p.strip()
            if not p_clean.startswith(('http', 'www', 'v1', 'v2', 'v3')):
                if '/' in p_clean or p_clean.split('.')[-1].lower() in ['py', 'js', 'jsx', 'tsx', 'ts', 'html', 'css', 'json', 'yaml', 'yml', 'sh', 'txt']:
                    return p_clean
    return None


def sanitize_command(command: str) -> str:
    cmd = command.strip()
    
    # 1. Auto-create folders on 'cd' if target does not exist
    if cmd.startswith("cd ") and "&&" not in cmd:
        target_dir = cmd[3:].strip().replace('"', '').replace("'", "")
        if target_dir not in ['.', '..', '/']:
            return f"mkdir -p {target_dir} && cd {target_dir}"

    # 2. Force remove files to prevent non-existent file exit-code errors
    if cmd.startswith("rm ") and "-f" not in cmd:
        return cmd.replace("rm ", "rm -f ")

    # 3. Ensure background processes run detached and free ports first
    is_server_cmd = any(k in cmd for k in ["npm start", "npm run dev", "npm run start", "vite", "python3 main.py", "python3 app.py", "python main.py", "python app.py"])
    if is_server_cmd:
        clean_cmd = cmd.rstrip("&").strip()
        ports_to_kill = "3000 5173 8000 5000 8080"
        # Prepend port-killing commands using fuser (fast, local) and fallback npx kill-port
        kill_cmd = f"fuser -k {ports_to_kill.replace(' ', '/tcp ')}/tcp 2>/dev/null || npx -y kill-port {ports_to_kill} 2>/dev/null || true"
        return f"{kill_cmd} && {clean_cmd} > dev_server.log 2>&1 &"

    return cmd


async def update_tasks_todo(runtime: 'DockerRuntime', session_id: str, state: AgentState):
    import json as _json
    from agent.schema import FileWriteAction, CmdRunAction
    
    plan_str = state.get('plan', '{}')
    if not plan_str:
        return
    try:
        plan_data = _json.loads(plan_str)
    except Exception:
        return
        
    steps = plan_data.get('steps', [])
    if not steps:
        return
        
    todo_content = f"# Project: {plan_data.get('project', 'My App')}\n\n"
    todo_content += f"## Description\n{plan_data.get('description', '')}\n\n"
    todo_content += "## Tasks Checklist\n\n"
    
    for step in steps:
        fpath = step.get('file', '')
        if not fpath:
            continue
        
        # Check if file exists inside container silently (bypass observability logs)
        import asyncio
        loop = asyncio.get_event_loop()
        def _silent_check(f=fpath):
            try:
                res = runtime.container.exec_run(f"test -f '/workspace/{f}'")
                return res.exit_code == 0
            except Exception:
                return False
        exists = await loop.run_in_executor(None, _silent_check)
        
        action_name = step.get('action', 'modify').lower()
        
        # Standard boilerplate files must ALWAYS be checked against modified_files
        boilerplate_files = {'src/App.jsx', 'src/App.tsx', 'src/main.jsx', 'src/index.css', 'src/App.css', 'App.jsx', 'App.tsx'}
        is_boilerplate_path = fpath in boilerplate_files or fpath.lstrip('/') in boilerplate_files
        
        if action_name == 'create' and not is_boilerplate_path:
            completed = exists
        else:
            # For modify/run/etc, or boilerplate files, check if the file was modified in this session
            modified_list = state.get('modified_files', [])
            completed = fpath in modified_list or fpath.lstrip('/') in [m.lstrip('/') for m in modified_list]
            
        status_icon = "[x]" if completed else "[ ]"
        action_name_upper = action_name.upper()
        todo_content += f"- {status_icon} **{action_name_upper}** `{fpath}`\n"
        todo_content += f"  *Description:* {step.get('description', '')}\n\n"
        
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        def _silent_write():
            import tarfile, io, time
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                tarinfo = tarfile.TarInfo(name="tasks_todo.md")
                content_bytes = todo_content.encode('utf-8')
                tarinfo.size = len(content_bytes)
                tarinfo.mtime = int(time.time())
                tar.addfile(tarinfo, io.BytesIO(content_bytes))
            tar_stream.seek(0)
            runtime.container.put_archive('/workspace', tar_stream)
        await loop.run_in_executor(None, _silent_write)
    except Exception as e:
        logger.warning("failed_to_write_tasks_todo", session_id=session_id, error=str(e))


MICROAGENTS = {
    "react": """
## React (Vite/Next) Coding Guidelines
- Use modern functional components with hooks. Do not use legacy class components.
- Import CSS styles directly (e.g. `import './App.css'`).
- Always run `npx -y kill-port 3000 5173` or similar tool before launching development servers.
- Check that all component references are correctly case-matched (e.g. `App.jsx` vs `app.jsx`).
- **CRITICAL**: When scaffolding a React + Vite project (which creates default boilerplate files), you MUST replace or modify `src/App.jsx` (or `src/App.tsx`) to render the actual application UI. Do NOT leave the default Vite counter boilerplate in place. The entry rendering flow must be updated so that the new UI is immediately visible.
""",
    "python": """
## Python Development Guidelines
- Strictly conform to PEP-8 styling standards.
- Incorporate proper try-except error catching blocks for IO and network actions.
- List all dependencies in `requirements.txt`.
""",
    "abap": """
## Senior SAP ABAP Enterprise Architect Guidelines
- Do NOT attempt to compile, execute, preview, or validate the ABAP code locally.
- Generate source code only. Assume the code will later be imported into SAP.
- Follow the 16-stage methodology (Requirement Analysis -> Business Domain Detection -> ... -> Documentation).
- Every business module must have its own package (e.g., ZCORE, ZAUTH).
- Output comprehensive repository folders (packages/, dictionary/, classes/, etc.).
"""
}


def parse_yaml_frontmatter(content: str) -> tuple[dict, str]:
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return {}, content
    
    frontmatter_text = match.group(1)
    body = content[match.end():]
    
    metadata = {}
    triggers = []
    current_key = None
    for line in frontmatter_text.splitlines():
        line_str = line.strip()
        if not line_str:
            continue
        if line_str.startswith('-'):
            if current_key == 'triggers':
                triggers.append(line_str[1:].strip().strip('"').strip("'"))
        elif ':' in line_str:
            parts = line_str.split(':', 1)
            key = parts[0].strip()
            val = parts[1].strip()
            current_key = key
            if key == 'triggers' and val:
                if val.startswith('[') and val.endswith(']'):
                    triggers = [t.strip().strip('"').strip("'") for t in val[1:-1].split(',')]
    metadata['triggers'] = triggers
    return metadata, body


# Module-level microagent cache (avoid repeated disk I/O)
_cached_global_microagents: list[dict] | None = None


def load_global_microagents() -> list[dict]:
    global _cached_global_microagents
    if _cached_global_microagents is not None:
        return _cached_global_microagents

    import os
    microagents = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    microagents_dir = os.path.join(base_dir, "microagents")
    if not os.path.exists(microagents_dir):
        return []
    
    try:
        for filename in os.listdir(microagents_dir):
            if filename.endswith(".md"):
                filepath = os.path.join(microagents_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                metadata, body = parse_yaml_frontmatter(content)
                microagents.append({
                    'filename': filename,
                    'triggers': metadata.get('triggers', []),
                    'content': body.strip()
                })
    except Exception as e:
        logger.error("error_loading_global_microagents", error=str(e))
    
    _cached_global_microagents = microagents
    return microagents


async def load_workspace_repo_agent(runtime) -> str | None:
    try:
        check_res = await runtime.execute(CmdRunAction(command="test -f /workspace/.myaiagent/repo.md", is_hidden=True))
        if check_res.get('exit_code') == 0:
            cat_res = await runtime.execute(CmdRunAction(command="cat /workspace/.myaiagent/repo.md", is_hidden=True))
            if cat_res.get('exit_code') == 0:
                return cat_res.get('output', '').strip()
    except Exception as e:
        logger.warning("failed_to_load_workspace_repo_agent", error=str(e))
    return None


async def get_dynamic_microagent_instructions(plan_str: str, message_history: list, runtime, session_id: str = "") -> str:
    instructions = []
    
    # 1. Check for Repository-specific instructions first
    repo_agent_content = await load_workspace_repo_agent(runtime)
    if repo_agent_content:
        instructions.append("## Repository-Specific Guidelines\n" + repo_agent_content)
    
    # 2. Load AGENTS.md knowledge vault (cached per session)
    try:
        from agent.rules_loader import AgentsRulesLoader
        agents_rules = AgentsRulesLoader.get_rules(session_id, plan_str, message_history)
        if agents_rules:
            instructions.append(agents_rules)
    except Exception as e:
        logger.warning("agents_md_load_failed", error=str(e))
    
    # 3. Match global microagents
    # Combine plan and latest message content to search for keywords
    context_text = plan_str.lower()
    for msg in message_history[-3:]:
        if hasattr(msg, 'content') and isinstance(msg.content, str):
            context_text += " " + msg.content.lower()
    
    global_microagents = load_global_microagents()
    matched_agents = []
    for agent in global_microagents:
        for trigger in agent['triggers']:
            if re.search(r'\b' + re.escape(trigger.lower()) + r'\b', context_text):
                matched_agents.append(agent)
                break
    
    for agent in matched_agents:
        instructions.append(agent['content'])
        
    # Fallback to hardcoded MICROAGENTS to maintain backward compatibility
    if not instructions:
        plan_lower = plan_str.lower()
        for key, rule in MICROAGENTS.items():
            if key in plan_lower:
                instructions.append(rule.strip())
                
    return "\n\n".join(instructions) if instructions else ""


def clean_cdata(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("<![CDATA[") and cleaned.endswith("]]>"):
        cleaned = cleaned[9:-3].strip()
    # Strip markdown code blocks wrapping the content (e.g. ```javascript ... ```)
    fenced_match = re.match(r"^```\w*\s*([\s\S]*?)\s*```$", cleaned)
    if fenced_match:
        cleaned = fenced_match.group(1).strip()
    # Handle nested CDATA inside markdown block
    if cleaned.startswith("<![CDATA[") and cleaned.endswith("]]>"):
        cleaned = cleaned[9:-3].strip()
    return cleaned


def detect_language_from_content(content: str) -> str | None:
    stripped = content.strip()
    if stripped.startswith('<') and ('html' in stripped[:100].lower() or '!doctype' in stripped[:100].lower() or 'div' in stripped.lower()):
        return 'html'
    if ':root' in stripped or 'body {' in stripped or 'margin:' in stripped or '@media' in stripped or 'color:' in stripped:
        return 'css'
    if 'document.add' in stripped or 'const ' in stripped or 'let ' in stripped or 'function(' in stripped or '=>' in stripped:
        return 'javascript'
    if 'def ' in stripped and ':' in stripped:
        return 'python'
    return None


def guess_path_from_language(language: str | None, plan_files: list[str] | None = None) -> str | None:
    if not plan_files or not language:
        return None
    
    lang = language.lower().strip()
    exts = []
    if lang in ['css']:
        exts = ['.css']
    elif lang in ['js', 'javascript', 'jsx']:
        exts = ['.js', '.jsx']
    elif lang in ['ts', 'typescript', 'tsx']:
        exts = ['.ts', '.tsx']
    elif lang in ['html', 'htm']:
        exts = ['.html', '.htm']
    elif lang in ['py', 'python']:
        exts = ['.py']
    elif lang in ['json']:
        exts = ['.json']
    elif lang in ['abap']:
        exts = ['.abap']
    
    if not exts:
        return None
        
    filtered = [f for f in plan_files if any(f.endswith(ext) for ext in exts)]
    if len(filtered) == 1:
        return filtered[0]
    return None


def parse_action(content: str, plan_files: list[str] | None = None) -> ActionType:
    """Extracts XML tags like <run>, <write path="...">, <think>, <finish> with robust fallback handling."""
    matches = []

    # 1. Standard Matching (with closing tags)
    for match in re.finditer(r'<run(?:_command|-command)?\s*>(.*?)</run(?:_command|-command)?\s*>', content, re.DOTALL | re.IGNORECASE):
        matches.append((match.start(), CmdRunAction(command=match.group(1).strip())))

    for match in re.finditer(r'<run(?:_command|-command)?\s+[^>]*?command\s*=\s*(?:[\'"]([^\'"]*)[\'"]|([^\s>]+))[^>]*?/?>', content, re.IGNORECASE):
        cmd = match.group(1) or match.group(2)
        matches.append((match.start(), CmdRunAction(command=cmd.strip())))

    for match in re.finditer(r'<write(?:_file|-file)?\s+[^>]*?path\s*=\s*(?:[\'"]([^\'"]*)[\'"]|([^\s>]+))[^>]*?>(.*?)</write(?:_file|-file)?\s*>', content, re.DOTALL | re.IGNORECASE):
        path = match.group(1) or match.group(2)
        write_content = clean_cdata(match.group(3).strip())
        matches.append((match.start(), FileWriteAction(path=path.strip(), content=write_content)))

    for match in re.finditer(
        r'<replace\s+[^>]*?path\s*=\s*(?:[\'"]([^\'"]*)[\'"]|([^\s>]+))[^>]*?>\s*<<<<\n(.*?)\n====\n(.*?)\n>>>>\n</replace>',
        content, re.DOTALL | re.IGNORECASE
    ):
        path = match.group(1) or match.group(2)
        target = match.group(3)
        replacement = match.group(4)
        matches.append((match.start(), FileReplaceAction(path=path.strip(), target_content=target, replacement_content=replacement)))

    for match in re.finditer(r'<browse\s+[^>]*?command\s*=\s*(?:[\'"]([^\'"]*)[\'"]|([^\s>]+))[^>]*?target\s*=\s*(?:[\'"]([^\'"]*)[\'"]|([^\s>]+))[^>]*?>', content, re.IGNORECASE):
        cmd = match.group(1) or match.group(2)
        target = match.group(3) or match.group(4)
        matches.append((match.start(), BrowserAction(command=cmd.strip(), target=target.strip())))

    for match in re.finditer(r'<search(?:_web|-web)?\s*>(.*?)</search(?:_web|-web)?\s*>', content, re.DOTALL | re.IGNORECASE):
        matches.append((match.start(), WebSearchAction(query=match.group(1).strip())))

    for match in re.finditer(r'<finish(?:_task|-task)?\s*>(.*?)</finish(?:_task|-task)?\s*>', content, re.DOTALL | re.IGNORECASE):
        matches.append((match.start(), FinishAction(message=match.group(1).strip())))

    if matches:
        return min(matches, key=lambda item: item[0])[1]

    # 2. Fallback Matching (for unclosed/truncated tags)
    open_write = re.search(r'<write(?:_file|-file)?\s+[^>]*?path\s*=\s*(?:[\'"]([^\'"]*)[\'"]|([^\s>]+))[^>]*?>', content, re.IGNORECASE)
    if open_write:
        path = open_write.group(1) or open_write.group(2)
        file_content = content[open_write.end():].strip()
        file_content = re.sub(r'</write(?:_file|-file)?\s*>\s*$', '', file_content, flags=re.IGNORECASE)
        file_content = clean_cdata(file_content)
        return FileWriteAction(path=path.strip(), content=file_content)

    open_run = re.search(r'<run(?:_command|-command)?\s*>', content, re.IGNORECASE)
    if open_run:
        cmd = content[open_run.end():].strip()
        cmd = re.sub(r'</run(?:_command|-command)?\s*>\s*$', '', cmd, flags=re.IGNORECASE)
        return CmdRunAction(command=cmd)

    open_search = re.search(r'<search(?:_web|-web)?\s*>', content, re.IGNORECASE)
    if open_search:
        q = content[open_search.end():].strip()
        q = re.sub(r'</search(?:_web|-web)?\s*>\s*$', '', q, flags=re.IGNORECASE)
        return WebSearchAction(query=q)

    open_finish = re.search(r'<finish(?:_task|-task)?\s*>', content, re.IGNORECASE)
    if open_finish:
        msg = content[open_finish.end():].strip()
        msg = re.sub(r'</finish(?:_task|-task)?\s*>\s*$', '', msg, flags=re.IGNORECASE)
        return FinishAction(message=msg)

    # 3. Fallback: Parse markdown code blocks (bolt-style)
    code_block_match = re.search(r'```(\w*)\n([\s\S]*?)```', content)
    if code_block_match:
        language = code_block_match.group(1).lower()
        code_content = code_block_match.group(2).strip()

        # If it is shell, run it
        if language in ['bash', 'sh', 'shell', 'zsh']:
            return CmdRunAction(command=code_content)
        
        # Else, try to infer the file path
        preceding_text = content[:code_block_match.start()]
        inferred = infer_path_from_text(preceding_text)
        if not inferred:
            inferred = guess_path_from_language(language, plan_files)
        if inferred:
            return FileWriteAction(path=inferred, content=code_content)

    # 4. Fallback: Parse CDATA blocks directly
    cdata_match = re.search(r'<!\[CDATA\[([\s\S]*?)\]\]>', content)
    if cdata_match:
        code_content = cdata_match.group(1).strip()
        preceding_text = content[:cdata_match.start()]
        inferred = infer_path_from_text(preceding_text)
        if not inferred:
            lang = detect_language_from_content(code_content)
            inferred = guess_path_from_language(lang, plan_files)
        if inferred:
            return FileWriteAction(path=inferred, content=code_content)

    return UnknownAction(content=content)


def parse_all_actions(content: str, plan_files: list[str] | None = None) -> list[ActionType]:
    """Extract ALL actions from LLM response in document order.
    
    Enables multi-action per turn: the LLM can batch multiple
    <write> and <run> tags in a single response, or falls back to
    multiple markdown code blocks.
    """
    matches: list[tuple[int, ActionType]] = []

    # Parse XML tags
    for match in re.finditer(r'<run(?:_command|-command)?\s*>(.*?)</run(?:_command|-command)?\s*>', content, re.DOTALL | re.IGNORECASE):
        matches.append((match.start(), CmdRunAction(command=match.group(1).strip())))

    for match in re.finditer(r'<run(?:_command|-command)?\s+[^>]*?command\s*=\s*(?:[\'"]([^\'"]*)[\'"]|([^\s>]+))[^>]*?/?>', content, re.IGNORECASE):
        cmd = match.group(1) or match.group(2)
        matches.append((match.start(), CmdRunAction(command=cmd.strip())))

    for match in re.finditer(
        r'<write(?:_file|-file)?\s+[^>]*?path\s*=\s*(?:[\'"]([^\'"]*)[\'"]|([^\s>]+))[^>]*?>(.*?)</write(?:_file|-file)?\s*>',
        content, re.DOTALL | re.IGNORECASE
    ):
        path = match.group(1) or match.group(2)
        write_content = clean_cdata(match.group(3).strip())
        matches.append((match.start(), FileWriteAction(path=path.strip(), content=write_content)))

    for match in re.finditer(
        r'<replace\s+[^>]*?path\s*=\s*(?:[\'"]([^\'"]*)[\'"]|([^\s>]+))[^>]*?>\s*<<<<\n(.*?)\n====\n(.*?)\n>>>>\n</replace>',
        content, re.DOTALL | re.IGNORECASE
    ):
        path = match.group(1) or match.group(2)
        target = match.group(3)
        replacement = match.group(4)
        matches.append((match.start(), FileReplaceAction(path=path.strip(), target_content=target, replacement_content=replacement)))

    for match in re.finditer(r'<search(?:_web|-web)?\s*>(.*?)</search(?:_web|-web)?\s*>', content, re.DOTALL | re.IGNORECASE):
        matches.append((match.start(), WebSearchAction(query=match.group(1).strip())))

    for match in re.finditer(r'<finish(?:_task|-task)?\s*>(.*?)</finish(?:_task|-task)?\s*>', content, re.DOTALL | re.IGNORECASE):
        matches.append((match.start(), FinishAction(message=match.group(1).strip())))

    # If any standard XML actions are matched, return them in order
    if matches:
        matches.sort(key=lambda item: item[0])
        return [action for _, action in matches]

    # Fallback to parsing markdown code blocks
    prev_end = 0
    for match in re.finditer(r'```(\w*)\n([\s\S]*?)```', content):
        language = match.group(1).lower()
        code_content = match.group(2).strip()
        start_idx = match.start()

        if language in ['bash', 'sh', 'shell', 'zsh']:
            matches.append((start_idx, CmdRunAction(command=code_content)))
        else:
            # Look for path in text between the end of the last block and this block
            preceding_text = content[prev_end:start_idx]
            inferred = infer_path_from_text(preceding_text)
            if not inferred:
                inferred = guess_path_from_language(language, plan_files)
            if inferred:
                matches.append((start_idx, FileWriteAction(path=inferred, content=code_content)))
        prev_end = match.end()

    # Fallback to parsing CDATA blocks directly
    prev_end = 0
    for match in re.finditer(r'<!\[CDATA\[([\s\S]*?)\]\]>', content):
        code_content = match.group(1).strip()
        start_idx = match.start()
        
        preceding_text = content[prev_end:start_idx]
        inferred = infer_path_from_text(preceding_text)
        if not inferred:
            lang = detect_language_from_content(code_content)
            inferred = guess_path_from_language(lang, plan_files)
        if inferred:
            matches.append((start_idx, FileWriteAction(path=inferred, content=code_content)))
        prev_end = match.end()

    matches.sort(key=lambda item: item[0])
    return [action for _, action in matches]


async def execute_actions_batch(
    runtime: 'DockerRuntime',
    actions: list[ActionType],
    session_id: str,
    state: AgentState,
    ws_callback=None,
) -> dict:
    """Execute multiple actions sequentially. Stops on first error or FinishAction."""
    import json as _json
    from .research_node import search_for_error

    observations: list[str] = []
    files_written: list[str] = []
    last_obs = None
    retries = state.get('retries', 0)
    error_history = list(state.get('error_history') or [])
    last_error_analysis = None
    final_status = 'implement'
    succeeded = 0
    failed = 0

    for i, action in enumerate(actions):
        if isinstance(action, CmdRunAction):
            action = CmdRunAction(command=sanitize_command(action.command))
            # Pre-validate command to auto-fix common failure patterns
            from agent.command_validator import CommandValidator
            validator = CommandValidator()
            validated = await validator.validate(action.command, runtime)
            if validated.modified:
                logger.info("command_pre_validated", session_id=session_id,
                            original=action.command[:100], fixed=validated.command[:100],
                            warning=validated.warning)
                action = CmdRunAction(command=validated.command)
                if ws_callback:
                    await ws_callback({"type": "command_auto_fixed", "original": action.command[:100], "fixed": validated.command[:100], "warning": validated.warning})
        action_detail = getattr(action, 'command', getattr(action, 'path', getattr(action, 'query', '')))[:100]
        logger.info("batch_action", session_id=session_id, idx=i+1, total=len(actions), action=action.type, detail=action_detail)

        if ws_callback:
            await ws_callback({"type": "action_exec_start", "action": action.type, "index": i+1, "total": len(actions), "detail": action_detail})

        locked_files = state.get('locked_files', [])
        if isinstance(action, FileWriteAction) and action.path in locked_files:
            logger.warning("write_blocked_locked_file", session_id=session_id, path=action.path)
            err_msg = f"Error: File {action.path} is locked and cannot be modified."
            observations.append(f"[write {action.path}] Locked file. Write blocked.")
            failed += 1
            if ws_callback:
                await ws_callback({"type": "action_exec", "action": "write", "path": action.path, "exit_code": 1, "output": err_msg})
            break

        if isinstance(action, FinishAction):
            final_status = 'validate'
            observations.append(f"[finish] {action.message}")
            succeeded += 1
            break

        if isinstance(action, WebSearchAction):
            tech_context = ''
            try:
                plan = _json.loads(state.get('plan', '{}'))
                ts = plan.get('tech_stack', {})
                tech_context = f"{ts.get('frontend','')} {ts.get('backend','')} {ts.get('language','')}".strip()
            except Exception:
                pass
            search_result = await search_for_error(action.query, tech_context)
            observations.append(f"[search '{action.query}'] {search_result}")
            succeeded += 1
            if ws_callback:
                await ws_callback({"type": "action_exec", "action": "search", "query": action.query[:100], "exit_code": 0, "output": search_result[:200]})
            continue

        # ── Pre-write content alignment check (catches boilerplate/TODOs) ──
        if isinstance(action, FileWriteAction):
            alignment = _static_validator.validate_content_alignment(
                action.path, action.content, state.get('plan', '')
            )
            if not alignment.passed:
                err_msg = f"Content alignment failed for {action.path}:\n" + "\n".join(alignment.errors)
                observations.append(f"[write {action.path}] Content rejected: {err_msg}")
                parsed_error = _error_analyzer.analyze(err_msg, 1)
                last_error_analysis = _error_analyzer.format_for_prompt(parsed_error)
                retries += 1
                failed += 1
                error_history.append({
                    'category': 'structure',
                    'severity': 'high',
                    'message': err_msg[:200],
                    'file': action.path,
                    'line': None,
                })
                last_obs = ErrorObservation(output=err_msg, exit_code=1)
                logger.warning(
                    "pre_write_content_alignment_failed",
                    session_id=session_id,
                    path=action.path,
                    errors=alignment.errors,
                )
                if ws_callback:
                    await ws_callback({
                        "type": "action_exec",
                        "action": "write",
                        "path": action.path,
                        "exit_code": 1,
                        "output": err_msg[:500],
                    })
                break

        # ── Issue #2: Static validation before execution ──────────────
        if isinstance(action, FileWriteAction):
            validation = _static_validator.validate_file(action.path, action.content)
            if not validation.passed:
                # Static validation failed — skip Docker exec, report error
                err_msg = f"Static validation failed for {action.path}:\n" + "\n".join(validation.errors)
                observations.append(f"[write {action.path}] Validation error: {err_msg}")
                parsed_error = _error_analyzer.analyze(err_msg, 1)
                last_error_analysis = _error_analyzer.format_for_prompt(parsed_error)
                retries += 1
                failed += 1
                error_history.append({
                    'category': 'syntax',
                    'severity': 'high',
                    'message': err_msg[:200],
                    'file': action.path,
                    'line': None,
                })
                last_obs = ErrorObservation(output=err_msg, exit_code=1)
                logger.warning(
                    "static_validation_failed",
                    session_id=session_id,
                    path=action.path,
                    errors=validation.errors,
                )
                if ws_callback:
                    await ws_callback({
                        "type": "action_exec",
                        "action": "write",
                        "path": action.path,
                        "exit_code": 1,
                        "output": err_msg[:500],
                    })
                break
            elif validation.warnings:
                logger.info(
                    "static_validation_warnings",
                    session_id=session_id,
                    path=action.path,
                    warnings=validation.warnings,
                )

        if isinstance(action, CmdRunAction):
            try:
                import json as _json
                _plan_obj = _json.loads(state.get('plan', '{}'))
                if _plan_obj.get('tech_stack', {}).get('language') == 'abap':
                    observations.append(f"[{action.type}] exit=0 | Execution skipped for ABAP.")
                    succeeded += 1
                    last_obs = CmdOutputObservation(output="Execution skipped for ABAP.", exit_code=0)
                    if ws_callback:
                        await ws_callback({"type": "action_exec", "action": action.type, "command": getattr(action, 'command', ''), "exit_code": 0, "output": "Execution skipped for ABAP."})
                    continue
            except Exception:
                pass

        obs_dict = await runtime.execute(action)
        exit_code = obs_dict.get('exit_code', 1)
        output = obs_dict.get('output', '')

        if isinstance(action, FileWriteAction):
            files_written.append(action.path)
            _get_memory_manager(session_id).update_working_memory(file_written=action.path)
            # Track structured todo status
            try:
                from agent.todo_manager import TodoManager
                TodoManager(session_id).mark_file_in_progress(action.path)
            except Exception:
                pass

        # Smart truncation: suppress noisy package manager output
        lines = output.splitlines()
        action_detail_lower = action_detail.lower()
        is_pkg_manager = any(kw in action_detail_lower for kw in ['npm', 'pip', 'yarn', 'pnpm', 'apt-get'])
        
        if is_pkg_manager and exit_code == 0:
            # Successful package installs are mostly noise
            truncated = f"[{action.type}] Success ({len(lines)} lines suppressed)"
        elif len(lines) > 30:
            truncated = "\n".join(lines[:5]) + f"\n\n... [{len(lines)-15} lines omitted] ...\n\n" + "\n".join(lines[-10:])
        else:
            truncated = output
        observations.append(f"[{action.type}] exit={exit_code} | {truncated}")

        if ws_callback:
            await ws_callback({"type": "action_exec", "action": action.type, "command": getattr(action, 'command', ''), "path": getattr(action, 'path', ''), "exit_code": exit_code, "output": truncated[:500]})

        if exit_code != 0 or 'error' in obs_dict:
            parsed_error = _error_analyzer.analyze(output, exit_code)
            last_error_analysis = _error_analyzer.format_for_prompt(parsed_error)
            retries += 1
            failed += 1
            error_history.append({'category': parsed_error.category.value, 'severity': parsed_error.severity.value, 'message': parsed_error.message[:200], 'file': parsed_error.file, 'line': parsed_error.line})
            last_obs = ErrorObservation(output=output, exit_code=exit_code)
            logger.error("batch_error", session_id=session_id, idx=i+1, category=parsed_error.category.value)
            break
        else:
            succeeded += 1
            last_obs = CmdOutputObservation(output=output, exit_code=0)

    if ws_callback:
        await ws_callback({"type": "batch_complete", "total": len(actions), "succeeded": succeeded, "failed": failed, "files_written": files_written})

    combined_obs = "\n\n".join(observations)
    if failed > 0:
        obs_msg = f"Batch: {succeeded}/{len(actions)} succeeded, stopped on error.\n\n{combined_obs}"
        if last_error_analysis:
            obs_msg += f"\n\nError analysis:\n{last_error_analysis}"
    else:
        obs_msg = f"Batch: {succeeded}/{len(actions)} completed.\n\n{combined_obs}"

    # Only refresh workspace listing if files were actually written (avoids extra Docker exec)
    workspace_summary = state.get('workspace_summary', '')
    if files_written:
        try:
            ws_result = await runtime.execute(CmdRunAction(command="find /workspace -maxdepth 3 -type f -not -path '*/node_modules/*' -not -path '*/.git/*' | head -100"))
            if ws_result.get('exit_code') == 0 and ws_result.get('output'):
                workspace_summary = f"Current workspace files:\n{ws_result['output'].strip()}"
        except Exception:
            pass

    # Update tasks_todo.md checklist
    try:
        temp_state = state.copy()
        temp_state['modified_files'] = list(state.get('modified_files', [])) + files_written
        await update_tasks_todo(runtime, session_id, temp_state)
    except Exception as e:
        logger.warning("failed_to_update_tasks_todo", session_id=session_id, error=str(e))

    # Persist structured todo state (marks written files as completed)
    try:
        from agent.todo_manager import TodoManager
        todo_mgr = TodoManager(session_id)
        for fp in files_written:
            todo_mgr.mark_file_completed(fp)
        await todo_mgr.save(runtime)
    except Exception as e:
        logger.warning("failed_to_persist_todo_state", session_id=session_id, error=str(e))

    return {
        'last_obs': last_obs,
        'retries': retries,
        'status': final_status,
        'messages': [HumanMessage(content=f"Observation:\n{obs_msg}")],
        # Always a list — `or None` would clobber accumulated history in merge
        'error_history': error_history,
        'last_error_analysis': last_error_analysis,
        'workspace_summary': workspace_summary,
        'modified_files': files_written,
    }


async def plan_bootstrap_node(state: AgentState) -> AgentState:
    """
    Bootstrap Plan Node - Generate project architecture and scaffold command.
    
    This is Phase 1 of two-phase planning. It produces:
    - project, description, tech_stack, environment
    - scaffold_command (e.g., npx -y create-vite@latest ./ --template react)
    - run_command
    - Empty steps[] (file-level steps come in Phase 2: plan_refine_node)
    """
    from .state_manager import merge_state_updates, log_state_transition
    from datetime import datetime, timezone
    
    old_status = state.get('status', 'plan')
    session_id = state.get('session_id', '')
    await check_paused(session_id)
    
    if state.get('chat_mode') == 'discuss':
        updates = {
            'status': 'setup_env',
            'messages': []
        }
        new_state = merge_state_updates(state, updates)
        log_state_transition(session_id, old_status, 'setup_env', {'reason': 'discuss_mode'})
        return new_state

    llm = _resolve_llm(state, role="planner")

    # Log Planner Agent Start Activity
    try:
        from agent.observability import ObservabilityManager
        ObservabilityManager().log(
            session_id=session_id,
            agent_name="Planner Agent",
            event_type="activity",
            description="Planner Agent started requirements analysis and application design",
            status="running",
            metadata={
                "task": "Generating application plan and architecture",
                "progress": 30,
                "status": "running"
            }
        )
    except Exception:
        pass
    
    # We expect the first message to be the SRS text
    from langchain_core.messages import HumanMessage
    messages_list = state.get('messages')
    if not messages_list:
        messages_list = [HumanMessage(content="")]
    srs = messages_list[0].content
    if isinstance(srs, list):
        # Fallback if messages are structured differently
        srs = str(srs)
    judge_feedback = state.get('judge_feedback', '')
    judge_attempts = state.get('judge_attempts', 0)
    
    workspace_context = ""
    workspace_idx_dict = None
    try:
        if session_id:
            import os
            local_ws_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "workspaces", session_id))
            if os.path.exists(local_ws_path):
                user_query = srs
                indexer = WorkspaceIndexer(local_ws_path)
                idx = indexer.index()
                workspace_context = indexer.get_ranked_context(
                    idx,
                    query=user_query,
                    max_tokens=3000
                )
                # Issue #3: Store workspace index and add architectural constraints
                workspace_idx_dict = {
                    'project_type': idx.project_type,
                    'framework': idx.framework,
                    'tech_stack': idx.tech_stack,
                    'dependencies': idx.dependencies,
                    'key_files': idx.key_files,
                    'entry_points': idx.entry_points,
                    'file_count': idx.file_count,
                    'directory_count': idx.directory_count,
                    'structure_tree': idx.structure_tree,
                }
                arch_constraints = get_architectural_constraints(workspace_idx_dict)
                if arch_constraints and arch_constraints != "No specific constraints detected.":
                    workspace_context += f"\n\nARCHITECTURAL CONSTRAINTS (MUST FOLLOW):\n{arch_constraints}"
    except Exception as e:
        logger.warning("plan_workspace_context_failed", error=str(e))
        
    if not workspace_context:
        workspace_context = "No existing workspace files found. This is a new project."
    
    # Run environment discovery before planning
    env_discovery = "Environment discovery unavailable."
    try:
        from runtime import DockerRuntime
        from agent.schema import CmdRunAction
        runtime = DockerRuntime.get(session_id)
        probe_cmd = "echo '--- HOST ENVIRONMENT ---' && uname -a && (cat /etc/os-release 2>/dev/null | grep PRETTY_NAME || true) && (command -v lsof >/dev/null || echo 'WARNING: lsof is not installed. Use pkill or fuser instead.') && (command -v fuser >/dev/null || echo 'WARNING: fuser is not installed. Use pkill instead.') && (command -v pkill >/dev/null || echo 'WARNING: pkill is not installed.')"
        probe_result = await runtime.execute(CmdRunAction(command=probe_cmd))
        env_discovery = probe_result.get('output', 'Environment details unavailable.')
    except Exception as e:
        logger.warning("plan_env_discovery_failed", error=str(e))

    # ── Phase 1: Context Management ────────────────────────────────────
    model_name = _get_model_name(state, role="planner")
    ctx_manager = ContextManager(model=model_name)
    messages = state.get('messages', [])

    # On re-plan (judge rejected), use a lighter prompt with old plan + critique
    # instead of re-processing the full SRS from scratch
    if judge_attempts > 0 and judge_feedback and state.get('plan'):
        fit = ctx_manager.fit_request(
            components={
                'old_plan':              {'text': state.get('plan', '{}'), 'share': 0.30, 'keep': 'head'},
                'critique':              {'text': judge_feedback,          'share': 0.20, 'keep': 'head'},
                'research_context':      {'text': state.get('research_context', 'No research available.'), 'share': 0.20, 'keep': 'head'},
                'environment_discovery': {'text': env_discovery,           'share': 0.08, 'keep': 'tail'},
            },
        )
        pruned_messages = ctx_manager.prune_messages(messages)
        from .prompts import BOOTSTRAP_PLAN_SCHEMA_INSTRUCTIONS
        from langchain_core.prompts import ChatPromptTemplate as _CPT
        replan_prompt = _CPT.from_messages([
            ('system', 'You are an expert software architect. Revise the project plan based on the reviewer critique and web research findings. Output ONLY the corrected JSON plan.'),
            ('human', 'PREVIOUS PLAN:\n{old_plan}\n\nCRITIQUE:\n{critique}\n\nWEB RESEARCH CONTEXT:\n{research_context}\n\nENVIRONMENT DISCOVERY:\n{environment_discovery}\n\n' + BOOTSTRAP_PLAN_SCHEMA_INSTRUCTIONS),
        ])
        from agent.plan_models import BootstrapPlan
        chain = replan_prompt | llm
        from agent.observability import ObservabilityCallbackHandler
        handler = ObservabilityCallbackHandler(session_id, "Planner Agent")
        try:
            response = await chain.ainvoke(fit['components'], config={"callbacks": [handler]})
            raw_text = response.content
            json_str = extract_plan_json(str(raw_text))
            parsed_plan = BootstrapPlan.model_validate_json(json_str)
            plan_json = parsed_plan.model_dump_json()
        except Exception as e:
            logger.error("plan_bootstrap_structured_output_error", session_id=session_id, error=str(e))
            from .state_manager import merge_state_updates
            updates = {
                'status': 'error',
                'plan_error': f"Planner produced invalid structured output: {str(e)}",
                'messages': [AIMessage(content=f"[Planner Error] Invalid output produced: {str(e)}")]
            }
            return merge_state_updates(state, updates)
    else:
        from .prompts import PLANNER_SYSTEM_PROMPT, BOOTSTRAP_PLAN_SCHEMA_INSTRUCTIONS
        fit = ctx_manager.fit_request(
            system_text=PLANNER_SYSTEM_PROMPT + BOOTSTRAP_PLAN_SCHEMA_INSTRUCTIONS,
            components={
                'srs_text':              {'text': srs,               'share': 0.35, 'keep': 'head'},
                'workspace_context':     {'text': workspace_context, 'share': 0.28, 'keep': 'head'},
                'environment_discovery': {'text': env_discovery,     'share': 0.08, 'keep': 'tail'},
                'judge_feedback':        {'text': judge_feedback,    'share': 0.10, 'keep': 'head'},
            },
        )
        pruned_messages = ctx_manager.prune_messages(messages)
        from agent.plan_models import BootstrapPlan
        chain = plan_bootstrap_prompt | llm
        from agent.observability import ObservabilityCallbackHandler
        handler = ObservabilityCallbackHandler(session_id, "Planner Agent")
        try:
            response = await chain.ainvoke(fit['components'], config={"callbacks": [handler]})
            raw_text = response.content
            json_str = extract_plan_json(str(raw_text))
            parsed_plan = BootstrapPlan.model_validate_json(json_str)
            plan_json = parsed_plan.model_dump_json()
        except Exception as e:
            logger.error("plan_bootstrap_structured_output_error", session_id=session_id, error=str(e))
            from .state_manager import merge_state_updates
            updates = {
                'status': 'error',
                'plan_error': f"Planner produced invalid structured output: {str(e)}",
                'messages': [AIMessage(content=f"[Planner Error] Invalid output produced: {str(e)}")]
            }
            return merge_state_updates(state, updates)

    # Update memory with plan
    memory = _get_memory_manager(session_id)
    memory.update_working_memory(plan=plan_json)

    # Log Planner Agent Completion Activity
    try:
        from agent.observability import ObservabilityManager
        ObservabilityManager().log(
            session_id=session_id,
            agent_name="Planner Agent",
            event_type="activity",
            description="Planner Agent completed plan generation successfully",
            status="success",
            metadata={
                "task": "Generating application plan and architecture",
                "progress": 100,
                "status": "success"
            }
        )
    except Exception:
        pass

    # Phase 1.1: Use state_manager for safe updates
    from .state_manager import merge_state_updates, log_state_transition
    
    # ── Task 3.3: Track token metrics ──────────────────────────────────
    current_tokens = count_message_tokens(pruned_messages)
    
    # Check if pruning occurred (original messages vs pruned messages)
    pruning_occurred = len(messages) != len(pruned_messages)
    
    # Check if overflow handling was triggered by looking for overflow indicator in pruned messages
    overflow_occurred = any(
        hasattr(msg, 'content') and isinstance(msg.content, str) and '[OVERFLOW HANDLING:' in msg.content
        for msg in pruned_messages
    )
    
    import json as _json
    tech_stack = {}
    try:
        parsed = _json.loads(plan_json)
        if isinstance(parsed, dict) and "tech_stack" in parsed:
            tech_stack = parsed["tech_stack"]
            # Auto-correct runtime for vanilla HTML/CSS/JS projects
            # The LLM sometimes outputs runtime: ["node"] even when the run_command uses python3
            if (tech_stack.get('frontend') == 'html_css_js'
                    and tech_stack.get('backend') == 'none'
                    and tech_stack.get('language') != 'abap'):
                env = parsed.get('environment', {})
                if isinstance(env, dict) and env.get('runtime') == ['node']:
                    env['runtime'] = ['python3']
                    parsed['environment'] = env
                    plan_json = _json.dumps(parsed)
                    logger.info("plan_bootstrap_runtime_autocorrected",
                                session_id=session_id,
                                corrected_runtime=['python3'])
    except Exception:
        pass

    updates = {
        'plan': plan_json,
        'tech_stack': tech_stack,
        'status': 'setup_env',
        'plan_generated_at': datetime.now().isoformat(),
        'current_task_index': 0,
        'execute_retry_count': 0,
        'validate_retry_count': 0,
        'retries': 0,
        'backend_retries': 0,
        'frontend_retries': 0,
        'judge_attempts': 0,
        'messages': [AIMessage(content=f'Plan ready:\n{plan_json}')],
        'token_count': current_tokens,
        'context_budget': ctx_manager.budget.to_dict(),
        'planning_phase': 'bootstrap',
        # Metrics tracking (Requirements 5.1, 5.2, 5.3, 5.4, 5.5)
        'total_tokens_processed': state.get('total_tokens_processed', 0) + current_tokens,
        'max_token_count_reached': max(
            state.get('max_token_count_reached', 0),
            current_tokens
        ),
    }
    
    # Issue #3: Persist workspace index in state for downstream nodes
    if workspace_idx_dict:
        updates['workspace_index'] = workspace_idx_dict
    
    # Increment pruning events if pruning occurred (Requirement 5.2)
    if pruning_occurred:
        updates['total_pruning_events'] = state.get('total_pruning_events', 0) + 1
    
    # Increment overflow events if overflow handling was triggered (Requirement 5.3)
    if overflow_occurred:
        updates['total_overflow_events'] = state.get('total_overflow_events', 0) + 1
        updates['context_overflow_count'] = state.get('context_overflow_count', 0) + 1
    
    new_state = merge_state_updates(state, updates)
    log_state_transition(session_id, old_status, 'setup_env', {
        'plan_length': len(plan_json),
        'judge_attempts': judge_attempts,
        'tokens': current_tokens,
        'pruning_occurred': pruning_occurred,
        'overflow_occurred': overflow_occurred,
    })
    
    return new_state


async def setup_environment_node(state: AgentState) -> AgentState:
    """
    Analyze the plan's tech_stack/environment and prepare the Docker sandbox.
    
    This node:
    1. Parses the plan JSON for tech_stack and environment fields
    2. Detects what runtimes/tools are needed
    3. Installs missing packages into the sandbox
    4. Reports available tools to the implement node
    
    Phase 1.1 Updates:
    - Uses state_manager for safe state updates
    - Tracks environment_ready flag
    - Logs state transitions
    """
    from .state_manager import merge_state_updates, log_state_transition
    from datetime import datetime, timezone
    
    old_status = state.get('status', 'setup_env')
    session_id = state.get('session_id', '')
    await check_paused(session_id)
    
    if state.get('chat_mode') == 'discuss':
        updates = {
            'status': 'implement',
            'messages': []
        }
        new_state = merge_state_updates(state, updates)
        log_state_transition(session_id, old_status, 'implement', {'reason': 'discuss_mode'})
        return new_state

    import json as _json

    session_id = state.get('session_id', '')
    plan_str = state.get('plan', '{}')

    # Log Environment Agent Setup Start Activity
    try:
        from agent.observability import ObservabilityManager
        ObservabilityManager().log(
            session_id=session_id,
            agent_name="Environment Agent",
            event_type="activity",
            description="Environment Agent initializing sandboxed container",
            status="running",
            metadata={
                "task": "Setting up workspace runtimes and tools",
                "progress": 40,
                "status": "running"
            }
        )
    except Exception:
        pass
    
    # Parse the plan
    try:
        plan = _json.loads(plan_str)
    except _json.JSONDecodeError:
        logger.warning("setup_env_plan_parse_failed", session_id=session_id)
        plan = {}

    tech_stack = plan.get('tech_stack', {})
    environment = plan.get('environment', {})
    runtimes_needed = environment.get('runtime', [])
    system_packages = environment.get('system_packages', [])
    global_tools = environment.get('global_tools', [])

    # ── Auto-detect from tech_stack if environment block is missing ──
    frontend = tech_stack.get('frontend', 'none')
    backend = tech_stack.get('backend', 'none')
    database = tech_stack.get('database', 'none')
    language = tech_stack.get('language', '')

    # ── ABAP bypass: skip environment setup entirely ──
    if language.lower() == 'abap':
        logger.info("setup_env_abap_bypass", session_id=session_id)
        environment_info = "Language: abap\nRuntime: SAP closed environment (no local sandbox)\nNo packages/tools to install."
        updates = {
            'environment_info': environment_info,
            'status': 'plan_refine',
            'messages': [AIMessage(content='[Environment Setup] ABAP project detected — skipping sandbox setup. Code will be generated for SAP deployment.')],
            'environment_ready': True,
            'setup_completed_at': datetime.now(timezone.utc).isoformat(),
            'scaffold_completed': True,
        }
        new_state = merge_state_updates(state, updates)
        log_state_transition(session_id, old_status, 'plan_refine', {'reason': 'abap_bypass'})
        return new_state

    if not runtimes_needed:
        runtimes_needed = []
        if frontend in ('react', 'vue', 'angular', 'next', 'svelte') or language in ('javascript', 'typescript'):
            runtimes_needed.append('node')
        if backend in ('fastapi', 'flask', 'django') or language == 'python':
            runtimes_needed.append('python3')
        if backend == 'spring_boot' or language == 'java':
            runtimes_needed.append('java')
        if language == 'go':
            runtimes_needed.append('go')
        if not runtimes_needed:
            runtimes_needed = ['python3']  # fallback: always have python

    if not system_packages:
        if database == 'postgresql':
            system_packages.append('postgresql-client')
        elif database == 'mongodb':
            system_packages.append('mongodb-clients')
        elif database == 'mysql':
            system_packages.append('default-mysql-client')

    # ── Get the sandbox and install what's needed ──
    setup_log = []
    runtime = DockerRuntime.get(session_id)
    
    # 1. Probe existing tools
    probe_cmd = "echo '--- VERSIONS ---' && python3 --version 2>/dev/null && node --version 2>/dev/null && npm --version 2>/dev/null && java -version 2>/dev/null && go version 2>/dev/null; echo '--- END ---'"
    probe_result = await runtime.execute(CmdRunAction(command=probe_cmd))
    existing_tools = probe_result.get('output', '')
    setup_log.append(f"Existing tools:\n{existing_tools}")
    
    # 2. Install system packages if needed
    pkgs_to_install = []
    if system_packages:
        pkgs_to_install.extend(system_packages)
    
    # Check if Java is needed but missing
    if 'java' in runtimes_needed and 'java version' not in existing_tools and 'openjdk' not in existing_tools:
        pkgs_to_install.extend(['default-jdk', 'maven'])
    
    # Check if Go is needed but missing
    if 'go' in runtimes_needed and 'go version' not in existing_tools:
        pkgs_to_install.append('golang')
    
    if pkgs_to_install:
        install_cmd = f"apt-get update -qq && apt-get install -y -qq {' '.join(pkgs_to_install)} 2>&1 | tail -5"
        logger.info("setup_env_installing_packages", session_id=session_id, packages=pkgs_to_install)
        result = await runtime.execute(CmdRunAction(command=install_cmd))
        if result.get('exit_code', 1) == 0:
            setup_log.append(f"Installed system packages: {', '.join(pkgs_to_install)}")
        else:
            setup_log.append(f"Warning: Some packages failed to install: {result.get('output', '')[:200]}")

    # 3. Install global npm tools if needed
    if global_tools and 'node' in runtimes_needed:
        for tool in global_tools:
            result = await runtime.execute(CmdRunAction(command=f"npm install -g {tool} 2>&1 | tail -3"))
            if result.get('exit_code', 1) == 0:
                setup_log.append(f"Installed global tool: {tool}")
            else:
                setup_log.append(f"Warning: Failed to install {tool}")

    # 4. Build the environment summary for the LLM
    env_summary_parts = [
        f"Runtime(s): {', '.join(runtimes_needed)}",
        f"Frontend stack: {frontend}",
        f"Backend stack: {backend}",
        f"Database: {database}",
        f"Language: {language}",
    ]
    if system_packages:
        env_summary_parts.append(f"System packages installed: {', '.join(system_packages)}")
    if global_tools:
        env_summary_parts.append(f"Global tools installed: {', '.join(global_tools)}")
    
    # Final probe to confirm
    final_probe = await runtime.execute(CmdRunAction(
        command="echo 'node:' $(node --version 2>/dev/null || echo 'N/A') '| npm:' $(npm --version 2>/dev/null || echo 'N/A') '| python:' $(python3 --version 2>/dev/null || echo 'N/A') '| java:' $(java -version 2>&1 | head -1 || echo 'N/A') '| go:' $(go version 2>/dev/null || echo 'N/A')"
    ))
    env_summary_parts.append(f"Verified versions: {final_probe.get('output', 'unknown')}")

    environment_info = '\n'.join(env_summary_parts)
    
    logger.info("setup_env_complete", session_id=session_id, environment=environment_info)

    # Log Environment Agent Setup Completion Activity
    try:
        from agent.observability import ObservabilityManager
        ObservabilityManager().log(
            session_id=session_id,
            agent_name="Environment Agent",
            event_type="activity",
            description="Environment Agent successfully validated and provisioned system requirements",
            status="success",
            metadata={
                "task": "Setting up workspace runtimes and tools",
                "progress": 100,
                "status": "success"
            }
        )
    except Exception:
        pass

    # ── 5. Copy Template Files if Selected ──────────────────────────
    scaffold_completed = False
    template_selected = ''
    try:
        import json as _scaffold_json
        plan_data = _scaffold_json.loads(plan_str)
        template_selected = plan_data.get('template_selected', '')
        if template_selected == 'none':
            template_selected = ''
    except Exception:
        pass

    if template_selected:
        # Normalize template name to handle variations like 'react-vite-ts' -> 'react-vite'
        import os
        _backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _templates_dir = os.path.join(_backend_dir, "templates")
        _normalized = template_selected.lower().strip()
        if os.path.exists(_templates_dir):
            _available = [d for d in os.listdir(_templates_dir) if os.path.isdir(os.path.join(_templates_dir, d))]
            if _normalized in _available:
                template_selected = _normalized
            else:
                for _avail in _available:
                    if _avail in _normalized or _normalized in _avail:
                        template_selected = _avail
                        break

        logger.info("setup_env_copying_template", session_id=session_id, template=template_selected)
        setup_log.append(f"Copying template: {template_selected}")

        try:
            from agent.observability import ObservabilityManager
            ObservabilityManager().log(
                session_id=session_id,
                agent_name="Environment Agent",
                event_type="activity",
                description=f"Copying pre-built template: {template_selected}",
                status="running",
                metadata={"template": template_selected, "progress": 70}
            )
        except Exception:
            pass
            
        import os
        import shutil
        
        # Determine paths
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_src_dir = os.path.join(backend_dir, "templates", template_selected)
        workspace_dest_dir = os.path.abspath(os.path.join(backend_dir, "..", "workspaces", session_id))
        
        if os.path.exists(template_src_dir):
            try:
                # Copy template directory contents to workspace
                shutil.copytree(template_src_dir, workspace_dest_dir, dirs_exist_ok=True)
                
                scaffold_completed = True
                setup_log.append(f"Template '{template_selected}' copied successfully.")
                logger.info("setup_env_template_success", session_id=session_id)
                
                # Install dependencies in the sandbox
                if os.path.exists(os.path.join(template_src_dir, "package.json")):
                    setup_log.append("Installing npm dependencies from template...")
                    await runtime.execute(CmdRunAction(command="npm install"))
                elif os.path.exists(os.path.join(template_src_dir, "requirements.txt")):
                    setup_log.append("Installing pip dependencies from template...")
                    await runtime.execute(CmdRunAction(command="pip install -r requirements.txt"))
                
                # If Python backend requested alongside frontend template (e.g. React + FastAPI)
                if backend in ['fastapi', 'flask', 'django']:
                    setup_log.append(f"Installing Python backend dependencies for '{backend}'...")
                    await runtime.execute(CmdRunAction(command="pip install fastapi uvicorn pydantic sqlalchemy --break-system-packages 2>&1 | tail -3"))
                    
            except Exception as e:
                setup_log.append(f"Template copy failed: {str(e)}")
                logger.warning("setup_env_template_failed", session_id=session_id, error=str(e))
        elif template_selected in DYNAMIC_SCAFFOLD_TEMPLATES:
            try:
                os.makedirs(workspace_dest_dir, exist_ok=True)
                scaffold_cmd = DYNAMIC_SCAFFOLD_TEMPLATES[template_selected]["command"]
                setup_log.append(f"Running dynamic scaffold for '{template_selected}': {scaffold_cmd}")
                result = await runtime.execute(CmdRunAction(command=scaffold_cmd))
                exit_code = result.get('exit_code', 0) if isinstance(result, dict) else getattr(result, 'exit_code', 0)
                output = result.get('output', '') if isinstance(result, dict) else getattr(result, 'output', '')
                if exit_code != 0:
                    raise Exception(f"Scaffold command failed with exit code {exit_code}: {output[:300]}")
                scaffold_completed = True
                setup_log.append(f"Dynamic scaffold '{template_selected}' completed.")
                logger.info("setup_env_dynamic_scaffold_success", session_id=session_id, template=template_selected)
            except Exception as e:
                setup_log.append(f"Dynamic scaffold failed: {str(e)}")
                logger.warning("setup_env_dynamic_scaffold_failed", session_id=session_id, template=template_selected, error=str(e))
                from agent.exceptions import TemplateNotFoundError
                raise TemplateNotFoundError(template_selected, template_src_dir)
        else:
            from agent.exceptions import TemplateNotFoundError
            raise TemplateNotFoundError(template_selected, template_src_dir)
    else:
        # No template selected — mark as completed
        scaffold_completed = True
        setup_log.append("No template selected — proceeding to detail planning.")

    updates = {
        'environment_info': environment_info,
        'status': 'plan_refine',
        'messages': [AIMessage(content=f'[Environment Setup Complete]\n{environment_info}\n\nScaffold: {"completed" if scaffold_completed else "failed or skipped"}')],
        'environment_ready': True,
        'setup_completed_at': datetime.now(timezone.utc).isoformat(),
        'scaffold_completed': scaffold_completed,
    }
    
    new_state = merge_state_updates(state, updates)
    log_state_transition(session_id, old_status, 'plan_refine', {
        'runtimes': runtimes_needed,
        'packages_installed': len(pkgs_to_install) if pkgs_to_install else 0,
        'scaffold_completed': scaffold_completed,
        'template_selected': template_selected or 'none',
    })
    return new_state


async def plan_refine_node(state: AgentState) -> AgentState:
    """
    Refine Plan Node - Generate API contracts and frontend/backend subagent plans.
    
    This is Phase 2 of two-phase planning. It runs AFTER setup_environment
    has executed the scaffold command. It:
    1. Re-indexes the workspace to discover actual scaffolded files
    2. Reads scaffolded file contents (src/App.jsx, src/main.jsx, etc.)
    3. Calls the LLM with a detail-planning prompt that includes full workspace context
    4. Produces a complete plan with exact file paths and implementation steps
    5. Routes to the Judge for approval
    """
    from .state_manager import merge_state_updates, log_state_transition
    from datetime import datetime, timezone
    
    old_status = state.get('status', 'plan_refine')
    session_id = state.get('session_id', '')
    await check_paused(session_id)
    
    if state.get('chat_mode') == 'discuss':
        updates = {
            'status': 'supervisor',
            'messages': [],
            'planning_phase': 'refine',
        }
        new_state = merge_state_updates(state, updates)
        log_state_transition(session_id, old_status, 'supervisor', {'reason': 'discuss_mode'})
        return new_state

    llm = _resolve_llm(state, role="planner")
    model_name = _get_model_name(state, role="planner")

    # Log Detail Planner Start Activity
    try:
        from agent.observability import ObservabilityManager
        ObservabilityManager().log(
            session_id=session_id,
            agent_name="Detail Planner Agent",
            event_type="activity",
            description="Detail Planner started — generating file-level implementation steps from scaffolded workspace",
            status="running",
            metadata={
                "task": "Generating detailed implementation plan",
                "progress": 50,
                "status": "running",
                "scaffold_completed": state.get('scaffold_completed', False),
            }
        )
    except Exception:
        pass
    
    # Get original user requirements from first message
    from langchain_core.messages import HumanMessage
    srs = state.get('messages', [HumanMessage(content="")])[0].content
    if isinstance(srs, list):
        srs = str(srs)
    
    bootstrap_plan_raw = state.get('plan', '{}')
    import json as _json
    try:
        # Pipeline wiring fix: if the orchestrator passed {} instead of the actual output,
        # explicitly reconstruct the necessary parts for the Detail Planner.
        parsed_plan = _json.loads(bootstrap_plan_raw)
        if not parsed_plan or bootstrap_plan_raw.strip() == '{}':
            bootstrap_plan = _json.dumps({
                "tech_stack": state.get('tech_stack', {}),
                "template_selected": "none"
            }, indent=2)
        else:
            bootstrap_plan = bootstrap_plan_raw
    except Exception:
        bootstrap_plan = bootstrap_plan_raw
        
    judge_feedback_raw = state.get('judge_feedback', '')
    if judge_feedback_raw:
        judge_feedback = f"MANDATORY OVERRIDE (PREVIOUS CRITIQUE):\n{judge_feedback_raw}\nEnsure your plan explicitly addresses this feedback."
    else:
        judge_feedback = ""
        
    research_context = state.get('research_context', 'No research available.')
    
    # Filter research context by project type
    tech_stack = state.get('tech_stack', {})
    if tech_stack.get('frontend') == 'html_css_js' and tech_stack.get('backend') == 'none':
        # Filter out backend-specific research
        if 'Backend Setup' in research_context or 'Node.js' in research_context or 'express' in research_context.lower():
            research_context = "Research context filtered out: Not applicable for standalone Vanilla JS frontend."

    environment_info = state.get('environment_info', 'No environment info.')
    
    # Extract architectural plan for folder structure guidance
    arch_plan_obj = state.get('architectural_plan')
    architectural_plan_str = ""
    if arch_plan_obj:
        try:
            import json as _json
            if hasattr(arch_plan_obj, "model_dump_json"):
                # Extract only the useful summary fields, not the full graph JSON
                arch_summary_parts = []
                if hasattr(arch_plan_obj, 'tech_stack_summary') and arch_plan_obj.tech_stack_summary:
                    arch_summary_parts.append(f"Tech Stack: {arch_plan_obj.tech_stack_summary}")
                if hasattr(arch_plan_obj, 'estimated_complexity') and arch_plan_obj.estimated_complexity:
                    arch_summary_parts.append(f"Complexity: {arch_plan_obj.estimated_complexity}")
                if hasattr(arch_plan_obj, 'architecture_decisions') and arch_plan_obj.architecture_decisions:
                    decisions = arch_plan_obj.architecture_decisions
                    for adr in decisions[:3]:  # Limit to 3 ADRs
                        if hasattr(adr, 'title'):
                            arch_summary_parts.append(f"ADR: {adr.title} - {getattr(adr, 'decision', '')}")
                if arch_summary_parts:
                    architectural_plan_str = "\n".join(arch_summary_parts)
                else:
                    # Fallback to compact JSON without diagram graph data
                    architectural_plan_str = arch_plan_obj.model_dump_json(indent=2)
            elif isinstance(arch_plan_obj, dict):
                architectural_plan_str = _json.dumps(arch_plan_obj, indent=2)
            else:
                architectural_plan_str = str(arch_plan_obj)
        except Exception as e:
            logger.warning("plan_refine_arch_plan_parse_failed", error=str(e))
            architectural_plan_str = str(arch_plan_obj)
    
    
    # ── Re-index the workspace (scaffolded files now exist) ────────────
    workspace_context = ""
    workspace_idx_dict = None
    try:
        if session_id:
            import os
            import re
            local_ws_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "workspaces", session_id))
            if os.path.exists(local_ws_path):
                indexer = WorkspaceIndexer(local_ws_path)
                idx = indexer.index()
                workspace_context = indexer.get_ranked_context(
                    idx,
                    query=srs,
                    max_tokens=5000  # Larger budget for detail planning
                )
                
                # Filter out tasks_todo.md to prevent previous iteration errors from poisoning context
                workspace_context = re.sub(r'(?m)^--- tasks_todo\.md ---.*?(?=(^--- |\Z))', '', workspace_context, flags=re.DOTALL)

                workspace_idx_dict = {
                    'project_type': idx.project_type,
                    'framework': idx.framework,
                    'tech_stack': idx.tech_stack,
                    'dependencies': idx.dependencies,
                    'key_files': idx.key_files,
                    'entry_points': idx.entry_points,
                    'file_count': idx.file_count,
                    'directory_count': idx.directory_count,
                    'structure_tree': idx.structure_tree,
                }
                logger.info(
                    "plan_refine_workspace_indexed",
                    session_id=session_id,
                    file_count=idx.file_count,
                    framework=idx.framework,
                    key_files=idx.key_files[:5],
                )
    except Exception as e:
        logger.warning("plan_refine_workspace_index_failed", error=str(e))
    
    # Fallback: if workspace is still empty (scaffold failed), get file listing from Docker
    if not workspace_context:
        try:
            runtime = DockerRuntime.get(session_id) if session_id else None
            if runtime:
                result = await runtime.execute(CmdRunAction(
                    command="find /workspace -maxdepth 3 -type f -not -path '*/node_modules/*' -not -path '*/.git/*' | head -100"
                ))
                if result.get('exit_code') == 0 and result.get('output'):
                    workspace_context = f"WORKSPACE FILES:\n{result['output'].strip()}"
                    
                    # Also read key entry-point files
                    common_files = [
                        'src/App.jsx', 'src/App.tsx', 'src/App.js',
                        'src/main.jsx', 'src/main.tsx', 'src/main.js',
                        'src/index.css', 'src/App.css', 'index.html',
                        'package.json', 'vite.config.js', 'vite.config.ts',
                    ]
                    file_contents = []
                    for fpath in common_files:
                        cat_result = await runtime.execute(CmdRunAction(
                            command=f"cat '/workspace/{fpath}' 2>/dev/null | head -80"
                        ))
                        if cat_result.get('exit_code') == 0 and cat_result.get('output', '').strip():
                            file_contents.append(f"\n--- {fpath} ---\n{cat_result['output'].strip()}")
                    if file_contents:
                        workspace_context += "\n\nFILE CONTENTS:" + "".join(file_contents)
        except Exception as e:
            logger.warning("plan_refine_docker_fallback_failed", error=str(e))
    
    if not workspace_context:
        workspace_context = "Workspace is empty. Scaffold may have failed. Plan all files as 'create' action."

    # ── Context Management: fit the whole request under the limit ──────
    ctx_manager = ContextManager(model=model_name)
    messages = state.get('messages', [])
    pruned_messages = ctx_manager.prune_messages(messages)

    from .prompts import REFINE_PLANNER_SYSTEM_PROMPT, REFINE_PLAN_SCHEMA_INSTRUCTIONS, ABAP_SYSTEM_INSTRUCTIONS, ABAP_REFINE_INSTRUCTIONS

    # Conditionally include ABAP instructions only for ABAP projects
    is_abap = tech_stack.get('language', '').lower() == 'abap'
    system_prompt = REFINE_PLANNER_SYSTEM_PROMPT + (ABAP_SYSTEM_INSTRUCTIONS if is_abap else '')
    schema_instructions = REFINE_PLAN_SCHEMA_INSTRUCTIONS + (ABAP_REFINE_INSTRUCTIONS if is_abap else '')

    fit = ctx_manager.fit_request(
        system_text=system_prompt + schema_instructions,
        components={
            'srs_text':          {'text': srs,                    'share': 0.20, 'keep': 'head'},
            'bootstrap_plan':    {'text': bootstrap_plan,         'share': 0.10, 'keep': 'head'},
            'architectural_plan':{'text': architectural_plan_str, 'share': 0.20, 'keep': 'head'},
            'workspace_context': {'text': workspace_context,      'share': 0.30, 'keep': 'head'},
            'environment_info':  {'text': environment_info,       'share': 0.05, 'keep': 'head'},
            'research_context':  {'text': research_context,       'share': 0.05, 'keep': 'head'},
            'judge_feedback':    {'text': judge_feedback,         'share': 0.05, 'keep': 'head'},
        },
    )

    # ── Call the Refine Planner LLM ────────────────────────────────────
    from agent.plan_models import DetailPlan
    from langchain_core.prompts import ChatPromptTemplate
    # Build the refine prompt dynamically with conditional ABAP instructions
    dynamic_refine_prompt = ChatPromptTemplate.from_messages([
        ('system', system_prompt),
        ('human',  'ORIGINAL REQUIREMENTS:\n{srs_text}\n\nBOOTSTRAP PLAN (from Phase 1):\n{bootstrap_plan}\n\nARCHITECTURAL PLAN:\n{architectural_plan}\n\nWORKSPACE CONTEXT (scaffolded files on disk):\n{workspace_context}\n\nENVIRONMENT INFO:\n{environment_info}\n\nRESEARCH CONTEXT:\n{research_context}\n\n{judge_feedback}\n\n' + schema_instructions),
    ])
    chain = dynamic_refine_prompt | llm
    from agent.observability import ObservabilityCallbackHandler
    handler = ObservabilityCallbackHandler(session_id, "Detail Planner Agent")

    try:
        response = await chain.ainvoke(fit['components'], config={"callbacks": [handler]})
        raw_text = response.content
        json_str = extract_plan_json(str(raw_text))
        parsed_plan = DetailPlan.model_validate_json(json_str)
        detail_plan_json = parsed_plan.model_dump_json()
    except Exception as e:
        logger.error("plan_refine_structured_output_error", session_id=session_id, error=str(e))
        from .state_manager import merge_state_updates
        updates = {
            'status': 'error',
            'plan_error': f"Detail Planner produced invalid structured output: {str(e)}",
            'messages': [AIMessage(content=f"[Detail Planner Error] Invalid output produced: {str(e)}")]
        }
        return merge_state_updates(state, updates)

    # Update memory with the refined plan
    memory = _get_memory_manager(session_id)
    memory.update_working_memory(plan=detail_plan_json)

    # Log Detail Planner Completion
    try:
        from agent.observability import ObservabilityManager
        ObservabilityManager().log(
            session_id=session_id,
            agent_name="Detail Planner Agent",
            event_type="activity",
            description="Detail Planner completed — file-level plan generated",
            status="success",
            metadata={
                "task": "Generating detailed implementation plan",
                "progress": 100,
                "status": "success",
                "plan_length": len(detail_plan_json),
            }
        )
    except Exception:
        pass

    current_tokens = count_message_tokens(pruned_messages)
    
    updates = {
        'plan': detail_plan_json,
        'status': 'judge',
        'planning_phase': 'refine',
        'execute_retry_count': 0,
        'validate_retry_count': 0,
        'retries': 0,
        'backend_retries': 0,
        'frontend_retries': 0,
        'plan_generated_at': datetime.now().isoformat(),
        'messages': [AIMessage(content=f'[Detail Plan Ready]\n{detail_plan_json}')],
        'token_count': current_tokens,
        'context_budget': ctx_manager.budget.to_dict(),
        'total_tokens_processed': state.get('total_tokens_processed', 0) + current_tokens,
        'max_token_count_reached': max(
            state.get('max_token_count_reached', 0),
            current_tokens
        ),
    }
    
    if workspace_idx_dict:
        updates['workspace_index'] = workspace_idx_dict
    
    new_state = merge_state_updates(state, updates)
    
    # Initialize tasks_todo.md checklist
    try:
        runtime = DockerRuntime.get(session_id)
        if runtime:
            await update_tasks_todo(runtime, session_id, new_state)
            # Also initialize structured todo persistence
            try:
                from agent.todo_manager import TodoManager
                todo_mgr = TodoManager(session_id)
                todo_mgr.sync_from_plan(detail_plan_json)
                await todo_mgr.save(runtime)
            except Exception as e:
                logger.warning("failed_to_init_structured_todos", session_id=session_id, error=str(e))
    except Exception as e:
        logger.warning("failed_to_initialize_tasks_todo", session_id=session_id, error=str(e))

    log_state_transition(session_id, old_status, 'judge', {
        'plan_length': len(detail_plan_json),
        'scaffold_completed': state.get('scaffold_completed', False),
    })
    
    return new_state



async def implement_node(state: AgentState) -> AgentState:
    """
    Implementation Node - Generate code and execute actions
    
    Phase 1.1 Updates:
    - Uses state_manager for safe state updates
    - Tracks pending_actions, execution_results
    - Logs state transitions
    """
    from .state_manager import merge_state_updates, log_state_transition
    
    old_status = state.get('status', 'implement')
    session_id = state.get('session_id', '')
    await check_paused(session_id)
    
    llm = _resolve_llm(state, role="coder")
    model_name = _get_model_name(state, role="coder")
    
    chat_mode = state.get('chat_mode', 'build')
    if chat_mode == 'discuss':
        from .prompts import discuss_prompt
        discuss_chain = discuss_prompt | llm
        
        ctx_manager = ContextManager(model=model_name)
        messages = state.get('messages', [])
        pruned_messages = ctx_manager.prune_messages(messages)
        
        from agent.observability import ObservabilityCallbackHandler
        handler = ObservabilityCallbackHandler(session_id, "Coder Agent")
        
        response = await discuss_chain.ainvoke({
            'messages': pruned_messages,
        }, config={"callbacks": [handler]})
        content = response.content if isinstance(response.content, str) else str(response.content)
        
        updates = {
            'messages': [AIMessage(content=content)],
            'status': 'done',
            'token_count': count_message_tokens(pruned_messages),
            'context_budget': ctx_manager.budget.to_dict(),
        }
        new_state = merge_state_updates(state, updates)
        log_state_transition(session_id, old_status, 'done', {'mode': 'discuss'})
        return new_state

    chain = implement_prompt | llm

    # ── Phase 1: Context Management ────────────────────────────────────
    # Messages are fitted together with all other prompt components in
    # fit_request() below, so the WHOLE request stays under the model limit.
    ctx_manager = ContextManager(model=model_name)
    messages = state.get('messages', [])

    # ── Phase 2: Error Analysis ────────────────────────────────────────
    last_obs_obj = state.get('last_obs')
    last_error = ''
    error_analysis_text = ''
    
    if last_obs_obj:
        exit_code = getattr(last_obs_obj, 'exit_code', 0)
        if exit_code != 0:
            raw_output = getattr(last_obs_obj, 'output', '')
            last_error = raw_output

            # Analyze the error
            parsed_error = _error_analyzer.analyze(raw_output, exit_code)
            error_analysis_text = _error_analyzer.format_for_prompt(parsed_error)

            # Track in memory
            memory = _get_memory_manager(session_id)
            memory.update_working_memory(
                error_seen=f"{parsed_error.category.value}: {parsed_error.message[:100]}"
            )

            # Check if retry is worthwhile
            retries = state.get('retries', 0)
            if not _error_analyzer.should_retry(parsed_error, retries):
                logger.warning(
                    "error_not_retryable",
                    session_id=session_id,
                    category=parsed_error.category.value,
                    retries=retries,
                )

            logger.info(
                "implement_with_error_analysis",
                session_id=session_id,
                category=parsed_error.category.value,
                severity=parsed_error.severity.value,
            )
    
    # ── Phase 3: Workspace Context ─────────────────────────────────────
    runtime = DockerRuntime.get(session_id) if session_id else None
    if not runtime:
        return state
    workspace_context = ""
    
    try:
        if session_id:
            import os
            local_ws_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "workspaces", session_id))
            if os.path.exists(local_ws_path):
                error_file = None
                parsed_error = locals().get('parsed_error')
                if parsed_error:
                    error_file = getattr(parsed_error, 'file', None)

                user_query = ""
                if state.get('messages'):
                    user_query = state.get('messages')[0].content

                import json as _json
                plan_json = {}
                try:
                    plan_json = _json.loads(state.get('plan', '{}'))
                except Exception:
                    pass
                plan_files = plan_json.get('files', [])

                indexer = WorkspaceIndexer(local_ws_path)
                idx = indexer.index()
                
                workspace_context = indexer.get_ranked_context(
                    idx,
                    plan_files=plan_files,
                    error_file=error_file,
                    query=user_query,
                    max_tokens=3500
                )
    except Exception as e:
        logger.warning("dynamic_context_collection_failed", error=str(e))

    if not workspace_context:
        try:
            if runtime:
                result = await runtime.execute(CmdRunAction(
                    command="find /workspace -maxdepth 3 -type f -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/dist/*' -not -path '*/.cache/*' | head -100"
                ))
                if result.get('exit_code') == 0 and result.get('output'):
                    file_list = result['output'].strip()
                    workspace_context = f"WORKSPACE CONTEXT:\nDirectory listing:\n{file_list}\n"

                    # After scaffolding, the LLM needs actual file contents to use <replace>.
                    # Read the key files from the plan's steps + common entry points.
                    files_to_read = set()
                    try:
                        import json as _json
                        plan_data = _json.loads(state.get('plan', '{}'))
                        for step in plan_data.get('steps', []):
                            f = step.get('file', '')
                            if f:
                                files_to_read.add(f)
                    except Exception:
                        pass

                    # Also read common entry points if they exist
                    common_files = [
                        'src/App.jsx', 'src/App.tsx', 'src/App.js',
                        'src/main.jsx', 'src/main.tsx', 'src/main.js',
                        'src/index.js', 'src/index.jsx', 'src/index.tsx',
                        'src/index.html', 'index.html', 'package.json',
                        'src/index.css', 'src/App.css', 'vite.config.js', 'vite.config.ts',
                    ]
                    files_to_read.update(common_files)

                    file_contents_parts = []
                    total_chars = 0
                    MAX_CONTEXT_CHARS = 8000

                    for fpath in files_to_read:
                        if total_chars >= MAX_CONTEXT_CHARS:
                            break
                        full_path = f"/workspace/{fpath}" if not fpath.startswith('/') else fpath
                        try:
                            cat_result = await runtime.execute(CmdRunAction(
                                command=f"cat '{full_path}' 2>/dev/null | head -80"
                            ))
                            if cat_result.get('exit_code') == 0 and cat_result.get('output', '').strip():
                                content = cat_result['output'].strip()
                                file_contents_parts.append(f"\n--- {fpath} ---\n{content}")
                                total_chars += len(content)
                        except Exception:
                            pass

                    if file_contents_parts:
                        workspace_context += "\nFile contents (for <replace> editing):" + "".join(file_contents_parts)
        except Exception:
            pass

    # Small courtesy delay — rate limiting is handled by GroqKeyPool
    await asyncio.sleep(0.5)
    
    # Inject dynamic microagent instructions into the research context
    microagent_rules = await get_dynamic_microagent_instructions(
        state.get('plan', ''),
        messages,
        runtime,
        session_id=session_id,
    )
    research_ctx = state.get('research_context', '') or 'No web research available. Use <search>query</search> to look up information.'
    if microagent_rules:
        research_ctx = f"{research_ctx}\n\n{microagent_rules}"

    # ── Fit the ENTIRE request under the model's context limit ─────────
    # Every component gets a max share of the budget; whatever they don't
    # use flows to the message history. Raw error logs keep their TAIL
    # (the actual failure), plans/research keep their HEAD.
    from .prompts import SYSTEM_PROMPT
    fit = ctx_manager.fit_request(
        messages=messages,
        system_text=SYSTEM_PROMPT,
        components={
            'plan':              {'text': state.get('plan', ''), 'share': 0.18, 'keep': 'head'},
            'workspace_context': {'text': workspace_context,     'share': 0.25, 'keep': 'head'},
            'research_context':  {'text': research_ctx,          'share': 0.08, 'keep': 'head'},
            'error':             {'text': last_error,            'share': 0.10, 'keep': 'tail'},
            'error_analysis':    {'text': error_analysis_text,   'share': 0.05, 'keep': 'head'},
            'environment_info':  {'text': state.get('environment_info', 'Python3 and Node.js pre-installed.'), 'share': 0.04, 'keep': 'head'},
        },
    )
    pruned_messages = fit['messages']
    fitted = fit['components']
    if fit['stats'].get('over_limit'):
        logger.warning(
            "implement_request_over_limit",
            session_id=session_id,
            request_tokens=fit['stats']['request_tokens'],
        )

    from agent.observability import ObservabilityCallbackHandler, WEBSOCKET_BROADCASTERS
    from agent.streaming_parser import StreamingMessageParser, ParserEvent
    from agent.schema import FileWriteAction, CmdRunAction, WebSearchAction, FinishAction

    handler = ObservabilityCallbackHandler(session_id, "Coder Agent")

    async def ws_callback(payload: dict):
        callbacks = WEBSOCKET_BROADCASTERS.get(session_id, [])
        for cb in callbacks:
            try:
                await cb(payload)
            except Exception:
                pass

    content = ""
    parser = StreamingMessageParser()
    runtime = DockerRuntime.get(session_id) if session_id else None
    if not runtime:
        return state

    executed_actions = []
    accumulated_batch_results = {
        'messages': [],
        'status': 'implement',
        'last_error_analysis': None,
        'last_obs': None,
        'retries': state.get('retries', 0),
        'error_history': list(state.get('error_history') or []),
        'workspace_summary': '',
        'modified_files': [],
    }

    import json as _json
    plan_files = []
    plan_str = state.get('plan', '{}')
    if plan_str:
        try:
            plan_data = _json.loads(plan_str)
            plan_files = plan_data.get('files', [])
        except Exception:
            pass

    async def handle_parser_event(event: ParserEvent):
        nonlocal accumulated_batch_results
        
        # Dispatch stream tracking events to WebSocket
        parser_payload = {
            "type": event.kind,
            "action": event.action,
            "path": event.path,
            "content": event.content,
            "command": event.command,
        }
        await ws_callback(parser_payload)

        if event.kind == "action_close":
            # Check if a previous action in this batch has already failed
            last_obs = accumulated_batch_results.get('last_obs')
            if last_obs and getattr(last_obs, 'exit_code', 0) != 0:
                logger.warning("skipping_action_due_to_prior_failure", session_id=session_id, action=event.action)
                return

            # Map parser action to corresponding schema action object
            action = None
            if event.action == "write":
                action = FileWriteAction(path=event.path, content=event.content)
            elif event.action == "run":
                from agent.schema import CmdRunAction
                action = CmdRunAction(command=event.content)
            elif event.action == "search":
                action = WebSearchAction(query=event.content)
            elif event.action == "finish":
                action = FinishAction(message=event.content)

            if action:
                executed_actions.append(action)
                
                # Execute action immediately
                res = await execute_actions_batch(
                    runtime=runtime,
                    actions=[action],
                    session_id=session_id,
                    state=state,
                    ws_callback=ws_callback,
                )
                
                # Accumulate execution observations & results
                accumulated_batch_results['messages'].extend(res.get('messages', []))
                accumulated_batch_results['status'] = res.get('status', 'implement')
                accumulated_batch_results['last_error_analysis'] = res.get('last_error_analysis')
                accumulated_batch_results['last_obs'] = res.get('last_obs')
                accumulated_batch_results['retries'] = res.get('retries', accumulated_batch_results['retries'])
                accumulated_batch_results['error_history'] = res.get('error_history', accumulated_batch_results['error_history'])
                accumulated_batch_results['workspace_summary'] = res.get('workspace_summary', accumulated_batch_results['workspace_summary'])
                accumulated_batch_results['modified_files'].extend(res.get('modified_files', []))

    # Stream the LLM response (scaffold already ran in setup_environment)
    async for chunk in chain.astream({
        'plan': fitted['plan'],
        'messages': pruned_messages,
        'error': fitted['error'],
        'workspace_context': fitted['workspace_context'],
        'error_analysis': fitted['error_analysis'],
        'locked_files_info': f"LOCKED FILES: {', '.join(state.get('locked_files', []))}" if state.get('locked_files') else "",
        'environment_info': fitted['environment_info'],
        'research_context': fitted['research_context'],
    }, config={"callbacks": [handler]}):
        chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
        content += chunk_content

        # Feed text to streaming parser
        for parser_event in parser.feed(chunk_content):
            await handle_parser_event(parser_event)

    # Flush any unclosed final tag
    for parser_event in parser.flush():
        await handle_parser_event(parser_event)

    if not executed_actions:
        updates = {
            'messages': [AIMessage(content=content)],
            'status': 'done',
            'token_count': count_message_tokens(pruned_messages),
            'context_budget': ctx_manager.budget.to_dict(),
        }
        new_state = merge_state_updates(state, updates)
        log_state_transition(session_id, old_status, 'done', {'reason': 'no_actions'})
        return new_state

    last_action = executed_actions[-1]
    new_status = accumulated_batch_results['status']
    
    updates = {
        'messages': [AIMessage(content=content)] + accumulated_batch_results['messages'],
        'status': new_status,
        '_action': last_action,
        'pending_actions': executed_actions,
        'token_count': count_message_tokens(pruned_messages),
        'context_budget': ctx_manager.budget.to_dict(),
        'last_error_analysis': accumulated_batch_results.get('last_error_analysis'),
        'last_obs': accumulated_batch_results.get('last_obs'),
        'retries': accumulated_batch_results.get('retries', state.get('retries', 0)),
        'error_history': accumulated_batch_results.get('error_history'),
        'workspace_summary': accumulated_batch_results.get('workspace_summary', ''),
        'implementation_explanation': content[:500],  # Store first 500 chars
        'modified_files': accumulated_batch_results.get('modified_files', []),
    }
    
    new_state = merge_state_updates(state, updates)
    log_state_transition(
        session_id, 
        old_status, 
        new_status,
        {'actions_executed': len(executed_actions), 'has_error': accumulated_batch_results.get('last_error_analysis') is not None}
    )
    return new_state




async def execute_node(state: AgentState) -> AgentState:
    """
    Execute Node - Run actions in Docker runtime
    
    Phase 1.1 Updates:
    - Uses state_manager for safe state updates
    - Tracks execution_results, modified_files
    - Logs state transitions
    """
    from .state_manager import merge_state_updates, log_state_transition
    
    old_status = state.get('status', 'execute')
    session_id = state.get('session_id')
    if not session_id:
        raise RuntimeError("session_id is required for execution")
    await check_paused(session_id)
    runtime = DockerRuntime.get(session_id)
    action = state.get('_action')
    if action is None:
        action = UnknownAction(content='')
    else:
        if isinstance(action, CmdRunAction):
            from agent.schema import CmdRunAction
            action = CmdRunAction(command=sanitize_command(action.command))

    locked_files = state.get('locked_files', [])
    if isinstance(action, FileWriteAction) and action.path in locked_files:
        logger.warning("execute_blocked_locked_file", session_id=session_id, path=action.path)
        err_msg = f"Error: File {action.path} is locked and cannot be modified."
        obs = ErrorObservation(output=err_msg, exit_code=1)
        
        updates = {
            'last_obs': obs,
            'retries': state.get('retries', 0),
            'messages': [HumanMessage(content=f"Observation: {err_msg}")],
        }
        new_state = merge_state_updates(state, updates)
        log_state_transition(session_id, old_status, old_status, {'error': 'locked_file'})
        return new_state
    
    if isinstance(action, UnknownAction):
        obs = ErrorObservation(output='Error: Could not parse a valid action (<run>, <write>, <finish>).', exit_code=1)
        logger.error("execute_unknown_action", session_id=session_id)
        
        updates = {
            'last_obs': obs,
            'retries': state.get('retries', 0) + 1,
            'execute_retry_count': state.get('execute_retry_count', 0) + 1,
            'messages': [HumanMessage(content='Observation: Invalid action format. You MUST use exactly ONE of the XML tags: <run>, <write>, or <finish>. Example: <run>ls</run>. DO NOT use markdown code blocks or plain text.')],
        }
        new_state = merge_state_updates(state, updates)
        log_state_transition(session_id, old_status, old_status, {'error': 'unknown_action'})
        return new_state
    
    # Log the action being executed
    action_type = type(action).__name__
    action_detail = ''
    if isinstance(action, CmdRunAction):
        action_detail = action.command[:100]
    elif isinstance(action, FileWriteAction):
        action_detail = action.path
    elif isinstance(action, WebSearchAction):
        action_detail = action.query[:100]
    logger.info("execute_start", session_id=session_id, action=action_type, detail=action_detail)

    # ── WebSearchAction: do live web search (no Docker needed) ──────────
    if isinstance(action, WebSearchAction):
        from .research_node import search_for_error

        tech_context = ''
        plan_str = state.get('plan', '{}')
        try:
            import json as _json
            plan = _json.loads(plan_str)
            tech_stack = plan.get('tech_stack', {})
            tech_context = f"{tech_stack.get('frontend', '')} {tech_stack.get('backend', '')} {tech_stack.get('language', '')}".strip()
        except Exception:
            pass

        search_result = await search_for_error(action.query, tech_context)

        obs = CmdOutputObservation(output=search_result, exit_code=0)
        logger.info("execute_search", session_id=session_id, query=action.query[:80])

        updates = {
            'last_obs': obs,
            'retries': state.get('retries', 0),
            'messages': [HumanMessage(
                content=f"Observation (web search for '{action.query}'):\n{search_result}"
            )],
            'execution_results': [{'action': 'search', 'query': action.query[:100], 'exit_code': 0}],
        }
        new_state = merge_state_updates(state, updates)
        log_state_transition(session_id, old_status, old_status, {'action': 'search'})
        return new_state
        
    if isinstance(action, CmdRunAction):
        try:
            import json as _json
            _plan_obj = _json.loads(state.get('plan', '{}'))
            if _plan_obj.get('tech_stack', {}).get('language') == 'abap':
                obs = CmdOutputObservation(output="Execution skipped for ABAP.", exit_code=0)
                updates = {
                    'last_obs': obs,
                    'retries': 0,
                    'messages': [HumanMessage(content="Observation: Command execution skipped because project language is ABAP.")],
                }
                new_state = merge_state_updates(state, updates)
                log_state_transition(session_id, old_status, old_status, {'action': 'run_skipped_abap'})
                return new_state
        except Exception:
            pass

    obs_dict = await runtime.execute(action)
    
    # ── Phase 2: Error analysis on execution results ────────────────────
    if 'error' in obs_dict:
        raw_output = obs_dict['output']
        exit_code = obs_dict.get('exit_code', 1)

        # Analyze the error
        parsed_error = _error_analyzer.analyze(raw_output, exit_code)
        error_context = _error_analyzer.format_for_prompt(parsed_error)

        obs = ErrorObservation(output=obs_dict['output'], exit_code=exit_code)
        logger.error(
            "execute_error",
            session_id=session_id,
            category=parsed_error.category.value,
            exit_code=obs.exit_code,
            output=obs.output[:200],
        )

        retries = state.get('retries', 0) + 1
        exec_retries = state.get('execute_retry_count', 0) + 1

        updates = {
            'last_obs': obs,
            'retries': retries,
            'execute_retry_count': exec_retries,
            'messages': [HumanMessage(
                content=f"Observation:\nExit code: {obs.exit_code}\n\n{error_context}"
            )],
            'last_error_analysis': error_context,
            'error_history': [{
                'category': parsed_error.category.value,
                'severity': parsed_error.severity.value,
                'message': parsed_error.message[:200],
                'file': parsed_error.file,
                'line': parsed_error.line,
            }],
            'execution_results': [{
                'action': action.type,
                'exit_code': exit_code,
                'error': parsed_error.category.value
            }],
        }
        new_state = merge_state_updates(state, updates)
        log_state_transition(session_id, old_status, old_status, {
            'error': parsed_error.category.value,
            'retries': retries
        })
        return new_state

    elif isinstance(action, BrowserAction):
        obs = BrowserObservation(output=obs_dict.get('output', ''), content=obs_dict.get('content', ''), exit_code=obs_dict.get('exit_code', 0))
        logger.info("execute_browser", session_id=session_id, exit_code=obs.exit_code)
    else:
        obs = CmdOutputObservation(output=obs_dict.get('output', ''), exit_code=obs_dict.get('exit_code', 0))
        if obs.exit_code == 0:
            logger.info("execute_success", session_id=session_id, output=obs.output[:100])
        else:
            # Non-zero exit code but not in 'error' key — still analyze
            parsed_error = _error_analyzer.analyze(obs.output, obs.exit_code)

            logger.error(
                "execute_failed",
                session_id=session_id,
                category=parsed_error.category.value,
                exit_code=obs.exit_code,
                output=obs.output[:200],
            )

            error_context = _error_analyzer.format_for_prompt(parsed_error)

            updates = {
                'last_obs': obs,
                'retries': state.get('retries', 0) + 1,
                'execute_retry_count': state.get('execute_retry_count', 0) + 1,
                'messages': [HumanMessage(
                    content=f"Observation:\nExit code: {obs.exit_code}\n\n{error_context}"
                )],
                'last_error_analysis': error_context,
                'execution_results': [{
                    'action': action.type,
                    'exit_code': obs.exit_code,
                    'error': parsed_error.category.value
                }],
            }
            new_state = merge_state_updates(state, updates)
            log_state_transition(session_id, old_status, old_status, {
                'error': parsed_error.category.value
            })
            return new_state
        
    retries = state.get('retries', 0) + (1 if getattr(obs, 'exit_code', 0) != 0 else 0)
    exec_retries = state.get('execute_retry_count', 0) + (1 if getattr(obs, 'exit_code', 0) != 0 else 0)
    
    # ── Phase 3: Update workspace summary after successful actions ──
    workspace_update = {}
    if obs_dict.get('exit_code', 0) == 0:
        # Refresh workspace file list
        try:
            result = await runtime.execute(CmdRunAction(
                command="find /workspace -maxdepth 3 -type f -not -path '*/node_modules/*' -not -path '*/.git/*' | head -100"
            ))
            if result.get('exit_code') == 0 and result.get('output'):
                workspace_update['workspace_summary'] = f"Current workspace files:\n{result['output'].strip()}"
        except Exception:
            pass

    raw_output = getattr(obs, 'output', '')
    # Smart truncation: suppress noisy package manager output
    lines = raw_output.splitlines()
    action_cmd = getattr(action, 'command', '').lower()
    is_pkg_manager = any(kw in action_cmd for kw in ['npm', 'pip', 'yarn', 'pnpm', 'apt-get'])
    
    if is_pkg_manager and getattr(obs, 'exit_code', 0) == 0 and len(lines) > 10:
        # Successful package installs: just show summary
        truncated_output = f"[Package manager output suppressed ({len(lines)} lines). Installation successful.]"
    elif len(lines) > 30:
        first_part = lines[:5]
        last_part = lines[-10:]
        omitted = len(lines) - 15
        truncated_output = "\n".join(first_part) + f"\n\n... [{omitted} lines omitted] ...\n\n" + "\n".join(last_part)
    else:
        truncated_output = raw_output

    # Track modified files if it's a FileWrite action
    modified_files = []
    if isinstance(action, FileWriteAction):
        modified_files = [action.path]

    result_state_updates: dict = {
        'last_obs': obs,
        'retries': retries,
        'execute_retry_count': exec_retries,
        'messages': [HumanMessage(content=f"Observation:\nExit code: {getattr(obs, 'exit_code', 0)}\nOutput:\n{truncated_output}")],
        'execution_results': [{
            'action': action.type,
            'exit_code': getattr(obs, 'exit_code', 0)
        }],
        'modified_files': modified_files,
    }
    if workspace_update:
        result_state_updates.update(workspace_update)
    
    new_state = merge_state_updates(state, result_state_updates)
    log_state_transition(session_id, old_status, old_status, {
        'action': action.type,
        'success': getattr(obs, 'exit_code', 0) == 0
    })
    return new_state


async def validate_node(state: AgentState) -> AgentState:
    """
    Validation Node - Multi-level app validation (Issue #10).
    
    Performs layered checks:
      Level 1: Compilation / syntax check (existing)
      Level 2: Port detection + process check (existing)
      Level 3: HTTP-level validation — status codes, error page detection  (NEW)
      Level 4: Stability check — app still alive after 3s delay (NEW)
    
    Produces a validation_score (0-100) and structured results.
    """
    from .state_manager import merge_state_updates, log_state_transition

    old_status = state.get('status', 'validate')
    session_id = state.get('session_id')
    if not session_id:
        raise RuntimeError("session_id is required for validation")
    await check_paused(session_id)
    runtime = DockerRuntime.get(session_id)

    # Log Validator Agent Start Activity
    try:
        from agent.observability import ObservabilityManager
        ObservabilityManager().log(
            session_id=session_id,
            agent_name="Validator Agent",
            event_type="activity",
            description="Validator Agent starting multi-level validation: compile, port, HTTP, stability",
            status="running",
            metadata={
                "task": "Verifying requirements and final build success",
                "progress": 80,
                "status": "running"
            }
        )
    except Exception:
        pass

    validation_logs = []
    validation_details = {}  # Structured results for each level
    tests_passed = True

    logger.info("validation_run_compile_checks", session_id=session_id)

    # ── Level 1: Compilation / Syntax Checks ───────────────────────────
    pkg_check = await runtime.execute(CmdRunAction(command="test -f /workspace/package.json"))
    is_node = pkg_check.get('exit_code') == 0

    level1_passed = True
    level1_details = []

    if is_node:
        compile_check = await runtime.execute(CmdRunAction(command="npx tsc --noEmit 2>&1 || npm run build --dry-run 2>&1 || echo 'No TypeScript or build runner configured'"))
        compile_out = compile_check.get('output', '').strip()
        if compile_check.get('exit_code') != 0 and "No TypeScript or build runner configured" not in compile_out:
            validation_logs.append(f"❌ Syntax/Compilation Error:\n{compile_out}")
            level1_details.append({'check': 'typescript_compile', 'passed': False, 'output': compile_out[:500]})
            level1_passed = False
            tests_passed = False
        elif "No TypeScript or build runner configured" in compile_out:
            js_syntax_check = await runtime.execute(CmdRunAction(
                command="find /workspace -maxdepth 4 -name '*.js' -not -path '*/node_modules/*' -not -path '*/.*' -exec node --check {} \\; 2>&1"
            ))
            js_syntax_out = js_syntax_check.get('output', '').strip()
            if js_syntax_check.get('exit_code') != 0 and js_syntax_out:
                validation_logs.append(f"❌ JavaScript Syntax Error:\n{js_syntax_out}")
                level1_details.append({'check': 'js_syntax', 'passed': False, 'output': js_syntax_out[:500]})
                level1_passed = False
                tests_passed = False
            else:
                level1_details.append({'check': 'js_syntax', 'passed': True})
        else:
            level1_details.append({'check': 'typescript_compile', 'passed': True})

        # Run tests if test script exists
        test_script_check = await runtime.execute(CmdRunAction(command="grep -q '\"test\"' /workspace/package.json"))
        if test_script_check.get('exit_code') == 0:
            test_run = await runtime.execute(CmdRunAction(command="npm test -- --watchAll=false --passWithNoTests 2>&1"))
            test_out = test_run.get('output', '').strip()
            if test_run.get('exit_code') != 0:
                validation_logs.append(f"❌ Unit Test Failures:\n{test_out}")
                level1_details.append({'check': 'unit_tests', 'passed': False, 'output': test_out[:500]})
                tests_passed = False
            else:
                level1_details.append({'check': 'unit_tests', 'passed': True})
    else:
        python_check = await runtime.execute(CmdRunAction(command="python3 -m py_compile $(find /workspace -maxdepth 3 -name '*.py' -not -path '*/.*') 2>&1"))
        if python_check.get('exit_code') != 0:
            validation_logs.append(f"❌ Python Compilation/Syntax Error:\n{python_check.get('output')}")
            level1_details.append({'check': 'python_compile', 'passed': False, 'output': python_check.get('output', '')[:500]})
            level1_passed = False
            tests_passed = False
        else:
            level1_details.append({'check': 'python_compile', 'passed': True})

        pytest_check = await runtime.execute(CmdRunAction(command="pytest --version 2>&1"))
        if pytest_check.get('exit_code') == 0:
            test_run = await runtime.execute(CmdRunAction(command="pytest 2>&1"))
            if test_run.get('exit_code') != 0:
                validation_logs.append(f"❌ Pytest Failures:\n{test_run.get('output')}")
                level1_details.append({'check': 'pytest', 'passed': False, 'output': test_run.get('output', '')[:500]})
                tests_passed = False
            else:
                level1_details.append({'check': 'pytest', 'passed': True})

    validation_details['level1_compilation'] = {
        'passed': level1_passed,
        'tests_passed': tests_passed,
        'details': level1_details,
    }

    # ── Level 1.5: File Content & Integrity Checks ─────────────────────
    level1_5_passed = True
    level1_5_details = []
    
    plan_files_to_check = []
    if state.get('plan'):
        try:
            import json as _json
            plan_data = _json.loads(state['plan'])
            for step in plan_data.get('steps', []):
                f = step.get('file')
                if f and f not in plan_files_to_check:
                    plan_files_to_check.append(f)
        except Exception:
            pass
            
    for f in ['src/App.jsx', 'src/App.tsx', 'src/main.jsx', 'src/index.css']:
        if f not in plan_files_to_check:
            exist_check = await runtime.execute(CmdRunAction(command=f"test -f /workspace/{f}"))
            if exist_check.get('exit_code') == 0:
                plan_files_to_check.append(f)
                
    for fpath in plan_files_to_check:
        exist_check = await runtime.execute(CmdRunAction(command=f"test -f /workspace/{fpath}"))
        if exist_check.get('exit_code') != 0:
            level1_5_details.append({'file': fpath, 'passed': False, 'reason': 'File does not exist'})
            validation_logs.append(f"❌ File Integrity: {fpath} does not exist in workspace")
            level1_5_passed = False
            continue
            
        cat_cmd = await runtime.execute(CmdRunAction(command=f"cat /workspace/{fpath} 2>/dev/null"))
        content = cat_cmd.get('output', '')
        
        if not content.strip():
            level1_5_details.append({'file': fpath, 'passed': False, 'reason': 'File is empty'})
            validation_logs.append(f"❌ File Integrity: {fpath} is empty")
            level1_5_passed = False
            continue
            
        is_boilerplate = False
        boilerplate_reasons = []
        
        # 1. Standard Boilerplate Check
        if fpath in ['src/App.jsx', 'src/App.tsx', 'App.jsx', 'App.tsx']:
            has_counter = "setCount" in content and "useState(0)" in content
            has_vite_react = "Vite + React" in content or "Vite and React logos" in content
            if has_counter and has_vite_react:
                is_boilerplate = True
                boilerplate_reasons.append("Unmodified Vite + React counter boilerplate detected")

        # 2. Python AST Parsing Check
        if fpath.endswith('.py') and not is_boilerplate:
            try:
                import ast as _ast
                _ast.parse(content)
            except SyntaxError as se:
                is_boilerplate = True
                boilerplate_reasons.append(f"Python AST Parsing SyntaxError: {str(se)} at line {se.lineno}")

        # 3. Placeholder / TODO Check
        if not is_boilerplate:
            # Matches TODO, FIXME, PLACEHOLDER, MOCK DATA, or stub comments
            placeholder_patterns = [
                r"(?i)\bTODO\b",
                r"(?i)\bFIXME\b",
                r"(?i)\bMOCK\s+DATA\b",
                r"(?i)\bPLACEHOLDER\b",
                r"(?i)\bINSERT\s+CODE\s+HERE\b",
                r"(?i)\bIMPLEMENT\s+HERE\b"
            ]
            import re as _re
            matched_placeholders = []
            for pat in placeholder_patterns:
                if _re.search(pat, content):
                    # Check if it is within common comment prefixes to avoid false positives on variable names
                    lines = content.splitlines()
                    for idx, line in enumerate(lines):
                        if _re.search(pat, line):
                            stripped = line.strip()
                            if any(stripped.startswith(prefix) for prefix in ['//', '#', '/*', '*']):
                                matched_placeholders.append(f"line {idx+1}: {stripped}")
                                break
            if matched_placeholders:
                is_boilerplate = True
                boilerplate_reasons.append(f"Placeholder/TODO comments detected: {', '.join(matched_placeholders[:2])}")

        # 4. LLM Critic Semantic Alignment Check
        if not is_boilerplate:
            try:
                llm = _resolve_llm(state, role="planner")
                critic_prompt = f"""You are an expert Code Critic and Validation Agent.
Your task is to analyze the file content below and determine if it is semantically aligned with the application requirements and the implementation plan.

[APPLICATION PLAN/REQUIREMENTS]:
{state.get('plan', 'No plan found')}

[FILE PATH]:
{fpath}

[FILE CONTENT]:
{content}

Analyze the file content. Check if:
1. The code actually implements the requirements mentioned in the plan, or if it is just irrelevant code, hallucinated functions, or generic boilerplate.
2. The code contains placeholder comments or stubbed logic (e.g., TODOs, mock values where real logic is expected).
3. The code is complete, correct, and directly related to building the application.

Respond in JSON format with two keys:
- "passed": boolean (true if the code is correct, complete, and aligned; false if it has placeholders, is unrelated, or is incomplete boilerplate/hallucination)
- "reason": string (a detailed explanation of why it failed or passed)

JSON Response:"""
                from langchain_core.messages import SystemMessage, HumanMessage
                response = await llm.ainvoke([
                    SystemMessage(content="You are a strict code validator. Always respond in valid JSON format."),
                    HumanMessage(content=critic_prompt)
                ])
                res_text = response.content if isinstance(response.content, str) else str(response.content)
                
                # Extract JSON block
                import json as _json
                import re as _re
                fenced = _re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', res_text)
                if fenced:
                    res_text = fenced.group(1)
                
                start_idx = res_text.find('{')
                end_idx = res_text.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    res_text = res_text[start_idx:end_idx+1]
                    
                critic_result = _json.loads(res_text)
                if not critic_result.get('passed', True):
                    is_boilerplate = True
                    boilerplate_reasons.append(f"Semantic Alignment Failure: {critic_result.get('reason', 'Unrelated or incomplete code')}")
            except Exception as e:
                logger.warning("critic_validation_failed", file=fpath, error=str(e))

        if is_boilerplate:
            level1_5_details.append({'file': fpath, 'passed': False, 'reason': ', '.join(boilerplate_reasons)})
            validation_logs.append(f"❌ File Integrity: {fpath} contains unmodified default Vite boilerplate or semantic issue: {', '.join(boilerplate_reasons)}")
            level1_5_passed = False
        else:
            level1_5_details.append({
                'file': fpath,
                'passed': True,
                'size': len(content),
                'preview': content[:200] + '...' if len(content) > 200 else content
            })

    validation_details['level1_5_integrity'] = {
        'passed': level1_5_passed,
        'details': level1_5_details,
    }

    # ── Level 2: Port Detection & Process Check ────────────────────────
    app_started = False
    app_url = None
    app_port = None
    error_output = []

    for port in [3000, 5173, 8000, 8080, 4200, 5000]:
        try:
            health = await runtime.health_check(port=port)
            if health.get('healthy'):
                app_started = True
                app_url = health.get('url')
                app_port = port
                logger.info("app_validated", session_id=session_id, port=port, url=app_url)
                break
        except Exception as e:
            error_output.append(f"Port {port}: {str(e)}")

    # Retry with delay if port check failed but compilation passed
    if not app_started and tests_passed:
        logger.info("validation_waiting_for_port", session_id=session_id)
        await asyncio.sleep(2.0)
        for port in [3000, 5173, 8000, 8080, 4200, 5000]:
            try:
                health = await runtime.health_check(port=port)
                if health.get('healthy'):
                    app_started = True
                    app_url = health.get('url')
                    app_port = port
                    logger.info("app_validated", session_id=session_id, port=port, url=app_url)
                    break
            except Exception:
                pass

    # Process check fallback
    process_info = ""
    if not app_started:
        result = await runtime.execute(CmdRunAction(command="ps aux | grep -E 'node|npm|python|flask|django|vite' | grep -v grep"))
        if result.get('exit_code') == 0 and result.get('output'):
            process_info = f"App process running but not accessible on common ports.\nProcesses:\n{result['output']}\n\nPort checks:\n" + "\n".join(error_output)
        else:
            process_info = f"No app process found running.\nPort checks:\n" + "\n".join(error_output)

        # Check app.log for crash info
        log_check = await runtime.execute(CmdRunAction(command="test -f /workspace/app.log"))
        if log_check.get('exit_code') == 0:
            log_content = await runtime.execute(CmdRunAction(command="tail -n 50 /workspace/app.log"))
            log_out = log_content.get('output', '').strip()
            if log_out:
                validation_logs.append(f"❌ Application Server Logs (app.log):\n{log_out}")

    validation_details['level2_port'] = {
        'passed': app_started,
        'port': app_port,
        'url': app_url,
        'process_info': process_info[:500] if process_info else '',
    }

    # ── Level 3: HTTP-Level Validation (NEW) ───────────────────────────
    http_validation_passed = False
    http_details = {}

    if app_started and app_url:
        try:
            # Check root endpoint
            root_health = await runtime.health_check(port=app_port or 3000)
            status_code = root_health.get('status_code', 0)
            http_details['root_status'] = status_code
            http_details['root_healthy'] = root_health.get('healthy', False)

            # Check if the response is an error page (5xx)
            if status_code >= 500:
                validation_logs.append(
                    f"⚠️ HTTP Warning: Root endpoint returned {status_code} (server error)"
                )
                http_details['error_page'] = True
            elif status_code >= 400 and status_code < 500:
                # 4xx on root is okay for APIs (might need /docs or /api)
                http_details['client_error'] = True
                # Try common API docs endpoints
                for alt_path in ['/docs', '/api', '/health', '/api/health']:
                    try:
                        alt_check = await runtime.execute(CmdRunAction(
                            command=f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{app_port}{alt_path} 2>/dev/null || echo '000'"
                        ))
                        alt_code = alt_check.get('output', '000').strip()
                        if alt_code.startswith('2'):
                            http_details[f'alt_{alt_path}'] = int(alt_code)
                            http_details['has_working_endpoint'] = True
                            break
                    except Exception:
                        pass
            else:
                http_validation_passed = True

            # Check response body sanity (not empty, not a crash dump)
            try:
                body_check = await runtime.execute(CmdRunAction(
                    command=f"curl -s http://localhost:{app_port}/ 2>/dev/null | head -c 2000"
                ))
                body = body_check.get('output', '').strip()
                http_details['body_length'] = len(body)

                if not body:
                    http_details['empty_response'] = True
                    validation_logs.append("⚠️ HTTP Warning: Root endpoint returned empty response")
                elif any(err in body.lower() for err in ['traceback', 'internal server error', 'cannot get', 'error occurred']):
                    http_details['error_in_body'] = True
                    validation_logs.append(
                        f"⚠️ HTTP Warning: Response body contains error indicators"
                    )
                else:
                    http_details['body_looks_healthy'] = True
            except Exception:
                pass

        except Exception as e:
            http_details['check_error'] = str(e)[:200]
            logger.warning("http_validation_error", session_id=session_id, error=str(e))

    validation_details['level3_http'] = {
        'passed': http_validation_passed,
        'details': http_details,
    }

    # ── Level 4: Stability Check (NEW) ─────────────────────────────────
    stability_passed = False
    stability_details = {}

    if app_started and app_url:
        # Wait 3 seconds and check if app is still alive
        await asyncio.sleep(3.0)
        try:
            recheck = await runtime.health_check(port=app_port or 3000)
            stability_passed = recheck.get('healthy', False)
            stability_details['recheck_status'] = recheck.get('status_code', 0)
            stability_details['still_alive'] = stability_passed

            if not stability_passed:
                validation_logs.append(
                    "❌ Stability Check Failed: App crashed or became unresponsive within 3 seconds"
                )
                # Check if process died
                proc_check = await runtime.execute(CmdRunAction(
                    command="ps aux | grep -E 'node|npm|python|flask|django|vite' | grep -v grep"
                ))
                stability_details['process_alive'] = proc_check.get('exit_code') == 0
        except Exception as e:
            stability_details['check_error'] = str(e)[:200]
            logger.warning("stability_check_error", session_id=session_id, error=str(e))

    validation_details['level4_stability'] = {
        'passed': stability_passed,
        'details': stability_details,
    }

    # ── Calculate Validation Score (0-100) ──────────────────────────────
    score = 0
    if validation_details['level1_compilation']['passed']:
        score += 20
    if validation_details['level1_compilation']['tests_passed']:
        score += 10
    if validation_details.get('level1_5_integrity', {}).get('passed', True):
        score += 15
    if validation_details['level2_port']['passed']:
        score += 25
    if validation_details['level3_http']['passed']:
        score += 15
    if validation_details['level4_stability']['passed']:
        score += 15

    validation_details['validation_score'] = score

    # ── Build final observation ─────────────────────────────────────────
    # Pass threshold: score >= 50 (compilation + port is minimum viable)
    final_passed = score >= 50

    if not app_started:
        if validation_logs:
            output_msg = f"Validation Failed (Score: {score}/100):\n" + "\n\n".join(validation_logs) + f"\n\nStartup Status:\n{process_info}"
        else:
            output_msg = f"Validation Failed (Score: {score}/100):\n{process_info}"

        obs = ValidatedObservation(
            output=output_msg,
            exit_code=1,
            app_started=False
        )
    elif not final_passed:
        # App runs but has critical issues
        output_msg = f"App running at {app_url} but has issues (Score: {score}/100):\n" + "\n\n".join(validation_logs)
        obs = ValidatedObservation(
            output=output_msg,
            exit_code=1,
            app_started=False
        )
    else:
        # Build success details
        success_parts = [f"App is running and accessible at {app_url} (Score: {score}/100)."]
        if http_validation_passed:
            success_parts.append("HTTP endpoints responding correctly.")
        if stability_passed:
            success_parts.append("Stability check passed (app alive after 3s).")
        if tests_passed:
            success_parts.append("All syntax and test validations passed.")
        if validation_logs:
            success_parts.append("Warnings:\n" + "\n".join(validation_logs))

        obs = ValidatedObservation(
            output="\n".join(success_parts),
            exit_code=0,
            app_started=True
        )

    # Log Validator Agent End Activity & Save Summary
    try:
        from agent.observability import ObservabilityManager
        ObservabilityManager().log(
            session_id=session_id,
            agent_name="Validator Agent",
            event_type="activity",
            description=f"Validator Agent completed multi-level validation. Score: {score}/100. Status: {'SUCCESS' if obs.app_started else 'FAILED'}",
            status="success" if obs.app_started else "failed",
            metadata={
                "task": "Verifying requirements and final build success",
                "progress": 100,
                "status": "success" if obs.app_started else "failed",
                "validation_score": score,
                "levels": {
                    "compilation": validation_details['level1_compilation']['passed'],
                    "integrity": validation_details.get('level1_5_integrity', {}).get('passed', True),
                    "port": validation_details['level2_port']['passed'],
                    "http": validation_details['level3_http']['passed'],
                    "stability": validation_details['level4_stability']['passed'],
                }
            }
        )

        # Save session summary log at the very end
        summary_dict = ObservabilityManager().get_session_summary(session_id)
        ObservabilityManager().log(
            session_id=session_id,
            agent_name="Validator Agent",
            event_type="session_summary",
            description="Final execution session summary compiled",
            status="success",
            metadata=summary_dict
        )
    except Exception:
        pass

    new_status = 'done' if obs.app_started else 'error'
    validate_retries = state.get('validate_retry_count', 0) + (0 if obs.app_started else 1)

    updates = {
        'last_obs': obs,
        'status': new_status,
        'validate_retry_count': validate_retries,
        'messages': [AIMessage(content=f'Validation: {obs.output}')],
        'validation_results': [validation_details],
        'validation_passed': obs.app_started,
        'app_port': app_port or 0,
    }

    new_state = merge_state_updates(state, updates)
    log_state_transition(session_id, old_status, new_status, {
        'app_started': obs.app_started,
        'tests_passed': tests_passed,
        'validation_score': score,
        'http_passed': http_validation_passed,
        'stability_passed': stability_passed,
    })
    return new_state


async def execute_structural_check(state: AgentState) -> AgentState:
    """
    Two-tier structural verification gate before semantic execution evaluation.
    Checks that previous commands had exit_code == 0 AND expected output files/binaries exist on disk.
    Pure Python check (no LLM call).
    """
    from .state_manager import merge_state_updates
    from runtime import DockerRuntime
    from .schema import CmdRunAction
    import json
    
    session_id = state.get('session_id', '')
    last_obs = state.get('last_obs')
    
    # 1. Check if the most recent execution or action batch failed with non-zero exit code
    exit_code = getattr(last_obs, 'exit_code', 0) if last_obs else 0
    if exit_code != 0:
        logger.warning("execute_structural_check_failed_exit_code", session_id=session_id, exit_code=exit_code)
        structural_retries = state.get('execute_structural_retries', 0)
        if structural_retries >= 3:
            updates = {
                'status': 'error',
                'execute_structural_ok': False,
                'messages': [AIMessage(content="[Execute Structural Check] Failed structural checks too many times.")]
            }
            return merge_state_updates(state, updates)
            
        updates = {
            'execute_structural_ok': False,
            'execute_structural_retries': structural_retries + 1,
            'messages': [AIMessage(content=f"[Execute Structural Check] Previous command exited with non-zero code {exit_code}.")]
        }
        return merge_state_updates(state, updates)
        
    # 2. Check if expected output files exist on disk (for non-ABAP repos)
    plan_str = state.get('plan', '{}')
    is_abap = False
    try:
        plan_dict = json.loads(plan_str)
        if plan_dict.get('tech_stack', {}).get('language') == 'abap':
            is_abap = True
    except Exception:
        pass

    if not is_abap and session_id:
        runtime = DockerRuntime.get(session_id)
        modified_files = state.get('modified_files', [])
        if runtime and modified_files:
            for fpath in modified_files[:5]:
                full_path = f"/workspace/{fpath.lstrip('/')}"
                res = await runtime.execute(CmdRunAction(command=f"test -f '{full_path}' || test -d '{full_path}'"))
                if res.get('exit_code') != 0:
                    logger.warning("execute_structural_check_missing_file", session_id=session_id, file=fpath)
                    updates = {
                        'execute_structural_ok': False,
                        'messages': [AIMessage(content=f"[Execute Structural Check] Expected output file {fpath} does not exist on disk.")]
                    }
                    return merge_state_updates(state, updates)
                    
    updates = {
        'execute_structural_ok': True
    }
    return merge_state_updates(state, updates)


async def validate_structural_check(state: AgentState) -> AgentState:
    """
    Two-tier structural verification gate before semantic validation node.
    Checks that a test report file was actually produced and is parseable (or required build/config artifacts exist).
    Pure Python check (no LLM call).
    """
    from .state_manager import merge_state_updates
    from runtime import DockerRuntime
    from .schema import CmdRunAction
    import json
    
    session_id = state.get('session_id', '')
    plan_str = state.get('plan', '{}')
    tech_stack = {}
    try:
        plan_dict = json.loads(plan_str)
        tech_stack = plan_dict.get('tech_stack', {})
    except Exception:
        pass

    # For ABAP or simple static HTML without framework, skip test report requirement
    lang = tech_stack.get('language', '').lower()
    backend = tech_stack.get('backend', '').lower()
    frontend = tech_stack.get('frontend', '').lower()
    if lang == 'abap' or backend == 'abap' or (frontend == 'html_css_js' and backend == 'none'):
        updates = {'validate_structural_ok': True}
        return merge_state_updates(state, updates)
        
    if session_id:
        runtime = DockerRuntime.get(session_id)
        if runtime:
            res = await runtime.execute(CmdRunAction(
                command="find /workspace -maxdepth 3 \( -name '*test-report*.*' -o -name '*junit*.*' -o -name '*coverage*.*' -o -name 'package.json' -o -name 'pytest.ini' -o -name 'pyproject.toml' -o -name 'requirements.txt' \) 2>/dev/null | head -n 1"
            ))
            output = res.get('output', '').strip()
            if res.get('exit_code') != 0 or not output:
                logger.warning("validate_structural_check_no_report_or_config", session_id=session_id)
                updates = {
                    'validate_structural_ok': False,
                    'messages': [AIMessage(content="[Validate Structural Check] No test report file or validation manifest found in workspace.")]
                }
                return merge_state_updates(state, updates)
                
    updates = {'validate_structural_ok': True}
    return merge_state_updates(state, updates)

