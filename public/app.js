/**
 * Social Sphere — Frontend Application Logic
 */

// Application State
const state = {
  activeTab: "explorer",
  page: 1,
  limit: 25,
  total: 0,
  totalPages: 1,
  scholars: [],
  filters: {
    q: "",
    institution: "all",
    wiki_status: "all",
    email_status: "all",
    missing_section: "all",
    sort_by: "citations",
    sort_dir: "desc"
  },
  viewMode: "table", // table or grid
  selectedScholar: null,
  activeScanId: null,
  scanEventSource: null
};

// DOM Elements Cache
const DOM = {
  // Navigation
  tabs: document.querySelectorAll(".nav-tab"),
  panes: document.querySelectorAll(".tab-pane"),
  statusPill: document.getElementById("statusPill"),
  statusText: document.getElementById("statusText"),
  btnExportTop: document.getElementById("btnExportTop"),

  // KPIs
  statTotalScholars: document.getElementById("statTotalScholars"),
  statVerifiedEmails: document.getElementById("statVerifiedEmails"),
  statWikiOpportunities: document.getElementById("statWikiOpportunities"),
  statMissingSections: document.getElementById("statMissingSections"),

  // Filters & Search
  searchInput: document.getElementById("searchInput"),
  clearSearchBtn: document.getElementById("clearSearchBtn"),
  filterInstitution: document.getElementById("filterInstitution"),
  filterWiki: document.getElementById("filterWiki"),
  filterEmail: document.getElementById("filterEmail"),
  filterMissing: document.getElementById("filterMissing"),
  sortBy: document.getElementById("sortBy"),
  btnViewTable: document.getElementById("btnViewTable"),
  btnViewGrid: document.getElementById("btnViewGrid"),
  btnResetFilters: document.getElementById("btnResetFilters"),
  resultsCount: document.getElementById("resultsCount"),

  // Viewports
  tableView: document.getElementById("tableView"),
  gridView: document.getElementById("gridView"),
  scholarsTableBody: document.getElementById("scholarsTableBody"),
  emptyState: document.getElementById("emptyState"),
  paginationBar: document.getElementById("paginationBar"),
  paginationInfo: document.getElementById("paginationInfo"),
  pageNumbers: document.getElementById("pageNumbers"),
  btnPrevPage: document.getElementById("btnPrevPage"),
  btnNextPage: document.getElementById("btnNextPage"),

  // Scanner Tab
  scannerForm: document.getElementById("scannerForm"),
  scanQuery: document.getElementById("scanQuery"),
  scanMinCitations: document.getElementById("scanMinCitations"),
  scanMinHIndex: document.getElementById("scanMinHIndex"),
  btnStartScan: document.getElementById("btnStartScan"),
  scanProgressBox: document.getElementById("scanProgressBox"),
  scanProgressBar: document.getElementById("scanProgressBar"),
  scanProgressPercent: document.getElementById("scanProgressPercent"),
  scanStatusBadge: document.getElementById("scanStatusBadge"),
  terminalLogs: document.getElementById("terminalLogs"),
  btnClearTerminal: document.getElementById("btnClearTerminal"),
  scannedResultsContainer: document.getElementById("scannedResultsContainer"),
  newLeadsBody: document.getElementById("newLeadsBody"),

  // Auditor Tab
  auditorForm: document.getElementById("auditorForm"),
  auditorInput: document.getElementById("auditorInput"),
  btnRunAudit: document.getElementById("btnRunAudit"),
  auditResultCard: document.getElementById("auditResultCard"),
  auditTitle: document.getElementById("auditTitle"),
  auditLink: document.getElementById("auditLink"),
  auditScore: document.getElementById("auditScore"),
  auditSectionsList: document.getElementById("auditSectionsList"),
  auditWarningsBox: document.getElementById("auditWarningsBox"),
  btnAuditPitch: document.getElementById("btnAuditPitch"),

  // Modals
  scholarModal: document.getElementById("scholarModal"),
  btnCloseScholarModal: document.getElementById("btnCloseScholarModal"),
  modalScholarName: document.getElementById("modalScholarName"),
  modalScholarInst: document.getElementById("modalScholarInst"),
  modalCitations: document.getElementById("modalCitations"),
  modalHIndex: document.getElementById("modalHIndex"),
  modalWikiStatus: document.getElementById("modalWikiStatus"),
  modalEmail: document.getElementById("modalEmail"),
  btnCopyModalEmail: document.getElementById("btnCopyModalEmail"),
  modalSummary: document.getElementById("modalSummary"),
  modalMissingSections: document.getElementById("modalMissingSections"),
  modalAssessmentSection: document.getElementById("modalAssessmentSection"),
  modalAssessment: document.getElementById("modalAssessment"),
  modalWikiLink: document.getElementById("modalWikiLink"),
  btnModalGeneratePitch: document.getElementById("btnModalGeneratePitch"),

  // Pitch Modal
  pitchModal: document.getElementById("pitchModal"),
  btnClosePitchModal: document.getElementById("btnClosePitchModal"),
  pitchRecipient: document.getElementById("pitchRecipient"),
  pitchSubject: document.getElementById("pitchSubject"),
  pitchBody: document.getElementById("pitchBody"),
  btnCopyPitchBody: document.getElementById("btnCopyPitchBody"),
  btnMailtoPitch: document.getElementById("btnMailtoPitch"),

  // Toast
  toastContainer: document.getElementById("toastContainer")
};

