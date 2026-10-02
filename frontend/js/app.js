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

// ============================================================================
// PHASE 6 — MUNICIPAL OPERATIONS CENTER (ADMIN UX)
// Professional, map-oriented, operational control surface
// ============================================================================

let adminActiveView = "overview";
let adminComplaintsPage = 1;
let adminComplaintsPerPage = 20;
let adminComplaintsTotalPages = 1;
let adminOpsMap = null;
let adminOpsMarkers = [];
let adminAnalyticsDays = 7;
let adminSSE = null;
let chartTimeline = null;
let chartSeverity = null;
let chartDepartment = null;
let chartOutcomes = null;

function setupAdminDashboard() {
  // Navigation tabs within Admin Center
  const navBtns = document.querySelectorAll(".admin-nav-btn");
  navBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const view = btn.dataset.adminView;
      if (view) switchAdminView(view);
    });
  });

  // Top action buttons
  const refreshAllBtn = document.getElementById("admin-refresh-all-btn");
  if (refreshAllBtn) {
    refreshAllBtn.addEventListener("click", () => {
      loadAdminOverview();
      if (adminActiveView === "complaints") loadAdminComplaints();
      else if (adminActiveView === "processing") loadAdminProcessingQueue();
      else if (adminActiveView === "map") loadAdminIncidentMap();
      else if (adminActiveView === "departments") loadAdminDepartments();
      else if (adminActiveView === "analytics") loadAdminAnalytics();
      else if (adminActiveView === "users") loadAdminUsers();
      else if (adminActiveView === "system") loadAdminSystemHealth();
      showToast("Municipal Operations Center refreshed.", "info", 2000);
    });
  }

  // Complaints filter listeners
  const searchInput = document.getElementById("admin-search-input");
  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        adminComplaintsPage = 1;
        loadAdminComplaints();
      }, 350);
    });
  }

  ["admin-filter-status", "admin-filter-severity", "admin-filter-dept", "admin-filter-aimode"].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("change", () => {
        adminComplaintsPage = 1;
        loadAdminComplaints();
      });
    }
  });

  // Pagination controls
  const prevBtn = document.getElementById("admin-page-prev");
  const nextBtn = document.getElementById("admin-page-next");
  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      if (adminComplaintsPage > 1) {
        adminComplaintsPage--;
        loadAdminComplaints();
      }
    });
  }
  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      if (adminComplaintsPage < adminComplaintsTotalPages) {
        adminComplaintsPage++;
        loadAdminComplaints();
      }
    });
  }

  // Processing queue controls
  const procFilter = document.getElementById("admin-proc-filter");
  if (procFilter) procFilter.addEventListener("change", loadAdminProcessingQueue);
  const procRefresh = document.getElementById("admin-refresh-proc-btn");
  if (procRefresh) procRefresh.addEventListener("click", loadAdminProcessingQueue);

  // Map controls
  const mapDept = document.getElementById("admin-map-filter-dept");
  const mapSev = document.getElementById("admin-map-filter-sev");
  const mapReload = document.getElementById("admin-map-reload-btn");
  if (mapDept) mapDept.addEventListener("change", loadAdminIncidentMap);
  if (mapSev) mapSev.addEventListener("change", loadAdminIncidentMap);
  if (mapReload) mapReload.addEventListener("click", loadAdminIncidentMap);

  // Analytics time pills
  const timePills = document.querySelectorAll(".time-pill-btn");
  timePills.forEach(pill => {
    pill.addEventListener("click", () => {
      timePills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      adminAnalyticsDays = parseInt(pill.dataset.days, 10) || 7;
      loadAdminAnalytics();
    });
  });

  // Users refresh button
  const usersRefresh = document.getElementById("admin-refresh-users-btn");
  if (usersRefresh) usersRefresh.addEventListener("click", loadAdminUsers);

  // Admin incident modal close button
  const closeAdminModal = document.getElementById("close-admin-modal");
  if (closeAdminModal) {
    closeAdminModal.addEventListener("click", () => closeModal("admin-detail-modal"));
  }
}

function switchAdminView(viewId) {
  adminActiveView = viewId;

  // Toggle active button
  document.querySelectorAll(".admin-nav-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.adminView === viewId);
  });

  // Toggle view panes
  document.querySelectorAll(".admin-view-pane").forEach(pane => {
    pane.classList.toggle("hidden", pane.id !== `admin-view-${viewId}`);
  });

  // Trigger relevant loader
  if (viewId === "overview") loadAdminOverview();
  else if (viewId === "complaints") loadAdminComplaints();
  else if (viewId === "processing") loadAdminProcessingQueue();
  else if (viewId === "map") loadAdminIncidentMap();
  else if (viewId === "departments") loadAdminDepartments();
  else if (viewId === "analytics") loadAdminAnalytics();
  else if (viewId === "users") loadAdminUsers();
  else if (viewId === "system") loadAdminSystemHealth();
}

