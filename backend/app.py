import os
import sys

print("[INFO] Loading backend/app.py...", flush=True)  # Debug print

import json
import uuid
import time
import random
import traceback
from typing import Dict, Any, List, Optional

import numpy as np
import bcrypt
import jwt
from datetime import datetime, timedelta
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, APIRouter, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from database import (
        init_db, save_document, get_document, list_documents,
        delete_document, save_chat_message,
        create_user, get_user_by_email, get_user_by_id
    )
except ImportError:
    from backend.database import (
        init_db, save_document, get_document, list_documents,
        delete_document, save_chat_message,
        create_user, get_user_by_email, get_user_by_id
    )


# ================= CUSTOM EXCEPTIONS =================
class RateLimitError(Exception):
    """Raised when Gemini API rate limit is exhausted after retries."""
    pass


class GeminiError(Exception):
    """Raised when the Gemini API returns a non-rate-limit error."""
    pass


# ================= CONFIG =================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
JWT_SECRET = os.getenv("JWT_SECRET", "legalai-secret-change-in-production-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 72

# Lazy init client
client = None

def get_gemini_client():
    global client
    if client:
        return client
        
    if not GEMINI_API_KEY:
        if os.environ.get("VERCEL"):
             print("[WARN] GEMINI_API_KEY not set yet", flush=True)
             return None
        else:
             raise ValueError("GEMINI_API_KEY environment variable not set")
    
    try:
        print("[INFO] Initializing Gemini Client...", flush=True)
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        return client
    except Exception as e:
        print(f"[ERROR] Failed to init Gemini Client: {e}", flush=True)
        return None

MODEL_ID = "gemini-2.5-flash"
EMBEDDING_MODEL_ID = "text-embedding-004"


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
    print(f"[INFO] VERCEL env var: {os.environ.get('VERCEL')}", flush=True)
    from database import DB_PATH
    if DB_PATH:
        print(f"[INFO] DB_PATH: {DB_PATH}", flush=True)
    else:
        print("[INFO] Running on Vercel (Postgres)", flush=True)
    try:
        init_db()
        print("[INFO] Database initialized successfully", flush=True)
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}", flush=True)


# ================= AUTH HELPERS =================
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(request: Request) -> dict:
    """Extract and validate JWT from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    
    token = auth[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = get_user_by_id(payload["sub"])
        if not user:
            raise HTTPException(401, "User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


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
    client = get_gemini_client()
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
                    raise GeminiError(f"AI model error (fallback failed): {str(e2)}")

            raise GeminiError(f"AI model error: {str(e)}")
    raise RateLimitError(f"Rate limit exceeded after 5 retries. Last error: {last_error}")


def get_embedding(text: str) -> List[float]:
    """Get embedding from Gemini API."""
    client = get_gemini_client()
    if not client:
        print("[ERROR] No Gemini Client", flush=True)
        return [0.0] * 768

    try:
        safe_text = text[:9000]
        result = client.models.embed_content(
            model=EMBEDDING_MODEL_ID,
            contents=safe_text
        )
        if hasattr(result, 'embeddings'):
             return result.embeddings[0].values
        return result.embedding
    except Exception as e:
        print(f"[ERROR] Embedding failed: {e}")
        return [0.0] * 768


import io
import pypdf

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> List[str]:
    stream = io.BytesIO(pdf_bytes)
    reader = pypdf.PdfReader(stream)
    return [page.extract_text() for page in reader.pages]


# ================= STRUCTURED JSON =================
STRUCT_PROMPT = """
You are a legal document analyst. Extract structured information from the following document text.

Return ONLY valid JSON with this exact schema:
{
  "document_type": "The type of document (e.g. Contract, NDA, CV/Resume, Court Order, Agreement, Letter, Report, etc.)",
  "title": "The title or subject of the document",
  "dates": ["List of important dates found in the document"],
  "parties": ["List of people, companies, or organizations mentioned"],
  "key_terms": ["List of important terms, concepts, or section headings"],
  "summary": "A brief 2-3 sentence summary of the document's purpose and content",
  "extracted_text_preview": "The first 500 characters of the document text as-is"
}

