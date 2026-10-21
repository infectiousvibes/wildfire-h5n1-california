"""Data-integrity and evaluation checks for the observational workflow."""
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from src.config import OBS_END, OBS_START, ROOT
from src.real_data import composite_end, sums
from src.real_models import BASELINE, FULL, cluster_samples, models


class UnitChecks(unittest.TestCase):
    def test_annual_composites_do_not_extend_into_future_year(self):
        self.assertEqual(composite_end(pd.Timestamp("2025-12-27"), 8), pd.Timestamp("2025-12-31"))
        self.assertEqual(composite_end(pd.Timestamp("2024-02-26"), 8), pd.Timestamp("2024-03-04"))

    def test_zonal_summary_excludes_outside_and_bad_quality(self):
        labels = np.array([[0, 1, 1], [2, 2, 0]], dtype="uint8")
        values = np.array([[999, 2, 4], [5, 90, 999]])
        good = np.array([[True, True, True], [True, False, True]])
        np.testing.assert_array_equal(sums(labels, values, good)[:2], [6, 5])
        np.testing.assert_array_equal(sums(labels, valid=good)[:2], [2, 1])

    def test_bootstrap_keeps_county_months_together(self):
        frame = pd.DataFrame({"county_fips": np.repeat(["a", "b", "c"], 4)})
        for sample in cluster_samples(frame, n_boot=30):
            counts = frame.iloc[sample].county_fips.value_counts()
            self.assertTrue((counts % 4 == 0).all())

    def test_predictor_ablation_and_training_only_imputation(self):
        self.assertEqual(len(FULL), 9)
        self.assertEqual(len(BASELINE), 5)
        estimator, features = models(1)["logistic_baseline"]
        train = pd.DataFrame(np.arange(40).reshape(8, 5), columns=features).astype(float)
        train.loc[0, features[0]] = np.nan
        estimator.fit(train, [0, 1] * 4)
        stats = estimator.steps[0][1].statistics_.copy()
        test = train.copy() * 10000
        test.loc[1, features[0]] = np.nan
        estimator.predict_proba(test)
        np.testing.assert_array_equal(stats, estimator.steps[0][1].statistics_)


class CompletedPanelChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = ROOT / "data/processed/real"
        if not (cls.directory / "panel.csv").exists():
            raise unittest.SkipTest("Panel not built yet")
        cls.panel = pd.read_csv(cls.directory / "panel.csv", dtype={"county_fips": str})

    def test_panel_keys_and_labels(self):
        p = self.panel
        self.assertEqual(len(p), 58 * len(pd.period_range(OBS_START, OBS_END, freq="M")))
        self.assertEqual(p.county_fips.nunique(), 58)
        self.assertEqual(p.month.nunique(), len(pd.period_range(OBS_START, OBS_END, freq="M")))
        self.assertFalse(p.duplicated(["county_fips", "month"]).any())
        self.assertTrue((p.y <= p.y_h5_inclusive).all())
        self.assertTrue((p.data_type == "observational").all())

    def test_lags_match_previous_month_source_summaries(self):
        for name, value in [("prism", "tmean"), ("ndvi", "ndvi"), ("lst", "lst"), ("fire", "fire_pixel_days")]:
            s = pd.read_csv(self.directory / (name + "_county_month.csv"), dtype={"county_fips": str})
            s["month"] = (pd.PeriodIndex(s.month, freq="M") + 1).astype(str)
            joined = self.panel.merge(
                s[["county_fips", "month", value]],
                on=["county_fips", "month"],
                how="left",
                suffixes=("", "_expected"),
                validate="1:1",
            )
            self.assertEqual(len(joined), len(self.panel))
            np.testing.assert_allclose(joined[value + "_lag1"], joined[value + "_expected"], equal_nan=True)

    def test_no_empty_model_feature_or_missing_landcover(self):
        self.assertFalse(self.panel[FULL].isna().all().any())
        self.assertTrue(self.panel.cultivated_fraction_2021.between(0, 1).all())

    def test_model_split_audit(self):
        f = ROOT / "results/real/validation_splits.json"
        if not f.exists():
            self.skipTest("Models not evaluated yet")
        for s in json.loads(f.read_text()):
            if s["validation"] == "county_holdout":
                self.assertTrue(set(s["train_counties"]).isdisjoint(s["test_counties"]))
            else:
                self.assertLess(s["train_end"], s["test_start"])


if __name__ == "__main__":
    unittest.main()
