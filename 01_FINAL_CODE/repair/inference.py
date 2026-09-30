import hashlib, json, warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
from scipy.stats import beta
from arch.bootstrap import SPA, StepM, StationaryBootstrap
from .common import *


def hac(y, x=None, term=0):
    y = np.asarray(y, float)
    X = (
        np.ones((len(y), 1))
        if x is None
        else sm.add_constant(np.asarray(x, float), has_constant="add")
    )
    valid = np.isfinite(y) & np.isfinite(X).all(axis=1)
    y = y[valid]
    X = X[valid]
    n = len(y)
    lag = auto_lag(n)
    m = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": lag})
    ci = m.conf_int()[term]
    return dict(
        estimate=float(m.params[term]),
        standard_error=float(m.bse[term]),
        statistic=float(m.tvalues[term]),
        p_value=float(m.pvalues[term]),
        ci_lower=float(ci[0]),
        ci_upper=float(ci[1]),
        n=n,
        hac_lag=lag,
        sidedness="two_sided",
        covariance="HAC_Bartlett_default_no_small_sample_correction",
    )


def adjust_groups(df, by, p="p_value", out="holm_p"):
    df[out] = np.nan
    for _, g in df.groupby(by, dropna=False):
        ok = g[p].notna()
        if ok.any():
            df.loc[g.index[ok], out] = multipletests(g.loc[ok, p], method="holm")[1]
    return df


def basic_tests():
    session = []
    pred = []
    rev = []
    week = []
    subs = []
    for t in TICKERS:
        source = raw(t)
        d = source[source.in_sample].reset_index(drop=True)
        rn = d.overnight_adjusted_return.to_numpy()
        rd = d.daytime_return.to_numpy()
        for label, x in [("N", rn), ("D", rd), ("N_minus_D", rn - rd)]:
            session.append(
                dict(
                    ticker=t,
                    test=label,
                    model_version="analytical_adjusted_return",
                    period_start=CONFIG["sample_start"],
                    period_end=CONFIG["sample_end"],
                    family=f"nine_ETFs_{label}",
                    primary=label == "N_minus_D",
                    annualized_mean=float(x.mean() * 252),
                    **hac(x),
                )
            )
        for label, x in [("N", rn), ("D", rd)]:
            y = x[1:]
            lag = x[:-1]
            sg = np.sign(lag)
            for method, xx in [("AR1", lag), ("lag_sign", sg)]:
                pred.append(
                    dict(
                        ticker=t,
                        session=label,
                        specification=method,
                        term="lag_return" if method == "AR1" else "lag_sign",
                        family=f"nine_ETFs_{label}_{method}",
                        revision_diagnostic=method == "lag_sign",
                        **hac(y, xx, 1),
                    )
                )
                pred.append(
                    dict(
                        ticker=t,
                        session=label,
                        specification=method,
                        term="intercept",
                        family=f"nine_ETFs_{label}_{method}_intercepts",
                        revision_diagnostic=method == "lag_sign",
                        **hac(y, xx, 0),
                    )
                )
            z = -sg
            g = z * y
            drift = z.mean() * y.mean()
            cov = np.mean((z - z.mean()) * (y - y.mean()))
            assert abs(g.mean() - drift - cov) < 1e-15
            rev.append(
                dict(
                    ticker=t,
                    session=label,
                    mean_gross_return=g.mean(),
                    mean_position=z.mean(),
                    unconditional_return=y.mean(),
                    exposure_times_drift=drift,
                    timing_covariance=cov,
                    decomposition_residual=g.mean() - drift - cov,
                    interpretation="sample_identity_not_causal",
                    family=f"nine_ETFs_reversal_mean_{label}",
                    **hac(g),
                )
            )
        for label, y, x in [
            ("D_on_same_N", rd, rn),
            ("N_on_previous_D", rn[1:], rd[:-1]),
        ]:
            pred.append(
                dict(
                    ticker=t,
                    session="cross_session",
                    specification=label,
                    term="cross_return",
                    family="cross_session_diagnostics",
                    revision_diagnostic=False,
                    information_caveat="shared_boundary_price_measurement_and_same_boundary_execution_not_tested",
                    **hac(y, x, 1),
                )
            )
        xx = np.column_stack([rd[:-1], rn[1:]])
        for term, name in [(0, "intercept"), (1, "lag_D"), (2, "same_N")]:
            pred.append(
                dict(
                    ticker=t,
                    session="cross_session",
                    specification="D_on_lag_D_and_same_N",
                    term=name,
                    family="cross_session_multivariate_diagnostics",
                    revision_diagnostic=False,
                    **hac(rd[1:], xx, term),
                )
            )
        pre = source[~source.in_sample].Date.iloc[-1]
        gap = d.Date.diff().dt.days.to_numpy()
        gap[0] = (d.Date.iloc[0] - pre).days
        ind = (gap > 1).astype(float)
        week.append(
            dict(
                ticker=t,
                weekday_n=int((ind == 0).sum()),
                weekend_holiday_n=int(ind.sum()),
                weekday_mean=float(rn[ind == 0].mean()),
                weekend_holiday_mean=float(rn[ind == 1].mean()),
                family="nine_ETFs_weekend_difference",
                method="full_chronological_HAC_indicator_regression",
                **hac(rn, ind, 1),
            )
        )
        for a, b in [
            ("2007-01-09", "2012-12-31"),
            ("2013-01-01", "2019-12-31"),
            ("2020-01-01", "2025-12-31"),
        ]:
            mask = (d.Date >= a) & (d.Date <= b)
            for label, x in [("N", rn), ("D", rd), ("N_minus_D", rn - rd)]:
                subs.append(
                    dict(
                        ticker=t,
                        period_start=a,
                        period_end=b,
                        test=label,
                        family=f"{a}_{b}_nine_{label}",
                        **hac(x[mask]),
                    )
                )
    s = adjust_groups(pd.DataFrame(session), ["family"])
    s["holm_27_sensitivity"] = multipletests(s.p_value, method="holm")[1]
    s.to_csv(OUT / "session_tests.csv", index=False)
    for name, rows in [
        ("predictability_tests", pred),
        ("reversal_decomposition", rev),
        ("weekend_difference_tests", week),
        ("subperiod_session_tests", subs),
    ]:
        adjust_groups(pd.DataFrame(rows), ["family"]).to_csv(
            OUT / f"{name}.csv", index=False
        )


