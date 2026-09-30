import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
from .common import *


def reconstructed(d):
    pc, pa = d.Close.shift(), d.Adj_Close.shift()
    if "Prior_Close" in d:
        pc = pc.fillna(d.Prior_Close)
        pa = pa.fillna(d.Prior_Adj_Close)
    f = d.Adj_Close / d.Close
    ao = d.Open * f
    return pd.DataFrame(
        dict(
            rN=ao / pa - 1,
            rD=d.Close / d.Open - 1,
            rC=d.Adj_Close / pa - 1,
            cash_rN=(d.Open + d.Dividends + d.get("Capital_Gains", 0)) / pc - 1,
            prev_close=pc,
            prev_adj_close=pa,
            factor=f,
            adjusted_open=ao,
        )
    )


def audit():
    OUT.mkdir(parents=True, exist_ok=True)
    schedule = mcal.get_calendar("NYSE").schedule("2006-11-01", CONFIG["sample_end"])
    schedule.to_csv(OUT / "exchange_schedule.csv", index_label="Date")
    expected = schedule.loc[CONFIG["sample_start"] : CONFIG["sample_end"]].index
    checks = []
    manifest = []
    actions = []
    anomalies = []
    reconciliation = []
    warmup = []
    for t in TICKERS:
        d = raw(t)
        r = reconstructed(d)
        s = d[d.in_sample]
        c = dict(
            ticker=t,
            raw_rows=len(d),
            sample_rows=len(s),
            start=str(s.Date.min().date()),
            end=str(s.Date.max().date()),
            duplicate_dates=int(d.Date.duplicated().sum()),
            nonpositive_prices=int(
                (d[["Open", "High", "Low", "Close", "Adj_Close"]] <= 0).sum().sum()
            ),
            missing_calendar_dates=len(expected.difference(s.Date)),
            extra_calendar_dates=len(pd.DatetimeIndex(s.Date).difference(expected)),
            max_identity_error=float(abs((1 + r.rN) * (1 + r.rD) - (1 + r.rC)).max()),
            previous_same_session_signals_rebuildable=bool(
                r.loc[d.Date < CONFIG["sample_start"], ["rN", "rD"]]
                .iloc[-1]
                .notna()
                .all()
            ),
        )
        assert d.Date.is_monotonic_increasing and c["sample_rows"] == 4776
        assert not any(
            c[k]
            for k in [
                "duplicate_dates",
                "nonpositive_prices",
                "missing_calendar_dates",
                "extra_calendar_dates",
            ]
        )
        assert (
            c["max_identity_error"] < 1e-12
            and c["previous_same_session_signals_rebuildable"]
        )
        for field, cache in [
            ("rN", "overnight_adjusted_return"),
            ("rD", "daytime_return"),
            ("rC", "close_to_close_adjusted_return"),
        ]:
            diff = d[cache] - r[field]
            c["max_cached_difference_" + field] = float(abs(diff).max())
            c["sign_mismatches_" + field] = int(
                (
                    (np.sign(d[cache]) != np.sign(r[field]))
                    & d[cache].notna()
                    & r[field].notna()
                ).sum()
            )
            for i in d.index:
                reconciliation.append(
                    dict(
                        ticker=t,
                        Date=d.Date[i],
                        field=field,
                        cached=d[cache][i],
                        reconstructed=r[field][i],
                        difference=diff[i],
                        usable=bool(pd.notna(r[field][i])),
                    )
                )
            assert abs(diff).max() < 1e-12
        flags = (
            d.anomaly_flag.fillna(False)
            | (d.Volume <= 0)
            | (r[["rN", "rD", "rC"]].abs().max(axis=1) >= 0.1)
        )
        for i in d.index[flags]:
            row = d.loc[i].to_dict()
            row.update(
                ticker=t,
                independent_check_status="not_independently_verified",
                kept=True,
            )
            anomalies.append(row)
        for i in d.index[
            (d.Dividends != 0)
            | (d.Stock_Splits != 0)
            | (d.get("Capital_Gains", 0) != 0)
        ]:
            row = d.loc[
                i,
                [
                    "Date",
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Adj_Close",
                    "Dividends",
                    "Stock_Splits",
                ],
            ].to_dict()
            row.update(
                ticker=t,
                previous_close=r.prev_close[i],
                previous_adj_close=r.prev_adj_close[i],
                adjustment_factor=r.factor[i],
                adjusted_overnight=r.rN[i],
                cash_distribution_overnight=r.cash_rN[i],
                difference_bps=(r.rN[i] - r.cash_rN[i]) * 1e4,
                capital_gains=d.get("Capital_Gains", pd.Series(0, index=d.index))[i],
                split_treatment="already_split_adjusted_OHLC_no_second_adjustment",
                distribution_treatment="signed_cash_at_ex_open_declared_settlement_scenario",
            )
            actions.append(row)
        if "Prior_Close" in d:
            f = d.iloc[0]
            warmup.append(
                dict(
                    ticker=t,
                    first_row=str(f.Date.date()),
                    prior_date=f.Prior_session_date,
                    stored_prior_close=f.Prior_Close,
                    stored_prior_adj_close=f.Prior_Adj_Close,
                    reconstructed_first_rN=r.rN.iloc[0],
                    cached_first_rN=f.overnight_adjusted_return,
                    status="reconstructed_from_preserved_raw_metadata",
                    independent_source=False,
                )
            )
        checks.append(c)
        manifest.append(
            dict(
                ticker=t,
                source_filename=source_path(t).name,
                sha256=sha256(source_path(t)),
                source="Provided Yahoo daily data; actual historical download timestamp unavailable",
                original_download_timestamp="unknown_not_preserved",
                source_fields=list(d.columns),
                raw_rows=len(d),
                sample_rows=len(s),
                sample_start=c["start"],
                sample_end=c["end"],
                download_parameters={
                    "auto_adjust": False,
                    "actions": True,
                    "repair": False,
                    "end_exclusive": "2026-01-01",
                },
                calendar="NYSE core sessions proxy for NYSE Arca",
                calendar_version=mcal.__version__,
                price_units="split_adjusted_not_distribution_adjusted",
                independent_vendor_validation="not_verified",
                signal_precision="original_pandas_default_parser_frozen_cached_returns",
            )
        )
    for name, rows in [
        ("data_checks", checks),
        ("corporate_action_audit", actions),
        ("anomaly_audit", anomalies),
        ("warmup_checks", warmup),
    ]:
        pd.DataFrame(rows).to_csv(OUT / f"{name}.csv", index=False)
    pd.DataFrame(reconciliation).to_parquet(
        OUT / "return_reconciliation.parquet", compression="zstd", index=False
    )
    json_write(OUT / "data_manifest.json", manifest)
    return checks


