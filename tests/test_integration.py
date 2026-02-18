"""
Integration Tests — AI Legal Document Assistant
Tests API endpoints working together (auth → upload → query flow).

Requires the backend to be running: uvicorn backend.app:app --port 8000

Run: python -m pytest tests/test_integration.py -v
"""

import requests
import uuid
import pytest

BASE_URL = "http://127.0.0.1:8000"

# Minimal valid PDF for upload tests
MINIMAL_PDF = (
    b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
    b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n"
    b"0000000010 00000 n\n0000000060 00000 n\n0000000111 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
)


def unique_email():
    return f"test_{uuid.uuid4().hex[:8]}@integration.test"


def register_and_login():
    """Helper: create a fresh user and return their token."""
    email = unique_email()
    r = requests.post(f"{BASE_URL}/register", json={
        "email": email,
        "password": "testpass123",
        "display_name": "Test User",
        "security_question": "What is your pet's name?",
        "security_answer": "fluffy"
    })
    assert r.status_code == 200, f"Register failed: {r.text}"
    data = r.json()
    return data["token"], email


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ───────────────────────────────────────────────────────
# Auth Flow
# ───────────────────────────────────────────────────────
class TestAuthFlow:
    def test_register_returns_token(self):
        token, _ = register_and_login()
        assert token is not None
        assert len(token) > 20

    def test_login_with_registered_user(self):
        email = unique_email()
        requests.post(f"{BASE_URL}/register", json={
            "email": email,
            "password": "pass123456",
            "display_name": "Login Test",
            "security_question": "What is your city?",
            "security_answer": "london"
        })
        r = requests.post(f"{BASE_URL}/login", json={
            "email": email,
            "password": "pass123456"
        })
        assert r.status_code == 200
        assert "token" in r.json()

    def test_login_wrong_password(self):
        email = unique_email()
        requests.post(f"{BASE_URL}/register", json={
            "email": email,
            "password": "correctpass",
            "display_name": "Wrong PW",
            "security_question": "Favorite color?",
            "security_answer": "blue"
        })
        r = requests.post(f"{BASE_URL}/login", json={
            "email": email,
            "password": "wrongpass"
        })
        assert r.status_code == 401

    def test_duplicate_registration(self):
        email = unique_email()
        requests.post(f"{BASE_URL}/register", json={
            "email": email,
            "password": "pass123",
            "display_name": "Dup Test",
            "security_question": "Pet name?",
            "security_answer": "rex"
        })
        r = requests.post(f"{BASE_URL}/register", json={
            "email": email,
            "password": "pass456",
            "display_name": "Dup Test 2",
            "security_question": "Pet name?",
            "security_answer": "max"
        })
        assert r.status_code == 409

    def test_me_endpoint(self):
        token, email = register_and_login()
        r = requests.get(f"{BASE_URL}/me", headers=auth_header(token))
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == email


# ───────────────────────────────────────────────────────
# Document Upload & Retrieval Flow
# ───────────────────────────────────────────────────────
class TestDocumentFlow:
    def test_upload_pdf(self):
        token, _ = register_and_login()
        files = {"file": ("test.pdf", MINIMAL_PDF, "application/pdf")}
        r = requests.post(f"{BASE_URL}/upload", headers=auth_header(token), files=files)
        assert r.status_code == 200
        data = r.json()
        assert "doc_id" in data
        assert data["filename"] == "test.pdf"
        assert "structured" in data

    def test_list_documents_after_upload(self):
        token, _ = register_and_login()
        files = {"file": ("doc.pdf", MINIMAL_PDF, "application/pdf")}
        requests.post(f"{BASE_URL}/upload", headers=auth_header(token), files=files)
        r = requests.get(f"{BASE_URL}/documents", headers=auth_header(token))
        assert r.status_code == 200
        docs = r.json()
        assert len(docs) >= 1

    def test_get_single_document(self):
        token, _ = register_and_login()
        files = {"file": ("single.pdf", MINIMAL_PDF, "application/pdf")}
        upload = requests.post(f"{BASE_URL}/upload", headers=auth_header(token), files=files)
        doc_id = upload.json()["doc_id"]
        r = requests.get(f"{BASE_URL}/documents/{doc_id}", headers=auth_header(token))
        assert r.status_code == 200
        data = r.json()
        assert data["doc_id"] == doc_id

    def test_delete_document(self):
        token, _ = register_and_login()
        files = {"file": ("delete_me.pdf", MINIMAL_PDF, "application/pdf")}
        upload = requests.post(f"{BASE_URL}/upload", headers=auth_header(token), files=files)
        doc_id = upload.json()["doc_id"]
        r = requests.delete(f"{BASE_URL}/documents/{doc_id}", headers=auth_header(token))
        assert r.status_code == 200
        # Verify it's gone
        r2 = requests.get(f"{BASE_URL}/documents/{doc_id}", headers=auth_header(token))
        assert r2.status_code == 404

    def test_upload_non_pdf_rejected(self):
        token, _ = register_and_login()
        files = {"file": ("test.txt", b"not a pdf", "text/plain")}
        r = requests.post(f"{BASE_URL}/upload", headers=auth_header(token), files=files)
        assert r.status_code == 400


# ───────────────────────────────────────────────────────
# Password Reset Flow
# ───────────────────────────────────────────────────────
class TestPasswordResetFlow:
    def test_get_security_question(self):
        email = unique_email()
        requests.post(f"{BASE_URL}/register", json={
            "email": email,
            "password": "pass123",
            "display_name": "Reset Test",
            "security_question": "What city were you born in?",
            "security_answer": "paris"
        })
        r = requests.post(f"{BASE_URL}/auth/question", json={"email": email})
        assert r.status_code == 200
        assert "question" in r.json()

    def test_reset_password_wrong_answer(self):
        email = unique_email()
        requests.post(f"{BASE_URL}/register", json={
            "email": email,
            "password": "pass123",
            "display_name": "Reset Fail",
            "security_question": "What is your pet?",
            "security_answer": "cat"
        })
        r = requests.post(f"{BASE_URL}/auth/reset-password", json={
            "email": email,
            "security_answer": "dog",
            "new_password": "newpass123"
        })
        assert r.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
