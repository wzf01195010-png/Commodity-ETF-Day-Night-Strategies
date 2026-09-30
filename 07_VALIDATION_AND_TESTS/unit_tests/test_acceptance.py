"""Acceptance checks against actual complete outputs; no new strategy estimation."""

import json
import numpy as np
import pandas as pd
from repair.common import OUT, TICKERS, IDS, LEGACY, INDEX, LEDGER, BH, metrics, raw


def test_complete_fixed_sample_and_baseline():
    d = pd.read_csv(OUT / "data_checks.csv")
    b = pd.read_csv(OUT / "legacy_reconciliation.csv")
    assert (
        len(d) == 9 and set(d.ticker) == set(TICKERS) and (d.sample_rows == 4776).all()
    )
    assert (d.start == "2007-01-09").all() and (d.end == "2025-12-31").all()
    assert len(b) == 675 and b.passed.all() and b.relative_difference.max() < 1e-8
    assert d.filter(like="sign_mismatches").to_numpy().sum() == 0


def test_every_grid_and_strategy_id_is_unambiguous():
    for fn, count in [
        ("strategy_metrics_ledger", 675),
        ("strategy_metrics_legacy", 675),
        ("strategy_metrics_index_bridge", 675),
        ("cost_sensitivity", 1125),
        ("subperiod_metrics", 2025),
        ("financing_sensitivity", 2025),
        ("breakeven_costs", 414),
    ]:
        d = pd.read_csv(OUT / f"{fn}.csv")
        assert len(d) == count
        assert set(d.ticker) == set(TICKERS)
        assert (d.strategy_id == "N_" + d.night_rule + "__D_" + d.day_rule).all()
    d = pd.read_csv(OUT / "strategy_metrics_ledger.csv")
    assert not d.duplicated(["ticker", "strategy_id", "cost_bps"]).any()
    assert not d.insolvent.any()


def test_bridge_zero_cost_and_difference_attribution():
    d = pd.read_csv(OUT / "model_comparison.csv")
    z = d[d.cost_bps == 0]
    np.testing.assert_allclose(
        z.terminal_wealth_index, z.terminal_wealth_legacy, rtol=2e-11
    )
    np.testing.assert_allclose(
        d.delta_target_cost_and_rebalancing + d.delta_distribution_price_convention,
        d.delta_total,
        atol=2e-12,
    )


def test_all_ledger_boundaries_cash_fees_timing_and_risk():
    results = pd.read_csv(OUT / "strategy_metrics_ledger.csv").set_index(
        ["ticker", "cost_bps", "strategy_id"]
    )
    checks = []
    for t in TICKERS:
        for b in [0, 1, 2]:
            ledger = pd.read_parquet(OUT / "trade_ledger" / f"{t}__{b}bps.parquet")
            daily = pd.read_parquet(OUT / "daily" / f"{t}__{LEDGER}__{b}bps.parquet")
            assert len(ledger) == 9553 * 25 and len(daily) == 4776
            assert (ledger.signal_available_at <= ledger.boundary_timestamp).all()
            cash_error = abs(
                ledger.cash_after
                - (
                    ledger.cash_before
                    + ledger.eligible_cash_interest
                    - ledger.borrow_cost
                    - ledger.financing_cost
                    + ledger.distribution_settlement
                    - ledger.shares_traded * ledger.price
                    - ledger.transaction_cost
                )
            ).max()
            equity_error = abs(
                ledger.equity_after_trade
                - (
                    ledger.cash_after
                    + ledger.shares_after * ledger.price
                    + ledger.distribution_receivable
                )
            ).max()
            fee_error = abs(
                ledger.transaction_cost - ledger.traded_notional * b / 1e4
            ).max()
            assert cash_error < 1e-8 and equity_error < 1e-8 and fee_error < 1e-10
            source = raw(t)
            source = source[source.in_sample]
            distributions = np.zeros(9553)
            distributions[1::2] = (source.Dividends + source.Capital_Gains).to_numpy()
            for s, g in ledger.groupby("strategy_id", sort=False):
                assert len(g) == 9553 and g.iloc[-1].shares_after == 0
                np.testing.assert_allclose(
                    g.distribution_accrual.to_numpy(),
                    g.shares_before.to_numpy() * distributions,
                    atol=1e-12,
                )
                expected = results.loc[t, b, s]
                path = np.r_[
                    100,
                    g[["equity_before_trade", "equity_after_trade"]].to_numpy().ravel(),
                ]
                ds = daily[s].to_numpy()
                got = metrics(ds, path)
                for k in ["terminal_wealth", "MDD", "Vol", "SR", "CAGR"]:
                    np.testing.assert_allclose(
                        got[k], expected[k], rtol=1e-10, atol=1e-12, equal_nan=True
                    )
                np.testing.assert_allclose(
                    100 * np.prod(1 + ds), expected.terminal_wealth, rtol=1e-11
                )
                assert int(g.executed_trade.sum()) == expected.executed_trades
            checks.append(
                dict(
                    ticker=t,
                    cost_bps=b,
                    ledger_rows=len(ledger),
                    max_cash_equation_residual=cash_error,
                    max_equity_equation_residual=equity_error,
                    max_fee_equation_residual=fee_error,
                    status="PASS",
                )
            )
    pd.DataFrame(checks).to_csv(OUT / "ledger_acceptance_checks.csv", index=False)


def test_bootstrap_complete_families_and_conventions():
    d = pd.read_csv(OUT / "pairwise_tests.csv")
    assert len(d) == 3726 and set(d.model_version) == {LEGACY, LEDGER}
    assert set(d.block_length) == {5, 10, 20} and (d.replications == 2000).all()
    assert (
        d.groupby(["ticker", "model_version", "cost_bps", "block_length"]).size() == 23
    ).all()
    assert (d.p_mean >= 1 / 2001).all() and (d.p_mean <= 1).all()
    assert d.status.eq("ok").all()


def test_spa_stepm_complete_loss_families():
    d = pd.read_csv(OUT / "spa_stepm_tests.csv")
    assert (
        len(d) == 162 and (d.candidates == 24).all() and (d.replications == 5000).all()
    )
    assert d.p_consistent.between(0, 1).all() and d.status.eq("ok").all()
    for r in d.itertuples():
        names = json.loads(r.candidate_ids)
        assert len(names) == 24 and "N_Cash__D_Cash" in names and IDS[BH] not in names
        assert len(json.loads(r.stepm_superior_ids)) == r.stepm_superior_count


def test_hac_full_samples_and_reversal_identity():
    d = pd.read_csv(OUT / "session_tests.csv")
    p = pd.read_csv(OUT / "predictability_tests.csv")
    r = pd.read_csv(OUT / "reversal_decomposition.csv")
    assert len(d) == 27 and (d.n == 4776).all() and (d.hac_lag == 9).all()
    assert len(p) == 117 and (p.hac_lag == 9).all()
    assert (p.loc[p.session.isin(["N", "D"]), "n"] == 4775).all()
    assert abs(r.decomposition_residual).max() < 1e-15


def test_subperiod_coverage_is_disjoint_complete_and_declared():
    d = pd.read_csv(OUT / "subperiod_metrics.csv")
    assert set(d.period_start) == {"2007-01-09", "2013-01-02", "2020-01-02"}
    assert set(d.period_end) == {"2012-12-31", "2019-12-31", "2025-12-31"}
    assert (d.groupby(["ticker", "strategy_id", "cost_bps"]).n.sum() == 4776).all()
    assert (d.selection_status == "descriptive_previously_inspected_subperiod").all()
