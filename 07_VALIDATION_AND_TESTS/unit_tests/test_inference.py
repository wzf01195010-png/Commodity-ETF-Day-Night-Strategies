"""Statistical checks on controlled synthetic data, not significance targets."""

import numpy as np
import pandas as pd
import statsmodels.api as sm
import pytest
from arch.bootstrap import SPA, StepM, StationaryBootstrap
from repair.inference import (
    hac,
    adjust_groups,
    bootstrap_counts,
    custom_tail,
    fixed_seed,
)


def test_hac_uses_valid_sample_and_intercept():
    rng = np.random.default_rng(20260928)
    x = rng.normal(size=300)
    y = 0.4 + 0.2 * x + rng.normal(size=300)
    y[:7] = np.nan
    got = hac(y, x, 1)
    direct = sm.OLS(y[7:], sm.add_constant(x[7:])).fit(
        cov_type="HAC", cov_kwds={"maxlags": 5}
    )
    assert got["n"] == 293 and got["hac_lag"] == 5
    assert got["estimate"] == pytest.approx(direct.params[1])
    assert got["p_value"] == pytest.approx(direct.pvalues[1])


def test_holm_families_do_not_leak_into_each_other():
    d = pd.DataFrame({"family": ["A", "A", "B"], "p_value": [0.01, 0.04, 0.03]})
    out = adjust_groups(d, ["family"])
    np.testing.assert_allclose(out.holm_p, [0.02, 0.04, 0.03])


def test_pairing_counts_preserve_same_bootstrap_draws():
    n, B, L, seed = 70, 21, 5, 129
    x = np.arange(n, dtype=float) ** 2
    counts = bootstrap_counts(n, B, L, seed)
    direct = [
        x[pos[0]].mean()
        for pos, _ in StationaryBootstrap(L, np.arange(n), seed=seed).bootstrap(B)
    ]
    np.testing.assert_allclose(counts @ x / n, direct)
    assert np.all(counts.sum(axis=1) == n)
    assert np.array_equal(counts, bootstrap_counts(n, B, L, seed))


def test_custom_tail_finite_simulation_convention():
    x = np.array([-3.0, -1.0, 0.0, 1.0, 2.0])
    assert custom_tail(x, 2, False) == pytest.approx(2 / 6)
    assert custom_tail(x, 2, True) == pytest.approx(3 / 6)
    assert custom_tail(x, 9, False) == pytest.approx(1 / 6)


def test_reversal_drift_can_be_nonzero_without_predictability():
    # All four equally likely (position, return) pairs: independent by construction.
    z = np.array([1.0, 1.0, 0.0, 0.0])
    r = np.array([0.01, 0.03, 0.01, 0.03])
    cov = np.mean((z - z.mean()) * (r - r.mean()))
    assert cov == pytest.approx(0)
    assert np.mean(z * r) == pytest.approx(0.01)
    assert np.mean(z * r) == pytest.approx(z.mean() * r.mean() + cov)


def test_stepm_reuses_full_spa_family_correctly():
    rng = np.random.default_rng(20260928)
    benchmark = rng.normal(0, 0.01, 250)
    candidates = np.column_stack(
        [
            benchmark - 0.025 + rng.normal(0, 0.005, 250),
            rng.normal(0, 0.01, 250),
            np.zeros(250),
        ]
    )
    options = dict(
        block_size=5, reps=199, bootstrap="stationary", studentize=True, seed=991
    )
    direct = SPA(benchmark, candidates, **options)
    direct.compute()
    step = StepM(benchmark, candidates, size=0.05, **options)
    step.compute()
    step.spa.compute()
    np.testing.assert_allclose(step.spa.pvalues.to_numpy(), direct.pvalues.to_numpy())
    assert 0 in step.superior_models


def test_seed_derivation_is_stable_and_different_families_differ():
    assert fixed_seed("paired_stationary", "DBA", 10) == fixed_seed(
        "paired_stationary", "DBA", 10
    )
    assert fixed_seed("paired_stationary", "DBA", 10) != fixed_seed(
        "paired_stationary", "DBB", 10
    )
