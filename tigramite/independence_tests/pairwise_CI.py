"""Tigramite causal discovery for time series."""

# Author: Jakob Runge <jakob@jakob-runge.com>
#
# License: GNU General Public License v3.0

from __future__ import print_function
from scipy import stats
import numpy as np
import sys
import warnings

from tigramite.independence_tests.independence_tests_base import CondIndTest
from tigramite.independence_tests.parcorr import ParCorr

class PairwiseMultCI(CondIndTest):
    r""" Multivariate CI-test that aggregates univariate tests

    Basically, the algorithm consists of two main steps:

    - Step 1: On the first part of the sample, conditional independencies of the form :math:`X_i \perp Y_j|Z`
      are learned

    - Step 2: On the second part of the sample, conditional independencies
      :math:`X_i \perp Y_j|(Z, S_{ij})` are tested, where the set :math:`S_{ij}` consists of components
      of :math:`X` that are independent of :math:`Y_j` given :math:`Z` (or components of :math:`Y` that
      are independent of :math:`X_i` given :math:`Z`). Using the Bonferroni method, the univariate tests
      are then aggregated.

    The main reasoning behind this two-step procedure is that the conditional independence tests in the second step
    have larger effect sizes. One can show, that in cases where the within-:math:`X` or within-:math:`Y` dependence
    is large, this method outperforms naive pairwise independence testing (i.e., without having the sets :math:`S_{ij}`)

    For the details, we refer to:

    - Tom Hochsprung, Jonas Wahl*, Andreas Gerhardus*, Urmi Ninad*, and Jakob Runge.
      Increasing Effect Sizes of Pairwise Conditional Independence Tests between Random Vectors. UAI2023, 2023.

    Parameters
    ----------
    alpha_pre: float
        Significance level for the first step of the algorithm.
        If cond_ind_test is instantiated with significance = "fixed_thres",
        then the value of alpha_pre is not used, and can, for example, be set to None

    pre_step_sample_fraction: float
        Relative size for the first part of the sample
        (abbreviation for "size block one")

    cond_ind_test: conditional independence test object
        This can be ParCorr or other classes from
        ``tigramite.independence_tests`` or an external test passed as a
        callable. This test can be based on the class
        tigramite.independence_tests.CondIndTest.

    fixed_thres_pre: In case cond_ind_test or self is instantiated with significance
        = "fixed_thres" (at least one such setting suffices), the pre_step works with a threshold instead of significance
        level


    **kwargs :
        Arguments passed on to Parent class CondIndTest.
    """

    # documentation
    @property
    def measure(self):
        """
        Concrete property to return the measure of the independence test
        """
        return self._measure

    def __init__(self, cond_ind_test = ParCorr(), alpha_pre = 0.5, pre_step_sample_fraction = 0.2, fixed_thres_pre = None, **kwargs):
        self._measure = 'pairwise_CI'
        self.cond_ind_test = cond_ind_test
        self.alpha_pre = alpha_pre
        self.pre_step_sample_fraction = pre_step_sample_fraction
        self.fixed_thres_pre = fixed_thres_pre
        self.two_sided = False
        CondIndTest.__init__(self, **kwargs)


    def calculate_dep_measure_and_significance(self, array, xyz, data_type = None, ci_test_thres = None):
        """Return aggregated p-value of all univariate independence tests.

        First, learns conditional independencies, uses these conditional independencies to have new conditional
        independence tests with larger effect sizes.

        Parameters
        ----------
        array : array-like
            data array with X, Y, Z in rows and observations in columns

        xyz : array of ints
            XYZ identifier array of shape (dim,).

        data_type: array of 0's and 1's, same dimensions as array
            relevant, for example for the CI-test RegressionCI,
            to indicate whether variables are discrete (=1) or
            continuous (=0).


        Returns
        -------
        pval : float
            an aggregated p-value of all univariate tests.
        """

        fixed_thres_bool = False
        if self.significance == "fixed_thres":
            fixed_thres_bool = True
            self.cond_ind_test.significance = "fixed_thres"
        if self.cond_ind_test.significance == "fixed_thres":
            fixed_thres_bool = True
            self.significance = "fixed_thres"

        if (fixed_thres_bool) and (self.fixed_thres_pre == None):
            raise ValueError("If significance == 'fixed_thres', fixed_thres_pre for the"
                             " pre-step needs to be defined in initializing PairwiseMultCI.")

        x_indices = np.where(xyz == 0)[0]
        y_indices = np.where(xyz == 1)[0]
        z_indices = np.where(xyz == 2)[0]

        dim_x = x_indices.shape[0]
        dim_y = y_indices.shape[0]
        # what if unconditional test ...
        dim_z = z_indices.shape[0]
        T = array.shape[1]
        size_first_block = np.floor(self.pre_step_sample_fraction * T)
        size_first_block = size_first_block.astype(int)

        # split the sample
        array_s1 = array[:, 0:size_first_block]
        x_s1 = array_s1[x_indices]
        y_s1 = array_s1[y_indices]
        z_s1 = array_s1[z_indices]

        array_s2 = array[:, size_first_block : T]
        x_s2 = array_s2[x_indices]
        y_s2 = array_s2[y_indices]
        z_s2 = array_s2[z_indices]

        if data_type is not None:
            x_type = data_type[x_indices, :].T
            y_type = data_type[y_indices, :].T
            z_type = data_type[z_indices, :].T
        else:
            x_type = None
            y_type = None
            z_type = None
        if x_type is not None:
            x_type_s1 = x_type[0:size_first_block, :]
            x_type_s2 = x_type[size_first_block : T, :]
        else:
            x_type_s1 = None
            x_type_s2 = None
        if y_type is not None:
            y_type_s1 = y_type[0:size_first_block, :]
            y_type_s2 = y_type[size_first_block : T, :]
        else:
            y_type_s1 = None
            y_type_s2 = None
        if z_type is not None:
            z_type_s1 = z_type[0:size_first_block, :]
            z_type_s2 = z_type[size_first_block: T, :]
        else:
            z_type_s1 = None
            z_type_s2 = None

        ## Step 1: estimate conditional independencies
        if fixed_thres_bool == False:
            p_vals_pre = np.zeros((dim_x, dim_y))
        else:
            vals_pre = np.zeros((dim_x, dim_y))
        for j in np.arange(0, dim_x):
            for jj in np.arange(0, dim_y):
                if fixed_thres_bool == False:
                    p_vals_pre[j, jj] = self.cond_ind_test.run_test_raw(x_s1[j].reshape(size_first_block, 1),
                                                                   y_s1[jj].reshape(size_first_block, 1),
                                                                   z_s1.reshape(size_first_block, dim_z),
                                                                   x_type = x_type_s1,
                                                                   y_type = y_type_s1,
                                                                   z_type = z_type_s1)[1]
                else:
                    vals_pre[j, jj] = self.cond_ind_test.run_test_raw(x_s1[j].reshape(size_first_block, 1),
                                                                   y_s1[jj].reshape(size_first_block, 1),
                                                                   z_s1.reshape(size_first_block, dim_z),
                                                                   x_type = x_type_s1,
                                                                   y_type = y_type_s1,
                                                                   z_type = z_type_s1,
                                                                   alpha_or_thres=999.)[0] # just a dummy
        if fixed_thres_bool == False:
            indep_set = np.where(p_vals_pre > self.alpha_pre)
        else:
            indep_set = np.where(np.abs(vals_pre) >= self.fixed_thres_pre)

        # Step 2: test conditional independencies with increased effect sizes
        if self.cond_ind_test.significance != "fixed_thres":
            p_vals_main = np.zeros((dim_x, dim_y))
        else:
            dependent_main = np.zeros((dim_x, dim_y))
        test_stats_main = np.zeros((dim_x, dim_y))

        for j in np.arange(0, dim_x):
            for jj in np.arange(0, dim_y):
                indicesY = np.zeros(0)
                indicesX = np.zeros(0)

                if (j in indep_set[0]):
                    indicesX_locs = np.where(indep_set[0] == j)
                    indicesY = np.setdiff1d(indep_set[1][indicesX_locs], jj)
                if (jj in indep_set[1]):
                    indicesY_locs = np.where(indep_set[1] == jj)
                    indicesX = np.setdiff1d(indep_set[0][indicesY_locs], j)
                lix = indicesX.shape[0]
                liy = indicesY.shape[0]
                if lix + liy > 0:
                    if (lix > liy):
                        if x_type_s2 is not None:
                            z_type = np.hstack((z_type_s2, x_type_s2[:, indicesX]))
                        if fixed_thres_bool == False:
                            test_result = self.cond_ind_test.run_test_raw(x_s2[j].reshape(T - size_first_block, 1),
                                                        y_s2[jj].reshape(T - size_first_block, 1),
                                                        np.hstack((z_s2.reshape(T - size_first_block, dim_z),
                                                                    x_s2[indicesX].reshape(T - size_first_block, lix))),
                                                        x_type = x_type_s2,
                                                        y_type = y_type_s2,
                                                        z_type = z_type_s2)
                        else:
                            test_result = self.cond_ind_test.run_test_raw(x_s2[j].reshape(T - size_first_block, 1),
                                                        y_s2[jj].reshape(T - size_first_block, 1),
                                                        np.hstack((z_s2.reshape(T - size_first_block, dim_z),
                                                                    x_s2[indicesX].reshape(T - size_first_block, lix))),
                                                        x_type = x_type_s2,
                                                        y_type = y_type_s2,
                                                        z_type = z_type_s2,
                                                        alpha_or_thres=999.) # just a dummy
                    elif (lix <= liy):
                        if y_type_s2 is not None:
                            z_type_s2 = np.hstack((z_type_s2, y_type_s2[:, indicesY]))
                        if fixed_thres_bool == False:
                            test_result = self.cond_ind_test.run_test_raw(x_s2[j].reshape(T - size_first_block, 1),
                                                        y_s2[jj].reshape(T - size_first_block, 1),
                                                        np.hstack((z_s2.reshape(T - size_first_block, dim_z),
                                                                    y_s2[indicesY].reshape(T - size_first_block, liy))),
                                                        x_type = x_type_s2,
                                                        y_type = y_type_s2,
                                                        z_type = z_type_s2)
                        else:
                            test_result = self.cond_ind_test.run_test_raw(x_s2[j].reshape(T - size_first_block, 1),
                                                        y_s2[jj].reshape(T - size_first_block, 1),
                                                        np.hstack((z_s2.reshape(T - size_first_block, dim_z),
                                                                    y_s2[indicesY].reshape(T - size_first_block, liy))),
                                                        x_type = x_type_s2,
                                                        y_type = y_type_s2,
                                                        z_type = z_type_s2,
                                                        alpha_or_thres=999.) # just a dummy

                else:
                    if fixed_thres_bool == False:
                        test_result = self.cond_ind_test.run_test_raw(x_s2[j].reshape(T - size_first_block, 1),
                                                                      y_s2[jj].reshape(T - size_first_block, 1),
                                                                      z_s2.reshape(T - size_first_block, dim_z),
                                                                      x_type = x_type_s2,
                                                                      y_type = y_type_s2,
                                                                      z_type = z_type_s2)
                    else:
                        test_result = self.cond_ind_test.run_test_raw(x_s2[j].reshape(T - size_first_block, 1),
                                                                      y_s2[jj].reshape(T - size_first_block, 1),
                                                                      z_s2.reshape(T - size_first_block, dim_z),
                                                                      x_type = x_type_s2,
                                                                      y_type = y_type_s2,
                                                                      z_type = z_type_s2,
                                                                      alpha_or_thres=999.) # just a dummy
                
                test_stats_main[j, jj] = test_result[0]
                if fixed_thres_bool == False:
                    p_vals_main[j, jj] = test_result[1]


        # Aggregate p-values
        test_stats_aggregated = np.max(np.abs(test_stats_main))
        if self.cond_ind_test.significance != "fixed_thres":
            p_aggregated = np.min(np.array([np.min(p_vals_main) * dim_x * dim_y, 1]))
        else:
            p_aggregated = None

        return test_stats_aggregated, p_aggregated


    def get_dependence_measure(self, array, xyz, data_type=None, ci_test_thres = None):

        self.dep_measure, self.signif = self.calculate_dep_measure_and_significance(array = array, xyz = xyz, data_type = data_type, ci_test_thres = ci_test_thres)

        return self.dep_measure

    def get_analytic_significance(self, value = None, T = None, dim = None, xyz = None, data_type=None):

        return self.signif