// Backward-compatible entrypoint for tab switching
function loadAdminDashboard() {
  if (!currentUser || currentUser.role !== "admin") return;
  const userDisplay = document.getElementById("admin-user-display");
  if (userDisplay) {
    userDisplay.textContent = `Admin: ${currentUser.username} (${currentUser.email || 'Municipal Ops'})`;
  }
  initAdminSSE();
  switchAdminView(adminActiveView);
}

// ── 1. Admin Overview ───────────────────────────────────────────────────────
async function loadAdminOverview() {
  try {
    const res = await fetch(`${API}/admin/overview`);
    if (!res.ok) throw new Error("Could not retrieve admin overview metrics.");
    const data = await res.json();
    const c = data.counts || {};

    // Update 8 Top Metrics
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val !== undefined ? val : 0;
    };

    setVal("adm-stat-total", c.total);
    setVal("adm-stat-submitted", c.submitted);
    setVal("adm-stat-processing", c.ai_processing);
    setVal("adm-stat-high", c.high_severity);
    setVal("adm-stat-verified", c.verified);
    setVal("adm-stat-inprogress", c.in_progress);
    setVal("adm-stat-resolved", c.resolved);
    setVal("adm-stat-failed", c.processing_failed);

    // Update Nav Badges
    const badgeActive = document.getElementById("admin-count-complaints");
    if (badgeActive) {
      const activeTotal = (c.submitted || 0) + (c.ai_processing || 0) + (c.verified || 0) + (c.assigned || 0) + (c.in_progress || 0);
      badgeActive.textContent = activeTotal;
    }
    const badgeFailed = document.getElementById("admin-count-failed");
    if (badgeFailed) {
      if (c.processing_failed > 0) {
        badgeFailed.textContent = c.processing_failed;
        badgeFailed.classList.remove("hidden");
      } else {
        badgeFailed.classList.add("hidden");
      }
    }

    // Render Urgent Attention Queue
    const urgentTbody = document.getElementById("adm-urgent-tbody");
    if (urgentTbody) {
      const items = data.urgent_items || [];
      if (!items.length) {
        urgentTbody.innerHTML = `
          <tr><td colspan="5" style="text-align: center; color: var(--civic-emerald); font-weight: 600; padding: 1.5rem;">
            ✅ No critical bottlenecks. All urgent incidents triaged.
          </td></tr>
        `;
      } else {
        urgentTbody.innerHTML = items.map(item => {
          const sevClass = (item.severity_level || "low").toLowerCase();
          const isFailed = item.status === "PROCESSING_FAILED";
          return `
            <tr>
              <td><a href="#" onclick="openAdminIncidentModal('${item.id}'); return false;" style="font-weight: 700; color: #38bdf8;">#${item.id}</a></td>
              <td>${item.address || 'Street incident'}</td>
              <td><span class="badge badge-${sevClass}">${item.severity_level || 'Pending'}</span></td>
              <td><span class="badge ${isFailed ? 'badge-failed' : 'badge-progress'}">${item.status}</span></td>
              <td>
                <button class="btn btn-sm ${isFailed ? 'btn-danger' : 'btn-primary'}" onclick="openAdminIncidentModal('${item.id}')" style="padding: 2px 8px; font-size: 0.75rem;">
                  ${isFailed ? '⚠️ Retry Triage' : 'Inspect'}
                </button>
              </td>
            </tr>
          `;
        }).join("");
      }
    }
  } catch (err) {
    console.error("Error loading admin overview:", err);
  }
}

// ── 2. Admin Live Operations Feed (SSE) ─────────────────────────────────────
function initAdminSSE() {
  if (adminSSE || !currentUser || currentUser.role !== "admin") return;

  try {
    adminSSE = new EventSource(`${API}/complaints/admin/events`);

    adminSSE.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        appendAdminFeedItem(data);
      } catch (e) {}
    };

    adminSSE.addEventListener("complaint_submitted", (e) => handleAdminEvent("NEW REPORT", e.data, "feed-new"));
    adminSSE.addEventListener("processing_stage_changed", (e) => handleAdminEvent("AI STAGE", e.data, "feed-stage"));
    adminSSE.addEventListener("processing_completed", (e) => handleAdminEvent("AI READY", e.data, "feed-ai"));
    adminSSE.addEventListener("processing_failed", (e) => handleAdminEvent("AI FAILED", e.data, "feed-failed"));
    adminSSE.addEventListener("complaint_status_changed", (e) => handleAdminEvent("STATUS", e.data, "feed-resolved"));

    adminSSE.onerror = () => {
      // Browser EventSource automatically reconnects with backoff
    };
  } catch (err) {
    console.warn("Could not initiate admin SSE:", err);
  }
}

function handleAdminEvent(badge, rawData, extraClass) {
  try {
    const data = typeof rawData === "string" ? JSON.parse(rawData) : rawData;
    appendAdminFeedItem({ badge, ...data }, extraClass);

    // Subtle restrained toast on high severity or failure
    if (data.severity === "High" || data.status === "PROCESSING_FAILED" || badge === "AI FAILED") {
      showToast(`🚨 High-Priority Incident Update: Ticket #${data.ticket_id || data.complaint_id}`, "error", 4000);
      loadAdminOverview();
    }
  } catch (e) {}
}

