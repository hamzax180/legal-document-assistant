// Docker/K8s compatibility: Use relative path /api in production (Nginx proxy),
// but keep http://127.0.0.1:8000 for local dev (port 3000).
const API_BASE = window.location.port === "3000" ? "http://127.0.0.1:8000" : "/api";

let docId = null;
let selectedFile = null;


// ===== TOAST NOTIFICATIONS =====
function showToast(message, type = "info", duration = 4500) {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;

  const icons = {
    success: "✓",
    error: "✕",
    info: "ℹ",
    warning: "⚠"
  };

  toast.innerHTML = `<span style="font-size: 1.1rem;">${icons[type] || "ℹ"}</span> ${message}`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, duration);
}


// ===== ERROR HANDLING HELPER =====
async function handleApiError(res, fallbackMsg) {
  let errorData;
  try {
    errorData = await res.json();
  } catch {
    errorData = { detail: fallbackMsg };
  }

  if (res.status === 429) {
    const msg = `Rate limit reached — please wait ${errorData.retry_after || 10}s and try again.`;
    showToast(msg, "warning");
    return msg;
  } else if (res.status === 503) {
    const msg = "AI service temporarily unavailable. Please try again in a moment.";
    showToast(msg, "warning");
    return msg;
  } else if (res.status === 500) {
    const msg = "Server error. Please try again. If it persists, restart the backend.";
    showToast(msg, "error");
    return msg;
  } else if (res.status === 404) {
    const msg = "Document not found. It may have been deleted. Please re-upload.";
    showToast(msg, "error");
    return msg;
  } else if (res.status === 400) {
    const msg = errorData.detail || "Bad request.";
    showToast(msg, "warning");
    return msg;
  }
  const msg = errorData.detail || fallbackMsg;
  showToast(msg, "error");
  return msg;
}


// ===== DOM ELEMENTS =====
const pdfInput = document.getElementById("pdfInput");
const uploadBtn = document.getElementById("uploadBtn");
const uploadStatus = document.getElementById("uploadStatus");
const jsonBox = document.getElementById("jsonBox");
const uploadZone = document.getElementById("uploadZone");
const fileName = document.getElementById("fileName");
const uploadOverlay = document.getElementById("uploadOverlay");
const uploadModalClose = document.getElementById("uploadModalClose");
const miniUploadZone = document.getElementById("miniUploadZone");
const uploadProgress = document.getElementById("uploadProgress");

const chatBox = document.getElementById("chatBox");
const questionInput = document.getElementById("questionInput");
const sendBtn = document.getElementById("sendBtn");

const evalBox = document.getElementById("evalBox");
const evalToggle = document.getElementById("evalToggle");

const docList = document.getElementById("docList");

const summaryBox = document.getElementById("summaryBox");
const summarizeBtn = document.getElementById("summarizeBtn");

const suggestBox = document.getElementById("suggestBox");

const sidebarToggle = document.getElementById("sidebarToggle");
const sidebar = document.getElementById("sidebar");

// Empty state refs
const summaryEmpty = document.getElementById("summaryEmpty");
const jsonEmpty = document.getElementById("jsonEmpty");
const suggestEmpty = document.getElementById("suggestEmpty");


// ===== UPLOAD MODAL =====
function openUploadModal() {
  uploadOverlay.classList.add("show");
}

function closeUploadModal() {
  uploadOverlay.classList.remove("show");
}

miniUploadZone.addEventListener("click", openUploadModal);
uploadModalClose.addEventListener("click", closeUploadModal);

uploadOverlay.addEventListener("click", (e) => {
  if (e.target === uploadOverlay) closeUploadModal();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && uploadOverlay.classList.contains("show")) {
    closeUploadModal();
  }
});


// ===== SIDEBAR TOGGLE =====
sidebarToggle.addEventListener("click", () => {
  sidebar.classList.toggle("collapsed");
  sidebar.classList.toggle("mobile-open");
});


// ===== PANEL TABS =====
document.querySelectorAll(".panel-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    const target = tab.dataset.tab;
    document.querySelectorAll(".panel-tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    document.querySelectorAll(".tab-content").forEach(tc => tc.classList.remove("active"));
    document.getElementById(`tab-${target}`).classList.add("active");
  });
});


// ===== UPLOAD ZONE: Click & Drag =====
uploadZone.addEventListener("click", () => pdfInput.click());

// Mouse glow effect on upload zone
uploadZone.addEventListener("mousemove", (e) => {
  const rect = uploadZone.getBoundingClientRect();
  const x = ((e.clientX - rect.left) / rect.width) * 100;
  const y = ((e.clientY - rect.top) / rect.height) * 100;
  uploadZone.style.setProperty("--mouse-x", x + "%");
  uploadZone.style.setProperty("--mouse-y", y + "%");
});

