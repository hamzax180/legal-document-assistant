import os
import json
import uuid
import time
import random
import traceback
from typing import Dict, Any, List, Optional

# import fitz  <-- Removed to save space
import numpy as np
# REMOVED: import faiss
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, APIRouter
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from google import genai
# REMOVED: from sentence_transformers import SentenceTransformer

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from database import init_db, save_document, get_document, list_documents, delete_document, save_chat_message
except ImportError:
    # Try fully qualified import if necessary (though sys.path fix should handle it)
    from backend.database import init_db, save_document, get_document, list_documents, delete_document, save_chat_message


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
    # In Vercel build phase, env vars might be missing depending on config, but runtime they should be there.
    # We'll allow it specifically for build if needed, but for now raise to fail fast.
    # Actually, let's print a warning instead of crashing immediately if it's imported during build?
    # But init is runtime.
    if os.environ.get("VERCEL"):
         print("[WARN] GEMINI_API_KEY not set yet")
    else:
         raise ValueError("GEMINI_API_KEY environment variable not set")
    client = None # Handle None later
else:
    client = genai.Client(api_key=GEMINI_API_KEY)

MODEL_ID = "gemini-2.5-flash"
EMBEDDING_MODEL_ID = "text-embedding-004"

# No local embedder: use API
# embedder = SentenceTransformer("all-MiniLM-L6-v2")


