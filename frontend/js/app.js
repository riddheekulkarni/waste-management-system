const API = "/api";

// APP STATE
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

// DEFAULT MAP CENTER (e.g. Pune/Mumbai region)
const DEFAULT_LAT = 18.5204;
const DEFAULT_LNG = 73.8567;

// ==========================================
// 0. TOAST NOTIFICATION SYSTEM
// ==========================================
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
  toast.innerHTML = `<span class="toast-icon">${icons[type] || "ℹ️"}</span><span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("toast-hide");
    toast.addEventListener("animationend", () => toast.remove(), { once: true });
  }, duration);
}

// INITIALIZATION
document.addEventListener("DOMContentLoaded", async () => {
  setupThemePreference();

  // Ensure toast container exists in DOM
  const toastContainer = document.createElement("div");
  toastContainer.id = "toast-container";
  document.body.appendChild(toastContainer);

  setupNavigation();
  setupAuth();
  setupReportForm();
  setupTrackView();
  setupAdminDashboard();
  setupModals();

  await checkAuthStatus();
  initReportMap();
});

// ==========================================
// 0. THEME PREFERENCE
// ==========================================
function setupThemePreference() {
  const toggle = document.getElementById("theme-toggle");
  const savedTheme = localStorage.getItem("eco-clean-theme");
  const theme = savedTheme === "light" ? "light" : "dark";

  applyTheme(theme);

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
    const action = isLight ? "Switch to dark mode" : "Switch to light mode";
    toggle.setAttribute("aria-label", action);
    toggle.setAttribute("title", action);
    toggle.querySelector(".theme-toggle-icon").textContent = isLight ? "🌙" : "☀️";
    toggle.querySelector(".theme-toggle-label").textContent = label;
  }
}

// ==========================================
// 1. AUTHENTICATION & ROLE MANAGEMENT
// ==========================================
async function checkAuthStatus() {
  try {
    const res = await fetch(`${API}/auth/me`);
    const data = await res.json();
    currentUser = data.user;
    updateUserAuthUI();
  } catch (err) {
    console.error("Auth check error:", err);
    currentUser = null;
    updateUserAuthUI();
  }
}

function updateUserAuthUI() {
  const authBar = document.getElementById("user-auth-bar");
  const adminLockTag = document.getElementById("admin-lock-tag");
  const adminLockedView = document.getElementById("admin-locked-view");
  const adminUnlockedView = document.getElementById("admin-unlocked-view");
  const myComplaintsGroup = document.getElementById("my-complaints-group");

  if (currentUser) {
    authBar.innerHTML = `
      <div class="user-badge-pill">
        <span class="user-name">👤 ${currentUser.username}</span>
        <span class="user-role-badge ${currentUser.role}">${currentUser.role}</span>
        <button class="btn btn-sm btn-secondary" id="logout-btn">Logout</button>
      </div>
    `;
    document.getElementById("logout-btn").addEventListener("click", handleLogout);

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
      <button class="btn btn-outline" id="open-auth-btn">
        <span class="icon">🔑</span> Sign In / Register
      </button>
    `;
    document.getElementById("open-auth-btn").addEventListener("click", () => openModal("auth-modal"));

    adminLockTag.textContent = "🔒";
    adminLockedView.classList.remove("hidden");
    adminUnlockedView.classList.add("hidden");
    if (myComplaintsGroup) myComplaintsGroup.classList.add("hidden");
  }
}

