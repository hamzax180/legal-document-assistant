# Build Failure Report

The Docker build process failed for the backend image (`legal-doc-backend`).

## Error Details
- **Timestamp**: After running for ~8 minutes.
- **Cause**: `Input/output error` (Likely Docker Desktop ran out of disk space or encountered a filesystem issue during heavy ML library installation).

## Recommended Actions
1.  **Restart Docker Desktop**.
2.  **Free Up Space**: Run `docker system prune` to clear unused data.
3.  **Build Manually**:
    ```bash
    docker build -t legal-doc-backend:latest ./backend
    docker build -t legal-doc-frontend:latest ./frontend
    ```
4.  **Create Secret**:
    ```bash
    # Only if you haven't already
    kubectl create secret generic backend-secret --from-literal=GEMINI_API_KEY=YOUR_KEY
    ```
5.  **Deploy**:
    ```bash
    kubectl apply -f k8s/
    ```

Please follow these steps to deploy locally.
