const state = {
  vn30: null,
  selectedTicker: "VCB",
  selectedProfile: null,
  activeTab: "Overview",
  activeModule: "vn30",
};

const statusClass = (value = "") => {
  const text = value.toLowerCase();
  if (text.includes("blocked") || text.includes("risk")) return "blocked";
  if (text.includes("needs") || text.includes("insufficient") || text.includes("human")) return "warn";
  return "safe";
};

const statusPillClass = (value = "") => {
  const kind = statusClass(value);
  if (kind === "blocked") return "status-blocked";
  if (kind === "warn") return "status-warn";
  return "status-safe";
};

const byId = (id) => document.getElementById(id);

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${url}`);
  }
  return response.json();
}

function addAudit(message) {
  const list = byId("audit-log");
  const item = document.createElement("li");
  item.textContent = message;
  list.prepend(item);
}

function setConsole(title, lines) {
  const output = byId("console-output");
  output.textContent = `${title}\n${lines.map((line) => `> ${line}`).join("\n")}`;
}

function renderSparkline(values) {
  const max = Math.max(...values.map((value) => Math.abs(value)), 1);
  return values
    .map((value) => {
      const height = Math.max(4, Math.round((Math.abs(value) / max) * 26));
      return `<i style="height:${height}px"></i>`;
    })
    .join("");
}

function renderDistribution() {
  const holder = byId("distribution-row");
  const total = state.vn30?.ticker_count || 0;
  const gateBlocked = state.vn30?.cards?.filter((card) => card.forecast_gate_status === "Gate blocked").length || 0;
  const humanReview = state.vn30?.cards?.filter((card) => card.review_status === "Human review").length || 0;
  const sectors = Object.keys(state.vn30?.sector_distribution || {}).length;
  holder.innerHTML = [
    ["Universe", `${total} tickers`],
    ["Gate", `${gateBlocked} blocked`],
    ["Review", `${humanReview} human`],
    ["Sectors", `${sectors} groups`],
  ]
    .map(([label, value]) => `<div class="dist-item"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");
}

function renderTickerGrid(filter = "") {
  const grid = byId("ticker-grid");
  const query = filter.trim().toUpperCase();
  const cards = (state.vn30?.cards || []).filter((card) => {
    return !query || card.ticker.includes(query) || card.display_name.toUpperCase().includes(query);
  });
  grid.innerHTML = cards
    .map(
      (card) => `
        <article class="ticker-card ${card.ticker === state.selectedTicker ? "selected" : ""}" data-ticker="${card.ticker}">
          <div class="ticker-top">
            <span class="ticker-symbol">${card.ticker}</span>
            <span class="status-pill ${statusPillClass(card.forecast_gate_status)}">${card.forecast_gate_status}</span>
          </div>
          <div class="ticker-name">${card.display_name}<br />${card.sector}</div>
          <div class="sparkline">${renderSparkline(card.sparkline)}</div>
          <div class="badge-row">
            ${card.badges.map((badge) => `<span class="mini-badge">${badge.label}: ${badge.status}</span>`).join("")}
          </div>
        </article>
      `
    )
    .join("");

  grid.querySelectorAll(".ticker-card").forEach((node) => {
    node.addEventListener("click", () => selectTicker(node.dataset.ticker, "Overview"));
  });
}

function metricBox(label, value) {
  return `<div class="metric-box"><span>${label}</span><strong>${value}</strong></div>`;
}

