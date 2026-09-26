# PDF RAG Assistant

Upload PDFs, then ask questions about them. Answers are generated only from
the retrieved chunks of your own documents (retrieval-augmented generation).

- **Backend:** Python, FastAPI, LangChain, Chroma (vector store), local
  sentence-transformers embeddings, Groq (chat generation)
- **Frontend:** static HTML/CSS/JS, built on the same design system as the
  landing page spec you provided (same fonts, colors, layout, animations),
  repurposed for uploading PDFs and chatting with them instead of a marketing page.

```
rag-pdf-app/
├── backend/
│   ├── app.py            FastAPI routes (upload / query / documents / stats)
│   ├── rag_pipeline.py    LangChain ingestion + retrieval/generation logic
│   ├── config.py          Settings loaded from .env
│   ├── requirements.txt
│   ├── .env.example       Copy to .env and fill in your key
│   ├── data/              Uploaded PDFs + a small documents.json registry
│   └── chroma_db/         Persisted vector store (created on first run)
└── frontend/
    ├── index.html
    ├── styles.css
    ├── main.js
    └── assets/logo.svg
```

## 1. Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# then edit .env and paste your GROQ_API_KEY (free at console.groq.com)

uvicorn app:app --reload --port 8000
```

The API is now at `http://localhost:8000` (interactive docs at `/docs`).

## 2. Frontend setup

No build step — just open `frontend/index.html` in a browser, or serve it:

```bash
cd frontend
python -m http.server 5500
# then visit http://localhost:5500
```

`main.js` points at `http://localhost:8000` by default — change the
`API_BASE` constant at the top of that file if your backend runs elsewhere
(e.g. once you deploy it).

## What you'll need to supply / decide

1. **A Groq API key** — required, in `backend/.env`. Get a free one at
   [console.groq.com](https://console.groq.com). This is the only external
   dependency: Groq handles chat generation, and embeddings run locally for
   free via `sentence-transformers` (Groq doesn't have an embeddings
   endpoint, so this is the standard pairing).
   - First run will download the embedding model (~90 MB) from Hugging Face,
     so you need internet access once even though no key is required for it.
   - Groq model names change over time — `llama-3.3-70b-versatile` is set
     as the default; check
     [console.groq.com/docs/models](https://console.groq.com/docs/models)
     for the current list and swap `LLM_MODEL` in `.env` if needed.
2. **The real logo** — `frontend/assets/logo.svg` is a placeholder; drop in
   your actual mark at the same path (or update the `<img>` src in `index.html`).
3. **"Geist Pixel Circle" font file** — the source spec referenced a local
   `fonts/GeistPixel-Circle.woff2` file, which wasn't provided, so it's left
   out. The primary display font (`BubbledotICG-FinePos`, loaded from the
   same OnlineWebFonts CDN link in the original spec) still works fine on
   its own; add the local `@font-face` back in `styles.css` if you have the
   file.
4. **One structural change from the original spec:** the original landing
   page has `overflow: hidden` on the whole page (a single, non-scrolling
   viewport). Since this app needs an upload area and a chat panel below the
   hero, only the hero itself (`.hero-viewport`) is locked to one screen —
   the page scrolls normally past it to reach the upload/chat section.
5. **CORS / deployment** — `CORS_ORIGINS` in `.env` defaults to `*` for local
   dev. Lock it down to your real frontend origin before deploying anywhere
   public, and consider adding auth in front of `/api/upload` so random
   visitors can't fill up your vector store.

## How the RAG pipeline works (`rag_pipeline.py`)

1. `PyPDFLoader` loads the PDF page by page.
2. `RecursiveCharacterTextSplitter` splits pages into ~1000-character chunks
   (150-char overlap), tagging each chunk with its source filename, page
   number, and a document ID.
3. `HuggingFaceEmbeddings` (running locally, `all-MiniLM-L6-v2`) embeds each
   chunk; `Chroma` stores the vectors persistently in `backend/chroma_db/`.
4. On a question, the retriever does a similarity search for the top-k
   chunks, which get stuffed into a prompt along with the question and sent
   to `ChatGroq`. The response, plus the source filenames/pages, are
   returned to the frontend.

A lightweight `documents.json` file tracks what's been uploaded so the
frontend can list documents and show live counts — swap it for a real
database if you need multi-user support.
