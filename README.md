# 📄 AI Legal Document Assistant

This project is an AI-powered web application that assists in analyzing legal PDF documents using Google's Gemini API, FAISS, and RAG (Retrieval-Augmented Generation). Built with Streamlit, it offers structured data extraction, semantic search, question answering, and AI-driven evaluation of responses.

## ✨ Features

- 📄 **PDF Text Extraction** using PyMuPDF
- 📊 **Structured Data Extraction** from legal text using a few-shot prompt and Gemini
- 🔍 **Semantic Search** over document content with FAISS and SentenceTransformers
- 💬 **RAG-based Q&A** to answer queries from the uploaded legal document
- 🧪 **Answer Evaluation** for helpfulness, completeness, and relevance via Gemini

## 🛠 Technologies Used

- Python
- Streamlit (UI framework)
- Google Generative AI (Gemini API)
- FAISS (vector similarity search)
- SentenceTransformers (`all-MiniLM-L6-v2`)
- PyMuPDF (`fitz`)
- JSON, NumPy

## 🚀 How to Run

1. **Install dependencies**:
   ```bash
   pip install streamlit google-generativeai sentence-transformers faiss-cpu pymupdf
Add your Gemini API Key:
Replace GEMINI_API_KEY = "..." in python.py with your actual API key.

Start the app:

streamlit run python.py
Use the app:

Upload a legal PDF

View structured json data extraction

Ask questions about the document and get answer

 AI-generated answers evalution reviewing its preformance

