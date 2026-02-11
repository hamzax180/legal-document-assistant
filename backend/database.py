"""
Persistence layer for the AI Legal Document Assistant.
Supports SQLite (Local) and Postgres (Vercel).
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

# Check if running on Vercel
IS_VERCEL = os.environ.get("VERCEL") == "1"

if IS_VERCEL:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    DB_URL = os.environ.get("POSTGRES_URL")
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
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    full_text TEXT NOT NULL,
    structured_json TEXT,
    page_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
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
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    full_text TEXT NOT NULL,
    structured_json TEXT,
    page_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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


def init_db():
    try:
        conn = get_conn()
        if IS_VERCEL:
            with conn.cursor() as cur:
                # Split schema execution for Postgres
                # executing simpler statements is safer
                cur.execute(SCHEMA_POSTGRES)
            conn.commit()
        else:
            conn.executescript(SCHEMA_SQLITE)
            conn.commit()
        conn.close()
    except Exception as e:
        print(f"[ERROR] Database init failed: {e}")


def save_document(doc_id: str, filename: str, pages: List[str],
                  structured: dict) -> None:
    conn = get_conn()
    full_text = "\n".join(pages)
    p = get_placeholder()
    
    try:
        cursor = conn.cursor()
        
        # Save document
        cursor.execute(
            f"INSERT INTO documents (id, filename, full_text, structured_json, page_count) "
            f"VALUES ({p}, {p}, {p}, {p}, {p})",
            (doc_id, filename, full_text, json.dumps(structured), len(pages))
        )
        
        # Save pages
        # For bulk insert, execute_batch or executemany is better, but loop is fine for small docs
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


def list_documents() -> List[dict]:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, filename, page_count, created_at FROM documents ORDER BY created_at DESC"
        )
        rows = cursor.fetchall()
        # Convert rows (which might be RealDictCursor or sqlite3.Row) to dicts
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_document(doc_id: str) -> Optional[dict]:
    conn = get_conn()
    p = get_placeholder()
    try:
        cursor = conn.cursor()
        
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
        # normalize to list of dicts first
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

        # Handle created_at formatting differences if needed
        # Postgres returns datetime object, SQLite returns string
        created_at = doc["created_at"]
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()

        return {
            "id": doc["id"],
            "filename": doc["filename"],
            "full_text": doc["full_text"],
            "structured": json.loads(doc["structured_json"]) if doc["structured_json"] else {},
            "pages": [r["content"] for r in pages_rows], # Access by key for both row types
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


def delete_document(doc_id: str) -> bool:
    conn = get_conn()
    p = get_placeholder()
    try:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM documents WHERE id = {p}", (doc_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
