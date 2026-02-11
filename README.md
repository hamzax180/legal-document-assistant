# AI Legal Document Assistant

A RAG-based legal document assistant that allows users to upload PDFs and ask questions using Google's Gemini Flash model.

![Screenshot](https://via.placeholder.com/800x400?text=AI+Legal+Assistant)
*(Add actual screenshot here)*

## Features
- **PDF Upload & Parsing**: Extracts text from PDF documents instantly.
- **RAG Architecture**: Retrieves relevant context from the document to answer queries accurately.
- **Gemini Flash Integration**: High-speed, low-latency responses.
- **Self-Evaluation**: Automatically grades answers on Helpfulness, Completeness, and Relevance.
- **Privacy-First**: In-memory processing (no persistent database storage of sensitive documents).

## Project Structure
- `backend/`: FastAPI application (Python).
- `frontend/`: Vanilla JS/HTML/CSS interface.
- `k8s/`: Kubernetes manifests for deployment.

## Quick Start (Docker)

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/hamzax180/legal-document-assistant.git
    cd legal-document-assistant
    ```

2.  **Set up Environment**:
    Create a `.env` file in the root or `backend/` directory with your API key:
    ```env
    GEMINI_API_KEY=YOUR_ACTUAL_API_KEY
    ```

3.  **Build and Run**:
    ```bash
    docker-compose up --build
    ```
    *(Note: If you don't have docker-compose, check `README_K8S.md` for individual build commands)*

4.  **Access**:
    Open `http://localhost` in your browser.

## Kubernetes Deployment
See [README_K8S.md](README_K8S.md) for detailed instructions on deploying to a local Kubernetes cluster.

## Security Note
This project requires a Google Gemini API Key.
**NEVER commit your API key to version control.**
ALWAYS use environment variables or Kubernetes Secrets.

## License
MIT