function appendAdminFeedItem(data, extraClass = "") {
  const container = document.getElementById("admin-feed-container");
  if (!container) return;

  const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const ticketId = data.ticket_id || data.complaint_id || "SYSTEM";
  const badgeText = data.badge || data.event || "EVENT";
  const msg = data.progress_message || data.message || `Incident #${ticketId} update (${data.status || data.stage || 'notified'})`;

  const item = document.createElement("div");
  item.className = `feed-item ${extraClass}`;
  item.innerHTML = `
    <div class="feed-item-top">
      <span class="feed-badge">${badgeText}</span>
      <span class="feed-time">${timeStr}</span>
    </div>
    <div class="feed-msg">
      ${ticketId !== 'SYSTEM' ? `<a href="#" onclick="openAdminIncidentModal('${ticketId}'); return false;" style="font-weight:700; color:#38bdf8;">#${ticketId}</a> ` : ''}
      ${msg}
    </div>
  `;

  container.insertBefore(item, container.firstChild);

  // Keep feed trimmed to last 40 items
  while (container.children.length > 40) {
    container.removeChild(container.lastChild);
  }
}

// ── 3. Complaints Operations Queue ──────────────────────────────────────────
async function loadAdminComplaints() {
  const search = document.getElementById("admin-search-input")?.value?.trim() || "";
  const status = document.getElementById("admin-filter-status")?.value || "";
  const severity = document.getElementById("admin-filter-severity")?.value || "";
  const department = document.getElementById("admin-filter-dept")?.value || "";
  const aiMode = document.getElementById("admin-filter-aimode")?.value || "";

  let url = `${API}/complaints?page=${adminComplaintsPage}&per_page=${adminComplaintsPerPage}`;
  if (search) url += `&q=${encodeURIComponent(search)}`;
  if (status) url += `&status=${encodeURIComponent(status)}`;
  if (severity) url += `&severity=${encodeURIComponent(severity)}`;
  if (department) url += `&department=${encodeURIComponent(department)}`;
  if (aiMode) url += `&ai_mode=${encodeURIComponent(aiMode)}`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("Could not load complaints queue.");
    const data = await res.json();

    const items = data.items || [];
    const total = data.total || 0;
    adminComplaintsTotalPages = data.pages || 1;

    // Update Pagination UI
    const pageInfo = document.getElementById("admin-page-info");
    const pageCurrent = document.getElementById("admin-page-current");
    const prevBtn = document.getElementById("admin-page-prev");
    const nextBtn = document.getElementById("admin-page-next");

    const startIdx = total === 0 ? 0 : (adminComplaintsPage - 1) * adminComplaintsPerPage + 1;
    const endIdx = Math.min(total, adminComplaintsPage * adminComplaintsPerPage);

    if (pageInfo) pageInfo.textContent = `Showing ${startIdx}-${endIdx} of ${total} complaints`;
    if (pageCurrent) pageCurrent.textContent = `Page ${adminComplaintsPage} of ${adminComplaintsTotalPages}`;
    if (prevBtn) prevBtn.disabled = adminComplaintsPage <= 1;
    if (nextBtn) nextBtn.disabled = adminComplaintsPage >= adminComplaintsTotalPages;

    // Render Data Table
    const tbody = document.getElementById("admin-complaints-tbody");
    if (!tbody) return;

    if (!items.length) {
      tbody.innerHTML = `
        <tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 2rem;">
          🔍 No complaints match the active search and filter criteria.
        </td></tr>
      `;
      return;
    }

    tbody.innerHTML = items.map(c => {
      const date = new Date(c.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
      const sevClass = (c.severity?.level || 'low').toLowerCase();
      const aiModeBadge = c.ai_mode === "REAL_YOLO" 
        ? `<span class="badge-mode-real" title="Production YOLOv8 Inference">REAL YOLO</span>`
        : `<span class="badge-mode-mock" title="Demonstration Pipeline">MOCK DEMO</span>`;
      
      const isFailed = c.status === "PROCESSING_FAILED" || c.processing_status === "FAILED";

      return `
        <tr>
          <td><a href="#" onclick="openAdminIncidentModal('${c.ticket_id}'); return false;" style="font-weight: 700; color: #38bdf8;">#${c.ticket_id}</a></td>
          <td style="font-size: 0.78rem; color: var(--text-muted); white-space: nowrap;">${date}</td>
          <td>${c.submitted_by || 'Citizen'}</td>
          <td>${c.address || c.landmark || 'Street Location'}</td>
          <td>${aiModeBadge}</td>
          <td><span class="badge badge-${sevClass}">${c.severity?.level || 'Pending'}</span></td>
          <td>${c.department || 'Pending Triage'}</td>
          <td><span class="badge ${isFailed ? 'badge-failed' : 'badge-progress'}">${c.status}</span></td>
          <td style="white-space: nowrap;">
            <button class="btn btn-sm btn-secondary" onclick="openAdminIncidentModal('${c.ticket_id}')">
              Inspect
            </button>
            ${isFailed ? `
              <button class="btn btn-sm btn-danger" onclick="retryComplaintAI('${c.ticket_id}')" style="margin-left: 4px;">
                🔄 Retry
              </button>
            ` : ''}
          </td>
        </tr>
      `;
    }).join("");

  } catch (err) {
    console.error("Error loading complaints queue:", err);
  }
}

// ── 4. AI Processing Center & Failure Management ────────────────────────────
async function loadAdminProcessingQueue() {
  const procFilter = document.getElementById("admin-proc-filter")?.value || "";
  let url = `${API}/complaints/admin/queue?per_page=50`;
  if (procFilter) url += `&processing_status=${encodeURIComponent(procFilter)}`;

  try {
    // 1. Fetch AI execution mode status
    const healthRes = await fetch(`${API}/admin/system-health`);
    if (healthRes.ok) {
      const healthData = await healthRes.json();
      const aiPill = document.getElementById("admin-ai-mode-pill");
      if (aiPill) {
        const mode = healthData.ai?.execution_mode || "MOCK_DEMO";
        const label = healthData.ai?.active_ai_type || mode;
        aiPill.innerHTML = mode === "REAL_YOLO"
          ? `<span class="badge-mode-real" style="font-size: 0.85rem; padding: 0.35rem 0.75rem;">🤖 ${label}</span>`
          : `<span class="badge-mode-mock" style="font-size: 0.85rem; padding: 0.35rem 0.75rem;">🧪 ${label}</span>`;
      }
    }

    // 2. Fetch processing queue
    const res = await fetch(url);
    if (!res.ok) throw new Error("Could not load AI processing queue.");
    const data = await res.json();
    const items = data.items || [];

    const tbody = document.getElementById("admin-proc-tbody");
    if (!tbody) return;

    if (!items.length) {
      tbody.innerHTML = `
        <tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 2rem;">
          No processing jobs found for stage: <strong>${procFilter || 'All'}</strong>.
        </td></tr>
      `;
      return;
    }

    tbody.innerHTML = items.map(item => {
      const date = new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      const duration = item.processing_duration_ms ? `${item.processing_duration_ms} ms` : "—";
      const retries = item.retry_count || 0;
      const errorMsg = item.processing_error ? `<span style="color: var(--civic-red); font-size: 0.78rem;">${item.processing_error}</span>` : `<span style="color: var(--text-muted);">None</span>`;
      const isRetryable = item.retryable || item.status === "PROCESSING_FAILED" || item.processing_status === "FAILED";

      return `
        <tr>
          <td><a href="#" onclick="openAdminIncidentModal('${item.id || item.ticket_id}'); return false;" style="font-weight: 700; color: #38bdf8;">#${item.id || item.ticket_id}</a></td>
          <td style="font-size: 0.8rem; color: var(--text-muted);">${date}</td>
          <td><span class="${item.ai_mode === 'REAL_YOLO' ? 'badge-mode-real' : 'badge-mode-mock'}">${item.ai_mode || 'MOCK_DEMO'}</span></td>
          <td><span class="badge ${item.processing_status === 'COMPLETED' ? 'badge-resolved' : item.processing_status === 'FAILED' ? 'badge-failed' : 'badge-progress'}">${item.processing_status}</span></td>
          <td>${duration}</td>
          <td>${retries}</td>
          <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${errorMsg}</td>
          <td>
            ${isRetryable ? `
              <button class="btn btn-sm btn-danger" onclick="retryComplaintAI('${item.id || item.ticket_id}')">
                🔄 Retry Job
              </button>
            ` : `
              <button class="btn btn-sm btn-secondary" onclick="openAdminIncidentModal('${item.id || item.ticket_id}')">
                Inspect
              </button>
            `}
          </td>
        </tr>
      `;
    }).join("");

  } catch (err) {
    console.error("Error loading AI processing queue:", err);
  }
}

async function retryComplaintAI(ticketId) {
  try {
    const res = await fetch(`${API}/complaints/${ticketId}/retry-processing`, {
      method: "POST"
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Retry failed.");

    showToast(`AI job for Ticket #${ticketId} re-enqueued successfully.`, "success");
    loadAdminOverview();
    loadAdminProcessingQueue();
    if (adminActiveView === "complaints") loadAdminComplaints();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ── 5. Live Operations Map ──────────────────────────────────────────────────
async function loadAdminIncidentMap() {
  const container = document.getElementById("admin-ops-map");
  if (!container) return;

  if (!adminOpsMap) {
    adminOpsMap = L.map("admin-ops-map").setView([DEFAULT_LAT, DEFAULT_LNG], 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap contributors"
    }).addTo(adminOpsMap);
  } else {
    setTimeout(() => adminOpsMap.invalidateSize(), 150);
  }

  const deptFilter = document.getElementById("admin-map-filter-dept")?.value || "";
  const sevFilter = document.getElementById("admin-map-filter-sev")?.value || "";

  try {
    const res = await fetch(`${API}/analytics/geo`);
    if (!res.ok) throw new Error("Could not retrieve geo analytics.");
    const data = await res.json();
    let points = data.points || [];

    // Filter points
    if (deptFilter) points = points.filter(p => p.department === deptFilter);
    if (sevFilter) points = points.filter(p => p.severity === sevFilter);

    // Update count display
    const countEl = document.getElementById("admin-map-count");
    if (countEl) countEl.textContent = `Showing ${points.length} incident locations on map`;

    // Clear previous markers
    adminOpsMarkers.forEach(m => adminOpsMap.removeLayer(m));
    adminOpsMarkers = [];

    points.forEach(p => {
      const color = p.severity === "High" ? "#dc2626" : p.severity === "Medium" ? "#d97706" : "#059669";
      const marker = L.circleMarker([p.latitude, p.longitude], {
        radius: p.severity === "High" ? 9 : 7,
        fillColor: color,
        color: "#ffffff",
        weight: 1.5,
        fillOpacity: 0.85,
      }).addTo(adminOpsMap);

      marker.bindPopup(`
        <div style="font-family: inherit; font-size: 0.85rem; line-height: 1.4;">
          <div style="font-weight: 800; margin-bottom: 2px;">Incident #${p.ticket_id}</div>
          <div style="color: ${color}; font-weight: 700; margin-bottom: 4px;">${p.severity} Severity</div>
          <div><strong>Status:</strong> ${p.status}</div>
          <div><strong>Dept:</strong> ${p.department || 'Pending'}</div>
          <div><strong>Address:</strong> ${p.address || 'Street Pin'}</div>
          <button class="btn btn-sm btn-primary" onclick="openAdminIncidentModal('${p.ticket_id}')" style="margin-top: 6px; width: 100%; padding: 3px 6px;">
            Inspect Incident
          </button>
        </div>
      `);

      adminOpsMarkers.push(marker);
    });

  } catch (err) {
    console.error("Error loading admin incident map:", err);
  }
}

