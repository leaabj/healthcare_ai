# Healthcare AI: Diabetes Readmission

## Scope and clinical purpose

The question is whether discharge-time information can help rank eligible
patients with recorded diabetes by risk of recorded inpatient readmission
**in fewer than 30 days after discharge**, so that a discharge team can decide
whom to contact for follow-up within a fixed contact capacity. This is
retrospective educational analysis, not a deployed tool and not evidence that
follow-up prevents readmissions.

## Files

| File / directory | Purpose |
|---|---|
| `Diabetes_Readmission_RAI_Skeleton.ipynb` | Executed Steps 1–9: framing, data, splits, pipeline, discrimination, calibration, threshold policy, final test, Responsible AI analysis |
| `utils.py` | Small helpers used by Steps 6–9: calibration metrics, patient-cluster bootstrap, threshold table and policy choice, subgroup table, error-tree leaves, dashboard model wrappers |
| `tool.py`, `templates/`, `static/` | Compact local tool with planning-calculator and discharge-CSV modes |
| `requirements-tool.txt` | Tool and notebook-preparation dependencies without the Responsible AI stack |
| `examples/` | Header-only discharge template and explicitly synthetic demonstration records |
| `environment.yml` | Pinned direct dependencies, including the Responsible AI toolbox |
| `requirements.lock.txt` | Full package versions of the executed Python 3.10 environment |
| `requirements-first-half.lock.txt` | Package versions of the environment that executed Steps 1–5 (kept for provenance) |
| `Data/` | Original UCI encounter CSV and ID mappings, included in the repository |
| `artifacts/` | Generated tables, figures, split manifest, policy lock, model files and saved RAI insights; ignored by Git |

## Install and quickstart

Run from the repository root. The notebook can be viewed without executing it.
The Responsible AI toolbox (`responsibleai`/`raiwidgets` 0.36.0) requires
numpy ≤ 1.26.2, pandas < 2 and scikit-learn ≤ 1.5.1 on Python 3.10, which is
why every pin below must stay as it is.

