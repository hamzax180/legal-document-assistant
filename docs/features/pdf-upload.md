# PDF Upload & Parsing

## Overview
The system accepts PDF documents via a drag-and-drop interface or file selection.

## How it Works
1.  User selects a PDF file (max 10MB).
2.  Backend validates the file type.
3.  **PyMuPDF** (`fitz`) extracts text from each page in memory.
4.  Text is chunked and indexed into a FAISS vector store.
5.  A unique Document ID is returned for the session.

## Constraints
- Only text-based PDFs are supported (OCR for images is not implemented).
- Files are stored in volatile memory (RAM) for privacy; restarting the server clears them.