// ----------------- Initialization -----------------

document.addEventListener("DOMContentLoaded", () => {
  initEventListeners();
  loadStats();
  loadInstitutions();
  loadScholars();
});

function initEventListeners() {
  // Navigation Tabs
  DOM.tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.tab;
      switchTab(target);
    });
  });

  // Search input with debounce
  let searchTimeout = null;
  DOM.searchInput.addEventListener("input", (e) => {
    clearTimeout(searchTimeout);
    DOM.clearSearchBtn.style.display = e.target.value ? "block" : "none";
    searchTimeout = setTimeout(() => {
      state.filters.q = e.target.value.trim();
      state.page = 1;
      loadScholars();
    }, 300);
  });

  DOM.clearSearchBtn.addEventListener("click", () => {
    DOM.searchInput.value = "";
    DOM.clearSearchBtn.style.display = "none";
    state.filters.q = "";
    state.page = 1;
    loadScholars();
  });

  // Keyboard shortcut '/' to focus search
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== DOM.searchInput && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") {
      e.preventDefault();
      switchTab("explorer");
      DOM.searchInput.focus();
    }
  });

  // Filter Dropdowns
  DOM.filterInstitution.addEventListener("change", (e) => {
    state.filters.institution = e.target.value;
    state.page = 1;
    loadScholars();
  });

  DOM.filterWiki.addEventListener("change", (e) => {
    state.filters.wiki_status = e.target.value;
    state.page = 1;
    loadScholars();
  });

  DOM.filterEmail.addEventListener("change", (e) => {
    state.filters.email_status = e.target.value;
    state.page = 1;
    loadScholars();
  });

  DOM.filterMissing.addEventListener("change", (e) => {
    state.filters.missing_section = e.target.value;
    state.page = 1;
    loadScholars();
  });

  DOM.sortBy.addEventListener("change", (e) => {
    state.filters.sort_by = e.target.value;
    state.filters.sort_dir = e.target.value === "citations" ? "desc" : "asc";
    state.page = 1;
    loadScholars();
  });

  // View Mode Toggles
  DOM.btnViewTable.addEventListener("click", () => setViewMode("table"));
  DOM.btnViewGrid.addEventListener("click", () => setViewMode("grid"));

  // Reset Filters
  DOM.btnResetFilters.addEventListener("click", resetFilters);

  // Pagination
  DOM.btnPrevPage.addEventListener("click", () => {
    if (state.page > 1) {
      state.page--;
      loadScholars();
    }
  });

  DOM.btnNextPage.addEventListener("click", () => {
    if (state.page < state.totalPages) {
      state.page++;
      loadScholars();
    }
  });

  // Export CSV
  DOM.btnExportTop.addEventListener("click", handleExportCsv);

  // Live Scanner Form
  DOM.scannerForm.addEventListener("submit", handleStartScan);
  DOM.btnClearTerminal.addEventListener("click", () => {
    DOM.terminalLogs.innerHTML = `<div class="terminal-line system">[SYSTEM] Console cleared.</div>`;
  });

  // Live Auditor Form
  DOM.auditorForm.addEventListener("submit", handleRunAudit);
  DOM.btnAuditPitch.addEventListener("click", () => {
    if (state.lastAudited) {
      openPitchModal({
        name: state.lastAudited.title,
        wikipedia_url: state.lastAudited.wikipedia_url,
        is_wiki: 1,
        missing_sections: state.lastAudited.missing_sections
      });
    }
  });

  // Modals Close handlers
  DOM.btnCloseScholarModal.addEventListener("click", () => closeModal(DOM.scholarModal));
  DOM.btnClosePitchModal.addEventListener("click", () => closeModal(DOM.pitchModal));

  DOM.scholarModal.addEventListener("click", (e) => {
    if (e.target === DOM.scholarModal) closeModal(DOM.scholarModal);
  });
  DOM.pitchModal.addEventListener("click", (e) => {
    if (e.target === DOM.pitchModal) closeModal(DOM.pitchModal);
  });

  // Modal actions
  DOM.btnCopyModalEmail.addEventListener("click", () => {
    if (state.selectedScholar && state.selectedScholar.email) {
      copyToClipboard(state.selectedScholar.email, "Email address copied to clipboard!");
    }
  });

  DOM.btnModalGeneratePitch.addEventListener("click", () => {
    if (state.selectedScholar) {
      closeModal(DOM.scholarModal);
      openPitchModal(state.selectedScholar);
    }
  });

  DOM.btnCopyPitchBody.addEventListener("click", () => {
    copyToClipboard(DOM.pitchBody.value, "Pitch email copied to clipboard!");
  });
}

