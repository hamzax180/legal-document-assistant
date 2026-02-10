# New Layout Design

I have redesigned the frontend layout to be more modern and user-friendly.

## Features
- **Two-Panel Layout:**
  - **Left Panel:** Document tools (Summary, JSON, Suggested Questions).
  - **Right Panel:** Interactive Chat & Evaluation.
- **Improved Sidebar:** Collapsible sidebar with document list.
- **Dark Glassmorphism:** Continued the premium dark theme with polished UI elements.

## Running the App

The application should be running on:
- **Frontend:** [http://127.0.0.1:3000](http://127.0.0.1:3000)
- **Backend API:** http://127.0.0.1:8000

If you need to restart standard commands:

**Backend:**
```bash
cd backend
.\venv\Scripts\activate
uvicorn app:app --reload --port 8000 --host 127.0.0.1
```

**Frontend:**
```bash
cd frontend
python -m http.server 3000 --bind 127.0.0.1
```

Enjoy the new design!