def fixed_seed(*labels):
    key = "|".join([str(CONFIG["seed"]), *map(str, labels)])
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], "little")


def mc_info(p, reps, plus_one=False):
    k = int(round(p * (reps + 1) - 1 if plus_one else p * reps))
    k = max(0, min(reps, k))
    return dict(
        mc_se=float(np.sqrt(p * (1 - p) / (reps + int(plus_one)))),
        mc_ci_lower=0.0 if k == 0 else float(beta.ppf(0.025, k, reps - k + 1)),
        mc_ci_upper=1.0 if k == reps else float(beta.ppf(0.975, k + 1, reps - k)),
        simulation_resolution=1 / (reps + int(plus_one)),
    )


def custom_tail(sim, observed, two_sided):
    if not np.isfinite(observed) or not np.isfinite(sim).all():
        return np.nan
    count = (
        np.count_nonzero(np.abs(sim) >= abs(observed))
        if two_sided
        else np.count_nonzero(sim >= observed)
    )
    return (1 + count) / (1 + len(sim))


def bootstrap_counts(n, reps, block, seed):
    bs = StationaryBootstrap(block, np.arange(n), seed=seed)
    counts = np.empty((reps, n), float)
    for b, (pos, kw) in enumerate(bs.bootstrap(reps)):
        counts[b] = np.bincount(pos[0], minlength=n)
    return counts


