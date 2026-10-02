/**
 * EcoClean Civic — Frontend Application Logic (Phase 5)
 * "Cleaner streets. Smarter civic response."
 */

const API = "/api";

// ── Application State ────────────────────────────────────────────────────────
let currentUser = null;
let reportMap = null;
let reportMarker = null;
let trackMap = null;
let trackMarkers = [];
let adminMap = null;
let adminMarkers = [];
let detailMap = null;
let severityChart = null;
let departmentChart = null;

// Default Map Center (Pune / Civic Default)
const DEFAULT_LAT = 18.5204;
const DEFAULT_LNG = 73.8567;

// Guided Reporting Wizard State
let wizardState = {
  step: 1,
  category: "Garbage Accumulation",
  lat: null,
  lng: null,
  address: "",
  landmark: "",
  details: "",
  imageFile: null,
  imagePreviewSrc: "",
};

// ── Toast Notification System ───────────────────────────────────────────────
function showToast(message, type = "info", duration = 3500) {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    document.body.appendChild(container);
  }

  const icons = { success: "✅", error: "❌", info: "ℹ️" };
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${icons[type] || "ℹ️"}</span><span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.25s ease-out";
    setTimeout(() => toast.remove(), 250);
  }, duration);
}

// ── Initialization ──────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  setupThemePreference();
  setupNavigation();
  setupAuth();
  setupWizard();
  setupTrackView();
  setupAdminDashboard();
  setupModals();

  await checkAuthStatus();
  initReportMap();
});

// ── Theme Preference ────────────────────────────────────────────────────────
function setupThemePreference() {
  const toggle = document.getElementById("theme-toggle");
  const savedTheme = localStorage.getItem("eco-clean-theme") || "dark";
  applyTheme(savedTheme);

  if (toggle) {
    toggle.addEventListener("click", () => {
      const nextTheme = document.body.classList.contains("theme-light") ? "dark" : "light";
      applyTheme(nextTheme);
      localStorage.setItem("eco-clean-theme", nextTheme);
    });
  }
}

function applyTheme(theme) {
  const isLight = theme === "light";
  const toggle = document.getElementById("theme-toggle");

  document.body.classList.toggle("theme-light", isLight);
  document.body.classList.toggle("theme-dark", !isLight);

  if (toggle) {
    const label = isLight ? "Dark" : "Light";
    toggle.setAttribute("aria-label", `Switch to ${label.toLowerCase()} mode`);
    toggle.querySelector(".theme-toggle-icon").textContent = isLight ? "🌙" : "☀️";
    toggle.querySelector(".theme-toggle-label").textContent = label;
  }
}

// ── Navigation & Tab System ─────────────────────────────────────────────────
function setupNavigation() {
  // Brand Logo click
  const logo = document.getElementById("brand-logo");
  if (logo) {
    logo.addEventListener("click", () => switchToTab("home"));
    logo.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") switchToTab("home");
    });
  }

  // Header Report CTA button
  const headerReportBtn = document.getElementById("header-report-btn");
  if (headerReportBtn) {
    headerReportBtn.addEventListener("click", () => {
      resetWizard();
      switchToTab("report");
    });
  }

  // Hero CTAs
  const heroReportBtn = document.getElementById("hero-report-btn");
  if (heroReportBtn) {
    heroReportBtn.addEventListener("click", () => {
      resetWizard();
      switchToTab("report");
    });
  }

  const heroTrackBtn = document.getElementById("hero-track-btn");
  if (heroTrackBtn) {
    heroTrackBtn.addEventListener("click", () => switchToTab("track"));
  }

  // Nav buttons
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tabId = btn.dataset.tab;
      switchToTab(tabId);
    });
  });
}

function switchToTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));

  const targetBtn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
  const targetPanel = document.getElementById(tabId);

  if (targetBtn) targetBtn.classList.add("active");
  if (targetPanel) {
    targetPanel.classList.add("active");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  if (tabId === "report") {
    setTimeout(() => { if (reportMap) reportMap.invalidateSize(); }, 250);
  } else if (tabId === "dashboard") {
    loadCitizenDashboard();
  } else if (tabId === "track") {
    loadTrackComplaints();
  } else if (tabId === "admin") {
    if (currentUser && currentUser.role === "admin") {
      loadAdminDashboard();
    }
  }
}

// ── Authentication & Role Management ────────────────────────────────────────
async function checkAuthStatus() {
  try {
    const res = await fetch(`${API}/auth/me`);
    const data = await res.json();
    currentUser = data.user;
    updateUserAuthUI();
  } catch (err) {
    currentUser = null;
    updateUserAuthUI();
  }
}

function updateUserAuthUI() {
  const authBar = document.getElementById("user-auth-bar");
  const dashNavBtn = document.getElementById("tab-nav-dashboard");
  const adminLockTag = document.getElementById("admin-lock-tag");
  const adminLockedView = document.getElementById("admin-locked-view");
  const adminUnlockedView = document.getElementById("admin-unlocked-view");
  const myComplaintsGroup = document.getElementById("my-complaints-group");

  if (currentUser) {
    authBar.innerHTML = `
      <div class="user-badge-pill">
        <span class="user-name">👤 ${currentUser.username}</span>
        <span class="user-role-badge ${currentUser.role}">${currentUser.role}</span>
        <button class="btn btn-sm btn-secondary" id="logout-btn" style="padding: 2px 8px; min-height: 28px;">Logout</button>
      </div>
    `;
    document.getElementById("logout-btn").addEventListener("click", handleLogout);

    if (dashNavBtn) dashNavBtn.classList.remove("hidden");

    if (currentUser.role === "admin") {
      adminLockTag.textContent = "🔓";
      adminLockedView.classList.add("hidden");
      adminUnlockedView.classList.remove("hidden");
    } else {
      adminLockTag.textContent = "🔒";
      adminLockedView.classList.remove("hidden");
      adminUnlockedView.classList.add("hidden");
    }

    if (myComplaintsGroup) myComplaintsGroup.classList.remove("hidden");
  } else {
    authBar.innerHTML = `
      <button class="btn btn-outline btn-sm" id="open-auth-btn" type="button">
        <span>🔑</span> Sign In
      </button>
    `;
    document.getElementById("open-auth-btn").addEventListener("click", () => openModal("auth-modal"));

    if (dashNavBtn) dashNavBtn.classList.add("hidden");
    adminLockTag.textContent = "🔒";
    adminLockedView.classList.remove("hidden");
    adminUnlockedView.classList.add("hidden");
    if (myComplaintsGroup) myComplaintsGroup.classList.add("hidden");
  }
}

