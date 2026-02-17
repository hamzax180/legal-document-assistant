"""
Persistence layer for the AI Legal Document Assistant.
Supports SQLite (Local) and Postgres (Vercel).
"""

import sqlite3
import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

# Check if running on Vercel
IS_VERCEL = os.environ.get("VERCEL") == "1"

if IS_VERCEL:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    DB_URL = os.environ.get("POSTGRES_URL")
    if DB_URL:
        print(f"[INFO] DB_URL found. Starts with: {DB_URL[:15]}...", flush=True)
    else:
        print("[ERROR] DB_URL (POSTGRES_URL) is None or empty!", flush=True)

    DB_PATH = None
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "legal_docs.db")


def get_conn():
    if IS_VERCEL:
        try:
            conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
            return conn
        except Exception as e:
            print(f"[ERROR] Postgres connection failed: {e}")
            raise e
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def get_current_timestamp_query():
    return "CURRENT_TIMESTAMP" if IS_VERCEL else "datetime('now')"


def get_placeholder():
    return "%s" if IS_VERCEL else "?"


SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    security_question TEXT,
    security_answer_hash TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    filename TEXT NOT NULL,
    full_text TEXT NOT NULL,
    structured_json TEXT,
    page_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL,
    page_num INTEGER NOT NULL,
    content TEXT NOT NULL,
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL,
    role TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
);
"""

SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    security_question TEXT,
    security_answer_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    filename TEXT NOT NULL,
    full_text TEXT NOT NULL,
    structured_json TEXT,
    page_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pages (
    id SERIAL PRIMARY KEY,
    doc_id TEXT NOT NULL,
    page_num INTEGER NOT NULL,
    content TEXT NOT NULL,
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    doc_id TEXT NOT NULL,
    role TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
);
"""


def _migrate_add_user_id(conn):
    """Add user_id column to documents table if it doesn't exist (migration)."""
    p = get_placeholder()
    try:
        cursor = conn.cursor()
        if IS_VERCEL:
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'documents' AND column_name = 'user_id'
            """)
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE documents ADD COLUMN user_id TEXT")
                conn.commit()
                print("[INFO] Migration: Added user_id column to documents", flush=True)
        else:
            cursor.execute("PRAGMA table_info(documents)")
            columns = [row["name"] for row in cursor.fetchall()]
            if "user_id" not in columns:
                cursor.execute("ALTER TABLE documents ADD COLUMN user_id TEXT")
                conn.commit()
                print("[INFO] Migration: Added user_id column to documents", flush=True)
    except Exception as e:
        print(f"[WARN] Migration check for user_id: {e}", flush=True)


def _migrate_add_security_cols(conn):
    """Add security_question/answer columns to users table if not exist."""
    print("[INFO] Checking security columns migration...", flush=True)
    try:
        cursor = conn.cursor()
        if IS_VERCEL:
            # Check if columns exist
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'security_question'
            """)
            if not cursor.fetchone():
                print("[INFO] Adding security columns to Postgres...", flush=True)
                cursor.execute("ALTER TABLE users ADD COLUMN security_question TEXT")
                cursor.execute("ALTER TABLE users ADD COLUMN security_answer_hash TEXT")
                conn.commit()
        else:
            cursor.execute("PRAGMA table_info(users)")
            columns = [row["name"] for row in cursor.fetchall()]
            if "security_question" not in columns:
                print("[INFO] Adding security columns to SQLite...", flush=True)
                cursor.execute("ALTER TABLE users ADD COLUMN security_question TEXT")
                cursor.execute("ALTER TABLE users ADD COLUMN security_answer_hash TEXT")
                conn.commit()
    except Exception as e:
        print(f"[WARN] Migration check for security cols: {e}", flush=True)


def init_db():
    try:
        conn = get_conn()
        if IS_VERCEL:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_POSTGRES)
            conn.commit()
        else:
            conn.executescript(SCHEMA_SQLITE)
            conn.commit()
        
        # Run migrations
        _migrate_add_user_id(conn)
        _migrate_add_security_cols(conn)
        
        conn.close()
    except Exception as e:
        print(f"[ERROR] Database init failed: {e}")


# ======================== USER FUNCTIONS ========================

