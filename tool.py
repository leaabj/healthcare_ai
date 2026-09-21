"""Local educational capacity planning from the notebook's policy-validation sweep."""

import argparse
import math
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from utils import pick_policy


ROOT = Path(__file__).resolve().parent
DEFAULTS = {
    "discharges": 1000,
    "capacity": 200,
    "recall_target": 35,
    "minutes_per_contact": 20,
}
TABLE_NAME = "policy_threshold_table.csv"
PREPARE_HELP = "Run python tool.py --prepare in the project environment to prepare policy-validation results."


class ArtifactError(ValueError):
    """Policy-validation artifacts cannot safely support a plan."""


def load_policy_table(artifact_dir):
    """Read and check the exported sweep, without reading test results or writing files."""
    columns = [
        "threshold", "tp", "fp", "fn", "tn", "precision", "recall", "specificity",
        "alerts_per_1000", "false_alerts_per_1000", "missed_per_1000",
        "staff_hours_per_1000",
    ]
    try:
        table = pd.read_csv(Path(artifact_dir) / TABLE_NAME)
        if table.empty or not set(columns).issubset(table.columns):
            raise ValueError("the threshold table is empty or missing required columns")
        table = table[columns].apply(pd.to_numeric, errors="raise")
        counts = table[["tp", "fp", "fn", "tn"]].to_numpy()
        if not np.isfinite(counts).all() or (counts < 0).any() or (counts != np.floor(counts)).any():
            raise ValueError("confusion counts must be finite nonnegative integers")
        totals = counts.sum(axis=1)
        positives = table["tp"] + table["fn"]
        negatives = table["fp"] + table["tn"]
        encounters = int(totals[0])
        if (
            encounters <= 0 or not (totals == encounters).all()
            or not (positives == positives.iloc[0]).all()
            or not (negatives == negatives.iloc[0]).all()
            or positives.iloc[0] <= 0 or negatives.iloc[0] <= 0
        ):
            raise ValueError("rows must describe one consistent cohort with both outcomes")
        thresholds = table["threshold"].to_numpy()
        valid_threshold = (np.isfinite(thresholds) & (thresholds >= 0) & (thresholds <= 1)) | np.isposinf(thresholds)
        if not valid_threshold.all() or table["threshold"].duplicated().any():
            raise ValueError("thresholds must be unique probabilities or the infinite no-contact threshold")
        alerts = table["tp"] + table["fp"]
        if not (np.isposinf(thresholds) & alerts.eq(0)).any():
            raise ValueError("the infinite no-contact candidate is missing")
        if (alerts[np.isposinf(thresholds)] != 0).any():
            raise ValueError("the infinite threshold must contact nobody")
        ordered = table.sort_values("threshold")
        if (ordered[["tp", "fp"]].diff().iloc[1:] > 0).any().any():
            raise ValueError("contact counts must not increase as the threshold rises")
        expected = {
            "precision": table["tp"] / alerts.replace(0, np.nan),
            "recall": table["tp"] / positives,
            "specificity": table["tn"] / negatives,
            "alerts_per_1000": 1000 * alerts / encounters,
            "false_alerts_per_1000": 1000 * table["fp"] / encounters,
            "missed_per_1000": 1000 * table["fn"] / encounters,
        }
        for name, values in expected.items():
            if not np.allclose(table[name], values, rtol=1e-9, atol=1e-10, equal_nan=True):
                raise ValueError(f"{name} is inconsistent with the confusion counts")
            # Use count-derived rates, not rounded CSV rates, for policy comparisons.
            table[name] = values
        hours = table["staff_hours_per_1000"].to_numpy()
        if not np.isfinite(hours).all() or (hours < 0).any() or (hours[alerts.eq(0)] != 0).any():
            raise ValueError("reference staffing hours must be finite and nonnegative, and zero for no contacts")
    except FileNotFoundError as exc:
        raise ArtifactError(f"Policy-validation results are missing. {PREPARE_HELP}") from exc
    except (OSError, ValueError, TypeError, OverflowError, pd.errors.ParserError) as exc:
        raise ArtifactError(f"Policy-validation results are unreadable or invalid: {exc}. {PREPARE_HELP}") from exc
    return table, encounters, float(positives.iloc[0] / encounters)


def normalize_inputs(payload):
    if not isinstance(payload, dict):
        raise ValueError("Send a JSON object containing the four planning inputs.")
    if set(payload) != set(DEFAULTS):
        raise ValueError("Provide only discharges, capacity, recall_target, and minutes_per_contact. All four are required.")
    for name, low, high in [
        ("discharges", 1, 1_000_000),
        ("capacity", 0, 1_000_000),
        ("minutes_per_contact", 1, 240),
    ]:
        value = payload[name]
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{name} must be a whole number from {low:,} to {high:,}.")
    if payload["capacity"] > payload["discharges"]:
        raise ValueError("capacity cannot exceed discharges.")
    recall = payload["recall_target"]
    if type(recall) not in (int, float) or not 0 <= recall <= 100 or not math.isfinite(recall):
        raise ValueError("recall_target must be a finite number from 0 to 100 percent.")
    return {**payload, "recall_target": float(recall)}


