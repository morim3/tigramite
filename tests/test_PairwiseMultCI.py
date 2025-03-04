"""
Tests for independence_tests.py.
"""
from __future__ import print_function
import numpy as np
import pytest
from scipy import stats

from tigramite.independence_tests.parcorr import ParCorr
from tigramite.independence_tests.robust_parcorr import RobustParCorr
from tigramite.independence_tests.pairwise_CI import PairwiseMultCI
from tigramite.independence_tests.cmiknn import CMIknn
from tigramite.independence_tests.regressionCI import RegressionCI
# PairwiseMultCI TESTING ##################################################
@pytest.fixture(params=[
    # Generate PairwiseMultCI test instances
    # test PairwiseMultCI for different combinations of:
    # significance (of the univariate tests),  alpha_pre, pre_step_sample_fraction, cond_ind_test, cond_ind_test_thres, cond_ind_test_thres_pre
    ('fixed_thres', 0.5, 0.2, ParCorr, 1, 0.5),
    ('fixed_thres', 0.5, 0.5, ParCorr, 1, 0.5),
    ('fixed_thres', 0.8, 0.2, ParCorr, 1, 0.5),
    ('fixed_thres', 0.8, 0.5, ParCorr, 1, 0.5),
    ('analytic', 0.5, 0.2, ParCorr, None, None),
    ('shuffle_test', 0.5, 0.2, ParCorr, None, None),
    ('analytic', 0.5, 0.5, ParCorr, None, None),
    ('shuffle_test', 0.5, 0.5, ParCorr, None, None),
    ('analytic', 0.8, 0.2, ParCorr, None, None),
    ('shuffle_test', 0.8, 0.2, ParCorr, None, None),
    ('analytic', 0.8, 0.5, ParCorr, None, None),
    ('shuffle_test', 0.8, 0.5, ParCorr, None, None),
    ('analytic', 0.5, 0.2, RobustParCorr, None, None),
    ('shuffle_test', 0.5, 0.2, RobustParCorr, None, None),
    ('analytic', 0.5, 0.5, RobustParCorr, None, None),
    ('shuffle_test', 0.5, 0.5, RobustParCorr, None, None),
    ('analytic', 0.8, 0.2, RobustParCorr, None, None),
    ('shuffle_test', 0.8, 0.2, RobustParCorr, None, None),
    ('analytic', 0.8, 0.5, RobustParCorr, None, None),
    ('shuffle_test', 0.8, 0.5, RobustParCorr, None, None),
    ('shuffle_test', 0.5, 0.2, CMIknn, None, None),
    ('shuffle_test', 0.5, 0.5, CMIknn, None, None),
    ('shuffle_test', 0.8, 0.2, CMIknn, None, None),
    ('shuffle_test', 0.8, 0.5, CMIknn, None, None),
])

def pairwise_mult_ci(request):
    # Unpack the parameters
    sig, alpha_pre, pre_step_sample_fraction, cond_ind_test, cond_ind_test_thres, cond_ind_test_thres_pre = request.param
    # Generate the par_corr_wls independence test
    if sig != "fixed_thres":
        return PairwiseMultCI(cond_ind_test = cond_ind_test(significance = sig),
                          alpha_pre = alpha_pre,
                          pre_step_sample_fraction = pre_step_sample_fraction)
    else:
        return PairwiseMultCI(cond_ind_test = cond_ind_test(significance = sig),
                          alpha_pre = None,
                          pre_step_sample_fraction=pre_step_sample_fraction,
                          significance= sig,
                          fixed_thres_pre = 2
                          )

@pytest.fixture(params=[
    # Generate PairwiseMultCI test instances
    # test PairwiseMultCI for different combinations of:
    # seed,  true_dep, T (=sample size)
    (123, 0, 100),
    (123, 0, 1000),
    (123, 0.2, 100),
    (123, 0.2, 1000),
    (123, 0.5, 100),
    (123, 0, 1000),
    (46, 0, 100),
    (46, 0, 1000),
    (46, 0.2, 100),
    (46, 0.2, 1000),
    (46, 0.5, 100),
    (46, 0, 1000),
])

def data_sample_c_cc_c(request):
    # Set the random seed
    seed, true_dep, T = request.param
    np.random.seed(seed)
    x = np.random.normal(0, 1, T).reshape(T, 1)
    y1 = np.random.normal(0, 1, T).reshape(T, 1)
    y2 = true_dep * x + y1 + 0.3 * np.random.normal(0, 1, T).reshape(T, 1)
    y = np.hstack((y1,y2))
    z = np.random.normal(0, 1, T).reshape(T, 1)
    # Return data xyz
    return x, y, z

def test_pairwise_mult_ci(pairwise_mult_ci, data_sample_c_cc_c):
    # Get the data sample values
    x, y, z = data_sample_c_cc_c
    # Get the analytic significance
    test_result = pairwise_mult_ci.run_test_raw(x = x, y = y, z = z, alpha_or_thres=1)
    val = test_result[0]
    pval = test_result[1]
    np.testing.assert_allclose(pval, 0.5, atol=0.5)
