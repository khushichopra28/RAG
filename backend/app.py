"""FastAPI backend for the PDF RAG assistant.

Run with:  uvicorn app:app --reload --port 8000
"""
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import rag_pipeline
from config import settings

app = FastAPI(title="PDF RAG Assistant")

# Credentialed CORS requires CORS_ORIGINS in .env to list explicit origins, not "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(settings.data_dir) / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class QueryRequest(BaseModel):
    question: str
    k: int | None = None


@app.on_event("startup")
def on_startup():
    settings.validate_startup()


@app.get("/api/health")
def health():
    is_valid = bool(settings.groq_api_key and settings.groq_api_key.startswith("gsk_"))
    return {"status": "ok", "configured": is_valid, "model": settings.llm_model}


@app.get("/api/stats")
def stats():
    return rag_pipeline.get_stats()


@app.get("/api/documents")
def documents():
    return rag_pipeline.list_documents()


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")

    if not settings.groq_api_key or not settings.groq_api_key.startswith("gsk_"):
        raise HTTPException(
            500,
            "GROQ_API_KEY is not set or malformed on the server. Add a valid 'gsk_' key to backend/.env.",
        )

    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
    with temp_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    try:
        record = rag_pipeline.ingest_pdf(str(temp_path), file.filename)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Failed to process PDF: {exc}") from exc

    return record


@app.post("/api/query")
def query(payload: QueryRequest):
    if not payload.question.strip():
        raise HTTPException(400, "Question cannot be empty.")
    if not settings.groq_api_key or not settings.groq_api_key.startswith("gsk_"):
        raise HTTPException(
            500,
            "GROQ_API_KEY is not set or malformed on the server. Add a valid 'gsk_' key to backend/.env.",
        )
    try:
        return rag_pipeline.answer_question(payload.question, payload.k)
    except Exception as exc:
        import traceback

        traceback.print_exc()
        raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc



@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    ok = rag_pipeline.delete_document(doc_id)
    if not ok:
        raise HTTPException(404, "Document not found.")
    return {"deleted": doc_id}
