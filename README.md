# Healthcare AI: Diabetes Readmission

## Scope and clinical purpose

The question is whether discharge-time information can help rank eligible
patients with recorded diabetes by risk of recorded inpatient readmission
**in fewer than 30 days after discharge**. This is retrospective educational
analysis, not a deployed tool or evidence that follow-up prevents readmissions.

## Files

| File / directory | Purpose |
|---|---|
| `Diabetes_Readmission_RAI_Skeleton.ipynb` | Executed Steps 1–5, plots, clinical framing, and group handoff |
| `environment.yml` | Pinned direct dependencies for the first-half scientific environment |
| `requirements-first-half.lock.txt` | Full package versions from the executed Python 3.10 environment |
| `Data/` | Downloaded public CSVs; generated locally and ignored by Git |
| `artifacts/` | Generated tables, figures, split manifest, provenance, and model files; ignored by Git |

## Install and quickstart

Run from the repository root. The notebook can be viewed without executing it.
To reproduce the analysis with the recorded dependency versions:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-first-half.lock.txt
python -m ipykernel install --prefix .venv --name healthcare-first-half --display-name "Healthcare first half (Python 3.10)"
jupyter lab
```

Alternatively, create the direct-dependency Conda environment:

```bash
conda env create -f environment.yml
conda activate healthcare-first-half
python -m ipykernel install --user --name healthcare-first-half --display-name "Healthcare first half (Python 3.10)"
jupyter lab
```

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

## Experimental design and measured results

Seed **42**, patient-disjoint partitions, no balancing:

| Partition | Encounters | Patients | Use |
|---|---:|---:|---|
| Training | 51,253 | 38,249 | Training-only EDA, preprocessing, fitting |
| Calibration validation | 5,422 | 4,098 | Reserved for calibrator fitting |
| Policy validation | 5,552 | 4,098 | Discrimination now; thresholds later |
| Final test | 10,864 | 8,197 | Reserved until full policy lock |

Separating calibration and policy validation prevents their fitting/selection
activities from using identical patients. All six pairwise patient-overlap
checks pass. No temporal or hospital split is claimed because the public file
lacks the necessary identifiers. No model tuning follows policy-set results.

The unweighted logistic-regression pipeline fits numeric imputation/scaling and
categorical imputation/encoding on training data only. It uses 17 original
predictors, generating 61 encoded features, and converged in 27 iterations.

**Policy-validation results, not final-test results:**

| Model | Average precision | ROC AUC |
|---|---:|---:|
| Training-prevalence baseline | 0.111 | 0.500 |
| Logistic regression | 0.250 | 0.672 |

Logistic AP 95% interval: **0.197–0.301**; ROC AUC interval:
**0.638–0.701**, using 300 patient-cluster bootstrap replicates.
AP is average precision, not trapezoidal PR AUC. Intervals condition on the
fitted model, exclude single-class replicates, and do not include training
uncertainty or adjust for multiple subgroup comparisons.

The age-80+ subgroup has lower observed ranking performance (ROC AUC 0.572,
755 encounters, 81 positives). This warrants later error/calibration review,
not an unsupported causal explanation or automatic age-based policy.
Several race and payer groups have very few events; the notebook retains their
counts, undefined metrics, and caution flags rather than claiming firm fairness
conclusions.

## Remaining work and responsible-AI handoff

1. **Calibration:** Use `X_cal/y_cal` with the base model frozen. Do not calibrate
   on policy or test data. Evaluate probability reliability on policy validation.
2. **Threshold selection:** Compare workload and recall policies on policy
   validation only. Budgets of 200/250 contacts per 1,000, 85% recall, and 40%
   precision are classroom aspirations, not achieved operating points.
3. **Final evaluation:** Lock model, calibration, features, and threshold before
   producing final-test predictions. Do not retune on test.
4. **RAI:** Establish compatible input/model representation; check default versus
   selected threshold semantics; investigate cohorts, fairness, errors,
   importance, counterfactuals, and causal assumptions.
5. **Presentation:** Use actual plots and results, clearly separating ranking,
   calibration, workload, fairness, and causal claims.

The notebook creates `artifacts/handoff.json`, `split_manifest.csv`,
`uncalibrated_logistic.joblib`, and `prevalence_baseline.joblib`.
Rerun the first half to regenerate dataframes and matrices; do not guess
preprocessing when loading a model. Load joblib files only from trusted sources
in the same compatible environment.

No calibration, threshold optimization, final-test metrics, or RAI dashboard
results are supplied by this first half. Patient identifiers never enter the
predictive feature matrix. Removing protected attributes alone does not establish
fairness; counterfactual changes and feature associations do not establish
treatment effects.

## Reference workflow

[IE-ML-for-Healthcare/RAI_opioid_risk_prevention](https://github.com/IE-ML-for-Healthcare/RAI_opioid_risk_prevention)
and the course Session 5–6 rubric, pages 6–8. The reference's synthetic OUD
findings do not transfer to these hospital records.
