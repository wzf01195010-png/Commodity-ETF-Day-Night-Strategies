#!/usr/bin/env python3
"""Extend the existing 25-strategy commodity ETF study to GLD, SLV and USO.

Inputs: the six untouched data/*_daily.csv files, the existing
results/backtest_summary.csv, data.py and backtest.py. On the first run, fetch
GLD/SLV/USO from Yahoo Finance using data.py (interval=1d,
auto_adjust=False, actions=True). Later runs reuse the three frozen CSVs in
results/commodity_etf_9assets_2007_2025/input_data/. Use --refresh-data to
download the three new funds again. No original six-ETF file is rewritten.

Outputs: one 675-row master CSV, one 225-row compact CSV, nine 25-row ETF
CSVs, one nine-row best-versus-buy-and-hold CSV, and the three new-fund data
CSVs, all inside results/commodity_etf_9assets_2007_2025/.

Install: python -m pip install numpy pandas yfinance pandas_market_calendars
Run:     python extend_9_etfs.py
         python extend_9_etfs.py --refresh-data  # optional new Yahoo snapshot

The common initial close is 2007-01-08; evaluation runs 2007-01-09 through
2025-12-31. Earlier downloaded bars are used only to calculate the known
2007-01-08 overnight signal. The saved new-fund data start 2007-01-08 and
include that date's actual previous-close values as metadata so the first
signal can be independently recomputed without inventing an earlier bar.

This script delegates all 25 positions, fees, compounding and risk metrics to
the unchanged backtest.py engine. Its target-exposure short simplification,
252-session annualization, zero risk-free rate, initial/final fees and opening/
closing wealth drawdown observations therefore match the six-fund analysis.
The 0-bp best strategy is selected ex post from the full sample.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

import numpy as np
import pandas as pd

import backtest as bt
import data as source


ROOT = Path(__file__).resolve().parent
BASE = ROOT / "results"
DEST = BASE / "commodity_etf_9assets_2007_2025"
OLD_TICKERS = bt.TICKERS
NEW_TICKERS = ("GLD", "SLV", "USO")
ALL_TICKERS = OLD_TICKERS + NEW_TICKERS
INITIAL_DATE = pd.Timestamp("2007-01-08")
FIRST_DATE = pd.Timestamp("2007-01-09")
LAST_DATE = pd.Timestamp("2025-12-31")
MASTER_NAME = "commodity_etf_9assets_25strategies_full_results_2007_2025.csv"
COMPACT_NAME = "commodity_etf_9assets_25strategy_summary_2007_2025.csv"
BEST_NAME = "commodity_etf_best_strategy_vs_BH_0bps.csv"
METRICS = ("Final_wealth", "CAGR", "Annualized_volatility",
           "Max_drawdown", "Sharpe_ratio", "Turnover_units", "Total_fees_paid")


def published_hashes() -> dict[Path, str]:
    """Snapshot the original six inputs and all seven published result files."""
    files = [ROOT / "data" / f"{t}_daily.csv" for t in OLD_TICKERS]
    files += [BASE / name for name in bt.RESULT_FILES]
    missing = [str(p) for p in files if not p.is_file()]
    if missing:
        raise FileNotFoundError("Missing existing project files: " + "; ".join(missing))
    return {p: bt.file_hash(p) for p in files}


def unchanged(snapshot: dict[Path, str]) -> None:
    for path, earlier in snapshot.items():
        if not path.is_file() or bt.file_hash(path) != earlier:
            raise RuntimeError(f"Original six-ETF file changed: {path}")


def calendar_dates(schedule: pd.DataFrame) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(schedule.index).tz_localize(None)


def download_and_store(ticker: str, schedule: pd.DataFrame, path: Path) -> None:
    """Use existing data.py QA, then trim actual bars to the requested Jan 8."""
    dates = calendar_dates(schedule)
    raw = source.download(ticker, source.DOWNLOAD_START, source.DOWNLOAD_END)
    source.validate_raw(ticker, raw, dates)
    full = source.add_returns(raw, dates)
    # data.py prints every flagged record. Keep the console report compact; its
    # flags/review outcome are retained in the saved CSV and errors still fail.
    with contextlib.redirect_stdout(io.StringIO()):
        full = source.review_anomalies(ticker, full, dates)
    prior_date = dates[dates.get_loc(INITIAL_DATE) - 1]
    if prior_date != pd.Timestamp("2007-01-05"):
        raise ValueError(f"Unexpected previous exchange session: {prior_date}")
    trimmed = full.loc[INITIAL_DATE:LAST_DATE].copy()
    if not trimmed.index.equals(dates[dates >= INITIAL_DATE]):
        raise ValueError(f"{ticker}: missing common-sample source dates")
    # These are metadata for a REAL earlier close, not a fabricated price row.
    # Jan 8 overnight was already calculated from Jan 5 before truncation.
    trimmed["Prior_session_date"] = ""
    trimmed["Prior_Close"] = np.nan
    trimmed["Prior_Adj_Close"] = np.nan
    trimmed.loc[INITIAL_DATE, "Prior_session_date"] = prior_date.strftime("%Y-%m-%d")
    trimmed.loc[INITIAL_DATE, "Prior_Close"] = full.loc[prior_date, "Close"]
    trimmed.loc[INITIAL_DATE, "Prior_Adj_Close"] = full.loc[prior_date, "Adj_Close"]
    columns = source.RAW_COLUMNS.copy()
    if "Capital_Gains" in trimmed:
        columns.append("Capital_Gains")
    columns += ["adjustment_factor", "adjusted_open", *source.RETURN_COLUMNS,
                "in_sample", "anomaly_flag", "anomaly_reason", "anomaly_review",
                "Prior_session_date", "Prior_Close", "Prior_Adj_Close"]
    path.parent.mkdir(parents=True, exist_ok=True)
    trimmed[columns].to_csv(path, index=True, date_format="%Y-%m-%d",
                            float_format="%.17g", na_rep="")


def read_new_input(ticker: str, schedule: pd.DataFrame, path: Path) -> pd.DataFrame:
    """Validate frozen trimmed data and recompute every saved return."""
    if not path.is_file():
        raise FileNotFoundError(f"Missing new-fund input: {path}")
    frame = pd.read_csv(path)
    needed = set(bt.REQUIRED_COLUMNS) | {
        "close_to_close_adjusted_return", "adjustment_factor", "anomaly_flag",
        "anomaly_reason", "anomaly_review", "Prior_session_date", "Prior_Close",
        "Prior_Adj_Close",
    }
    if missing := needed - set(frame.columns):
        raise ValueError(f"{ticker}: missing source columns {sorted(missing)}")
    text_dates = frame.Date.astype(str)
    if not text_dates.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        raise ValueError(f"{ticker}: Date is not YYYY-MM-DD")
    frame.index = pd.DatetimeIndex(pd.to_datetime(text_dates, format="%Y-%m-%d"))
    expected = calendar_dates(schedule)
    expected = expected[expected >= INITIAL_DATE]
    source.validate_raw(ticker, frame, expected)
    if not frame.index.equals(expected):
        raise ValueError(f"{ticker}: missing or extra exchange sessions")
    flags = frame.in_sample.astype(str).str.lower().map(
        {"true": True, "false": False, "1": True, "0": False})
    expected_flags = frame.index >= FIRST_DATE
    if flags.isna().any() or not np.array_equal(flags, expected_flags):
        raise ValueError(f"{ticker}: invalid in_sample flags")
    frame["in_sample"] = expected_flags
    numeric = [*bt.PRICE_COLUMNS, "adjustment_factor", "adjusted_open",
               *source.RETURN_COLUMNS]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    if not np.isfinite(frame[numeric].to_numpy(dtype=float)).all():
        raise ValueError(f"{ticker}: nonfinite price/return in saved input")
    prev_date = str(frame.iloc[0].Prior_session_date)
    expected_prev = calendar_dates(schedule)[calendar_dates(schedule).get_loc(INITIAL_DATE) - 1]
    if prev_date != expected_prev.strftime("%Y-%m-%d"):
        raise ValueError(f"{ticker}: missing genuine Jan 5 previous-close metadata")
    prior_close = float(frame.iloc[0].Prior_Close)
    prior_adj = float(frame.iloc[0].Prior_Adj_Close)
    if not np.isfinite([prior_close, prior_adj]).all() or min(prior_close, prior_adj) <= 0:
        raise ValueError(f"{ticker}: invalid previous-close metadata")
    if frame.Prior_session_date.iloc[1:].notna().any() or frame.Prior_Close.iloc[1:].notna().any() \
            or frame.Prior_Adj_Close.iloc[1:].notna().any():
        raise ValueError(f"{ticker}: previous-close metadata must appear only on Jan 8")
    factor = frame.Adj_Close / frame.Close
    adjusted_open = frame.Open * factor
    prev_close = np.r_[prior_close, frame.Close.to_numpy()[:-1]]
    prev_adj = np.r_[prior_adj, frame.Adj_Close.to_numpy()[:-1]]
    checks = {
        "adjustment_factor": factor,
        "adjusted_open": adjusted_open,
        "daytime_return": frame.Close / frame.Open - 1,
        "overnight_price_return": frame.Open.to_numpy() / prev_close - 1,
        "overnight_adjusted_return": adjusted_open.to_numpy() / prev_adj - 1,
        "close_to_close_adjusted_return": frame.Adj_Close.to_numpy() / prev_adj - 1,
    }
    for name, target in checks.items():
        bt.require_close(frame[name].to_numpy(dtype=float), np.asarray(target, dtype=float),
                         f"{ticker} saved {name}")
    composed = ((1 + frame.daytime_return.to_numpy())
                * (1 + frame.overnight_adjusted_return.to_numpy()) - 1)
    bt.require_close(composed, frame.close_to_close_adjusted_return.to_numpy(),
                     f"{ticker} adjusted close composition")
    if not frame.anomaly_flag.astype(str).str.lower().isin(("true", "false", "1", "0")).all():
        raise ValueError(f"{ticker}: invalid anomaly flags")
    if not frame.loc[frame.anomaly_flag.astype(str).str.lower().isin(("true", "1")),
                     "anomaly_review"].str.startswith("yahoo_window_consistent").all():
        raise ValueError(f"{ticker}: unrechecked anomalous records")
    if ticker == "SLV":
        # Its 2008-07-24 10-for-1 split is documented in the issuer's SEC
        # filing. Yahoo's earlier OHLC is already split-adjusted.
        # https://www.sec.gov/Archives/edgar/data/1330568/000119312508149627/dex991.htm
        split = float(frame.loc["2008-07-24", "Stock_Splits"])
        ratio = (frame.loc["2008-07-24", "Adj_Close"]
                 / frame.loc["2008-07-23", "Adj_Close"])
        if not np.isclose(split, 10.0) or not 0.5 < ratio < 1.5:
            raise ValueError(f"SLV split check failed: marker={split}, adjusted ratio={ratio}")
    if ticker == "USO":
        # The issuer's SEC filing documents a 1-for-8 reverse split after
        # 2020-04-28 close. Yahoo records factor 0.125 on 2020-04-29.
        # Its earlier OHLC bars are already split-adjusted: DO NOT apply 8x.
        # https://www.sec.gov/Archives/edgar/data/1327068/000117120020000310/i20281_uso-8k.htm
        split = float(frame.loc["2020-04-29", "Stock_Splits"])
        ratio = (frame.loc["2020-04-29", "Adj_Close"]
                 / frame.loc["2020-04-28", "Adj_Close"])
        if not np.isclose(split, 0.125) or not 0.5 < ratio < 1.5:
            raise ValueError(f"USO split check failed: marker={split}, adjusted ratio={ratio}")
    frame.attrs["source_sha256"] = bt.file_hash(path)
    return frame


def print_quality(ticker: str, frame: pd.DataFrame) -> None:
    flagged = frame.anomaly_flag.astype(str).str.lower().isin(("true", "1"))
    zero = frame.Volume == 0
    split = frame.Stock_Splits != 0
    dividends = frame.Dividends != 0
    sample = frame.loc[frame.in_sample]
    print(f"DATA {ticker}: stored={frame.index[0].date()}..{frame.index[-1].date()} "
          f"({len(frame)} rows), evaluated={sample.index[0].date()}.."
          f"{sample.index[-1].date()} ({len(sample)} sessions); "
          f"missing=0 duplicates=0 nonpositive/OHLC=0 "
          f"zero_volume={int(zero.sum())} anomalies={int(flagged.sum())} "
          f"splits={int(split.sum())} dividends={int(dividends.sum())}", flush=True)
    if flagged.any():
        print(f"  Reviewed anomaly dates: "
              f"{', '.join(frame.index[flagged].strftime('%Y-%m-%d')[:10])}"
              f"{' ...' if flagged.sum() > 10 else ''}", flush=True)
    if split.any():
        print("  Split markers: " + ", ".join(
            f"{d.date()}={r:g}" for d, r in frame.loc[split, "Stock_Splits"].items()), flush=True)
    if zero.any():
        print("  Zero-volume execution remains unverified: "
              + ", ".join(frame.index[zero].strftime("%Y-%m-%d")), flush=True)


def compare_old(old: pd.DataFrame, recomputed: pd.DataFrame,
                inputs: dict[str, pd.DataFrame]) -> None:
    keys = ["Ticker", "Strategy", "Cost_bps"]
    if len(old) != 450 or old.duplicated(keys).any():
        raise ValueError("Existing six-ETF summary is incomplete or duplicated")
    for ticker in OLD_TICKERS:
        stored = old.loc[old.Ticker == ticker, "Source_data_sha256"]
        if not stored.eq(inputs[ticker].attrs["source_sha256"]).all():
            raise ValueError(f"{ticker}: source file no longer matches saved six-ETF results")
    a, b = old.set_index(keys).sort_index(), recomputed.set_index(keys).sort_index()
    if not a.index.equals(b.index):
        raise ValueError("The original six-ETF strategy keys changed")
    differences = {}
    for field in METRICS:
        x, y = a[field].to_numpy(dtype=float), b[field].to_numpy(dtype=float)
        finite = np.isfinite(x) & np.isfinite(y)
        differences[field] = float(np.max(np.abs(x[finite] - y[finite]))) if finite.any() else np.nan
    print("SIX-ETF COMPARISON, maximum absolute differences: "
          + ", ".join(f"{k}={v:.3g}" for k, v in differences.items()), flush=True)
    try:
        bt.compare_existing(old, recomputed, keys, "original six ETF results")
    except Exception:
        for field in METRICS:
            x, y = a[field].to_numpy(dtype=float), b[field].to_numpy(dtype=float)
            mismatch = ~np.isclose(x, y, rtol=1e-9, atol=1e-10, equal_nan=True)
            if mismatch.any():
                print(f"Mismatch in {field}: "
                      f"{list(zip(a.index[mismatch][:5].tolist(), x[mismatch][:5], y[mismatch][:5]))}",
                      file=sys.stderr, flush=True)
        print("Source hashes and dates above identify whether data changed; "
              "the original outputs have not been replaced.", file=sys.stderr)
        raise


def run_all(inputs: dict[str, pd.DataFrame], schedule: pd.DataFrame,
            old: pd.DataFrame) -> pd.DataFrame:
    results = []
    sample_dates = calendar_dates(schedule)
    sample_dates = sample_dates[(sample_dates >= FIRST_DATE) & (sample_dates <= LAST_DATE)]
    for ticker in ALL_TICKERS:
        frame = inputs[ticker]
        actual = frame.index[frame.in_sample]
        if not actual.equals(sample_dates) or frame.index[frame.index.get_loc(actual[0]) - 1] != INITIAL_DATE:
            raise ValueError(f"{ticker}: evaluation or initial price date differs")
        for day, night in bt.STRATEGIES:
            for cost in bt.COSTS_BPS:
                summary, curve = bt.run_strategy(ticker, frame, schedule, day, night, cost)
                bt.verify_curve(frame, curve, summary["Strategy"], cost)
                results.append(summary)
        print(f"BACKTEST {ticker}: 25 strategies x 3 costs passed", flush=True)
        if ticker == OLD_TICKERS[-1]:
            compare_old(old, pd.DataFrame(results), inputs)
    return pd.DataFrame(results).sort_values(
        ["Ticker", "Strategy", "Cost_bps"], kind="stable").reset_index(drop=True)


def validate_master(master: pd.DataFrame, inputs: dict[str, pd.DataFrame]) -> None:
    keys = ["Ticker", "Strategy", "Cost_bps"]
    if len(master) != 675 or master.duplicated(keys).any() or set(master.Ticker) != set(ALL_TICKERS):
        raise ValueError("Master result must have nine tickers and 675 unique rows")
    bt.validate_panel(master, ["Ticker", "Cost_bps"])
    if not master.groupby(["Ticker", "Strategy"]).Cost_bps.apply(
            lambda x: set(x) == {0, 1, 2}).all():
        raise ValueError("Every strategy must have costs 0, 1 and 2")
    if set(master.Strategy) != set(bt.STRATEGY_NAMES):
        raise ValueError("Incorrect 25-strategy registry")
    if not master.Start_date.eq("2007-01-09").all() or not master.End_date.eq("2025-12-31").all():
        raise ValueError("Non-common evaluation period")
    if not master.Initial_date.eq("2007-01-08").all() or not master.Trading_days.eq(4776).all():
        raise ValueError("Non-common initial close or missing trading days")
    if not master.Initial_wealth.eq(100).all() or not master.Annualization_days.eq(252).all() \
            or not master.Risk_free_rate.eq(0).all():
        raise ValueError("Core wealth/annualization assumptions changed")
    max_decomposition_error = 0.0
    nonmonotonic = []
    for ticker in ALL_TICKERS:
        fund = master.loc[master.Ticker == ticker].set_index(["Strategy", "Cost_bps"])
        frame = inputs[ticker]
        bh = fund.loc[("Long/Long", 0), "Final_wealth"]
        normalized = (100 * frame.loc[LAST_DATE, "Adj_Close"]
                      / frame.loc[INITIAL_DATE, "Adj_Close"])
        np.testing.assert_allclose(bh, normalized, rtol=1e-9, atol=1e-10)
        for day, night in bt.STRATEGIES:
            name = f"{day}/{night}"
            wealth = [float(fund.loc[(name, cost), "Final_wealth"]) for cost in bt.COSTS_BPS]
            for low, high in zip(wealth, wealth[1:]):
                if high > low + 1e-9 * max(1.0, abs(low), abs(high)):
                    nonmonotonic.append((ticker, name, low, high,
                                         list(fund.loc[name, "Status"])))
            lhs = wealth[0]
            rhs = (fund.loc[(f"{day}/Cash", 0), "Final_wealth"]
                   * fund.loc[(f"Cash/{night}", 0), "Final_wealth"] / 100)
            error = abs(lhs - rhs)
            max_decomposition_error = max(max_decomposition_error, error)
            np.testing.assert_allclose(lhs, rhs, rtol=1e-9, atol=1e-8,
                                       err_msg=f"{ticker} {name} session decomposition")
    print(f"0-bp multiplicative day/night decomposition: "
          f"maximum absolute wealth error = {max_decomposition_error:.12g}", flush=True)
    if nonmonotonic:
        print("WARNING: higher-cost terminal wealth exceeded lower-cost wealth:",
              nonmonotonic[:10], file=sys.stderr, flush=True)
        # A nonpositive-wealth algebraic path may invert this ordering; those
        # cases require a separate economic interpretation and remain marked.
        if any(all(status == "OK" for status in item[4]) for item in nonmonotonic):
            raise ValueError("Unexplained cost monotonicity violation on a valid wealth path")
    else:
        print("Cost monotonicity: all 225 ETF-strategy profiles pass", flush=True)


def compact_table(master: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (ticker, strategy), group in master.groupby(["Ticker", "Strategy"], sort=True):
        by_cost = group.set_index("Cost_bps")
        if set(by_cost.index) != {0, 1, 2}:
            raise ValueError(f"Missing costs for {ticker} {strategy}")
        rows.append({
            "Ticker": ticker, "Strategy": strategy,
            **{f"Final_wealth_{c}bps": by_cost.loc[c, "Final_wealth"] for c in (0, 1, 2)},
            "CAGR_0bps": by_cost.loc[0, "CAGR"],
            "Max_drawdown_0bps": by_cost.loc[0, "Max_drawdown"],
            "Annualized_volatility_0bps": by_cost.loc[0, "Annualized_volatility"],
            "Sharpe_ratio_0bps": by_cost.loc[0, "Sharpe_ratio"],
            "Turnover_units_0bps": by_cost.loc[0, "Turnover_units"],
            "Benchmark_Flag": ("Buy-and-Hold" if strategy == "Long/Long" else
                               "Cash" if strategy == "Cash/Cash" else "Strategy"),
        })
    result = pd.DataFrame(rows)
    if len(result) != 225 or result.duplicated(["Ticker", "Strategy"]).any():
        raise ValueError("Compact table must contain 225 unique rows")
    return result


def best_table(master: pd.DataFrame) -> pd.DataFrame:
    rows = []
    zero = master.loc[master.Cost_bps == 0]
    for ticker in ALL_TICKERS:
        fund = zero.loc[zero.Ticker == ticker]
        best = fund.loc[fund.Final_wealth.idxmax()]
        bh = fund.loc[fund.Strategy == "Long/Long"].iloc[0]
        rows.append({
            "Ticker": ticker,
            "Best_Strategy_0bps": best.Strategy,
            "Best_Strategy_Final_Wealth_0bps": best.Final_wealth,
            "Best_Strategy_CAGR_0bps": best.CAGR,
            "Best_Strategy_MDD_0bps": best.Max_drawdown,
            "Best_Strategy_Volatility_0bps": best.Annualized_volatility,
            "Best_Strategy_Sharpe_0bps": best.Sharpe_ratio,
            "BH_Final_Wealth_0bps": bh.Final_wealth,
            "BH_CAGR_0bps": bh.CAGR,
            "BH_MDD_0bps": bh.Max_drawdown,
            "BH_Volatility_0bps": bh.Annualized_volatility,
            "BH_Sharpe_0bps": bh.Sharpe_ratio,
            "Wealth_Ratio_Best_to_BH": best.Final_wealth / bh.Final_wealth,
            "Selection": "EX_POST_FULL_SAMPLE_MAX_FINAL_WEALTH",
        })
    result = pd.DataFrame(rows).sort_values("Ticker").reset_index(drop=True)
    if len(result) != 9 or result.Ticker.nunique() != 9:
        raise ValueError("Best-versus-buy-and-hold table must have nine tickers")
    return result


def write_outputs(folder: Path, master: pd.DataFrame,
                  compact: pd.DataFrame, best: pd.DataFrame) -> None:
    master.to_csv(folder / MASTER_NAME, index=False, float_format="%.17g", na_rep="NaN")
    compact.to_csv(folder / COMPACT_NAME, index=False, float_format="%.17g", na_rep="NaN")
    best.to_csv(folder / BEST_NAME, index=False, float_format="%.17g", na_rep="NaN")
    for ticker in ALL_TICKERS:
        compact.loc[compact.Ticker == ticker].to_csv(
            folder / f"{ticker}_25_strategies_2007_2025.csv", index=False,
            float_format="%.17g", na_rep="NaN")
    if len(pd.read_csv(folder / MASTER_NAME)) != 675 \
            or len(pd.read_csv(folder / COMPACT_NAME)) != 225 \
            or len(pd.read_csv(folder / BEST_NAME)) != 9:
        raise ValueError("Output CSV row counts changed upon writing")
    for ticker in ALL_TICKERS:
        if len(pd.read_csv(folder / f"{ticker}_25_strategies_2007_2025.csv")) != 25:
            raise ValueError(f"{ticker}: individual CSV does not have 25 rows")
    expected = {MASTER_NAME, COMPACT_NAME, BEST_NAME}
    expected |= {f"{t}_25_strategies_2007_2025.csv" for t in ALL_TICKERS}
    if {p.name for p in folder.glob("*.csv")} != expected:
        raise ValueError("New output folder has a missing/unexpected result CSV")


def publish(folder: Path, temp_root: Path) -> None:
    backup = temp_root / "previous_generation"
    if DEST.exists():
        os.replace(DEST, backup)
    try:
        os.replace(folder, DEST)
    except BaseException:
        if backup.exists():
            os.replace(backup, DEST)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-data", action="store_true",
                        help="Download a new Yahoo snapshot for GLD, SLV and USO")
    args = parser.parse_args()
    snapshot = published_hashes()
    schedule = bt.calendar_schedule()
    old = pd.read_csv(BASE / "backtest_summary.csv")
    inputs = {ticker: bt.read_and_validate(ticker, schedule) for ticker in OLD_TICKERS}
    # Recompute and compare the six BEFORE changing even the new output folder.
    # run_all does the comparison after its sixth ticker and before GLD begins.
    reuse = (not args.refresh_data and DEST.is_dir()
             and all((DEST / "input_data" / f"{t}_daily.csv").is_file()
                     for t in NEW_TICKERS))
    if DEST.exists() and not reuse and not args.refresh_data:
        raise ValueError("Existing extension lacks a complete frozen input set; "
                         "use --refresh-data after inspecting it")
    with tempfile.TemporaryDirectory(prefix=".commodity9-", dir=BASE) as temp:
        temporary = Path(temp)
        folder = temporary / "new_generation"
        data_folder = folder / "input_data"
        data_folder.mkdir(parents=True)
        for ticker in NEW_TICKERS:
            path = data_folder / f"{ticker}_daily.csv"
            if reuse:
                shutil.copy2(DEST / "input_data" / path.name, path)
            else:
                print(f"Downloading and checking {ticker} from Yahoo...", flush=True)
                download_and_store(ticker, schedule, path)
            frame = read_new_input(ticker, schedule, path)
            inputs[ticker] = frame
            print_quality(ticker, frame)
        master = run_all(inputs, schedule, old)
        validate_master(master, inputs)
        compact = compact_table(master)
        best = best_table(master)
        write_outputs(folder, master, compact, best)
        unchanged(snapshot)
        publish(folder, temporary)
    unchanged(snapshot)
    print("ETF | Best Strategy 0bps | Best Final Wealth | BH Final Wealth | Difference")
    for row in best.itertuples():
        difference = row.Best_Strategy_Final_Wealth_0bps - row.BH_Final_Wealth_0bps
        print(f"{row.Ticker} | {row.Best_Strategy_0bps} | "
              f"{row.Best_Strategy_Final_Wealth_0bps:.2f} | "
              f"{row.BH_Final_Wealth_0bps:.2f} | {difference:+.2f}")
    print("TOTAL: 9 ETFs; 25 strategies; 225 ETF-strategy pairs; "
          "675 strategy-cost observations; 2007-01-09..2025-12-31 "
          "(initial close 2007-01-08).")
    print(f"Published: {DEST}; original six data/result files unchanged.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"EXTENSION FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