def create_user(email: str, password_hash: str, display_name: str = None, 
                security_question: str = None, security_answer_hash: str = None) -> dict:
    """Create a new user and return the user dict."""
    conn = get_conn()
    p = get_placeholder()
    user_id = str(uuid.uuid4())
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"INSERT INTO users (id, email, password_hash, display_name, security_question, security_answer_hash) "
            f"VALUES ({p}, {p}, {p}, {p}, {p}, {p})",
            (
                user_id, 
                email.lower().strip(), 
                password_hash, 
                display_name or email.split("@")[0],
                security_question,
                security_answer_hash
            )
        )
        conn.commit()
        return {
            "id": user_id, 
            "email": email.lower().strip(), 
            "display_name": display_name or email.split("@")[0]
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_user_by_email(email: str) -> Optional[dict]:
    """Get user by email address."""
    conn = get_conn()
    p = get_placeholder()
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM users WHERE email = {p}", (email.lower().strip(),))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def get_user_by_id(user_id: str) -> Optional[dict]:
    """Get user by ID."""
    conn = get_conn()
    p = get_placeholder()
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT id, email, display_name, created_at FROM users WHERE id = {p}", (user_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def get_user_security_question(email: str) -> Optional[str]:
    """Get the security question for a user by email."""
    user = get_user_by_email(email)
    if user:
        return user.get("security_question")
    return None


def update_password(email: str, new_password_hash: str) -> bool:
    """Update a user's password."""
    conn = get_conn()
    p = get_placeholder()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE users SET password_hash = {p} WHERE email = {p}",
            (new_password_hash, email.lower().strip())
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] update_password failed: {e}")
        return False
    finally:
        conn.close()


# ======================== DOCUMENT FUNCTIONS ========================

def save_document(doc_id: str, filename: str, pages: List[str],
                  structured: dict, user_id: str = None) -> None:
    conn = get_conn()
    full_text = "\n".join(pages)
    p = get_placeholder()
    
    try:
        cursor = conn.cursor()
        
        # Save document
        cursor.execute(
            f"INSERT INTO documents (id, user_id, filename, full_text, structured_json, page_count) "
            f"VALUES ({p}, {p}, {p}, {p}, {p}, {p})",
            (doc_id, user_id, filename, full_text, json.dumps(structured), len(pages))
        )
        
        # Save pages
        for i, page in enumerate(pages):
            cursor.execute(
                f"INSERT INTO pages (doc_id, page_num, content) VALUES ({p}, {p}, {p})",
                (doc_id, i, page)
            )
            
        conn.commit()
    except Exception as e:
        print(f"[ERROR] save_document failed: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()


def list_documents(user_id: str = None) -> List[dict]:
    conn = get_conn()
    p = get_placeholder()
    try:
        cursor = conn.cursor()
        if user_id:
            cursor.execute(
                f"SELECT id, filename, page_count, created_at FROM documents WHERE user_id = {p} ORDER BY created_at DESC",
                (user_id,)
            )
        else:
            cursor.execute(
                "SELECT id, filename, page_count, created_at FROM documents ORDER BY created_at DESC"
            )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_document(doc_id: str, user_id: str = None) -> Optional[dict]:
    conn = get_conn()
    p = get_placeholder()
    try:
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute(f"SELECT * FROM documents WHERE id = {p} AND user_id = {p}", (doc_id, user_id))
        else:
            cursor.execute(f"SELECT * FROM documents WHERE id = {p}", (doc_id,))
        doc = cursor.fetchone()
        
        if not doc:
            return None

        cursor.execute(
            f"SELECT content FROM pages WHERE doc_id = {p} ORDER BY page_num", (doc_id,)
        )
        pages_rows = cursor.fetchall()

        cursor.execute(
            f"SELECT role, message FROM chat_history WHERE doc_id = {p} ORDER BY created_at",
            (doc_id,)
        )
        chats_rows = cursor.fetchall()
        
        # Process chat history
        chat_pairs = []
        i = 0
        chat_list = [dict(c) for c in chats_rows]
        
        while i < len(chat_list):
            pair = {}
            if chat_list[i]["role"] == "user":
                pair["user"] = chat_list[i]["message"]
                if i + 1 < len(chat_list) and chat_list[i + 1]["role"] == "assistant":
                    pair["assistant"] = chat_list[i + 1]["message"]
                    i += 2
                else:
                    pair["assistant"] = ""
                    i += 1
                chat_pairs.append(pair)
            else:
                i += 1

        created_at = doc["created_at"]
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()

        return {
            "id": doc["id"],
            "filename": doc["filename"],
            "full_text": doc["full_text"],
            "structured": json.loads(doc["structured_json"]) if doc["structured_json"] else {},
            "pages": [r["content"] for r in pages_rows],
            "chat": chat_pairs,
            "page_count": doc["page_count"],
            "created_at": created_at,
        }
    finally:
        conn.close()


def save_chat_message(doc_id: str, role: str, message: str) -> None:
    conn = get_conn()
    p = get_placeholder()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"INSERT INTO chat_history (doc_id, role, message) VALUES ({p}, {p}, {p})",
            (doc_id, role, message)
        )
        conn.commit()
    except Exception as e:
        print(f"[ERROR] save_chat_message failed: {e}")
    finally:
        conn.close()


def delete_document(doc_id: str, user_id: str = None) -> bool:
    conn = get_conn()
    p = get_placeholder()
    try:
        cursor = conn.cursor()
        if user_id:
            cursor.execute(f"DELETE FROM documents WHERE id = {p} AND user_id = {p}", (doc_id, user_id))
        else:
            cursor.execute(f"DELETE FROM documents WHERE id = {p}", (doc_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
