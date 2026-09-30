#!/usr/bin/env python3
"""Download and validate six commodity ETFs; calculate daytime/overnight returns.

Input: Yahoo Finance via yfinance, daily bars from 2006-12-01 (inclusive) to
2026-01-01 (exclusive). Requested research years: 2007-2025. Five funds first
traded on 2007-01-05; their first two bars supply lagged overnight history.
The common evaluable sample is 2007-01-09 through 2025-12-31. DBC retains
December 2006 warmup; pre-inception dates for the other funds are not missing
observations and are never fabricated.
Output: data/{DBA,DBB,DBC,DBE,DBO,DBP}_daily.csv beside this script. Console QA
only; no log, chart, report, or separate warmup file is created.
Install (Python 3.10+):
    python -m pip install numpy pandas yfinance pandas_market_calendars
Run from any directory:
    python /path/to/data.py

Methods/assumptions:
* NYSE regular-session calendar applies to these NYSE Arca ETFs, including
  extraordinary closures and early closes. Daily labels are exchange-local
  dates, never UTC-midnight timestamps. Any real timestamp conversion uses
  America/New_York. Early-close days retain Yahoo's actual daily Close.
* Prices are never filled, observations fabricated, or outliers deleted.
  Missing exchange sessions fail validation. Overnight calculations also
  explicitly require consecutive exchange sessions, including across weekends.
* auto_adjust=False, actions=True, repair=False. Yahoo's historical OHLC already
  accounts for splits; Stock_Splits is informational and is NOT applied again.
* adjusted_open = Open * Adj_Close / Close. Daytime return is Close/Open-1;
  adjusted overnight is adjusted_open/previous Adj_Close-1. Their product
  exactly matches the adjusted close-to-close gross return.
* Adjusted prices are retrospective, distribution-adjusted return indices,
  not executable opening prices or a cash dividend ledger. The backtest uses
  this consistent synthetic total-return convention, without adding Dividends
  again. An actual share/cash account (especially short dividend obligations)
  can differ. Price-only overnight is also retained for comparison.
* Absolute leg/close-to-close moves >=10%, intraday high/low range >=20%, and
  adjustment-factor changes not explained by recorded actions are flagged.
  Zero-volume provider bars are also rechecked and retained with an explicit
  execution-unverified warning, not treated as evidence of executable trades.
  Flagged observations are re-requested in overlapping short Yahoo windows,
  checked against OHLC and actions, retained, and marked in the CSV. A match
  corroborates Yahoo's consistency, not an independent exchange-tape audit.
* Each request has at most three attempts. All six datasets must pass before
  the six output CSVs are written; a failure exits nonzero, never as success.

References:
https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html
https://pandas-market-calendars.readthedocs.io/en/latest/usage.html
https://www.nyse.com/markets/hours-calendars
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
import yfinance as yf


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TICKERS = ("DBA", "DBB", "DBC", "DBE", "DBO", "DBP")
DOWNLOAD_START = "2006-12-01"
DOWNLOAD_END = "2026-01-01"  # Yahoo end is exclusive.
SAMPLE_START = "2007-01-09"
SAMPLE_END = "2025-12-31"
# Inception/first-trading dates confirmed against Invesco's fund data and
# Yahoo's first bars. NYSE and the former AMEX share these session dates.
# https://www.sec.gov/Archives/edgar/data/1367306/000156459022006811/dbe-10k_20211231.htm
FIRST_TRADING_DATE = {ticker: "2007-01-05" for ticker in TICKERS}
FIRST_TRADING_DATE["DBC"] = "2006-02-03"
TIMEZONE = "America/New_York"
MAX_ATTEMPTS = 3
PRICE_COLUMNS = ["Open", "High", "Low", "Close", "Adj_Close"]
RAW_COLUMNS = PRICE_COLUMNS + ["Volume", "Dividends", "Stock_Splits"]
RETURN_COLUMNS = [
    "daytime_return", "overnight_price_return", "overnight_adjusted_return",
    "close_to_close_adjusted_return",
]


def download(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Bounded retries; preserve missing raw rows so QA can find them."""
    last_error = "unknown error"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            frame = yf.download(
                ticker, start=start, end=end, interval="1d", auto_adjust=False,
                actions=True, repair=False, keepna=True, prepost=False,
                threads=False, progress=False, multi_level_index=False,
                ignore_tz=True, timeout=30,
            )
            if frame is None or frame.empty:
                raise ValueError("Yahoo returned no observations")
            if isinstance(frame.columns, pd.MultiIndex):
                frame = frame.xs(ticker, axis=1, level=-1)
            frame = frame.rename(columns={
                "Adj Close": "Adj_Close", "Stock Splits": "Stock_Splits",
                "Capital Gains": "Capital_Gains",
            })
            missing = set(RAW_COLUMNS) - set(frame.columns)
            if missing:
                raise ValueError(f"Missing required Yahoo columns: {sorted(missing)}")
            dates = pd.DatetimeIndex(frame.index)
            if dates.tz is not None:
                # Only actual timezone-aware timestamps are converted. A naive
                # daily Date label is already an exchange date, not UTC.
                dates = dates.tz_convert(TIMEZONE).tz_localize(None)
            if not dates.equals(dates.normalize()):
                raise ValueError("Unexpected intraday time in daily date labels")
            frame.index = dates
            frame.index.name = "Date"
            return frame
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            print(f"{ticker} {start}..{end}: attempt {attempt}/{MAX_ATTEMPTS} "
                  f"failed: {last_error}", file=sys.stderr, flush=True)
            if attempt < MAX_ATTEMPTS:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"{ticker}: download failed after {MAX_ATTEMPTS} attempts; "
                       f"last error: {last_error}")


