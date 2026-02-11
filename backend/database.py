"""
SQLite persistence layer for the AI Legal Document Assistant.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

# Check if running on Vercel (or similar serverless env)
IS_VERCEL = os.environ.get("VERCEL") == "1"

if IS_VERCEL:
    # Use in-memory DB for maximum stability on Vercel
    # We rely on client-side full_text (stateless mode) for persistence
    # but keep this for temporary duration of lambda life.
    DB_PATH = ":memory:"
else:
    # Use local storage
    DB_PATH = os.path.join(os.path.dirname(__file__), "legal_docs.db")

# Global connection for in-memory DB on Vercel to persist across function calls
_global_mem_conn = None

SCHEMA_SQL = """
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

def get_conn():
    global _global_mem_conn
    
    if IS_VERCEL:
        if _global_mem_conn is None:
            _global_mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            _global_mem_conn.row_factory = sqlite3.Row
            _global_mem_conn.execute("PRAGMA foreign_keys = ON")
            _global_mem_conn.executescript(SCHEMA_SQL)
            _global_mem_conn.commit()
        return _global_mem_conn

    # Local file-based DB
    should_init = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    
    if should_init:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        
    return conn


def init_db():
    # Explicit initialization wrapper if needed, 
    # but get_conn now handles it automatically.
    conn = get_conn()
    if not IS_VERCEL:
        conn.close()


def save_document(doc_id: str, filename: str, pages: List[str],
                  structured: dict) -> None:
    conn = get_conn()
    full_text = "\n".join(pages)
    conn.execute(
        "INSERT INTO documents (id, filename, full_text, structured_json, page_count) "
        "VALUES (?, ?, ?, ?, ?)",
        (doc_id, filename, full_text, json.dumps(structured), len(pages))
    )
    for i, page in enumerate(pages):
        conn.execute(
            "INSERT INTO pages (doc_id, page_num, content) VALUES (?, ?, ?)",
            (doc_id, i, page)
        )
    conn.commit()
    conn.close()


def list_documents() -> List[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, filename, page_count, created_at FROM documents ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_document(doc_id: str) -> Optional[dict]:
    conn = get_conn()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not doc:
        conn.close()
        return None

    pages = conn.execute(
        "SELECT content FROM pages WHERE doc_id = ? ORDER BY page_num", (doc_id,)
    ).fetchall()

    chats = conn.execute(
        "SELECT role, message FROM chat_history WHERE doc_id = ? ORDER BY created_at",
        (doc_id,)
    ).fetchall()

    conn.close()

    # Pair up chat messages into user/assistant pairs
    chat_pairs = []
    i = 0
    chat_list = [dict(c) for c in chats]
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

    return {
        "id": doc["id"],
        "filename": doc["filename"],
        "full_text": doc["full_text"],
        "structured": json.loads(doc["structured_json"]) if doc["structured_json"] else {},
        "pages": [p["content"] for p in pages],
        "chat": chat_pairs,
        "page_count": doc["page_count"],
        "created_at": doc["created_at"],
    }


def save_chat_message(doc_id: str, role: str, message: str) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO chat_history (doc_id, role, message) VALUES (?, ?, ?)",
        (doc_id, role, message)
    )
    conn.commit()
    conn.close()


def delete_document(doc_id: str) -> bool:
    conn = get_conn()
    cursor = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0
