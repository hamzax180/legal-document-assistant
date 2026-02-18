"""
System / Functional Tests — AI Legal Document Assistant
Tests complete end-to-end user workflows as a real user would experience them.

Requires the backend to be running: uvicorn backend.app:app --port 8000

Run: python -m pytest tests/test_system.py -v
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
    email = f"sys_{uuid.uuid4().hex[:8]}@test.com"
    r = requests.post(f"{BASE_URL}/register", json={
        "email": email,
        "password": "systemtest123",
        "display_name": "System Tester",
        "security_question": "Favorite color?",
        "security_answer": "green"
    })
    assert r.status_code == 200
    return r.json()["token"], email


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ───────────────────────────────────────────────────────
# E2E: Full User Journey
# ───────────────────────────────────────────────────────
class TestFullUserJourney:
    """Simulates a complete user workflow: register → upload → analyze → ask → summarize → delete → logout."""

    def test_complete_workflow(self):
        # Step 1: Register
        token, email = fresh_user()
        assert token

        # Step 2: Verify identity
        r = requests.get(f"{BASE_URL}/me", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["email"] == email

        # Step 3: Upload a document
        files = {"file": ("workflow_test.pdf", MINIMAL_PDF, "application/pdf")}
        r = requests.post(f"{BASE_URL}/upload", headers=auth(token), files=files)
        assert r.status_code == 200
        data = r.json()
        doc_id = data["doc_id"]
        assert data["filename"] == "workflow_test.pdf"
        assert isinstance(data["structured"], dict)

        # Step 4: List documents (should have 1)
        r = requests.get(f"{BASE_URL}/documents", headers=auth(token))
        docs = r.json()
        assert any(d["id"] == doc_id for d in docs)

        # Step 5: Load the document
        r = requests.get(f"{BASE_URL}/documents/{doc_id}", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["doc_id"] == doc_id

        # Step 6: Ask a question
        r = requests.post(f"{BASE_URL}/ask", headers={
            **auth(token), "Content-Type": "application/json"
        }, json={
            "doc_id": doc_id,
            "question": "What is this document about?",
            "evaluate": False
        })
        assert r.status_code == 200
        assert "answer" in r.json()

        # Step 7: Get suggestions
        r = requests.post(f"{BASE_URL}/suggest", headers={
            **auth(token), "Content-Type": "application/json"
        }, json={"doc_id": doc_id})
        assert r.status_code == 200
        assert "questions" in r.json()

        # Step 8: Generate summary
        r = requests.post(f"{BASE_URL}/summarize", headers={
            **auth(token), "Content-Type": "application/json"
        }, json={"doc_id": doc_id})
        assert r.status_code == 200
        assert "summary" in r.json()

        # Step 9: Delete document
        r = requests.delete(f"{BASE_URL}/documents/{doc_id}", headers=auth(token))
        assert r.status_code == 200

        # Step 10: Verify document is gone
        r = requests.get(f"{BASE_URL}/documents/{doc_id}", headers=auth(token))
        assert r.status_code == 404


# ───────────────────────────────────────────────────────
# E2E: Multi-Document Management
# ───────────────────────────────────────────────────────
class TestMultiDocumentWorkflow:
    def test_upload_multiple_then_list(self):
        token, _ = fresh_user()

        doc_ids = []
        for i in range(3):
            files = {"file": (f"doc_{i}.pdf", MINIMAL_PDF, "application/pdf")}
            r = requests.post(f"{BASE_URL}/upload", headers=auth(token), files=files)
            assert r.status_code == 200
            doc_ids.append(r.json()["doc_id"])

        r = requests.get(f"{BASE_URL}/documents", headers=auth(token))
        docs = r.json()
        assert len(docs) >= 3

        # Clean up
        for doc_id in doc_ids:
            requests.delete(f"{BASE_URL}/documents/{doc_id}", headers=auth(token))


# ───────────────────────────────────────────────────────
# E2E: Password Reset Journey
# ───────────────────────────────────────────────────────
class TestPasswordResetJourney:
    def test_full_reset_flow(self):
        email = f"reset_{uuid.uuid4().hex[:8]}@test.com"

        # Register
        requests.post(f"{BASE_URL}/register", json={
            "email": email,
            "password": "oldpass123",
            "display_name": "Reset User",
            "security_question": "First pet?",
            "security_answer": "buddy"
        })

        # Get security question
        r = requests.post(f"{BASE_URL}/auth/question", json={"email": email})
        assert r.status_code == 200
        assert r.json()["question"] == "First pet?"

        # Reset password
        r = requests.post(f"{BASE_URL}/auth/reset-password", json={
            "email": email,
            "security_answer": "buddy",
            "new_password": "newpass456"
        })
        assert r.status_code == 200

        # Login with new password
        r = requests.post(f"{BASE_URL}/login", json={
            "email": email,
            "password": "newpass456"
        })
        assert r.status_code == 200
        assert "token" in r.json()

        # Old password should fail
        r = requests.post(f"{BASE_URL}/login", json={
            "email": email,
            "password": "oldpass123"
        })
        assert r.status_code == 401


# ───────────────────────────────────────────────────────
# E2E: Structured Data Extraction Validation
# ───────────────────────────────────────────────────────
class TestStructuredExtraction:
    def test_uploaded_doc_has_structured_data(self):
        token, _ = fresh_user()
        files = {"file": ("struct_test.pdf", MINIMAL_PDF, "application/pdf")}
        r = requests.post(f"{BASE_URL}/upload", headers=auth(token), files=files)
        assert r.status_code == 200
        structured = r.json().get("structured", {})
        assert isinstance(structured, dict)
        # Should have at least document_type from our prompt
        assert "document_type" in structured or "error" in structured


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
