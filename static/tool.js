(() => {
  "use strict";

  const form = document.getElementById("score-form");
  const button = document.getElementById("score-button");
  const formState = document.getElementById("form-state");
  const errorMessage = document.getElementById("error-message");
  const resultPanel = document.getElementById("result-panel");
  const results = document.getElementById("results");
  const emptyState = document.getElementById("empty-state");
  const fileInput = document.getElementById("discharge-csv");
  const capacity = form.elements.namedItem("capacity");
  const minutes = form.elements.namedItem("minutes_per_contact");
  const eligible = form.elements.namedItem("eligible");
  const rankedRows = document.getElementById("ranked-rows");
  const warnings = document.getElementById("warnings");
  const tieMessage = document.getElementById("tie-message");
  const download = document.getElementById("download-results");
  const numberFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });
  const integerFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
  const percentFormat = new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 2 });
  // Unlike $, the final assertion also rejects a trailing newline.
  const referencePattern = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}(?![\s\S])/;
  const maxFileBytes = 2 * 1024 * 1024;
  let requestVersion = 0;
  let activeRequest = null;
  let downloadUrl = null;
  const plannerWorkspace = document.getElementById("planner-workspace");
  const csvWorkspace = document.getElementById("csv-workspace");
  const plannerMode = document.getElementById("planner-mode");
  const csvMode = document.getElementById("csv-mode");

  function initializePlanner() {
    const planForm = document.getElementById("plan-form");
    const planButton = document.getElementById("planner-calculate-button");
    const planState = document.getElementById("planner-form-state");
    const planError = document.getElementById("planner-error-message");
    const planPanel = document.getElementById("planner-result-panel");
    const planResults = document.getElementById("planner-results");
    const planEmpty = document.getElementById("planner-empty-state");
    const discharges = planForm.elements.namedItem("discharges");
    const planCapacity = planForm.elements.namedItem("capacity");
    const planNumberFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });
    const planPercentFormat = new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 1 });
    let version = 0;
    let request = null;

    function validateCapacity() {
      const count = discharges.valueAsNumber;
      planCapacity.max = Number.isFinite(count) && count >= 1 ? String(count) : "1000000";
      planCapacity.setCustomValidity(planCapacity.valueAsNumber > count
        ? "Contact capacity cannot exceed eligible discharges." : "");
    }

    function clearPlan(message) {
      planResults.hidden = true;
      planEmpty.hidden = false;
      planEmpty.textContent = message;
      planError.hidden = true;
      planError.textContent = "";
    }

    function invalidatePlan() {
      version += 1;
      if (request) request.abort();
      request = null;
      validateCapacity();
      clearPlan("Calculate a plan to see an up-to-date historical estimate.");
      planPanel.setAttribute("aria-busy", "false");
      planButton.disabled = false;
      planButton.textContent = "Calculate plan";
      planState.textContent = "Calculate again to update the historical estimate.";
    }

    function validPlan(data) {
      if (!data || typeof data.feasible !== "boolean" || !data.plan || !data.reference) return false;
      const plan = data.plan;
      return ["contacts", "true_positives", "false_positives", "missed", "recall", "staff_hours"]
        .every((key) => Number.isFinite(plan[key]))
        && (plan.threshold === null || Number.isFinite(plan.threshold))
        && (plan.precision === null || Number.isFinite(plan.precision))
        && Number.isFinite(data.maximum_recall)
        && (data.minimum_contacts_for_target === null || Number.isFinite(data.minimum_contacts_for_target))
        && Number.isInteger(data.reference.encounters)
        && Number.isFinite(data.reference.prevalence)
        && data.reference.source === "Policy validation";
    }

    function renderPlan(data) {
      const plan = data.plan;
      const title = data.feasible ? "Target achievable" : "Target not achievable";
      document.getElementById("planner-plan-status").classList.toggle("is-infeasible", !data.feasible);
      setText("planner-status-title", title);
      if (data.feasible) {
        setText("planner-status-detail", "Highest precision within your capacity and recall target in the historical reference data.");
        setText("planner-plan-label", "Plan meeting your inputs");
      } else {
        const detail = data.minimum_contacts_for_target === null
          ? "No historical threshold meets this target."
          : `Target needs approximately ${planNumberFormat.format(data.minimum_contacts_for_target)} contacts.`;
        setText("planner-status-detail", `Historical maximum recall within capacity: ${planPercentFormat.format(data.maximum_recall)}. ${detail}`);
        setText("planner-plan-label", "Capacity-limited alternative · not a recommendation");
      }
      setText("planner-contacts-value", planNumberFormat.format(plan.contacts));
      setText("planner-hours-value", planNumberFormat.format(plan.staff_hours));
      setText("planner-identified-value", planNumberFormat.format(plan.true_positives));
      setText("planner-missed-value", planNumberFormat.format(plan.missed));
      setText("planner-false-positives-value", planNumberFormat.format(plan.false_positives));
      setText("planner-recall-value", planPercentFormat.format(plan.recall));
      setText("planner-precision-value", plan.precision === null ? "Not applicable" : planPercentFormat.format(plan.precision));
      setText("planner-threshold-value", plan.threshold === null ? "No contacts" : percentFormat.format(plan.threshold));
      setText("planner-reference", `${data.reference.source} · ${integerFormat.format(data.reference.encounters)} historical encounters · ${planPercentFormat.format(data.reference.prevalence)} readmission rate. Counts projected to eligible discharges; rounded for display.`);
      planEmpty.hidden = true;
      planResults.hidden = false;
      planState.textContent = `${title} in historical reference data. ${planNumberFormat.format(plan.contacts)} expected contacts and ${planNumberFormat.format(plan.staff_hours)} staff hours.`;
    }

    async function calculatePlan() {
      validateCapacity();
      if (plannerWorkspace.hidden || planButton.disabled || !planForm.reportValidity()) return;
      const currentVersion = ++version;
      const controller = new AbortController();
      request = controller;
      const payload = {
        discharges: discharges.valueAsNumber,
        capacity: planCapacity.valueAsNumber,
        recall_target: planForm.elements.namedItem("recall_target").valueAsNumber,
        minutes_per_contact: planForm.elements.namedItem("minutes_per_contact").valueAsNumber
      };
      clearPlan("Calculating your historical planning estimate…");
      planPanel.setAttribute("aria-busy", "true");
      planButton.disabled = true;
      planButton.textContent = "Calculating…";
      planState.textContent = "Calculating your historical plan…";
      try {
        const response = await fetch(planForm.action, {
          method: "POST",
          headers: { "Content-Type": "application/json", "Accept": "application/json" },
          body: JSON.stringify(payload),
          credentials: "omit",
          cache: "no-store",
          signal: controller.signal
        });
        if (currentVersion !== version) return;
        let data;
        try {
          data = await response.json();
        } catch {
          throw new Error("The planning service returned an unreadable response. Please try again.");
        }
        if (currentVersion !== version) return;
        if (!response.ok) {
          throw new Error(typeof data?.error === "string" ? data.error : "The planning service could not calculate this plan. Please try again.");
        }
        if (!validPlan(data)) {
          throw new Error("The planning service returned an incomplete estimate. No result is shown. Please try again.");
        }
        renderPlan(data);
      } catch (error) {
        if (currentVersion !== version) return;
        clearPlan("No current estimate. Resolve the error and calculate again.");
        planError.textContent = error instanceof TypeError
          ? "Unable to reach the planning service. Check that the local app is running, then try again."
          : error.message || "Unable to calculate a plan. Please try again.";
        planError.hidden = false;
        planState.textContent = "";
      } finally {
        if (currentVersion === version) {
          request = null;
          planPanel.setAttribute("aria-busy", "false");
          planButton.disabled = false;
          planButton.textContent = "Calculate plan";
        }
      }
    }

    planForm.addEventListener("input", invalidatePlan);
    planForm.addEventListener("change", invalidatePlan);
    planForm.addEventListener("submit", (event) => {
      event.preventDefault();
      calculatePlan();
    });
    return { invalidate: invalidatePlan, calculate: calculatePlan };
  }

  function setText(id, text) {
    document.getElementById(id).textContent = text;
  }

  function clearResults(message) {
    results.hidden = true;
    emptyState.hidden = false;
    emptyState.textContent = message;
    rankedRows.replaceChildren();
    warnings.replaceChildren();
    warnings.hidden = true;
    tieMessage.textContent = "";
    tieMessage.hidden = true;
    for (const id of ["records-value", "selected-value", "hours-value", "selection-summary"]) {
      setText(id, "");
    }
    download.hidden = true;
    download.removeAttribute("href");
    if (downloadUrl !== null) URL.revokeObjectURL(downloadUrl);
    downloadUrl = null;
    errorMessage.hidden = true;
    errorMessage.textContent = "";
  }

  function invalidate(message) {
    requestVersion += 1;
    if (activeRequest) activeRequest.abort();
    activeRequest = null;
    clearResults(message);
    resultPanel.setAttribute("aria-busy", "false");
    button.disabled = false;
    button.textContent = "Prioritise follow-up";
    formState.textContent = message;
  }

  function isValidResponse(data, requestedCapacity) {
    if (!data || !data.summary || !Array.isArray(data.rows) || !Array.isArray(data.warnings)) return false;
    const summary = data.summary;
    if (!["records", "capacity", "selected", "review", "remaining_capacity"]
      .every((key) => Number.isInteger(summary[key]) && summary[key] >= 0)) return false;
    if (summary.records < 1 || summary.records > 5000 || summary.records !== data.rows.length
      || summary.capacity !== requestedCapacity || summary.selected > summary.capacity
      || summary.selected + summary.review > summary.records
      || summary.remaining_capacity !== summary.capacity - summary.selected
      || !Number.isFinite(summary.staff_hours) || summary.staff_hours < 0
      || !(summary.boundary_risk === null || (Number.isFinite(summary.boundary_risk)
        && summary.boundary_risk >= 0 && summary.boundary_risk <= 1))
      || !data.warnings.every((warning) => typeof warning === "string")) return false;

    const references = new Set();
    let selected = 0;
    let review = 0;
    for (const row of data.rows) {
      if (!row || typeof row.discharge_reference !== "string"
        || !referencePattern.test(row.discharge_reference) || references.has(row.discharge_reference)
        || !Number.isFinite(row.risk) || row.risk < 0 || row.risk > 1
        || typeof row.selected !== "boolean" || typeof row.review !== "boolean"
        || (row.selected && row.review)) return false;
      references.add(row.discharge_reference);
      selected += Number(row.selected);
      review += Number(row.review);
    }
    return selected === summary.selected && review === summary.review;
  }

  function renderResults(data) {
    const summary = data.summary;
    setText("records-value", integerFormat.format(summary.records));
    setText("selected-value", integerFormat.format(summary.selected));
    setText("hours-value", numberFormat.format(summary.staff_hours));
    setText("selection-summary", `${integerFormat.format(summary.selected)} of ${integerFormat.format(summary.records)} records selected · ${integerFormat.format(summary.capacity)} available contacts · ${integerFormat.format(summary.remaining_capacity)} slots remaining.`);
    if (summary.review > 0) {
      tieMessage.textContent = `${integerFormat.format(summary.review)} records share the same unrounded risk at the capacity boundary. All need review; none in this tied group is automatically selected. ${integerFormat.format(summary.remaining_capacity)} contact slots remain. This boundary is determined by capacity, not a clinical risk threshold.`;
      tieMessage.hidden = false;
    }

    const warningItems = document.createDocumentFragment();
    for (const warning of data.warnings) {
      const item = document.createElement("li");
      item.textContent = warning;
      warningItems.append(item);
    }
    warnings.replaceChildren(warningItems);
    warnings.hidden = data.warnings.length === 0;

    const tableRows = document.createDocumentFragment();
    const csvLines = ["discharge_reference,risk,selected,review"];
    for (const row of data.rows) {
      const tableRow = document.createElement("tr");
      const reference = document.createElement("th");
      reference.scope = "row";
      reference.textContent = row.discharge_reference;
      const risk = document.createElement("td");
      risk.className = "risk-column";
      risk.textContent = percentFormat.format(row.risk);
      const status = document.createElement("td");
      status.textContent = row.selected ? "Selected" : row.review ? "Review tie" : "Not selected";
      if (row.selected) tableRow.className = "selected-row";
      if (row.review) tableRow.className = "review-row";
      tableRow.append(reference, risk, status);
      tableRows.append(tableRow);
      // Validated references cannot contain delimiters, quotes or formula prefixes.
      csvLines.push(`${row.discharge_reference},${String(row.risk)},${row.selected},${row.review}`);
    }
    rankedRows.replaceChildren(tableRows);
    downloadUrl = URL.createObjectURL(new Blob([csvLines.join("\r\n") + "\r\n"], { type: "text/csv;charset=utf-8" }));
    download.href = downloadUrl;
    download.hidden = false;
    emptyState.hidden = true;
    results.hidden = false;
    formState.textContent = `${integerFormat.format(summary.records)} records loaded. ${integerFormat.format(summary.selected)} selected. ${integerFormat.format(summary.review)} need tie review. ${numberFormat.format(summary.staff_hours)} staff hours.`;
  }

  async function scoreDischarges() {
    if (csvWorkspace.hidden) return;
    if (button.disabled || !form.reportValidity()) return;
    const file = fileInput.files[0];
    if (!file || !eligible.checked) return;
    invalidate("Reading and scoring the discharge CSV…");
    if (file.size > maxFileBytes) {
      errorMessage.textContent = "The CSV must be no larger than 2 MiB. Choose a smaller file.";
      errorMessage.hidden = false;
      emptyState.textContent = "No records loaded.";
      formState.textContent = "File is too large. No records uploaded.";
      return;
    }

    const version = requestVersion;
    const controller = new AbortController();
    activeRequest = controller;
    const requestedCapacity = capacity.valueAsNumber;
    const query = new URLSearchParams({
      capacity: String(requestedCapacity),
      minutes_per_contact: String(minutes.valueAsNumber),
      eligible: "true"
    });
    resultPanel.setAttribute("aria-busy", "true");
    button.disabled = true;
    button.textContent = "Scoring…";

    try {
      const body = await file.text();
      if (version !== requestVersion || controller.signal.aborted) return;
      const response = await fetch(`${form.action}?${query}`, {
        method: "POST",
        headers: { "Content-Type": "text/csv; charset=utf-8", "Accept": "application/json" },
        body,
        credentials: "omit",
        cache: "no-store",
        signal: controller.signal
      });
      if (version !== requestVersion) return;
      let data;
      try {
        data = await response.json();
      } catch {
        throw new Error("The scoring service returned an unreadable response. Please try again.");
      }
      if (version !== requestVersion) return;
      if (!response.ok) {
        throw new Error(typeof data?.error === "string" ? data.error : "The scoring service could not score this CSV. Please try again.");
      }
      if (!isValidResponse(data, requestedCapacity)) {
        throw new Error("The scoring service returned an incomplete result. No records are shown. Please try again.");
      }
      renderResults(data);
    } catch (error) {
      if (version !== requestVersion) return;
      clearResults("No current results. Resolve the error and prioritise follow-up again.");
      errorMessage.textContent = error instanceof TypeError
        ? "Unable to reach the scoring service or read the file. Check that the local app is running and choose the file again."
        : error.message || "Unable to score the CSV. Please try again.";
      errorMessage.hidden = false;
      formState.textContent = "No records loaded.";
    } finally {
      if (version === requestVersion) {
        activeRequest = null;
        resultPanel.setAttribute("aria-busy", "false");
        button.disabled = false;
        button.textContent = "Prioritise follow-up";
      }
    }
  }

  function markStale() {
    invalidate("Inputs changed. Prioritise follow-up to load current results.");
  }

  form.addEventListener("input", markStale);
  form.addEventListener("change", markStale);
  form.addEventListener("reset", () => {
    invalidate("Cleared. Choose a discharge CSV to begin.");
    fileInput.value = "";
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    scoreDischarges();
  });
  const planner = initializePlanner();

  function switchMode(showCsv) {
    if (csvWorkspace.hidden === !showCsv) return;
    planner.invalidate();
    form.reset();
    plannerWorkspace.hidden = showCsv;
    csvWorkspace.hidden = !showCsv;
    plannerMode.setAttribute("aria-pressed", String(!showCsv));
    csvMode.setAttribute("aria-pressed", String(showCsv));
  }

  plannerMode.addEventListener("click", () => switchMode(false));
  csvMode.addEventListener("click", () => switchMode(true));
  planner.calculate();
  window.addEventListener("pagehide", () => {
    planner.invalidate();
    invalidate("Choose a discharge CSV and prioritise follow-up again.");
    form.reset();
  });
})();
