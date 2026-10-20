# Metrics helpers: bootstrap CIs for AUC/PR-AUC.
import numpy as np


def bootstrap_auc_ci(y, prob, n_boot=1000, seed=42, metric="roc"):
    from sklearn.metrics import average_precision_score, roc_auc_score
    rng = np.random.default_rng(seed)
    y = np.asarray(y)
    prob = np.asarray(prob)
    fn = roc_auc_score if metric == "roc" else average_precision_score
    stats = []
    n = len(y)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        if len(np.unique(y[idx])) < 2:
            continue
        stats.append(fn(y[idx], prob[idx]))
    lo, hi = np.percentile(stats, [2.5, 97.5])
    return float(lo), float(hi)