def calculate_plan(table, encounters, prevalence, inputs):
    discharges = inputs["discharges"]
    budget = inputs["capacity"] * 1000 / discharges
    recall_floor = inputs["recall_target"] / 100
    best_recall = pick_policy(table, "recall", budget)
    selected = pick_policy(table, "precision", budget, recall_floor)
    feasible = selected is not None
    if not feasible:
        selected = best_recall
    scale = discharges / encounters
    contacts = float((selected["tp"] + selected["fp"]) * scale)
    meeting_target = table.loc[table["recall"] >= recall_floor]
    minimum_contacts = None
    if not meeting_target.empty:
        minimum_contacts = float((meeting_target["tp"] + meeting_target["fp"]).min() * scale)
    threshold = float(selected["threshold"])
    precision = float(selected["precision"])
    return {
        "feasible": feasible,
        "plan": {
            "threshold": threshold if math.isfinite(threshold) else None,
            "contacts": contacts,
            "true_positives": float(selected["tp"] * scale),
            "false_positives": float(selected["fp"] * scale),
            "missed": float(selected["fn"] * scale),
            "recall": float(selected["recall"]),
            "precision": precision if math.isfinite(precision) else None,
            "staff_hours": contacts * inputs["minutes_per_contact"] / 60,
        },
        "maximum_recall": float(best_recall["recall"]),
        "minimum_contacts_for_target": minimum_contacts,
        "reference": {"encounters": encounters, "prevalence": prevalence, "source": "Policy validation"},
        "constraints": inputs,
    }


def create_app(artifact_dir=None):
    app = Flask(__name__)
    app.config["ARTIFACT_DIR"] = Path(artifact_dir) if artifact_dir is not None else ROOT / "artifacts"

    @app.get("/")
    def index():
        return render_template("tool.html", defaults=DEFAULTS)

    @app.post("/api/plan")
    def plan():
        try:
            inputs = normalize_inputs(request.get_json())
        except (BadRequest, UnsupportedMediaType):
            return jsonify(error="Send a valid JSON object with Content-Type: application/json."), 400
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        try:
            table, encounters, prevalence = load_policy_table(app.config["ARTIFACT_DIR"])
        except ArtifactError as exc:
            return jsonify(error=str(exc)), 503
        return jsonify(calculate_plan(table, encounters, prevalence, inputs))

    return app


def prepare_artifacts():
    """Execute original notebook cells through Section 7 in an unsaved, fresh kernel."""
    import nbformat
    from jupyter_client import KernelManager
    from nbclient import NotebookClient

    notebook_path = ROOT / "Diabetes_Readmission_RAI_Skeleton.ipynb"
    notebook = nbformat.read(notebook_path, as_version=4)
    section_eight = re.compile(r"^#{1,6}\s+(?:Section\s+)?8[.)\s]", re.IGNORECASE | re.MULTILINE)
    stop = next(
        (index for index, cell in enumerate(notebook.cells)
         if cell.cell_type == "markdown" and section_eight.search(cell.source)),
        None,
    )
    if stop is None:
        raise RuntimeError("Cannot locate the Section 8 heading; refusing to execute any notebook cells.")
    notebook.cells = notebook.cells[:stop]
    code_cells = sum(cell.cell_type == "code" for cell in notebook.cells)
    print(f"Preparing policy validation: {code_cells} code cells through Section 7.", flush=True)
    print(f"Kernel Python: {sys.executable}", flush=True)
    print("This explicitly fits the notebook models and regenerates local artifacts. Held-out test evaluation is excluded.", flush=True)
    print("The saved notebook is not changed. Preparation may take several minutes.", flush=True)

    def show_progress(cell, cell_index, **kwargs):
        if cell.cell_type == "code":
            print(f"Executing notebook cell {cell_index + 1}/{len(notebook.cells)} ...", flush=True)

    manager = KernelManager(kernel_name="python3")
    # Do not rely on a notebook kernelspec pointing to a different environment.
    manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
    client = NotebookClient(
        notebook,
        km=manager,
        timeout=1800,
        allow_errors=False,
        resources={"metadata": {"path": str(ROOT)}},
        on_cell_start=show_progress,
    )
    client.execute(cleanup_kc=True)
    _, encounters, _ = load_policy_table(ROOT / "artifacts")
    print(f"Ready: {TABLE_NAME} from {encounters:,} policy-validation encounters.", flush=True)
    print("Start the planner with: python tool.py", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Local educational hospital follow-up capacity planner.")
    parser.add_argument("--prepare", action="store_true", help="Run the existing notebook through Section 7, without saving it or evaluating test data.")
    parser.add_argument("--port", type=int, default=8000, help="Local HTTP port (default: 8000).")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.prepare:
        try:
            prepare_artifacts()
        except Exception as exc:
            print(f"Preparation failed: {exc}", file=sys.stderr)
            return 1
        return 0
    print(f"Hospital follow-up planner: http://127.0.0.1:{args.port}", flush=True)
    print("Local educational planning using historical policy validation; not clinical advice.", flush=True)
    if not (ROOT / "artifacts" / TABLE_NAME).is_file():
        print(PREPARE_HELP, flush=True)
    create_app().run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
