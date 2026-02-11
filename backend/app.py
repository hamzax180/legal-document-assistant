import os
import json
import uuid
import time
import random
import traceback
from typing import Dict, Any, List

import fitz
import numpy as np
import faiss
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from google import genai
from sentence_transformers import SentenceTransformer

from database import init_db, save_document, get_document, list_documents, delete_document, save_chat_message


# ================= CUSTOM EXCEPTIONS =================
class RateLimitError(Exception):
    """Raised when Gemini API rate limit is exhausted after retries."""
    pass


class GeminiError(Exception):
    """Raised when the Gemini API returns a non-rate-limit error."""
    pass


# ================= CONFIG =================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set")

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_ID = "gemini-2.5-flash"
embedder = SentenceTransformer("all-MiniLM-L6-v2")


# ================= APP =================
app = FastAPI(title="AI Legal Document Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cache for FAISS indexes + pages (rebuilt on demand from DB)
DOCS: Dict[str, Dict[str, Any]] = {}


@app.on_event("startup")
def startup():
    init_db()


# ================= EXCEPTION HANDLERS =================
@app.exception_handler(RateLimitError)
async def rate_limit_handler(request: Request, exc: RateLimitError):
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit",
            "detail": "The AI service is currently overloaded. Please wait a moment and try again.",
            "retry_after": 10
        }
    )


@app.exception_handler(GeminiError)
async def gemini_error_handler(request: Request, exc: GeminiError):
    return JSONResponse(
        status_code=503,
        content={
            "error": "ai_service_unavailable",
            "detail": "The AI service encountered an error. Please try again shortly.",
            "message": str(exc)
        }
    )


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    print(f"[ERROR] Unhandled exception: {traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "detail": "An unexpected server error occurred. Please try again."
        }
    )


# ================= HELPERS =================
def safe_generate(prompt: str) -> str:
    last_error = None
    for attempt in range(5):
        try:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "resourceexhausted" in err_str or "rate limit" in err_str or "quota" in err_str:
                last_error = e
                wait_time = (2 ** attempt) + random.random()
                print(f"[WARN] Rate limited (attempt {attempt + 1}/5), retrying in {wait_time:.1f}s...")
                time.sleep(wait_time)
                continue
            raise GeminiError(f"AI model error: {str(e)}")
    raise RateLimitError(f"Rate limit exceeded after 5 retries. Last error: {last_error}")


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> List[str]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return [page.get_text() for page in doc]


# ================= STRUCTURED JSON =================
STRUCT_PROMPT = """
Return ONLY valid JSON.

Extract structured information from the text:
"""


def extract_structured_info(text: str):
    raw = safe_generate(STRUCT_PROMPT + text)
    try:
        return json.loads(raw)
    except:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(raw[start:end + 1])
            except:
                pass
    return {"error": "Invalid JSON from model", "raw_output": raw[:800]}


# ================= FAISS =================
def build_faiss_index(pages: List[str]):
    emb = embedder.encode(pages).astype("float32")
    index = faiss.IndexFlatL2(emb.shape[1])
    index.add(emb)
    return index


def ensure_doc_in_cache(doc_id: str) -> dict:
    """Load a document into in-memory cache if not already present."""
    if doc_id in DOCS:
        return DOCS[doc_id]

    doc_data = get_document(doc_id)
    if not doc_data:
        return None

    pages = doc_data["pages"]
    index = build_faiss_index(pages)

    DOCS[doc_id] = {
        "pages": pages,
        "index": index,
        "chat": doc_data["chat"],
        "full_text": doc_data["full_text"],
    }
    return DOCS[doc_id]


# ================= RAG =================
def rag_qa(query: str, pages: List[str], index, history: List[dict]):
    q_emb = embedder.encode([query]).astype("float32")
    _, I = index.search(q_emb, k=3)

    context = "\n---\n".join(pages[i] for i in I[0])
    history_text = "\n".join(
        f"User: {m['user']}\nAssistant: {m['assistant']}"
        for m in history
    )

    prompt = f"""
Use document context and chat history to answer clearly.

History:
{history_text}

Context:
{context}

Question: {query}
"""

    answer = safe_generate(prompt)
    return answer, context


# ================= EVALUATION =================
def evaluate_response(query: str, context: str, answer: str):
    prompt = f"""
Return ONLY valid JSON.

Keys:
- helpfulness (1-5)
- completeness (1-5)
- relevance (1-5)
- reasoning

Query: {query}
Context: {context[:1200]}
Answer: {answer}
"""

    raw = safe_generate(prompt)
    try:
        return json.loads(raw)
    except:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(raw[start:end + 1])
            except:
                pass

    return {
        "helpfulness": None,
        "completeness": None,
        "relevance": None,
        "reasoning": "Evaluation returned invalid JSON",
        "raw_output": raw[:600]
    }