uploadZone.addEventListener("dragover", e => {
  e.preventDefault();
  uploadZone.classList.add("drag-over");
});

uploadZone.addEventListener("dragleave", () => {
  uploadZone.classList.remove("drag-over");
});

// DROP Handler
uploadZone.addEventListener("drop", e => {
  e.preventDefault();
  uploadZone.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file && file.name.toLowerCase().endsWith(".pdf")) {
    selectedFile = file;
    pdfInput.files = e.dataTransfer.files;
    showSelectedFile(file.name);
  } else {
    showToast("Please drop a valid PDF file.", "warning");
  }
});

// FILE INPUT Handler
pdfInput.addEventListener("change", () => {
  if (pdfInput.files[0]) {
    selectedFile = pdfInput.files[0];
    showSelectedFile(selectedFile.name);
  }
});

function showSelectedFile(name) {
  fileName.textContent = name;
  uploadBtn.style.display = "flex";
}


// ===== EMPTY STATE MANAGEMENT =====
function updateEmptyStates() {
  if (summaryEmpty) {
    summaryEmpty.style.display = summaryBox.innerHTML.trim() ? "none" : "block";
  }
  if (jsonEmpty) {
    jsonEmpty.style.display = jsonBox.textContent.trim() ? "none" : "block";
  }
  if (suggestEmpty) {
    suggestEmpty.style.display = suggestBox.children.length > 0 ? "none" : "block";
  }
}


// ===== SIDEBAR: Load Documents =====
async function loadDocuments() {
  try {
    const res = await fetch(`${API_BASE}/documents`);
    const docs = await res.json();

    if (!docs.length) {
      docList.innerHTML = `
        <div class="sidebar-empty">
          <div class="sidebar-empty-icon">
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none" opacity="0.3">
              <rect x="8" y="4" width="24" height="32" rx="3" stroke="currentColor" stroke-width="1.5"/>
              <path d="M14 14h12M14 19h8M14 24h10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.5"/>
            </svg>
          </div>
          No documents yet.<br>Upload a PDF to get started.
        </div>`;
      return;
    }

    docList.innerHTML = "";
    docs.forEach(doc => {
      const item = document.createElement("div");
      item.className = `sidebar-item${doc.id === docId ? " active" : ""}`;
      item.dataset.id = doc.id;

      const date = new Date(doc.created_at + "Z");
      const dateStr = date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });

      item.innerHTML = `
        <div class="sidebar-item-name" title="${doc.filename}">${doc.filename}</div>
        <div class="sidebar-item-meta">${doc.page_count} pages · ${dateStr}</div>
        <button class="sidebar-item-delete" title="Delete document" onclick="event.stopPropagation(); deleteDoc('${doc.id}')">✕</button>
      `;

      item.addEventListener("click", () => loadDocument(doc.id));
      docList.appendChild(item);
    });
  } catch (err) {
    console.error("Failed to load documents:", err);
  }
}


// ===== SIDEBAR: Load Single Document =====
async function loadDocument(id) {
  try {
    const res = await fetch(`${API_BASE}/documents/${id}`);
    const data = await res.json();

    docId = data.doc_id;

    // Update sidebar active state
    document.querySelectorAll(".sidebar-item").forEach(el => {
      el.classList.toggle("active", el.dataset.id === docId);
    });

    // Show JSON
    jsonBox.textContent = JSON.stringify(data.structured, null, 2);

    // Show chat history
    if (data.chat_history && data.chat_history.length) {
      renderHistory(data.chat_history);
    } else {
      chatBox.innerHTML = `
        <div class="chat-welcome">
          <div class="chat-welcome-icon">
            <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
              <circle cx="32" cy="32" r="28" stroke="currentColor" stroke-width="1" opacity="0.15"/>
              <circle cx="32" cy="32" r="20" stroke="currentColor" stroke-width="1" opacity="0.1"/>
              <path d="M20 22h24a2 2 0 012 2v14a2 2 0 01-2 2H28l-8 6V24a2 2 0 012-2z" stroke="currentColor" stroke-width="1.5" opacity="0.4"/>
              <path d="M28 31h8M28 35h5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.3"/>
            </svg>
          </div>
          <h3>Ask anything about your document</h3>
          <p>Start asking questions about <strong>${data.filename}</strong>.</p>
        </div>
      `;
    }

    summaryBox.innerHTML = "";
    evalBox.innerHTML = "";
    uploadStatus.textContent = `✓ Loaded: ${data.filename} (${data.pages} pages)`;

    fetchSuggestions(docId);
    updateEmptyStates();

    if (window.innerWidth <= 768) {
      sidebar.classList.remove("mobile-open");
    }

  } catch (err) {
    console.error("Failed to load document:", err);
    showToast("Failed to load document", "error");
  }
}