// ----------------- Tab Navigation -----------------

function switchTab(targetTab) {
  state.activeTab = targetTab;
  DOM.tabs.forEach(tab => {
    tab.classList.toggle("active", tab.dataset.tab === targetTab);
  });
  DOM.panes.forEach(pane => {
    pane.classList.toggle("active", pane.id === `pane${capitalize(targetTab)}`);
  });
}

function setViewMode(mode) {
  state.viewMode = mode;
  DOM.btnViewTable.classList.toggle("active", mode === "table");
  DOM.btnViewGrid.classList.toggle("active", mode === "grid");

  if (mode === "table") {
    DOM.tableView.style.display = "block";
    DOM.gridView.style.display = "none";
  } else {
    DOM.tableView.style.display = "none";
    DOM.gridView.style.display = "grid";
  }
}

// ----------------- API Calls -----------------

async function loadStats() {
  try {
    const res = await fetch("/api/stats");
    if (!res.ok) throw new Error("Stats request failed");
    const data = await res.json();

    DOM.statTotalScholars.textContent = data.total_scholars.toLocaleString();
    DOM.statVerifiedEmails.textContent = data.with_email.toLocaleString();
    DOM.statWikiOpportunities.textContent = data.wiki_opportunities.toLocaleString();
    DOM.statMissingSections.textContent = data.with_missing_sections.toLocaleString();

    DOM.statusText.textContent = `Live Database: ${data.total_scholars.toLocaleString()} Scholars`;
    DOM.statusPill.style.borderColor = "rgba(16, 185, 129, 0.4)";
  } catch (err) {
    console.error("Error loading stats:", err);
    DOM.statusText.textContent = "Offline (Local DB)";
  }
}

async function loadInstitutions() {
  try {
    const res = await fetch("/api/institutions");
    if (!res.ok) return;
    const items = await res.json();

    DOM.filterInstitution.innerHTML = `<option value="all">All Universities</option>`;
    items.forEach(inst => {
      const opt = document.createElement("option");
      opt.value = inst.name;
      opt.textContent = `${inst.name} (${inst.count})`;
      DOM.filterInstitution.appendChild(opt);
    });
  } catch (err) {
    console.error("Error loading institutions:", err);
  }
}

async function loadScholars() {
  DOM.scholarsTableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 3rem; color: #94A3B8;">Loading matching profiles...</td></tr>`;
  DOM.gridView.innerHTML = `<div style="text-align: center; grid-column: 1/-1; padding: 3rem; color: #94A3B8;">Loading matching profiles...</div>`;

  const params = new URLSearchParams({
    page: state.page,
    limit: state.limit,
    sort_by: state.filters.sort_by,
    sort_dir: state.filters.sort_dir
  });

  if (state.filters.q) params.set("q", state.filters.q);
  if (state.filters.institution !== "all") params.set("institution", state.filters.institution);
  if (state.filters.wiki_status !== "all") params.set("wiki_status", state.filters.wiki_status);
  if (state.filters.email_status !== "all") params.set("email_status", state.filters.email_status);
  if (state.filters.missing_section !== "all") params.set("missing_section", state.filters.missing_section);

  try {
    const res = await fetch(`/api/scholars?${params.toString()}`);
    if (!res.ok) throw new Error("Scholars request failed");
    const data = await res.json();

    state.scholars = data.scholars;
    state.total = data.total;
    state.totalPages = data.total_pages;

    renderScholars();
    renderPagination();
  } catch (err) {
    console.error("Error loading scholars:", err);
    DOM.scholarsTableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem; color: #F87171;">Error loading data from server.</td></tr>`;
  }
}