def date_list(index: pd.DatetimeIndex) -> str:
    return ", ".join(index.strftime("%Y-%m-%d"))


def validate_raw(ticker: str, frame: pd.DataFrame,
                 expected: pd.DatetimeIndex) -> None:
    """Require a complete exchange-calendar sample, including warmup."""
    if frame.index.hasnans:
        raise ValueError(f"{ticker}: missing date labels")
    if frame.index.has_duplicates:
        raise ValueError(f"{ticker}: duplicate dates: "
                         f"{date_list(frame.index[frame.index.duplicated()])}")
    if not frame.index.is_monotonic_increasing:
        raise ValueError(f"{ticker}: date rows are not sorted")
    missing = expected.difference(frame.index)
    extra = frame.index.difference(expected)
    if len(missing) or len(extra):
        raise ValueError(f"{ticker}: unexpected missing sessions=[{date_list(missing)}]; "
                         f"non-session/out-of-range rows=[{date_list(extra)}]. "
                         "No filling or stitching is allowed.")
    numeric = RAW_COLUMNS + (["Capital_Gains"] if "Capital_Gains" in frame else [])
    for column in numeric:
        values = pd.to_numeric(frame[column], errors="raise")
        bad = ~np.isfinite(values.to_numpy(dtype=float))
        if bad.any():
            raise ValueError(f"{ticker}: missing/nonfinite {column}: "
                             f"{date_list(frame.index[bad])}")
        frame[column] = values
    prices = frame[PRICE_COLUMNS]
    bad_price = (prices <= 0).any(axis=1)
    if bad_price.any():
        raise ValueError(f"{ticker}: nonpositive prices: "
                         f"{date_list(frame.index[bad_price])}")
    # Allow only float representation noise, never a material OHLC violation.
    tolerance = frame["High"].abs() * 1e-7
    bad_ohlc = (
        (frame["Low"] > frame["High"] + tolerance)
        | (frame[["Open", "Close"]].max(axis=1) > frame["High"] + tolerance)
        | (frame[["Open", "Close"]].min(axis=1) < frame["Low"] - tolerance)
    )
    if bad_ohlc.any():
        raise ValueError(f"{ticker}: OHLC relationship violations:\n"
                         f"{frame.loc[bad_ohlc, PRICE_COLUMNS].to_string()}")
    if (frame["Volume"] < 0).any() or (frame["Stock_Splits"] < 0).any():
        raise ValueError(f"{ticker}: negative volume or invalid split ratio")
    if not np.allclose(frame["Volume"], np.round(frame["Volume"]), atol=1e-8, rtol=0):
        raise ValueError(f"{ticker}: noninteger daily volume")


