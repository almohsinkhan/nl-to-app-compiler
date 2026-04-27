// TODO: When deploying the backend to Render, change this to your Render API URL
// e.g., "https://your-backend.onrender.com"
// Leave as "" for local development using FastAPI's static server.


const SAMPLE_PROMPTS = [
  "Build a CRM with login, contacts, dashboard, and role-based permissions.",
  "Create a school portal for students, teachers, and admin with assignments and grading.",
  "Design an inventory app with products, suppliers, purchase orders, and low-stock alerts.",
  "Generate a booking platform for service providers with schedules, payments, and reviews.",
];

function byId(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setMessage(node, text, tone = "") {
  node.textContent = text || "";
  node.classList.remove("success", "error");
  if (tone) node.classList.add(tone);
}

function listHtml(items, emptyText) {
  if (!items || items.length === 0) {
    return `<li class="empty">${escapeHtml(emptyText)}</li>`;
  }
  return items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

function setLoading(button, loadingText, isLoading) {
  if (isLoading) {
    button.dataset.originalHtml = button.innerHTML;
    button.textContent = loadingText;
    button.disabled = true;
    return;
  }
  if (button.dataset.originalHtml) {
    button.innerHTML = button.dataset.originalHtml;
  }
  button.disabled = false;
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const text = await response.text();
  let parsed = {};
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = { detail: text };
    }
  }

  if (!response.ok) {
    const detail = parsed.detail;
    if (typeof detail === "string") throw new Error(detail);
    if (Array.isArray(detail)) {
      throw new Error(detail.map((d) => d.msg || JSON.stringify(d)).join("; "));
    }
    throw new Error(`Request failed (${response.status}).`);
  }
  return parsed;
}

function renderSamplePrompts(promptInput, sampleContainer) {
  sampleContainer.innerHTML = "";
  for (const prompt of SAMPLE_PROMPTS) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "sample-btn";
    button.textContent = prompt;
    button.addEventListener("click", () => {
      promptInput.value = prompt;
      promptInput.focus();
    });
    sampleContainer.appendChild(button);
  }
}



