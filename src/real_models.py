"""Matched observational benchmarks; geographic and temporal evaluation.

The synthetic notebooks and results are intentionally left unchanged.
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.calibration import calibration_curve
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             precision_score, recall_score, f1_score,
                             roc_auc_score, roc_curve, precision_recall_curve)
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .config import OBS_END, OBS_START, ROOT

DATA = ROOT / "data/processed/real"
RESULTS = ROOT / "results/real"
FIGURES = ROOT / "figures/real"
BASELINE = ["tmean_lag1", "ppt_lag1", "cultivated_fraction_2021", "sin_month", "cos_month"]
DISTURBANCE = ["fire_pixel_days_lag1_log", "frp_mw_sum_lag1_log", "ndvi_lag1", "lst_lag1"]
FULL = BASELINE + DISTURBANCE
SEED = 42


def models(jobs=4):
    def logit():
        return make_pipeline(SimpleImputer(strategy="median", add_indicator=True),
                             StandardScaler(), LogisticRegression(max_iter=3000, random_state=SEED))
    def forest():
        return make_pipeline(SimpleImputer(strategy="median", add_indicator=True),
                             RandomForestClassifier(n_estimators=400, min_samples_leaf=5,
                                                    class_weight="balanced_subsample",
                                                    random_state=SEED, n_jobs=jobs))
    return {"logistic_baseline": (logit(), BASELINE), "logistic_full": (logit(), FULL),
            "forest_baseline": (forest(), BASELINE), "forest_full": (forest(), FULL)}


def metric_values(y, probability):
    y, probability = np.asarray(y), np.asarray(probability)
    pred = probability >= 0.5
    both = len(np.unique(y)) == 2
    return dict(roc_auc=roc_auc_score(y, probability) if both else np.nan,
                average_precision=average_precision_score(y, probability) if both else np.nan,
                brier=brier_score_loss(y, probability),
                precision=precision_score(y, pred, zero_division=0),
                recall=recall_score(y, pred, zero_division=0),
                f1=f1_score(y, pred, zero_division=0),
                prevalence=float(y.mean()), n=len(y), n_positive=int(y.sum()))


def cluster_samples(frame, n_boot=1000, seed=SEED):
    rng = np.random.default_rng(seed)
    groups = frame.county_fips.unique()
    indices = [np.flatnonzero(frame.county_fips.to_numpy() == c) for c in groups]
    for _ in range(n_boot):
        yield np.concatenate([indices[i] for i in rng.integers(0, len(groups), len(groups))])


def uncertainty(frame, outcome, validation, n_boot):
    """Resample whole counties; CIs conditional on fitted prediction models."""
    names = list(models())
    values = {n: {m: [] for m in ["roc_auc", "average_precision", "brier"]} for n in names}
    deltas = {family: {m: [] for m in ["roc_auc", "average_precision", "brier"]}
              for family in ["logistic", "forest"]}
    for indices in cluster_samples(frame, n_boot):
        sample = frame.iloc[indices]
        y = sample[outcome].to_numpy()
        if len(np.unique(y)) < 2:
            continue
        for name in names:
            met = metric_values(y, sample[name])
            for metric in values[name]:
                values[name][metric].append(met[metric])
        for family in deltas:
            for metric in deltas[family]:
                deltas[family][metric].append(values[family + "_full"][metric][-1] -
                                               values[family + "_baseline"][metric][-1])
    rows, differences = [], []
    for name in names:
        row = dict(outcome=outcome, validation=validation, model=name,
                   **metric_values(frame[outcome], frame[name]))
        for metric, vals in values[name].items():
            row[metric + "_lo"], row[metric + "_hi"] = np.percentile(vals, [2.5, 97.5])
        rows.append(row)
    for family in deltas:
        a = metric_values(frame[outcome], frame[family + "_full"])
        b = metric_values(frame[outcome], frame[family + "_baseline"])
        for metric, vals in deltas[family].items():
            lo, hi = np.percentile(vals, [2.5, 97.5])
            differences.append(dict(outcome=outcome, validation=validation, model_family=family,
                                    metric=metric, full_minus_baseline=a[metric] - b[metric],
                                    ci_low=lo, ci_high=hi, bootstrap_samples=len(vals)))
    return rows, differences


def evaluate(panel, outcome, jobs=4, importance=True):
    specifications = models(jobs)
    y = panel[outcome].to_numpy()
    output = panel[["county_fips", "county", "month", outcome]].copy()
    output["fold"] = -1
    for name in specifications:
        output[name] = np.nan
    imports, fit_audit, split_audit = [], [], []
    for fold, (train, test) in enumerate(GroupKFold(n_splits=5).split(panel, y, panel.county_fips)):
        train_counties, test_counties = set(panel.iloc[train].county_fips), set(panel.iloc[test].county_fips)
        assert train_counties.isdisjoint(test_counties)
        output.loc[test, "fold"] = fold
        split_audit.append(dict(outcome=outcome, validation="county_holdout", fold=fold,
                                train_counties=sorted(train_counties), test_counties=sorted(test_counties),
                                train_n=len(train), test_n=len(test)))
        for name, (estimator, features) in specifications.items():
            model = clone(estimator)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                model.fit(panel.iloc[train][features], y[train])
            probability = model.predict_proba(panel.iloc[test][features])[:, 1]
            output.loc[test, name] = probability
            fit_audit.append(dict(outcome=outcome, validation="county_holdout", fold=fold, model=name,
                                  warnings="; ".join(str(w.message) for w in caught)))
            if importance and outcome == "y" and name == "forest_full" and len(np.unique(y[test])) == 2:
                perm = permutation_importance(model, panel.iloc[test][features], y[test],
                                              scoring="average_precision", n_repeats=10,
                                              random_state=SEED, n_jobs=1)
                for feature, mean, sd in zip(features, perm.importances_mean, perm.importances_std):
                    imports.append(dict(fold=fold, feature=feature, ap_decrease=mean,
                                        permutation_sd=sd, test_n=len(test)))
            print(outcome, "county fold", fold, name, "complete", flush=True)
    assert output[list(specifications)].notna().all().all()
    # A separate chronological evaluation; no models refit on its test outcomes.
    train, test = np.flatnonzero(panel.month < "2025-01"), np.flatnonzero(panel.month >= "2025-01")
    temporal = panel.iloc[test][["county_fips", "county", "month", outcome]].copy().reset_index(drop=True)
    split_audit.append(dict(outcome=outcome, validation="temporal_2025", train_start="2022-01", train_end="2024-12",
                            test_start="2025-01", test_end=OBS_END, train_n=len(train), test_n=len(test)))
    for name, (estimator, features) in specifications.items():
        model = clone(estimator)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model.fit(panel.iloc[train][features], y[train])
        temporal[name] = model.predict_proba(panel.iloc[test][features])[:, 1]
        fit_audit.append(dict(outcome=outcome, validation="temporal_2025", fold=-1, model=name,
                              warnings="; ".join(str(w.message) for w in caught)))
        print(outcome, "2025 holdout", name, "complete", flush=True)
    return output, temporal, imports, fit_audit, split_audit


def plot_discrimination(frame, target, filename, title):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for name in models():
        y, p = frame[target], frame[name]
        fpr, tpr, _ = roc_curve(y, p)
        precision, recall, _ = precision_recall_curve(y, p)
        axes[0].plot(fpr, tpr, label=f"{name}: {roc_auc_score(y, p):.3f}")
        axes[1].plot(recall, precision, label=f"{name}: {average_precision_score(y, p):.3f}")
    axes[0].plot([0, 1], [0, 1], "k--", lw=.8)
    axes[1].axhline(frame[target].mean(), color="gray", ls="--", label="Outcome prevalence")
    axes[0].set(xlabel="False positive rate", ylabel="True positive rate", title="ROC-AUC")
    axes[1].set(xlabel="Recall", ylabel="Precision", title="Average precision")
    for ax in axes:
        ax.legend(fontsize=7)
        ax.grid(alpha=.2)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(filename, dpi=180)
    plt.close(fig)


def make_figures(panel, oof, temporal, importance):
    plot_discrimination(oof, "y", FIGURES / "county_holdout_performance.png", "Observed APHIS H5N1 reports — held-out counties")
    plot_discrimination(temporal, "y", FIGURES / "temporal_holdout_performance.png", "Observed APHIS H5N1 reports — 2025 temporal holdout")
    fig, ax = plt.subplots(figsize=(6, 5))
    for name in models():
        frac, mean = calibration_curve(temporal.y, temporal[name], n_bins=6, strategy="quantile")
        ax.plot(mean, frac, marker="o", label=name)
    ax.plot([0, 1], [0, 1], "k--", lw=.8)
    ax.set(xlabel="Mean predicted probability", ylabel="Observed positive fraction",
           title="Calibration on the 2025 holdout")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / "temporal_calibration.png", dpi=180)
    plt.close(fig)
    if len(importance):
        summary = importance.groupby("feature").ap_decrease.agg(["mean", "std"]).sort_values("mean")
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.barh(summary.index, summary["mean"], xerr=summary["std"].fillna(0))
        ax.set(xlabel="Held-out average-precision decrease (mean ± fold SD)",
               title="Random forest: held-out permutation importance")
        fig.tight_layout()
        fig.savefig(FIGURES / "heldout_permutation_importance.png", dpi=180)
        plt.close(fig)
    monthly = panel.groupby("month").agg(h5n1=("h5n1", "sum"), h5_all=("h5_any", "sum"))
    fig, ax = plt.subplots(figsize=(11, 4))
    x = pd.to_datetime(monthly.index + "-01")
    ax.plot(x, monthly.h5n1, label="Explicit H5N1 records")
    ax.plot(x, monthly.h5_all, label="All HPAI H5 records", alpha=.7)
    ax.set(ylabel="Reported wild-bird records", title="California APHIS surveillance snapshot — not sampling-adjusted prevalence")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "reported_detections_by_month.png", dpi=180)
    plt.close(fig)
    # Actual county geometry; cross-validated predictions rather than in-sample fits.
    from .real_data import counties
    mean = oof.groupby("county_fips").forest_full.mean().rename("mean_oof_probability")
    geo = counties().merge(mean, left_on="GEOID", right_index=True, validate="1:1").to_crs(3310)
    fig, ax = plt.subplots(figsize=(7, 8))
    geo.plot(column="mean_oof_probability", ax=ax, legend=True, cmap="YlOrRd", edgecolor="white", linewidth=.3)
    ax.set_title(f"Mean county-held-out H5N1 report probability\nRetrospective model output, {OBS_START}–{OBS_END}")
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(FIGURES / "county_oof_probability.png", dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--no-importance", action="store_true")
    args = parser.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    panel_path = DATA / "panel.csv"
    if not panel_path.exists():
        raise SystemExit("No completed observational panel. Run `python -m src.real_data audit` "
                         "and resolve missing coverage before building the panel and fitting models.")
    panel = pd.read_csv(panel_path, dtype={"county_fips": str})
    expected_rows = 58 * len(pd.period_range(OBS_START, OBS_END, freq="M"))
    assert len(panel) == expected_rows and panel.county_fips.nunique() == 58
    assert not panel.duplicated(["county_fips", "month"]).any()
    assert set(panel.data_type) == {"observational"}
    if panel[FULL].isna().all().any():
        raise ValueError("A required predictor is entirely missing; extraction is incomplete")
    all_metrics, all_diffs, fits, splits = [], [], [], []
    primary = None
    for outcome in ["y", "y_h5_inclusive"]:
        oof, temporal, importance, audit, split = evaluate(panel, outcome, args.jobs, not args.no_importance)
        oof.to_csv(RESULTS / (outcome + "_county_oof_predictions.csv"), index=False)
        temporal.to_csv(RESULTS / (outcome + "_temporal_2025_predictions.csv"), index=False)
        for name, frame in [("county_holdout", oof), ("temporal_2025", temporal)]:
            met, diffs = uncertainty(frame, outcome, name, args.bootstrap)
            all_metrics.extend(met)
            all_diffs.extend(diffs)
            print(outcome, name, "bootstrap complete", flush=True)
        fits.extend(audit)
        splits.extend(split)
        if outcome == "y":
            primary = oof, temporal, pd.DataFrame(importance)
    metrics, differences = pd.DataFrame(all_metrics), pd.DataFrame(all_diffs)
    metrics.to_csv(RESULTS / "model_metrics.csv", index=False)
    differences.to_csv(RESULTS / "paired_feature_set_differences.csv", index=False)
    pd.DataFrame(fits).to_csv(RESULTS / "fit_audit.csv", index=False)
    (RESULTS / "validation_splits.json").write_text(json.dumps(splits, indent=2) + "\n")
    primary[2].to_csv(RESULTS / "heldout_permutation_importance.csv", index=False)
    make_figures(panel, *primary)
    dependencies = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
    (RESULTS / "environment.txt").write_text("Python " + platform.python_version() + "\n" + dependencies)
    lines = ["# Observational benchmark results", "", "Data: actual APHIS surveillance reports and public environmental products; synthetic examples are separate.",
             "", f"Panel: {len(panel):,} county-months, 58 counties, {OBS_START}–{OBS_END}; {int(panel.y.sum())} positive H5N1 county-months.",
             "", "## Primary outcome: explicit H5N1 reports", "",
             "| Validation | Model | ROC-AUC | Average precision | Brier | Outcome prevalence |",
             "| --- | --- | --- | --- | --- | --- |"]
    for r in metrics[metrics.outcome == "y"].itertuples():
        lines.append(f"| {r.validation} | {r.model} | {r.roc_auc:.3f} | {r.average_precision:.3f} | {r.brier:.3f} | {r.prevalence:.3f} |")
    lines += ["", "## Added environmental predictors", "",
              "Full-minus-baseline average precision, with paired county-bootstrap 95% intervals:", ""]
    for r in differences[(differences.outcome == "y") & (differences.metric == "average_precision")].itertuples():
        lines.append(f"- {r.validation}, {r.model_family}: {r.full_minus_baseline:+.3f} (95% interval {r.ci_low:+.3f} to {r.ci_high:+.3f}).")
    lines += ["", "Intervals are conditional on fitted predictions and resample whole counties; model-selection uncertainty is not included.",
              "A positive point estimate alone does not establish added predictive value; intervals and temporal performance must also be considered.",
              "", "The inclusive-H5 sensitivity results, complete interval estimates, split audit, out-of-fold predictions, and missingness reports accompany this summary.",
              "", "## Limits", "",
              "This is an exploratory retrospective ecological prediction study, not a validated early-warning system or a causal analysis. Absence of a reported detection is not a tested-negative outcome. Surveillance effort and subtype ascertainment are incomplete. Climate and satellite predictors use the prior month; final revised source products do not reproduce real-time data availability. County holdouts do not separate neighboring counties with a buffer. Small satellite archive gaps and QA masking are documented in the data quality audit; imputation occurs within each training fold.", ""]
    (RESULTS / "analysis_summary.md").write_text("\n".join(lines))
    print(metrics.to_string(index=False), flush=True)
    print("OBSERVATIONAL ANALYSIS COMPLETE", flush=True)


if __name__ == "__main__":
    main()