def add_returns(frame: pd.DataFrame, expected: pd.DatetimeIndex) -> pd.DataFrame:
    """Do not bridge an unexpected missing session even if called separately."""
    frame = frame.copy()
    ordinal = expected.get_indexer(frame.index)
    consecutive = np.zeros(len(frame), dtype=bool)
    consecutive[1:] = ((ordinal[1:] >= 0) & (ordinal[:-1] >= 0)
                       & (np.diff(ordinal) == 1))
    frame["adjustment_factor"] = frame["Adj_Close"] / frame["Close"]
    frame["adjusted_open"] = frame["Open"] * frame["adjustment_factor"]
    frame["daytime_return"] = frame["Close"] / frame["Open"] - 1.0
    frame["overnight_price_return"] = (
        frame["Open"] / frame["Close"].shift(1) - 1.0
    ).where(consecutive)
    frame["overnight_adjusted_return"] = (
        frame["adjusted_open"] / frame["Adj_Close"].shift(1) - 1.0
    ).where(consecutive)
    frame["close_to_close_adjusted_return"] = (
        frame["Adj_Close"] / frame["Adj_Close"].shift(1) - 1.0
    ).where(consecutive)
    frame["in_sample"] = ((frame.index >= SAMPLE_START) & (frame.index <= SAMPLE_END))
    valid = frame["close_to_close_adjusted_return"].notna()
    composed = ((1.0 + frame["overnight_adjusted_return"])
                * (1.0 + frame["daytime_return"]) - 1.0)
    np.testing.assert_allclose(
        composed[valid], frame.loc[valid, "close_to_close_adjusted_return"],
        rtol=1e-11, atol=1e-13,
        err_msg="Day/night composition does not equal adjusted close return",
    )
    if frame.loc[frame["in_sample"], RETURN_COLUMNS].isna().any().any():
        raise ValueError("Missing formal-sample returns; cannot run full-sample backtest")
    return frame


