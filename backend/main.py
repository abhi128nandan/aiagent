"""
Application entry point.

This file is intentionally thin — it only wires up middleware, routers,
and lifecycle hooks.  All business logic lives in `routes/`, `agent/`,
and `core/`.
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.logger import get_logger
from routes.agent import router as agent_router
from routes.secrets import router as secrets_router
from routes.settings import router as settings_router
from routes.conversations import router as conversations_router

settings = get_settings()
settings.export_to_env()
logger = get_logger(__name__)


# ── Lifecycle ───────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    logger.info("app_starting", app=settings.APP_NAME, version=settings.APP_VERSION)
    
    # Start background tasks
    from services.sandbox_service import SandboxService
    cleanup_task = asyncio.create_task(
        SandboxService.start_cleanup_task(
            interval_seconds=settings.SANDBOX_CLEANUP_INTERVAL,
            max_age_seconds=86400  # 24 hours
        )
    )
    
    # --- Startup Check: Verify Templates Exist ---
    import os
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    templates_dir = os.path.join(backend_dir, "templates")
    
    # We parse agent.prompts to extract the EXACT enum of templates we told the LLM to use
    from agent.prompts import BOOTSTRAP_PLAN_SCHEMA_INSTRUCTIONS
    from agent.nodes import DYNAMIC_SCAFFOLD_TEMPLATES
    import re
    # Look for the line: - "template_selected" MUST be exactly one of: ...
    match = re.search(r'"template_selected" MUST be exactly one of:\s*(.*?)\.', BOOTSTRAP_PLAN_SCHEMA_INSTRUCTIONS)
    if match:
        enum_str = match.group(1)
        # Extract quoted strings
        expected_templates = [t.strip('"\'') for t in re.findall(r'["\']([^"\']+)["\']', enum_str)]
        static_templates = [t for t in expected_templates if t.lower() != "none" and t not in DYNAMIC_SCAFFOLD_TEMPLATES]
        
        for template in static_templates:
            template_path = os.path.join(templates_dir, template)
            if not os.path.isdir(template_path):
                raise RuntimeError(f"Startup check failed: Template directory '{template}' enumerated in prompt does not exist at {template_path}")
        logger.info("startup_check_passed", static_templates_verified=static_templates, dynamic_templates=list(DYNAMIC_SCAFFOLD_TEMPLATES.keys()))
    else:
        logger.warning("startup_check_warning", msg="Could not parse template enum from BOOTSTRAP_PLAN_SCHEMA_INSTRUCTIONS")
    # ---------------------------------------------
    
    yield
    
    # Cleanup
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    
    from agent.graph import close_checkpointer
    await close_checkpointer()
    logger.info("app_shutting_down")


# ── App Factory ─────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(agent_router)
app.include_router(secrets_router)
app.include_router(settings_router)
app.include_router(conversations_router)


@app.get("/")
def read_root():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
