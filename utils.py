"""Helpers for Sections 6-9 of the readmission notebook.

- positive_proba(estimator, X): positive-class probabilities from a fitted classifier.
- calibration_metrics(y, p): Brier, log loss, quantile-bin ECE, mean predicted, observed prevalence.
- reliability_table(y, p, n_bins): tie-preserving quantile risk bands with mean predicted and observed rates.
- patient_bootstrap(stat_fn, frame, patient_col, ...): patient-cluster percentile interval for any statistic.
- calibration_intervals(frame, patient_col, ...): bootstrap intervals for Brier and ECE of a frame with columns y, p.
- threshold_table(y, p, minutes_per_contact, thresholds=None): confusion counts and per-1,000 impact per threshold.
- pick_policy(table, objective, ...): deterministic policy choice under an alert budget and/or recall floor.
- subgroup_policy_table(frame, ...): error, selection and calibration metrics per subgroup at a fixed threshold.
- ThresholdedEstimator: wrapper whose .predict applies the locked threshold, for the RAI dashboard.
- error_tree_leaves(tree): leaf cohorts of the dashboard's error-analysis tree with rule, size and error rate.
- leaf_mask(frame, rule): boolean mask selecting the encounters of such a leaf.
- PolicyScaleEstimator: variant whose predict_proba puts the locked threshold at 0.5, for counterfactual generation only.
"""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.metrics import brier_score_loss, log_loss


def positive_proba(estimator, X):
    return estimator.predict_proba(X)[:, list(estimator.classes_).index(1)]


def reliability_table(y, p, n_bins=10):
    """Up to n_bins quantile bands (1 = lowest risk), keeping equal scores together.

    Ties can produce unequal counts or fewer occupied bands; constant scores form one band.
    """
    frame = pd.DataFrame({"y": np.asarray(y), "p": np.asarray(p)})
    boundaries = np.unique(np.quantile(frame["p"], np.linspace(0, 1, n_bins + 1)[1:-1]))
    frame["band"] = np.searchsorted(boundaries, frame["p"], side="left") + 1
    table = frame.groupby("band", observed=True).agg(
        records=("y", "size"), min_predicted=("p", "min"), max_predicted=("p", "max"),
        mean_predicted=("p", "mean"), observed_rate=("y", "mean"))
    table["abs_gap"] = (table["mean_predicted"] - table["observed_rate"]).abs()
    return table


def calibration_metrics(y, p, n_bins=10):
    """Record-weighted calibration gap in tie-preserving quantile bins.

    The ece_equal_count field uses approximately equal-count bins, not equal-width bins;
    exact equal counts are not guaranteed when scores tie.
    """
    table = reliability_table(y, p, n_bins)
    return {
        "brier": brier_score_loss(y, p),
        "log_loss": log_loss(y, np.clip(p, 1e-6, 1 - 1e-6)),
        "ece_equal_count": float(np.average(table["abs_gap"], weights=table["records"])),
        "mean_predicted": float(np.mean(p)),
        "observed_prevalence": float(np.mean(y)),
    }


def patient_bootstrap(stat_fn, frame, patient_col, n_bootstrap=300, seed=42):
    """Point estimate and percentile 95% interval of stat_fn(frame) when patients are resampled with replacement
    and all their encounters travel together. Replicates with an undefined statistic are dropped; the count of
    valid replicates is returned, matching the convention of Step 5."""
    point = stat_fn(frame)
    members = list(frame.groupby(patient_col).indices.values())
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_bootstrap):
        rows = np.concatenate([members[k] for k in rng.integers(0, len(members), size=len(members))])
        value = stat_fn(frame.iloc[rows])
        if np.isfinite(value):
            draws.append(value)
    low, high = np.quantile(draws, [0.025, 0.975]) if draws else (np.nan, np.nan)
    return point, low, high, len(draws)


def calibration_intervals(frame, patient_col, n_bootstrap=300, seed=42):
    """Patient-cluster 95% intervals for Brier and quantile-bin ECE of a frame with columns y and p."""
    statistics = {"brier": lambda f: brier_score_loss(f["y"], f["p"]),
                  "ece_equal_count": lambda f: calibration_metrics(f["y"], f["p"])["ece_equal_count"]}
    out = {}
    for name, statistic in statistics.items():
        _, out[f"{name}_low"], out[f"{name}_high"], out["valid_bootstraps"] = patient_bootstrap(
            statistic, frame, patient_col, n_bootstrap, seed)
    return out


def threshold_table(y, p, minutes_per_contact, thresholds=None):
    """One row per candidate threshold with rule `alert if score >= threshold`.
    Default candidates: 0 (alert everyone), every distinct score, and inf (alert nobody)."""
    y, p = np.asarray(y).astype(int), np.asarray(p)
    if thresholds is None:
        thresholds = np.r_[0.0, np.unique(p), np.inf]
    thresholds = np.asarray(thresholds, dtype=float)
    n, positives = len(y), int(y.sum())
    alerts = np.array([(p >= t).sum() for t in thresholds])
    tp = np.array([y[p >= t].sum() for t in thresholds])
    fp, fn = alerts - tp, positives - tp
    table = pd.DataFrame({"threshold": thresholds, "tp": tp, "fp": fp, "fn": fn, "tn": n - alerts - fn})
    with np.errstate(invalid="ignore", divide="ignore"):
        table["precision"] = tp / alerts
        table["recall"] = tp / positives
        table["specificity"] = table["tn"] / (n - positives)
    table["alerts_per_1000"] = 1000 * alerts / n
    table["false_alerts_per_1000"] = 1000 * fp / n
    table["missed_per_1000"] = 1000 * fn / n
    table["staff_hours_per_1000"] = table["alerts_per_1000"] * minutes_per_contact / 60
    return table