// ===== DELETE DOCUMENT =====
async function deleteDoc(id) {
  if (!confirm("Delete this document and all its chat history?")) return;

  try {
    await fetch(`${API_BASE}/documents/${id}`, { method: "DELETE" });

    if (docId === id) {
      docId = null;
      jsonBox.textContent = "";
      summaryBox.innerHTML = "";
      suggestBox.innerHTML = "";
      chatBox.innerHTML = `
        <div class="chat-welcome">
          <div class="chat-welcome-icon">
            <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
              <circle cx="32" cy="32" r="28" stroke="currentColor" stroke-width="1" opacity="0.15"/>
              <path d="M20 22h24a2 2 0 012 2v14a2 2 0 01-2 2H28l-8 6V24a2 2 0 012-2z" stroke="currentColor" stroke-width="1.5" opacity="0.4"/>
            </svg>
          </div>
          <h3>Ask anything about your document</h3>
          <p>Upload a legal PDF and start asking questions.<br>The AI will analyze and respond using context from your document.</p>
        </div>
      `;
      evalBox.innerHTML = "";
      uploadStatus.textContent = "";
      updateEmptyStates();
    }

    loadDocuments();
    showToast("Document deleted successfully", "success");
  } catch (err) {
    console.error("Failed to delete document:", err);
    showToast("Failed to delete document", "error");
  }
}


// ===== CHAT HELPERS =====
function getTimeStr() {
  return new Date().toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function addMsg(role, text) {
  const welcome = chatBox.querySelector(".chat-welcome");
  if (welcome) welcome.remove();

  // Remove typing indicator if present
  const typing = chatBox.querySelector(".typing-indicator");
  if (typing) typing.remove();

  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.innerHTML = `
    <strong>${role === "user" ? "You" : "Assistant"}:</strong>
    <span class="msg-time">${getTimeStr()}</span>
    ${text}
  `;
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function showTypingIndicator() {
  const welcome = chatBox.querySelector(".chat-welcome");
  if (welcome) welcome.remove();

  const div = document.createElement("div");
  div.className = "typing-indicator";
  div.innerHTML = `
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
  `;
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function removeTypingIndicator() {
  const typing = chatBox.querySelector(".typing-indicator");
  if (typing) typing.remove();
}

function renderHistory(history) {
  chatBox.innerHTML = "";
  history.forEach(m => {
    addMsg("user", m.user);
    addMsg("assistant", m.assistant);
  });
}


// ===== UPLOAD CLICK =====
uploadBtn.onclick = async () => {
  if (!selectedFile) {
    showToast("No file selected. Please choose a PDF.", "warning");
    return;
  }

  // Show progress, hide button
  uploadBtn.style.display = "none";
  uploadProgress.style.display = "block";
  uploadStatus.textContent = "Uploading & analyzing...";

  const form = new FormData();
  form.append("file", selectedFile);

  try {
    const res = await fetch(`${API_BASE}/upload`, { method: "POST", body: form });
    if (!res.ok) {
      const errMsg = await handleApiError(res, "Upload failed.");
      uploadStatus.textContent = errMsg;
      uploadProgress.style.display = "none";
      uploadBtn.style.display = "flex";
      return;
    }

    const data = await res.json();

    docId = data.doc_id;
    uploadStatus.textContent = `✓ Uploaded: ${data.filename} (${data.pages} pages)`;
    jsonBox.textContent = JSON.stringify(data.structured, null, 2);
    summaryBox.innerHTML = "";

    loadDocuments();
    fetchSuggestions(docId);

    // Reset UI
    fileName.textContent = "";
    uploadBtn.style.display = "none";
    uploadProgress.style.display = "none";
    pdfInput.value = "";
    closeUploadModal();
    updateEmptyStates();

    // Switch to JSON tab
    document.querySelector('.panel-tab[data-tab="json"]').click();

    chatBox.innerHTML = `
      <div class="chat-welcome">
        <div class="chat-welcome-icon">
          <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
            <circle cx="32" cy="32" r="28" stroke="currentColor" stroke-width="1" opacity="0.15"/>
            <path d="M22 32l6 6 14-14" stroke="#22c55e" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.8"/>
          </svg>
        </div>
        <h3>Document ready!</h3>
        <p>Ask anything about <strong>${data.filename}</strong>.</p>
      </div>
    `;

    showToast(`"${data.filename}" uploaded successfully!`, "success");

  } catch (err) {
    console.error("Upload error:", err);
    uploadStatus.textContent = "";
    uploadProgress.style.display = "none";
    uploadBtn.style.display = "flex";
    showToast("Could not connect to the server. Is the backend running?", "error");
  }
};


// ===== SUMMARIZE =====
summarizeBtn.onclick = async () => {
  if (!docId) return;

  summarizeBtn.classList.add("loading");
  summaryBox.innerHTML = '<div class="summary-loading"><div class="spinner"></div><span>Generating summary...</span></div>';
  if (summaryEmpty) summaryEmpty.style.display = "none";

  try {
    const res = await fetch(`${API_BASE}/summarize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id: docId })
    });

    if (!res.ok) {
      const errMsg = await handleApiError(res, "Failed to generate summary.");
      summaryBox.innerHTML = `<div class="summary-error">${errMsg}</div>`;
      summarizeBtn.classList.remove("loading");
      updateEmptyStates();
      return;
    }

    const data = await res.json();
    summaryBox.innerHTML = data.summary.replace(/\n/g, "<br>");
    updateEmptyStates();
    showToast("Summary generated!", "success");
  } catch (err) {
    summaryBox.innerHTML = '<div class="summary-error">Could not connect to the server. Is the backend running?</div>';
    showToast("Failed to generate summary", "error");
    console.error(err);
  } finally {
    summarizeBtn.classList.remove("loading");
  }
};


// ===== SUGGESTED QUESTIONS =====
async function fetchSuggestions(id) {
  suggestBox.innerHTML = "";

  try {
    const res = await fetch(`${API_BASE}/suggest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id: id })
    });

    const data = await res.json();

    if (data.questions && data.questions.length) {
      suggestBox.innerHTML = "";

      data.questions.forEach((q, i) => {
        const chip = document.createElement("button");
        chip.className = "suggest-chip";
        chip.textContent = q;
        chip.style.animationDelay = `${i * 0.1}s`;
        chip.addEventListener("click", () => {
          questionInput.value = q;
          questionInput.focus();
          sendBtn.onclick();
        });
        suggestBox.appendChild(chip);
      });
    }

    updateEmptyStates();
  } catch (err) {
    console.error("Failed to fetch suggestions:", err);
  }
}