// ── 6. Department Operations ────────────────────────────────────────────────
async function loadAdminDepartments() {
  const container = document.getElementById("admin-departments-grid");
  if (!container) return;

  try {
    const res = await fetch(`${API}/admin/departments`);
    if (!res.ok) throw new Error("Could not load department metrics.");
    const data = await res.json();
    const depts = data.departments || [];

    const icons = {
      "Sanitation Department": "🗑️",
      "Recycling Department": "♻️",
      "Health & Hazmat Department": "☣️",
      "Public Works Department": "🏗️",
    };

    container.innerHTML = depts.map(d => `
      <div class="dept-card">
        <div class="dept-card-header">
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <span style="font-size: 1.35rem;">${icons[d.department] || '🏛️'}</span>
            <h3>${d.department}</h3>
          </div>
          <span class="badge ${d.active > 0 ? 'badge-progress' : 'badge-resolved'}">
            ${d.active} Active
          </span>
        </div>

        <div class="dept-stats-grid">
          <div class="dept-stat-box">
            <span class="val" style="color: #38bdf8;">${d.total}</span>
            <span class="lbl">Total Assigned</span>
          </div>
          <div class="dept-stat-box">
            <span class="val" style="color: var(--civic-amber);">${d.active}</span>
            <span class="lbl">Pending Action</span>
          </div>
          <div class="dept-stat-box">
            <span class="val" style="color: var(--civic-emerald);">${d.resolved}</span>
            <span class="lbl">Resolved</span>
          </div>
          <div class="dept-stat-box">
            <span class="val" style="color: var(--civic-red);">${d.high_severity}</span>
            <span class="lbl">High Severity</span>
          </div>
        </div>

        <button class="btn btn-secondary btn-sm" onclick="filterDepartmentInQueue('${d.department}')" style="margin-top: 0.5rem;">
          📋 View Department Queue →
        </button>
      </div>
    `).join("");

  } catch (err) {
    console.error("Error loading departments:", err);
  }
}

