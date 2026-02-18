const API_BASE = window.location.port === "3000" ? "http://127.0.0.1:8000" : "/api";

// ===== AUTH STATE =====
let authToken = localStorage.getItem("legalai_token") || sessionStorage.getItem("legalai_token");
let currentUser = JSON.parse(localStorage.getItem("legalai_user") || sessionStorage.getItem("legalai_user") || "null");

function requireAuth() {
  if (!authToken) {
    window.location.href = "/login";
    return false;
  }
  return true;
}

function getAuthHeaders() {
  return {
    "Authorization": `Bearer ${authToken}`,
    "Content-Type": "application/json"
  };
}

function getAuthHeadersRaw() {
  return {
    "Authorization": `Bearer ${authToken}`
  };
}

function logout() {
  localStorage.removeItem("legalai_token");
  localStorage.removeItem("legalai_user");
  sessionStorage.removeItem("legalai_token");
  sessionStorage.removeItem("legalai_user");
  window.location.href = "/login";
}

// Validate token on load
async function validateToken() {
  if (!authToken) return requireAuth();

  try {
    const res = await fetch(`${API_BASE}/me`, {
      headers: getAuthHeadersRaw()
    });
    if (!res.ok) {
      logout();
      return;
    }
    const data = await res.json();
    currentUser = data;

    // Update whichever storage is being used
    if (localStorage.getItem("legalai_token")) {
      localStorage.setItem("legalai_user", JSON.stringify(data));
    } else {
      sessionStorage.setItem("legalai_user", JSON.stringify(data));
    }

    updateUserUI();
  } catch {
    // If backend is down, still allow cached user data
    if (currentUser) {
      updateUserUI();
    } else {
      logout();
    }
  }
}

function updateUserUI() {
  const userNameEl = document.getElementById("userName");
  const userAvatarEl = document.getElementById("userAvatar");
  if (currentUser && userNameEl) {
    userNameEl.textContent = currentUser.display_name || currentUser.email;
    if (userAvatarEl) {
      const initials = (currentUser.display_name || currentUser.email || "U")
        .split(" ")
        .map(w => w[0])
        .join("")
        .substring(0, 2)
        .toUpperCase();
      userAvatarEl.textContent = initials;
    }
  }
}

// Check auth immediately
if (!requireAuth()) {
  // Stop execution — redirect happening
} else {
  // Continue app initialization
  initApp();
}

