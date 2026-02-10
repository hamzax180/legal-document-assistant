# Kubernetes Deployment Guide

This guide explains how to deploy the Legal Doc Assistant to a local Kubernetes cluster.

## Prerequisites
- Docker Desktop or Minikube
- `kubectl` configured

## 1. Build Docker Images
Since we are using a local cluster, we need to build the images so they are available to Kubernetes.
```bash
docker build -t legal-doc-backend:latest ./backend
docker build -t legal-doc-frontend:latest ./frontend
```
*Note: For Minikube, run `eval $(minikube docker-env)` first to build inside the Minikube Docker daemon.*

## 2. Create Secret
The backend requires `GEMINI_API_KEY`. Create a secret for it:
```bash
kubectl create secret generic backend-secret --from-literal=GEMINI_API_KEY=YOUR_ACTUAL_API_KEY
```

## 3. Apply Manifests
Deploy the backend and frontend (2 replicas each):
```bash
kubectl apply -f k8s/
```

## 4. Access the Application
- **Frontend**: `http://localhost` (if LoadBalancer supported by Docker Desktop) or via `minikube service frontend`.
- **Backend (Internal)**: Accessible to frontend via `http://backend:8000`.

## 5. Scaling
To scale replicas (default is 2):
```bash
kubectl scale deployment backend --replicas=3
kubectl scale deployment frontend --replicas=3
```