// ----------------- Rendering -----------------

function renderScholars() {
  DOM.resultsCount.textContent = `Found ${state.total.toLocaleString()} scholar profiles`;

  if (state.scholars.length === 0) {
    DOM.tableView.style.display = "none";
    DOM.gridView.style.display = "none";
    DOM.emptyState.style.display = "flex";
    DOM.paginationBar.style.display = "none";
    return;
  }

  DOM.emptyState.style.display = "none";
  DOM.paginationBar.style.display = "flex";

  if (state.viewMode === "table") {
    DOM.tableView.style.display = "block";
    DOM.gridView.style.display = "none";
  } else {
    DOM.tableView.style.display = "none";
    DOM.gridView.style.display = "grid";
  }

  // 1. Render Table Rows
  DOM.scholarsTableBody.innerHTML = "";
  state.scholars.forEach(s => {
    const tr = document.createElement("tr");

    // Metrics pills
    const citationsPill = s.citations > 0 
      ? `<span class="metric-pill ${s.citations >= 10000 ? 'high' : ''}">Citations: ${s.citations.toLocaleString()}</span>` 
      : '';
    const hIndexPill = s.h_index > 0 
      ? `<span class="metric-pill">h-index: ${s.h_index}</span>` 
      : '';

    // Email cell
    const emailCell = s.email && s.email !== "Not found"
      ? `<span class="email-pill" onclick="copyToClipboard('${escapeJs(s.email)}', 'Copied ${escapeJs(s.email)}')">
           <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path></svg>
           ${escapeHtml(s.email)}
         </span>`
      : `<span class="email-pill not-found">No Email Found</span>`;

    // Wiki badge
    const wikiBadge = s.is_wiki && s.wikipedia_url
      ? `<a href="${escapeHtml(s.wikipedia_url)}" target="_blank" rel="noopener" class="badge-wiki live">
           <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
           Has Wikipedia
         </a>`
      : `<span class="badge-wiki missing">
           <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
           No Wiki Page (Opportunity)
         </span>`;

    // Missing sections tags
    let missingHtml = `<span class="tag-ok">Complete / None Flagged</span>`;
    if (s.missing_sections && s.missing_sections.length > 0) {
      missingHtml = `<div class="missing-tag-group">` + 
        s.missing_sections.slice(0, 3).map(m => `<span class="tag-missing">${escapeHtml(m)}</span>`).join("") +
        (s.missing_sections.length > 3 ? `<span class="tag-ok">+${s.missing_sections.length - 3} more</span>` : "") +
        `</div>`;
    }

    tr.innerHTML = `
      <td>
        <div class="scholar-title-cell">
          <a class="scholar-name-link" onclick="openScholarModal(${s.id})">${escapeHtml(s.name)}</a>
          <div class="metrics-pills">
            ${citationsPill}
            ${hIndexPill}
          </div>
        </div>
      </td>
      <td class="inst-cell">${escapeHtml(s.institution)}</td>
      <td>${emailCell}</td>
      <td>${wikiBadge}</td>
      <td>${missingHtml}</td>
      <td>
        <div class="row-actions">
          <button class="action-icon-btn" onclick="openScholarModal(${s.id})" title="View Full Profile">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
          </button>
          <button class="action-icon-btn" onclick="triggerPitchForScholar(${s.id})" title="Generate Cold Outreach Pitch">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
          </button>
        </div>
      </td>
    `;
    DOM.scholarsTableBody.appendChild(tr);
  });

  // 2. Render Grid Cards
  DOM.gridView.innerHTML = "";
  state.scholars.forEach(s => {
    const card = document.createElement("div");
    card.className = "scholar-card glass-panel";

    const citationsPill = s.citations > 0 
      ? `<span class="metric-pill ${s.citations >= 10000 ? 'high' : ''}">Citations: ${s.citations.toLocaleString()}</span>` 
      : '';
    const hIndexPill = s.h_index > 0 
      ? `<span class="metric-pill">h-index: ${s.h_index}</span>` 
      : '';

    const wikiBadge = s.is_wiki && s.wikipedia_url
      ? `<a href="${escapeHtml(s.wikipedia_url)}" target="_blank" rel="noopener" class="badge-wiki live">Wiki Live</a>`
      : `<span class="badge-wiki missing">No Wiki Page</span>`;

    const emailBtn = s.email && s.email !== "Not found"
      ? `<span class="email-pill" onclick="copyToClipboard('${escapeJs(s.email)}', 'Email copied!')">${escapeHtml(s.email)}</span>`
      : `<span class="email-pill not-found">Pending Email</span>`;

    card.innerHTML = `
      <div>
        <div class="card-top">
          <div>
            <h3 class="scholar-name-link" onclick="openScholarModal(${s.id})">${escapeHtml(s.name)}</h3>
            <span class="card-inst">${escapeHtml(s.institution)}</span>
          </div>
          ${wikiBadge}
        </div>
        <div class="metrics-pills" style="margin: 0.75rem 0;">
          ${citationsPill}
          ${hIndexPill}
        </div>
        <p class="card-bio-snippet">${escapeHtml(s.summary || "No biography available.")}</p>
      </div>

      <div style="border-top: 1px solid var(--border-subtle); padding-top: 0.85rem; display: flex; align-items: center; justify-content: space-between;">
        ${emailBtn}
        <button class="btn btn-secondary btn-sm" onclick="triggerPitchForScholar(${s.id})">Pitch</button>
      </div>
    `;
    DOM.gridView.appendChild(card);
  });
}

