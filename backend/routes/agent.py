"""
Agent routes — WebSocket streaming + HTTP endpoints for session management.

This module owns all the agent-facing API surface. The WebSocket endpoint
streams LangGraph events to the frontend, and the HTTP endpoints let the
frontend query session status, list sessions, etc.
"""
import uuid
import json
import asyncio
import time
from typing import Optional
import os
import tempfile
from collections import deque
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query, UploadFile, File, Response
from pydantic import BaseModel as PydanticBaseModel
from langchain_core.messages import HumanMessage

from core.config import get_settings
from core.logger import get_logger
from services.settings_service import SettingsService
from services.conversation_service import ConversationService
from services.sandbox_service import SandboxService

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/agent", tags=["agent"])

PING_INTERVAL = 10
PING_TIMEOUT = 120  # 2 minutes — allows for rate-limit backoff waits
MAX_EVENT_BUFFER = 1000


class _EventBuffer:
    def __init__(self, max_size: int = MAX_EVENT_BUFFER) -> None:
        self._max_size = max_size
        self._buffers: dict[str, deque[dict]] = {}
        self._seq: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def add(self, session_id: str, payload: dict) -> int:
        async with self._lock:
            seq = self._seq.get(session_id, 0) + 1
            self._seq[session_id] = seq
            buf = self._buffers.setdefault(session_id, deque(maxlen=self._max_size))
            item = {**payload, "seq": seq}
            buf.append(item)
            
            # Persist to PostgreSQL asynchronously to avoid blocking
            try:
                from services.conversation_service import ConversationService
                service = ConversationService()
                await asyncio.to_thread(
                    service.add_event,
                    session_id,
                    payload.get("type", "unknown"),
                    payload,
                    seq
                )
            except Exception as e:
                logger.warning("event_persistence_failed", session_id=session_id, error=str(e))
                
            return seq

    async def replay_after(self, session_id: str, last_seq: int) -> list[dict]:
        async with self._lock:
            # If not in memory (e.g. server restarted), lazily load from DB
            if session_id not in self._buffers:
                try:
                    from services.conversation_service import ConversationService
                    service = ConversationService()
                    events = await asyncio.to_thread(service.get_events, session_id)
                    max_seq = max([e.get("seq", 0) for e in events]) if events else 0
                    self._seq[session_id] = max_seq
                    
                    buf = self._buffers.setdefault(session_id, deque(maxlen=self._max_size))
                    for e in events:
                        buf.append(e)
                except Exception as e:
                    logger.warning("event_load_failed", session_id=session_id, error=str(e))

            buf = list(self._buffers.get(session_id, deque()))
        return [item for item in buf if item.get("seq", 0) > last_seq]


EVENT_BUFFER = _EventBuffer()



class CreateSessionRequest(PydanticBaseModel):
    profile_id: str | None = None


class WriteFileRequest(PydanticBaseModel):
    path: str
    content: str



# ── Helpers ─────────────────────────────────────────────────────────────

def serialize_data(data):
    """Recursively serialize Pydantic models, Exceptions, and LangChain messages for JSON."""
    if isinstance(data, PydanticBaseModel):
        return serialize_data(data.model_dump())
    if isinstance(data, dict):
        return {str(k): serialize_data(v) for k, v in data.items()}
    if isinstance(data, (list, tuple, set)):
        return [serialize_data(v) for v in data]
    if isinstance(data, Exception):
        return {"error": data.__class__.__name__, "message": str(data)}
    
    # Handle LangChain messages gracefully
    if hasattr(data, 'content') and hasattr(data, 'type') and not isinstance(data, type):
        return {'type': getattr(data, 'type', type(data).__name__), 'content': serialize_data(getattr(data, 'content', str(data)))}
    
    # Safe fallback for non-primitive types
    if data is not None and not isinstance(data, (str, int, float, bool)):
        import json
        try:
            json.dumps(data)
            return data
        except (TypeError, ValueError):
            return str(data)
            
    return data


# ── HTTP Endpoints ──────────────────────────────────────────────────────

