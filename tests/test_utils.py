import unittest

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve

from utils import calibration_metrics, reliability_table


class ReliabilityTableTests(unittest.TestCase):
    def test_constant_scores_are_one_calibration_group(self):
        outcomes = np.r_[np.zeros(50), np.ones(50)]
        scores = np.full(100, 0.5)

        table = reliability_table(outcomes, scores)

        self.assertEqual(table["records"].tolist(), [100])
        self.assertEqual(calibration_metrics(outcomes, scores)["ece_equal_count"], 0.0)

    def test_tied_scores_are_independent_of_row_order(self):
        outcomes = np.array([0, 0, 0, 0, 0, 0, 1, 1, 1, 1])
        scores = np.array([0.1] * 8 + [0.9] * 2)
        permutation = np.array([6, 0, 8, 1, 7, 2, 9, 3, 4, 5])

        table = reliability_table(outcomes, scores)
        reordered = reliability_table(outcomes[permutation], scores[permutation])

        pd.testing.assert_frame_equal(table, reordered)
        self.assertEqual(table["records"].tolist(), [8, 2])
        self.assertAlmostEqual(calibration_metrics(outcomes, scores)["ece_equal_count"], 0.14)

    def test_quantile_boundaries_match_reliability_plot(self):
        outcomes = np.array([0, 0, 1, 0, 1, 1])
        scores = np.array([0.05, 0.1, 0.2, 0.4, 0.7, 0.9])
        observed, predicted = calibration_curve(outcomes, scores, n_bins=5, strategy="quantile")

        table = reliability_table(outcomes, scores, n_bins=5)

        np.testing.assert_allclose(table["observed_rate"], observed)
        np.testing.assert_allclose(table["mean_predicted"], predicted)


if __name__ == "__main__":
    unittest.main()