function setupAuth() {
  // Auth Modal Tabs
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

  // Toggle Register mode for Citizen
  let isRegisterMode = false;
  const toggleBtn = document.getElementById("toggle-register-btn");
  const title = document.getElementById("citizen-auth-title");
  const citizenSubmitBtn = document.querySelector("#citizen-login-form button[type='submit']");
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
        citizenIdentifierLabel.textContent = "Username";
        citizenIdentifierInput.placeholder = "Choose a username, e.g. john_doe";
        citizenEmailGroup.style.display = "flex";
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

  // Forms
  document.getElementById("citizen-login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const identifier = document.getElementById("citizen-identifier").value.trim();
    const password = document.getElementById("citizen-password").value;

    const endpoint = isRegisterMode ? `${API}/auth/register` : `${API}/auth/login`;
    const payload = isRegisterMode
      ? { username: identifier, email: citizenEmailInput.value.trim(), password, role: "citizen" }
      : { identifier, password, role: "citizen" };

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
      showToast(`Welcome, ${currentUser.username}!`, "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  document.getElementById("admin-login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const identifier = document.getElementById("admin-identifier").value.trim();
    const password = document.getElementById("admin-password").value;

    try {
      const res = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, password, role: "admin" })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Admin login failed");

      currentUser = data.user;
      updateUserAuthUI();
      closeModal("auth-modal");
      showToast(`Welcome to Municipal Operations Center, ${currentUser.username}!`, "success");
      loadAdminDashboard();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Demo Login Buttons
  document.getElementById("demo-citizen-btn").addEventListener("click", () => demoLogin("citizen@civic.gov", "citizen123", "citizen"));
  document.getElementById("demo-admin-btn").addEventListener("click", () => demoLogin("admin@civic.gov", "admin123", "admin"));
  document.getElementById("admin-login-trigger-btn").addEventListener("click", () => {
    openModal("auth-modal");
    adminTab.click();
  });
}

async function demoLogin(identifier, password, role) {
  try {
    const res = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier, password, role })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Demo login failed");

    currentUser = data.user;
    updateUserAuthUI();
    closeModal("auth-modal");
    showToast(`Signed in as ${currentUser.username} (${currentUser.role})`, "success");
    if (role === "admin") {
      switchToTab("admin");
    }
  } catch (err) {
    showToast(`Demo login error: ${err.message}`, "error");
  }
}

async function handleLogout() {
  await fetch(`${API}/auth/logout`, { method: "POST" });
  currentUser = null;
  updateUserAuthUI();
  switchToTab("report");
}

// ==========================================
// 2. NAVIGATION & TABS
// ==========================================
function setupNavigation() {
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

  if (targetBtn && targetPanel) {
    targetBtn.classList.add("active");
    targetPanel.classList.add("active");
  }

  if (tabId === "report") {
    setTimeout(() => { if (reportMap) reportMap.invalidateSize(); }, 200);
  } else if (tabId === "track") {
    loadTrackComplaints();
  } else if (tabId === "admin") {
    if (currentUser && currentUser.role === "admin") {
      loadAdminDashboard();
    }
  }
}

// ==========================================
// 3. USER-FRIENDLY LOCATION SELECTION & MAP
// ==========================================
function initReportMap() {
  const container = document.getElementById("report-map");
  if (!container || reportMap) return;

  reportMap = L.map("report-map").setView([DEFAULT_LAT, DEFAULT_LNG], 13);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors"
  }).addTo(reportMap);

  reportMarker = L.marker([DEFAULT_LAT, DEFAULT_LNG], { draggable: true }).addTo(reportMap);

  // Default address reverse-geocode
  updateLocation(DEFAULT_LAT, DEFAULT_LNG, false);

  // Map Click Listener
  reportMap.on("click", (e) => {
    const { lat, lng } = e.latlng;
    reportMarker.setLatLng([lat, lng]);
    updateLocation(lat, lng, true);
  });

  // Marker Drag Listener
  reportMarker.on("dragend", (e) => {
    const { lat, lng } = e.target.getLatLng();
    updateLocation(lat, lng, true);
  });
}

