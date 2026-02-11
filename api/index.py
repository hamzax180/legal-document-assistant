print("[INFO] Loading api/index.py...", flush=True)
import sys
import os
print(f"[INFO] Current working directory: {os.getcwd()}", flush=True)
print(f"[INFO] sys.path: {sys.path}", flush=True)

try:
    from backend.app import app
    print("[INFO] Successfully imported app from backend.app", flush=True)
except Exception as e:
    print(f"[ERROR] Failed to import app: {e}", flush=True)
