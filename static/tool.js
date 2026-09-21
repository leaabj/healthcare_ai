(() => {
  "use strict";

  const form = document.getElementById("plan-form");
  const button = document.getElementById("calculate-button");
  const formState = document.getElementById("form-state");
  const errorMessage = document.getElementById("error-message");
  const resultPanel = document.getElementById("result-panel");
  const results = document.getElementById("results");
  const emptyState = document.getElementById("empty-state");
  const discharges = form.elements.namedItem("discharges");
  const capacity = form.elements.namedItem("capacity");
  const numberFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });
  const integerFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
  const percentFormat = new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 1 });
  const thresholdFormat = new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 2 });
  let requestVersion = 0;
  let activeRequest = null;

  function validateCapacity() {
    const dischargeCount = discharges.valueAsNumber;
    capacity.max = Number.isFinite(dischargeCount) && dischargeCount >= 1
      ? String(dischargeCount)
      : "1000000";
    capacity.setCustomValidity(
      capacity.valueAsNumber > dischargeCount
        ? "Contact capacity cannot exceed eligible discharges."
        : ""
    );
  }

  function setText(id, text) {
    document.getElementById(id).textContent = text;
  }

  function clearResults(message) {
    results.hidden = true;
    emptyState.hidden = false;
    emptyState.textContent = message;
    errorMessage.hidden = true;
    errorMessage.textContent = "";
  }

  function isValidResponse(data) {
    if (!data || typeof data.feasible !== "boolean" || !data.plan || !data.reference) return false;
    const finite = Number.isFinite;
    const plan = data.plan;
    return ["contacts", "true_positives", "false_positives", "missed", "recall", "staff_hours"]
      .every((key) => finite(plan[key]))
      && (plan.threshold === null || finite(plan.threshold))
      && (plan.precision === null || finite(plan.precision))
      && finite(data.maximum_recall)
      && (data.minimum_contacts_for_target === null || finite(data.minimum_contacts_for_target))
      && Number.isInteger(data.reference.encounters)
      && finite(data.reference.prevalence)
      && data.reference.source === "Policy validation";
  }

  function renderPlan(data) {
    const plan = data.plan;
    const statusTitle = data.feasible ? "Target achievable" : "Target not achievable";
    document.getElementById("plan-status").dataset.feasible = String(data.feasible);
    setText("status-title", statusTitle);
    if (data.feasible) {
      setText("status-detail", "A model threshold meets your recall target within your contact capacity. This is the highest-precision qualifying plan in the historical reference data.");
      setText("plan-label", "Plan meeting your inputs");
    } else {
      const targetDetail = data.minimum_contacts_for_target === null
        ? "No available threshold reaches this target in the historical reference data."
        : `Reaching your target would require about ${numberFormat.format(data.minimum_contacts_for_target)} contacts in this period.`;
      setText("status-detail", `Maximum recall within your contact capacity is ${percentFormat.format(data.maximum_recall)}. ${targetDetail} The alternative below gives the highest recall available within your capacity, but does not meet your target.`);
      setText("plan-label", "Capacity-limited alternative · not a recommendation");
    }
    setText("contacts-value", numberFormat.format(plan.contacts));
    setText("hours-value", numberFormat.format(plan.staff_hours));
    setText("identified-value", numberFormat.format(plan.true_positives));
    setText("missed-value", numberFormat.format(plan.missed));
    setText("false-positives-value", numberFormat.format(plan.false_positives));
    setText("recall-value", percentFormat.format(plan.recall));
    setText("precision-value", plan.precision === null ? "Not applicable" : percentFormat.format(plan.precision));
    setText("threshold-value", plan.threshold === null ? "No contacts" : thresholdFormat.format(plan.threshold));
    setText("reference", `Reference: ${data.reference.source} · ${integerFormat.format(data.reference.encounters)} encounters · ${percentFormat.format(data.reference.prevalence)} recorded readmissions. Counts are projected to your eligible discharges and rounded for display.`);
    emptyState.hidden = true;
    results.hidden = false;
    formState.textContent = `${statusTitle}. ${numberFormat.format(plan.contacts)} expected contacts and ${numberFormat.format(plan.staff_hours)} staff hours. Estimated recall: ${percentFormat.format(plan.recall)}.${data.feasible ? "" : " Results show a capacity-limited alternative, not a recommendation."}`;
  }

  function markStale() {
    requestVersion += 1;
    if (activeRequest) activeRequest.abort();
    activeRequest = null;
    validateCapacity();
    clearResults("Inputs changed. Calculate a new plan to see an up-to-date estimate.");
    resultPanel.setAttribute("aria-busy", "false");
    button.disabled = false;
    button.textContent = "Calculate plan";
    formState.textContent = "Inputs changed. Calculate again to update the estimate.";
  }

  async function calculatePlan() {
    validateCapacity();
    if (!form.reportValidity() || button.disabled) return;

    const version = ++requestVersion;
    const controller = new AbortController();
    activeRequest = controller;
    const payload = {
      discharges: discharges.valueAsNumber,
      capacity: capacity.valueAsNumber,
      recall_target: form.elements.namedItem("recall_target").valueAsNumber,
      minutes_per_contact: form.elements.namedItem("minutes_per_contact").valueAsNumber
    };
    clearResults("Calculating your planning estimate…");
    resultPanel.setAttribute("aria-busy", "true");
    button.disabled = true;
    button.textContent = "Calculating…";
    formState.textContent = "Calculating your plan…";

    try {
      const response = await fetch(form.action, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal
      });
      let data;
      try {
        data = await response.json();
      } catch {
        throw new Error("The planning service returned an unreadable response. Please try again.");
      }
      if (version !== requestVersion) return;
      if (!response.ok) {
        throw new Error(typeof data?.error === "string" ? data.error : "The planning service could not calculate this plan. Please try again.");
      }
      if (!isValidResponse(data)) {
        throw new Error("The planning service returned an incomplete estimate. No result is shown. Please try again.");
      }
      renderPlan(data);
    } catch (error) {
      if (version !== requestVersion) return;
      clearResults("No current estimate is available. Resolve the error and calculate again.");
      errorMessage.textContent = error instanceof TypeError
        ? "Unable to reach the planning service. Check that the local app is running, then try again."
        : error.message || "Unable to calculate a plan. Please try again.";
      errorMessage.hidden = false;
      formState.textContent = "";
    } finally {
      if (version === requestVersion) {
        activeRequest = null;
        resultPanel.setAttribute("aria-busy", "false");
        button.disabled = false;
        button.textContent = "Calculate plan";
      }
    }
  }

  form.addEventListener("input", markStale);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    calculatePlan();
  });
  calculatePlan();
})();