function renderPagination() {
  const start = (state.page - 1) * state.limit + 1;
  const end = Math.min(state.page * state.limit, state.total);
  DOM.paginationInfo.textContent = `Showing ${start.toLocaleString()} - ${end.toLocaleString()} of ${state.total.toLocaleString()}`;

  DOM.btnPrevPage.disabled = state.page <= 1;
  DOM.btnNextPage.disabled = state.page >= state.totalPages;

  // Render page number buttons
  DOM.pageNumbers.innerHTML = "";
  const total = state.totalPages;
  const cur = state.page;

  let pages = [];
  if (total <= 7) {
    for (let i = 1; i <= total; i++) pages.push(i);
  } else {
    pages.push(1);
    if (cur > 3) pages.push("...");
    const pStart = Math.max(2, cur - 1);
    const pEnd = Math.min(total - 1, cur + 1);
    for (let i = pStart; i <= pEnd; i++) pages.push(i);
    if (cur < total - 2) pages.push("...");
    pages.push(total);
  }

  pages.forEach(p => {
    if (p === "...") {
      const span = document.createElement("span");
      span.style.padding = "0 0.35rem";
      span.style.color = "var(--text-dim)";
      span.textContent = "...";
      DOM.pageNumbers.appendChild(span);
    } else {
      const btn = document.createElement("button");
      btn.className = `page-btn ${p === cur ? 'active' : ''}`;
      btn.textContent = p;
      btn.addEventListener("click", () => {
        state.page = p;
        loadScholars();
      });
      DOM.pageNumbers.appendChild(btn);
    }
  });
}

function resetFilters() {
  DOM.searchInput.value = "";
  DOM.clearSearchBtn.style.display = "none";
  DOM.filterInstitution.value = "all";
  DOM.filterWiki.value = "all";
  DOM.filterEmail.value = "all";
  DOM.filterMissing.value = "all";
  DOM.sortBy.value = "citations";

  state.filters = {
    q: "",
    institution: "all",
    wiki_status: "all",
    email_status: "all",
    missing_section: "all",
    sort_by: "citations",
    sort_dir: "desc"
  };
  state.page = 1;
  loadScholars();
}

// ----------------- Scholar Detail Modal -----------------