def pairwise():
    B = CONFIG["pairwise_reps"]
    rows = []
    for t in TICKERS:
        panels = {
            (m, c): pd.read_parquet(OUT / "daily" / f"{t}__{m}__{c}bps.parquet")[
                IDS
            ].to_numpy()
            for m in [LEGACY, LEDGER]
            for c in CONFIG["cost_bps"]
        }
        keys = list(panels)
        whole = np.column_stack(list(panels.values()))
        n = len(whole)
        for L in CONFIG["bootstrap_blocks"]:
            seed = fixed_seed("paired_stationary", t, L)
            counts = bootstrap_counts(n, B, L, seed)
            means = (counts @ whole) / n
            second = (counts @ (whole**2)) / n
            sds = np.sqrt(np.maximum((second - means**2) * n / (n - 1), 0))
            with np.errstate(divide="ignore", invalid="ignore"):
                sr_boot = means / sds * np.sqrt(252)
            for k, (m, cost) in enumerate(keys):
                arr = panels[m, cost]
                mu = arr.mean(0)
                sd = arr.std(0, ddof=1)
                with np.errstate(divide="ignore", invalid="ignore"):
                    sr = mu / sd * np.sqrt(252)
                bmu = means[:, 25 * k : 25 * (k + 1)]
                bsr = sr_boot[:, 25 * k : 25 * (k + 1)]
                best = int(np.argmax(np.prod(1 + arr, axis=0)))
                for j, (night, day) in enumerate(STRATS):
                    if j in [CASH, BH]:
                        continue
                    theta = mu[j] - mu[BH]
                    srt = sr[j] - sr[BH]
                    bm = bmu[:, j] - bmu[:, BH]
                    bs = bsr[:, j] - bsr[:, BH]
                    p = custom_tail(bm - theta, theta, False)
                    ps = custom_tail(bs - srt, srt, True)
                    ci = 2 * theta - np.quantile(bm, [0.975, 0.025])
                    cs = 2 * srt - np.quantile(bs, [0.975, 0.025])
                    hm = hac(arr[:, j] - arr[:, BH])
                    r = dict(
                        ticker=t,
                        night_rule=night,
                        day_rule=day,
                        strategy_id=IDS[j],
                        model_version=m,
                        cost_bps=cost,
                        block_length=L,
                        replications=B,
                        seed=seed,
                        n=n,
                        benchmark=IDS[BH],
                        selected_best_terminal_wealth=j == best,
                        selection_status="exploratory_not_selection_adjusted",
                        method="nonstudentized_centered_paired_stationary_bootstrap",
                        p_convention="(exceedances+1)/(B+1)",
                        mean_difference=theta,
                        annualized_mean_difference=theta * 252,
                        mean_ci_lower=ci[0],
                        mean_ci_upper=ci[1],
                        p_mean=p,
                        mean_alternative="greater_original_protocol",
                        sharpe_difference=srt,
                        sharpe_ci_lower=cs[0],
                        sharpe_ci_upper=cs[1],
                        p_sharpe=ps,
                        sharpe_alternative="two_sided",
                        hac_lag=hm["hac_lag"],
                        hac_statistic=hm["statistic"],
                        status=(
                            "ok" if np.isfinite(ps) else "degenerate_sharpe_resample"
                        ),
                    )
                    r.update({f"mean_{a}": v for a, v in mc_info(p, B, True).items()})
                    if np.isfinite(ps):
                        r.update(
                            {f"sharpe_{a}": v for a, v in mc_info(ps, B, True).items()}
                        )
                    rows.append(r)
            del counts, means, second, sds, sr_boot
            print(t, "paired bootstrap block", L, "complete", flush=True)
        d = pd.DataFrame(rows)
        adjust_groups(
            d,
            ["ticker", "model_version", "cost_bps", "block_length"],
            "p_mean",
            "holm_mean_23_exploratory",
        )
        adjust_groups(
            d,
            ["ticker", "model_version", "cost_bps", "block_length"],
            "p_sharpe",
            "holm_sharpe_23_exploratory",
        )
        d.to_csv(OUT / "pairwise_tests.csv", index=False)


def spa_stepm():
    B = CONFIG["spa_reps"]
    rows = []
    names = [s for j, s in enumerate(IDS) if j != BH]
    for t in TICKERS:
        for cost in CONFIG["cost_bps"]:
            for L in CONFIG["bootstrap_blocks"]:
                seed = fixed_seed("spa_stepm", t, cost, L)
                for m in [LEGACY, LEDGER]:
                    dd = pd.read_parquet(OUT / "daily" / f"{t}__{m}__{cost}bps.parquet")
                    arr = dd[IDS].to_numpy()
                    bh = -arr[:, BH]
                    loss = -dd[names].to_numpy()
                    deg = [
                        names[j] for j in range(24) if np.std(bh - loss[:, j]) < 1e-15
                    ]
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter("always")
                        step = StepM(
                            bh,
                            loss,
                            size=0.05,
                            block_size=L,
                            reps=B,
                            bootstrap="stationary",
                            studentize=True,
                            seed=seed,
                        )
                        step.compute()
                        step.spa.compute()
                        p = step.spa.pvalues
                    rows.append(
                        dict(
                            ticker=t,
                            model_version=m,
                            cost_bps=cost,
                            block_length=L,
                            replications=B,
                            seed=seed,
                            n=len(arr),
                            candidates=24,
                            candidate_ids=json.dumps(names),
                            benchmark=IDS[BH],
                            loss_definition="negative_daily_net_return",
                            null="all_candidate_expected_returns_at_most_BH",
                            p_consistent=float(p["consistent"]),
                            p_lower=float(p["lower"]),
                            p_upper=float(p["upper"]),
                            stepm_superior_count=len(step.superior_models),
                            stepm_superior_ids=json.dumps(
                                [names[int(i)] for i in step.superior_models]
                            ),
                            stepm_size=0.05,
                            family="24_non_BH_including_Cash_within_one_ETF_and_cost",
                            p_convention="arch_native_mean_strict_greater_no_manual_plus_one",
                            degenerate_candidates=json.dumps(deg),
                            status="ok" if not deg else "degenerate_candidate_reported",
                            warnings="; ".join(str(w.message) for w in caught),
                            **mc_info(float(p["consistent"]), B),
                        )
                    )
                print(t, "SPA/StepM", cost, L, "complete", flush=True)
                pd.DataFrame(rows).to_csv(OUT / "spa_stepm_tests.csv", index=False)
