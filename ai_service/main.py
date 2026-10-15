import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load env variables before other imports
load_dotenv()

from chat.router import router as chat_router
from llm.router import router as llm_router
from document_processing.router import router as doc_router
from rag.router import router as rag_router
from workflow.router import router as workflow_router
from evaluation.router import router as evaluation_router
from communication.router import router as communication_router

from fastapi import Response
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
# Allow the Node.js backend and Vite dev server to communicate with this service.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Node.js backend
        "http://localhost:5173",   # Vite dev server
        "http://localhost:4173",   # Vite preview
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register instrumentation middleware
app.add_middleware(ObservabilityMiddleware)

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
    return {"status": "healthy"}

@app.get("/metrics", tags=["Observability"])
async def metrics():
    """Exposes Prometheus metrics for scraping."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import uvicorn
    logging.info("Starting AI Service…")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
