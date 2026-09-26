// ---------------------------------------------------------------------------
// Point this at your backend. Defaults to the local FastAPI dev server.
// ---------------------------------------------------------------------------
const API_BASE = "http://localhost:8000";

// ---------------------------------------------------------------------------
// Mobile menu
// ---------------------------------------------------------------------------
const burgerBtn = document.getElementById("burgerBtn");
const overlay = document.getElementById("menuOverlay");
const mobileMenu = document.getElementById("mobileMenu");

function openMenu() {
  burgerBtn.setAttribute("aria-expanded", "true");
  overlay.hidden = false;
  mobileMenu.hidden = false;
  document.body.classList.add("menu-open");
}
function closeMenu() {
  burgerBtn.setAttribute("aria-expanded", "false");
  overlay.hidden = true;
  mobileMenu.hidden = true;
  document.body.classList.remove("menu-open");
}
burgerBtn?.addEventListener("click", () => {
  burgerBtn.getAttribute("aria-expanded") === "true" ? closeMenu() : openMenu();
});
overlay?.addEventListener("click", closeMenu);
document.addEventListener("keydown", (e) => e.key === "Escape" && closeMenu());
mobileMenu?.querySelectorAll("a").forEach((a) => a.addEventListener("click", closeMenu));
window.addEventListener("resize", () => window.innerWidth > 720 && closeMenu());

// ---------------------------------------------------------------------------
// Stats count-up
// ---------------------------------------------------------------------------
function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

function countUp(el, target, { suffix = "", decimals = 0, duration = 1500, startOffset = 0 } = {}) {
  setTimeout(() => {
    const start = performance.now();
    function tick(now) {
      const p = Math.min((now - start) / duration, 1);
      const value = target * easeOutCubic(p);
      el.textContent = value.toFixed(decimals) + suffix;
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }, startOffset);
}

const statEls = document.querySelectorAll(".stat-value");
const statObserver = new IntersectionObserver(
  (entries, obs) => {
    entries.forEach((entry, i) => {
      if (!entry.isIntersecting) return;
      const el = entry.target;
      countUp(el, Number(el.dataset.target || 0), {
        suffix: el.dataset.suffix || "",
        decimals: Number(el.dataset.decimals || 0),
        duration: 1500 + i * 80,
        startOffset: 480 + i * 90,
      });
      obs.unobserve(el);
    });
  },
  { threshold: 0.25 }
);
statEls.forEach((el) => statObserver.observe(el));

// Pull live numbers from the backend once, then let the observer animate them.
async function loadStats() {
  try {
    const res = await fetch(`${API_BASE}/api/stats`);
    if (!res.ok) return;
    const data = await res.json();
    setTarget("statDocuments", data.documents);
    setTarget("statChunks", data.chunks);
    setTarget("statPages", data.pages);
  } catch {
    // Backend not running yet — the placeholder 0s stay as-is.
  }
}
function setTarget(id, value) {
  const el = document.getElementById(id);
  if (el) el.dataset.target = value;
}
loadStats();

// ---------------------------------------------------------------------------
// Upload
// ---------------------------------------------------------------------------
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const uploadStatus = document.getElementById("uploadStatus");
const docList = document.getElementById("docList");

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("keydown", (e) => (e.key === "Enter" || e.key === " ") && fileInput.click());
fileInput.addEventListener("change", () => fileInput.files[0] && handleUpload(fileInput.files[0]));

["dragenter", "dragover"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
  })
);
dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files?.[0];
  if (file) handleUpload(file);
});

async function handleUpload(file) {
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    uploadStatus.textContent = "Only PDF files are supported.";
    return;
  }
  uploadStatus.textContent = `Processing ${file.name}…`;
  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`${API_BASE}/api/upload`, { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed.");
    uploadStatus.textContent = `Indexed ${file.name} (${data.chunks} chunks, ${data.pages} pages).`;
    await refreshDocuments();
    await loadStats();
  } catch (err) {
    uploadStatus.textContent = `Error: ${err.message}`;
  } finally {
    fileInput.value = "";
  }
}

async function refreshDocuments() {
  try {
    const res = await fetch(`${API_BASE}/api/documents`);
    const docs = await res.json();
    docList.innerHTML = "";
    if (!docs.length) {
      docList.innerHTML = `<li class="doc-empty">No documents uploaded yet.</li>`;
      return;
    }
    docs.forEach((doc) => {
      const li = document.createElement("li");
      li.className = "doc-item";
      li.innerHTML = `
        <span>${doc.filename}<br><span class="doc-meta">${doc.chunks} chunks · ${doc.pages} pages</span></span>
        <button class="doc-remove" data-id="${doc.id}" aria-label="Remove document">✕</button>
      `;
      docList.appendChild(li);
    });
    docList.querySelectorAll(".doc-remove").forEach((btn) =>
      btn.addEventListener("click", async () => {
        await fetch(`${API_BASE}/api/documents/${btn.dataset.id}`, { method: "DELETE" });
        await refreshDocuments();
        await loadStats();
      })
    );
  } catch {
    // Backend not reachable yet.
  }
}
refreshDocuments();

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------
const chatWindow = document.getElementById("chatWindow");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");

function appendMessage(text, role, sources = []) {
  const div = document.createElement("div");
  div.className = `msg msg-${role}`;
  div.textContent = text;
  if (sources.length) {
    const src = document.createElement("div");
    src.className = "msg-sources";
    src.textContent = "Source: " + sources.map((s) => `${s.filename} (p.${s.page})`).join(", ");
    div.appendChild(src);
  }
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = chatInput.value.trim();
  if (!question) return;
  appendMessage(question, "user");
  chatInput.value = "";
  const sendBtn = chatForm.querySelector(".chat-send");
  sendBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Something went wrong.");
    appendMessage(data.answer, "bot", data.sources || []);
  } catch (err) {
    appendMessage(`Error: ${err.message}`, "bot");
  } finally {
    sendBtn.disabled = false;
  }
});