With [uv](https://docs.astral.sh/uv/) (no conda needed):

```bash
uv python install 3.10
uv venv .venv --python 3.10
uv pip install --python .venv -r requirements.lock.txt
.venv/bin/python -m ipykernel install --prefix .venv --name healthcare-first-half --display-name "Healthcare first half (Python 3.10)"
.venv/bin/jupyter lab
```

With conda:

```bash
conda env create -f environment.yml
conda activate healthcare-ai
python -m ipykernel install --user --name healthcare-first-half --display-name "Healthcare first half (Python 3.10)"
jupyter lab
```

Open the notebook, select the kernel, and use **Restart kernel and run all**.
A full run takes about 12 minutes; most of it is counterfactual generation in
Step 9. The two `ResponsibleAIDashboard` cells start a local web server and
render the interactive dashboard inside the notebook. Saved insights in
`artifacts/rai_insights` can be reloaded with `RAIInsights.load` and passed to
`ResponsibleAIDashboard` without recomputing.

## Hospital Follow-up Tool

Use the compact toggle to switch between **Planning calculator** and
**Discharge CSV**. The planner estimates workload from historical validation
results. CSV mode counts uploaded records automatically, scores them, and lets
you view or download a capacity-limited list. A header-only template and clearly
**synthetic** example are available for the CSV demonstration.

Run with Python 3.10 using the existing project environment, or with `uv`:

```bash
# Once on a fresh clone: generate real model results through notebook Section 7.
uv run --no-project --python 3.10 --with-requirements requirements-tool.txt python tool.py --prepare

# Start the tool; open http://127.0.0.1:8000
uv run --no-project --python 3.10 --with-requirements requirements-tool.txt python tool.py
```

If both `artifacts/calibrated_logistic.joblib` and `artifacts/policy_threshold_table.csv` already exist,
skip preparation. In the installed project environment, use `python tool.py`
directly. Use `--port 8001` to choose a different local port.

Preparation runs the existing notebook through Section 7 in a fresh kernel,
regenerating its ignored artifacts (including the original policy lock), but
does not change the saved notebook or evaluate held-out test data. It does not
require the Responsible AI dashboard packages.

### Planning calculator

Enter eligible discharge volume, contact capacity, recall target, and minutes per
contact for the same period. The planner uses the calibrated model's historical
policy-validation threshold sweep, selecting highest precision subject to the
capacity and recall constraints. Infeasible requests show the best recall within
capacity and the minimum projected contacts needed for the requested recall.
Displayed readmissions identified/missed and precision/recall are historical
projections—not measurements of an uploaded group or guarantees for a hospital.
Changing planning inputs does not modify the notebook's locked policy.

### Discharge CSV

The tool scores records with the saved calibrated logistic model; it does not
retrain on uploads or use the test set. It selects the highest predicted risks
up to capacity. **This is a new capacity-based demonstration policy, not the
notebook's locked threshold or a clinically validated recommendation.** If equal
risks straddle the last available contact, the entire boundary group is marked
**Review tie** rather than choosing patients arbitrarily. Higher-risk records
remain selected; remaining slots need manual review. Zero capacity selects none,
and capacity above the number of records selects all. Staff hours count only
automatic selections at the entered minutes per contact.

### CSV contract

One row per eligible discharge, not necessarily one per unique person. The file
must contain `discharge_reference` plus all 17 model predictors; column order may
vary. Extra columns (including names or readmission outcomes) are rejected.

| Fields | Required representation |
|---|---|
| `discharge_reference` | Unique pseudonymous reference, 1–64 ASCII letters/digits/underscore/dot/hyphen; starts with a letter or digit |
| `time_in_hospital` | Whole days, 1–14 |
| `num_lab_procedures`, `num_procedures`, `num_medications`, `number_diagnoses` | Nonnegative whole-number counts from the index stay |
| `number_outpatient`, `number_emergency`, `number_inpatient` | Nonnegative whole-number visits during the preceding year |
| `age` | Released age band, e.g. `[60-70)`, ages 20+ only |
| `race`, `gender` | Exact category names used by the trained model |
| `admission_type_id`, `admission_source_id` | UCI category codes, not arbitrary hospital codes; see `Data/IDS_mapping.csv` |
| `A1Cresult` | `None` (not measured), `Norm`, `>7`, or `>8` |
| `insulin` | `No`, `Steady`, `Up`, or `Down` |
| `change`, `diabetesMed` | `No`/`Ch` and `No`/`Yes`, respectively |

Use UTF-8 CSV (a BOM is accepted), at most 2 MiB and 5,000 records. Numeric counts
other than stay duration are capped at 10,000 as an input sanity bound, not a
clinical validity guarantee. Only race may be blank or `?`; it uses the existing
training-fitted imputation with a warning. Literal `None` in HbA1c is preserved.
Unknown categories, missing required values, duplicate references, malformed rows,
and unsafe reference formats are rejected rather than silently repaired.

The uploader must confirm the file is already filtered to diabetes-coded adults
aged 20+ with eligible home/outpatient discharge codes **1, 6, 7, 8, 16, 17**.
Age is checked, but diabetes eligibility and discharge destination cannot be
verified from the 17 predictors alone. A hospital export requires explicit
mapping to these definitions; uploading an arbitrary export is not sufficient.

### Interpretation and privacy

Results contain a discharge reference, predicted recorded-readmission risk, and
selection/review status. **Actual recall, precision, readmissions missed, and
benefit cannot be measured without future outcomes.** The tool does not fabricate
those metrics, infer that contacting someone prevents readmission, or advise
changes to medication/testing. Predictions come from historical 1999–2008 data;
current hospital use requires external validation, subgroup assessment, privacy
approval, and clinical governance. Standard care must not be withheld based on
selection status.

Use synthetic or appropriately deidentified records only. Pseudonymous references
and omission of names do not by themselves establish deidentification. The server
binds to localhost, accepts CSV text in memory, and does not save uploads or
results. No third-party services, browser persistent storage, or model uploads
are used. Scoring responses use `Cache-Control: no-store`; clearing the interface
removes its displayed results and download link. Downloaded CSVs remain on the
user's device and are their responsibility. These measures are not a compliance
certification or secure-erasure guarantee. Do not expose the development server
on a network. Load only trusted locally generated joblib artifacts.

Focused regression checks: `python -m unittest discover -s tests -v`.

## Data and cohort

- Source: [Diabetes 130-US Hospitals, 1999–2008](https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008).
- Real deidentified records, not synthetic data: 101,766 source encounters.
- Target: `readmitted == "<30"` versus `">30"` or `"NO"`.
- Eligible cohort: age 20+ and documented home/outpatient discharge codes
  **1, 6, 7, 8, 16, 17**, including departures against medical advice.
- Deaths, hospice, facility transfers, ongoing stays, and uncertain destinations
  are excluded. The exact mappings and sequential counts are saved.
- Implemented cohort: **73,091 encounters / 54,642 patients**.
- Age is released in ten-year bands; exact 18+ eligibility cannot be recovered.
- Literal `None` for HbA1c means not measured, not normal. `?` represents missing data.
- Out-of-network readmissions are not captured. Historical participating
  institutions and the restricted follow-up cohort limit generalizability.

Source documentation and citation:
Clore et al. (2014), DOI [10.24432/C5230J](https://doi.org/10.24432/C5230J);
Strack et al. (2014), [source paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC3996476/).
The dataset is **CC BY 4.0**; attribute it when sharing derived data or results.
No changes have been made to the source CSV contents; the notebook verifies
their SHA-256 hashes.

## Experimental design

Seed **42**, patient-disjoint partitions, no resampling or class weighting:

| Partition | Encounters | Patients | Use |
|---|---:|---:|---|
| Training | 51,253 | 38,249 | Training-only EDA, preprocessing, fitting |
| Calibration validation | 5,422 | 4,098 | Calibrator fitting only |
| Policy validation | 5,552 | 4,098 | Discrimination, calibration assessment, threshold selection, RAI exploration |
| Final test | 10,864 | 8,197 | One evaluation after the policy lock |

All six pairwise patient-overlap checks pass. No temporal or hospital split is
possible because the public file lacks the identifiers. The prespecified model
is an unweighted L2 logistic-regression pipeline over 17 raw predictors (61
encoded features), fitted on training data only. Uncertainty intervals are
percentile intervals from 300 patient-cluster bootstrap replicates and
condition on the fitted model; undefined replicates are dropped and counted.

## Results

**Discrimination (policy validation, Step 5).** AP 0.250 (95% interval
0.197–0.301) versus a prevalence of 0.111; ROC AUC 0.672 (0.638–0.701). The
age-80+ subgroup has lower ranking performance (ROC AUC 0.572).

**Calibration (Step 6).** Platt scaling fitted on the calibration partition
with the base model frozen. On policy validation the calibrated model has
Brier 0.093 (0.086–0.101) against 0.099 for a constant-prevalence prediction,
quantile-bin ECE 0.014 (0.009–0.024), mean predicted risk 0.100 against an
observed rate of 0.111, and unchanged ranking. The highest-risk tenth predicts
0.25 while 0.30 were readmitted. Calibration changes little because a logistic
model is already on a probability scale.
ECE uses up to ten score-quantile bins, keeping identical predictions together.
Ties may reduce the number of occupied bins or make their sizes unequal; the
constant-prevalence baseline has one bin. The `ece_equal_count` columns refer
to this approximately equal-count strategy. This corrects the earlier
row-order-dependent tie splitting without changing predictions or policy.

**Threshold policy (Step 7).** Candidates are every distinct calibrated score
with the rule *contact if score ≥ threshold*. Two methods plus an illustrative
harm-weight sensitivity were compared on policy validation; the prespecified
joint rule (200 contacts per 1,000 and 85% recall) is infeasible, because 85%
recall needs 726 contacts per 1,000 at precision 0.13. The locked policy is
therefore the workload policy at the primary budget: threshold **0.1165**,
with per 1,000 discharges 199 contacts, 45 contacts to patients later
readmitted, 154 unnecessary contacts, 66 missed readmissions, and about 66
staff hours at an assumed 20 minutes per contact (recall 0.41, precision 0.23).
The 40% precision and 85% recall aspirations cannot hold together with this
model. The lock is written to `artifacts/policy_lock.json` before any test row
is read.

**Final test (Step 8), evaluated once.** AP 0.180 (0.157–0.204) at a test
prevalence of 0.095 (1.9× prevalence, against 2.3× on policy validation),
ROC AUC 0.647 (0.627–0.669), Brier 0.083, ECE 0.007. At the locked threshold:
182 contacts per 1,000 (within budget), recall 0.36 (0.32–0.40), precision
0.19 (0.17–0.21), 148 unnecessary contacts and 61 missed readmissions per
1,000. Recall and precision are below the policy-validation values and outside
the test intervals: the validation numbers were the best of thousands of
candidates on one sample, and the lower test prevalence lowers precision. The
threshold was not changed. Subgroup checks at the locked threshold show
patients aged 80+ contacted most often (selection rate 0.28, false-positive
rate 0.26), the highest recall for ages 20–39 (0.51), and 13 subgroup rows
with too few patients for any disparity claim.

**Responsible AI (Step 9).** `RAIInsights` is built for the locked calibrated
model wrapped so that `predict` applies the locked threshold, on 10,000
training and 2,000 policy-validation encounters with training-fitted imputation
of the 2% missing race values. Findings:

- *Cohorts:* patients with a prior inpatient stay are 32% of encounters, have a
  16% readmission rate against 10% overall, and 56% of them are contacted; the
  83% of stays without an HbA1c test have a readmission rate close to average.
- *Fairness at the locked threshold:* recall ranges from 0.36 to 0.51 across
  adequately supported groups; unnecessary contacts fall most on patients aged
  80+; calibration ratios stay near 1 for large groups.
- *Error analysis:* the highest-error leaf of the dashboard tree, encounters
  with 2–6 prior inpatient visits, has a contact rate of 0.86 and an error rate
  of 0.67 made almost entirely of unnecessary contacts: a cohort the model
  over-flags rather than misses.
- *Importance:* prior inpatient visits dominate, followed by diagnosis count,
  insulin, age and HbA1c result, in both the mimic explainer and the exact
  logistic odds ratios.
- *Counterfactuals:* DiCE flips classes at 0.50, not at the locked threshold,
  so the dashboard view does not describe the policy (actionable
  counterfactuals for 0.6% of encounters). Recomputed against the policy
  boundary, changing only testing and treatment fields flips 36% of
  encounters, so the contact decision is sensitive to how in-hospital care is
  documented; the changes reflect model weights, not recourse a clinician could
  offer.
- *Causal:* a recorded HbA1c result above 8 is associated with 0.034 (95%
  interval 0.014–0.055) lower readmission probability than no test under an
  explicit pre-treatment adjustment set, and 0.031 when the dashboard also
  adjusts for in-hospital treatment variables; exploratory and
  assumption-dependent. Whether follow-up contacts prevent readmission is not
  estimable from these data.
- *Risks and monitoring (9.7):* unequal contact burden on patients aged 80+,
  over-flagging of frequently hospitalised patients, and sensitivity to
  documentation and drift, each with a mitigation, a monitoring measure and a
  trigger; plus a clinician-ready conclusion.

## Reproducibility, governance and license

Seed 42 throughout; the split manifest, policy lock, environment versions,
data provenance and hashes are saved to `artifacts/`. Patient identifiers never
enter the feature matrix. Calibration uses the calibration partition only,
threshold selection uses policy validation only, and the test partition is read
once after the lock; the gate in Step 8 checks internal consistency, and the
no-peeking guarantee is procedural (one run from a fresh kernel). Removing
protected attributes alone does not establish fairness; feature importance,
counterfactuals and the causal estimates describe model behaviour and
associations, not treatment effects. Data license: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Reference workflow

[IE-ML-for-Healthcare/RAI_opioid_risk_prevention](https://github.com/IE-ML-for-Healthcare/RAI_opioid_risk_prevention)
and the course Session 5–6 rubric. The reference's synthetic OUD findings do
not transfer to these hospital records.
