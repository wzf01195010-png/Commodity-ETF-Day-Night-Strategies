import numpy as np
import pandas as pd
from scipy.optimize import brentq
from .common import *
from .data_audit import inputs
from .ledger import execute, daily_from_log, FIELDS


def run_one(inp, j, bps, **kw):
    log, path = execute(
        inp["prices"],
        inp["targets"][:, j],
        inp["distributions"],
        inp["time_days"],
        bps / 1e4,
        **kw,
    )
    daily = daily_from_log(log)
    m = metrics(daily, path)
    m.update(
        signal_transitions=int(log[:, 20].sum()),
        executed_trades=int(log[:, 22].sum()),
        rebalance_trades=int(log[:, 21].sum()),
        monetary_turnover=float(log[:, 11].sum()),
        equity_normalized_turnover=float(
            np.sum(
                np.divide(
                    log[:, 11], log[:, 6], out=np.zeros(len(log)), where=log[:, 6] > 0
                )
            )
        ),
        transaction_cost=float(log[:, 12].sum()),
        borrow_cost=float(log[:, 13].sum()),
        financing_cost=float(log[:, 14].sum()),
        cash_interest=float(log[:, 15].sum()),
        distribution_cash=float(log[:, 4].sum()),
        terminal_receivable=float(log[-1, 5]),
        insolvent=bool(log[:, 23].max()),
        self_financing_error=float(abs(log[:, 24]).max()),
        target_error=float(abs(log[:, 25]).max()),
    )
    assert m["self_financing_error"] < 1e-8 and m["target_error"] < 1e-8
    if not m["insolvent"]:
        assert np.isclose(100 * np.prod(1 + daily), path[-1], rtol=1e-11)
    return m, daily, log


def key(t, j, b, model, inp):
    n, d = STRATS[j]
    return dict(
        ticker=t,
        night_rule=n,
        day_rule=d,
        strategy_id=IDS[j],
        cost_bps=b,
        model_version=model,
        period_start=str(inp["sample"].Date.iloc[0].date()),
        period_end=str(inp["sample"].Date.iloc[-1].date()),
        n=len(inp["sample"]),
    )