function filterDepartmentInQueue(deptName) {
  const select = document.getElementById("admin-filter-dept");
  if (select) select.value = deptName;
  switchAdminView("complaints");
}

// ── 7. Municipal Analytics ──────────────────────────────────────────────────
async function loadAdminAnalytics() {
  try {
    const res = await fetch(`${API}/admin/analytics?days=${adminAnalyticsDays}`);
    if (!res.ok) throw new Error("Could not load analytics.");
    const data = await res.json();

    // 1. Timeline Inflow Chart
    const ctxTimeline = document.getElementById("chart-admin-timeline");
    if (ctxTimeline) {
      if (chartTimeline) chartTimeline.destroy();
      chartTimeline = new Chart(ctxTimeline, {
        type: "line",
        data: {
          labels: data.timeline?.labels || [],
          datasets: [{
            label: "Incidents Reported",
            data: data.timeline?.counts || [],
            borderColor: "#38bdf8",
            backgroundColor: "rgba(56, 189, 248, 0.15)",
            fill: true,
            tension: 0.3,
            pointRadius: 4,
          }]
        },
        options: { responsive: true, maintainAspectRatio: false }
      });
    }

    // 2. Severity Breakdown Chart
    const ctxSev = document.getElementById("severity-chart");
    if (ctxSev) {
      if (chartSeverity) chartSeverity.destroy();
      const s = data.by_severity || {};
      chartSeverity = new Chart(ctxSev, {
        type: "doughnut",
        data: {
          labels: ["High Severity", "Medium Severity", "Low Severity"],
          datasets: [{
            data: [s.High || 0, s.Medium || 0, s.Low || 0],
            backgroundColor: ["#dc2626", "#d97706", "#059669"]
          }]
        },
        options: { responsive: true, maintainAspectRatio: false }
      });
    }

    // 3. Department Workload Chart
    const ctxDept = document.getElementById("department-chart");
    if (ctxDept) {
      if (chartDepartment) chartDepartment.destroy();
      const d = data.by_department || {};
      chartDepartment = new Chart(ctxDept, {
        type: "bar",
        data: {
          labels: Object.keys(d),
          datasets: [{
            label: "Assigned Cases",
            data: Object.values(d),
            backgroundColor: "#2563eb"
          }]
        },
        options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y' }
      });
    }

    // 4. Outcomes Chart
    const ctxOutcomes = document.getElementById("chart-admin-outcomes");
    if (ctxOutcomes) {
      if (chartOutcomes) chartOutcomes.destroy();
      const o = data.processing_outcomes || {};
      chartOutcomes = new Chart(ctxOutcomes, {
        type: "doughnut",
        data: {
          labels: ["Successful Triage", "Processing Failures"],
          datasets: [{
            data: [o.success || 0, o.failed || 0],
            backgroundColor: ["#059669", "#dc2626"]
          }]
        },
        options: { responsive: true, maintainAspectRatio: false }
      });
    }

  } catch (err) {
    console.error("Error loading admin analytics:", err);
  }
}