function setupAuth() {
  const citizenTab = document.getElementById("auth-tab-citizen");
  const adminTab = document.getElementById("auth-tab-admin");
  const citizenForm = document.getElementById("auth-form-citizen");
  const adminForm = document.getElementById("auth-form-admin");

  citizenTab.addEventListener("click", () => {
    citizenTab.classList.add("active");
    adminTab.classList.remove("active");
    citizenForm.classList.remove("hidden");
    adminForm.classList.add("hidden");
  });

  adminTab.addEventListener("click", () => {
    adminTab.classList.add("active");
    citizenTab.classList.remove("active");
    adminForm.classList.remove("hidden");
    citizenForm.classList.add("hidden");
  });

  // Password visibility toggle
  const setupPwToggle = (btnId, inputId) => {
    const btn = document.getElementById(btnId);
    const input = document.getElementById(inputId);
    if (btn && input) {
      btn.addEventListener("click", () => {
        const isPassword = input.type === "password";
        input.type = isPassword ? "text" : "password";
        btn.textContent = isPassword ? "🙈" : "👁️";
      });
    }
  };
  setupPwToggle("toggle-pw-citizen", "citizen-password");
  setupPwToggle("toggle-pw-admin", "admin-password");

  // Toggle Register Mode for Citizen
  let isRegisterMode = false;
  const toggleBtn = document.getElementById("toggle-register-btn");
  const title = document.getElementById("citizen-auth-title");
  const citizenSubmitBtn = document.getElementById("citizen-submit-btn");
  const citizenIdentifierLabel = document.getElementById("citizen-identifier-label");
  const citizenIdentifierInput = document.getElementById("citizen-identifier");
  const citizenEmailGroup = document.getElementById("citizen-email-group");
  const citizenEmailInput = document.getElementById("citizen-email");

  if (toggleBtn) {
    toggleBtn.addEventListener("click", (e) => {
      e.preventDefault();
      isRegisterMode = !isRegisterMode;
      if (isRegisterMode) {
        title.textContent = "Citizen Registration";
        citizenSubmitBtn.textContent = "Create Citizen Account";
        toggleBtn.textContent = "Sign in here";
        citizenIdentifierLabel.textContent = "Choose Username";
        citizenIdentifierInput.placeholder = "e.g. priya_patil";
        citizenEmailGroup.style.display = "block";
        citizenEmailInput.required = true;
      } else {
        title.textContent = "Citizen Sign In";
        citizenSubmitBtn.textContent = "Sign In as Citizen";
        toggleBtn.textContent = "Register here";
        citizenIdentifierLabel.textContent = "Username or Email";
        citizenIdentifierInput.placeholder = "e.g. john_doe or citizen@civic.gov";
        citizenEmailGroup.style.display = "none";
        citizenEmailInput.required = false;
      }
    });
  }

  // Citizen Login/Register Form Submit
  document.getElementById("citizen-login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const identifier = citizenIdentifierInput.value.trim();
    const password = document.getElementById("citizen-password").value;

    const endpoint = isRegisterMode ? `${API}/auth/register` : `${API}/auth/login`;
    const payload = isRegisterMode
      ? { username: identifier, email: citizenEmailInput.value.trim(), password, role: "citizen" }
      : { identifier, password, role: "citizen" };

    citizenSubmitBtn.disabled = true;
    citizenSubmitBtn.textContent = "Verifying...";

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Authentication failed");

      currentUser = data.user;
      updateUserAuthUI();
      closeModal("auth-modal");
      showToast(`Signed in successfully as ${currentUser.username}!`, "success");
      switchToTab("dashboard");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      citizenSubmitBtn.disabled = false;
      citizenSubmitBtn.textContent = isRegisterMode ? "Create Citizen Account" : "Sign In as Citizen";
    }
  });

  // Admin Login Form Submit
  document.getElementById("admin-login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const identifier = document.getElementById("admin-identifier").value.trim();
    const password = document.getElementById("admin-password").value;
    const btn = e.target.querySelector("button[type='submit']");

    btn.disabled = true;
    btn.textContent = "Verifying...";

    try {
      const res = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, password, role: "admin" })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Admin authentication failed");

      currentUser = data.user;
      updateUserAuthUI();
      closeModal("auth-modal");
      showToast(`Welcome to Municipal Operations Center, ${currentUser.username}!`, "success");
      switchToTab("admin");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "Sign In to Admin Portal";
    }
  });

  // Demo Login Quick Action Buttons
  document.getElementById("demo-citizen-btn").addEventListener("click", () => handleDemoLogin("citizen"));
  document.getElementById("demo-admin-btn").addEventListener("click", () => handleDemoLogin("admin"));
  document.getElementById("admin-login-trigger-btn").addEventListener("click", () => {
    openModal("auth-modal");
    document.getElementById("auth-tab-admin").click();
  });
}

async function handleDemoLogin(role) {
  try {
    const res = await fetch(`${API}/auth/demo-login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Demo login failed");

    currentUser = data.user;
    updateUserAuthUI();
    closeModal("auth-modal");
    showToast(`Signed in as Demo ${currentUser.role} (${currentUser.username})`, "success");

    if (role === "admin") {
      switchToTab("admin");
    } else {
      switchToTab("dashboard");
    }
  } catch (err) {
    showToast(`Demo login error: ${err.message}`, "error");
  }
}

async function handleLogout() {
  await fetch(`${API}/auth/logout`, { method: "POST" });
  currentUser = null;
  updateUserAuthUI();
  showToast("Logged out successfully.", "info");
  switchToTab("home");
}

// ── Citizen Dashboard ───────────────────────────────────────────────────────
async function loadCitizenDashboard() {
  if (!currentUser) {
    switchToTab("home");
    openModal("auth-modal");
    return;
  }

  const welcome = document.getElementById("dashboard-welcome-msg");
  if (welcome) {
    welcome.textContent = `Welcome back, ${currentUser.username}. Here is the real-time status of your reported civic issues.`;
  }

  const refreshBtn = document.getElementById("dash-refresh-btn");
  if (refreshBtn) refreshBtn.disabled = true;

  try {
    const res = await fetch(`${API}/complaints?per_page=100`);
    if (!res.ok) throw new Error("Could not retrieve complaint records.");
    const data = await res.json();
    const complaints = data.items || [];

    // Compute Metrics
    const total = complaints.length;
    const active = complaints.filter(c => ["AI_PROCESSING", "VERIFIED", "ASSIGNED", "IN_PROGRESS"].includes(c.status)).length;
    const resolved = complaints.filter(c => ["RESOLVED", "CLOSED"].includes(c.status)).length;

    document.getElementById("dash-stat-total").textContent = total;
    document.getElementById("dash-stat-active").textContent = active;
    document.getElementById("dash-stat-resolved").textContent = resolved;

    // Render Active Complaints Cards
    const activeList = document.getElementById("dash-active-list");
    const activeComplaints = complaints.filter(c => !["RESOLVED", "CLOSED", "REJECTED"].includes(c.status));

    if (!activeComplaints.length) {
      activeList.innerHTML = `
        <div class="empty-state" style="grid-column: 1/-1;">
          <div class="empty-state-icon">🌱</div>
          <h4>No Active Issues</h4>
          <p>You have no pending complaints. Help keep our community clean by reporting any new waste accumulation.</p>
          <button class="btn btn-primary btn-sm" onclick="resetWizard(); switchToTab('report')">
            <span>📸</span> Report an Issue
          </button>
        </div>
      `;
    } else {
      activeList.innerHTML = activeComplaints.map(c => renderComplaintCardHTML(c)).join("");
    }

    // Render History Table
    const historyTbody = document.getElementById("dash-history-tbody");
    if (!complaints.length) {
      historyTbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 2rem;">No complaint history yet.</td></tr>`;
    } else {
      historyTbody.innerHTML = complaints.map(c => {
        const date = new Date(c.created_at).toLocaleDateString();
        const sev = c.severity ? c.severity.level : "PENDING";
        const sevClass = (sev || "low").toLowerCase();
        return `
          <tr>
            <td><strong>#${c.ticket_id}</strong></td>
            <td>${date}</td>
            <td>${c.address || "Location specified"}</td>
            <td><span class="badge badge-${sevClass}">${sev}</span></td>
            <td>${c.department || "Triage Pending"}</td>
            <td><span class="badge badge-${c.status === 'Resolved' ? 'resolved' : 'progress'}">${c.status}</span></td>
            <td>
              <button class="btn btn-secondary btn-sm" onclick="openComplaintDetail('${c.ticket_id}')">
                Inspect
              </button>
            </td>
          </tr>
        `;
      }).join("");
    }

  } catch (err) {
    showToast(err.message, "error");
  } finally {
    if (refreshBtn) refreshBtn.disabled = false;
  }
}

