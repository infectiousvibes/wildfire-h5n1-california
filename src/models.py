# Models and spatially explicit validation (GroupKFold by county).
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, f1_score, precision_score,
                             recall_score, roc_auc_score)
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def get_models(random_state=42):
    # Baseline: epidemiologic logistic regression (interpretable reference)
    baseline = Pipeline([
        ("scaler", StandardScaler()),
        ("logit", LogisticRegression(max_iter=2000, random_state=random_state)),
    ])
    # ML model: random forest with non-linear interactions and class balancing
    rf = RandomForestClassifier(
        n_estimators=400, min_samples_leaf=5,
        class_weight="balanced_subsample",
        n_jobs=-1, random_state=random_state,
    )
    return {"Logistic (baseline)": baseline, "Random Forest (full)": rf}


def spatial_cv(df, features, target="y", group="county", n_splits=5, random_state=42):
    # GroupKFold by county: every test fold is a set of entirely unseen counties.
    X, y, groups, d = _xy(df, features, target, group)
    gkf = GroupKFold(n_splits=n_splits)
    models = get_models(random_state)
    metrics_rows, curves = [], {}
    for name, model in models.items():
        oof = cross_val_predict(model, X, y, groups=groups, cv=gkf, method="predict_proba")[:, 1]
        pred = (oof >= 0.5).astype(int)
        metrics_rows.append(dict(
            model=name,
            roc_auc=roc_auc_score(y, oof),
            pr_auc=average_precision_score(y, oof),
            precision=precision_score(y, pred, zero_division=0),
            recall=recall_score(y, pred, zero_division=0),
            f1=f1_score(y, pred, zero_division=0),
            n=len(y), n_positive=int(y.sum()),
        ))
        curves[name] = _curves(y, oof)
    return pd.DataFrame(metrics_rows), curves, d


def fit_full(df, features, target="y", random_state=42):
    # Fit the full-feature Random Forest on all data; used for risk map + importance.
    from .features import build_xy
    X, y, groups, d = build_xy(df, features, target)
    rf = get_models(random_state)["Random Forest (full)"]
    rf.fit(X, y)
    return rf, d


def _xy(df, features, target, group):
    from .features import build_xy
    X, y, groups, d = build_xy(df, features, target, group)
    return X, y, groups, d


def _curves(y, prob):
    from sklearn.metrics import precision_recall_curve, roc_curve
    fpr, tpr, _ = roc_curve(y, prob)
    prec, rec, _ = precision_recall_curve(y, prob)
    return {"fpr": fpr, "tpr": tpr, "precision": prec, "recall": rec}