@router.get("/health")
async def health():
    """Quick health-check for the agent subsystem."""
    return {"status": "ok", "version": settings.APP_VERSION}


@router.get("/groq/stats")
async def groq_key_stats():
    """Get Groq API key pool statistics — useful for monitoring rate limits."""
    try:
        from agent.groq_key_pool import get_groq_pool
        pool = get_groq_pool()
        return {
            "pool_size": pool.size,
            "keys": pool.get_stats(),
            "provider": settings.DEFAULT_LLM_PROVIDER,
            "model": settings.DEFAULT_LLM_MODEL,
        }
    except Exception as e:
        return {"error": str(e), "pool_size": 0, "keys": []}


@router.post("/sessions")
async def create_session(payload: CreateSessionRequest | None = None):
    """Create a new agent session and return its ID."""
    conversation_service = ConversationService()
    try:
        conversation = conversation_service.create_conversation()
        session_id = conversation["id"]
    except Exception as exc:
        logger.warning("conversation_create_failed", error=str(exc))
        conversation = None
        session_id = str(uuid.uuid4())

    logger.info("session_created", session_id=session_id)

    # Get LLM profile (from request or default)
    service = SettingsService()
    profile = None
    if payload and payload.profile_id:
        profile = service.get_profile(payload.profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
    else:
        profile = service.get_default_profile()

    # If no profile found, create a default one using current settings
    if profile is None:
        logger.info("no_default_profile_using_settings", session_id=session_id)

    response = {"session_id": session_id}
    if conversation:
        response["conversation"] = conversation
    if profile:
        response["profile_id"] = profile.id
        response["profile"] = profile.model_dump()
    return response


# ── WebSocket Endpoint ──────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    Main agent communication channel.

    The frontend sends a JSON payload:
        { "session_id": "...", "message": "..." }

    The backend streams LangGraph events back as JSON frames.
    """
    await ws.accept()
    session_id = "unknown"

    last_pong = time.time()
    receive_task = None
    ping_task = None
    graph_task = None
    monitor_task = None

    async def receive_loop():
        nonlocal last_pong, graph_task
        while True:
            try:
                msg = await ws.receive_json()
            except WebSocketDisconnect:
                break
            except Exception:
                break

            msg_type = msg.get("type")
            if msg_type == "pong":
                last_pong = time.time()
                continue
            if msg_type == "ping":
                await ws.send_json({"type": "pong", "ts": msg.get("ts")})
                last_pong = time.time()
                continue
            if msg_type == "interactive_input":
                # User typed input for an interactive command prompt
                input_data = msg.get("data", "")
                if input_data and session_id != "unknown":
                    try:
                        from runtime import send_interactive_input
                        send_interactive_input(session_id, input_data)
                    except Exception as e:
                        logger.warning("interactive_input_failed", session_id=session_id, error=str(e))
            elif msg_type == "kill_process":
                pid = msg.get("pid")
                sig = msg.get("signal", 15)
                if session_id != "unknown":
                    try:
                        from runtime import DockerRuntime
                        rt = DockerRuntime.get(session_id)
                        await rt.kill_process(pid, sig)
                    except Exception as e:
                        logger.warning("ws_kill_process_failed", session_id=session_id, pid=pid, error=str(e))
            elif msg_type == "restart_command":
                if session_id != "unknown":
                    try:
                        from runtime import DockerRuntime
                        rt = DockerRuntime.get(session_id)
                        rt.should_restart_current = True
                    except Exception as e:
                        logger.warning("ws_restart_command_failed", session_id=session_id, error=str(e))
            elif msg_type == "pause_agent":
                if session_id != "unknown":
                    from agent.nodes import get_session_resume_event
                    get_session_resume_event(session_id).clear()
                    logger.info("agent_paused_requested", session_id=session_id)
            elif msg_type == "resume_agent":
                if session_id != "unknown":
                    from agent.nodes import get_session_resume_event
                    get_session_resume_event(session_id).set()
                    logger.info("agent_resumed_requested", session_id=session_id)
            elif msg_type == "cancel_agent":
                if graph_task and not graph_task.done():
                    graph_task.cancel()
                    logger.info("agent_cancel_requested", session_id=session_id)

    async def process_monitor_loop():
        from runtime import DockerRuntime
        while True:
            try:
                await asyncio.sleep(2)
                if session_id != "unknown":
                    rt = DockerRuntime.get(session_id)
                    processes = await rt.get_active_processes()
                    fg_proc = rt.get_foreground_process(processes)
                    try:
                        await ws.send_json({
                            "type": "process_list",
                            "processes": processes,
                            "foreground_process": fg_proc,
                            "session_id": session_id
                        })
                    except (RuntimeError, WebSocketDisconnect) as e:
                        logger.debug("process_monitor_send_failed", session_id=session_id, error=str(e))
                        break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("process_monitor_error", session_id=session_id, error=str(e))
                # Break the loop on WebSocket-related send errors
                if "websocket.send" in str(e) or "Cannot call" in str(e):
                    break

    async def ping_loop():
        while True:
            await asyncio.sleep(PING_INTERVAL)
            if time.time() - last_pong > PING_TIMEOUT:
                logger.info("ws_ping_timeout", session_id=session_id)
                try:
                    await ws.close(code=1001)
                except Exception:
                    pass
                break
            try:
                await ws.send_json({"type": "ping", "ts": time.time()})
            except Exception:
                break

    # Set default values in case connection fails early
    session_id = str(uuid.uuid4())
    obs_ws_callback = None
    try:
        data = await ws.receive_json()
        session_id = data.get("session_id") or str(uuid.uuid4())
        action = data.get("action", "start")
        message = data.get("message", "")
        profile_id = data.get("profile_id")
        last_seq = int(data.get("last_seq") or 0)
        chat_mode = data.get("chat_mode", "build")
        locked_files = data.get("locked_files", [])

        # Register observability WebSocket broadcaster
        from agent.observability import register_broadcaster
        async def obs_ws_callback(payload: dict):
            try:
                safe_payload = serialize_data(payload)
                seq = await EVENT_BUFFER.add(session_id, safe_payload)
                await ws.send_json({**safe_payload, "seq": seq})
            except Exception as e:
                logger.debug("obs_ws_broadcast_failed", error=str(e))
                
        register_broadcaster(session_id, obs_ws_callback)

        # Get LLM profile
        settings_service = SettingsService()
        profile = None
        if profile_id:
            profile = settings_service.get_profile(profile_id)
        if profile is None:
            profile = settings_service.get_default_profile()

        logger.info("ws_session_start", session_id=session_id, action=action, chat_mode=chat_mode, num_locked=len(locked_files))

        # Mark conversation as active
        conversation_service = ConversationService()
        try:
            conversation_service.mark_active(session_id)
        except Exception as exc:
            logger.warning("conversation_mark_active_failed", session_id=session_id, error=str(exc))

        # Lazy import to avoid circular deps — graph is built once per worker
        from agent.graph import get_graph
        graph = await get_graph()

        # Set recursion limit to 100 to allow building complete applications
        # Default is 25, but complex apps need more iterations
        config = {
            "configurable": {"thread_id": session_id},
            "recursion_limit": 100
        }

        replay_events = await EVENT_BUFFER.replay_after(session_id, last_seq)
        for event in replay_events:
            await ws.send_json({**event, "replay": True})

        # Fetch existing state values to check status
        current_state = await graph.aget_state(config)
        current_values = current_state.values if current_state else {}
        checkpoint_status = current_values.get("status")

        if action == "resume":
            state = {
                "session_id": session_id,
                "llm_profile": profile.model_dump() if profile else None,
                "chat_mode": chat_mode,
                "locked_files": locked_files,
            }
            # Append new message if provided on resume
            if message:
                existing_messages = list(current_values.get("messages") or [])
                existing_messages.append(HumanMessage(content=message))
                state["messages"] = existing_messages
                
            # If the session was in error, reset it to allow recovery
            if checkpoint_status == "error":
                state["status"] = "plan"
                state["node_exception"] = None
                state["plan_error"] = None
        else:
            state = {
                "session_id": session_id,
                "messages": [HumanMessage(content=message)] if message else [],
                "retries": 0,
                "files": {},
                "last_obs": None,
                "llm_profile": profile.model_dump() if profile else None,
                "chat_mode": chat_mode,
                "locked_files": locked_files,
                "status": "plan",
            }


        last_pong = time.time()
        receive_task = asyncio.create_task(receive_loop())
        ping_task = asyncio.create_task(ping_loop())
        monitor_task = asyncio.create_task(process_monitor_loop())

        async def run_graph():
            try:
                async for event in graph.astream_events(state, config, version="v2"):
                    if event["event"] in [
                        "on_chain_start",
                        "on_chain_end",
                        "on_chat_model_stream",
                        "on_tool_end",
                    ]:
                        chunk = ""
                        if event["event"] == "on_chat_model_stream":
                            chunk_obj = event.get("data", {}).get("chunk")
                            chunk = getattr(chunk_obj, "content", "") if chunk_obj else ""
                            if not chunk:
                                continue

                        serialized_data = serialize_data(event.get("data"))

                        payload = {
                            "type": event["event"],
                            "node": event.get("name"),
                            "data": serialized_data,
                            "chunk": chunk,
                        }
                        seq = await EVENT_BUFFER.add(session_id, payload)
                        
                        try:
                            await ws.send_json({**payload, "seq": seq})
                        except (RuntimeError, WebSocketDisconnect):
                            logger.info("ws_client_stopped_generation", session_id=session_id)
                            break
            except asyncio.CancelledError:
                logger.info("ws_generation_cancelled", session_id=session_id)
                # Send log message and cancelled event to frontend
                payload = {
                    "type": "agent_log",
                    "data": "\r\n\x1b[31m✗ Agent execution cancelled by user.\x1b[0m\r\n",
                }
                seq = await EVENT_BUFFER.add(session_id, payload)
                try:
                    await ws.send_json({**payload, "seq": seq})
                except Exception:
                    pass
                payload_cancelled = {
                    "type": "agent_cancelled",
                    "session_id": session_id
                }
                seq_c = await EVENT_BUFFER.add(session_id, payload_cancelled)
                try:
                    await ws.send_json({**payload_cancelled, "seq": seq_c})
                except Exception:
                    pass
                raise

        graph_task = asyncio.create_task(run_graph())
        
        done, pending = await asyncio.wait(
            [receive_task, graph_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        if graph_task in done:
            exc = graph_task.exception()
            if exc:
                raise exc
            # Graph finished normally, keep connection open until client disconnects
            await receive_task

    except WebSocketDisconnect:
        logger.info("ws_disconnected", session_id=session_id)
        try:
            ConversationService().pause_conversation(session_id)
        except Exception:
            pass
    except Exception as e:
        logger.error("ws_error", session_id=session_id, error=str(e), exc_info=True)
        try:
            await ws.send_json({
                "type": "error",
                "error": str(e),
                "message": f"Execution error: {str(e)}"
            })
        except Exception:
            pass
        try:
            await ws.close(code=1011)
        except Exception:
            pass
    finally:
        if obs_ws_callback:
            try:
                from agent.observability import unregister_broadcaster
                unregister_broadcaster(session_id, obs_ws_callback)
            except Exception:
                pass
        for task in (receive_task, ping_task, graph_task, monitor_task):
            if task:
                task.cancel()


# ── Sandbox Management Endpoints (OpenHands-style) ──────────────────────

@router.get("/sandboxes")
async def list_sandboxes():
    """Get all tracked sandboxes across the application."""
    try:
        service = SandboxService()
        sandboxes = await service.list_all()
        return {"sandboxes": [s.model_dump() for s in sandboxes]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sandbox/{session_id}/status")
async def sandbox_status(session_id: str):
    """Get the current status of a sandbox container."""
    try:
        service = SandboxService()
        info = await service.get_status(session_id)
        return info.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sandbox/{session_id}/health")
async def sandbox_health(session_id: str, port: int = 3000):
    """Health-check: is the app running inside the sandbox?"""
    try:
        service = SandboxService()
        result = await service.health(session_id, port=port)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sandbox/{session_id}/files")
async def sandbox_files(session_id: str):
    """List generated files in the sandbox workspace."""
    try:
        service = SandboxService()
        return {"files": await service.list_files(session_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sandbox/{session_id}/files/read")
async def sandbox_file_read(session_id: str, path: str = Query(...)):
    """Read one generated text file from the sandbox workspace."""
    try:
        service = SandboxService()
        return {"path": path, "content": await service.read_file(session_id, path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sandbox/{session_id}/files/write")
async def sandbox_file_write(session_id: str, request: WriteFileRequest):
    """Write one text file back to the sandbox workspace."""
    try:
        service = SandboxService()
        await service.write_file(session_id, request.path, request.content)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/sandbox/{session_id}/download")
async def sandbox_download(session_id: str):
    """Download the entire workspace as a ZIP file."""
    try:
        service = SandboxService()
        zip_bytes = await service.download_workspace(session_id)
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=workspace_{session_id[:8]}.zip"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sandbox/{session_id}/pause")
async def sandbox_pause(session_id: str):
    """Pause a running sandbox (frees CPU, preserves state)."""
    try:
        service = SandboxService()
        success = await service.pause(session_id)
        return {"paused": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sandbox/{session_id}/resume")
async def sandbox_resume(session_id: str):
    """Resume a paused sandbox."""
    try:
        service = SandboxService()
        success = await service.resume(session_id)
        return {"resumed": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sandbox/{session_id}/usage")
async def sandbox_usage(session_id: str):
    """Get sandbox container CPU and memory usage."""
    try:
        service = SandboxService()
        return await service.usage(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sandbox/{session_id}")
async def sandbox_delete(session_id: str):
    """Stop and remove a sandbox container."""
    try:
        service = SandboxService()
        await service.delete(session_id)
        return {"deleted": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Document Upload & RAG Endpoints ─────────────────────────────────────

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    enable_rag: bool = True,
):
    """
    Upload an SRS document (PDF, DOCX, MD, TXT) for processing.

    If RAG is enabled and dependencies are available, the document will be
    chunked, embedded, and indexed for semantic search during agent planning.
    """
    # Validate file type
    allowed_extensions = {".pdf", ".docx", ".doc", ".md", ".txt", ".markdown"}
    filename = file.filename or "upload.txt"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(allowed_extensions))}",
        )

    # Save to temp file
    tmp_path: str | None = None
    try:
        suffix = ext
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Process the document
        from agent.srs_loader import load_srs_with_rag

        result = load_srs_with_rag(tmp_path, enable_rag=enable_rag)

        logger.info(
            "document_uploaded",
            file_name=filename,
            text_length=len(result["text"]),
            chunks=result["chunks"],
            rag=result["rag_enabled"],
        )

        return {
            "filename": filename,
            "document_id": result["document_id"],
            "text_length": len(result["text"]),
            "text_preview": result["text"][:500],
            "full_text": result["text"],
            "chunks_indexed": result["chunks"],
            "rag_enabled": result["rag_enabled"],
        }

    except Exception as e:
        logger.error("document_upload_failed", file_name=filename, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temp file
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


@router.get("/rag/search")
async def rag_search(
    query: str = Query(..., description="Search query"),
    document_id: str = Query(None, description="Filter by document ID"),
    top_k: int = Query(5, ge=1, le=20, description="Number of results"),
):
    """Search indexed documents using semantic similarity."""
    try:
        from agent.embedding_engine import EmbeddingEngine

        engine = EmbeddingEngine()
        results = engine.search(query, top_k=top_k, document_id=document_id)
        return {"query": query, "results": results, "count": len(results)}
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="RAG dependencies not installed. Install: pip install sentence-transformers chromadb",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/sandbox/{session_id}/terminal")
async def sandbox_terminal(ws: WebSocket, session_id: str):
    """WebSocket endpoint for raw interactive shell access to the container."""
    await ws.accept()
    
    try:
        from services.sandbox_service import SandboxService
        service = SandboxService()
        runtime = await service.get_runtime(session_id)
        container_name = runtime.container_name
    except Exception as e:
        await ws.send_json({"type": "output", "data": f"\r\nError connecting to sandbox: {str(e)}\r\n"})
        await ws.close()
        return

    import pty
    import os
    import subprocess
    import fcntl
    import termios
    import struct

    # Open pseudo-terminal
    master_fd, slave_fd = pty.openpty()
    
    # Spawn docker exec inside the pty
    p = subprocess.Popen(
        ["docker", "exec", "-it", container_name, "/bin/bash"],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        preexec_fn=os.setsid,
    )
    os.close(slave_fd)

    output_queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def read_callback():
        try:
            data = os.read(master_fd, 4096)
            if not data:
                loop.call_soon_threadsafe(output_queue.put_nowait, None)
                return
            loop.call_soon_threadsafe(output_queue.put_nowait, data)
        except Exception:
            loop.call_soon_threadsafe(output_queue.put_nowait, None)

    loop.add_reader(master_fd, read_callback)

    async def write_loop():
        try:
            while True:
                msg = await ws.receive_json()
                msg_type = msg.get("type")
                if msg_type == "input":
                    data = msg.get("data", "")
                    if data:
                        os.write(master_fd, data.encode("utf-8"))
                elif msg_type == "resize":
                    cols = msg.get("cols", 80)
                    rows = msg.get("rows", 24)
                    try:
                        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
                    except Exception:
                        pass
        except Exception:
            pass
        finally:
            # Signal the read loop to stop by putting None
            await output_queue.put(None)

    write_task = asyncio.create_task(write_loop())

    try:
        while True:
            data = await output_queue.get()
            if data is None:
                break
            # Send raw terminal output back as JSON
            await ws.send_json({"type": "output", "data": data.decode("utf-8", errors="replace")})
    except Exception:
        pass
    finally:
        # Cleanup
        write_task.cancel()
        loop.remove_reader(master_fd)
        try:
            os.close(master_fd)
        except Exception:
            pass
        
        # Terminate subprocess
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=1)
            except subprocess.TimeoutExpired:
                p.kill()
        
        try:
            await ws.close()
        except Exception:
            pass


# ── AI Agent Observability Endpoints ────────────────────────────────────

@router.get("/session/{session_id}/architecture")
async def get_session_architecture(session_id: str):
    """Retrieve the generated architectural plan (Mermaid diagrams and ADRs) for a session."""
    from agent.graph import get_graph
    try:
        graph = await get_graph()
        config = {"configurable": {"thread_id": session_id}}
        state_snapshot = await graph.aget_state(config)
        
        if not state_snapshot or not state_snapshot.values:
            return {"status": "no_plan", "message": "No state found for this session."}
            
        arch_plan = state_snapshot.values.get("architectural_plan")
        if not arch_plan:
            return {"status": "no_plan", "message": "No architectural plan has been generated yet."}
            
        return serialize_data(arch_plan)
    except Exception as e:
        logger.error("get_session_architecture_failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to retrieve architecture: {str(e)}")


@router.get("/session/{session_id}/observability")
def get_observability_logs(
    session_id: str,
    agent_name: Optional[str] = None,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
):
    """Retrieve and filter observability logs for a session."""
    from agent.observability import ObservabilityManager
    manager = ObservabilityManager()
    return manager.get_logs(
        session_id=session_id,
        agent_name=agent_name,
        event_type=event_type,
        status=status,
        search=search,
    )


@router.get("/session/{session_id}/observability/summary")
def get_observability_summary(session_id: str):
    """Get aggregated session execution summary."""
    from agent.observability import ObservabilityManager
    manager = ObservabilityManager()
    return manager.get_session_summary(session_id)


@router.get("/session/{session_id}/observability/export/json")
def export_observability_json(session_id: str):
    """Export observability logs as raw JSON file."""
    from agent.observability import ObservabilityManager
    manager = ObservabilityManager()
    logs = manager.get_logs(session_id)
    content = json.dumps(logs, indent=2)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=agent_observability_{session_id}.json"},
    )


@router.get("/session/{session_id}/observability/export/csv")
def export_observability_csv(session_id: str):
    """Export observability logs as CSV file."""
    from agent.observability import ObservabilityManager
    manager = ObservabilityManager()
    content = manager.export_as_csv(session_id)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=agent_observability_{session_id}.csv"},
    )


@router.get("/session/{session_id}/observability/export/pdf")
def export_observability_pdf(session_id: str):
    """Export observability logs as PDF report."""
    from agent.observability import ObservabilityManager
    manager = ObservabilityManager()
    pdf_bytes = manager.export_as_pdf(session_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=agent_report_{session_id}.pdf"},
    )


# ── File History Endpoints ──────────────────────────────────────────────


class FileRestoreRequest(PydanticBaseModel):
    path: str
    timestamp: int


@router.get("/session/{session_id}/file-history/{path:path}")
async def get_file_history(session_id: str, path: str):
    """List all saved versions of a file for the UI diff viewer."""
    from runtime import DockerRuntime
    from agent.file_history import FileHistoryManager

    try:
        runtime = DockerRuntime.get(session_id)
        history = FileHistoryManager()
        versions = await history.get_versions(runtime, path)
        return {"path": path, "versions": versions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/file-version/{path:path}")
async def get_file_version(session_id: str, path: str, timestamp: int = Query(...)):
    """Get the content of a specific saved version of a file."""
    from runtime import DockerRuntime
    from agent.file_history import FileHistoryManager

    try:
        runtime = DockerRuntime.get(session_id)
        history = FileHistoryManager()
        content = await history.get_version_content(runtime, path, timestamp)
        if content is None:
            raise HTTPException(status_code=404, detail="Version not found")
        return {"path": path, "timestamp": timestamp, "content": content}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/{session_id}/file-restore")
async def restore_file_version(session_id: str, request: FileRestoreRequest):
    """Restore a specific version of a file (undo AI edit)."""
    from runtime import DockerRuntime
    from agent.file_history import FileHistoryManager

    try:
        runtime = DockerRuntime.get(session_id)
        history = FileHistoryManager()
        success = await history.restore_version(runtime, request.path, request.timestamp)
        if not success:
            raise HTTPException(status_code=404, detail="Version not found or restore failed")
        return {"status": "restored", "path": request.path, "timestamp": request.timestamp}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AnalyzeProjectRequest(PydanticBaseModel):
    workspace_path: str = "/workspace"


@router.post("/analyze")
async def analyze_project(request: AnalyzeProjectRequest):
    """
    Trigger an autonomous code improvement run on the specified workspace.

    Runs the scan -> build kg -> analyze -> prioritize -> plan -> generate fixes ->
    review -> apply -> learn loop.
    """
    session_id = str(uuid.uuid4())
    logger.info("api_analyze_project_triggered", session_id=session_id, path=request.workspace_path)

    try:
        from agent.analyze_graph import build_analyze_graph
        graph = build_analyze_graph()

        initial_state = {
            "session_id": session_id,
            "status": "scanning",
            "workspace_path": request.workspace_path,
            "workspace_index": None,
            "knowledge_graph": None,
            "issues": [],
            "plan": None,
            "changes": [],
            "applied_changes": [],
            "errors": [],
            "retries": 0,
            "memory": {},
        }

        # Run graph to completion
        final_state = await graph.ainvoke(initial_state)

        # Filter out heavy contents (like full file content) before returning to keep payload clean
        clean_changes = []
        for change in final_state.get("changes", []):
            clean_changes.append({
                "file": change["file"],
                "change_type": change["change_type"],
                "diff_summary": change["diff_summary"],
                "validation_passed": change.get("validation_passed", False),
                "reviewed_approved": change.get("reviewed_approved", False),
            })

        return {
            "session_id": session_id,
            "status": final_state.get("status"),
            "issues": final_state.get("issues", []),
            "plan": final_state.get("plan"),
            "changes": clean_changes,
            "applied_changes": [
                {
                    "file": c["file"],
                    "diff_summary": c["diff_summary"],
                }
                for c in final_state.get("applied_changes", [])
            ],
            "errors": final_state.get("errors", []),
        }
    except Exception as e:
        logger.error("api_analyze_project_failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")




