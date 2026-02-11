# Deployment Architecture

## Kubernetes (K8s)
- **Frontend**: Served via Nginx Pod. Exposes port 30888 via a `NodePort` Service.
- **Backend**: Python/FastAPI Pod. Exposes port 8000 via a `ClusterIP` Service.
- **Secrets**: `backend-secret` securely stores the `GEMINI_API_KEY`.
- **Scaling**: Configured for replicas (default 2, scalable).

## Docker Compose (Local Dev)
- **Frontend**: Runs on port `3000`.
- **Backend**: Runs on port `8000`.
- **Volumes**: Local SQLite DB is mounted for persistence (`./backend/legal_docs.db:/app/legal_docs.db`).

## Docker Structure
- **Backend**: `python:3.9-slim`. Optimized with multi-stage builds.
- **Frontend**: `nginx:alpine`. Static assets + proxy config.
