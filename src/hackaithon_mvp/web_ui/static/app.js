const state = {
  summary: null,
  technical: false,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  window.setTimeout(() => el.classList.remove("show"), 1800);
}

async function copyText(text, label) {
  try {
    await navigator.clipboard.writeText(text);
    toast(label);
  } catch {
    toast("Clipboard unavailable");
  }
}

function activatePage(id) {
  $$(".page").forEach((page) => page.classList.toggle("active", page.id === id));
  $$("#nav button").forEach((button) => button.classList.toggle("active", button.dataset.target === id));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderStock(profile) {
  $("#stock-title").textContent = `${profile.ticker} - ${profile.company_name}`;
  $("#stock-ticker").textContent = profile.ticker;
  $("#stock-company").textContent = profile.company_name;
  $("#stock-exchange").textContent = profile.exchange;
  const panels = $("#stock-panels");
  panels.innerHTML = "";
  profile.panels.forEach((panel) => {
    const article = document.createElement("article");
    article.className = "panel";
    article.innerHTML = `
      <h3>${panel.name}</h3>
      <span class="badge ${panel.status.includes("blocked") ? "blocked" : panel.status.includes("required") ? "warning" : "safe"}">${panel.status}</span>
      <ul>${panel.items.map((item) => `<li>${item}</li>`).join("")}</ul>
    `;
    panels.appendChild(article);
  });
}

async function loadStock(ticker) {
  const response = await fetch(`/api/demo-stock?ticker=${encodeURIComponent(ticker)}`);
  renderStock(await response.json());
}

function renderDataSources() {
  const root = $("#data-sources");
  root.innerHTML = "";
  window.VSEF_MOCK.dataSources.forEach(([name, status]) => {
    const card = document.createElement("article");
    card.className = "mini-card";
    card.innerHTML = `<strong>${name}</strong><span>${status}</span>`;
    root.appendChild(card);
  });
}

function renderRisk() {
  const root = $("#risk-grid");
  root.innerHTML = "";
  window.VSEF_MOCK.riskItems.forEach(([name, level, source, action]) => {
    const card = document.createElement("article");
    card.className = "risk-card";
    card.innerHTML = `
      <h3>${name}</h3>
      <div><span>Risk level</span><strong>${level}</strong></div>
      <div><span>Evidence source</span><strong>${source}</strong></div>
      <div><span>Required human action</span><strong>${action}</strong></div>
    `;
    root.appendChild(card);
  });
}

function renderSocial() {
  const root = $("#social-cards");
  root.innerHTML = "";
  window.VSEF_MOCK.socialCards.forEach((title) => {
    const card = document.createElement("article");
    card.className = "panel";
    card.innerHTML = `<h3>${title}</h3><p>demo placeholder</p><span class="badge muted">human verification required</span>`;
    root.appendChild(card);
  });
}

function renderEvaluation() {
  const root = $("#evaluation-rows");
  root.innerHTML = "";
  window.VSEF_MOCK.evaluationRows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = row.map((cell) => `<td>${cell}</td>`).join("");
    root.appendChild(tr);
  });
}

function renderReview() {
  const root = $("#review-grid");
  root.innerHTML = "";
  window.VSEF_MOCK.reviewItems.forEach(([title, status, evidence, risk, action]) => {
    const card = document.createElement("article");
    card.className = "review-card";
    card.innerHTML = `
      <h3>${title}</h3>
      <span class="badge ${status.includes("blocked") ? "blocked" : status.includes("required") || status.includes("needs") ? "warning" : "safe"}">${status}</span>
      <p><strong>Evidence:</strong> ${evidence}</p>
      <p><strong>Risk:</strong> ${risk}</p>
      <p><strong>Reviewer action:</strong> ${action}</p>
    `;
    root.appendChild(card);
  });
}

function drawCharts() {
  const charts = $$(".bar-chart");
  const values = [
    [["Completed", 120], ["Skipped", 77730], ["Failed", 0]],
    [["Baseline", 32850], ["Auxiliary", 22500], ["Stack", 22500]]
  ];
  charts.forEach((chart, index) => {
    chart.innerHTML = `<h3>${chart.dataset.title}</h3>`;
    const max = Math.max(...values[index].map((item) => item[1]));
    values[index].forEach(([label, value]) => {
      const row = document.createElement("div");
      row.className = "bar-row";
      row.innerHTML = `<span>${label}</span><div><i style="width:${max ? (value / max) * 100 : 0}%"></i></div><strong>${value.toLocaleString()}</strong>`;
      chart.appendChild(row);
    });
  });
}

function wireNavigation() {
  $$("#nav button, .nav-cta").forEach((button) => {
    button.addEventListener("click", () => activatePage(button.dataset.target));
  });
}

function wireViewToggle() {
  $("#proposal-view").addEventListener("click", () => {
    state.technical = false;
    document.body.classList.remove("technical");
    $("#proposal-view").classList.add("active");
    $("#technical-view").classList.remove("active");
  });
  $("#technical-view").addEventListener("click", () => {
    state.technical = true;
    document.body.classList.add("technical");
    $("#technical-view").classList.add("active");
    $("#proposal-view").classList.remove("active");
  });
}

function wireModals() {
  $$(".modal-button").forEach((button) => {
    button.addEventListener("click", () => {
      const modal = $(`#${button.dataset.modal}`);
      modal.setAttribute("aria-hidden", "false");
      modal.classList.add("open");
    });
  });
  $$(".modal-close").forEach((button) => {
    button.addEventListener("click", () => {
      const modal = button.closest(".modal");
      modal.setAttribute("aria-hidden", "true");
      modal.classList.remove("open");
    });
  });
  $$(".modal").forEach((modal) => {
    modal.addEventListener("click", (event) => {
      if (event.target === modal) {
        modal.setAttribute("aria-hidden", "true");
        modal.classList.remove("open");
      }
    });
  });
}

function wireCopies() {
  $("#copy-safe-claim").addEventListener("click", () => copyText($("#safe-claim").textContent, "Pitch-safe text copied"));
  $("#copy-blocked-warnings").addEventListener("click", () => copyText(window.VSEF_MOCK.blockedWarnings.join("\n"), "Warnings copied"));
  $("#copy-pitch").addEventListener("click", () => copyText(window.VSEF_MOCK.pitchSummary, "Pitch summary copied"));
  $("#export-json").addEventListener("click", () => {
    const payload = JSON.stringify(state.summary || window.VSEF_MOCK, null, 2);
    const blob = new Blob([payload], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "vsef_demo_summary.json";
    link.click();
    URL.revokeObjectURL(url);
    toast("Demo JSON prepared locally");
  });
}

async function boot() {
  wireNavigation();
  wireViewToggle();
  wireModals();
  wireCopies();
  renderDataSources();
  renderRisk();
  renderSocial();
  renderEvaluation();
  renderReview();
  drawCharts();
  await loadStock("VCB");
  $("#ticker-select").addEventListener("change", (event) => loadStock(event.target.value));
  try {
    const response = await fetch("/api/summary");
    state.summary = await response.json();
  } catch {
    state.summary = null;
  }
}

boot();