// ── Guided Reporting Wizard Logic ───────────────────────────────────────────
function setupWizard() {
  // Step 1: Category selection
  const catCards = document.querySelectorAll(".category-card");
  catCards.forEach(card => {
    const selectCard = () => {
      catCards.forEach(c => c.classList.remove("selected"));
      card.classList.add("selected");
      wizardState.category = card.dataset.category;
    };
    card.addEventListener("click", selectCard);
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") selectCard();
    });
  });

  // Step 1 -> Step 2
  document.getElementById("btn-next-step-1").addEventListener("click", () => {
    goToWizardStep(2);
  });

  // Step 2 -> Step 1
  document.getElementById("btn-prev-step-2").addEventListener("click", () => {
    goToWizardStep(1);
  });

  // Step 2 -> Step 3
  document.getElementById("btn-next-step-2").addEventListener("click", () => {
    const address = document.getElementById("address-input").value.trim();
    if (!address) {
      showToast("Please select a location on the map or click 'Detect My Location'.", "info");
      return;
    }
    wizardState.address = address;
    wizardState.lat = document.getElementById("lat-input").value;
    wizardState.lng = document.getElementById("lng-input").value;
    goToWizardStep(3);
  });

  // Step 3: Photo dropzone & camera
  const imageInput = document.getElementById("image-input");
  const dropzone = document.getElementById("dropzone");
  const dropzoneContent = document.getElementById("dropzone-content");
  const previewContainer = document.getElementById("image-preview-container");
  const previewImg = document.getElementById("image-preview");
  const removeBtn = document.getElementById("remove-img-btn");

  imageInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      handleImageSelection(e.target.files[0]);
    }
  });

  removeBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    wizardState.imageFile = null;
    wizardState.imagePreviewSrc = "";
    imageInput.value = "";
    previewImg.src = "";
    previewContainer.classList.add("hidden");
    dropzoneContent.classList.remove("hidden");
  });

  // Drag-and-drop
  ["dragenter", "dragover"].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
  });
  ["dragleave", "drop"].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => { e.preventDefault(); dropzone.classList.remove("dragover"); });
  });
  dropzone.addEventListener("drop", (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleImageSelection(e.dataTransfer.files[0]);
    }
  });

  function handleImageSelection(file) {
    if (!file.type.startsWith("image/")) {
      showToast("Please upload an image file (JPG, PNG, or WEBP).", "error");
      return;
    }
    if (file.size > 16 * 1024 * 1024) {
      showToast("Image size must be less than 16MB.", "error");
      return;
    }

    wizardState.imageFile = file;
    const reader = new FileReader();
    reader.onload = (evt) => {
      wizardState.imagePreviewSrc = evt.target.result;
      previewImg.src = evt.target.result;
      dropzoneContent.classList.add("hidden");
      previewContainer.classList.remove("hidden");
    };
    reader.readAsDataURL(file);
  }

  // Step 3 -> Step 2
  document.getElementById("btn-prev-step-3").addEventListener("click", () => {
    goToWizardStep(2);
  });

  // Step 3 -> Step 4
  document.getElementById("btn-next-step-3").addEventListener("click", () => {
    if (!wizardState.imageFile) {
      showToast("Please upload a photo of the waste issue.", "info");
      return;
    }
    goToWizardStep(4);
  });

  // Step 4 -> Step 3
  document.getElementById("btn-prev-step-4").addEventListener("click", () => {
    goToWizardStep(3);
  });

  // Step 4 -> Step 5 (Review)
  document.getElementById("btn-next-step-4").addEventListener("click", () => {
    wizardState.landmark = document.getElementById("landmark-input").value.trim();
    wizardState.details = document.getElementById("details-input").value.trim();

    // Populate Review Step
    document.getElementById("rev-category").textContent = wizardState.category;
    document.getElementById("rev-address").textContent = wizardState.address;
    document.getElementById("rev-landmark").textContent = wizardState.landmark || "None provided";
    document.getElementById("rev-photo-thumb").src = wizardState.imagePreviewSrc;

    goToWizardStep(5);
  });

  // Step 5 -> Step 4
  document.getElementById("btn-prev-step-5").addEventListener("click", () => {
    goToWizardStep(4);
  });

  // Step 5: Final Submission -> Step 6 (AI Processing with SSE)
  document.getElementById("wizard-form").addEventListener("submit", handleWizardSubmission);

  // Address search and GPS buttons
  document.getElementById("use-location-btn").addEventListener("click", detectUserLocation);
  document.getElementById("search-address-btn").addEventListener("click", searchAddressQuery);
}

function goToWizardStep(stepNum) {
  wizardState.step = stepNum;

  // Update Stepper Nodes
  document.querySelectorAll(".wizard-step-node").forEach(node => {
    const nodeStep = parseInt(node.dataset.step);
    node.classList.remove("active", "completed");
    if (nodeStep === stepNum) {
      node.classList.add("active");
    } else if (nodeStep < stepNum) {
      node.classList.add("completed");
    }
  });

  // Show Active Pane
  document.querySelectorAll(".wizard-step-pane").forEach(pane => pane.classList.remove("active"));
  const activePane = document.getElementById(`pane-step-${stepNum}`);
  if (activePane) activePane.classList.add("active");

  if (stepNum === 2 && reportMap) {
    setTimeout(() => reportMap.invalidateSize(), 250);
  }
}