async function openScholarModal(scholarId) {
  let s = state.scholars.find(x => x.id === scholarId);
  if (!s) {
    try {
      const res = await fetch(`/api/scholars/${scholarId}`);
      if (!res.ok) return;
      s = await res.json();
    } catch (err) {
      return;
    }
  }

  state.selectedScholar = s;

  DOM.modalScholarName.textContent = s.name;
  DOM.modalScholarInst.textContent = s.institution;
  DOM.modalCitations.textContent = s.citations > 0 ? s.citations.toLocaleString() : "N/A";
  DOM.modalHIndex.textContent = s.h_index > 0 ? s.h_index : "N/A";
  DOM.modalWikiStatus.textContent = s.is_wiki ? "Has Article" : "Missing Article";
  DOM.modalWikiStatus.style.color = s.is_wiki ? "var(--accent-emerald)" : "var(--accent-amber)";

  DOM.modalEmail.textContent = s.email && s.email !== "Not found" ? s.email : "No contact email discovered";
  DOM.modalSummary.textContent = s.summary || "No biographical information available.";

  // Missing sections
  DOM.modalMissingSections.innerHTML = "";
  if (s.missing_sections && s.missing_sections.length > 0) {
    s.missing_sections.forEach(m => {
      const tag = document.createElement("span");
      tag.className = "tag-missing";
      tag.textContent = m;
      DOM.modalMissingSections.appendChild(tag);
    });
  } else {
    DOM.modalMissingSections.innerHTML = `<span class="tag-ok">No missing sections flagged.</span>`;
  }

  // Assessment
  if (s.assessment) {
    DOM.modalAssessmentSection.style.display = "block";
    DOM.modalAssessment.textContent = s.assessment;
  } else {
    DOM.modalAssessmentSection.style.display = "none";
  }

  if (s.wikipedia_url && s.wikipedia_url !== "N/A") {
    DOM.modalWikiLink.style.display = "inline-flex";
    DOM.modalWikiLink.href = s.wikipedia_url;
  } else {
    DOM.modalWikiLink.style.display = "none";
  }

  openModal(DOM.scholarModal);
}

// ----------------- Pitch Generator -----------------

function triggerPitchForScholar(scholarId) {
  const s = state.scholars.find(x => x.id === scholarId);
  if (s) {
    openPitchModal(s);
  }
}

async function openPitchModal(scholar) {
  DOM.pitchRecipient.value = scholar.email && scholar.email !== "Not found" ? scholar.email : `Faculty Communications for ${scholar.name}`;
  DOM.pitchSubject.value = "Generating personalized proposal...";
  DOM.pitchBody.value = "Analyzing scholar achievements, citations, and Wikipedia guidelines...";
  openModal(DOM.pitchModal);

  try {
    const res = await fetch("/api/pitch/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scholar_id: scholar.id,
        name: scholar.name,
        institution: scholar.institution,
        citations: scholar.citations,
        h_index: scholar.h_index,
        wikipedia_url: scholar.wikipedia_url,
        is_wiki: scholar.is_wiki ? 1 : 0,
        email: scholar.email,
        missing_sections: scholar.missing_sections || []
      })
    });

    if (!res.ok) throw new Error("Pitch generation failed");
    const data = await res.json();

    DOM.pitchSubject.value = data.subject;
    DOM.pitchBody.value = data.body;

    const emailDest = scholar.email && scholar.email !== "Not found" ? scholar.email : "";
    const mailtoUrl = `mailto:${encodeURIComponent(emailDest)}?subject=${encodeURIComponent(data.subject)}&body=${encodeURIComponent(data.body)}`;
    DOM.btnMailtoPitch.href = mailtoUrl;

  } catch (err) {
    console.error("Pitch error:", err);
    DOM.pitchSubject.value = `Wikipedia Biography Proposal for ${scholar.name}`;
    DOM.pitchBody.value = `Dear Professor ${scholar.name},\n\nWe would love to discuss creating/expanding your official Wikipedia biography.`;
  }
}

// ----------------- Live Scanner -----------------

