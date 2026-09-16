# Step 1: Clinical Problem Framing & Study Objective

**Status:** Proposed study framing; no model results are reported in this document.

## 1.1 Clinical Question

**Primary question:**

> Can information available at hospital discharge identify patients with a recorded diabetes diagnosis who are at higher risk of recorded inpatient readmission in fewer than 30 days, to help clinical staff prioritize post-discharge follow-up?

This is a **retrospective prediction study**, not a trial of whether model-guided interventions reduce readmissions.

### Structured study question

| Element | Definition |
|---|---|
| **Population** | Eligible inpatient encounters involving patients aged 20+ with a recorded diabetes diagnosis in the source dataset |
| **Index model** | A machine-learning risk model using information available by discharge |
| **Comparator** | A prevalence-only baseline, with logistic regression as the initial predictive model |
| **Outcome** | Recorded inpatient readmission in fewer than 30 days after discharge |
| **Intended use** | Support prioritization of follow-up, diabetes education, and care-coordination review |

**Why not claim comparison against clinical judgment or LACE?** The dataset does not contain clinician risk judgments, and a valid LACE comparison would require confirming that all components can be reconstructed. These are potential future comparisons, not evaluations already supported by the planned analysis.

## 1.2 Clinical Context & Motivation

Hospital readmissions create additional care needs, patient disruption, and healthcare expenditure. Patients with diabetes may have complex medication regimens and comorbidities that make discharge planning and continuity of care particularly important.

The source dataset contains **101,766 inpatient encounters** across **130 US hospitals and integrated delivery networks from 1999–2008**. In the unfiltered public dataset, **11,357 encounters—11.16%—have the `<30` readmission label**. Prevalence must be recalculated after applying our eligibility criteria.