function resetWizard() {
  wizardState.step = 1;
  wizardState.category = "Garbage Accumulation";
  wizardState.imageFile = null;
  wizardState.imagePreviewSrc = "";

  document.querySelectorAll(".category-card").forEach((c, idx) => {
    c.classList.toggle("selected", idx === 0);
  });

  const previewContainer = document.getElementById("image-preview-container");
  const dropzoneContent = document.getElementById("dropzone-content");
  if (previewContainer && dropzoneContent) {
    previewContainer.classList.add("hidden");
    dropzoneContent.classList.remove("hidden");
  }

  const uploadResult = document.getElementById("upload-result");
  if (uploadResult) {
    uploadResult.classList.add("hidden");
    uploadResult.innerHTML = "";
  }

  const wizardForm = document.getElementById("wizard-form");
  if (wizardForm) wizardForm.classList.remove("hidden");

  goToWizardStep(1);
}

// ── Location & Map Handling ─────────────────────────────────────────────────
function initReportMap() {
  const container = document.getElementById("report-map");
  if (!container || reportMap) return;

  reportMap = L.map("report-map").setView([DEFAULT_LAT, DEFAULT_LNG], 13);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors"
  }).addTo(reportMap);

  reportMarker = L.marker([DEFAULT_LAT, DEFAULT_LNG], { draggable: true }).addTo(reportMap);
  updateLocation(DEFAULT_LAT, DEFAULT_LNG, false);

  reportMap.on("click", (e) => {
    const { lat, lng } = e.latlng;
    reportMarker.setLatLng([lat, lng]);
    updateLocation(lat, lng, true);
  });

  reportMarker.on("dragend", (e) => {
    const { lat, lng } = e.target.getLatLng();
    updateLocation(lat, lng, true);
  });
}