If a field cannot be determined, use an empty string or empty array. Do NOT omit any field.
Return ONLY the JSON object, no markdown, no explanation.

Document text:
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


def ensure_doc_in_cache(doc_id: str, user_id: str = None) -> dict:
    """Load a document into in-memory cache if not already present."""
    if doc_id in DOCS:
        return DOCS[doc_id]

    doc_data = get_document(doc_id, user_id=user_id)
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
    
    norm_index = np.linalg.norm(index_embeddings, axis=1)
    norm_query = np.linalg.norm(q_emb)
    
    if norm_query == 0:
        scores = np.zeros(len(pages))
    else:
        norm_index[norm_index == 0] = 1e-10
        scores = np.dot(index_embeddings, q_emb) / (norm_index * norm_query)

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
class RegisterBody(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = None
    security_question: str
    security_answer: str

class LoginBody(BaseModel):
    email: str
    password: str

class GetQuestionBody(BaseModel):
    email: str

class ResetPasswordBody(BaseModel):
    email: str
    security_answer: str
    new_password: str

class AskBody(BaseModel):
    doc_id: Optional[str] = None
    question: str
    evaluate: bool = True
    full_text: Optional[str] = None

class StatelessBody(BaseModel):
    doc_id: Optional[str] = None
    full_text: Optional[str] = None


# ================= AUTH ROUTES =================
@router.post("/register")
def register(body: RegisterBody):
    if not body.email or not body.password:
        raise HTTPException(400, "Email and password are required")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if not body.security_question or not body.security_answer:
        raise HTTPException(400, "Security question and answer are required")
    
    existing = get_user_by_email(body.email)
    if existing:
        raise HTTPException(409, "An account with this email already exists")
    
    hashed_pw = hash_password(body.password)
    hashed_ans = hash_password(body.security_answer.lower().strip())

    try:
        user = create_user(
            email=body.email, 
            password_hash=hashed_pw, 
            display_name=body.display_name,
            security_question=body.security_question,
            security_answer_hash=hashed_ans
        )
    except Exception as e:
        print(f"[ERROR] Registration failed: {e}")
        raise HTTPException(500, "Registration failed")
    
    token = create_token(user["id"], user["email"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"]
        }
    }


@router.post("/auth/question")
def get_security_question(body: GetQuestionBody):
    from database import get_user_security_question
    question = get_user_security_question(body.email)
    if not question:
        # Return 404 so UI knows email is invalid
        raise HTTPException(404, "Email not found")
    return {"question": question}


@router.post("/auth/reset-password")
def reset_password(body: ResetPasswordBody):
    user = get_user_by_email(body.email)
    if not user:
        raise HTTPException(404, "User not found")
    
    # Verify security answer
    if not verify_password(body.security_answer.lower().strip(), user["security_answer_hash"]):
        raise HTTPException(401, "Incorrect security answer")
    
    # Update password
    new_hash = hash_password(body.new_password)
    from database import update_password
    if update_password(body.email, new_hash):
        return {"message": "Password updated successfully"}
    else:
        raise HTTPException(500, "Failed to update password")


@router.post("/login")
def login(body: LoginBody):
    if not body.email or not body.password:
        raise HTTPException(400, "Email and password are required")
    
    user = get_user_by_email(body.email)
    if not user:
        raise HTTPException(401, "Invalid email or password")
    
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    
    token = create_token(user["id"], user["email"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"]
        }
    }


@router.get("/me")
def get_me(request: Request):
    user = get_current_user(request)
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"]
    }


# ================= ROUTES =================
@router.get("/")
def root():
    return {"message": "Backend running. Visit /docs"}


