# Backend Service

This project component provides the API for the Legal Document Assistant.

## API Overview
- `POST /upload`: Process PDF document.
- `POST /ask`: Query the document with RAG.

## Setup
1. `pip install -r requirements.txt`
2. `uvicorn app:app --reload`
