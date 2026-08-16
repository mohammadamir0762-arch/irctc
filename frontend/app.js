const API_BASE = window.API_BASE; // set in config.js

const pnrForm = document.getElementById("pnr-form");
const mockBanner = document.getElementById("mock-banner");
const pnrSummaryEl = document.getElementById("pnr-summary");
const resolvedEl = document.getElementById("resolved");

const predictForm = document.getElementById("predict-form");
const resultEl = document.getElementById("result");
const errorEl = document.getElementById("error");
const probabilityValueEl = document.getElementById("probability-value");
const confidenceLabelEl = document.getElementById("confidence-label");
const topFactorsEl = document.getElementById("top-factors");
const estimatedNoteEl = document.getElementById("estimated-note");
const ringEl = document.querySelector(".probability-ring");

function resetResultSections() {
  errorEl.classList.add("hidden");
  resultEl.classList.add("hidden");
  resolvedEl.classList.add("hidden");
  pnrSummaryEl.classList.add("hidden");
  mockBanner.classList.add("hidden");
}

function showError(message) {
  errorEl.textContent = message;
  errorEl.classList.remove("hidden");
}

function ringColor(probability) {
  if (probability >= 0.75) return "#34d399";
  if (probability >= 0.4) return "#fbbf24";
  return "#f87171";
}

function renderPrediction(data, estimatedFields) {
  probabilityValueEl.textContent = `${Math.round(data.probability * 100)}%`;
  confidenceLabelEl.textContent = data.confidence_label;
  ringEl.style.borderColor = ringColor(data.probability);

  topFactorsEl.innerHTML = data.top_factors
    .map((f) => `<li><strong>${f.factor}:</strong> ${f.impact}</li>`)
    .join("") || "<li>No standout factors — inputs are close to typical values.</li>";

  if (estimatedFields && estimatedFields.length) {
    estimatedNoteEl.textContent = `Some inputs (${estimatedFields.join(", ")}) aren't available from the PNR lookup and are estimated, not exact.`;
    estimatedNoteEl.classList.remove("hidden");
  } else {
    estimatedNoteEl.classList.add("hidden");
  }

  resultEl.classList.remove("hidden");
}

pnrForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  resetResultSections();

  const pnrNumber = document.getElementById("pnr_number").value.trim();
  if (!/^\d{10}$/.test(pnrNumber)) {
    showError("PNR number must be exactly 10 digits.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/pnr/${pnrNumber}`);
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || `Request failed (${res.status})`);
    }
    const data = await res.json();

    if (data.is_mock) {
      mockBanner.classList.remove("hidden");
    }

    if (data.resolved) {
      resolvedEl.textContent = `PNR ${data.pnr_number}: ${data.status}`;
      resolvedEl.className = `resolved status-${data.status.toLowerCase()}`;
      resolvedEl.classList.remove("hidden");
      return;
    }

    const s = data.pnr_summary;
    pnrSummaryEl.innerHTML = `
      <div class="train-title">${s.train_name} (${s.train_number})</div>
      <div class="muted">${s.from_station} → ${s.to_station}</div>
      <div class="muted">Journey date: ${s.journey_date} · Chart prepared: ${s.chart_prepared ? "Yes" : "No"}</div>
      <div class="muted">Status: ${s.current_status}</div>
    `;
    pnrSummaryEl.classList.remove("hidden");

    renderPrediction(data, data.estimated_fields);
  } catch (err) {
    showError(err.message);
  }
});

async function loadOptions() {
  const res = await fetch(`${API_BASE}/options`);
  const options = await res.json();
  for (const [field, values] of Object.entries(options)) {
    const select = document.getElementById(field);
    select.innerHTML = values.map((v) => `<option value="${v}">${v}</option>`).join("");
  }
}

predictForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  resetResultSections();

  const formData = new FormData(predictForm);
  const payload = {
    travel_class: formData.get("travel_class"),
    booking_position: Number(formData.get("booking_position")),
    current_position: Number(formData.get("current_position")),
    days_before_journey: Number(formData.get("days_before_journey")),
  };

  try {
    const res = await fetch(`${API_BASE}/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || `Request failed (${res.status})`);
    }
    const data = await res.json();
    renderPrediction(data, null);
  } catch (err) {
    showError(err.message);
  }
});

async function loadModelInfo() {
  const res = await fetch(`${API_BASE}/model`);
  const m = await res.json();
  document.getElementById("model-note").textContent =
    `Model: trained on ${m.n_tickets.toLocaleString()} real waitlisted tickets ` +
    `(${m.source}). Test AUC ${m.test_auc}, Brier ${m.test_brier}.`;
}

if (!window.API_BASE_CONFIGURED) {
  showError(
    "This site has no backend URL configured. Set DEPLOYED_API in frontend/config.js " +
      "to your Render URL and redeploy."
  );
} else {
  loadOptions()
    .then(loadModelInfo)
    .catch((err) => {
      showError(`Could not reach the API at ${API_BASE}. Is the backend running? (${err.message})`);
    });
}
