# Publication-style figures. Map functions work with lat/lon out of the box;
# for real choropleths, load TIGER counties with geopandas and join on FIPS
# (template: see choropleth_counties below).
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def map_panel(df, value, title, fname, cmap="YlOrRd", label="", size_by=None):
    fig, ax = plt.subplots(figsize=(7, 8))
    sc = ax.scatter(df["lon"], df["lat"], c=df[value], s=60,
                    cmap=cmap, edgecolor="0.3", linewidth=0.4, zorder=3)
    plt.colorbar(sc, ax=ax, shrink=0.6, label=label or value)
    ax.set_title(title + " (SYNTHETIC demo)" if df.get("_synthetic") is not False else title)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(fname, dpi=200)
    plt.close(fig)


def choropleth_counties(gdf, value_col, title, fname):
    # Real-data choropleth template: gdf = TIGER counties (STATEFP=='06') joined to panel aggregates.
    fig, ax = plt.subplots(figsize=(7, 8))
    gdf.plot(column=value_col, ax=ax, cmap="YlOrRd", legend=True,
             legend_kwds={"shrink": 0.6}, edgecolor="0.7", linewidth=0.3)
    ax.set_title(title)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(fname, dpi=200)
    plt.close(fig)


def temporal_trend(df, fname):
    monthly = df.groupby("month_idx").agg(detections=("y", "sum"),
                                          fire=("fire_count", "sum")).reset_index()
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(monthly["month_idx"], monthly["detections"], marker="o", ms=3, label="H5N1 detections")
    ax.set_xlabel("Months since Jan 2022")
    ax.set_ylabel("Statewide detections", color="C0")
    ax2 = ax.twinx()
    ax2.fill_between(monthly["month_idx"], monthly["fire"], color="C1", alpha=0.3, label="Active-fire detections")
    ax2.set_ylabel("VIIRS fire detections", color="C1")
    ax.set_title("Monthly H5N1 wild-bird detections vs. wildfire activity (SYNTHETIC demo)")
    fig.tight_layout()
    fig.savefig(fname, dpi=200)
    plt.close(fig)


def roc_pr_panel(curves, metrics, fname):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    for name, c in curves.items():
        axes[0].plot(c["fpr"], c["tpr"], label=name)
        axes[1].plot(c["recall"], c["precision"], label=name)
    axes[0].plot([0, 1], [0, 1], "k--", lw=0.8)
    axes[0].set_xlabel("False positive rate")
    axes[0].set_ylabel("True positive rate")
    axes[0].set_title("ROC (out-of-fold, county holdout)")
    axes[0].legend(fontsize=8)
    axes[1].set_xlabel("Recall")
    axes[1].set_ylabel("Precision")
    axes[1].set_title("Precision–recall")
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=0.3)
    auc_txt = "; ".join(f"{r.model}: AUC={r.roc_auc:.3f}, PR={r.pr_auc:.3f}"
                        for r in metrics.itertuples())
    fig.suptitle(auc_txt, fontsize=9, y=1.02)
    fig.tight_layout()
    fig.savefig(fname, dpi=200, bbox_inches="tight")
    plt.close(fig)


def importance_plot(perm, feature_names, fname):
    order = np.argsort(perm.importances_mean)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.barh(np.array(feature_names)[order], perm.importances_mean[order],
            xerr=perm.importances_std[order], color="steelblue", alpha=0.85)
    ax.set_xlabel("Mean permutation importance (decrease in ROC-AUC)")
    ax.set_title("Which environmental features drive predicted risk? (SYNTHETIC demo)")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(fname, dpi=200)
    plt.close(fig)


def risk_map(df_pred, fname):
    fig, ax = plt.subplots(figsize=(7, 8))
    sc = ax.scatter(df_pred["lon"], df_pred["lat"], c=df_pred["risk"],
                    s=60, cmap="RdYlGn_r", edgecolor="0.3", linewidth=0.4, zorder=3)
    plt.colorbar(sc, ax=ax, shrink=0.6, label="Mean predicted H5N1 detection probability")
    ax.set_title("Predicted county-level H5N1 detection risk (SYNTHETIC demo)")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(fname, dpi=200)
    plt.close(fig)