async function updateLocation(lat, lng, fetchAddress = true) {
  document.getElementById("lat-input").value = lat.toFixed(6);
  document.getElementById("lng-input").value = lng.toFixed(6);

  if (fetchAddress) {
    document.getElementById("address-input").value = "Fetching address...";
    try {
      const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`);
      const data = await res.json();
      if (data && data.display_name) {
        document.getElementById("address-input").value = data.display_name;
      } else {
        document.getElementById("address-input").value = `Coordinates: ${lat.toFixed(4)}, ${lng.toFixed(4)}`;
      }
    } catch (err) {
      document.getElementById("address-input").value = `Location: ${lat.toFixed(4)}, ${lng.toFixed(4)}`;
    }
  } else {
    document.getElementById("address-input").value = "Central Municipal District, City Center";
  }
}

// Address Search & Geolocation Handlers
function setupReportForm() {
  const addressSearchInput = document.getElementById("address-search-input");
  const searchAddressBtn = document.getElementById("search-address-btn");
  const useLocationBtn = document.getElementById("use-location-btn");
  const imageInput = document.getElementById("image-input");
  const dropzone = document.getElementById("dropzone");
  const previewContainer = document.getElementById("image-preview-container");
  const previewImg = document.getElementById("image-preview");
  const removeImgBtn = document.getElementById("remove-img-btn");
  const dropzoneContent = document.getElementById("dropzone-content");

  // Address Search Button
  searchAddressBtn.addEventListener("click", async () => {
    const query = addressSearchInput.value.trim();
    if (!query) return;

    searchAddressBtn.textContent = "Searching...";
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
      } else {
        showToast("Location not found. Try clicking directly on the map.", "info");
      }
    } catch (err) {
      showToast("Error searching location.", "error");
    } finally {
      searchAddressBtn.textContent = "Search";
    }
  });

  // Detect My Location Button
  useLocationBtn.addEventListener("click", () => {
    if (!navigator.geolocation) {
      showToast("Geolocation is not supported by your browser.", "error");
      return;
    }

    useLocationBtn.innerHTML = `<span>⏳ Detecting...</span>`;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        reportMap.setView([lat, lng], 16);
        reportMarker.setLatLng([lat, lng]);
        updateLocation(lat, lng, true);
        useLocationBtn.innerHTML = `<span class="icon">📍</span> Detect My Location`;
      },
      () => {
        showToast("Could not retrieve location. Please click on the map.", "info");
        useLocationBtn.innerHTML = `<span class="icon">📍</span> Detect My Location`;
      }
    );
  });

  // Image Upload Preview
  imageInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const reader = new FileReader();
      reader.onload = (evt) => {
        previewImg.src = evt.target.result;
        dropzoneContent.classList.add("hidden");
        previewContainer.classList.remove("hidden");
      };
      reader.readAsDataURL(file);
    }
  });

  removeImgBtn.addEventListener("click", () => {
    imageInput.value = "";
    previewImg.src = "";
    previewContainer.classList.add("hidden");
    dropzoneContent.classList.remove("hidden");
  });

  // Drag and drop styles
  ["dragenter", "dragover"].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
  });
  ["dragleave", "drop"].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => { e.preventDefault(); dropzone.classList.remove("dragover"); });
  });

  // Form Submit
  document.getElementById("upload-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const submitBtn = document.getElementById("submit-btn");
    const resultBox = document.getElementById("upload-result");

    if (!imageInput.files.length) {
      showToast("Please select a waste photo first.", "info");
      return;
    }

    const formData = new FormData();
    formData.append("image", imageInput.files[0]);

    const lat = document.getElementById("lat-input").value;
    const lng = document.getElementById("lng-input").value;
    let address = document.getElementById("address-input").value;
    const landmark = document.getElementById("landmark-input").value.trim();

    if (landmark) {
      address += ` (${landmark})`;
    }

    if (lat) formData.append("latitude", lat);
    if (lng) formData.append("longitude", lng);
    if (address) formData.append("address", address);

    submitBtn.disabled = true;
    submitBtn.innerHTML = `⏳ Analyzing Image & Submitting...`;

    try {
      const res = await fetch(`${API}/complaints/upload`, { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Upload failed");

      resultBox.className = "glass-card result-card success";
      resultBox.innerHTML = `
        <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem;">
          <span style="font-size: 1.8rem;">🎉</span>
          <div>
            <h3 style="font-size: 1.1rem; color: var(--accent-emerald);">Complaint Registered — Ticket #${data.ticket_id}</h3>
            <span style="font-size: 0.85rem; color: var(--text-muted);">Routed to <strong>${data.department}</strong></span>
          </div>
        </div>
        <p style="font-size: 0.9rem; margin-top: 0.5rem;">
          📍 <strong>Location:</strong> ${data.address}<br/>
          📊 <strong>AI Severity Assessment:</strong> <span class="badge badge-${data.severity.level.toLowerCase()}">${data.severity.level} Severity</span> (${data.severity.item_count} items detected)
        </p>
        <button class="btn btn-sm btn-secondary" style="margin-top: 0.75rem;" onclick="switchToTab('track')">
          View in Complaints Tracker →
        </button>
      `;

      e.target.reset();
      removeImgBtn.click();
    } catch (err) {
      resultBox.className = "glass-card result-card error";
      resultBox.innerHTML = `❌ Error: ${err.message}`;
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `🚀 Submit Complaint to Municipal Team`;
    }
  });
}

// ==========================================
// 4. TRACK COMPLAINTS SECTION
// ==========================================
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
    setTimeout(() => { initTrackMap(); }, 200);
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
    const complaints = await res.json();

    renderComplaintsCards(complaints);
    updateTrackMapMarkers(complaints);
  } catch (err) {
    console.error("Error loading complaints:", err);
  }
}

function renderComplaintsCards(complaints) {
  const list = document.getElementById("complaint-list");
  if (!complaints.length) {
    list.innerHTML = `<p style="color: var(--text-muted); padding: 2rem; grid-column: 1/-1; text-align: center;">No complaints match your selected filters.</p>`;
    return;
  }

  list.innerHTML = complaints.map((c) => {
    const date = new Date(c.created_at).toLocaleString();
    const statusClass = c.status === "Resolved" ? "badge-resolved" : c.status === "In Progress" ? "badge-progress" : "badge-open";
    return `
      <div class="glass-card complaint-card severity-${c.severity.level}">
        <div class="card-header-row">
          <span class="ticket-id">Ticket #${c.ticket_id}</span>
          <span class="badge ${statusClass}">${c.status}</span>
        </div>
        <img src="/uploads/${c.image_path}" class="card-img-thumb" alt="Waste photo" />
        <div class="card-body-info">
          <div class="info-item">📌 ${c.address}</div>
          <div class="info-item">🏛️ ${c.department}</div>
          <div class="info-item">⚠️ Severity: <strong>${c.severity.level}</strong> (${c.severity.item_count} items detected)</div>
          <div class="info-item">🕒 ${date}</div>
        </div>
        <div class="card-footer-row">
          <span style="font-size: 0.78rem; color: var(--text-dim);">By: ${c.submitted_by}</span>
          <button class="btn btn-sm btn-secondary" onclick="openComplaintDetail('${c.ticket_id}')">Inspect Details</button>
        </div>
      </div>
    `;
  }).join("");
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

  loadTrackComplaints();
}

function updateTrackMapMarkers(complaints) {
  if (!trackMap) return;

  trackMarkers.forEach((m) => trackMap.removeLayer(m));
  trackMarkers = [];

  const bounds = [];

  complaints.forEach((c) => {
    if (c.latitude && c.longitude) {
      const color = c.severity.level === "High" ? "#ef4444" : c.severity.level === "Medium" ? "#f59e0b" : "#10b981";
      const marker = L.circleMarker([c.latitude, c.longitude], {
        radius: 9,
        fillColor: color,
        color: "#ffffff",
        weight: 2,
        opacity: 1,
        fillOpacity: 0.85
      }).addTo(trackMap);

      marker.bindPopup(`
        <div style="font-family: sans-serif; color: #1e293b;">
          <strong>Ticket #${c.ticket_id}</strong><br/>
          Status: <b>${c.status}</b><br/>
          Severity: <b>${c.severity.level}</b><br/>
          ${c.address}<br/>
          <button style="margin-top: 6px; cursor: pointer; padding: 4px 8px;" onclick="openComplaintDetail('${c.ticket_id}')">Inspect Ticket</button>
        </div>
      `);

      trackMarkers.push(marker);
      bounds.push([c.latitude, c.longitude]);
    }
  });

  if (bounds.length > 0) {
    trackMap.fitBounds(bounds, { padding: [30, 30] });
  }
}

// ==========================================
// 5. ADMIN DASHBOARD SECTION
// ==========================================
function setupAdminDashboard() {
  document.getElementById("refresh-admin-btn").addEventListener("click", loadAdminDashboard);
  document.getElementById("admin-filter-department").addEventListener("change", loadAdminDashboard);
}

async function loadAdminDashboard() {
  if (!currentUser || currentUser.role !== "admin") return;

  try {
    const summaryRes = await fetch(`${API}/analytics/summary`);
    const summary = await summaryRes.json();

    document.getElementById("stat-total").textContent = summary.total_complaints;
    document.getElementById("stat-open").textContent = summary.by_status["Open"] || 0;
    document.getElementById("stat-resolved").textContent = summary.by_status["Resolved"] || 0;
    document.getElementById("stat-high").textContent = summary.by_severity["High"] || 0;

    renderAdminCharts(summary);

    const department = document.getElementById("admin-filter-department").value;
    const params = department ? `?department=${encodeURIComponent(department)}` : "";
    const listRes = await fetch(`${API}/complaints${params}`);
    const complaints = await listRes.json();

    renderAdminTable(complaints);
    initAdminMap(complaints);
  } catch (err) {
    console.error("Error loading admin dashboard:", err);
  }
}

function renderAdminCharts(summary) {
  // Severity Donut Chart
  const sevCtx = document.getElementById("severity-chart").getContext("2d");
  if (severityChart) severityChart.destroy();

  severityChart = new Chart(sevCtx, {
    type: "doughnut",
    data: {
      labels: Object.keys(summary.by_severity),
      datasets: [{
        data: Object.values(summary.by_severity),
        backgroundColor: ["#10b981", "#f59e0b", "#ef4444"]
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { color: "#94a3b8" } } }
    }
  });

  // Department Bar Chart
  const deptCtx = document.getElementById("department-chart").getContext("2d");
  if (departmentChart) departmentChart.destroy();

  departmentChart = new Chart(deptCtx, {
    type: "bar",
    data: {
      labels: Object.keys(summary.by_department),
      datasets: [{
        label: "Tickets Dispatched",
        data: Object.values(summary.by_department),
        backgroundColor: "#3b82f6"
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: "#94a3b8" } },
        y: { ticks: { color: "#94a3b8" }, beginAtZero: true }
      },
      plugins: { legend: { display: false } }
    }
  });
}

function renderAdminTable(complaints) {
  const tbody = document.querySelector("#admin-table tbody");
  const statuses = ["Open", "In Progress", "Resolved"];

  tbody.innerHTML = complaints.map((c) => {
    const date = new Date(c.created_at).toLocaleDateString();
    const options = statuses
      .map((s) => `<option value="${s}" ${s === c.status ? "selected" : ""}>${s}</option>`)
      .join("");

    return `
      <tr>
        <td><strong>#${c.ticket_id}</strong></td>
        <td>${date}</td>
        <td>${c.submitted_by}</td>
        <td>${c.address}</td>
        <td><span class="badge badge-${c.severity.level.toLowerCase()}">${c.severity.level}</span></td>
        <td>${c.department}</td>
        <td>
          <select class="status-select select-sm" data-ticket="${c.ticket_id}">${options}</select>
        </td>
        <td>
          <button class="btn btn-sm btn-secondary" onclick="openComplaintDetail('${c.ticket_id}')">Inspect</button>
        </td>
      </tr>
    `;
  }).join("");

  document.querySelectorAll(".status-select").forEach((sel) => {
    sel.addEventListener("change", async (e) => {
      const ticketId = e.target.dataset.ticket;
      const newStatus = e.target.value;
      try {
        const res = await fetch(`${API}/complaints/${ticketId}/status`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: newStatus }),
        });
        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.error || "Update failed");
        }
        showToast(`Ticket #${ticketId} updated to "${newStatus}"`, "success");
        loadAdminDashboard();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  });
}

