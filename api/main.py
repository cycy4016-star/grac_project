from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.middleware import register_middleware
from api.routes import router
from config.settings import settings
from utils.logger import get_logger, patch_base_agent

patch_base_agent()
logger = get_logger("api")

app = FastAPI(
    title="GRaC API",
    description="Governance, Risk & Compliance Agent — AI-powered compliance assistant",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Mount UI static files and routes
from ui.routes import mount_static, router as ui_router
mount_static(app)
app.include_router(ui_router)

# Admin and system routes
from api.admin_routes import router as admin_router
from api.system_routes import router as system_router
app.include_router(admin_router)
app.include_router(system_router)


@app.on_event("startup")
async def startup():
    logger.info(
        f"GRaC API starting — sector={settings.ACTIVE_SECTOR} "
        f"host={settings.API_HOST}:{settings.API_PORT}"
    )
    # Pre-load embedding model (extracts ONNX runtime on first call)
    try:
        import threading
        def _warm_embeddings():
            from tools.embedding_tools import _detect_embedding_provider, load_embedding_model
            from config.settings import settings
            provider, model_name, _ = _detect_embedding_provider()
            if provider == "local":
                logger.info("Pre-loading ONNX embedding model...")
                model = load_embedding_model(model_name)
                model.encode(["warmup"], show_progress_bar=False)
                logger.info("ONNX embedding model ready")
        t = threading.Thread(target=_warm_embeddings, daemon=True)
        t.start()
    except Exception as e:
        logger.warning(f"Embedding warmup skipped: {e}")


@app.on_event("shutdown")
async def shutdown():
    logger.info("GRaC API shutting down")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error": {
                "message": "Internal server error",
            },
        },
    )


register_middleware(app)
app.include_router(router)
