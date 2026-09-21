"""Local historical capacity planning and in-memory discharge-list scoring."""

import argparse
import csv
import io
import math
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
import warnings

import joblib
import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file
from sklearn.calibration import CalibratedClassifierCV
from sklearn.exceptions import InconsistentVersionWarning
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, UnsupportedMediaType

from utils import pick_policy, positive_proba


ROOT = Path(__file__).resolve().parent
DEFAULTS = {
    "discharges": 1000, "capacity": 200, "recall_target": 35, "minutes_per_contact": 20,
}
SCORE_DEFAULTS = {"capacity": 30, "minutes_per_contact": 20}
TABLE_NAME = "policy_threshold_table.csv"
NUMERIC_FEATURES = (
    "time_in_hospital", "num_lab_procedures", "num_procedures", "num_medications",
    "number_outpatient", "number_emergency", "number_inpatient", "number_diagnoses",
)
CATEGORICAL_FEATURES = (
    "age", "race", "gender", "admission_type_id", "admission_source_id",
    "A1Cresult", "insulin", "change", "diabetesMed",
)
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
CSV_COLUMNS = ("discharge_reference",) + FEATURES
MODEL_NAME = "calibrated_logistic.joblib"
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000
PREPARE_HELP = "Run python tool.py --prepare in the pinned project environment to prepare the trusted local model."
MODEL_ERROR = "The trusted local model is missing or incompatible. " + PREPARE_HELP
MODEL_WARNING = (
    "This historical model is not clinically validated on current patients. "
    "Observed recall, precision, and clinical benefit for this list are unknown."
)
REFERENCE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")


class ArtifactError(ValueError):
    """Local model or policy-validation artifacts cannot safely support the request."""


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