function initApp() {
  let docId = null;
  let currentDocFullText = null;
  let selectedFile = null;


  // Initialize User UI
  updateUserUI();
  validateToken();

  // Logout Listener
  const logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", logout);
  }

  // ===== TOAST NOTIFICATIONS =====
  // ===== TOAST NOTIFICATIONS =====
  function showToast(message, type = "info", duration = 4500) {
    let container = document.getElementById("toastContainer");

    // Create container if it doesn't exist (e.g. in index.html)
    if (!container) {
      container = document.createElement("div");
      container.id = "toastContainer";
      container.className = "toast-container";
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;

    const icons = {
      success: "✓",
      error: "✕",
      info: "ℹ",
      warning: "⚠"
    };

    toast.innerHTML = `<div class="toast-icon">${icons[type] || "ℹ"}</div> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.classList.add("toast-exiting");
      toast.addEventListener("animationend", () => toast.remove());
    }, duration);
  }


  // ===== ERROR HANDLING HELPER =====
  async function handleApiError(res, fallbackMsg) {
    // Handle 401 globally
    if (res.status === 401) {
      showToast("Session expired. Redirecting to login...", "warning");
      setTimeout(() => logout(), 1500);
      return "Session expired";
    }

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
      const msg = errorData.detail || errorData.message || "AI service temporarily unavailable. Please try again in a moment.";
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

  // ================= AUTHENTICATION =================

  const loginForm = document.getElementById("loginForm");
  const registerForm = document.getElementById("registerForm");
  const authError = document.getElementById("authError");
  const loginToggle = document.getElementById("loginToggle");
  const registerToggle = document.getElementById("registerToggle");
  const toggleSlider = document.getElementById("toggleSlider");

  // New Elements
  const forgotPasswordLink = document.getElementById("forgotPasswordLink");
  const forgotPasswordView = document.getElementById("forgotPasswordView");
  const backToLoginBtn = document.getElementById("backToLogin");
  const cancelResetBtn = document.getElementById("cancelReset");
  const authToggleContainer = document.getElementById("authToggle");

  // Forgot Password Forms
  const forgotStep1Form = document.getElementById("forgotStep1Form");
  const forgotStep2Form = document.getElementById("forgotStep2Form");

  let isLoginMode = true;

  function switchAuthMode(mode) {
    if (forgotPasswordView.style.display !== "none") {
      forgotPasswordView.style.display = "none";
      authToggleContainer.style.display = "flex";
    }

    hideError();
    isLoginMode = mode === "login";

    if (isLoginMode) {
      loginToggle.classList.add("active");
      registerToggle.classList.remove("active");
      toggleSlider.style.transform = "translateX(0)";
      loginForm.style.display = "flex";
      registerForm.style.display = "none";
    } else {
      registerToggle.classList.add("active");
      loginToggle.classList.remove("active");
      toggleSlider.style.transform = "translateX(100%)";
      loginForm.style.display = "none";
      registerForm.style.display = "flex";
    }
  }

  // Helper to safely stringify error details
  function getErrorMessage(data, fallback) {
    if (!data) return fallback;
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      // Pydantic validation error
      return data.detail.map(e => `${e.loc[1]}: ${e.msg}`).join(", ");
    }
    if (typeof data.detail === "object") return JSON.stringify(data.detail);
    return data.message || fallback;
  }

  // Only add listeners if elements exist (simple check for login page)
  // We wrap this in a function to be called after DOM load if needed, 
  // though script is at bottom of body so it should be fine.
  if (loginToggle) {
    console.log("Initializing Auth Listeners..."); // Debug

    loginToggle.addEventListener("click", () => switchAuthMode("login"));
    registerToggle.addEventListener("click", () => switchAuthMode("register"));

    if (forgotPasswordLink) {
      forgotPasswordLink.addEventListener("click", (e) => {
        console.log("Forgot Password Clicked"); // Debug
        e.preventDefault();
        hideError();
        loginForm.style.display = "none";
        registerForm.style.display = "none";
        authToggleContainer.style.display = "none";
        forgotPasswordView.style.display = "block";

        forgotStep1Form.style.display = "flex";
        forgotStep2Form.style.display = "none";
        document.getElementById("forgotEmail").value = "";
        document.getElementById("forgotAnswer").value = "";
        document.getElementById("newPassword").value = "";
      });
    } else {
      console.error("Forgot Password Link not found in DOM");
    }

    if (backToLoginBtn) backToLoginBtn.addEventListener("click", closeForgotView);
    if (cancelResetBtn) cancelResetBtn.addEventListener("click", closeForgotView);

    // Forgot Password Step 1: Get Question
    if (forgotStep1Form) {
      forgotStep1Form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("forgotEmail").value.trim();
        const btn = document.getElementById("forgotStep1Submit");

        if (!email) return showError("Please enter your email");

        hideError();
        setLoading(btn, true);

        try {
          const res = await fetch(`${API_BASE}/auth/question`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email })
          });

          const data = await res.json();
          if (!res.ok) {
            throw new Error(getErrorMessage(data, "Email not found"));
          }

          document.getElementById("securityQuestionDisplay").textContent = data.question;

          forgotStep1Form.style.display = "none";
          forgotStep2Form.style.display = "flex";
          setLoading(btn, false); // Reset button state

        } catch (err) {
          showError(err.message);
          setLoading(btn, false);
        }
      });
    }

    // Forgot Password Step 2: Reset Password
    if (forgotStep2Form) {
      forgotStep2Form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("forgotEmail").value.trim();
        const answer = document.getElementById("forgotAnswer").value.trim();
        const newPassword = document.getElementById("newPassword").value;
        const btn = document.getElementById("forgotStep2Submit");

        if (!answer || !newPassword) return showError("Please fill all fields");
        if (newPassword.length < 6) return showError("Password must be at least 6 characters");

        hideError();
        setLoading(btn, true);

        try {
          const res = await fetch(`${API_BASE}/auth/reset-password`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email,
              security_answer: answer,
              new_password: newPassword
            })
          });

          const data = await res.json();
          if (!res.ok) {
            throw new Error(getErrorMessage(data, "Failed to reset password"));
          }

          showSuccessOverlay("Password Reset!", "You can now login with your new password.");
          setTimeout(() => {
            window.location.reload();
          }, 2000);

        } catch (err) {
          showError(err.message);
          setLoading(btn, false);
        }
      });
    }
  }

  function closeForgotView() {
    forgotPasswordView.style.display = "none";
    authToggleContainer.style.display = "flex";
    switchAuthMode("login");
  }

  // Prevent default browser validation bubbles
  document.querySelectorAll('input, select').forEach(input => {
    input.addEventListener('invalid', (e) => {
      e.preventDefault();
      // focus the first invalid input
      if (e.target.form.querySelector(':invalid') === e.target) {
        showError(e.target.validationMessage);
        e.target.focus();
      }
    });
  });

  if (registerForm) {
    registerForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("registerName").value.trim();
      const email = document.getElementById("registerEmail").value.trim();
      const password = document.getElementById("registerPassword").value;
      const question = document.getElementById("registerQuestion").value;
      const answer = document.getElementById("registerAnswer").value.trim();

      const btn = document.getElementById("registerSubmit");

      // Custom validation check
      if (password.length < 6) {
        showError("Password must be at least 6 characters");
        return;
      }

      if (!question) {
        showError("Please select a security question");
        return;
      }

      hideError();
      setLoading(btn, true);

      try {
        const res = await fetch(`${API_BASE}/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email,
            password,
            display_name: name,
            security_question: question,
            security_answer: answer
          })
        });

        const data = await res.json();

        if (!res.ok) {
          throw new Error(getErrorMessage(data, "Registration failed"));
        }

        localStorage.setItem("legalai_token", data.token);
        localStorage.setItem("legalai_user", JSON.stringify(data.user));

        showSuccessOverlay(`Welcome, ${data.user.display_name}!`, "Setting up your workspace...");

        setTimeout(() => window.location.href = "/", 2000);

      } catch (err) {
        showError(err.message);
        setLoading(btn, false);
      }
    });
  }



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
  const sidebarOverlay = document.getElementById("sidebarOverlay");

  // Empty state refs
  const summaryEmpty = document.getElementById("summaryEmpty");
  const jsonEmpty = document.getElementById("jsonEmpty");
  const suggestEmpty = document.getElementById("suggestEmpty");


  // ===== UPLOAD MODAL =====
  function openUploadModal() {
    uploadOverlay.classList.add("show");
    if (window.innerWidth <= 768) {
      sidebar.classList.remove("mobile-open");
      sidebarOverlay.classList.remove("active");
    }
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
  function toggleSidebar() {
    const isMobile = window.innerWidth <= 768;
    if (isMobile) {
      sidebar.classList.toggle("mobile-open");
      sidebarOverlay.classList.toggle("active");
      sidebar.classList.remove("collapsed");
    } else {
      sidebar.classList.toggle("collapsed");
    }
  }

  sidebarToggle.addEventListener("click", toggleSidebar);

  document.getElementById("sidebarCloseMobile")?.addEventListener("click", toggleSidebar);

  sidebarOverlay.addEventListener("click", () => {
    if (sidebar.classList.contains("mobile-open")) {
      toggleSidebar();
    }
  });

  // ===== MOBILE VIEW TOGGLE =====
  const viewChatBtn = document.getElementById("viewChat");
  const viewInfoBtn = document.getElementById("viewInfo");
  const mainWrapper = document.querySelector(".main-wrapper");

  if (viewChatBtn && viewInfoBtn) {
    viewChatBtn.addEventListener("click", () => {
      mainWrapper.classList.remove("show-info");
      viewChatBtn.classList.add("active");
      viewInfoBtn.classList.remove("active");
    });

    viewInfoBtn.addEventListener("click", () => {
      mainWrapper.classList.add("show-info");
      viewInfoBtn.classList.add("active");
      viewChatBtn.classList.remove("active");
    });
  }


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
      const res = await fetch(`${API_BASE}/documents`, {
        headers: getAuthHeadersRaw()
      });

      if (res.status === 401) return logout();

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
      const res = await fetch(`${API_BASE}/documents/${id}`, {
        headers: getAuthHeadersRaw()
      });

      if (res.status === 401) return logout();

      const data = await res.json();

      docId = data.doc_id;

      document.querySelectorAll(".sidebar-item").forEach(el => {
        el.classList.toggle("active", el.dataset.id === docId);
      });

      jsonBox.textContent = JSON.stringify(data.structured, null, 2);

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
        sidebarOverlay.classList.remove("active");
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
      await fetch(`${API_BASE}/documents/${id}`, {
        method: "DELETE",
        headers: getAuthHeadersRaw()
      });

      if (docId === id) {
        docId = null;
        currentDocFullText = null;
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

    uploadBtn.style.display = "none";
    uploadProgress.style.display = "block";
    uploadStatus.textContent = "Uploading & analyzing...";

    const form = new FormData();
    form.append("file", selectedFile);

    try {
      const res = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        headers: getAuthHeadersRaw(),
        body: form
      });
      if (!res.ok) {
        if (res.status === 401) return logout();
        const errMsg = await handleApiError(res, "Upload failed.");
        uploadStatus.textContent = errMsg;
        uploadProgress.style.display = "none";
        uploadBtn.style.display = "flex";
        return;
      }

      const data = await res.json();

      docId = data.doc_id;
      currentDocFullText = data.full_text || null;

      uploadStatus.textContent = `✓ Uploaded: ${data.filename} (${data.pages} pages)`;
      jsonBox.textContent = JSON.stringify(data.structured, null, 2);
      summaryBox.innerHTML = "";

      loadDocuments();
      fetchSuggestions(docId);

      fileName.textContent = "";
      uploadBtn.style.display = "none";
      uploadProgress.style.display = "none";
      pdfInput.value = "";
      closeUploadModal();
      updateEmptyStates();

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
        headers: getAuthHeaders(),
        body: JSON.stringify({
          doc_id: docId,
          full_text: currentDocFullText
        })
      });

      if (!res.ok) {
        if (res.status === 401) return logout();
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
        headers: getAuthHeaders(),
        body: JSON.stringify({
          doc_id: id,
          full_text: currentDocFullText
        })
      });

      if (res.status === 401) return logout();

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

    showTypingIndicator();

    try {
      const res = await fetch(`${API_BASE}/ask`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          doc_id: docId,
          question: q,
          evaluate: evalToggle.checked,
          full_text: currentDocFullText
        })
      });

      removeTypingIndicator();

      if (!res.ok) {
        if (res.status === 401) return logout();
        const errMsg = await handleApiError(res, "Failed to get an answer.");
        addMsg("assistant", errMsg);
        return;
      }

      const data = await res.json();

      if ((!data.chat_history || data.chat_history.length === 0) && data.answer) {
        addMsg("assistant", data.answer);
      } else {
        renderHistory(data.chat_history);
      }

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

      // Show source context used by AI
      if (data.context) {
        const sourcesDiv = document.createElement("div");
        sourcesDiv.className = "sources-card";
        sourcesDiv.innerHTML = `
          <button class="sources-toggle" onclick="this.parentElement.classList.toggle('expanded')">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style="vertical-align: -2px; margin-right: 6px;">
              <path d="M4 2C2.5 2 2 3 2 4v2c0 1-1 1-1 1s1 0 1 1v2c0 1 .5 2 2 2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
              <path d="M10 2c1.5 0 2 1 2 2v2c0 1 1 1 1 1s-1 0-1 1v2c0 1-.5 2-2 2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
            </svg>
            Source Text Used by AI
            <span class="sources-arrow">▼</span>
          </button>
          <div class="sources-content">
            <pre class="sources-pre">${data.context.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
          </div>
        `;
        evalBox.appendChild(sourcesDiv);
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


  // ===== LOGOUT BUTTON =====
  document.getElementById("logoutBtn")?.addEventListener("click", logout);


  // ===== INIT =====
  window.deleteDoc = deleteDoc;

  validateToken();
  loadDocuments();
  updateEmptyStates();
}
