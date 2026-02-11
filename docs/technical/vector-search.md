# Vector Search Technology

## FAISS
We use **FAISS (Facebook AI Similarity Search) CPU** for efficient similarity search of dense vectors in memory. The index is built on-the-fly when a document is uploaded.

## Embedding Model
- **Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Output**: 384-dimensional dense vectors.

## Indexing
Indices are built per-document (`IndexFlatL2`). This `in-memory` design ensures privacy as no vectors are persisted to disk, clearing all data on server restart.