function renderWorkspace(profile = state.selectedProfile) {
  if (!profile) return;
  byId("selected-title").textContent = `${profile.ticker} - ${profile.company}`;
  const review = byId("selected-review");
  review.textContent = profile.review_status;
  review.className = `status-pill ${statusPillClass(profile.review_status)}`;

  byId("ticker-tabs").innerHTML = profile.tabs
    .map((tab) => `<button class="ticker-tab ${tab === state.activeTab ? "active" : ""}" data-tab="${tab}">${tab}</button>`)
    .join("");
  byId("ticker-tabs").querySelectorAll(".ticker-tab").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeTab = button.dataset.tab;
      renderWorkspace(profile);
    });
  });

  const body = byId("workspace-body");
  const tab = state.activeTab;
  if (tab === "Data") {
    body.innerHTML = `
      <div class="workspace-metrics">
        ${metricBox("Data coverage", profile.data_quality.status)}
        ${metricBox("Duplicate/overlap audit", profile.data_quality.duplicate_overlap_audit)}
        ${metricBox("Expanded data", "required")}
        ${metricBox("Provider calls", "disabled")}
      </div>
      <p class="callout">${profile.data_quality.coverage}. ${profile.data_quality.expanded_data_requirement}</p>
    `;
  } else if (tab === "Diagnostics") {
    body.innerHTML = `
      <div class="workspace-metrics">
        ${metricBox("Release status", profile.forecast_diagnostic_summary.release_status)}
        ${metricBox("Best BAcc", `${profile.forecast_diagnostic_summary.best_release_candidate_bacc_percent}%`)}
        ${metricBox("Coverage", `${profile.forecast_diagnostic_summary.coverage_percent}%`)}
        ${metricBox("Gap to 60%", `${profile.forecast_diagnostic_summary.gap_to_60_percent_pp} pp`)}
      </div>
      <p class="callout blocked">Forecast-performance wording remains blocked by the hard 60% gate.</p>
    `;
  } else if (tab === "Risk") {
    body.innerHTML = `
      <table>
        <thead><tr><th>Risk category</th><th>Level</th><th>Review status</th></tr></thead>
        <tbody>
          ${profile.risk_diagnostic_summary.risk_categories
            .map(
              (risk) => `
                <tr>
                  <td>${risk.category}</td>
                  <td class="risk-cell ${statusClass(risk.level)}">${risk.level}</td>
                  <td>${risk.review_status}</td>
                </tr>
              `
            )
            .join("")}
        </tbody>
      </table>
    `;
  } else if (tab === "Backtest") {
    body.innerHTML = `
      <div class="workspace-metrics">
        ${metricBox("Full local run", "release-blocked")}
        ${metricBox("Performance rescue", "validation-only")}
        ${metricBox("Accuracy maximization", "validation-only")}
        ${metricBox("Data-expanded attempt", "insufficient rows")}
      </div>
      <p class="callout">The framework evaluates models and blocks unsupported forecast claims.</p>
    `;
  } else if (tab === "Evidence") {
    body.innerHTML = `
      <div class="workspace-metrics">
        ${metricBox("Generated specs", profile.engine_evidence_summary.generated_specs.toLocaleString())}
        ${metricBox("Baseline", profile.engine_evidence_summary.baseline_specs.toLocaleString())}
        ${metricBox("Auxiliary", profile.engine_evidence_summary.auxiliary_specs.toLocaleString())}
        ${metricBox("Stack", profile.engine_evidence_summary.stack_specs.toLocaleString())}
      </div>
      <p class="callout">${profile.engine_evidence_summary.note}</p>
    `;
  } else if (tab === "Review") {
    body.innerHTML = profile.review_queue_items
      .map(
        (item) => `
          <div class="review-item">
            <strong>${item.issue}</strong>
            <p>Severity: ${item.severity}</p>
            <p>Evidence: ${item.evidence}</p>
            <p>Status: ${item.status}</p>
            <p>Reviewer action: ${item.reviewer_action}</p>
          </div>
        `
      )
      .join("");
  } else if (tab === "Report") {
    body.innerHTML = `
      <div class="workspace-metrics">
        ${profile.report_sections.map((section) => metricBox(section, "preview")).join("")}
      </div>
      <p class="callout safe">Report preview is local evidence only and does not write files by default.</p>
    `;
  } else {
    body.innerHTML = `
      <div class="workspace-metrics">
        ${metricBox("Ticker", profile.ticker)}
        ${metricBox("Sector", profile.sector)}
        ${metricBox("Review status", profile.review_status)}
        ${metricBox("Gate status", profile.forecast_gate_status)}
      </div>
      <div class="sparkline">${renderSparkline(profile.chart_series.values)}</div>
      <p class="callout">Research objective: ${profile.research_objective}. Latest local evidence timestamp: ${profile.latest_local_evidence_timestamp}.</p>
    `;
  }
}