function renderBlueprint(blueprint) {
  if (!blueprint) {
    return '<section class="blueprint-section"><h4>No blueprint generated.</h4></section>';
  }

  const tables = blueprint.database?.tables ?? [];
  const endpoints = blueprint.api?.endpoints ?? [];
  const pages = blueprint.ui?.pages ?? [];
  const roles = blueprint.auth?.roles ?? [];
  const rules = blueprint.logic?.rules ?? [];

  const tableCards =
    tables.length === 0
      ? '<p class="subtle">No tables found.</p>'
      : tables
          .map((table) => {
            const fields =
              table.fields?.length > 0
                ? table.fields
                    .map(
                      (field) =>
                        `<li>${escapeHtml(field.name)}: ${escapeHtml(field.type)}${field.required ? " (required)" : ""}${
                          field.unique ? " (unique)" : ""
                        }</li>`
                    )
                    .join("")
                : '<li class="empty">No fields.</li>';
            return `
              <article class="mini-card">
                <div class="mini-card-title">
                  <span>${escapeHtml(table.name)}</span>
                  <span>${escapeHtml(table.primary_key || "id")}</span>
                </div>
                <ul class="token-list">${fields}</ul>
              </article>
            `;
          })
          .join("");

  const endpointCards =
    endpoints.length === 0
      ? '<p class="subtle">No endpoints found.</p>'
      : endpoints
          .map(
            (endpoint) => `
              <article class="mini-card">
                <div class="mini-card-title">
                  <span>${escapeHtml(endpoint.name)}</span>
                  <span class="method-chip">${escapeHtml(endpoint.method)}</span>
                </div>
                <ul class="token-list">
                  <li>Path: ${escapeHtml(endpoint.path)}</li>
                  <li>Auth required: ${endpoint.auth_required ? "Yes" : "No"}</li>
                  <li>Source table: ${escapeHtml(endpoint.source_table || "-")}</li>
                </ul>
              </article>
            `
          )
          .join("");

  const pageCards =
    pages.length === 0
      ? '<p class="subtle">No pages found.</p>'
      : pages
          .map((page) => {
            const components =
              page.components?.length > 0
                ? page.components
                    .map(
                      (component) =>
                        `<li>${escapeHtml(component.id)} (${escapeHtml(component.type)}) -> ${escapeHtml(
                          component.binds_to_endpoint || "-"
                        )}</li>`
                    )
                    .join("")
                : '<li class="empty">No components.</li>';
            return `
              <article class="mini-card">
                <div class="mini-card-title">
                  <span>${escapeHtml(page.name)}</span>
                  <span>${escapeHtml(page.route)}</span>
                </div>
                <ul class="token-list">${components}</ul>
              </article>
            `;
          })
          .join("");

  const roleCards =
    roles.length === 0
      ? '<p class="subtle">No roles found.</p>'
      : roles
          .map(
            (role) => `
              <article class="mini-card">
                <div class="mini-card-title">
                  <span>${escapeHtml(role.role)}</span>
                </div>
                <ul class="token-list">
                  ${
                    role.permissions?.length
                      ? role.permissions.map((permission) => `<li>${escapeHtml(permission)}</li>`).join("")
                      : '<li class="empty">No permissions.</li>'
                  }
                </ul>
              </article>
            `
          )
          .join("");

  const ruleCards =
    rules.length === 0
      ? '<p class="subtle">No logic rules found.</p>'
      : rules
          .map(
            (rule) => `
              <article class="mini-card">
                <div class="mini-card-title">
                  <span>${escapeHtml(rule.id)}</span>
                </div>
                <ul class="token-list">
                  <li>${escapeHtml(rule.description)}</li>
                  <li>Applies to: ${escapeHtml((rule.applies_to || []).join(", ") || "-")}</li>
                </ul>
              </article>
            `
          )
          .join("");

  return `
    <section class="blueprint-section">
      <h4>Database (${tables.length})</h4>
      <div class="mini-grid">${tableCards}</div>
    </section>
    <section class="blueprint-section">
      <h4>API Endpoints (${endpoints.length})</h4>
      <div class="mini-grid">${endpointCards}</div>
    </section>
    <section class="blueprint-section">
      <h4>UI Pages (${pages.length})</h4>
      <div class="mini-grid">${pageCards}</div>
    </section>
    <section class="blueprint-section">
      <h4>Auth Roles (${roles.length})</h4>
      <div class="mini-grid">${roleCards}</div>
    </section>
    <section class="blueprint-section">
      <h4>Business Rules (${rules.length})</h4>
      <div class="mini-grid">${ruleCards}</div>
    </section>
  `;
}

function renderIssueDetails(items) {
  if (!items || items.length === 0) {
    return '<li class="empty">No issue details.</li>';
  }
  return items
    .map((issue) => {
      const severity = escapeHtml(issue.severity || "error");
      const code = escapeHtml(issue.code || "UNKNOWN");
      const location = escapeHtml(issue.location || "unknown");
      const message = escapeHtml(issue.message || "");
      return `<li><strong>[${severity}] ${code}</strong> at <strong>${location}</strong>: ${message}</li>`;
    })
    .join("");
}

function renderEvaluationSummary(summary) {
  const entries = Object.entries(summary || {});
  if (entries.length === 0) {
    return '<p class="subtle">No summary data returned.</p>';
  }
  return entries
    .map(([key, value]) => {
      const printable = typeof value === "object" ? JSON.stringify(value) : String(value);
      return `
        <div class="summary-item">
          <span>${escapeHtml(key)}</span>
          <strong>${escapeHtml(printable)}</strong>
        </div>
      `;
    })
    .join("");
}

