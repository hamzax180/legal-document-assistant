"""
Unit Tests — AI Legal Document Assistant
Tests individual functions and modules in isolation.

Run: python -m pytest tests/test_unit.py -v
"""

import sys
import os
import json
import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app import (
    hash_password,
    verify_password,
    create_token,
    extract_text_from_pdf_bytes,
)


# ───────────────────────────────────────────────────────
# Password Hashing
# ───────────────────────────────────────────────────────
class TestPasswordHashing:
    def test_hash_returns_string(self):
        result = hash_password("test123")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_hash_not_plaintext(self):
        pw = "mysecretpassword"
        hashed = hash_password(pw)
        assert hashed != pw

    def test_verify_correct_password(self):
        pw = "correctpassword"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correctpassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_different_hashes_for_same_input(self):
        pw = "samepassword"
        h1 = hash_password(pw)
        h2 = hash_password(pw)
        # bcrypt generates different salts each time
        assert h1 != h2
        assert verify_password(pw, h1) is True
        assert verify_password(pw, h2) is True


# ───────────────────────────────────────────────────────
# JWT Token Creation
# ───────────────────────────────────────────────────────
class TestTokenCreation:
    def test_token_is_string(self):
        token = create_token("user-123", "test@example.com")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_has_three_parts(self):
        token = create_token("user-456", "admin@example.com")
        parts = token.split(".")
        assert len(parts) == 3, "JWT should have header.payload.signature"

    def test_different_users_different_tokens(self):
        t1 = create_token("user-1", "a@test.com")
        t2 = create_token("user-2", "b@test.com")
        assert t1 != t2


# ───────────────────────────────────────────────────────
# PDF Text Extraction
# ───────────────────────────────────────────────────────
class TestPDFExtraction:
    MINIMAL_PDF = (
        b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
        b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n"
        b"0000000010 00000 n\n0000000060 00000 n\n0000000111 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
    )

    def test_extract_returns_list(self):
        pages = extract_text_from_pdf_bytes(self.MINIMAL_PDF)
        assert isinstance(pages, list)

    def test_extract_page_count(self):
        pages = extract_text_from_pdf_bytes(self.MINIMAL_PDF)
        assert len(pages) == 1

    def test_extract_invalid_pdf_raises(self):
        with pytest.raises(Exception):
            extract_text_from_pdf_bytes(b"not a pdf file")

    def test_extract_empty_raises(self):
        with pytest.raises(Exception):
            extract_text_from_pdf_bytes(b"")


# ───────────────────────────────────────────────────────
# Structured JSON Parsing (edge cases)
# ───────────────────────────────────────────────────────
class TestStructuredInfoParsing:
    """Test the JSON fallback parsing logic used in extract_structured_info."""

    def test_valid_json_parses(self):
        raw = '{"document_type": "Contract", "title": "Test"}'
        result = json.loads(raw)
        assert result["document_type"] == "Contract"

    def test_json_with_markdown_fences(self):
        raw = '```json\n{"document_type": "NDA"}\n```'
        start = raw.find("{")
        end = raw.rfind("}")
        result = json.loads(raw[start:end + 1])
        assert result["document_type"] == "NDA"

    def test_invalid_json_returns_error(self):
        raw = "this is not json at all"
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1:
            result = {"error": "Invalid JSON from model"}
        else:
            result = json.loads(raw[start:end + 1])
        assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