# ================= MODELS =================
class AskBody(BaseModel):
    doc_id: str
    question: str
    evaluate: bool = True


class DocIdBody(BaseModel):
    doc_id: str


# ================= ROUTES =================
@app.get("/")
def root():
    return {"message": "Backend running. Visit /docs"}


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files allowed")

    pdf_bytes = await file.read()
    pages = extract_text_from_pdf_bytes(pdf_bytes)
    index = build_faiss_index(pages)
    structured = extract_structured_info("\n".join(pages))

    doc_id = str(uuid.uuid4())

    # Persist to SQLite
    save_document(doc_id, file.filename, pages, structured)

    # Cache in memory
    DOCS[doc_id] = {
        "pages": pages,
        "index": index,
        "chat": [],
        "full_text": "\n".join(pages)
    }

    return {
        "doc_id": doc_id,
        "filename": file.filename,
        "structured": structured,
        "pages": len(pages)
    }


@app.get("/documents")
def get_all_documents():
    """List all uploaded documents."""
    return list_documents()


@app.get("/documents/{doc_id}")
def get_single_document(doc_id: str):
    """Load a document by ID, including structured data and chat history."""
    doc_data = get_document(doc_id)
    if not doc_data:
        raise HTTPException(404, "Document not found")

    # Ensure it's in cache for future Q&A
    ensure_doc_in_cache(doc_id)

    return {
        "doc_id": doc_data["id"],
        "filename": doc_data["filename"],
        "structured": doc_data["structured"],
        "pages": doc_data["page_count"],
        "chat_history": doc_data["chat"],
        "created_at": doc_data["created_at"],
    }


@app.delete("/documents/{doc_id}")
def remove_document(doc_id: str):
    """Delete a document and all its data."""
    if doc_id in DOCS:
        del DOCS[doc_id]

    if not delete_document(doc_id):
        raise HTTPException(404, "Document not found")

    return {"message": "Document deleted"}


@app.post("/ask")
def ask_question(body: AskBody):
    doc = ensure_doc_in_cache(body.doc_id)
    if not doc:
        raise HTTPException(404, "Invalid doc_id")

    answer, _context = rag_qa(
        body.question,
        doc["pages"],
        doc["index"],
        doc["chat"]
    )

    doc["chat"].append({"user": body.question, "assistant": answer})

    # Persist chat to SQLite
    save_chat_message(body.doc_id, "user", body.question)
    save_chat_message(body.doc_id, "assistant", answer)

    evaluation = None
    if body.evaluate:
        try:
            evaluation = evaluate_response(body.question, doc["full_text"], answer)
        except Exception as e:
            evaluation = {
                "helpfulness": None,
                "completeness": None,
                "relevance": None,
                "reasoning": f"Evaluation failed: {str(e)}"
            }

    return {
        "answer": answer,
        "chat_history": doc["chat"],
        "evaluation": evaluation
    }


@app.post("/summarize")
def summarize_document(body: DocIdBody):
    """Generate a comprehensive summary of the entire document."""
    doc = ensure_doc_in_cache(body.doc_id)
    if not doc:
        raise HTTPException(404, "Invalid doc_id")

    prompt = f"""
You are a legal document analyst. Provide a clear, well-structured summary of the following legal document.

Format your response as:
## Brief Summary
A 2-3 sentence overview of what this document is about.

## Key Points
- Bullet points of the most important provisions, terms, or findings.

## Section-by-Section Breakdown
Summarize each major section of the document.

---
Document Text:
{doc['full_text'][:12000]}
"""

    result = safe_generate(prompt)
    return {"summary": result}


@app.post("/suggest")
def suggest_questions(body: DocIdBody):
    """Auto-generate relevant questions about the document."""
    doc = ensure_doc_in_cache(body.doc_id)
    if not doc:
        raise HTTPException(404, "Invalid doc_id")

    prompt = f"""
You are a legal document assistant. Based on the document below, suggest exactly 5 important questions
a user would likely want to ask about this legal document.

Return ONLY a JSON array of strings, like:
["Question 1?", "Question 2?", "Question 3?", "Question 4?", "Question 5?"]

Document Text:
{doc['full_text'][:8000]}
"""

    raw = safe_generate(prompt)
    try:
        questions = json.loads(raw)
        if isinstance(questions, list):
            return {"questions": questions[:5]}
    except:
        start, end = raw.find("["), raw.rfind("]")
        if start != -1 and end != -1:
            try:
                questions = json.loads(raw[start:end + 1])
                return {"questions": questions[:5]}
            except:
                pass

    return {"questions": [
        "What are the key terms of this document?",
        "Who are the parties involved?",
        "What are the important deadlines?",
        "Are there any risk clauses?",
        "What are the main obligations?"
    ]}
