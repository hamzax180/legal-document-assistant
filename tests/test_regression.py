"""
Regression Tests — AI Legal Document Assistant
Tests for previously discovered bugs to prevent them from reappearing.

Requires the backend to be running: uvicorn backend.app:app --port 8000

Run: python -m pytest tests/test_regression.py -v
"""

import requests
import uuid
import json
import pytest

BASE_URL = "http://127.0.0.1:8000"

MINIMAL_PDF = (
    b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
    b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n"
    b"0000000010 00000 n\n0000000060 00000 n\n0000000111 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
)


def fresh_user():
    email = f"reg_{uuid.uuid4().hex[:8]}@test.com"
    r = requests.post(f"{BASE_URL}/register", json={
        "email": email,
        "password": "regtest123",
        "display_name": "Regression Tester",
        "security_question": "Favorite food?",
        "security_answer": "pizza"
    })
    assert r.status_code == 200
    return r.json()["token"], email


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ───────────────────────────────────────────────────────
# BUG FIX: Cross-user document access (IDOR)
# Previously, any authenticated user could access any document by ID.
# ───────────────────────────────────────────────────────
class TestCrossUserDocumentAccess:
    def test_user_cannot_read_other_users_document(self):
        token_a, _ = fresh_user()
        token_b, _ = fresh_user()

        # User A uploads
        files = {"file": ("private.pdf", MINIMAL_PDF, "application/pdf")}
        r = requests.post(f"{BASE_URL}/upload", headers=auth(token_a), files=files)
        doc_id = r.json()["doc_id"]

        # User B tries to access
        r = requests.get(f"{BASE_URL}/documents/{doc_id}", headers=auth(token_b))
        assert r.status_code == 404, "User B should NOT see User A's document"

    def test_user_cannot_delete_other_users_document(self):
        token_a, _ = fresh_user()
        token_b, _ = fresh_user()

        files = {"file": ("private.pdf", MINIMAL_PDF, "application/pdf")}
        r = requests.post(f"{BASE_URL}/upload", headers=auth(token_a), files=files)
        doc_id = r.json()["doc_id"]

        r = requests.delete(f"{BASE_URL}/documents/{doc_id}", headers=auth(token_b))
        assert r.status_code == 404, "User B should NOT be able to delete User A's document"

        # Verify it still exists for User A
        r = requests.get(f"{BASE_URL}/documents/{doc_id}", headers=auth(token_a))
        assert r.status_code == 200

    def test_user_cannot_ask_on_other_users_document(self):
        token_a, _ = fresh_user()
        token_b, _ = fresh_user()

        files = {"file": ("private.pdf", MINIMAL_PDF, "application/pdf")}
        r = requests.post(f"{BASE_URL}/upload", headers=auth(token_a), files=files)
        doc_id = r.json()["doc_id"]

        r = requests.post(f"{BASE_URL}/ask", headers={
            **auth(token_b), "Content-Type": "application/json"
        }, json={
            "doc_id": doc_id,
            "question": "What is this?",
            "evaluate": False
        })
        assert r.status_code == 404, "User B should NOT query User A's document"


# ───────────────────────────────────────────────────────
# BUG FIX: Unauthenticated access
# Previously, some endpoints didn't check authentication.
# ───────────────────────────────────────────────────────
class TestUnauthenticatedAccess:
    def test_documents_requires_auth(self):
        r = requests.get(f"{BASE_URL}/documents")
        assert r.status_code == 401

    def test_upload_requires_auth(self):
        files = {"file": ("test.pdf", MINIMAL_PDF, "application/pdf")}
        r = requests.post(f"{BASE_URL}/upload", files=files)
        assert r.status_code == 401

    def test_me_requires_auth(self):
        r = requests.get(f"{BASE_URL}/me")
        assert r.status_code == 401

    def test_ask_requires_auth(self):
        r = requests.post(f"{BASE_URL}/ask", json={
            "question": "test",
            "doc_id": "fake-id"
        }, headers={"Content-Type": "application/json"})
        assert r.status_code == 401

    def test_invalid_token_rejected(self):
        r = requests.get(f"{BASE_URL}/documents", headers={
            "Authorization": "Bearer invalid.fake.token"
        })
        assert r.status_code == 401

    def test_expired_token_format_rejected(self):
        r = requests.get(f"{BASE_URL}/me", headers={
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiZXhwIjoxfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        })
        assert r.status_code == 401


# ───────────────────────────────────────────────────────
# BUG FIX: Empty structured JSON response
# Previously, the STRUCT_PROMPT was too vague and returned {}.
# ───────────────────────────────────────────────────────
class TestStructuredJsonNotEmpty:
    def test_structured_data_has_expected_keys(self):
        token, _ = fresh_user()
        files = {"file": ("structure.pdf", MINIMAL_PDF, "application/pdf")}
        r = requests.post(f"{BASE_URL}/upload", headers=auth(token), files=files)
        assert r.status_code == 200
        structured = r.json().get("structured", {})
        # Should not be empty anymore
        assert len(structured) > 0, "Structured data should not be empty"
        # If it extracted successfully, it should have document_type
        if "error" not in structured:
            assert "document_type" in structured


# ───────────────────────────────────────────────────────
# BUG FIX: Context returned in /ask response
# Previously, context was not returned, so users couldn't see source text.
# ───────────────────────────────────────────────────────
class TestContextInAskResponse:
    def test_ask_returns_context_field(self):
        token, _ = fresh_user()
        files = {"file": ("ctx_test.pdf", MINIMAL_PDF, "application/pdf")}
        r = requests.post(f"{BASE_URL}/upload", headers=auth(token), files=files)
        doc_id = r.json()["doc_id"]

        r = requests.post(f"{BASE_URL}/ask", headers={
            **auth(token), "Content-Type": "application/json"
        }, json={
            "doc_id": doc_id,
            "question": "What is this?",
            "evaluate": False
        })
        assert r.status_code == 200
        data = r.json()
        assert "context" in data, "Response should include 'context' field with source text"


# ───────────────────────────────────────────────────────
# BUG FIX: Non-PDF file upload
# Ensure non-PDF files are always rejected.
# ───────────────────────────────────────────────────────
class TestFileTypeValidation:
    def test_txt_rejected(self):
        token, _ = fresh_user()
        files = {"file": ("test.txt", b"hello world", "text/plain")}
        r = requests.post(f"{BASE_URL}/upload", headers=auth(token), files=files)
        assert r.status_code == 400

    def test_exe_rejected(self):
        token, _ = fresh_user()
        files = {"file": ("malware.exe", b"\x00\x01\x02", "application/octet-stream")}
        r = requests.post(f"{BASE_URL}/upload", headers=auth(token), files=files)
        assert r.status_code == 400

    def test_html_rejected(self):
        token, _ = fresh_user()
        files = {"file": ("page.html", b"<html></html>", "text/html")}
        r = requests.post(f"{BASE_URL}/upload", headers=auth(token), files=files)
        assert r.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
