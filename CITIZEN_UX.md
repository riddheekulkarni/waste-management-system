# EcoClean Civic — Citizen Experience & Guided Reporting Architecture (Phase 5)

This document describes the Phase 5 citizen-facing frontend architecture, design system, guided reporting wizard, citizen dashboard, real-time SSE tracking, and accessibility considerations for EcoClean Civic.

---

## 1. Product Positioning & Direction

* **Product Name**: **EcoClean Civic**
* **Civic Positioning**: *"Cleaner streets. Smarter civic response."*
* **Core Citizen Narrative**:
  > *"Report a problem. Let AI understand it. Track what happens next."*
* **Design Philosophy**:
  * Clean, trustworthy, accessible, professional municipal platform.
  * Avoids noisy gaming aesthetics, heavy cyberpunk neon, excessive glassmorphism, or non-functional decorative clutter.
  * Direct, readable typography paired with subtle borders, muted civic surfaces, and high-contrast indicators.

---

## 2. Design System & Tokens

Defined via CSS custom properties in [`frontend/css/styles.css`](file:///c:/projects/waste-management-system/frontend/css/styles.css):

### 2.1 Color Tokens
* **Civic Primary**: Deep Slate Navy (`--civic-navy`: `#0f172a`, `--civic-slate`: `#1e293b`)
* **Civic Accent**: Eco Emerald (`--civic-emerald`: `#059669`, hover `#047857`, light tint `rgba(5, 150, 105, 0.12)`)
* **Civic Blue**: Municipal Action Blue (`--civic-blue`: `#2563eb`, light tint `rgba(37, 99, 235, 0.12)`)
* **Civic Amber**: Caution / Pending Triage (`--civic-amber`: `#d97706`)
* **Civic Red**: Urgent Hazard / Failure (`--civic-red`: `#dc2626`)
* **Surfaces**:
  * Dark Mode: Page `#0b0f19`, Surface `#111827`, Elevated `#1f2937`
  * Light Mode: Page `#f8fafc`, Surface `#ffffff`, Elevated `#f1f5f9`
* **Typography**: Primary typeface is *Plus Jakarta Sans* (weights 400, 500, 600, 700, 800) with system font fallbacks.

### 2.2 Reusable UI Components
* **Buttons**: `.btn-primary` (emerald CTA), `.btn-secondary` (surface neutral), `.btn-outline` (bordered), `.btn-header-cta`. Minimum touch target size 44x44px.
* **Cards**: `.civic-card`, `.step-card`, `.feature-card`, `.complaint-card`.
* **Badges**: `.badge-open`, `.badge-progress`, `.badge-resolved`, `.badge-failed`, `.badge-high`, `.badge-medium`, `.badge-low`.
* **Form Inputs**: Accessible inputs with visible focus rings (`--border-focus: #10b981`).
* **Empty & Loading States**: Clean empty states with icon and action button on all card grids and history tables.

---

## 3. Citizen User Journey

```text
1. Public Landing Page
   │ (Discovers capabilities, workflow, and transparency guarantees)
   ▼
2. Authentication (Citizen Sign In / Registration)
   │ (Single-field identifier, email, password visibility toggle)
   ▼
3. Citizen Dashboard
   │ (Inspects active reports, historical clearance, and municipal metrics)
   ▼
4. Guided 5-Step Reporting Wizard
   ├─► Step 1: Select Issue Category (Garbage, Overflow, Dumping, Debris, Hazmat, Green)
   ├─► Step 2: Choose Location (GPS Detect, Search Address, Interactive Leaflet Pin)
   ├─► Step 3: Upload Evidence (Mobile camera capture or drag-and-drop, client validation)
   ├─► Step 4: Add Helpful Details (Landmark notes, proximity directions)
   └─► Step 5: Review & Confirm (Photo thumbnail, address readout, landmark review)
   ▼
5. Real-Time AI Processing & Timeline (Step 6)
   │ (Subscribed to Server-Sent Events /api/complaints/<ticket_id>/events)
   ├─► ✓ Report Registered
   ├─► ● Analyzing Image (YOLOv8)
   ├─► ○ Calculating Severity
   ├─► ○ Checking Proximity Duplicates
   ├─► ○ Assigning Department
   └─► ✓ Verification Completed
   ▼
6. Tracking & Inspection
   │ (Inspects bounding box detections, department dispatch, and resolution timeline)
   └─► Closed when municipal team resolves issue on-site.
```

---

## 4. Guided Reporting Wizard Implementation

Located in `#report` section of [`frontend/index.html`](file:///c:/projects/waste-management-system/frontend/index.html) and managed by `setupWizard()` in [`frontend/js/app.js`](file:///c:/projects/waste-management-system/frontend/js/app.js):

1. **Step Stepper**: Visual node indicator updating `active` and `completed` states.
2. **Category Selection**: 6 interactive cards with icons and descriptions. Keyboard navigable via Enter/Space.
3. **Location Selection**:
   * "Detect My Location" utilizes browser `navigator.geolocation` and reverse-geocodes with Nominatim OpenStreetMap.
   * Address search bar centers map and places draggable marker.
   * Clicking anywhere on the Leaflet map relocates the pin and automatically fetches the street address.
   * Coordinates remain internal while a friendly street address is displayed.
4. **Photo Evidence Upload**:
   * File input with `accept="image/*"` and `capture="environment"` enables native mobile camera trigger.
   * Drag-and-drop support with visual highlight.
   * Live image preview with file size limit check (<16MB) and "Change Photo" button.
5. **Details**:
   * Optional landmark notes (e.g. "Opposite bus stop near pillar 42").
6. **Review Summary**:
   * Confirms category, location, landmark, and photo thumbnail before sending `POST /api/complaints/upload`.
7. **Real-Time Processing Stepper (Step 6)**:
   * Replaces static polling with live SSE stage progression.
   * Updates timeline dots dynamically as backend worker processes each stage.
   * Displays full verified result card upon completion.

---

## 5. Citizen Dashboard

Located in `#dashboard` section of [`frontend/index.html`](file:///c:/projects/waste-management-system/frontend/index.html) and loaded via `loadCitizenDashboard()`:
* **Metric Cards**: Dynamically aggregates:
  * Total Reports Submitted
  * Active / In Progress Reports
  * Resolved Issues
* **Active Complaints Cards**: Displays high-priority cards for tickets in `AI_PROCESSING`, `VERIFIED`, `ASSIGNED`, or `IN_PROGRESS`.
* **Report History Table**: Chronological table of all past complaints with status, department, and direct "Inspect" action.
* **Empty State**: Inviting empty state guiding citizens to submit their first report when no records exist.

---

## 6. Real-Time Tracking & Inspection

* Subscribes to `GET /api/complaints/<ticket_id>/events` via native browser `EventSource`.
* Updates stage indicators, severity ratings, and department dispatch in real time.
* If SSE disconnects or browser lacks `EventSource`, controlled fallback polling to `GET /api/complaints/<ticket_id>` activates at 2.5-second intervals (capped at 25 attempts, stopping immediately on terminal status).
* **Complaint Detail Inspection Modal**:
  * Lifecycle progress stepper: `SUBMITTED` $\rightarrow$ `AI_PROCESSING` $\rightarrow$ `VERIFIED` $\rightarrow$ `ASSIGNED` $\rightarrow$ `IN_PROGRESS` $\rightarrow$ `RESOLVED`.
  * Visual evidence toggles: "🎯 AI Bounding Boxes" vs "📷 Original Photo".
  * Interactive map showing incident coordinates.
  * AI detected items breakdown with confidence scores and coverage ratio.

---

## 7. Responsive & Accessibility Decisions

* **Responsive Design**:
  * Flexible grids using `repeat(auto-fit, minmax(...))` adapting from mobile (1 column) to tablet (2 columns) to desktop (3-4 columns).
  * Navigation switches to compact layout on screens narrower than 768px.
  * Wizard step indicator simplifies cleanly on mobile devices.
* **Accessibility (WCAG AA)**:
  * Visible focus outlines (`:focus-visible`) across all buttons, inputs, category cards, and links.
  * All interactive elements have descriptive `aria-label`, `role="button"`, and keyboard event handlers (`Enter` and `Space`).
  * Contrast ratios between text and background exceed 4.5:1 for normal text and 3:1 for large headings.
  * Modals include `role="dialog"`, `aria-modal="true"`, and `Escape` key close handlers.

---

## 8. Preserved Admin Portal

* The municipal operations center dashboard (`#admin`), stats metrics, Chart.js breakdown charts, incident map, filterable tickets table, and status PATCH actions remain 100% operational and untouched for Phase 6.
