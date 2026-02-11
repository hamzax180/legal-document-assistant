# Deployment Architecture

## Kubernetes (K8s)
- **Frontend**: Served via Nginx in a Pod. Exposes port 80 via a `LoadBalancer` Service.
- **Backend**: Python/FastAPI app in a Pod. Exposes port 8000 via a `ClusterIP` Service (internal only).
- **Secrets**: `backend-secret` stores the `GEMINI_API_KEY`.
- **Scaling**: Configured for 2 replicas by default in `k8s/backend-deployment.yaml`.

## Docker
- **Backend**: Uses `python:3.9-slim` base image. Copies `requirements.txt` and specific source files.
- **Frontend**: Uses `nginx:alpine` to serve static assets and proxy API requests.
