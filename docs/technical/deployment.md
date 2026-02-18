## Production (Vercel)
- **Frontend & Backend**: Deployed as a unified serverless application on Vercel.
- **API Routing**: Rewrites configured in `vercel.json` for clean URLs and `/api` proxying.
- **Database**: 
    - **Vercel Postgres**: Primary production database for user data and document persistence.
    - **SQLite**: Local fallback/development database.
- **Secrets**: Environment variables (`GEMINI_API_KEY`, `POSTGRES_URL`, `JWT_SECRET`) managed via Vercel Dashboard.

## Kubernetes (K8s) — Hybrid/On-Prem
- **Frontend**: Served via Nginx Pod. Exposes port 80 (standard) or NodePort.
- **Backend**: Python/FastAPI Pod. 
- **Secrets**: `backend-secret` securely stores the `GEMINI_API_KEY`.
- **Scaling**: Optimized for replica-based horizontal scaling.

## Docker & Docker Compose
- **Unified Stack**: Runs both Python backend and Nginx frontend.
- **Volumes**: Data persisted via local SQLite mount.

