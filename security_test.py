import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

def log(msg, status="INFO"):
    print(f"[{status}] {msg}")

def test_security():
    # 1. Setup Victim
    log("Creating Victim account...")
    victim_email = "victim@test.com"
    r = requests.post(f"{BASE_URL}/register", json={
        "email": victim_email, "password": "password123", "display_name": "Victim"
    })
    # Handle case if already exists (restart/re-run)
    if r.status_code == 409:
        r = requests.post(f"{BASE_URL}/login", json={"email": victim_email, "password": "password123"})
    
    if r.status_code != 200:
        log(f"Failed to setup victim: {r.text}", "ERROR")
        sys.exit(1)
        
    victim_token = r.json()["token"]
    log("Victim logged in.")

    # 2. Victim Uploads Data
    log("Victim uploading confidential document...")
    # Valid minimal PDF content
    minimal_pdf = (
        b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
        b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n"
        b"0000000010 00000 n\n0000000060 00000 n\n0000000111 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
    )
    files = {'file': ('confidential.pdf', minimal_pdf, 'application/pdf')}
    r = requests.post(f"{BASE_URL}/upload", headers={"Authorization": f"Bearer {victim_token}"}, files=files)
    
    if r.status_code != 200:
        log(f"Victim upload failed: {r.text}", "ERROR")
        sys.exit(1)
        
    doc_id = r.json()["doc_id"]
    log(f"Confidential Doc ID secured: {doc_id}")

    # 3. Setup Attacker
    log("Creating Attacker account...")
    attacker_email = "attacker@test.com"
    r = requests.post(f"{BASE_URL}/register", json={
        "email": attacker_email, "password": "password123", "display_name": "Attacker"
    })
    if r.status_code == 409:
        r = requests.post(f"{BASE_URL}/login", json={"email": attacker_email, "password": "password123"})
        
    attacker_token = r.json()["token"]
    log("Attacker logged in.")

    # 4. Attack: List Documents
    log("Attack 1: Attacker trying to list all documents...")
    r = requests.get(f"{BASE_URL}/documents", headers={"Authorization": f"Bearer {attacker_token}"})
    docs = r.json()
    
    if len(docs) == 0:
        log("PASS: Attacker sees empty list.", "SUCCESS")
    else:
        log(f"FAIL: Attacker saw {len(docs)} documents! {docs}", "CRITICAL_FAIL")

    # 5. Attack: Direct Access to Doc ID
    log(f"Attack 2: Attacker trying to access Victim's Doc ID {doc_id} directly...")
    r = requests.get(f"{BASE_URL}/documents/{doc_id}", headers={"Authorization": f"Bearer {attacker_token}"})
    
    if r.status_code == 404:
        log("PASS: Server returned 404 Not Found.", "SUCCESS")
    else:
        log(f"FAIL: Server returned {r.status_code}: {r.text}", "CRITICAL_FAIL")

    # 6. Attack: Delete Doc
    log(f"Attack 3: Attacker trying to delete Victim's Doc ID {doc_id}...")
    r = requests.delete(f"{BASE_URL}/documents/{doc_id}", headers={"Authorization": f"Bearer {attacker_token}"})
    
    if r.status_code == 404:
        log("PASS: Server returned 404 Not Found.", "SUCCESS")
    else:
        log(f"FAIL: Server returned {r.status_code}: {r.text}", "CRITICAL_FAIL")

    # 7. Attack: No Auth
    log("Attack 4: Accessing without token...")
    r = requests.get(f"{BASE_URL}/documents")
    if r.status_code == 401:
        log("PASS: Server returned 401 Unauthorized.", "SUCCESS")
    else:
        log(f"FAIL: Server returned {r.status_code}", "CRITICAL_FAIL")

if __name__ == "__main__":
    try:
        test_security()
    except Exception as e:
        log(f"Test failed with exception: {e}", "ERROR")