def load_model(artifact_dir):
    """Load only the fixed local artifact and derive its fitted feature/category schema."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", InconsistentVersionWarning)
            model = joblib.load(Path(artifact_dir) / MODEL_NAME)
        if not isinstance(model, CalibratedClassifierCV):
            raise ValueError
        if list(model.classes_) != [0, 1] or len(model.calibrated_classifiers_) != 1:
            raise ValueError
        features = tuple(model.feature_names_in_)
        if len(features) != len(FEATURES) or set(features) != set(FEATURES):
            raise ValueError
        estimator = model.calibrated_classifiers_[0].estimator
        preprocess = estimator.named_steps["preprocess"]
        if tuple(preprocess.feature_names_in_) != features:
            raise ValueError
        transformers = {name: (transformer, tuple(columns))
                        for name, transformer, columns in preprocess.transformers_}
        numeric, numeric_columns = transformers["numeric"]
        categorical, categorical_columns = transformers["categorical"]
        if (len(numeric_columns) != len(NUMERIC_FEATURES)
                or set(numeric_columns) != set(NUMERIC_FEATURES)
                or len(categorical_columns) != len(CATEGORICAL_FEATURES)
                or set(categorical_columns) != set(CATEGORICAL_FEATURES)):
            raise ValueError
        if any(columns for name, (_, columns) in transformers.items()
               if name not in {"numeric", "categorical"}):
            raise ValueError
        encoder = categorical.named_steps["encode"]
        imputer = categorical.named_steps["impute"]
        if len(encoder.categories_) != len(categorical_columns):
            raise ValueError
        if imputer.strategy != "most_frequent" or len(imputer.statistics_) != len(categorical_columns):
            raise ValueError
        categories = {}
        for name, values, fill in zip(categorical_columns, encoder.categories_, imputer.statistics_):
            if not len(values) or not all(isinstance(value, str) for value in values):
                raise ValueError
            categories[name] = frozenset(values)
            if fill not in categories[name]:
                raise ValueError
        return model, features, categories
    except Exception:
        raise ArtifactError(MODEL_ERROR) from None


def parse_csv(raw, features, categories):
    """Validate every field before constructing the model frame; never drop columns."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("The CSV must be UTF-8 encoded.") from None
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    references, records, seen = [], [], set()
    missing_race = False
    try:
        header = next(reader, None)
        if (header is None or len(header) != len(CSV_COLUMNS)
                or len(set(header)) != len(header) or set(header) != set(CSV_COLUMNS)):
            raise ValueError("CSV columns must be discharge_reference and exactly the 17 template features, with no duplicates or extra columns.")
        for row_number, row in enumerate(reader, start=2):
            if len(records) >= MAX_ROWS:
                raise ValueError("The CSV may contain at most 5000 records.")
            if len(row) != len(header):
                raise ValueError(f"CSV row {row_number} has an incorrect number of columns.")
            values = dict(zip(header, row))
            reference = values.pop("discharge_reference")
            if not REFERENCE_PATTERN.fullmatch(reference):
                raise ValueError(f"CSV row {row_number}: discharge_reference must be 1–64 safe ASCII letters, digits, periods, underscores or hyphens, starting with a letter or digit.")
            if reference in seen:
                raise ValueError(f"CSV row {row_number}: discharge_reference must be unique.")
            seen.add(reference)
            for name in NUMERIC_FEATURES:
                value = values[name]
                # Decimal integers only: no rounding, nonfinite values or imputation.
                maximum = 14 if name == "time_in_hospital" else 10000
                minimum = 1 if name == "time_in_hospital" else 0
                if not re.fullmatch(r"[0-9]{1,5}", value) or not minimum <= int(value) <= maximum:
                    raise ValueError(f"CSV row {row_number}: {name} must be a whole number from {minimum} to {maximum}.")
                values[name] = int(value)
            for name in CATEGORICAL_FEATURES:
                value = values[name]
                if name == "race" and value in {"", "?"}:
                    values[name] = np.nan
                    missing_race = True
                    continue
                if name == "age":
                    age = re.fullmatch(r"\[([0-9]+)-([0-9]+)\)", value)
                    if age is None or int(age[1]) < 20:
                        raise ValueError(f"CSV row {row_number}: age must be an eligible adult age band (20+).")
                if name == "gender" and value not in {"Female", "Male"}:
                    raise ValueError(f"CSV row {row_number}: gender must be Female or Male.")
                if name in {"admission_type_id", "admission_source_id"} and not re.fullmatch(r"[1-9][0-9]*", value):
                    raise ValueError(f"CSV row {row_number}: {name} must use a canonical admission code.")
                if value not in categories[name]:
                    raise ValueError(f"CSV row {row_number}: {name} is not a category supported by the fitted model.")
            references.append(reference)
            records.append(values)
    except csv.Error:
        raise ValueError(f"Malformed CSV near row {reader.line_num}.") from None
    if not records:
        raise ValueError("The CSV must contain at least one discharge record.")
    return references, pd.DataFrame.from_records(records, columns=features), missing_race


def select_discharges(references, risks, capacity, minutes_per_contact):
    """Reserve the entire boundary tie for review instead of choosing arbitrary members."""
    rows = sorted(
        ({"discharge_reference": reference, "risk": float(risk), "selected": False, "review": False}
         for reference, risk in zip(references, risks)),
        key=lambda row: (-row["risk"], row["discharge_reference"]),
    )
    limit = min(capacity, len(rows))
    boundary = rows[limit - 1]["risk"] if limit else None
    tied_boundary = bool(limit and limit < len(rows) and rows[limit]["risk"] == boundary)
    for index, row in enumerate(rows):
        row["review"] = tied_boundary and row["risk"] == boundary
        row["selected"] = index < limit and not row["review"]
    selected = sum(row["selected"] for row in rows)
    return {
        "summary": {
            "records": len(rows), "capacity": capacity, "selected": selected,
            "review": sum(row["review"] for row in rows),
            "remaining_capacity": capacity - selected,
            "staff_hours": selected * minutes_per_contact / 60,
            "boundary_risk": boundary,
        },
        "rows": rows,
    }


