"""Render final tables/figures from CSV/parquet outputs, never from handwritten values."""

import json
from pathlib import Path
import numpy as np
import pandas as pd
from .common import OUT, TICKERS, STRATS, IDS, LEDGER, BH, CONFIG

TABLE_NAMES = {
    "desc": "session_mean_tests",
    "pred": "daytime_predictability_tests",
    "predictability_N": "overnight_predictability_tests",
    "spa": "spa_stepm_results_block10",
    "spa_block_sensitivity": "spa_stepm_block_length_sensitivity",
    "pairwise": "long_reversal_vs_buy_hold_bootstrap",
    "sub": "selected_subperiod_terminal_wealth_2bps",
    "breakeven": "selected_break_even_costs_vs_buy_hold",
    "weekend": "weekend_holiday_difference_tests",
    "trades": "executed_trades_0bps_2007_2025",
    "turnover": "equity_normalized_turnover_0bps_2007_2025",
    "signal_transitions": "signal_transitions_0bps_2007_2025",
}
for cost, suffix in [(0, ""), (1, "_1bp"), (2, "_2bps")]:
    for key, label in [("mdd", "mdd"), ("vol", "volatility"), ("sharpe", "sharpe")]:
        TABLE_NAMES[key + suffix] = f"{label}_{cost}bps_2007_2025"
    TABLE_NAMES[{0: "tw_0bps", 1: "tw_1bp", 2: "tw_2bps"}[cost]] = (
        f"terminal_wealth_{cost}bps_2007_2025"
    )


def fmt(x, places=4):
    return "--" if pd.isna(x) else f"{x:.{places}f}"


def tables():
    templates = json.loads((Path(__file__).parent / "table_templates.json").read_text())
    dest = OUT / "latex_tables"
    dest.mkdir(exist_ok=True)
    bodies = {}
    metrics = pd.read_csv(OUT / "strategy_metrics_ledger.csv").set_index(
        ["ticker", "cost_bps", "night_rule", "day_rule"]
    )
    for b in [0, 1, 2]:
        mapping = [
            ({0: "tw_0bps", 1: "tw_1bp", 2: "tw_2bps"}[b], "terminal_wealth", 1, 2)
        ]
        suffix = {0: "", 1: "_1bp", 2: "_2bps"}[b]
        mapping += [
            ("mdd" + suffix, "MDD", 100, 2),
            ("vol" + suffix, "Vol", 100, 2),
            ("sharpe" + suffix, "SR", 1, 3),
        ]
        if b == 0:
            mapping += [
                ("trades", "executed_trades", 1, 0),
                ("signal_transitions", "signal_transitions", 1, 0),
                ("turnover", "equity_normalized_turnover", 1, 2),
            ]
        for name, col, scale, digits in mapping:
            bodies[name] = [
                [
                    n,
                    d,
                    *[
                        fmt(metrics.loc[(t, b, n, d), col] * scale, digits)
                        for t in TICKERS
                    ],
                ]
                for n, d in STRATS
            ]
    s = pd.read_csv(OUT / "session_tests.csv").set_index(["ticker", "test"])
    rows = []
    for t in TICKERS:
        n, d, x = [s.loc[t, label] for label in ["N", "D", "N_minus_D"]]
        rows.append(
            [
                t,
                fmt(n.annualized_mean * 100, 2),
                fmt(n.holm_p),
                fmt(d.annualized_mean * 100, 2),
                fmt(d.holm_p),
                fmt(x.annualized_mean * 100, 2),
                fmt(x.p_value),
                fmt(x.holm_p),
                str(n.n),
                str(n.hac_lag),
            ]
        )
    bodies["desc"] = rows
    p = pd.read_csv(OUT / "predictability_tests.csv").set_index(
        ["ticker", "session", "specification", "term"]
    )
    r = pd.read_csv(OUT / "reversal_decomposition.csv").set_index(["ticker", "session"])
    for session, name in [("D", "pred"), ("N", "predictability_N")]:
        rows = []
        for t in TICKERS:
            a = p.loc[t, session, "AR1", "lag_return"]
            g = p.loc[t, session, "lag_sign", "lag_sign"]
            rr = r.loc[t, session]
            rows.append(
                [
                    t,
                    fmt(a.estimate, 5),
                    fmt(a.p_value),
                    fmt(a.holm_p),
                    fmt(g.estimate, 6),
                    fmt(g.p_value),
                    fmt(g.holm_p),
                    fmt(rr.mean_gross_return * 25200, 2),
                    fmt(rr.p_value),
                    str(a.n),
                    str(a.hac_lag),
                ]
            )
        bodies[name] = rows
    spa = pd.read_csv(OUT / "spa_stepm_tests.csv")
    spa = spa[spa.model_version == LEDGER].set_index(
        ["ticker", "cost_bps", "block_length"]
    )
    rows = []
    for t in TICKERS:
        row = [t]
        for b in [0, 1, 2]:
            a = spa.loc[t, b, 10]
            row.extend([fmt(a.p_consistent), str(a.stepm_superior_count)])
        rows.append(row)
    bodies["spa"] = rows
    bodies["spa_block_sensitivity"] = [
        [
            t,
            str(b),
            *[fmt(spa.loc[(t, b, L), "p_consistent"]) for L in [5, 10, 20]],
            *[str(spa.loc[(t, b, L), "stepm_superior_count"]) for L in [5, 10, 20]],
        ]
        for t in TICKERS
        for b in [0, 1, 2]
    ]
    bs = pd.read_csv(OUT / "pairwise_tests.csv")
    bs = bs[
        (bs.model_version == LEDGER)
        & (bs.block_length == 10)
        & (bs.strategy_id == "N_Long__D_Reversal")
    ].set_index(["ticker", "cost_bps"])
    bodies["pairwise"] = []
    for t in TICKERS:
        for b in [0, 1, 2]:
            a = bs.loc[t, b]
            bodies["pairwise"].append(
                [
                    t,
                    str(b),
                    fmt(a.annualized_mean_difference * 100, 2),
                    fmt(a.p_mean),
                    fmt(a.sharpe_difference, 3),
                    f"[{fmt(a.sharpe_ci_lower,3)}, {fmt(a.sharpe_ci_upper,3)}]",
                    fmt(a.p_sharpe),
                ]
            )
    sub = pd.read_csv(OUT / "subperiod_metrics.csv")
    sub = sub[sub.cost_bps == 2].set_index(["ticker", "period_start", "strategy_id"])
    chosen = [
        "N_Long__D_Long",
        "N_Long__D_Cash",
        "N_Long__D_Reversal",
        "N_Short__D_Short",
    ]
    bodies["sub"] = [
        [
            t,
            a,
            str(sub.loc[(t, a, chosen[0]), "n"]),
            *[fmt(sub.loc[(t, a, s), "terminal_wealth"], 2) for s in chosen],
        ]
        for t in TICKERS
        for a in ["2007-01-09", "2013-01-02", "2020-01-02"]
    ]
    be = pd.read_csv(OUT / "breakeven_costs.csv")
    be = be[be.benchmark == "BH"].set_index(["ticker", "night_rule", "day_rule"])
    bodies["breakeven"] = []
    for t in TICKERS:
        for n, d in [
            ("Long", "Cash"),
            ("Long", "Reversal"),
            ("Cash", "Reversal"),
            ("Short", "Short"),
        ]:
            a = be.loc[t, n, d]
            bodies["breakeven"].append(
                [t, n, d, fmt(a.breakeven_bps, 3), a.status.replace("_", r"\_")]
            )
    w = pd.read_csv(OUT / "weekend_difference_tests.csv").set_index("ticker")
    bodies["weekend"] = []
    for t in TICKERS:
        a = w.loc[t]
        bodies["weekend"].append(
            [
                t,
                str(a.weekday_n),
                str(a.weekend_holiday_n),
                fmt(a.weekday_mean * 25200, 2),
                fmt(a.weekend_holiday_mean * 25200, 2),
                fmt(a.estimate * 25200, 2),
                fmt(a.p_value),
                fmt(a.holm_p),
                str(a.n),
                str(a.hac_lag),
            ]
        )
    assert set(bodies) == set(templates) == set(TABLE_NAMES)
    for name, rows in bodies.items():
        body = "".join(" & ".join(row) + r" \\" + "\n" for row in rows)
        (dest / (TABLE_NAMES[name] + ".tex")).write_text(
            templates[name]["prefix"] + body + templates[name]["suffix"]
        )
    print(
        f"Generated {len(bodies)} final LaTeX tables from machine-readable results.",
        flush=True,
    )