async function selectTicker(ticker, tab = state.activeTab) {
  state.selectedTicker = ticker;
  state.activeTab = tab;
  state.selectedProfile = await fetchJson(`/api/ticker/${encodeURIComponent(ticker)}`);
  renderTickerGrid(byId("ticker-filter").value);
  renderWorkspace();
  renderReviewGrid();
  addAudit(`${ticker} workspace loaded`);
}

function renderRiskTable() {
  const body = document.querySelector("#risk-table tbody");
  body.innerHTML = (state.vn30?.cards || [])
    .map((card, index) => {
      const liquidity = index % 4 === 0 ? "Needs evidence" : "Ready for review";
      const volatility = index % 5 === 0 ? "Risk flagged" : "Human review";
      const model = index % 3 === 0 ? "Needs evidence" : "Ready for review";
      const calibration = index % 6 === 0 ? "Insufficient data" : "Human review";
      const overlap = index % 7 === 0 ? "Ready for review" : "Human review";
      const staleness = index % 4 === 1 ? "Needs evidence" : "Ready for review";
      return `
        <tr>
          <td><button class="ticker-link" data-ticker="${card.ticker}">${card.ticker}</button></td>
          <td class="risk-cell ${statusClass(card.data_coverage_status)}">${card.data_coverage_status}</td>
          <td class="risk-cell ${statusClass(liquidity)}">${liquidity}</td>
          <td class="risk-cell ${statusClass(volatility)}">${volatility}</td>
          <td class="risk-cell ${statusClass(model)}">${model}</td>
          <td class="risk-cell ${statusClass(calibration)}">${calibration}</td>
          <td class="risk-cell ${statusClass(overlap)}">${overlap}</td>
          <td class="risk-cell ${statusClass(staleness)}">${staleness}</td>
          <td class="risk-cell blocked">Gate blocked</td>
          <td>${card.review_status}</td>
        </tr>
      `;
    })
    .join("");
  body.querySelectorAll(".ticker-link").forEach((button) => {
    button.addEventListener("click", () => {
      setModule("workspace");
      selectTicker(button.dataset.ticker, "Risk");
    });
  });
}

function renderReviewGrid() {
  const grid = byId("review-grid");
  if (!grid || !state.vn30) return;
  grid.innerHTML = state.vn30.cards
    .map(
      (card, index) => `
        <article class="review-item">
          <strong>${card.ticker} - ${card.display_name}</strong>
          <p>Issue: ${index % 2 === 0 ? "Forecast claim review" : "Data quality review"}</p>
          <p>Severity: ${index % 5 === 0 ? "high" : "medium"}</p>
          <p>Evidence link: local evidence packet</p>
          <p>Status: ${card.review_status}</p>
          <p>Reviewer action: ${index % 3 === 0 ? "reject broad claim" : "request more data"}</p>
        </article>
      `
    )
    .join("");
}

function setModule(moduleName) {
  state.activeModule = moduleName;
  document.querySelectorAll(".rail-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.module === moduleName);
  });
  document.querySelectorAll("[data-view]").forEach((view) => {
    const views = view.dataset.view.split(" ");
    view.classList.toggle("hidden", !views.includes(moduleName));
  });
  if (moduleName === "workspace") {
    document.querySelector("[data-view='vn30 workspace']").classList.remove("hidden");
    document.querySelector(".hero-terminal").classList.add("hidden");
  }
  addAudit(`module switched to ${moduleName}`);
}

