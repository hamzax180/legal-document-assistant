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

## Architecture
The application is containerized using Docker and designed to run on Kubernetes with high availability.

### High-Level Design
```mermaid
graph TD
    User[User Browser] -->|HTTP/80| FrontendSVC[K8s Service: Frontend (LoadBalancer)]
    FrontendSVC -->|Round Robin| PodFE[Pod: Frontend (Nginx)]
    
    subgraph Kubernetes Cluster
        PodFE -->|Serve Static| HTML[index.html / app.js]
        PodFE -->|Proxy /api| BackendSVC[K8s Service: Backend (ClusterIP)]
        
        BackendSVC -->|Round Robin| PodBE[Pod: Backend (FastAPI)]
        
        subgraph "Pod: Backend"
            API[FastAPI] -->|Parse| PyMuPDF
            API -->|Search| FAISS[(In-Memory Vector DB)]
        end
    end
    
    PodBE -->|HTTPS| Gemini[Google Gemini API]
```

### Components
1.  **Frontend (Nginx)**: 
    -   Serves the static web assets.
    -   Acts as a reverse proxy, forwarding `/api` requests to the internal backend service.
    -   Running 2 Replicas for availability.
    
2.  **Backend (FastAPI)**:
    -   Handles file processing, embedding, and LLM interaction.
    -   Stateless design allows for horizontal scaling.
    -   Running 2 Replicas.

3.  **Kubernetes Resources**:
    -   **Deployments**: Manage the pod replicas.
    -   **Services**: Expose the frontend externally and the backend internally.
    -   **Secrets**: Securely store the `GEMINI_API_KEY`.

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