// ── 8. Users Management ─────────────────────────────────────────────────────
async function loadAdminUsers() {
  const tbody = document.getElementById("admin-users-tbody");
  if (!tbody) return;

  try {
    const res = await fetch(`${API}/auth/users`);
    if (!res.ok) throw new Error("Could not load users list.");
    const data = await res.json();
    const users = data.users || [];

    if (!users.length) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No users found.</td></tr>`;
      return;
    }

    tbody.innerHTML = users.map(u => {
      const date = new Date(u.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
      const isAdmin = u.role === "admin";
      return `
        <tr>
          <td style="font-family: monospace; font-size: 0.8rem;">#${u.id}</td>
          <td><strong>${u.username}</strong></td>
          <td>${u.email || '—'}</td>
          <td><span class="user-role-badge ${u.role}">${isAdmin ? '🛡️ Admin' : '👤 Citizen'}</span></td>
          <td style="color: var(--text-secondary); font-size: 0.82rem;">${date}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    console.error("Error loading users:", err);
  }
}

// ── 9. System Health Diagnostics ────────────────────────────────────────────
async function loadAdminSystemHealth() {
  const grid = document.getElementById("admin-system-health-grid");
  if (!grid) return;

  try {
    const res = await fetch(`${API}/admin/system-health`);
    if (!res.ok) throw new Error("Could not fetch system health.");
    const h = await res.json();

    const isHealthy = h.status === "Healthy";
    const isRedisOk = (h.redis || "").includes("Healthy");

    grid.innerHTML = `
      <div class="health-card">
        <div class="health-card-header">
          <h3>🗄️ Relational Database</h3>
          <span class="health-badge ${isHealthy ? 'health-healthy' : 'health-warning'}">${h.database}</span>
        </div>
        <div class="health-details">
          SQLite / PostgreSQL engine connection verified via active transaction probe.
        </div>
      </div>

      <div class="health-card">
        <div class="health-card-header">
          <h3>⚡ Redis & Event Bus</h3>
          <span class="health-badge ${isRedisOk ? 'health-healthy' : 'health-warning'}">${h.redis}</span>
        </div>
        <div class="health-details">
          Pub/Sub real-time channel delivery and worker synchronization service.
        </div>
      </div>

      <div class="health-card">
        <div class="health-card-header">
          <h3>👷 Background RQ Queue</h3>
          <span class="health-badge health-healthy">Mode: ${h.queue?.mode?.toUpperCase() || 'REDIS'}</span>
        </div>
        <div class="health-details">
          Pending asynchronous jobs in queue: <strong>${h.queue?.size || 0}</strong>
        </div>
      </div>

      <div class="health-card">
        <div class="health-card-header">
          <h3>🤖 Computer Vision Pipeline</h3>
          <span class="health-badge ${h.ai?.execution_mode === 'REAL_YOLO' ? 'health-healthy' : 'health-warning'}">
            ${h.ai?.execution_mode || 'MOCK_DEMO'}
          </span>
        </div>
        <div class="health-details">
          ${h.ai?.active_ai_type || 'AI Inference'}<br/>
          Model weights: <code>${h.ai?.weights_path || 'best.pt'}</code> (${h.ai?.weights_file_present ? 'Verified' : 'Simulated'})
        </div>
      </div>

      <div class="health-card">
        <div class="health-card-header">
          <h3>📊 Active Operations Backlog</h3>
          <span class="health-badge health-healthy">${h.active_complaints || 0} Active</span>
        </div>
        <div class="health-details">
          Complaints currently moving through triage, assignment, and field work.
        </div>
      </div>
    `;

  } catch (err) {
    console.error("Error loading system health:", err);
  }
}