def inputs(t, start=None, end=None, price_mode="cash"):
    e = engine()
    d = raw(t)
    sample = d[d.in_sample].copy()
    if start is not None:
        sample = sample[sample.Date >= start]
    if end is not None:
        sample = sample[sample.Date <= end]
    idx = sample.index.to_numpy()
    assert idx[0] > 0
    pre = d.iloc[idx[0] - 1]
    rn = sample.overnight_adjusted_return.to_numpy()
    rd = sample.daytime_return.to_numpy()
    z = np.zeros((2 * len(sample) + 1, 25))
    for j, (n, day) in enumerate(STRATS):
        z[:-1:2, j] = e.positions(n, rn, pre.overnight_adjusted_return)
        z[1:-1:2, j] = e.positions(day, rd, pre.daytime_return)
    schedule = pd.read_csv(
        OUT / "exchange_schedule.csv",
        index_col="Date",
        parse_dates=["Date", "market_open", "market_close"],
    )
    times = [schedule.loc[pre.Date, "market_close"]]
    for date in sample.Date:
        times.extend(
            [schedule.loc[date, "market_open"], schedule.loc[date, "market_close"]]
        )
    ti = pd.DatetimeIndex(times)
    p = np.empty(2 * len(sample) + 1)
    p[0] = pre.Close
    p[1::2] = sample.Open
    p[2::2] = sample.Close
    div = np.zeros(len(p))
    div[1::2] = (sample.Dividends + sample.get("Capital_Gains", 0)).to_numpy()
    if price_mode == "index":
        p[0] = pre.Adj_Close
        p[1::2] = sample.adjusted_open
        p[2::2] = sample.Adj_Close
        div[:] = 0
    dates = np.empty(len(p), dtype="datetime64[ns]")
    dates[-1] = np.datetime64("NaT")
    dates[:-1:2] = d.Date.iloc[idx - 1].values
    dates[1:-1:2] = d.Date.iloc[idx - 1].values
    avail = []
    for i in idx:
        avail.extend(
            [
                schedule.loc[d.Date.iloc[i - 1], "market_open"],
                schedule.loc[d.Date.iloc[i - 1], "market_close"],
            ]
        )
    avail.append(ti[-1])
    ai = pd.DatetimeIndex(avail)
    assert np.all(ai.asi8 <= ti.asi8)
    return dict(
        sample=sample,
        prices=p,
        targets=z,
        distributions=div,
        time_days=ti.asi8.astype(float) / (86400 * 1e9),
        timestamps=ti,
        signal_dates=dates,
        signal_available=ai,
        lagN0=float(pre.overnight_adjusted_return),
        lagD0=float(pre.daytime_return),
    )
