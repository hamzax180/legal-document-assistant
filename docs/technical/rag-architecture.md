# RAG Architecture (Retrieval-Augmented Generation)

## High-Level Flow
The system follows a standard RAG pipeline to answer user questions:

1.  **Ingestion**: The uploaded PDF text is extracted using `PyMuPDF`.
2.  **Chunking**: The document is split into manageable chunks for processing.
3.  **Embedding**: Each chunk is converted into a 384-dimensional vector using `sentence-transformers/all-MiniLM-L6-v2`.
4.  **Indexing**: Vectors are stored in an in-memory FAISS index.

## Query Process
1.  **User Question**: The question is embedded using the same transformer model.
2.  **Retrieval**: The FAISS index is searched for the top 3 most similar chunks (k=3).
3.  **Prompt Construction**: A strict prompt is built containing:
    ```
    Context: ...chunk 1... ...chunk 2...
    Question: ...user question...
    Answer in detail based on context only.
    ```
4.  **Generation**: The prompt is sent to Google's Gemini Flash model to generate the final response.