def run_all():
    e = engine()
    oldrows = []
    newrows = []
    indexrows = []
    costrows = []
    subrows = []
    raterows = []
    recon = []
    (OUT / "daily").mkdir(exist_ok=True)
    (OUT / "trade_ledger").mkdir(exist_ok=True)
    for t in TICKERS:
        inp = inputs(t)
        ix = inputs(t, price_mode="index")
        df = e.load(t)
        references = Path(
            os.environ.get(
                "COMMODITY_LEGACY_REFERENCE_ROOT", str(ROOT / "Commodity_ETFS")
            )
        )
        ref = pd.read_csv(references / f"{t}_25_strategies_2007_2025.csv")
        old_by = {
            (
                import_legacy_label(r.Strategy)["night_rule"],
                import_legacy_label(r.Strategy)["day_rule"],
            ): r
            for _, r in ref.iterrows()
        }
        for b in CONFIG["cost_bps"]:
            logs = []
            panels = {m: np.empty((len(df), 25)) for m in [LEGACY, INDEX, LEDGER]}
            for j, (n, d) in enumerate(STRATS):
                r = e.run(df, n, d, b / 1e4)
                om = e.metrics(r["daily"], r["sessW"])
                lm = {
                    **metrics(r["daily"], np.r_[100, r["sessW"], r["TW"]]),
                    **{f"original_{k}": v for k, v in om.items()},
                    "signal_transitions": r["trades"],
                    "signal_transition_units": r["turnover"],
                }
                oldrows.append({**key(t, j, b, LEGACY, inp), **lm})
                expected = old_by[n, d][f"Final_wealth_{b}bps"]
                rel = abs(r["TW"] - expected) / abs(expected)
                recon.append(
                    {
                        **key(t, j, b, LEGACY, inp),
                        "legacy_label": f"{d}/{n}",
                        "legacy_label_order": "DAY/NIGHT",
                        "original_csv_tw": expected,
                        "recomputed_tw": r["TW"],
                        "relative_difference": rel,
                        "passed": rel < 1e-8,
                    }
                )
                im, iday, _ = run_one(ix, j, b)
                indexrows.append({**key(t, j, b, INDEX, inp), **im})
                m, daily, log = run_one(inp, j, b)
                newrows.append({**key(t, j, b, LEDGER, inp), **m})
                if b == 0:
                    assert np.isclose(im["terminal_wealth"], r["TW"], rtol=2e-11)
                panels[LEGACY][:, j] = r["daily"]
                panels[INDEX][:, j] = iday
                panels[LEDGER][:, j] = daily
                lf = pd.DataFrame(log, columns=FIELDS)
                lf.insert(0, "boundary_timestamp", inp["timestamps"])
                lf["signal_date"] = inp["signal_dates"]
                lf["signal_available_at"] = inp["signal_available"]
                lf["ticker"] = t
                lf["night_rule"] = n
                lf["day_rule"] = d
                lf["strategy_id"] = IDS[j]
                lf["cost_bps"] = b
                lf["model_version"] = LEDGER
                logs.append(lf)
            for model, arr in panels.items():
                d = pd.DataFrame(arr, columns=IDS)
                d.insert(0, "Date", df.Date.to_numpy())
                d.to_parquet(
                    OUT / "daily" / f"{t}__{model}__{b}bps.parquet",
                    index=False,
                    compression="zstd",
                )
            pd.concat(logs, ignore_index=True).to_parquet(
                OUT / "trade_ledger" / f"{t}__{b}bps.parquet",
                index=False,
                compression="zstd",
            )
        for b in CONFIG["sensitivity_cost_bps"]:
            for j in range(25):
                costrows.append({**key(t, j, b, LEDGER, inp), **run_one(inp, j, b)[0]})
        for a, b in [
            ("2007-01-09", "2012-12-31"),
            ("2013-01-01", "2019-12-31"),
            ("2020-01-01", "2025-12-31"),
        ]:
            sub = inputs(t, a, b)
            for cost in CONFIG["cost_bps"]:
                for j in range(25):
                    subrows.append(
                        {
                            **key(t, j, cost, LEDGER, sub),
                            **run_one(sub, j, cost)[0],
                            "selection_status": "descriptive_previously_inspected_subperiod",
                        }
                    )
        for name, br, fr, cr, delay in [
            ("cash_2pct_borrow_2pct_finance_5pct", 0.02, 0.05, 0.02, 0),
            ("cash_5pct_borrow_5pct_finance_8pct", 0.05, 0.08, 0.05, 0),
            ("distribution_settlement_20_calendar_days", 0, 0, 0, 20),
        ]:
            for b in CONFIG["cost_bps"]:
                for j in range(25):
                    m, _, _ = run_one(
                        inp,
                        j,
                        b,
                        borrow_rate=br,
                        financing_rate=fr,
                        cash_rate=cr,
                        settlement_delay_days=delay,
                    )
                    raterows.append(
                        {
                            **key(t, j, b, LEDGER, inp),
                            **m,
                            "scenario": name,
                            "borrow_rate": br,
                            "financing_rate": fr,
                            "eligible_cash_rate": cr,
                            "settlement_delay_days": delay,
                            "historical_rate_estimate": False,
                        }
                    )
        for name, rows in [
            ("strategy_metrics_legacy", oldrows),
            ("strategy_metrics_ledger", newrows),
            ("strategy_metrics_index_bridge", indexrows),
            ("cost_sensitivity", costrows),
            ("subperiod_metrics", subrows),
            ("financing_sensitivity", raterows),
            ("legacy_reconciliation", recon),
        ]:
            pd.DataFrame(rows).to_csv(OUT / f"{name}.csv", index=False)
        print(t, "all backtests and sensitivities complete", flush=True)
    keys = ["ticker", "strategy_id", "night_rule", "day_rule", "cost_bps"]
    c = (
        pd.DataFrame(oldrows)
        .merge(pd.DataFrame(indexrows), on=keys, suffixes=("_legacy", "_index"))
        .merge(pd.DataFrame(newrows), on=keys)
    )
    c["delta_target_cost_and_rebalancing"] = (
        c.terminal_wealth_index - c.terminal_wealth_legacy
    )
    c["delta_distribution_price_convention"] = (
        c.terminal_wealth - c.terminal_wealth_index
    )
    c["delta_total"] = c.terminal_wealth - c.terminal_wealth_legacy
    c.to_csv(OUT / "model_comparison.csv", index=False)
    assert len(recon) == 675 and all(r["passed"] for r in recon)


def breakeven():
    rows = []
    grid = np.array([0, 1, 2, 5, 10, 20, 50, 100], float)
    for t in TICKERS:
        inp = inputs(t)
        cache = {}

        def tw(j, b):
            k = (j, float(b))
            if k not in cache:
                cache[k] = run_one(inp, j, b)[0]["terminal_wealth"]
            return cache[k]

        for j in range(25):
            if j in [BH, CASH]:
                continue
            for benchmark in ["BH", "Cash"]:

                def f(b):
                    return tw(j, b) - (tw(BH, b) if benchmark == "BH" else 100)

                f0 = f(0)
                root = np.nan
                status = (
                    "no_gross_advantage"
                    if f0 <= 0
                    else "no_crossing_on_0_to_100bps_grid"
                )
                if f0 > 0:
                    for a, b in zip(grid[:-1], grid[1:]):
                        if f(a) > 0 and f(b) <= 0:
                            root = brentq(f, a, b, xtol=1e-8)
                            status = "first_bracketed_crossing"
                            break
                rows.append(
                    {
                        **key(t, j, 0, LEDGER, inp),
                        "benchmark": benchmark,
                        "breakeven_bps": root,
                        "status": status,
                        "search_grid_bps": "0,1,2,5,10,20,50,100",
                        "root_definition": "first_positive_to_nonpositive_grid_bracket_not_global_monotonicity_claim",
                    }
                )
        print(t, "break-even complete", flush=True)
    pd.DataFrame(rows).to_csv(OUT / "breakeven_costs.csv", index=False)