def scoring_inputs(args):
    if set(args) != {"capacity", "minutes_per_contact", "eligible"} or any(len(args.getlist(name)) != 1 for name in args):
        raise ValueError("Provide capacity, minutes_per_contact and eligible exactly once.")
    if args["eligible"] != "true":
        raise ValueError("Confirm the list contains only prefiltered diabetes-coded adults aged 20+ with eligible home/outpatient discharges.")
    inputs = {}
    for name, minimum, maximum in (("capacity", 0, MAX_ROWS), ("minutes_per_contact", 1, 240)):
        value = args[name]
        if not re.fullmatch(r"[0-9]{1,4}", value) or not minimum <= int(value) <= maximum:
            raise ValueError(f"{name} must be an integer from {minimum} to {maximum}.")
        inputs[name] = int(value)
    return inputs


def create_app(artifact_dir=None):
    app = Flask(__name__)
    app.config["ARTIFACT_DIR"] = Path(artifact_dir) if artifact_dir is not None else ROOT / "artifacts"
    app.config["MAX_CONTENT_LENGTH"] = MAX_BYTES

    @app.before_request
    def require_local_origin():
        # Reject cross-origin browser traffic, including simple text/csv POSTs.
        try:
            target = urlsplit(request.host_url)
            if target.hostname not in {"127.0.0.1", "localhost", "::1"}:
                return jsonify(error="Use the localhost address for this tool."), 400
            origin = request.headers.get("Origin")
            if origin is not None:
                source = urlsplit(origin)
                if (source.scheme, source.hostname, source.port) != (target.scheme, target.hostname, target.port) or source.path or source.query or source.fragment or source.username is not None:
                    return jsonify(error="Only same-origin local requests are accepted."), 400
        except ValueError:
            return jsonify(error="Only same-origin local requests are accepted."), 400
        if request.headers.get("Sec-Fetch-Site") not in {None, "same-origin", "none"}:
            return jsonify(error="Only same-origin local requests are accepted."), 400

    @app.after_request
    def prevent_caching(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def oversized_request(error):
        return jsonify(error="The CSV request must not exceed 2 MiB."), 413

    @app.get("/")
    def index():
        return render_template("tool.html", defaults=DEFAULTS, score_defaults=SCORE_DEFAULTS)

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

    @app.get("/template.csv")
    def template():
        return send_file(ROOT / "examples" / "discharge_template.csv", mimetype="text/csv", as_attachment=True, conditional=False, etag=False)

    @app.get("/example.csv")
    def example():
        return send_file(ROOT / "examples" / "discharge_example.csv", mimetype="text/csv", as_attachment=True, conditional=False, etag=False)

    @app.post("/api/score")
    def score():
        if request.mimetype != "text/csv" or request.mimetype_params.get("charset", "utf-8").lower() not in {"utf-8", "utf8"}:
            return jsonify(error="Send UTF-8 CSV with Content-Type: text/csv."), 400
        try:
            inputs = scoring_inputs(request.args)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        raw = request.get_data(cache=False)
        if len(raw) > MAX_BYTES:
            raise RequestEntityTooLarge
        try:
            model, features, categories = load_model(app.config["ARTIFACT_DIR"])
        except ArtifactError:
            return jsonify(error=MODEL_ERROR), 503
        try:
            references, frame, missing_race = parse_csv(raw, features, categories)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        try:
            risks = np.asarray(positive_proba(model, frame), dtype=float)
            if risks.shape != (len(frame),) or not np.isfinite(risks).all() or ((risks < 0) | (risks > 1)).any():
                raise ValueError
        except Exception:
            return jsonify(error=MODEL_ERROR), 503
        result = select_discharges(references, risks, **inputs)
        result["warnings"] = [MODEL_WARNING]
        if missing_race:
            result["warnings"].append("Missing race values were imputed using the model's fitted training-cohort mode, not inferred from this list.")
        return jsonify(result)

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
    print(f"Preparing the calibrated model: {code_cells} code cells through Section 7.", flush=True)
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
    load_model(ROOT / "artifacts")
    print(f"Ready: {MODEL_NAME} with the required 17-feature fitted schema.", flush=True)
    print("Start the discharge-list tool with: python tool.py", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Local educational discharge-list risk scoring.")
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
    print(f"Discharge-list tool: http://127.0.0.1:{args.port}", flush=True)
    print(MODEL_WARNING, flush=True)
    if not (ROOT / "artifacts" / MODEL_NAME).is_file():
        print(PREPARE_HELP, flush=True)
    create_app().run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