def figures():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    dest = OUT / "figures"
    dest.mkdir(exist_ok=True)
    chosen = [
        "N_Long__D_Long",
        "N_Long__D_Cash",
        "N_Long__D_Reversal",
        "N_Short__D_Short",
    ]
    labels = ["Long / Long (BH)", "Long / Cash", "Long / Reversal", "Short / Short"]
    metrics = pd.read_csv(OUT / "cost_sensitivity.csv")
    fig, axes = plt.subplots(3, 3, figsize=(12, 9), layout="constrained")
    for ax, t in zip(axes.flat, TICKERS):
        for s, label in zip(chosen, labels):
            a = metrics[(metrics.ticker == t) & (metrics.strategy_id == s)].sort_values(
                "cost_bps"
            )
            ax.plot(
                a.cost_bps, a.terminal_wealth, marker="o", markersize=3, label=label
            )
        ax.set(
            title=t,
            xlabel="Cost per traded notional (bps)",
            ylabel="Terminal wealth (initial = 100)",
        )
        ax.grid(alpha=0.2)
    fig.suptitle("Scenario trading costs · 2007–2025 · Night rule / Day rule")
    fig.legend(
        *axes[0, 0].get_legend_handles_labels(), loc="outside lower center", ncol=4
    )
    fig.savefig(
        dest / "terminal_wealth_vs_transaction_cost_2007_2025.png",
        dpi=160,
        bbox_inches="tight",
        pad_inches=0.15,
    )
    plt.close(fig)
    fig, axes = plt.subplots(3, 3, figsize=(12, 9), layout="constrained")
    for ax, t in zip(axes.flat, TICKERS):
        d = pd.read_parquet(OUT / "daily" / f"{t}__{LEDGER}__2bps.parquet")
        for s, label in zip(chosen, labels):
            ax.plot(d.Date, 100 * np.cumprod(1 + d[s]), label=label, linewidth=1)
        ax.set(title=t, ylabel="Close equity (initial = 100)", yscale="log")
        ax.grid(alpha=0.2)
        ax.xaxis.set_major_locator(mdates.YearLocator(5))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.set_xlim(d.Date.iloc[0], d.Date.iloc[-1])
    fig.suptitle("Selected strategies · 2 bps scenario · Night rule / Day rule")
    fig.legend(
        *axes[0, 0].get_legend_handles_labels(), loc="outside lower center", ncol=4
    )
    fig.savefig(
        dest / "selected_strategy_wealth_paths_2bps_2007_2025.png",
        dpi=160,
        bbox_inches="tight",
        pad_inches=0.15,
    )
    plt.close(fig)
    print(
        "Generated 2 final figures from stored results (no strategy rerun).", flush=True
    )


if __name__ == "__main__":
    tables()
    figures()