// ===== ASK QUESTION =====
sendBtn.onclick = async () => {
  if (!docId) {
    addMsg("assistant", "Upload a PDF first.");
    return;
  }

  const q = questionInput.value.trim();
  if (!q) return;

  addMsg("user", q);
  questionInput.value = "";
  evalBox.innerHTML = "";

  // Show typing indicator
  showTypingIndicator();

  try {
    const res = await fetch(`${API_BASE}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        doc_id: docId,
        question: q,
        evaluate: evalToggle.checked
      })
    });

    removeTypingIndicator();

    if (!res.ok) {
      const errMsg = await handleApiError(res, "Failed to get an answer.");
      addMsg("assistant", errMsg);
      return;
    }

    const data = await res.json();
    renderHistory(data.chat_history);

    if (data.evaluation && data.evaluation.helpfulness !== null) {
      evalBox.innerHTML = `
        <div class="evaluation-card">
          <div class="eval-title">AI Evaluation</div>
          ${renderEvalRow("Helpfulness", data.evaluation.helpfulness)}
          ${renderEvalRow("Completeness", data.evaluation.completeness)}
          ${renderEvalRow("Relevance", data.evaluation.relevance)}
          <div class="eval-reasoning">
            <strong>Reasoning</strong><br>${(data.evaluation.reasoning || "No reasoning provided.").replace(/\n/g, "<br>")}
          </div>
        </div>
      `;

      requestAnimationFrame(() => {
        document.querySelectorAll(".eval-bar-fill").forEach(bar => {
          bar.style.width = bar.dataset.target + "%";
        });
      });

    } else if (data.evaluation) {
      evalBox.textContent = JSON.stringify(data.evaluation, null, 2);
    } else {
      evalBox.textContent = "No evaluation returned.";
    }

  } catch (e) {
    removeTypingIndicator();
    addMsg("assistant", "Could not connect to the server. Is the backend running?");
    showToast("Connection error", "error");
    console.error(e);
  }
};


function renderEvalRow(label, score) {
  const percent = Math.max(0, Math.min(5, score)) * 20;
  return `
    <div class="eval-row">
      <div class="eval-label">${label}</div>
      <div class="eval-bar">
        <div class="eval-bar-fill" data-target="${percent}"></div>
      </div>
      <div class="eval-score">${score}/5</div>
    </div>
  `;
}

questionInput.addEventListener("keydown", e => {
  if (e.key === "Enter") sendBtn.onclick();
});


// ===== INIT =====
window.deleteDoc = deleteDoc;

loadDocuments();
updateEmptyStates();