document.addEventListener("DOMContentLoaded", () => {

  const promptInput = byId("prompt-input");
  const samplePrompts = byId("sample-prompts");
  const clearPromptBtn = byId("clear-prompt-btn");
  const compileBtn = byId("compile-btn");
  const evaluateBtn = byId("evaluate-btn");
  const compileMessage = byId("compile-message");

  const resultPanel = byId("panel-result");
  const validityPill = byId("validity-pill");
  const metricLatency = byId("metric-latency");
  const metricRetries = byId("metric-retries");
  const metricBlueprint = byId("metric-blueprint");
  const assumptionsList = byId("assumptions-list");
  const clarificationsList = byId("clarifications-list");
  const issuesList = byId("issues-list");
  const repairedList = byId("repaired-list");
  const issueDetailsList = byId("issue-details-list");
  const blueprintContent = byId("blueprint-content");
  const rawJson = byId("raw-json");

  const evaluationPanel = byId("panel-evaluate");
  const evaluationBadge = byId("evaluation-badge");
  const evaluationSummary = byId("evaluation-summary");
  const evaluationJson = byId("evaluation-json");


  clearPromptBtn.addEventListener("click", () => {
    promptInput.value = "";
    promptInput.focus();
  });

  compileBtn.addEventListener("click", async () => {
    const prompt = promptInput.value.trim();
    if (!prompt) {
      setMessage(compileMessage, "Enter a prompt before compiling.", "error");
      return;
    }

    setLoading(compileBtn, "Compiling...", true);
    setMessage(compileMessage, "");

    try {
      const response = await postJson(`${API_BASE_URL}/compile`, { prompt });
      const resultNav = document.querySelector('[data-panel="result"]');
      if (resultNav) resultNav.click();
      else resultPanel.classList.remove("hidden");

      const isValid = !!response.valid;
      validityPill.textContent = isValid ? "Valid" : "Needs Review";
      validityPill.classList.remove("ok", "warn");
      validityPill.classList.add(isValid ? "ok" : "warn");

      metricLatency.textContent = `${response.latency_ms ?? 0} ms`;
      metricRetries.textContent = String(response.retries ?? 0);
      metricBlueprint.textContent = response.blueprint ? "Generated" : "Not Generated";

      assumptionsList.innerHTML = listHtml(response.assumptions, "No assumptions.");
      clarificationsList.innerHTML = listHtml(response.clarification_questions, "No clarification questions.");
      issuesList.innerHTML = listHtml(response.issues, "No issue messages.");
      repairedList.innerHTML = listHtml(response.repaired, "No repair actions.");
      issueDetailsList.innerHTML = renderIssueDetails(response.issue_details);
      blueprintContent.innerHTML = renderBlueprint(response.blueprint);
      rawJson.textContent = JSON.stringify(response, null, 2);

      const baseMessage = isValid ? "Compilation complete." : "Compilation completed with follow-up items.";
      setMessage(compileMessage, baseMessage, isValid ? "success" : "error");
    } catch (error) {
      setMessage(compileMessage, error.message || "Compile request failed.", "error");
    } finally {
      setLoading(compileBtn, "Compiling...", false);
    }
  });

  evaluateBtn.addEventListener("click", async () => {
    setLoading(evaluateBtn, "Evaluating...", true);
    setMessage(compileMessage, "");

    try {
      const response = await fetch(`${API_BASE_URL}/evaluate`, { method: "POST" });
      const text = await response.text();
      let parsed = {};
      try {
        parsed = text ? JSON.parse(text) : {};
      } catch {
        parsed = { raw: text };
      }

      if (!response.ok) {
        throw new Error("Evaluation request failed.");
      }

      const evalNav = document.querySelector('[data-panel="evaluate"]');
      if (evalNav) evalNav.click();
      else evaluationPanel.classList.remove("hidden");
      evaluationBadge.textContent = "Completed";
      evaluationBadge.classList.remove("warn");
      evaluationBadge.classList.add("ok");
      evaluationSummary.innerHTML = renderEvaluationSummary(parsed.summary || {});
      evaluationJson.textContent = JSON.stringify(parsed, null, 2);
      setMessage(compileMessage, "Evaluation run completed.", "success");
    } catch (error) {
      const evalNav = document.querySelector('[data-panel="evaluate"]');
      if (evalNav) evalNav.click();
      else evaluationPanel.classList.remove("hidden");
      evaluationBadge.textContent = "Failed";
      evaluationBadge.classList.remove("ok");
      evaluationBadge.classList.add("warn");
      evaluationSummary.innerHTML = '<p class="subtle">Unable to run evaluation.</p>';
      evaluationJson.textContent = "";
      setMessage(compileMessage, error.message || "Evaluation failed.", "error");
    } finally {
      setLoading(evaluateBtn, "Evaluating...", false);
    }
  });

  renderSamplePrompts(promptInput, samplePrompts);

});