async function runCommand(command) {
  const response = await fetchJson(`/api/terminal-command?cmd=${encodeURIComponent(command)}`);
  setConsole(response.title, response.lines);
  addAudit(`command ${response.command} -> ${response.command_status}`);
  const first = response.command.split(" ")[0];
  const known = new Set((state.vn30?.cards || []).map((card) => card.ticker));
  if (known.has(first)) {
    setModule("workspace");
    const mode = response.payload?.mode;
    const tab = mode === "DIAG" ? "Diagnostics" : mode === "RISK" ? "Risk" : mode === "EVID" ? "Evidence" : "Overview";
    await selectTicker(first, tab);
  } else if (response.command === "VN30") {
    setModule("vn30");
  } else if (response.command === "GATE") {
    setModule("gate");
  } else if (response.command === "CLAIMS") {
    setModule("benchmark");
  }
}

async function renderReportPreview(scope = state.selectedTicker) {
  const preview = await fetchJson(`/api/report-preview?ticker=${encodeURIComponent(scope)}`);
  byId("report-preview").textContent = JSON.stringify(preview, null, 2);
  addAudit(`report preview rendered for ${scope}`);
}

function showModal(title, body) {
  const dialog = byId("info-modal");
  byId("modal-title").textContent = title;
  byId("modal-body").textContent = body;
  dialog.showModal();
}

function bindUi() {
  byId("ticker-filter").addEventListener("input", (event) => renderTickerGrid(event.target.value));
  byId("command-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const input = byId("command-input");
    runCommand(input.value || "HELP");
  });
  document.querySelectorAll(".rail-button").forEach((button) => {
    button.addEventListener("click", () => setModule(button.dataset.module));
  });
  document.querySelector(".accordion").addEventListener("click", () => {
    document.querySelector(".accordion-body").classList.toggle("open");
  });
  document.querySelector(".modal-close").addEventListener("click", () => byId("info-modal").close());
  byId("copy-pitch").addEventListener("click", async () => {
    const text =
      "Within a bounded VN30 hourly absolute-direction benchmark, the classical L2 Logistic champion reached 61.61% final accuracy over 4,074 rows.";
    await navigator.clipboard.writeText(text);
    addAudit("pitch-safe claim text copied");
  });
  byId("copy-claims").addEventListener("click", async () => {
    const text =
      "Blocked: broad system-wide 61% forecast-performance wording. Blocked: production or profitability guarantee. Blocked: broker/order execution workflow.";
    await navigator.clipboard.writeText(text);
    addAudit("blocked-claim warnings copied");
  });
  byId("explain-benchmark").addEventListener("click", () => {
    showModal(
      "61.61% exact scope",
      "The benchmark is limited to VN30 hourly absolute_direction, L2 Logistic, feature_set_C_closest, h40, and 4,074 rows. It is not broad system-wide forecast wording."
    );
  });
  byId("explain-gate").addEventListener("click", () => {
    showModal(
      "60% hard gate",
      "The current broad/local release candidate is 55.7273% BAcc, 4.2727 percentage points below the 60% gate, so broad forecast-performance wording remains blocked."
    );
  });
  byId("preview-report").addEventListener("click", () => renderReportPreview(state.selectedTicker));
  document.querySelectorAll("[data-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
      byId("assistant-input").value = button.dataset.prompt;
      runCommand(button.dataset.prompt.includes("61.61") ? "CLAIMS" : button.dataset.prompt.includes("60%") ? "GATE" : "HELP");
    });
  });
}

async function init() {
  bindUi();
  state.vn30 = await fetchJson("/api/vn30");
  renderDistribution();
  renderTickerGrid();
  renderRiskTable();
  renderReviewGrid();
  await selectTicker("VCB", "Overview");
  await renderReportPreview("VCB");
  setConsole("READY", ["local-only VN30 terminal loaded", "type HELP for supported research commands"]);
}

init().catch((error) => {
  console.error(error);
  setConsole("ERROR", [error.message]);
});