// ── 10. Admin Incident Inspector & Triage Modal ──────────────────────────────
async function openAdminIncidentModal(ticketId) {
  try {
    const res = await fetch(`${API}/complaints/${ticketId}`);
    if (!res.ok) throw new Error("Could not load incident details.");
    const c = await res.json();

    const titleEl = document.getElementById("admin-modal-title");
    const ticketIdEl = document.getElementById("admin-modal-ticket-id");
    const bodyEl = document.getElementById("admin-modal-body");

    if (titleEl) titleEl.textContent = `Incident Triage #${c.ticket_id}`;
    if (ticketIdEl) ticketIdEl.textContent = `Reported: ${new Date(c.created_at).toLocaleString()}`;

    const hasAnnotated = !!c.annotated_image_path;
    const annotatedSrc = `/uploads/${c.annotated_image_path}`;
    const originalSrc = `/uploads/${c.image_path}`;
    const isFailed = c.status === "PROCESSING_FAILED" || c.processing_status === "FAILED";

    // Valid forward transitions according to backend state machine
    const legalTransitions = {
      "SUBMITTED": ["AI_PROCESSING", "REJECTED"],
      "AI_PROCESSING": ["VERIFIED", "PROCESSING_FAILED", "DUPLICATE"],
      "PROCESSING_FAILED": ["AI_PROCESSING", "REJECTED"],
      "VERIFIED": ["ASSIGNED", "IN_PROGRESS", "RESOLVED", "DUPLICATE", "REJECTED", "NEEDS_INFORMATION"],
      "ASSIGNED": ["IN_PROGRESS", "RESOLVED", "REJECTED", "NEEDS_INFORMATION"],
      "IN_PROGRESS": ["RESOLUTION_SUBMITTED", "RESOLVED", "REJECTED", "NEEDS_INFORMATION"],
      "RESOLUTION_SUBMITTED": ["RESOLVED", "IN_PROGRESS", "REJECTED"],
      "NEEDS_INFORMATION": ["IN_PROGRESS", "VERIFIED", "REJECTED"],
      "DUPLICATE": ["VERIFIED", "REJECTED"],
      "RESOLVED": [],
      "REJECTED": [],
    };

    const currentStatus = (c.status || "").toUpperCase();
    const possibleStatuses = legalTransitions[currentStatus] || [];

    const depts = [
      "Sanitation Department",
      "Recycling Department",
      "Health & Hazmat Department",
      "Public Works Department",
    ];

    bodyEl.innerHTML = `
      <div class="admin-inspector-grid">
        <!-- LEFT: VISUAL EVIDENCE & DETECTIONS -->
        <div class="inspector-pane">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="font-weight: 700; font-size: 0.88rem;">Visual Evidence</span>
            ${hasAnnotated ? `
              <div style="display: flex; gap: 0.35rem;">
                <button type="button" class="btn btn-sm btn-primary active" id="btn-admin-boxes" onclick="toggleAdminImageView('annotated')">🎯 AI Boxes</button>
                <button type="button" class="btn btn-sm btn-outline" id="btn-admin-orig" onclick="toggleAdminImageView('original')">📷 Original</button>
              </div>
            ` : ''}
          </div>

          <div style="border-radius: var(--radius-md); overflow: hidden; background: #000; border: 1px solid var(--border-color); text-align: center; min-height: 220px; display: flex; align-items: center; justify-content: center;">
            <img id="admin-inspector-img" src="${hasAnnotated ? annotatedSrc : originalSrc}" data-annotated="${annotatedSrc}" data-original="${originalSrc}" alt="Incident evidence" style="max-width: 100%; max-height: 320px; object-fit: contain;" />
          </div>

          <!-- DETECTIONS CHIPS -->
          <div class="civic-card" style="padding: 0.85rem;">
            <h4 style="font-size: 0.82rem; margin-bottom: 0.5rem; text-transform: uppercase; color: var(--text-secondary);">
              🔍 Classified Classes (${c.detections ? c.detections.length : 0})
            </h4>
            <div style="display: flex; flex-wrap: wrap; gap: 0.4rem;">
              ${c.detections && c.detections.length > 0 
                ? c.detections.map(d => `<span class="badge badge-low">🏷️ <strong>${d.class}</strong> (${(d.confidence * 100).toFixed(0)}%)</span>`).join("")
                : `<span style="color: var(--text-muted); font-size: 0.82rem;">No bounding boxes detected</span>`
              }
            </div>
            <div style="margin-top: 0.65rem; font-size: 0.82rem; color: var(--text-secondary);">
              Coverage: <strong>${((c.severity?.coverage_ratio || 0) * 100).toFixed(1)}%</strong> | Severity Score: <strong>${c.severity?.level || 'Low'}</strong>
            </div>
          </div>
        </div>

        <!-- RIGHT: OPERATIONAL TRIAGE & METADATA -->
        <div class="inspector-pane">
          <!-- TRIAGE ACTIONS -->
          <div class="triage-action-box">
            <h4><span>⚖️</span> Municipal Dispatch Triage</h4>

            <!-- DEPARTMENT REASSIGNMENT -->
            <div class="form-group">
              <label style="font-size: 0.78rem; font-weight: 700;">Assign Department</label>
              <div style="display: flex; gap: 0.5rem;">
                <select id="modal-assign-dept" style="flex: 1; padding: 0.4rem 0.6rem; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: var(--bg-input); color: var(--text-primary); font-size: 0.85rem;">
                  ${depts.map(d => `<option value="${d}" ${c.department === d ? 'selected' : ''}>${d}</option>`).join("")}
                </select>
                <button class="btn btn-primary btn-sm" onclick="saveIncidentDepartment('${c.ticket_id}')">Save</button>
              </div>
            </div>

            <!-- STATUS TRANSITION -->
            <div class="form-group" style="margin-top: 0.5rem;">
              <label style="font-size: 0.78rem; font-weight: 700;">Transition Lifecycle State (Current: ${c.status})</label>
              <div style="display: flex; gap: 0.5rem;">
                <select id="modal-update-status" style="flex: 1; padding: 0.4rem 0.6rem; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: var(--bg-input); color: var(--text-primary); font-size: 0.85rem;">
                  <option value="${c.status}" selected>— Keep Current (${c.status}) —</option>
                  ${possibleStatuses.map(st => `<option value="${st}">→ ${st}</option>`).join("")}
                </select>
                <button class="btn btn-secondary btn-sm" onclick="saveIncidentStatus('${c.ticket_id}')">Update</button>
              </div>
            </div>

            ${isFailed ? `
              <div style="margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid var(--border-color);">
                <button class="btn btn-danger btn-sm btn-block" onclick="retryComplaintAI('${c.ticket_id}'); closeModal('admin-detail-modal');">
                  🔄 Retry Failed AI Analysis
                </button>
              </div>
            ` : ''}
          </div>

          <!-- METADATA CARD -->
          <div class="civic-card" style="padding: 1rem; font-size: 0.85rem; line-height: 1.6;">
            <div><strong>Citizen:</strong> ${c.submitted_by || 'Anonymous'}</div>
            <div><strong>Location:</strong> ${c.address || 'Street Coordinates'}</div>
            ${c.landmark ? `<div><strong>Landmark:</strong> ${c.landmark}</div>` : ''}
            <div><strong>AI Pipeline:</strong> <span class="${c.ai_mode === 'REAL_YOLO' ? 'badge-mode-real' : 'badge-mode-mock'}">${c.ai_mode || 'MOCK_DEMO'}</span></div>
            ${c.is_duplicate ? `<div style="color: var(--civic-amber);">⚠️ Proximity duplicate linked to #${c.duplicate_of_id}</div>` : ''}
          </div>
        </div>
      </div>
    `;

    openModal("admin-detail-modal");

  } catch (err) {
    showToast(err.message, "error");
  }
}

function toggleAdminImageView(viewType) {
  const img = document.getElementById("admin-inspector-img");
  const btnBoxes = document.getElementById("btn-admin-boxes");
  const btnOrig = document.getElementById("btn-admin-orig");
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

async function saveIncidentDepartment(ticketId) {
  const dept = document.getElementById("modal-assign-dept")?.value;
  if (!dept) return;

  try {
    const res = await fetch(`${API}/complaints/${ticketId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ department: dept })
    });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.error || "Could not update department.");
    }
    showToast(`Assigned Ticket #${ticketId} to ${dept}`, "success");
    loadAdminOverview();
    if (adminActiveView === "complaints") loadAdminComplaints();
    if (adminActiveView === "departments") loadAdminDepartments();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function saveIncidentStatus(ticketId) {
  const newStatus = document.getElementById("modal-update-status")?.value;
  if (!newStatus) return;

  try {
    const res = await fetch(`${API}/complaints/${ticketId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus })
    });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.error || "Could not update lifecycle status.");
    }
    showToast(`Ticket #${ticketId} transitioned to ${newStatus}`, "success");
    closeModal("admin-detail-modal");
    loadAdminOverview();
    if (adminActiveView === "complaints") loadAdminComplaints();
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