def review_anomalies(ticker: str, frame: pd.DataFrame,
                     expected: pd.DatetimeIndex) -> pd.DataFrame:
    """Preserve large moves and label overlapping-download consistency checks."""
    reasons = pd.Series("", index=frame.index, dtype=object)
    for column in RETURN_COLUMNS:
        mask = frame[column].abs() >= 0.10
        reasons.loc[mask] += column + ";"
    mask = frame["High"] / frame["Low"] - 1.0 >= 0.20
    reasons.loc[mask] += "intraday_range;"
    zero_volume = frame["Volume"] == 0
    reasons.loc[zero_volume] += "zero_volume;"
    factor_change = frame["adjustment_factor"] / frame["adjustment_factor"].shift(1) - 1
    recorded_action = (frame["Dividends"] != 0) | (frame["Stock_Splits"] != 0)
    if "Capital_Gains" in frame:
        recorded_action |= frame["Capital_Gains"] != 0
    unexplained = (factor_change.abs() > 1e-4) & ~recorded_action
    reasons.loc[unexplained] += "unexplained_adjustment_change;"
    frame["anomaly_flag"] = reasons != ""
    frame["anomaly_reason"] = reasons.str.rstrip(";")
    frame["anomaly_review"] = "not_flagged"
    flagged = frame.index[frame["anomaly_flag"]]
    if len(flagged) == 0:
        return frame

    # Merge nearby review windows, avoiding a full redownload for each outlier.
    windows: list[list[pd.Timestamp]] = []
    for date in flagged:
        start = max(pd.Timestamp(DOWNLOAD_START), date - pd.Timedelta(days=7))
        end = min(pd.Timestamp(DOWNLOAD_END), date + pd.Timedelta(days=8))
        if windows and start <= windows[-1][1]:
            windows[-1][1] = max(end, windows[-1][1])
        else:
            windows.append([start, end])
    review_columns = RAW_COLUMNS + (["Capital_Gains"] if "Capital_Gains" in frame else [])
    for start, end in windows:
        check = download(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        expected_window = expected[(expected >= start) & (expected < end)]
        validate_raw(ticker, check, expected_window)
        for column in review_columns:
            if column not in check:
                raise ValueError(f"{ticker}: anomaly review lost column {column}")
            # Yahoo may recompute adjusted-history floats across range requests;
            # tolerate only tiny rounding, not different economic observations.
            tolerance = 2e-6 if column == "Adj_Close" else 1e-9
            np.testing.assert_allclose(
                frame.loc[expected_window, column], check.loc[expected_window, column],
                rtol=tolerance, atol=1e-8,
                err_msg=f"{ticker}: anomaly recheck mismatch in {column}",
            )
    frame.loc[flagged, "anomaly_review"] = "yahoo_window_consistent_retained"
    frame.loc[zero_volume, "anomaly_review"] = (
        "yahoo_window_consistent_zero_volume_execution_unverified"
    )
    print(f"{ticker}: {len(flagged)} anomaly dates rechecked and retained:", flush=True)
    print(frame.loc[flagged, ["Close", "Volume", "Dividends", "Stock_Splits",
                             "daytime_return", "overnight_price_return",
                             "overnight_adjusted_return", "anomaly_reason"]].to_string(),
          flush=True)
    if unexplained.any():
        # A repeat from the same source cannot explain an unrecorded factor jump.
        raise ValueError(f"{ticker}: unexplained adjustment-factor jump remains: "
                         f"{date_list(frame.index[unexplained])}; no output written")
    return frame


def main() -> int:
    print(f"Versions: Python {sys.version.split()[0]}, pandas {pd.__version__}, "
          f"numpy {np.__version__}, yfinance {yf.__version__}, "
          f"pandas_market_calendars {mcal.__version__}", flush=True)
    calendar = mcal.get_calendar("NYSE")
    schedule = calendar.schedule(DOWNLOAD_START, SAMPLE_END, tz=TIMEZONE)
    expected = pd.DatetimeIndex(schedule.index).tz_localize(None)
    formal_expected = expected[(expected >= SAMPLE_START) & (expected <= SAMPLE_END)]
    print(f"NYSE/Arca calendar: {len(expected)} total sessions; "
          f"{len(formal_expected)} formal sessions; "
          f"{len(calendar.early_closes(schedule))} early closes including warmup.", flush=True)
    outputs: dict[str, pd.DataFrame] = {}
    failures: list[str] = []
    for ticker in TICKERS:
        print(f"Downloading/checking {ticker}...", flush=True)
        try:
            ticker_start = max(DOWNLOAD_START, FIRST_TRADING_DATE[ticker])
            ticker_expected = expected[expected >= ticker_start]
            frame = download(ticker, ticker_start, DOWNLOAD_END)
            validate_raw(ticker, frame, ticker_expected)
            frame = add_returns(frame, ticker_expected)
            frame = review_anomalies(ticker, frame, ticker_expected)
            # The only expected return NAs are the first warmup day's overnight
            # and close-to-close values; there is no earlier downloaded close.
            expected_na = pd.DataFrame(False, index=frame.index, columns=RETURN_COLUMNS)
            expected_na.iloc[0, 1:] = True
            if not frame[RETURN_COLUMNS].isna().equals(expected_na):
                raise ValueError(f"{ticker}: unexpected return missingness")
            outputs[ticker] = frame
            formal = frame.loc[frame["in_sample"]]
            status = "WARN_ZERO_VOLUME_EXECUTION_UNVERIFIED" if (frame["Volume"] == 0).any() else "PASS"
            print(f"{ticker}: {status} raw={frame.index[0].date()}..{frame.index[-1].date()} "
                  f"{len(frame)}/{len(ticker_expected)}; formal={formal.index[0].date()}.."
                  f"{formal.index[-1].date()} {len(formal)}/{len(formal_expected)}; "
                  "duplicates=0; missing raw=0; missing sessions=0; bad prices/OHLC=0; "
                  "composition=PASS", flush=True)
        except Exception as exc:
            failures.append(f"{ticker}: {type(exc).__name__}: {exc}")
            print(f"FAILED {failures[-1]}", file=sys.stderr, flush=True)
    if failures:
        print("FAILED: No data CSVs written in this run. Existing CSVs, if any, "
              "are unchanged and must not be mistaken for a successful new run.",
              file=sys.stderr)
        return 1
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for ticker, frame in outputs.items():
        ordered = RAW_COLUMNS + (["Capital_Gains"] if "Capital_Gains" in frame else [])
        ordered += ["adjustment_factor", "adjusted_open"] + RETURN_COLUMNS
        ordered += ["in_sample", "anomaly_flag", "anomaly_reason", "anomaly_review"]
        destination = DATA_DIR / f"{ticker}_daily.csv"
        frame[ordered].to_csv(destination, index=True, date_format="%Y-%m-%d",
                              float_format="%.17g", na_rep="")
        print(f"Wrote {destination}", flush=True)
    print("SUCCESS: six data CSVs validated and saved. Returns are decimals.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"FATAL: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(1)
