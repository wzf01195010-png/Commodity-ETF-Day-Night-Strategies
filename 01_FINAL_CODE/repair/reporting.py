"""Summaries from final outputs; no new fitting, signals, or data filtering."""

import pandas as pd
import numpy as np
from .common import OUT, TICKERS, LEGACY, LEDGER, IDS, BH, CASH, json_write, CONFIG


def findings():
    counts = []
    winners = []
    for name, model in [("legacy", LEGACY), ("ledger", LEDGER)]:
        d = pd.read_csv(OUT / f"strategy_metrics_{name}.csv")
        for b in [0, 1, 2]:
            q = d[d.cost_bps == b].copy()
            bh = q[q.strategy_id == IDS[BH]].set_index("ticker").terminal_wealth
            q["benchmark_terminal_wealth"] = q.ticker.map(bh)
            active = q[~q.strategy_id.isin([IDS[BH], IDS[CASH]])]
            better = active[active.terminal_wealth > active.benchmark_terminal_wealth]
            counts.append(
                dict(
                    model_version=model,
                    cost_bps=b,
                    denominator=len(active),
                    outperformers=len(better),
                    absolute_profitable_outperformers=int(
                        (better.terminal_wealth > 100).sum()
                    ),
                )
            )
            if name == "ledger" and b == 2:
                winners = better.to_dict("records")
    counts = pd.DataFrame(counts)
    counts.to_csv(OUT / "outperformer_counts.csv", index=False)
    pd.DataFrame(winners).to_csv(OUT / "relative_outperformers_2bps.csv", index=False)
    c = pd.read_csv(OUT / "model_comparison.csv")
    a = pd.read_csv(OUT / "corporate_action_audit.csv")
    spa = pd.read_csv(OUT / "spa_stepm_tests.csv")
    spa = spa[spa.model_version == LEDGER]
    s = pd.read_csv(OUT / "session_tests.csv")
    p = pd.read_csv(OUT / "predictability_tests.csv")
    new = pd.read_csv(OUT / "strategy_metrics_ledger.csv")
    ss = new[
        (new.night_rule == "Short") & (new.day_rule == "Short") & (new.cost_bps == 2)
    ]
    base = pd.read_csv(OUT / "legacy_reconciliation.csv")
    summary = dict(
        sample_start=CONFIG["sample_start"],
        sample_end=CONFIG["sample_end"],
        days_per_etf=4776,
        tickers=TICKERS,
        etf_count=9,
        strategies_per_etf=25,
        cost_bps=[0, 1, 2],
        main_result_rows=len(new),
        baseline_reconciled_rows=len(base),
        baseline_max_relative_error=float(base.relative_difference.max()),
        cost_counts=counts.to_dict("records"),
        relative_winners_2bps=winners,
        significant_holm_session={
            label: s[(s.test == label) & (s.holm_p < 0.05)].ticker.tolist()
            for label in ["N", "D", "N_minus_D"]
        },
        positive_overnight_mean_count=int(((s.test == "N") & (s.estimate > 0)).sum()),
        daytime_ar_negative_count=int(
            (
                (p.session == "D")
                & (p.specification == "AR1")
                & (p.term == "lag_return")
                & (p.estimate < 0)
            ).sum()
        ),
        daytime_ar_raw_significant_count=int(
            (
                (p.session == "D")
                & (p.specification == "AR1")
                & (p.term == "lag_return")
                & (p.p_value < 0.05)
            ).sum()
        ),
        daytime_sign_raw_significant_count=int(
            (
                (p.session == "D")
                & (p.specification == "lag_sign")
                & (p.term == "lag_sign")
                & (p.p_value < 0.05)
            ).sum()
        ),
        spa_baseline_families=int((spa.block_length == 10).sum()),
        spa_all_families=len(spa),
        spa_rejections=int((spa.p_consistent < 0.05).sum()),
        stepm_superior_count=int(spa.stepm_superior_count.sum()),
        spa_min_p_by_block={
            str(L): float(spa.loc[spa.block_length == L, "p_consistent"].min())
            for L in [5, 10, 20]
        },
        short_short_executed_trades_range_2bps=[
            int(ss.executed_trades.min()),
            int(ss.executed_trades.max()),
        ],
        distribution_overnight_max_difference_bps=float(a.difference_bps.abs().max()),
        retained_anomalies=len(pd.read_csv(OUT / "anomaly_audit.csv")),
        max_absolute_terminal_change=float(c.delta_total.abs().max()),
        max_self_financing_error=float(new.self_financing_error.max()),
        max_target_weight_error=float(new.target_error.max()),
        manuscript_updated=False,
    )
    json_write(OUT / "findings_summary.json", summary)
    # Paired old/new inference contrasts use the SAME current procedure/draws on
    # different wealth engines. They are not mislabeled as original 2025 p-values.
    for fn, keys in [
        (
            "pairwise_tests",
            [
                "ticker",
                "strategy_id",
                "night_rule",
                "day_rule",
                "cost_bps",
                "block_length",
            ],
        ),
        ("spa_stepm_tests", ["ticker", "cost_bps", "block_length"]),
    ]:
        d = pd.read_csv(OUT / f"{fn}.csv")
        old = d[d.model_version == LEGACY]
        new = d[d.model_version == LEDGER]
        joined = old.merge(
            new, on=keys, suffixes=("_legacy", "_ledger"), validate="one_to_one"
        )
        joined.to_csv(OUT / f"old_vs_new_{fn}.csv", index=False)
    print(
        "Findings and paired old/new contrasts generated from completed CSVs.",
        flush=True,
    )


if __name__ == "__main__":
    findings()