The source study used the Cerner Health Facts data warehouse. It notes that **out-of-network care is not captured**, so recorded readmission is an imperfect measure of all subsequent hospital use. See the [source study](https://pmc.ncbi.nlm.nih.gov/articles/PMC3996476/).

### Why investigate a predictive model?

A model may help rank patients consistently using available clinical and utilization information. However:

- It must demonstrate improvement over a simple baseline.
- High predicted risk does not necessarily mean greater benefit from intervention.
- Alerts create review workload; deployment is not “without additional clinical burden.”
- A basic logistic-regression model does not automatically capture complex interactions unless they are explicitly modeled.

**Policy context:** CMS’s Hospital Readmissions Reduction Program covers selected conditions and procedures, **not diabetes as a standalone measure**, and payment reductions began in fiscal year 2013—after this dataset’s observation period. It provides broader motivation for care coordination, not a direct policy outcome for this study. See [CMS HRRP](https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/hospital-readmissions-reduction-program-hrrp).

No specific national cost estimate or blanket performance claim for existing clinical scores is assumed here. Such claims require a source identifying the applicable population and year.

## 1.3 Target Population

| Criterion | Definition |
|---|---|
| **Age** | Age **20+**, using the released 10-year age bands. Patients aged 18–19 cannot be separated from other patients in `[10–20)` |
| **Diabetes eligibility** | Use the source dataset’s inclusion of encounters during which diabetes was recorded; diabetes need not be the primary reason for admission |
| **Source eligibility** | Inpatient stay of 1–14 days, with laboratory tests performed and medications administered |
| **Proposed exclusions** | Death during admission, hospice discharge, and transfers **out** to facilities outside the intended outpatient follow-up pathway, identified using the discharge-code mappings |
| **Repeated encounters** | May be retained, but all encounters from one patient must remain in the same data partition |
| **Target variable** | `1` when `readmitted == "<30"`; `0` when `readmitted` is `">30"` or `"NO"` |

### Important cohort decisions

- Do not automatically impose a new `249.xx/250.xx` restriction on the three released diagnosis columns. The source already selected diabetes-coded encounters; an additional restriction could create a different population.
- Transfers **into** the hospital and transfers **out at discharge** are different eligibility questions.
- Obstetric admissions and discharge against medical advice should not be excluded without a documented clinical reason and a reliable identification rule. Such exclusions could remove vulnerable patients.
- Describe the outcome as **recorded readmission regardless of cause**, not specifically diabetes-caused, unplanned, or preventable readmission.
- Document the exact discharge codes and encounter/patient counts for every implemented exclusion before model evaluation.

## 1.4 Decision Context & Deployment Scenario

### Proposed workflow

1. An eligible patient approaches hospital discharge.
2. The model uses information available by discharge to estimate early-readmission risk.
3. A threshold, selected on policy-validation data, identifies patients for additional review.
4. Nurses, case managers, or diabetes educators assess appropriate support, such as:
   - Diabetes education.
   - Medication-reconciliation review.
   - Follow-up appointment scheduling.
   - Post-discharge telephone contact.

**End users:** Nurses, case managers, and diabetes educators.

**Role:** Decision support—not automatic treatment allocation, discharge delay, or denial of care.

**Prediction timing:** Admission-time prediction would be a different project. It would require a new feature-availability assessment and removal of whole-admission information, such as final length of stay and total procedures. The public extract does not reliably timestamp all features at 24–48 hours.

## 1.5 Success Criteria

The following are **proposed targets to investigate**, not expected results or established clinical standards.

| Dimension | Proposed criterion | Interpretation |
|---|---|---|
| **Recall** | Explore whether ≥85% is feasible | Identify a high proportion of encounters with recorded early readmission |
| **Precision** | Explore whether ≥40% is feasible | Limit contacts concerning patients without recorded early readmission |
| **Discrimination** | Compare average precision and ROC AUC against the prevalence baseline | Establish whether the model meaningfully improves ranking |
| **ROC AUC aspiration** | 0.75, if retained, is an aspirational benchmark | Not a guarantee or sufficient evidence of clinical usefulness |
| **Calibration** | Evaluate reliability plots, Brier score, and comparison with the baseline | Assess whether probabilities correspond to observed frequencies |
| **Workload** | Compare budgets of 200 and 250 flagged discharges per 1,000 | Explicit planning scenarios—not measured staffing capacity |
| **Subgroups** | Report performance, event counts, and uncertainty | Identify potential disparities without overinterpreting small groups |

**Do not use Brier ≤0.18 as a success criterion.** At the raw prevalence of 11.16%, a constant prediction equal to prevalence has an expected Brier score of:

$$
p(1-p) \approx 0.1116(1-0.1116) = 0.0991
$$

A model scoring 0.18 could therefore pass that threshold while performing worse than this simple benchmark. Brier score also reflects more than calibration alone. In the actual evaluation, fit the prevalence-only baseline on training data and measure its Brier score on the designated evaluation partition; do not estimate a baseline prediction from final-test labels.

If the recall, precision, and workload requirements cannot be met together, report **infeasibility**, rather than adjusting the requirements after inspecting the test set.

## 1.6 Constraints & Limitations

| Constraint | Impact on the study |
|---|---|
| **Historical data, 1999–2008** | Performance may not transfer to current coding, treatment, and discharge practices |
| **Selected hospitals participating in one EHR data warehouse** | Multiple hospitals are represented, but the sample is not necessarily representative of all US or international hospitals |
| **Out-of-network readmissions not captured** | Some negative labels may reflect incomplete observation |
| **Age bands rather than exact ages** | Cannot isolate all adults aged 18+ |
| **Limited social information** | Payer information exists, but income, education, housing stability, and social support are not adequately represented |
| **Missing or imperfectly recorded demographic information** | Subgroup analyses may be affected by missingness and recording practices |
| **No suitable public dates or hospital identifiers** | A genuine temporal or hospital-held-out split is not supported |
| **No evaluated follow-up intervention** | Cannot estimate how many readmissions model-guided care would prevent |

These are **deidentified clinical records**, not a synthetic patient dataset. Deidentification does not itself establish demographic misclassification.

## 1.7 Potential Harms & Mitigations

| Harm | Description | Proposed mitigation |
|---|---|---|
| **False negatives** | Patients subsequently readmitted are not prioritized | Evaluate recall/FNR; maintain standard discharge care for everyone |
| **False positives** | Additional contacts, patient burden, and diverted staff time | Set an explicit total-alert budget and explain uncertainty |
| **Unequal performance** | Some groups may experience more missed cases or unnecessary contacts | Report subgroup metrics, event counts, uncertainty, and calibration |
| **Over-reliance** | Staff may treat the score as a definitive clinical judgment | Preserve clinician review and document the intended use |
| **Misinterpreted benefit** | High risk is mistaken for preventable risk or intervention responsiveness | Separate risk prediction from treatment-effect claims |

Subgroup-specific thresholds are **not an automatic fairness fix**. They require explicit justification, assessment of competing harms, and appropriate ethical/legal review.

## 1.8 “So What?” Summary

> **Illustrative scenario—not a model result:** If the eligible cohort had an early-readmission rate of approximately 11.16%, and the model achieved 85% recall and 40% precision, then among 1,000 eligible discharges it would flag approximately **237**. About **95** flagged encounters would have a recorded early readmission, about **142** would not, and about **17** early readmissions would be missed. This would fit a budget of 250 contacts per 1,000 discharges, but not a budget of 200.

The workload follows from:

$$
\text{Alerts per 1,000} =
\frac{1,000 \times \text{prevalence} \times \text{recall}}{\text{precision}}
$$

This illustration assumes one contact per flagged discharge. Repeated outreach or multiple services would require additional staff time. Recalculate the figures using the eligible cohort’s prevalence and measured validation performance.

**These figures describe identification and workload—not readmissions prevented.** Demonstrating prevention would require a prospective evaluation of the follow-up intervention.

## References

1. Clore, J., Cios, K., DeShazo, J., & Strack, B. (2014). [Diabetes 130-US Hospitals for Years 1999–2008](https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008). UCI Machine Learning Repository. DOI: [10.24432/C5230J](https://doi.org/10.24432/C5230J). Dataset license: CC BY 4.0. The raw `<30` count cited above was calculated from the public CSV.
2. Strack, B., et al. (2014). [Impact of HbA1c Measurement on Hospital Readmission Rates: Analysis of 70,000 Clinical Database Patient Records](https://pmc.ncbi.nlm.nih.gov/articles/PMC3996476/). BioMed Research International. DOI: [10.1155/2014/781670](https://doi.org/10.1155/2014/781670).
3. Centers for Medicare & Medicaid Services. [Hospital Readmissions Reduction Program](https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/hospital-readmissions-reduction-program-hrrp).
