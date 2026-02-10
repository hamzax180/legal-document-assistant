// Docker/K8s compatibility: Use relative path /api in production (Nginx proxy),
// but keep http://127.0.0.1:8000 for local dev (port 3000).
const API_BASE = window.location.port === "3000" ? "http://127.0.0.1:8000" : "/api";

let docId = null;

// DOM Elements
const pdfInput = document.getElementById("pdfInput");
const uploadBtn = document.getElementById("uploadBtn");
const uploadStatus = document.getElementById("uploadStatus");
const jsonBox = document.getElementById("jsonBox");
const uploadZone = document.getElementById("uploadZone");
const fileName = document.getElementById("fileName");
const uploadOverlay = document.getElementById("uploadOverlay");
const uploadModalClose = document.getElementById("uploadModalClose");
const miniUploadZone = document.getElementById("miniUploadZone");

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
  // Desktop toggle
  sidebar.classList.toggle("collapsed");
  // Mobile toggle
  sidebar.classList.toggle("mobile-open");
});


// ===== PANEL TABS =====
document.querySelectorAll(".panel-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    const target = tab.dataset.tab;

    // Switch active tab
    document.querySelectorAll(".panel-tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");

    // Switch content
    document.querySelectorAll(".tab-content").forEach(tc => tc.classList.remove("active"));
    document.getElementById(`tab-${target}`).classList.add("active");
  });
});


// ===== UPLOAD ZONE: Click & Drag =====
uploadZone.addEventListener("click", () => pdfInput.click());

uploadZone.addEventListener("dragover", e => {
  e.preventDefault();
  uploadZone.classList.add("drag-over");
});

uploadZone.addEventListener("dragleave", () => {
  uploadZone.classList.remove("drag-over");
});

uploadZone.addEventListener("drop", e => {
  e.preventDefault();
  uploadZone.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file && file.name.toLowerCase().endsWith(".pdf")) {
    pdfInput.files = e.dataTransfer.files;
    showSelectedFile(file.name);
  }
});

pdfInput.addEventListener("change", () => {
  if (pdfInput.files[0]) {
    showSelectedFile(pdfInput.files[0].name);
  }
});

function showSelectedFile(name) {
  fileName.textContent = name;
  uploadBtn.style.display = "block";
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
      docList.innerHTML = '<div class="sidebar-empty">No documents yet.<br>Upload a PDF to get started.</div>';
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
          <div class="chat-welcome-icon">💬</div>
          <h3>Ask anything about your document</h3>
          <p>Start asking questions about <strong>${data.filename}</strong>.</p>
        </div>
      `;
    }

    // Reset summary
    summaryBox.innerHTML = "";

    // Reset eval
    evalBox.innerHTML = "";

    // Load suggested questions
    fetchSuggestions(docId);

    uploadStatus.textContent = `Loaded: ${data.filename} (${data.pages} pages)`;

    // Update empty states
    updateEmptyStates();

    // Close sidebar on mobile
    if (window.innerWidth <= 768) {
      sidebar.classList.remove("mobile-open");
    }

  } catch (err) {
    console.error("Failed to load document:", err);
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
          <div class="chat-welcome-icon">💬</div>
          <h3>Ask anything about your document</h3>
          <p>Upload a legal PDF and start asking questions.<br>The AI will analyze and respond using context from your document.</p>
        </div>
      `;
      evalBox.innerHTML = "";
      uploadStatus.textContent = "";
      updateEmptyStates();
    }

    loadDocuments();
  } catch (err) {
    console.error("Failed to delete document:", err);
  }
}


// ===== CHAT HELPERS =====
function addMsg(role, text) {
  // Remove welcome message if present
  const welcome = chatBox.querySelector(".chat-welcome");
  if (welcome) welcome.remove();

  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.innerHTML = `<strong>${role === "user" ? "You" : "Assistant"}:</strong><br>${text}`;
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function renderHistory(history) {
  chatBox.innerHTML = "";
  history.forEach(m => {
    addMsg("user", m.user);
    addMsg("assistant", m.assistant);
  });
}


// ===== UPLOAD =====
uploadBtn.onclick = async () => {
  const file = pdfInput.files[0];
  if (!file) return;

  uploadStatus.textContent = "Uploading & analyzing...";
  chatBox.innerHTML = "";
  jsonBox.textContent = "";
  evalBox.innerHTML = "";
  summaryBox.innerHTML = "";

  const form = new FormData();
  form.append("file", file);

  try {
    const res = await fetch(`${API_BASE}/upload`, { method: "POST", body: form });
    const data = await res.json();

    docId = data.doc_id;
    uploadStatus.textContent = `Uploaded: ${data.filename} (${data.pages} pages)`;

    jsonBox.textContent = JSON.stringify(data.structured, null, 2);

    summaryBox.innerHTML = "";

    // Refresh sidebar
    loadDocuments();

    // Fetch suggested questions
    fetchSuggestions(docId);

    // Reset upload zone
    fileName.textContent = "";
    uploadBtn.style.display = "none";
    pdfInput.value = "";

    // Close upload modal
    closeUploadModal();

    // Update empty states
    updateEmptyStates();

    // Switch to JSON tab to show results
    document.querySelector('.panel-tab[data-tab="json"]').click();

    // Set welcome message in chat
    chatBox.innerHTML = `
      <div class="chat-welcome">
        <div class="chat-welcome-icon">💬</div>
        <h3>Document ready!</h3>
        <p>Ask anything about <strong>${data.filename}</strong>.</p>
      </div>
    `;

  } catch (err) {
    uploadStatus.textContent = "Upload failed.";
    console.error(err);
  }
};


// ===== SUMMARIZE =====
summarizeBtn.onclick = async () => {
  if (!docId) return;

  summaryBox.innerHTML = '<div class="summary-loading">⏳ Generating summary...</div>';
  if (summaryEmpty) summaryEmpty.style.display = "none";

  try {
    const res = await fetch(`${API_BASE}/summarize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id: docId })
    });

    const data = await res.json();
    summaryBox.innerHTML = data.summary.replace(/\n/g, "<br>");
    updateEmptyStates();
  } catch (err) {
    summaryBox.innerHTML = "Failed to generate summary.";
    console.error(err);
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
        chip.style.animationDelay = `${i * 0.08}s`;
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
    addMsg("assistant", "Error contacting backend.");
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
loadDocuments();
updateEmptyStates();