@router.post("/upload")
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    user = get_current_user(request)
    
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files allowed")

    print(f"[INFO] Uploading file: {file.filename} (user: {user['email']})")
    pdf_bytes = await file.read()
    print(f"[INFO] File read, size: {len(pdf_bytes)} bytes")
    
    try:
        pages = extract_text_from_pdf_bytes(pdf_bytes)
        print(f"[INFO] Text extracted, pages: {len(pages)}")
    except Exception as e:
        print(f"[ERROR] PDF extraction failed: {e}")
        raise HTTPException(500, f"PDF processing failed: {str(e)}")

    structured = {}
    try:
        structured = extract_structured_info("\n".join(pages))
        print(f"[INFO] Structured info extracted")
    except Exception as e:
        print(f"[ERROR] Structured info extraction failed: {e}")
        structured = {}

    doc_id = str(uuid.uuid4())
    full_text = "\n".join(pages)

    # Persist to DB
    try:
        save_document(doc_id, file.filename, pages, structured, user_id=user["id"])
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

    return {
        "doc_id": doc_id,
        "filename": file.filename,
        "structured": structured,
        "pages": len(pages),
        "full_text": full_text
    }


@router.get("/documents")
def get_all_documents(request: Request):
    """List all uploaded documents for the current user."""
    user = get_current_user(request)
    try:
        return list_documents(user_id=user["id"])
    except Exception as e:
        print(f"[ERROR] listing documents failed: {e}")
        return []


@router.get("/documents/{doc_id}")
def get_single_document(doc_id: str, request: Request):
    """Load a document by ID (must belong to current user)."""
    user = get_current_user(request)
    doc_data = get_document(doc_id, user_id=user["id"])
    if not doc_data:
        raise HTTPException(404, "Document not found")

    ensure_doc_in_cache(doc_id, user_id=user["id"])

    return {
        "doc_id": doc_data["id"],
        "filename": doc_data["filename"],
        "structured": doc_data["structured"],
        "pages": doc_data["page_count"],
        "chat_history": doc_data["chat"],
        "created_at": doc_data["created_at"],
    }


@router.delete("/documents/{doc_id}")
def remove_document(doc_id: str, request: Request):
    """Delete a document (must belong to current user)."""
    user = get_current_user(request)
    
    if doc_id in DOCS:
        del DOCS[doc_id]

    if not delete_document(doc_id, user_id=user["id"]):
        raise HTTPException(404, "Document not found")

    return {"message": "Document deleted"}


@router.post("/ask")
def ask_question(body: AskBody, request: Request):
    user = get_current_user(request)
    
    # STATEFUL HANDLING (Prioritized if doc_id is present)
    if body.doc_id:
        doc = ensure_doc_in_cache(body.doc_id, user_id=user["id"])
        if not doc:
            raise HTTPException(404, "Document not found. It may have been deleted. Please re-upload.")

        answer, _context = rag_qa(
            body.question,
            doc["pages"],
            doc["index"],
            doc["chat"]
        )

        doc["chat"].append({"user": body.question, "assistant": answer})

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
            "evaluation": evaluation,
            "context": _context
        }

    # STATELESS HANDLING (Fallback if no doc_id)
    if body.full_text:
        prompt = f"""
Use the provided document text to answer the question.

Document Text:
{body.full_text}

Question: {body.question}
"""
        answer = safe_generate(prompt)
        
        evaluation = None
        if body.evaluate:
             try:
                 evaluation = evaluate_response(body.question, body.full_text, answer)
             except:
                 pass

        return {
            "answer": answer,
            "chat_history": [],
            "evaluation": evaluation
        }


@router.post("/summarize")
def summarize_document(body: StatelessBody, request: Request):
    """Generate a comprehensive summary of the entire document."""
    user = get_current_user(request)
    
    text_to_summarize = None
    
    if body.full_text:
        text_to_summarize = body.full_text
    else:
        doc = ensure_doc_in_cache(body.doc_id, user_id=user["id"])
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

    result = safe_generate(prompt)
    return {"summary": result}


@router.post("/suggest")
def suggest_questions(body: StatelessBody, request: Request):
    """Auto-generate relevant questions about the document."""
    user = get_current_user(request)
    
    text_for_context = None
    
    if body.full_text:
         text_for_context = body.full_text
    else:
        doc = ensure_doc_in_cache(body.doc_id, user_id=user["id"])
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