async function updateLocation(lat, lng, fetchAddress = true) {
  document.getElementById("lat-input").value = lat.toFixed(6);
  document.getElementById("lng-input").value = lng.toFixed(6);

  if (fetchAddress) {
    document.getElementById("address-input").value = "Fetching street address...";
    try {
      const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`);
      const data = await res.json();
      if (data && data.display_name) {
        document.getElementById("address-input").value = data.display_name;
      } else {
        document.getElementById("address-input").value = `Coordinates: ${lat.toFixed(4)}, ${lng.toFixed(4)}`;
      }
    } catch (_) {
      document.getElementById("address-input").value = `Location: ${lat.toFixed(4)}, ${lng.toFixed(4)}`;
    }
  } else {
    document.getElementById("address-input").value = "Central Municipal District, City Center";
  }
}

function detectUserLocation() {
  if (!navigator.geolocation) {
    showToast("Geolocation is not supported by your browser.", "error");
    return;
  }

  const btn = document.getElementById("use-location-btn");
  btn.disabled = true;
  btn.innerHTML = `<span>⏳ Detecting...</span>`;

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const lat = pos.coords.latitude;
      const lng = pos.coords.longitude;
      reportMap.setView([lat, lng], 16);
      reportMarker.setLatLng([lat, lng]);
      updateLocation(lat, lng, true);
      btn.disabled = false;
      btn.innerHTML = `<span>📍</span> Detect My Location`;
      showToast("Current location detected!", "success");
    },
    () => {
      btn.disabled = false;
      btn.innerHTML = `<span>📍</span> Detect My Location`;
      showToast("Could not retrieve GPS location. Please click directly on the map.", "info");
    }
  );
}

async function searchAddressQuery() {
  const query = document.getElementById("address-search-input").value.trim();
  if (!query) return;

  const btn = document.getElementById("search-address-btn");
  btn.disabled = true;
  btn.textContent = "Searching...";

  try {
    const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}`);
    const results = await res.json();
    if (results && results.length > 0) {
      const first = results[0];
      const lat = parseFloat(first.lat);
      const lng = parseFloat(first.lon);

      reportMap.setView([lat, lng], 15);
      reportMarker.setLatLng([lat, lng]);
      document.getElementById("address-input").value = first.display_name;
      document.getElementById("lat-input").value = lat.toFixed(6);
      document.getElementById("lng-input").value = lng.toFixed(6);
      showToast("Location found!", "success");
    } else {
      showToast("Location not found. Try clicking directly on the map.", "info");
    }
  } catch (_) {
    showToast("Error searching address.", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Search";
  }
}

// ── Wizard Submission & Real-Time SSE Processing (Step 6) ───────────────────
async function handleWizardSubmission(e) {
  e.preventDefault();

  if (!currentUser) {
    showToast("Please sign in or register to submit your report.", "info");
    openModal("auth-modal");
    return;
  }

  const submitBtn = document.getElementById("submit-btn");
  const wizardForm = document.getElementById("wizard-form");
  const resultCard = document.getElementById("upload-result");

  submitBtn.disabled = true;
  submitBtn.innerHTML = `<span>⏳ Submitting...</span>`;

  // Build FormData
  const formData = new FormData();
  formData.append("image", wizardState.imageFile);

  let finalAddress = wizardState.address;
  if (wizardState.landmark) {
    finalAddress += ` (Landmark: ${wizardState.landmark})`;
  }
  if (wizardState.details) {
    finalAddress += ` [Notes: ${wizardState.details}]`;
  }
  formData.append("address", finalAddress);

  if (wizardState.lat) formData.append("latitude", wizardState.lat);
  if (wizardState.lng) formData.append("longitude", wizardState.lng);

  try {
    const res = await fetch(`${API}/complaints/upload`, {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Submission failed");

    // Hide form and show live processing timeline
    wizardForm.classList.add("hidden");
    resultCard.classList.remove("hidden");

    renderLiveTimeline(data);
    startRealtimeSSE(data);

  } catch (err) {
    showToast(err.message, "error");
    submitBtn.disabled = false;
    submitBtn.innerHTML = `🚀 Submit Report to Municipal Team`;
  }
}

function renderLiveTimeline(data) {
  const resultCard = document.getElementById("upload-result");
  const isRealAI = data.ai_mode === "REAL_YOLO";
  const aiBadge = isRealAI
    ? `<span class="badge" style="background: rgba(5, 150, 105, 0.2); color: #10b981; border: 1px solid #10b981;">🤖 REAL AI / YOLOv8</span>`
    : `<span class="badge" style="background: rgba(217, 119, 6, 0.2); color: #f59e0b; border: 1px solid #f59e0b;">⚠️ DEMO / MOCK AI</span>`;

  resultCard.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 1.5rem;">
      <div>
        <h3 style="font-size: 1.35rem; margin-bottom: 0.2rem;">Report Registered — Ticket #${data.ticket_id}</h3>
        <p style="color: var(--text-muted); font-size: 0.85rem;">Submitted on ${new Date().toLocaleTimeString()} • ${wizardState.category}</p>
      </div>
      <div>${aiBadge}</div>
    </div>

    <!-- TIMELINE STEPPER -->
    <ul class="timeline-stepper">
      <li class="timeline-step completed" id="tl-step-submitted">
        <div class="timeline-dot">✓</div>
        <div>
          <strong>Report Registered</strong>
          <span style="display: block; font-size: 0.8rem; color: var(--text-muted);">Securely saved in municipal database</span>
        </div>
      </li>
      <li class="timeline-step active" id="tl-step-analyzing">
        <div class="timeline-dot">●</div>
        <div>
          <strong>Analyzing Image (YOLOv8)</strong>
          <span style="display: block; font-size: 0.8rem; color: var(--text-muted);" id="tl-analyzing-desc">Scanning visual evidence for waste items</span>
        </div>
      </li>
      <li class="timeline-step" id="tl-step-severity">
        <div class="timeline-dot">○</div>
        <div>
          <strong>Calculating Overlap Severity</strong>
          <span style="display: block; font-size: 0.8rem; color: var(--text-muted);">Computing union area and frame coverage ratio</span>
        </div>
      </li>
      <li class="timeline-step" id="tl-step-duplicate">
        <div class="timeline-dot">○</div>
        <div>
          <strong>Proximity Duplicate Check</strong>
          <span style="display: block; font-size: 0.8rem; color: var(--text-muted);">Scanning 50m radius for existing open complaints</span>
        </div>
      </li>
      <li class="timeline-step" id="tl-step-department">
        <div class="timeline-dot">○</div>
        <div>
          <strong>Assigning Municipal Department</strong>
          <span style="display: block; font-size: 0.8rem; color: var(--text-muted);">Routing to Sanitation, Recycling, or Public Works</span>
        </div>
      </li>
      <li class="timeline-step" id="tl-step-completed">
        <div class="timeline-dot">○</div>
        <div>
          <strong>Verification Complete</strong>
          <span style="display: block; font-size: 0.8rem; color: var(--text-muted);" id="tl-final-desc">Awaiting triage completion</span>
        </div>
      </li>
    </ul>

    <!-- FINAL VERIFIED RESULT DISPLAY (Revealed on Completion) -->
    <div id="tl-result-box" class="civic-card hidden" style="margin-top: 1.5rem; background: var(--bg-surface-elevated);"></div>
  `;
}

function startRealtimeSSE(complaintData) {
  const ticketId = complaintData.ticket_id;
  let eventSource = null;
  let fallbackTimer = null;
  let isClosed = false;

  const cleanup = () => {
    if (isClosed) return;
    isClosed = true;
    if (eventSource) {
      try { eventSource.close(); } catch (_) {}
      eventSource = null;
    }
    if (fallbackTimer) {
      clearInterval(fallbackTimer);
      fallbackTimer = null;
    }
  };

  const setStepState = (stepId, state) => {
    const el = document.getElementById(stepId);
    if (!el) return;
    el.classList.remove("active", "completed", "failed");
    el.classList.add(state);
    const dot = el.querySelector(".timeline-dot");
    if (dot) {
      dot.textContent = state === "completed" ? "✓" : state === "failed" ? "✕" : state === "active" ? "●" : "○";
    }
  };

  const updateTimelineStage = (stage) => {
    if (stage === "ANALYZING_IMAGE") {
      setStepState("tl-step-submitted", "completed");
      setStepState("tl-step-analyzing", "active");
    } else if (stage === "CALCULATING_SEVERITY") {
      setStepState("tl-step-submitted", "completed");
      setStepState("tl-step-analyzing", "completed");
      setStepState("tl-step-severity", "active");
    } else if (stage === "CHECKING_DUPLICATES") {
      setStepState("tl-step-submitted", "completed");
      setStepState("tl-step-analyzing", "completed");
      setStepState("tl-step-severity", "completed");
      setStepState("tl-step-duplicate", "active");
    } else if (stage === "ASSIGNING_DEPARTMENT") {
      setStepState("tl-step-submitted", "completed");
      setStepState("tl-step-analyzing", "completed");
      setStepState("tl-step-severity", "completed");
      setStepState("tl-step-duplicate", "completed");
      setStepState("tl-step-department", "active");
    }
  };

  const showFinalSuccess = (finalData) => {
    cleanup();
    ["tl-step-submitted", "tl-step-analyzing", "tl-step-severity", "tl-step-duplicate", "tl-step-department", "tl-step-completed"].forEach(id => {
      setStepState(id, "completed");
    });

    const resultBox = document.getElementById("tl-result-box");
    if (resultBox) {
      const sev = finalData.severity ? (finalData.severity.level || finalData.severity) : "Standard";
      const sevClass = (sev || "low").toLowerCase();
      const isDuplicate = finalData.is_duplicate;

      resultBox.classList.remove("hidden");
      resultBox.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 1rem;">
          <div style="display: flex; align-items: center; gap: 0.75rem;">
            <span style="font-size: 1.8rem;">🎉</span>
            <div>
              <h4 style="font-size: 1.15rem; color: var(--civic-emerald); margin: 0;">Verified & Routed to ${finalData.department || "Municipal Operations"}</h4>
              <span style="font-size: 0.85rem; color: var(--text-muted);">${finalData.progress_message || "AI Verification completed successfully"}</span>
            </div>
          </div>
          <span class="badge badge-${sevClass}" style="font-size: 0.85rem; padding: 0.35rem 0.75rem;">${sev} Severity</span>
        </div>

        ${isDuplicate ? `<div class="badge badge-open" style="margin-bottom: 1rem;">⚠️ Linked to duplicate incident #${finalData.duplicate_of_id}</div>` : ''}

        <p style="font-size: 0.88rem; color: var(--text-secondary); margin-bottom: 1.25rem;">
          Your report has been verified. Sanitation field units have been notified and assigned to this location.
        </p>

        <div style="display: flex; gap: 0.75rem; flex-wrap: wrap;">
          <button class="btn btn-primary btn-sm" onclick="openComplaintDetail('${ticketId}')">
            🔍 Inspect AI Bounding Boxes
          </button>
          <button class="btn btn-secondary btn-sm" onclick="switchToTab('dashboard')">
            Go to My Dashboard →
          </button>
          <button class="btn btn-outline btn-sm" onclick="resetWizard(); goToWizardStep(1)">
            + Report Another Issue
          </button>
        </div>
      `;
    }

    showToast(`Ticket #${ticketId} verified successfully!`, "success");
  };

  const showFinalFailure = (errorMsg) => {
    cleanup();
    setStepState("tl-step-completed", "failed");
    const finalDesc = document.getElementById("tl-final-desc");
    if (finalDesc) finalDesc.textContent = errorMsg || "AI processing could not be completed.";

    const resultBox = document.getElementById("tl-result-box");
    if (resultBox) {
      resultBox.classList.remove("hidden");
      resultBox.innerHTML = `
        <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;">
          <span style="font-size: 1.75rem;">❌</span>
          <div>
            <h4 style="font-size: 1.05rem; color: var(--civic-red); margin: 0;">Processing Encountered an Issue</h4>
            <span style="font-size: 0.85rem; color: var(--text-muted);">${errorMsg || "Image analysis failed."}</span>
          </div>
        </div>
        <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 1rem;">
          The report is saved in our database. Our municipal team will manually inspect the image.
        </p>
        <button class="btn btn-secondary btn-sm" onclick="switchToTab('dashboard')">
          View in My Dashboard
        </button>
      `;
    }

    showToast(`Processing issue for #${ticketId}`, "error");
  };

  // Fallback Polling Mechanism
  const startFallbackPolling = () => {
    if (fallbackTimer || isClosed) return;
    console.info(`[RealTime] Activating fallback polling for ticket #${ticketId}`);
    let tries = 0;
    fallbackTimer = setInterval(async () => {
      tries++;
      if (tries > 25 || isClosed) {
        cleanup();
        return;
      }
      try {
        const res = await fetch(`${API}/complaints/${ticketId}`);
        if (res.ok) {
          const latest = await res.json();
          if (latest.status !== "AI_PROCESSING") {
            if (latest.status === "PROCESSING_FAILED") {
              showFinalFailure(latest.processing_error);
            } else {
              showFinalSuccess(latest);
            }
          } else {
            updateTimelineStage(latest.processing_status);
          }
        }
      } catch (_) {}
    }, 2500);
  };

  // Server-Sent Events (SSE) Connection
  if (window.EventSource) {
    try {
      eventSource = new EventSource(`${API}/complaints/${ticketId}/events`);

      const handleEventMessage = (payload) => {
        if (payload.stage) updateTimelineStage(payload.stage);
        if (payload.processing_status) updateTimelineStage(payload.processing_status);

        if (payload.event === "processing_completed" || ["VERIFIED", "DUPLICATE"].includes(payload.status)) {
          showFinalSuccess(payload);
        } else if (payload.event === "processing_failed" || payload.status === "PROCESSING_FAILED" || payload.processing_status === "FAILED") {
          showFinalFailure(payload.error || payload.progress_message);
        }
      };

      eventSource.addEventListener("complaint_status", (e) => {
        try { handleEventMessage(JSON.parse(e.data)); } catch (_) {}
      });
      eventSource.addEventListener("processing_stage_changed", (e) => {
        try { handleEventMessage(JSON.parse(e.data)); } catch (_) {}
      });
      eventSource.addEventListener("processing_completed", (e) => {
        try { handleEventMessage(JSON.parse(e.data)); } catch (_) {}
      });
      eventSource.addEventListener("processing_failed", (e) => {
        try { handleEventMessage(JSON.parse(e.data)); } catch (_) {}
      });

      eventSource.onerror = () => {
        if (eventSource) {
          try { eventSource.close(); } catch (_) {}
          eventSource = null;
        }
        startFallbackPolling();
      };
    } catch (_) {
      startFallbackPolling();
    }
  } else {
    startFallbackPolling();
  }
}

// ── Public Tracking View ────────────────────────────────────────────────────
function setupTrackView() {
  const cardsBtn = document.getElementById("view-cards-btn");
  const mapBtn = document.getElementById("view-map-btn");
  const cardsContainer = document.getElementById("cards-view-container");
  const mapContainer = document.getElementById("map-view-container");

  cardsBtn.addEventListener("click", () => {
    cardsBtn.classList.add("active");
    mapBtn.classList.remove("active");
    cardsContainer.classList.remove("hidden");
    mapContainer.classList.add("hidden");
  });

  mapBtn.addEventListener("click", () => {
    mapBtn.classList.add("active");
    cardsBtn.classList.remove("active");
    mapContainer.classList.remove("hidden");
    cardsContainer.classList.add("hidden");
    setTimeout(() => initTrackMap(), 200);
  });

  document.getElementById("refresh-track-btn").addEventListener("click", loadTrackComplaints);
  document.getElementById("filter-status").addEventListener("change", loadTrackComplaints);
  document.getElementById("filter-department").addEventListener("change", loadTrackComplaints);
  document.getElementById("filter-severity").addEventListener("change", loadTrackComplaints);
  document.getElementById("filter-my-complaints").addEventListener("change", loadTrackComplaints);
}

async function loadTrackComplaints() {
  const status = document.getElementById("filter-status").value;
  const department = document.getElementById("filter-department").value;
  const severity = document.getElementById("filter-severity").value;
  const myComplaints = document.getElementById("filter-my-complaints").checked;

  const params = new URLSearchParams();
  if (status) params.append("status", status);
  if (department) params.append("department", department);
  if (severity) params.append("severity", severity);
  if (myComplaints) params.append("my_complaints", "true");

  try {
    const res = await fetch(`${API}/complaints?${params.toString()}`);
    if (res.status === 401) {
      document.getElementById("complaint-list").innerHTML = `
        <div class="empty-state" style="grid-column: 1/-1;">
          <div class="empty-state-icon">🔒</div>
          <h4>Sign In to Track Reports</h4>
          <p>Please sign in or register to follow your municipal reports and inspect live progress.</p>
          <button class="btn btn-primary btn-sm" onclick="openModal('auth-modal')">Sign In / Register</button>
        </div>
      `;
      return;
    }

    const data = await res.json();
    const complaints = Array.isArray(data) ? data : (data.items || []);

    renderComplaintsCards(complaints);
    updateTrackMapMarkers(complaints);
  } catch (err) {
    console.error("Error loading complaints:", err);
  }
}

function renderComplaintCardHTML(c) {
  const date = new Date(c.created_at).toLocaleDateString();
  const statusClass = c.status === "Resolved" ? "badge-resolved" : c.status === "In Progress" ? "badge-progress" : "badge-open";
  const thumbSrc = c.annotated_image_path ? `/uploads/${c.annotated_image_path}` : `/uploads/${c.image_path}`;
  const isRealAI = c.ai_mode === "REAL_YOLO";
  const aiBadge = isRealAI
    ? `<span class="badge" style="background: rgba(5, 150, 105, 0.15); color: #10b981; font-size: 0.65rem;">REAL YOLOv8</span>`
    : `<span class="badge" style="background: rgba(217, 119, 6, 0.15); color: #f59e0b; font-size: 0.65rem;">DEMO AI</span>`;

  const sevLevel = c.severity ? c.severity.level : "PENDING";
  const sevCount = c.severity ? c.severity.item_count : 0;

  return `
    <div class="complaint-card">
      <div class="card-header-row">
        <div style="display: flex; align-items: center; gap: 0.4rem;">
          <span class="ticket-id">#${c.ticket_id}</span>
          ${aiBadge}
        </div>
        <span class="badge ${statusClass}">${c.status}</span>
      </div>
      <div style="position: relative;">
        <img src="${thumbSrc}" class="card-img-thumb" alt="Waste photo" loading="lazy" />
        <span style="position: absolute; bottom: 8px; right: 8px; background: rgba(0,0,0,0.8); color: #fff; font-size: 0.68rem; padding: 2px 6px; border-radius: 4px;">
          ${sevLevel} Severity (${sevCount} items)
        </span>
      </div>
      <div class="card-body-info">
        <div><strong>📌 Location:</strong> ${c.address || "Street location"}</div>
        <div><strong>🏛️ Routed:</strong> ${c.department || "Municipal Operations"}</div>
        <div><strong>🕒 Reported:</strong> ${date}</div>
      </div>
      <div class="card-footer-row">
        <span style="font-size: 0.75rem; color: var(--text-muted);">By: ${c.submitted_by}</span>
        <button class="btn btn-secondary btn-sm" onclick="openComplaintDetail('${c.ticket_id}')">
          Inspect Details
        </button>
      </div>
    </div>
  `;
}

function renderComplaintsCards(complaints) {
  const list = document.getElementById("complaint-list");
  if (!complaints.length) {
    list.innerHTML = `
      <div class="empty-state" style="grid-column: 1/-1;">
        <div class="empty-state-icon">🔍</div>
        <h4>No Reports Found</h4>
        <p>No complaints matched your selected status or department filters.</p>
      </div>
    `;
    return;
  }
  list.innerHTML = complaints.map(c => renderComplaintCardHTML(c)).join("");
}

function initTrackMap() {
  if (trackMap) {
    trackMap.invalidateSize();
    return;
  }
  trackMap = L.map("track-map").setView([DEFAULT_LAT, DEFAULT_LNG], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors"
  }).addTo(trackMap);
}

function updateTrackMapMarkers(complaints) {
  if (!trackMap) return;
  trackMarkers.forEach(m => trackMap.removeLayer(m));
  trackMarkers = [];

  complaints.forEach(c => {
    if (c.latitude && c.longitude) {
      const marker = L.marker([c.latitude, c.longitude])
        .addTo(trackMap)
        .bindPopup(`
          <strong>Ticket #${c.ticket_id}</strong><br/>
          Status: <b>${c.status}</b><br/>
          Dept: ${c.department}<br/>
          <button class="btn btn-sm btn-primary" style="margin-top: 4px; padding: 2px 6px;" onclick="openComplaintDetail('${c.ticket_id}')">View</button>
        `);
      trackMarkers.push(marker);
    }
  });
}

// ── Complaint Detail & Lifecycle Inspection Modal ───────────────────────────
async function openComplaintDetail(ticketId) {
  try {
    const res = await fetch(`${API}/complaints/${ticketId}`);
    if (!res.ok) throw new Error("Could not load complaint details.");
    const c = await res.json();

    const modalContent = document.getElementById("detail-modal-content");
    const date = new Date(c.created_at).toLocaleString();
    const isRealAI = c.ai_mode === "REAL_YOLO";
    const hasAnnotated = !!c.annotated_image_path;
    const annotatedSrc = `/uploads/${c.annotated_image_path}`;
    const originalSrc = `/uploads/${c.image_path}`;

    // Lifecycle Stepper calculation
    const allStages = ["SUBMITTED", "AI_PROCESSING", "VERIFIED", "ASSIGNED", "IN_PROGRESS", "RESOLVED"];
    const currentStatus = (c.status || "").toUpperCase();
    const activeIdx = allStages.indexOf(currentStatus) >= 0 ? allStages.indexOf(currentStatus) : 2;

    modalContent.innerHTML = `
      <div style="margin-bottom: 1.25rem; display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 0.5rem;">
        <div>
          <div style="display: flex; align-items: center; gap: 0.6rem;">
            <h3 style="font-size: 1.35rem; margin: 0;">Ticket #${c.ticket_id}</h3>
            <span class="badge ${c.status === 'Resolved' ? 'badge-resolved' : 'badge-progress'}">${c.status}</span>
          </div>
          <p style="color: var(--text-muted); font-size: 0.82rem; margin-top: 0.35rem;">
            Reported on ${date} by <strong>${c.submitted_by}</strong>
          </p>
        </div>
        <span class="badge badge-${(c.severity.level || 'low').toLowerCase()}" style="font-size: 0.85rem; padding: 0.35rem 0.75rem;">
          ${c.severity.level} Severity (${c.severity.item_count} items)
        </span>
      </div>

      <!-- LIFECYCLE PROGRESS STEPPER -->
      <div class="civic-card" style="margin-bottom: 1.25rem; padding: 0.85rem 1.25rem; background: var(--bg-surface-elevated);">
        <div style="font-size: 0.75rem; text-transform: uppercase; font-weight: 700; color: var(--text-muted); margin-bottom: 0.65rem;">
          Verified Lifecycle Progress:
        </div>
        <div style="display: flex; justify-content: space-between; position: relative;">
          ${allStages.map((st, i) => {
            const isDone = i <= activeIdx;
            const isCurrent = i === activeIdx;
            const col = isCurrent ? "var(--civic-blue)" : isDone ? "var(--civic-emerald)" : "var(--text-muted)";
            return `
              <div style="text-align: center; flex: 1;">
                <div style="width: 22px; height: 22px; border-radius: 50%; background: ${col}; color: #fff; margin: 0 auto 4px; display: flex; align-items: center; justify-content: center; font-size: 0.7rem; font-weight: 800;">
                  ${isDone ? '✓' : (i + 1)}
                </div>
                <span style="font-size: 0.68rem; font-weight: 600; color: ${col};">${st}</span>
              </div>
            `;
          }).join("")}
        </div>
      </div>

      <div class="detail-grid">
        <div>
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <span style="font-size: 0.85rem; font-weight: 600;">Visual Evidence Inspection</span>
            ${hasAnnotated ? `
            <div style="display: flex; gap: 0.35rem;">
              <button type="button" class="btn btn-sm btn-primary active" id="btn-toggle-boxes" onclick="toggleModalImageView('annotated')">🎯 AI Bounding Boxes</button>
              <button type="button" class="btn btn-sm btn-outline" id="btn-toggle-orig" onclick="toggleModalImageView('original')">📷 Original Photo</button>
            </div>
            ` : ''}
          </div>

          <div style="border-radius: var(--radius-md); overflow: hidden; background: #000; border: 1px solid var(--border-color); text-align: center; min-height: 220px; display: flex; align-items: center; justify-content: center;">
            <img id="detail-modal-img" src="${hasAnnotated ? annotatedSrc : originalSrc}" data-annotated="${annotatedSrc}" data-original="${originalSrc}" alt="Complaint inspection" style="max-width: 100%; max-height: 340px; object-fit: contain;" />
          </div>

          <!-- DETECTED ITEMS -->
          <div class="civic-card" style="margin-top: 1rem; padding: 0.85rem;">
            <h4 style="font-size: 0.85rem; margin-bottom: 0.5rem;">🔍 Classified Waste Items (${c.detections ? c.detections.length : 0})</h4>
            <div style="display: flex; flex-wrap: wrap; gap: 0.4rem;">
              ${c.detections && c.detections.length > 0 
                ? c.detections.map(d => `<span class="badge badge-low">🏷️ <strong>${d.class}</strong> (${(d.confidence * 100).toFixed(0)}%)</span>`).join("")
                : `<span style="color: var(--text-muted); font-size: 0.85rem;">No individual bounding boxes identified</span>`
              }
            </div>
          </div>
        </div>

        <div>
          <div class="civic-card" style="padding: 1rem; margin-bottom: 1rem;">
            <p style="margin-bottom: 0.4rem;">📌 <strong>Address:</strong> ${c.address}</p>
            <p style="margin-bottom: 0.4rem;">🏛️ <strong>Dispatched:</strong> <strong>${c.department}</strong></p>
            <p style="margin-bottom: 0.4rem;">📊 <strong>Frame Area:</strong> ${((c.severity.coverage_ratio || 0) * 100).toFixed(1)}% of photo</p>
            ${c.is_duplicate ? `<p style="color: var(--civic-amber); font-size: 0.82rem; margin-top: 0.5rem;">⚠️ Proximity duplicate linked to Ticket #${c.duplicate_of_id}</p>` : ''}
          </div>
          <div id="detail-map" class="interactive-map" style="height: 220px;"></div>
        </div>
      </div>
    `;

    openModal("complaint-detail-modal");

    setTimeout(() => {
      if (detailMap) detailMap.remove();
      if (c.latitude && c.longitude) {
        detailMap = L.map("detail-map").setView([c.latitude, c.longitude], 15);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(detailMap);
        L.marker([c.latitude, c.longitude]).addTo(detailMap).bindPopup(c.address).openPopup();
      }
    }, 250);

  } catch (err) {
    showToast(err.message, "error");
  }
}

function toggleModalImageView(viewType) {
  const img = document.getElementById("detail-modal-img");
  const btnBoxes = document.getElementById("btn-toggle-boxes");
  const btnOrig = document.getElementById("btn-toggle-orig");
  if (!img) return;

  if (viewType === "annotated") {
    img.src = img.dataset.annotated;
    if (btnBoxes) btnBoxes.classList.add("active");
    if (btnOrig) btnOrig.classList.remove("active");
  } else {
    img.src = img.dataset.original;
    if (btnOrig) btnOrig.classList.add("active");
    if (btnBoxes) btnBoxes.classList.remove("active");
  }
}

// ── Admin Dashboard (Preserved for Phase 6) ──────────────────────────────────
function setupAdminDashboard() {
  document.getElementById("refresh-admin-btn").addEventListener("click", loadAdminDashboard);
  document.getElementById("admin-filter-department").addEventListener("change", loadAdminDashboard);
}

async function loadAdminDashboard() {
  if (!currentUser || currentUser.role !== "admin") return;

  try {
    const statsRes = await fetch(`${API}/analytics/stats`);
    if (statsRes.ok) {
      const stats = await statsRes.json();
      document.getElementById("stat-total").textContent = stats.total_complaints || 0;
      document.getElementById("stat-open").textContent = stats.open_complaints || 0;
      document.getElementById("stat-resolved").textContent = stats.resolved_complaints || 0;
      document.getElementById("stat-high").textContent = stats.high_severity || 0;
      renderAdminCharts(stats);
    }

    const deptFilter = document.getElementById("admin-filter-department").value;
    const complaintsRes = await fetch(`${API}/complaints?per_page=100${deptFilter ? `&department=${encodeURIComponent(deptFilter)}` : ''}`);
    if (complaintsRes.ok) {
      const data = await complaintsRes.json();
      const complaints = data.items || [];
      renderAdminTable(complaints);
      renderAdminMap(complaints);
    }
  } catch (err) {
    console.error("Error loading admin dashboard:", err);
  }
}

function renderAdminCharts(stats) {
  const sevCtx = document.getElementById("severity-chart");
  const deptCtx = document.getElementById("department-chart");

  if (sevCtx) {
    if (severityChart) severityChart.destroy();
    severityChart = new Chart(sevCtx, {
      type: "doughnut",
      data: {
        labels: ["High", "Medium", "Low"],
        datasets: [{
          data: [
            stats.severity_breakdown?.High || 0,
            stats.severity_breakdown?.Medium || 0,
            stats.severity_breakdown?.Low || 0,
          ],
          backgroundColor: ["#ef4444", "#f59e0b", "#10b981"]
        }]
      },
      options: { responsive: true, maintainAspectRatio: false }
    });
  }

  if (deptCtx) {
    if (departmentChart) departmentChart.destroy();
    const deptLabels = Object.keys(stats.department_breakdown || {});
    const deptData = Object.values(stats.department_breakdown || {});
    departmentChart = new Chart(deptCtx, {
      type: "bar",
      data: {
        labels: deptLabels,
        datasets: [{
          label: "Assigned Incidents",
          data: deptData,
          backgroundColor: "#3b82f6"
        }]
      },
      options: { responsive: true, maintainAspectRatio: false }
    });
  }
}

function renderAdminMap(complaints) {
  if (!adminMap) {
    adminMap = L.map("admin-map").setView([DEFAULT_LAT, DEFAULT_LNG], 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(adminMap);
  } else {
    adminMap.invalidateSize();
  }

  adminMarkers.forEach(m => adminMap.removeLayer(m));
  adminMarkers = [];

  complaints.forEach(c => {
    if (c.latitude && c.longitude) {
      const m = L.circleMarker([c.latitude, c.longitude], {
        radius: 8,
        fillColor: c.severity.level === "High" ? "#ef4444" : "#f59e0b",
        color: "#fff",
        weight: 1,
        fillOpacity: 0.8
      }).addTo(adminMap).bindPopup(`<strong>#${c.ticket_id}</strong><br/>${c.address}`);
      adminMarkers.push(m);
    }
  });
}