def pick_policy(table, objective, alerts_per_1000_max=np.inf, recall_floor=0.0):
    """Row maximising `objective` ("recall" or "precision") among thresholds within the alert budget and at or
    above the recall floor; ties go to the higher threshold (fewer alerts). None when nothing is feasible."""
    feasible = table[(table["alerts_per_1000"] <= alerts_per_1000_max) & (table["recall"] >= recall_floor)]
    if feasible.empty:
        return None
    return feasible.sort_values([objective, "threshold"], ascending=False).iloc[0]


def subgroup_policy_table(frame, group_columns, score_col, target_col, patient_col, threshold, min_patients=20):
    """Per subgroup at a fixed threshold: support, selection rate, recall, FNR, FPR, precision and calibration.
    A caution flag marks fewer than `min_patients` distinct patients contributing either outcome."""
    rows = []
    for attribute in group_columns:
        for group, part in frame.groupby(attribute, dropna=False, sort=True):
            y, alert = part[target_col].to_numpy(), (part[score_col] >= threshold).to_numpy()
            positive_patients = part.loc[y == 1, patient_col].nunique()
            negative_patients = part.loc[y == 0, patient_col].nunique()
            with np.errstate(invalid="ignore", divide="ignore"):
                rows.append({
                    "attribute": attribute, "group": group, "encounters": len(part),
                    "patients": part[patient_col].nunique(), "positives": int(y.sum()),
                    "positive_patients": positive_patients, "negative_patients": negative_patients,
                    "selection_rate": alert.mean(),
                    "recall": (alert & (y == 1)).sum() / (y == 1).sum(),
                    "fnr": (~alert & (y == 1)).sum() / (y == 1).sum(),
                    "fpr": (alert & (y == 0)).sum() / (y == 0).sum(),
                    "precision": (alert & (y == 1)).sum() / alert.sum(),
                    "mean_predicted": part[score_col].mean(), "observed": y.mean(),
                    "caution": "Small / single-class patient support"
                    if min(positive_patients, negative_patients) < min_patients else "",
                })
    return pd.DataFrame(rows)


class ThresholdedEstimator(BaseEstimator, ClassifierMixin):
    """Wrap a fitted probabilistic classifier so `.predict` applies the locked threshold instead of 0.5,
    while `.predict_proba` stays unchanged for the Responsible AI dashboard."""

    def __init__(self, base, threshold):
        self.base, self.threshold = base, threshold

    def fit(self, X, y=None):
        return self

    @property
    def classes_(self):
        return self.base.classes_

    def predict_proba(self, X):
        return self.base.predict_proba(X)

    def predict(self, X):
        return (positive_proba(self.base, X) >= self.threshold).astype(int)


def error_tree_leaves(tree):
    """Leaves of a Responsible AI error-analysis tree as a table: the full rule from the root, cohort size,
    error count and error rate. The tree is the list of node dicts returned by rai.error_analysis.get()[0].tree."""
    nodes = {node["id"]: node for node in tree}
    parents = {node["parentId"] for node in tree if node["parentId"] is not None}
    rows = []
    for node in tree:
        if node["id"] in parents:
            continue
        conditions, current = [], node
        while current["parentId"] is not None:
            conditions.append(current["condition"])
            current = nodes[current["parentId"]]
        rows.append({"rule": " and ".join(reversed(conditions)), "encounters": int(node["size"]),
                     "errors": int(node["error"]), "error_rate": node["error"] / node["size"]})
    return pd.DataFrame(rows).sort_values("error_rate", ascending=False).reset_index(drop=True)


class PolicyScaleEstimator(ThresholdedEstimator):
    """Same wrapper, but `predict_proba` is rescaled monotonically so that 0.5 maps to the locked threshold.
    Used only to generate counterfactuals, because DiCE infers the class from `predict_proba` with a 0.5 rule
    and therefore ignores the wrapper's `predict`. Ranking is unchanged; the scale is not a probability."""

    def predict_proba(self, X):
        p, t = positive_proba(self.base, X), self.threshold
        p = np.where(p < t, 0.5 * p / t, 0.5 + 0.5 * (p - t) / (1 - t))
        return np.c_[1 - p, p]


def leaf_mask(frame, rule):
    """Boolean mask for a rule from error_tree_leaves: conditions joined by ' and ', each either
    `feature <= 6.50` style or `feature == level1 | level2` (`!=` for exclusion) as the dashboard prints them."""
    mask = pd.Series(True, index=frame.index)
    for condition in rule.split(" and "):
        feature, operator, value = condition.split(" ", 2)
        column = frame[feature]
        if operator in ("==", "!="):
            included = column.astype(str).isin(value.split(" | "))
            mask &= included if operator == "==" else ~included
        else:
            mask &= {"<=": column.le, "<": column.lt, ">": column.gt, ">=": column.ge}[operator](float(value))
    return mask