async function handleStartScan(e) {
  e.preventDefault();
  const query = DOM.scanQuery.value.trim();
  const minCitations = parseInt(DOM.scanMinCitations.value, 10) || 10000;
  const minHIndex = parseInt(DOM.scanMinHIndex.value, 10) || 40;

  if (!query) return;

  DOM.btnStartScan.disabled = true;
  DOM.btnStartScan.innerHTML = `<span class="status-dot"></span> Scanning...`;
  DOM.scanProgressBox.style.display = "block";
  DOM.scanProgressBar.style.width = "5%";
  DOM.scanProgressPercent.textContent = "5%";
  DOM.scanStatusBadge.textContent = "Starting background scan...";
  DOM.scannedResultsContainer.style.display = "none";
  DOM.newLeadsBody.innerHTML = "";

  appendTerminalLog(`[INIT] Starting background scan task for query: "${query}"`, "info");

  try {
    const res = await fetch("/api/scan/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: query,
        min_citations: minCitations,
        min_h_index: minHIndex
      })
    });

    if (!res.ok) throw new Error("Failed to start scan");
    const data = await res.json();

    state.activeScanId = data.scan_id;
    appendTerminalLog(`[DISPATCH] Scan worker assigned task ID: ${data.scan_id}`, "success");

    // Connect to Server-Sent Events (SSE) for live stream
    startLogStream(data.scan_id);

  } catch (err) {
    console.error("Scan start error:", err);
    appendTerminalLog(`[ERROR] Could not start scan: ${err.message}`, "error");
    DOM.btnStartScan.disabled = false;
    DOM.btnStartScan.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Start Background Scan`;
  }
}

function startLogStream(scanId) {
  if (state.scanEventSource) {
    state.scanEventSource.close();
  }

  // Use EventSource for real-time SSE stream
  const eventSource = new EventSource(`/api/scan/logs/${scanId}`);
  state.scanEventSource = eventSource;

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.msg === "END_OF_STREAM") {
        eventSource.close();
        handleScanComplete(scanId);
        return;
      }
      appendTerminalLog(`[${data.time}] ${data.msg}`, data.level || "info");

      // Poll progress
      checkScanProgress(scanId);
    } catch (e) {
      console.error("SSE parse error", e);
    }
  };

  eventSource.onerror = () => {
    eventSource.close();
    // Fallback to polling
    pollScanStatus(scanId);
  };
}

async function checkScanProgress(scanId) {
  try {
    const res = await fetch(`/api/scan/status/${scanId}`);
    if (res.ok) {
      const data = await res.json();
      DOM.scanProgressBar.style.width = `${data.progress}%`;
      DOM.scanProgressPercent.textContent = `${data.progress}%`;
      DOM.scanStatusBadge.textContent = data.status === "completed" ? "Completed" : "Running...";

      if (data.found_scholars && data.found_scholars.length > 0) {
        renderNewLeads(data.found_scholars);
      }
    }
  } catch (e) {}
}

async function pollScanStatus(scanId) {
  const interval = setInterval(async () => {
    try {
      const res = await fetch(`/api/scan/status/${scanId}`);
      if (!res.ok) {
        clearInterval(interval);
        return;
      }
      const data = await res.json();
      DOM.scanProgressBar.style.width = `${data.progress}%`;
      DOM.scanProgressPercent.textContent = `${data.progress}%`;

      if (data.found_scholars && data.found_scholars.length > 0) {
        renderNewLeads(data.found_scholars);
      }

      if (data.status === "completed" || data.status === "error") {
        clearInterval(interval);
        handleScanComplete(scanId);
      }
    } catch (err) {
      clearInterval(interval);
    }
  }, 1500);
}

function handleScanComplete(scanId) {
  DOM.btnStartScan.disabled = false;
  DOM.btnStartScan.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Start Background Scan`;
  DOM.scanProgressBar.style.width = "100%";
  DOM.scanProgressPercent.textContent = "100%";
  DOM.scanStatusBadge.textContent = "Scan Completed";
  showToast("Live academic scan finished successfully!", "success");

  // Refresh main dataset & KPIs
  loadStats();
  loadScholars();
}