function renderAdminTable(complaints) {
  const tbody = document.querySelector("#admin-table tbody");
  if (!tbody) return;

  tbody.innerHTML = complaints.map(c => `
    <tr>
      <td><strong>#${c.ticket_id}</strong></td>
      <td>${new Date(c.created_at).toLocaleDateString()}</td>
      <td>${c.submitted_by}</td>
      <td>${c.address}</td>
      <td><span class="badge badge-${(c.severity.level || 'low').toLowerCase()}">${c.severity.level}</span></td>
      <td>${c.department}</td>
      <td>
        <select onchange="updateTicketStatus('${c.ticket_id}', this.value)" style="padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; background: var(--bg-input); color: var(--text-primary); border: 1px solid var(--border-color);">
          <option value="Open" ${c.status === 'Open' ? 'selected' : ''}>Open</option>
          <option value="In Progress" ${c.status === 'In Progress' ? 'selected' : ''}>In Progress</option>
          <option value="Resolved" ${c.status === 'Resolved' ? 'selected' : ''}>Resolved</option>
        </select>
      </td>
      <td>
        <button class="btn btn-sm btn-secondary" onclick="openComplaintDetail('${c.ticket_id}')">Inspect</button>
      </td>
    </tr>
  `).join("");
}

async function updateTicketStatus(ticketId, newStatus) {
  try {
    const res = await fetch(`${API}/complaints/${ticketId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus })
    });
    if (!res.ok) throw new Error("Could not update ticket status.");
    showToast(`Ticket #${ticketId} status updated to ${newStatus}`, "success");
    loadAdminDashboard();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ── Modal Utilities ─────────────────────────────────────────────────────────
function setupModals() {
  document.getElementById("close-auth-modal").addEventListener("click", () => closeModal("auth-modal"));
  document.getElementById("close-detail-modal").addEventListener("click", () => closeModal("complaint-detail-modal"));

  window.addEventListener("click", (e) => {
    if (e.target.classList.contains("modal-overlay")) {
      e.target.classList.add("hidden");
    }
  });

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      document.querySelectorAll(".modal-overlay").forEach(m => m.classList.add("hidden"));
    }
  });
}

function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove("hidden");
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add("hidden");
}
