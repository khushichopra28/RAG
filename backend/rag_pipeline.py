"""
Core RAG pipeline built with LangChain:

  PDF -> PyPDFLoader -> RecursiveCharacterTextSplitter -> local HF embeddings
      -> Chroma (persisted) -> retriever -> ChatGroq -> answer + sources

Groq only serves chat/completions (no embeddings endpoint), so embeddings
run locally and for free via sentence-transformers; only the generation
step calls out to Groq.

A small JSON file (documents.json) tracks which PDFs have been ingested,
so the frontend can list documents and show live stats without needing
a separate database.
"""
import json
import os
import time
import uuid
from pathlib import Path
from typing import TypedDict

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate

from config import settings

DATA_DIR = Path(settings.data_dir)
CHROMA_DIR = Path(settings.chroma_dir)
REGISTRY_PATH = DATA_DIR / "documents.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)


class DocumentRecord(TypedDict):
    id: str
    filename: str
    chunks: int
    pages: int
    uploaded_at: float


# ---------------------------------------------------------------------------
# Registry (list of ingested documents) — plain JSON, no DB needed for a demo
# ---------------------------------------------------------------------------
def _load_registry() -> list[DocumentRecord]:
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text())
    return []


def _save_registry(records: list[DocumentRecord]) -> None:
    REGISTRY_PATH.write_text(json.dumps(records, indent=2))


def list_documents() -> list[DocumentRecord]:
    return _load_registry()


# ---------------------------------------------------------------------------
# Embeddings + vector store (singletons)
# ---------------------------------------------------------------------------
_embeddings = None
_vectorstore = None


def get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model)
    return _embeddings


def get_vectorstore() -> Chroma:
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = Chroma(
            collection_name="pdf_documents",
            embedding_function=get_embeddings(),
            persist_directory=str(CHROMA_DIR),
        )
    return _vectorstore


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------
def ingest_pdf(file_path: str, original_filename: str) -> DocumentRecord:
    """Load a PDF, split it into chunks, embed and store them."""
    loader = PyPDFLoader(file_path)
    pages = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    chunks = splitter.split_documents(pages)

    doc_id = str(uuid.uuid4())
    for chunk in chunks:
        chunk.metadata["doc_id"] = doc_id
        chunk.metadata["source"] = original_filename

    vectorstore = get_vectorstore()
    vectorstore.add_documents(chunks)

    record: DocumentRecord = {
        "id": doc_id,
        "filename": original_filename,
        "chunks": len(chunks),
        "pages": len(pages),
        "uploaded_at": time.time(),
    }
    records = _load_registry()
    records.append(record)
    _save_registry(records)
    return record


def delete_document(doc_id: str) -> bool:
    records = _load_registry()
    match = next((r for r in records if r["id"] == doc_id), None)
    if not match:
        return False

    vectorstore = get_vectorstore()
    vectorstore._collection.delete(where={"doc_id": doc_id})  # noqa: SLF001

    records = [r for r in records if r["id"] != doc_id]
    _save_registry(records)
    return True


# ---------------------------------------------------------------------------
# Retrieval + generation
# ---------------------------------------------------------------------------
ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant that answers questions using only the "
            "provided context from the user's uploaded PDFs. If the answer is "
            "not contained in the context, say so plainly instead of guessing. "
            "Keep answers concise and cite the source filename when relevant.",
        ),
        (
            "human",
            "Context:\n{context}\n\nQuestion: {question}",
        ),
    ]
)


def answer_question(question: str, k: int | None = None) -> dict:
    vectorstore = get_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": k or settings.retriever_k})

    docs = retriever.invoke(question)
    if not docs:
        return {
            "answer": "I don't have any documents to search yet — upload a PDF first.",
            "sources": [],
        }

    context = "\n\n---\n\n".join(
        f"[{d.metadata.get('source', 'unknown')}, page {d.metadata.get('page', '?')}]\n{d.page_content}"
        for d in docs
    )

    llm = ChatGroq(model=settings.llm_model, api_key=settings.groq_api_key, temperature=0.2)
    chain = ANSWER_PROMPT | llm
    response = chain.invoke({"context": context, "question": question})

    sources = sorted(
        {(d.metadata.get("source", "unknown"), d.metadata.get("page", 0)) for d in docs}
    )
    return {
        "answer": response.content,
        "sources": [{"filename": s[0], "page": s[1]} for s in sources],
    }


def get_stats() -> dict:
    records = _load_registry()
    total_chunks = sum(r["chunks"] for r in records)
    total_pages = sum(r["pages"] for r in records)
    return {
        "documents": len(records),
        "chunks": total_chunks,
        "pages": total_pages,
    }