# ================= APP =================
app = FastAPI(title="AI Legal Document Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter()

# In-memory cache for embeddings + pages (rebuilt on demand from DB)
DOCS: Dict[str, Dict[str, Any]] = {}


@app.on_event("startup")
def startup():
    print(f"[INFO] VERCEL env var: {os.environ.get('VERCEL')}")
    from database import DB_PATH
    print(f"[INFO] DB_PATH: {DB_PATH}")
    try:
        init_db()
        print("[INFO] Database initialized successfully")
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")


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
    if not client:
        raise GeminiError("Gemini Client not initialized (Missing API Key)")
        
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
            
            # Fallback logic for 404/Not Found/Invalid Argument implies model issue
            if "not found" in err_str or "404" in err_str or "invalid argument" in err_str:
                print(f"[WARN] Model {MODEL_ID} failed ({e}), trying fallback to gemini-1.5-flash")
                try:
                    response = client.models.generate_content(
                        model="gemini-1.5-flash",
                        contents=prompt
                    )
                    return response.text.strip()
                except Exception as e2:
                    print(f"[ERROR] Fallback model also failed: {e2}")
                    # Raise original error to avoid confusion, or the new one?
                    # Let's raise the fallback error as it's the last attempt
                    raise GeminiError(f"AI model error (fallback failed): {str(e2)}")

            raise GeminiError(f"AI model error: {str(e)}")
    raise RateLimitError(f"Rate limit exceeded after 5 retries. Last error: {last_error}")


def get_embedding(text: str) -> List[float]:
    """Get embedding from Gemini API."""
    if not client:
        print("[ERROR] No Gemini Client")
        return [0.0] * 768

    try:
        # Truncate to avoid limit (input limit is usually large (~3k-10k tokens), but let's be safe with 9000 chars)
        safe_text = text[:9000]
        result = client.models.embed_content(
            model=EMBEDDING_MODEL_ID,
            contents=safe_text
        )
        # Handle new SDK response structure
        if hasattr(result, 'embeddings'):
             return result.embeddings[0].values
        return result.embedding
    except Exception as e:
        print(f"[ERROR] Embedding failed: {e}")
        # Try fallback model if potentially model related (though embedding-004 is standard)
        # We won't fallback embedding model for now as 004 is very standard.
        
        # Fallback: zero vector (not ideal but prevents crash)
        return [0.0] * 768


import io
import pypdf  # Lighter alternative to PyMuPDF

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> List[str]:
    stream = io.BytesIO(pdf_bytes)
    reader = pypdf.PdfReader(stream)
    return [page.extract_text() for page in reader.pages]


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


# ================= VECTOR SEARCH (NUMPY) =================
def build_index(pages: List[str]):
    """Build a simple numpy embedding index."""
    embeddings = []
    for page in pages:
        embeddings.append(get_embedding(page))
    return np.array(embeddings, dtype="float32")


def ensure_doc_in_cache(doc_id: str) -> dict:
    """Load a document into in-memory cache if not already present."""
    if doc_id in DOCS:
        return DOCS[doc_id]

    doc_data = get_document(doc_id)
    if not doc_data:
        return None

    pages = doc_data["pages"]
    index = build_index(pages)

    DOCS[doc_id] = {
        "pages": pages,
        "index": index,
        "chat": doc_data["chat"],
        "full_text": doc_data["full_text"],
    }
    return DOCS[doc_id]


# ================= RAG =================
def rag_qa(query: str, pages: List[str], index_embeddings, history: List[dict]):
    q_emb = np.array(get_embedding(query), dtype="float32")
    
    # Cosine similarity: (A . B) / (|A| * |B|)
    # Note: If embeddings are normalized, |A|=1, |B|=1, so just dot product.
    # But let's compute full cosine to be safe.
    
    norm_index = np.linalg.norm(index_embeddings, axis=1)
    norm_query = np.linalg.norm(q_emb)
    
    # Avoid division by zero
    if norm_query == 0:
        scores = np.zeros(len(pages))
    else:
        # Add epsilon to avoid div by zero in index
        norm_index[norm_index == 0] = 1e-10
        scores = np.dot(index_embeddings, q_emb) / (norm_index * norm_query)

    # Get top 3 indices
    top_k_indices = np.argsort(scores)[::-1][:3]

    context = "\n---\n".join(pages[i] for i in top_k_indices)
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
    doc_id: Optional[str] = None
    question: str
    evaluate: bool = True
    full_text: Optional[str] = None  # For stateless mode

class StatelessBody(BaseModel):
    doc_id: Optional[str] = None
    full_text: Optional[str] = None

# ================= ROUTES =================
@router.get("/")
def root():
    return {"message": "Backend running. Visit /docs"}


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files allowed")

    print(f"[INFO] Uploading file: {file.filename}")
    pdf_bytes = await file.read()
    print(f"[INFO] File read, size: {len(pdf_bytes)} bytes")
    
    try:
        pages = extract_text_from_pdf_bytes(pdf_bytes)
        print(f"[INFO] Text extracted, pages: {len(pages)}")
    except Exception as e:
        print(f"[ERROR] PDF extraction failed: {e}")
        raise HTTPException(500, f"PDF processing failed: {str(e)}")

    # In stateless mode for Vercel, we might skip indexing to save time/resources
    # But let's keep it if we can, or just rely on full_text return.
    
    structured = {}
    # Skip structured extraction for speed in stateless demo if needed, 
    # but let's try to keep it.
    try:
        structured = extract_structured_info("\n".join(pages))
        print(f"[INFO] Structured info extracted")
    except Exception as e:
        print(f"[ERROR] Structured info extraction failed: {e}")
        structured = {}

    doc_id = str(uuid.uuid4())
    full_text = "\n".join(pages)

    # Persist to SQLite (Best Effort)
    try:
        save_document(doc_id, file.filename, pages, structured)
        print(f"[INFO] Document saved to DB: {doc_id}")
    except Exception as e:
        print(f"[ERROR] Database save failed: {e}")
        pass

    # Cache in memory
    try:
        index = build_index(pages)
        DOCS[doc_id] = {
            "pages": pages,
            "index": index,
            "chat": [],
            "full_text": full_text
        }
    except Exception as e:
        print(f"[ERROR] Indexing failed: {e}")
        # Continue without index (will force stateless mode downstream)

    return {
        "doc_id": doc_id,
        "filename": file.filename,
        "structured": structured,
        "pages": len(pages),
        "full_text": full_text  # RETURN THIS for stateless client-side storage
    }


@router.get("/documents")
def get_all_documents():
    """List all uploaded documents."""
    try:
        return list_documents()
    except Exception as e:
        print(f"[ERROR] listing documents failed: {e}")
        return []


@router.get("/documents/{doc_id}")
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


@router.delete("/documents/{doc_id}")
def remove_document(doc_id: str):
    """Delete a document and all its data."""
    if doc_id in DOCS:
        del DOCS[doc_id]

    if not delete_document(doc_id):
        raise HTTPException(404, "Document not found")

    return {"message": "Document deleted"}


@router.post("/ask")
def ask_question(body: AskBody):
    # STATELESS HANDLING
    if body.full_text:
        # Context Stuffing (Best for Vercel/Stateless)
        # We skip RAG index lookup and just dump text into prompt.
        # Gemini Flash has 1M context, so this is fine for most docs.
        
        prompt = f"""
Use the provided document text to answer the question.

Document Text:
{body.full_text}

Question: {body.question}
"""
        answer = safe_generate(prompt)
        
        # We don't have persistent chat history in stateless mode unless client sends it.
        # For this demo, we just return the answer.
        
        evaluation = None
        if body.evaluate:
             try:
                 evaluation = evaluate_response(body.question, body.full_text, answer)
             except:
                 pass

        return {
            "answer": answer,
            "chat_history": [], # Stateless, we don't track history here
            "evaluation": evaluation
        }

    # STATEFUL HANDLING (Legacy/Local)
    doc = ensure_doc_in_cache(body.doc_id)
    if not doc:
        raise HTTPException(404, "Document not found. It may have been deleted. Please re-upload.")

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


@router.post("/summarize")
def summarize_document(body: StatelessBody):
    """Generate a comprehensive summary of the entire document."""
    
    text_to_summarize = None
    
    if body.full_text:
        text_to_summarize = body.full_text
    else:
        doc = ensure_doc_in_cache(body.doc_id)
        if doc:
            text_to_summarize = doc['full_text']
            
    if not text_to_summarize:
        raise HTTPException(404, "Document not found")

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
{text_to_summarize[:100000]} 
""" 
# Limit to 100k chars to be safe, though Flash handles more.

    result = safe_generate(prompt)
    return {"summary": result}


@router.post("/suggest")
def suggest_questions(body: StatelessBody):
    """Auto-generate relevant questions about the document."""
    
    text_for_context = None
    
    if body.full_text:
         text_for_context = body.full_text
    else:
        doc = ensure_doc_in_cache(body.doc_id)
        if doc:
            text_for_context = doc['full_text']
            
    if not text_for_context:
        raise HTTPException(404, "Document not found")

    prompt = f"""
You are a legal document assistant. Based on the document below, suggest exactly 5 important questions
a user would likely want to ask about this legal document.

Return ONLY a JSON array of strings, like:
["Question 1?", "Question 2?", "Question 3?", "Question 4?", "Question 5?"]

Document Text:
{text_for_context[:50000]}
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

# Mount Router with conditionally applied prefix
IS_VERCEL = os.environ.get("VERCEL") == "1"
PREFIX = "/api" if IS_VERCEL else ""
app.include_router(router, prefix=PREFIX)
print(f"[INFO] Router mounted with prefix: '{PREFIX}'")
