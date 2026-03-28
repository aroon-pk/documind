import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db.chroma import ChromaVectorStore
from app.embedding import EmbeddingService
from app.rag import RAGService
from app.routes.ask import router as ask_router
from app.routes.upload import router as upload_router
from app.services.document_service import DocumentService
from app.services.llm_service import LLMService


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("documind.main")

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
CHROMA_DIR = Path(os.getenv("CHROMA_PERSIST_DIR", str(BASE_DIR / "chroma_data")))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared services once when the app starts."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    embedding_service = EmbeddingService()
    vector_store = ChromaVectorStore(persist_directory=CHROMA_DIR)
    llm_service = LLMService()
    rag_service = RAGService(
        embedding_service=embedding_service,
        vector_store=vector_store,
        llm_service=llm_service,
    )
    document_service = DocumentService(upload_dir=UPLOAD_DIR, rag_service=rag_service)

    app.state.document_service = document_service
    app.state.rag_service = rag_service

    logger.info("DocuMind Lite started")
    yield
    logger.info("DocuMind Lite stopped")


app = FastAPI(
    title="DocuMind Lite",
    description="Upload PDFs and ask questions using a lightweight RAG pipeline.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)
app.include_router(ask_router)

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the single-page frontend."""
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health", tags=["system"])
async def health_check():
    return {"status": "ok"}
