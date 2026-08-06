import time
import json
import difflib
import queue
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List
import psycopg
from psycopg.rows import dict_row
from langchain_core.callbacks import BaseCallbackHandler
from core.config import get_settings
from core.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Global registry of active websockets to broadcast events in real-time
# Key: session_id, Value: list of ws_callback async functions
WEBSOCKET_BROADCASTERS: Dict[str, List[Any]] = {}

def register_broadcaster(session_id: str, callback: Any):
    """Register a WebSocket callback to broadcast observability events."""
    if session_id not in WEBSOCKET_BROADCASTERS:
        WEBSOCKET_BROADCASTERS[session_id] = []
    if callback not in WEBSOCKET_BROADCASTERS[session_id]:
        WEBSOCKET_BROADCASTERS[session_id].append(callback)

def unregister_broadcaster(session_id: str, callback: Any):
    """Unregister a WebSocket callback."""
    if session_id in WEBSOCKET_BROADCASTERS:
        try:
            WEBSOCKET_BROADCASTERS[session_id].remove(callback)
        except ValueError:
            pass
        if not WEBSOCKET_BROADCASTERS[session_id]:
            WEBSOCKET_BROADCASTERS.pop(session_id)


class ObservabilityManager:
    """Handles persistence, querying, and formatting of AI Agent Observability Logs."""
    
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ObservabilityManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, dsn: Optional[str] = None) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._dsn = dsn or settings.database_url
        self._use_memory = False
        self._memory_logs: list[dict] = []
        self._ensure_table()
        
        # Thread-safe queue for asynchronous database writes
        self._queue = queue.Queue()
        self._worker_thread = threading.Thread(target=self._db_worker, daemon=True)
        self._worker_thread.start()

    def _ensure_table(self) -> None:
        try:
            with psycopg.connect(self._dsn) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agent_observability_logs (
                        id SERIAL PRIMARY KEY,
                        session_id UUID NOT NULL,
                        trace_id UUID,
                        stage_id TEXT,
                        parent_span_id TEXT,
                        timestamp TIMESTAMPTZ DEFAULT NOW(),
                        agent_name TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        description TEXT NOT NULL,
                        status TEXT NOT NULL,
                        duration DOUBLE PRECISION DEFAULT 0.0,
                        metadata JSONB DEFAULT '{}'::jsonb
                    );
                    CREATE INDEX IF NOT EXISTS idx_agent_obs_session_id ON agent_observability_logs(session_id);
                    CREATE INDEX IF NOT EXISTS idx_agent_obs_event_type ON agent_observability_logs(event_type);
                    """
                )
                
                # Add columns if they do not exist
                conn.execute("ALTER TABLE agent_observability_logs ADD COLUMN IF NOT EXISTS trace_id UUID;")
                conn.execute("ALTER TABLE agent_observability_logs ADD COLUMN IF NOT EXISTS stage_id TEXT;")
                conn.execute("ALTER TABLE agent_observability_logs ADD COLUMN IF NOT EXISTS parent_span_id TEXT;")
                conn.commit()
        except Exception as e:
            logger.error("obs_ensure_table_failed", error=str(e))

    def _db_worker(self):
        """Background thread worker to insert logs into PostgreSQL sequentially without blocking."""
        conn = None
        while True:
            try:
                task = self._queue.get()
                if task is None:
                    break
                
                if len(task) == 11:
                    session_id, trace_id, stage_id, parent_span_id, timestamp, agent_name, event_type, description, status, duration, metadata = task
                else:
                    session_id, timestamp, agent_name, event_type, description, status, duration, metadata = task
                    trace_id = None
                    stage_id = None
                    parent_span_id = None
                
                # Check connection status
                if self._use_memory:
                    self._memory_logs.append({"session_id": session_id, "agent_name": agent_name, "event_type": event_type, "description": description})
                    self._queue.task_done() if hasattr(self._queue, 'task_done') else None
                    continue

                if conn is None or conn.closed:
                    try:
                        conn = psycopg.connect(self._dsn)
                    except Exception as e:
                        logger.warning("obs_db_fallback_memory", error=str(e))
                        self._use_memory = True
                        self._memory_logs.append({"session_id": session_id, "agent_name": agent_name, "event_type": event_type, "description": description})
                        continue
                
                try:
                    conn.execute(
                        """
                        INSERT INTO agent_observability_logs 
                        (session_id, trace_id, stage_id, parent_span_id, timestamp, agent_name, event_type, description, status, duration, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            session_id,
                            trace_id,
                            stage_id,
                            parent_span_id,
                            timestamp,
                            agent_name,
                            event_type,
                            description,
                            status,
                            duration,
                            json.dumps(metadata, default=str),
                        ),
                    )
                    conn.commit()
                except Exception as db_err:
                    logger.error("obs_db_insert_failed_worker", error=str(db_err))
                    try:
                        conn.close()
                    except Exception:
                        pass
                    conn = None
                    # Put task back in queue to retry
                    self._queue.put(task)
                    time.sleep(1)
            except Exception as e:
                logger.error("obs_worker_loop_error", error=str(e))
                time.sleep(1)

    def log(
        self,
        session_id: str,
        agent_name: str,
        event_type: str,
        description: str,
        status: str = "success",
        duration: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        stage_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Save a new log entry to the database asynchronously and broadcast it to active web sockets."""
        if metadata is None:
            metadata = {}

        timestamp = datetime.now()
        log_entry = {
            "session_id": session_id,
            "trace_id": trace_id,
            "stage_id": stage_id,
            "parent_span_id": parent_span_id,
            "timestamp": timestamp.isoformat(),
            "agent_name": agent_name,
            "event_type": event_type,
            "description": description,
            "status": status,
            "duration": duration,
            "metadata": metadata,
        }

        # 1. Enqueue database write operation
        import uuid
        is_valid_uuid = False
        if session_id:
            try:
                uuid.UUID(str(session_id))
                is_valid_uuid = True
            except ValueError:
                pass

        if is_valid_uuid:
            self._queue.put((
                str(session_id),
                trace_id,
                stage_id,
                parent_span_id,
                timestamp,
                agent_name,
                event_type,
                description,
                status,
                duration,
                metadata
            ))
        else:
            logger.warning("obs_log_skipped_invalid_uuid", session_id=session_id)

        # 2. Broadcast via WebSockets in current event loop
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(self._broadcast_event(session_id, log_entry))
        except RuntimeError:
            pass

        return log_entry

    async def _broadcast_event(self, session_id: str, log_entry: Dict[str, Any]):
        """Broadcast log event to registered websocket connections."""
        callbacks = WEBSOCKET_BROADCASTERS.get(session_id, [])
        if not callbacks:
            return
        
        payload = {
            "type": "observability_log",
            "log": log_entry
        }
        
        for cb in callbacks:
            try:
                await cb(payload)
            except Exception as e:
                logger.debug("obs_ws_broadcast_failed", error=str(e))

    def get_logs(
        self,
        session_id: str,
        agent_name: Optional[str] = None,
        event_type: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query and filter logs for a given session."""
        query = """
            SELECT id, session_id::text, timestamp, agent_name, event_type, description, status, duration, metadata
            FROM agent_observability_logs
            WHERE session_id = %s
        """
        params = [session_id]

        if agent_name:
            query += " AND agent_name = %s"
            params.append(agent_name)
        if event_type:
            query += " AND event_type = %s"
            params.append(event_type)
        if status:
            query += " AND status = %s"
            params.append(status)
        if search:
            query += """ AND (
                description ILIKE %s OR 
                agent_name ILIKE %s OR 
                event_type ILIKE %s OR
                metadata::text ILIKE %s
            )"""
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param, search_param])

        query += " ORDER BY timestamp ASC"

        try:
            with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
                rows = conn.execute(query, params).fetchall()
                # Format timestamps to iso strings
                for r in rows:
                    if r["timestamp"]:
                        r["timestamp"] = r["timestamp"].isoformat()
                    # Ensure metadata is dict
                    if isinstance(r["metadata"], str):
                        r["metadata"] = json.loads(r["metadata"])
                return rows
        except Exception as e:
            logger.error("obs_get_logs_failed", session_id=session_id, error=str(e))
            return []

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Aggregate logs to provide a comprehensive session summary."""
        logs = self.get_logs(session_id)
        
        files_created = 0
        files_modified = 0
        files_deleted = 0
        commands_executed = 0
        errors_encountered = 0
        fixes_applied = 0
        build_attempts = 0
        total_tokens = 0
        agent_token_usage = {}
        agent_runtime = {}
        total_duration = 0.0
        status = "SUCCESS"

        # Advanced Metrics
        judge_attempts = 0
        judge_rejections = 0
        planner_attempts = 0
        hallucinated_files_detected = 0
        invalid_paths_detected = 0
        duplicate_plannings = 0
        retry_count = 0
        timeline = []

        start_time = None
        end_time = None

        for log in logs:
            duration = log.get("duration", 0.0)
            total_duration += duration
            agent_name = log.get("agent_name", "unknown")
            agent_runtime[agent_name] = agent_runtime.get(agent_name, 0.0) + duration
            
            # Timestamp calculations
            ts = datetime.fromisoformat(log["timestamp"])
            if start_time is None or ts < start_time:
                start_time = ts
            if end_time is None or ts > end_time:
                end_time = ts

            e_type = log["event_type"]
            meta = log.get("metadata", {})
            desc = log.get("description", "")
            
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            if not isinstance(meta, dict):
                meta = {}

            # Populate Timeline
            timeline.append({
                "timestamp": ts.isoformat(),
                "agent": agent_name,
                "event": e_type,
                "status": log.get("status", "SUCCESS")
            })

            # Base Metrics
            if e_type == "file_create":
                files_created += 1
            elif e_type == "file_modify":
                files_modified += 1
            elif e_type == "file_delete":
                files_deleted += 1
            elif e_type == "terminal":
                commands_executed += 1
            elif e_type == "error":
                errors_encountered += 1
                status = "FAILED"
                # Check for specific invalid path errors
                if "No such file or directory" in desc or "does not exist" in desc:
                    invalid_paths_detected += 1
            elif e_type == "autofix":
                fixes_applied += 1
            elif e_type == "build":
                build_attempts += 1
            elif e_type == "retry":
                retry_count += 1
            elif e_type == "prompt_log":
                usage = meta.get("token_usage", {})
                if isinstance(usage, str):
                    try:
                        usage = json.loads(usage)
                    except Exception:
                        usage = {}
                if isinstance(usage, dict):
                    t_tokens = usage.get("total_tokens", 0)
                    total_tokens += t_tokens
                    agent_token_usage[agent_name] = agent_token_usage.get(agent_name, 0) + t_tokens
                
                # Check planner/judge stats
                if agent_name == "Judge Agent":
                    judge_attempts += 1
                    if "Rejected" in desc or "rejected" in desc.lower():
                        judge_rejections += 1
                    # Hallucination tracking based on Judge feedback
                    if "Framework mismatch" in desc or "hallucinated" in desc.lower() or "not match architecture" in desc.lower():
                        hallucinated_files_detected += 1
                elif agent_name == "Planner Agent":
                    planner_attempts += 1
                    if planner_attempts > 1:
                        duplicate_plannings += 1

        # Advanced Calculation
        estimated_cost = round((total_tokens / 1000) * 0.002, 6)
        cost_per_agent = {k: round((v / 1000) * 0.002, 6) for k, v in agent_token_usage.items()}
        
        judge_pass_rate = 100.0
        if judge_attempts > 0:
            judge_pass_rate = round(((judge_attempts - judge_rejections) / judge_attempts) * 100, 2)
            
        planner_accuracy_score = 100.0
        if planner_attempts > 0:
            # Penalize accuracy based on rejections and duplicate plannings
            penalty = (judge_rejections * 15) + (duplicate_plannings * 10)
            planner_accuracy_score = max(0.0, 100.0 - penalty)
            
        architecture_consistency_score = max(0.0, 100.0 - (hallucinated_files_detected * 20))
        
        execution_success_rate = 100.0
        if commands_executed > 0:
            execution_success_rate = round(((commands_executed - errors_encountered) / commands_executed) * 100, 2)

        duration_sec = (end_time - start_time).total_seconds() if (start_time and end_time) else total_duration

        return {
            "session_id": session_id,
            "files_created": files_created,
            "files_modified": files_modified,
            "files_deleted": files_deleted,
            "commands_executed": commands_executed,
            "errors_encountered": errors_encountered,
            "fixes_applied": fixes_applied,
            "build_attempts": build_attempts,
            "total_tokens": total_tokens,
            "agent_token_usage": agent_token_usage,
            "cost_per_agent": cost_per_agent,
            "estimated_cost": estimated_cost,
            "duration_seconds": round(duration_sec, 2),
            "agent_runtime_seconds": {k: round(v, 2) for k, v in agent_runtime.items()},
            "final_status": status,
            # New Advanced Metrics
            "agent_status_timeline": timeline,
            "planner_accuracy_score": planner_accuracy_score,
            "judge_pass_rate": judge_pass_rate,
            "architecture_consistency_score": architecture_consistency_score,
            "hallucinated_files_detected": hallucinated_files_detected,
            "invalid_paths_detected": invalid_paths_detected,
            "duplicate_plannings": duplicate_plannings,
            "retry_count": retry_count,
            "execution_success_rate": execution_success_rate,
        }

    def export_as_csv(self, session_id: str) -> str:
        """Export logs as a CSV string."""
        import csv
        import io

        logs = self.get_logs(session_id)
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Headers
        writer.writerow(["Timestamp", "Agent Name", "Event Type", "Description", "Status", "Duration (s)", "Metadata"])
        
        for log in logs:
            writer.writerow([
                log["timestamp"],
                log["agent_name"],
                log["event_type"],
                log["description"],
                log["status"],
                log["duration"],
                json.dumps(log["metadata"], default=str)
            ])
            
        return output.getvalue()

    def export_as_pdf(self, session_id: str, title: str = "AI Agent Observability Report") -> bytes:
        """Generate a well-formatted PDF report of the session using PyMuPDF."""
        import fitz

        logs = self.get_logs(session_id)
        summary = self.get_session_summary(session_id)

        # Create a new PDF document
        doc = fitz.open()
        
        # Page layout configurations
        margin = 50
        width = 595  # A4 width
        height = 842 # A4 height
        
        # Color palette
        brand_color = fitz.pdfcolor["darkblue"]
        text_color = fitz.pdfcolor["black"]
        muted_color = fitz.pdfcolor["gray"]
        bg_color = (0.95, 0.95, 0.97)

        # Helper to start a new page
        def new_page():
            page = doc.new_page(width=width, height=height)
            page.draw_rect(fitz.Rect(margin - 10, margin - 10, width - margin + 10, height - margin + 10), color=(0.9, 0.9, 0.9), width=1)
            return page, margin + 20

        # Title Page
        page, y = new_page()
        
        page.insert_text((margin, y), title, fontsize=20, color=brand_color)
        y += 30
        page.insert_text((margin, y), f"Session ID: {session_id}", fontsize=10, color=muted_color)
        y += 15
        page.insert_text((margin, y), f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", fontsize=10, color=muted_color)
        y += 40

        # Draw summary box
        page.draw_rect(fitz.Rect(margin, y, width - margin, y + 150), fill=bg_color, width=0)
        page.insert_text((margin + 15, y + 25), "SESSION STATE SUMMARY", fontsize=12, color=brand_color)
        
        summary_lines = [
            f"Files Created: {summary['files_created']}   |   Modified: {summary['files_modified']}   |   Deleted: {summary['files_deleted']}",
            f"Commands Executed: {summary['commands_executed']}",
            f"Build Attempts: {summary['build_attempts']}   |   Errors: {summary['errors_encountered']}",
            f"Auto-Fixes Applied: {summary['fixes_applied']}",
            f"Total Tokens: {summary['total_tokens']} (Est. Cost: ${summary['estimated_cost']})",
            f"Duration: {summary['duration_seconds']} seconds",
            f"Final Status: {summary['final_status']}"
        ]
        
        sy = y + 50
        for line in summary_lines:
            page.insert_text((margin + 15, sy), line, fontsize=10, color=text_color)
            sy += 15
            
        y += 180
        page.insert_text((margin, y), "CHRONOLOGICAL LOG TIMELINE", fontsize=14, color=brand_color)
        y += 25

        for log in logs:
            if y > height - margin - 40:
                page, y = new_page()
                page.insert_text((margin, y), "LOG TIMELINE (CONTINUED)", fontsize=10, color=brand_color)
                y += 20

            # Render log header
            ts = datetime.fromisoformat(log["timestamp"]).strftime("%I:%M:%S %p")
            header = f"[{ts}] {log['agent_name']} — {log['event_type'].upper()}"
            page.insert_text((margin, y), header, fontsize=9, color=brand_color)
            y += 12
            
            # Render description
            desc = log["description"]
            page.insert_text((margin + 15, y), desc, fontsize=9, color=text_color)
            y += 12

            meta = log.get("metadata", {})
            meta_str = ""
            if log["event_type"] == "terminal":
                meta_str = f"Command: {meta.get('command')} | Exit Code: {meta.get('exit_code')}"
            elif log["event_type"] == "prompt_log":
                meta_str = f"Tokens: {meta.get('token_usage', {}).get('total_tokens')} | Prompt: {meta.get('prompt', '')[:80]}..."
            elif log["event_type"] in ("file_create", "file_modify", "file_read"):
                meta_str = f"File: {meta.get('file_path')}"
            elif log["event_type"] == "error":
                meta_str = f"Error: {meta.get('error_message')} at line {meta.get('line_number')}"

            if meta_str:
                page.insert_text((margin + 15, y), meta_str, fontsize=8, color=muted_color)
                y += 12
                
            y += 8

        return doc.write()


# ── LangChain Callback Handler ──────────────────────────────────────────

class ObservabilityCallbackHandler(BaseCallbackHandler):
    """LangChain callback to automatically capture Prompts and Responses."""

    def __init__(self, session_id: str, agent_name: str) -> None:
        super().__init__()
        self.session_id = session_id
        self.agent_name = agent_name
        self.start_time = 0.0
        self.prompt_text = ""
        self.manager = ObservabilityManager()

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any,
    ) -> Any:
        self.start_time = time.time()
        self.prompt_text = "\n".join(prompts)

    def on_llm_end(
        self,
        response: Any,
        **kwargs: Any,
    ) -> Any:
        duration = round(time.time() - self.start_time, 2)
        
        generations = response.generations
        if not generations or not generations[0]:
            return
            
        generation = generations[0][0]
        response_text = getattr(generation, "text", "") or getattr(generation, "content", "")
        if not response_text and hasattr(generation, "message"):
            response_text = generation.message.content

        # Retrieve token counts from LLM output if available
        llm_output = response.llm_output or {}
        token_usage = llm_output.get("token_usage", {
            "prompt_tokens": len(self.prompt_text) // 4,
            "completion_tokens": len(response_text) // 4,
            "total_tokens": (len(self.prompt_text) + len(response_text)) // 4
        })

        self.manager.log(
            session_id=self.session_id,
            agent_name=self.agent_name,
            event_type="prompt_log",
            description=f"LLM Interaction completed by {self.agent_name}",
            duration=duration,
            metadata={
                "prompt": self.prompt_text,
                "response": response_text,
                "token_usage": token_usage,
                "processing_time": duration,
            },
        )