if __name__ == '__main__':

    import tigramite
    from tigramite.data_processing import DataFrame
    import tigramite.data_processing as pp
    import numpy as np
    from tigramite.independence_tests.robust_parcorr import RobustParCorr
    from tigramite.independence_tests.cmiknn import CMIknn
    alpha = 0.05
    ci = PairwiseMultCI(fixed_thres_pre = 0.5, cond_ind_test = ParCorr(significance = "fixed_thres"))
    # ci = PairwiseMultCI(cond_ind_test=ParCorr(significance="fixed_thres"))
    # ci = PairwiseMultCI(cond_ind_test=ParCorr(significance="analytic"))
    T = 100
    reals = 1
    rate = np.zeros(reals)
    np.random.seed(123)
    for t in range(reals):
        # continuous example
        x = np.random.normal(0, 1, T).reshape(T, 1)
        y1 = np.random.normal(0, 1, T).reshape(T, 1)
        y2 = 5 * x + y1 + 0.3 * np.random.normal(0, 1, T).reshape(T, 1)
        z = np.random.normal(0, 1, T).reshape(T, 1)
        # discrete example
        #x = np.random.binomial(n=10, p=0.5, size=T).reshape(T, 1)
        #y1 = np.random.binomial(n=10, p=0.5, size=T).reshape(T, 1)
        #y2 = np.random.binomial(n=10, p=0.5, size=T).reshape(T, 1) +  x + y1
        # z = np.random.binomial(n=10, p=0.5, size=T).reshape(T, 1)

        test_stat, pval, dependent = ci.run_test_raw(x = x, y = np.hstack((y1,y2)), z = z, alpha_or_thres=0.91)#, z = z, alpha_pre = 0.5, pre_step_sample_fraction = 0.2, cond_ind_test = base_ci)# , x_type = np.ones((T, 1)), y_type = np.ones((T, 2)) , z_type = np.zeros((T, 1)))
        print(dependent)
        if (pval <= alpha):
            rate[t] = 1
        print("test_stat ", test_stat)
        print("pval ", pval)
    print(np.mean(rate))

