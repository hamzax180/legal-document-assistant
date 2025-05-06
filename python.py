import os
import json
import fitz  # PyMuPDF
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import streamlit as st

# Set up Gemini API (use your key here)
GEMINI_API_KEY = "AIzaSyCTwyBXsKHQMI0I1AEC2ggvZg0UPR2rjtk"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-2.0-flash")

# Load embedding model
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# Function: Extract text from uploaded PDF
def extract_text_from_pdf(file_path):
    doc = fitz.open(file_path)
    pages = []
    for page in doc:
        pages.append(page.get_text())
    return pages

# Function: Generate structured summary
few_shot_prompt = '''
You are a legal document assistant. Here are examples of how to extract data from legal text:

Input: "This Non-Disclosure Agreement (NDA) is made effective as of Jan 1, 2019, between Altinbas Inc. and Hamzah Al Ahdal It shall remain in effect for three years."
Output: {
  "parties_involved": ["Altinbas Inc.", "Hamzah Al Ahdal"],
  "effective_date": "2019-01-01",
  "duration": "3 years",
  "type": "Non-Disclosure Agreement"
}

Now extract structured info from this text:
'''

def extract_structured_info(text):
    prompt = few_shot_prompt + text
    response = model.generate_content(prompt)
    return response.text

# RAG setup: Create FAISS index from document pages
def build_faiss_index(pages):
    embeddings = embedder.encode(pages)
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(np.array(embeddings))
    return index, embeddings

# RAG Q&A over document
def rag_qa(query, pages, index, embeddings):
    query_embedding = embedder.encode([query])
    D, I = index.search(np.array(query_embedding), k=3)
    retrieved_chunks = [pages[i] for i in I[0]]
    context = "\n---\n".join(retrieved_chunks)
    prompt = f"Answer the following question using the context below:\n\nContext:\n{context}\n\nQuestion: {query}\nAnswer:"
    response = model.generate_content(prompt)
    return response.text

# GenAI Evaluation: Let Gemini score its own answers for helpfulness, completeness, relevance
def evaluate_response(query, context, answer):
    eval_prompt = f"""
    Evaluate the following response based on the context and query:

    Query: {query}
    Context: {context[:1000]}...
    Answer: {answer}

    Give a short JSON with keys: helpfulness (1-5), completeness (1-5), relevance (1-5), and reasoning.
    """
    eval_response = model.generate_content(eval_prompt)
    return eval_response.text

# ------------------ Streamlit UI ------------------
st.set_page_config(page_title="Legal Document Assistant", layout="wide")
st.title("📄 AI Legal Document Assistant (Gemini + RAG + Evaluation)")

uploaded_file = st.file_uploader("Upload a Legal PDF", type="pdf")

if uploaded_file:
    with open("temp_doc.pdf", "wb") as f:
        f.write(uploaded_file.read())

    pages = extract_text_from_pdf("temp_doc.pdf")
    full_text = "\n".join(pages)

    with st.spinner("Extracting structured data..."):
        structured_output = extract_structured_info(full_text)
        # Clean up the structured output (remove any code block markers like "```json")
        try:
            structured_json = json.loads(structured_output.replace("```json", "").replace("```", "").strip())
            st.subheader("📊 Structured Summary (JSON)")
            st.json(structured_json)
        except json.JSONDecodeError:
            st.error("Error parsing structured summary response.")

    with st.spinner("Building knowledge index for Q&A..."):
        index, embeddings = build_faiss_index(pages)

    st.subheader("💬 Ask a question about the document")
    user_query = st.text_input("Your Question")
    if user_query:
        with st.spinner("Retrieving answer with RAG..."):
            answer = rag_qa(user_query, pages, index, embeddings)
        st.success("Answer:")
        st.write(answer)

        # Optional: Evaluate the generated answer
        with st.spinner("Evaluating answer using GenAI..."):
            eval_result = evaluate_response(user_query, "\n".join(pages), answer)
            # Clean up the evaluation result (remove any code block markers like "```json")
            try:
                eval_json = json.loads(eval_result.replace("```json", "").replace("```", "").strip())
                st.subheader("🧪 GenAI Evaluation")
                st.json(eval_json)
            except json.JSONDecodeError:
                st.error("Error parsing evaluation response.")
