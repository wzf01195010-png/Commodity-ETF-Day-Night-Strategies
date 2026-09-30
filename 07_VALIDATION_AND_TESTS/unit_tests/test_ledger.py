import numpy as np
import pytest
from repair.ledger import execute, solve_target, daily_from_log, FIELDS
from repair.common import import_legacy_label, engine, auto_lag, metrics


def col(a, n):
    return a[:, FIELDS.index(n)]


def run(p, z, c=0, div=None, days=None, **kw):
    p = np.array(p, float)
    return execute(
        p,
        np.array(z, float),
        np.zeros(len(p)) if div is None else np.array(div, float),
        np.arange(len(p), dtype=float) if days is None else np.array(days, float),
        c,
        **kw
    )


def test_unchanged_short_covers_twenty():
    a, _ = run([100, 110, 110], [-1, -1, 0])
    assert col(a, "equity_before_trade")[1] == pytest.approx(90)
    assert col(a, "shares_traded")[1] * 110 == pytest.approx(20)
    assert col(a, "rebalance_trade")[1] == 1
    assert col(a, "signal_switch")[1] == 0


def test_long_no_drift_trade():
    a, _ = run([100, 110, 110], [1, 1, 0])
    assert col(a, "traded_notional")[1] == 0


@pytest.mark.parametrize("target", [1.0, -1.0])
def test_flip_post_cost_self_financing(target):
    v, d, f = solve_target(100, -target * 100, target, 0.001)
    assert v == pytest.approx(target * (100 - f))
    assert abs(d) > 199
    assert f == pytest.approx(0.001 * abs(d))


@pytest.mark.parametrize("z", [1, -1])
def test_constant_price_costs(z):
    a, p = run([100, 100, 100], [z, z, 0], c=0.001)
    assert p[-1] == pytest.approx(100 - col(a, "transaction_cost").sum())
    assert abs(col(a, "self_financing_residual")).max() < 1e-12
    assert abs(col(a, "target_weight_residual")).max() < 1e-12


def test_split_adjusted_no_double_application():
    a, p = run([50, 50, 50], [1, 1, 0])
    assert p[-1] == 100
    assert col(a, "shares_after")[0] == 2
    assert col(a, "traded_notional")[1] == 0


@pytest.mark.parametrize("z", [1, -1])
def test_distribution_once_long_and_short(z):
    a, p = run([100, 95, 95], [z, z, 0], div=[0, 5, 0])
    assert col(a, "distribution_accrual")[1] == z * 5
    assert col(a, "distribution_settlement").sum() == z * 5
    assert p[-1] == pytest.approx(100)
    assert col(a, "distribution_receivable")[-1] == 0


def test_delayed_signed_receivable():
    a, p = run(
        [100, 95, 95, 95],
        [1, 1, 1, 0],
        div=[0, 5, 0, 0],
        days=[0, 1, 5, 22],
        settlement_delay_days=20,
    )
    assert col(a, "distribution_receivable")[1] == 5
    assert col(a, "distribution_settlement")[1] == 0
    assert col(a, "distribution_settlement")[-1] == 5
    assert p[-1] == pytest.approx(100)


def test_gross_recursion_random_path():
    rng = np.random.default_rng(20260928)
    r = rng.normal(0, 0.01, 100)
    p = 100 * np.cumprod(np.r_[1, 1 + r])
    z = np.r_[rng.choice([-1.0, 0.0, 1.0], 100), 0]
    a, w = run(p, z)
    assert w[-1] == pytest.approx(100 * np.prod(1 + z[:-1] * r), rel=1e-12)


def test_entry_and_exit_both_in_wealth_and_drawdown():
    a, p = run([100, 100, 100], [1, 1, 0], c=0.01)
    assert p[0] == 100 and p[2] < 100 and p[-1] < p[-2]
    d = daily_from_log(a)
    assert 100 * np.prod(1 + d) == pytest.approx(p[-1])
    assert metrics(d, p)["MDD"] == pytest.approx(1 - p[-1] / 100)


def test_insolvency_stops_no_resume():
    a, p = run([100, 250, 240, 240, 260], [-1, -1, -1, -1, 0])
    assert col(a, "insolvent")[1] == 1
    assert np.all(col(a, "shares_after")[1:] == 0)
    assert np.all(p[4:] == p[4])


def test_interest_excludes_restricted_short_proceeds():
    a, p = run(
        [100, 100, 100],
        [-1, -1, 0],
        days=[0, 365, 365],
        cash_rate=0.05,
        borrow_rate=0.02,
    )
    assert col(a, "restricted_short_collateral")[1] == 100
    assert col(a, "eligible_cash_balance")[1] == 100
    assert col(a, "eligible_cash_interest")[1] == 5
    assert col(a, "borrow_cost")[1] == 2
    assert p[-1] == pytest.approx(103)


def test_importer_explicit_transpose():
    assert import_legacy_label("Cash/Long") == dict(
        night_rule="Long", day_rule="Cash", strategy_id="N_Long__D_Cash"
    )
    assert import_legacy_label("Reversal/Short")["night_rule"] == "Short"


def test_signal_no_lookahead_and_zero_sign():
    e = engine()
    r = np.array([0.1, -0.1, 0, 0.2])
    assert np.array_equal(e.positions("Momentum", r, 0), [0, 1, -1, 0])
    a = e.positions("Reversal", r, 0.3)
    r[2:] = [-0.9, -0.5]
    assert np.array_equal(e.positions("Reversal", r, 0.3)[:3], a[:3])


def test_actual_hac_lag():
    assert auto_lag(4776) == 9 and auto_lag(100) == 4