function initAdminMap(complaints) {
  if (!adminMap) {
    adminMap = L.map("admin-map").setView([DEFAULT_LAT, DEFAULT_LNG], 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap contributors"
    }).addTo(adminMap);
  }

  adminMarkers.forEach((m) => adminMap.removeLayer(m));
  adminMarkers = [];

  const bounds = [];
  complaints.forEach((c) => {
    if (c.latitude && c.longitude) {
      const color = c.severity.level === "High" ? "#ef4444" : c.severity.level === "Medium" ? "#f59e0b" : "#10b981";
      const marker = L.circleMarker([c.latitude, c.longitude], {
        radius: 8,
        fillColor: color,
        color: "#ffffff",
        weight: 2,
        fillOpacity: 0.9
      }).addTo(adminMap);

      marker.bindPopup(`<b>Ticket #${c.ticket_id}</b><br/>Severity: ${c.severity.level}<br/>Dept: ${c.department}`);
      adminMarkers.push(marker);
      bounds.push([c.latitude, c.longitude]);
    }
  });

  if (bounds.length > 0) {
    adminMap.fitBounds(bounds, { padding: [20, 20] });
  }
}

// ==========================================
// 6. COMPLAINT INSPECTION MODAL
// ==========================================
async function openComplaintDetail(ticketId) {
  try {
    const res = await fetch(`${API}/complaints/${ticketId}`);
    const c = await res.json();
    if (!res.ok) throw new Error("Could not load ticket details");

    const content = document.getElementById("detail-modal-content");
    const date = new Date(c.created_at).toLocaleString();

    content.innerHTML = `
      <div style="margin-bottom: 1rem;">
        <span class="user-role-badge" style="float: right;">${c.status}</span>
        <h2>Ticket #${c.ticket_id}</h2>
        <p style="color: var(--text-muted); font-size: 0.85rem;">Submitted on ${date} by ${c.submitted_by}</p>
      </div>

      <div class="detail-grid">
        <div>
          <div class="detail-img-box">
            <img src="/uploads/${c.image_path}" alt="Complaint image" />
          </div>
          <div style="margin-top: 1rem; font-size: 0.88rem;">
            <h4>AI Detection Analysis:</h4>
            <ul style="margin-left: 1.2rem; color: var(--text-muted); margin-top: 0.4rem;">
              ${c.detections && c.detections.length > 0 
                ? c.detections.map(d => `<li><strong>${d.class}</strong> (${(d.confidence * 100).toFixed(0)}% confidence)</li>`).join("")
                : `<li>Items Detected: ${c.severity.item_count} items</li>`}
            </ul>
          </div>
        </div>

        <div>
          <div class="glass-card" style="padding: 1rem; margin-bottom: 1rem;">
            <p>📌 <strong>Address:</strong> ${c.address}</p>
            <p>🏛️ <strong>Dispatched Dept:</strong> ${c.department}</p>
            <p>📊 <strong>Severity Score:</strong> <span class="badge badge-${c.severity.level.toLowerCase()}">${c.severity.level}</span></p>
          </div>
          <div id="detail-map" class="interactive-map" style="height: 200px;"></div>
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

// ==========================================
// 7. MODAL UTILITIES
// ==========================================
function setupModals() {
  document.getElementById("close-auth-modal").addEventListener("click", () => closeModal("auth-modal"));
  document.getElementById("close-detail-modal").addEventListener("click", () => closeModal("complaint-detail-modal"));

  window.addEventListener("click", (e) => {
    if (e.target.classList.contains("modal-overlay")) {
      e.target.classList.add("hidden");
    }
  });
}

function openModal(id) {
  document.getElementById(id).classList.remove("hidden");
}

function closeModal(id) {
  document.getElementById(id).classList.add("hidden");
}
