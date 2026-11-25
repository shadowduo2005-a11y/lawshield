import os
import logging
import secrets

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Disable remote telemetry to prevent network timeouts/retries on dead endpoints
os.environ["GUARDRAILS_DISABLE_TELEMETRY"] = "true"
os.environ["DO_NOT_TRACK"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"

# Load env variables before other imports
load_dotenv()

from chat.router import router as chat_router
from llm.router import router as llm_router
from document_processing.router import router as doc_router
from rag.router import router as rag_router
from workflow.router import router as workflow_router
from evaluation.router import router as evaluation_router
from communication.router import router as communication_router

from config.settings import settings
from llm.providers.factory import resolve_llm_provider_name
from masking.ner import get_analyzer
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from observability import initialize_observability, ObservabilityMiddleware

# Initialize tracing, structured logging, and metrics
initialize_observability()

app = FastAPI(
    title="LawShield AI Service",
    description="Multi-agent legal AI with RAG, masking, and citation verification.",
    version="1.0.0",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Browser access is limited to explicitly configured origins. Server-to-server
# requests from the Node backend do not require CORS permission.
allowed_origins = [
    origin.strip().rstrip("/")
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register instrumentation middleware
app.add_middleware(ObservabilityMiddleware)


@app.middleware("http")
async def verify_service_token(request: Request, call_next):
    """Optionally protect all non-operational endpoints from public use."""
    public_paths = {"/health", "/ready", "/metrics", "/docs", "/openapi.json", "/redoc"}
    expected = settings.AI_SERVICE_TOKEN
    if expected and request.url.path not in public_paths:
        supplied = request.headers.get("X-Service-Token", "")
        if not secrets.compare_digest(supplied, expected):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or missing service token."},
            )
    return await call_next(request)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(chat_router)
app.include_router(llm_router)
app.include_router(doc_router)
app.include_router(rag_router)
app.include_router(workflow_router)
app.include_router(evaluation_router)
app.include_router(communication_router)

# ── Health & Metrics ──────────────────────────────────────────────────────────
@app.get("/health", tags=["Ops"])
async def health_check():
    return {"status": "healthy", "service": "lawshield-ai"}


@app.get("/ready", tags=["Ops"])
async def readiness_check():
    """Verify local chat prerequisites without making a paid LLM request."""
    checks = {}
    try:
        if settings.ENVIRONMENT.lower() == "production":
            if not settings.AI_SERVICE_TOKEN:
                raise RuntimeError("AI_SERVICE_TOKEN is required in production")
            if len(settings.AI_SERVICE_TOKEN) < 32:
                raise RuntimeError("AI_SERVICE_TOKEN must contain at least 32 characters")
        checks["llm_provider"] = resolve_llm_provider_name()
        get_analyzer()
        checks["pii_analyzer"] = "ready"
    except Exception as exc:
        logging.exception("AI service readiness check failed")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "error": str(exc), "checks": checks},
        )
    return {"status": "ready", "checks": checks}

@app.get("/metrics", tags=["Observability"])
async def metrics():
    """Exposes Prometheus metrics for scraping."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import uvicorn
    logging.info("Starting AI Service…")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.ENVIRONMENT.lower() == "development",
    )