function renderNewLeads(leads) {
  DOM.scannedResultsContainer.style.display = "block";
  DOM.newLeadsBody.innerHTML = "";
  leads.forEach(l => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${escapeHtml(l.name)}</strong></td>
      <td>${l.citations ? l.citations.toLocaleString() : 'N/A'}</td>
      <td>${l.h_index || 'N/A'}</td>
      <td>${l.email ? `<span class="email-pill">${escapeHtml(l.email)}</span>` : '<span class="email-pill not-found">Pending</span>'}</td>
      <td>${l.wikipedia_url ? `<a href="${escapeHtml(l.wikipedia_url)}" target="_blank" rel="noopener" class="wiki-ext-link">Wiki Link</a>` : '<span class="badge-wiki missing">No Page</span>'}</td>
      <td>
        <button class="btn btn-secondary btn-sm" onclick="openPitchModal({name: '${escapeJs(l.name)}', citations: ${l.citations}, h_index: ${l.h_index}, email: '${escapeJs(l.email)}', is_wiki: ${l.is_wiki}})">
          Pitch
        </button>
      </td>
    `;
    DOM.newLeadsBody.appendChild(tr);
  });
}

function appendTerminalLog(message, level = "info") {
  const line = document.createElement("div");
  line.className = `terminal-line ${level}`;
  line.textContent = message;
  DOM.terminalLogs.appendChild(line);
  DOM.terminalLogs.scrollTop = DOM.terminalLogs.scrollHeight;
}

// ----------------- Live Wikipedia Auditor -----------------

async function handleRunAudit(e) {
  e.preventDefault();
  const query = DOM.auditorInput.value.trim();
  if (!query) return;

  DOM.btnRunAudit.disabled = true;
  DOM.btnRunAudit.textContent = "Auditing MediaWiki...";

  try {
    const res = await fetch("/api/wiki/audit-live", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query })
    });

    if (!res.ok) throw new Error("Audit request failed");
    const data = await res.json();

    if (!data.success) {
      showToast(data.error || "Profile not found on Wikipedia", "error");
      DOM.btnRunAudit.disabled = false;
      DOM.btnRunAudit.textContent = "Audit Page Live";
      return;
    }

    state.lastAudited = data;

    DOM.auditResultCard.style.display = "block";
    DOM.auditTitle.textContent = data.title;
    DOM.auditLink.href = data.wikipedia_url;
    DOM.auditScore.textContent = `${data.completeness_score}/100`;

    // Sections checklist
    DOM.auditSectionsList.innerHTML = "";
    if (data.found_sections) {
      data.found_sections.forEach(sec => {
        const item = document.createElement("div");
        item.className = "check-item";
        item.innerHTML = `<span class="check-icon found">✓</span> <span>${escapeHtml(sec)}</span>`;
        DOM.auditSectionsList.appendChild(item);
      });
    }
    if (data.missing_sections) {
      data.missing_sections.forEach(sec => {
        const item = document.createElement("div");
        item.className = "check-item";
        item.innerHTML = `<span class="check-icon missing">✕</span> <span><strong>Missing:</strong> ${escapeHtml(sec)}</span>`;
        DOM.auditSectionsList.appendChild(item);
      });
    }

    // Warnings
    DOM.auditWarningsBox.innerHTML = `
      <p><strong>Infobox Status:</strong> ${data.has_infobox ? '<span style="color: #34D399;">Present</span>' : '<span style="color: #F87171;">Missing Infobox Template</span>'}</p>
      <p style="margin-top: 0.5rem;"><strong>Assessment:</strong> ${escapeHtml(data.recommendation)}</p>
      ${data.warnings && data.warnings.length > 0 ? `<p style="margin-top: 0.5rem; color: #FBBF24;"><strong>Templates Flagged:</strong> ${escapeHtml(data.warnings.join(", "))}</p>` : ''}
    `;

    DOM.btnRunAudit.disabled = false;
    DOM.btnRunAudit.textContent = "Audit Page Live";
    showToast("Wikipedia page audit complete!", "success");

  } catch (err) {
    console.error("Audit error:", err);
    showToast("Audit failed: " + err.message, "error");
    DOM.btnRunAudit.disabled = false;
    DOM.btnRunAudit.textContent = "Audit Page Live";
  }
}

// ----------------- Export CSV -----------------

function handleExportCsv() {
  const params = new URLSearchParams();
  if (state.filters.q) params.set("q", state.filters.q);
  if (state.filters.institution !== "all") params.set("institution", state.filters.institution);
  if (state.filters.wiki_status !== "all") params.set("wiki_status", state.filters.wiki_status);
  if (state.filters.email_status !== "all") params.set("email_status", state.filters.email_status);
  if (state.filters.missing_section !== "all") params.set("missing_section", state.filters.missing_section);

  showToast("Preparing CSV export download...", "info");
  window.location.href = `/api/export?${params.toString()}`;
}

// ----------------- Helpers & Utilities -----------------

function openModal(modalEl) {
  modalEl.style.display = "flex";
  document.body.style.overflow = "hidden";
}

function closeModal(modalEl) {
  modalEl.style.display = "none";
  document.body.style.overflow = "auto";
}

function copyToClipboard(text, successMsg = "Copied to clipboard!") {
  navigator.clipboard.writeText(text).then(() => {
    showToast(successMsg, "success");
  }).catch(() => {
    showToast("Failed to copy", "error");
  });
}

function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span class="status-dot" style="${type === 'success' ? 'background: #10B981;' : type === 'error' ? 'background: #EF4444;' : 'background: #6366F1;'}"></span>
    <span>${escapeHtml(message)}</span>
  `;
  DOM.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(10px)";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeJs(str) {
  if (!str) return "";
  return String(str).replace(/'/g, "\\'").replace(/"/g, '\\"');
}

function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}
