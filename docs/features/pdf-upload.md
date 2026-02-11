# PDF Upload & Parsing

## Overview
The system accepts PDF documents via a drag-and-drop interface or file selection.

## How it Works
1.  User selects a PDF file (max 10MB).
2.  Backend validates the file type.
3.  **PyMuPDF** (`fitz`) extracts text from each page in memory.
4.  Text is chunked and indexed into a FAISS vector store.
5.  A unique Document ID is returned for the session.

## Data Storage
- **Metadata**: Document info and chat history stored in SQLite (`legal_docs.db`).
- **Vectors**: Stored in FAISS index (reloaded on startup if implemented, currently in-memory).
- **Privacy**: Data resides locally within the container. Deleting the container/volume wipes the data.
