#!/usr/bin/env python3
"""Backtest all 25 same-period day/night rules for six commodity ETFs.

Purpose
-------
Read the six CSV files made by data.py, verify their integrity and session
alignment, and run the common 2007-01-09 through 2025-12-31 sample. This script
never downloads market data or imports data.py.

Input / output (relative to THIS SCRIPT, not the working directory)
----------------------------------------------------------------
Input: data/{DBA,DBB,DBC,DBE,DBO,DBP}_daily.csv, including available warmup.
Five funds first trade on 2007-01-05; Jan 5 and Jan 8 supply the first lagged
overnight signal for Jan 9. DBC also retains December 2006. No pre-listing
bars are created; all 25 strategies use the same common evaluation dates.
Output: results/backtest_summary.csv and results/equity_curves.csv, published
with the five research outputs as one validated generation by research.py.
This script stages the two new files and snapshots all seven OLD outputs in
the temporary .commodity_pending directory. Old results remain unchanged
until research.py validates all comparisons and publishes the complete set.
Successful publication or a handled failure cleans the temporary directory.

Install: python -m pip install numpy pandas pandas_market_calendars
Run:     python backtest.py
         python research.py
Use the existing six data files; neither script downloads or modifies data.py.

Methods and assumptions
-----------------------
* NYSE's exchange-session calendar is used for the NYSE Arca-listed funds;
  their regular US-equity trading dates agree. Daily Date values are exchange
  date labels, not UTC instants. Calendar close instants use America/New_York.
* Day/Night names specify day and night rules, in that order. Each Momentum
  position is sign(previous trading session's SAME-leg return); Reversal is
  its negative. Zero signals mean flat. Missing signals are fatal, not zero.
  Long=+1, Short=-1, Cash=0. The unique strategy registry is STRATEGIES below:
  the Cartesian product of five rules. Flat is accepted only as a legacy
  input alias for Cash, and is never emitted as a new strategy name.
* Night[t] runs from close[t-1] to open[t], and its signal night_return[t-1]
  is already known at close[t-1]. Day[t] uses day_return[t-1] at open[t].
  The zero rule is exact, with no tuned tolerance. Yahoo adjusted-price float
  revisions can change the sign of near-zero overnight observations on a
  later download; source hashes identify the exact dataset used in each run.
* This is a discrete-leg, fully compounded target-exposure model: positions
  are +1, 0, or -1 times current equity and a leg earns position * leg_return.
  Short returns are the negative of adjusted asset returns, an idealized
  total-return short exposure. Short losses are not clipped. Maintaining a
  constant -100% exposure requires notional resizing in a real account;
  resizing costs are not modeled. The specified turnover measure charges
  only changes in exposure state, abs(new_position - old_position), so an
  unchanged side has zero turnover and a side reversal has two units.
* Fees equal current wealth * turnover_units * cost_bps / 10000, deducted
  BEFORE the next realized return. Sequence: initial entry at the preceding
  close; night return; open rebalance fee; day return; close rebalance fee.
  Intermediate close rebalances establish the NEXT night's position. The
  last close liquidates instead. Every strategy starts flat with wealth 100
  at the last pre-sample session close and ends flat. Initial entry costs
  belong to the first daily return; final liquidation belongs to the last.
  Open_wealth and Close_wealth are AFTER that boundary's transaction fee.
* Adjusted prices express Yahoo's consistent total-return price convention,
  not executable historical prices or a shares/dividends cash ledger. There
  is no additional dividend credit or split adjustment in this backtest.
  No borrow fees, financing, extra slippage, tax, or market impact are included.
  A provider-reported zero-volume session is retained as supplied and flagged
  in Data_quality_status. Prices on that session do not establish executable
  fills; results involving it remain conditional on the price-based model.
* Daily net returns combine both legs and applicable fees. Volatility uses
  sample standard deviation (ddof=1), with 252 sessions/year. Sharpe uses
  daily mean/std * sqrt(252) and risk-free rate zero. CAGR uses actual elapsed
  seconds between the initial and final exchange closes / 365.2425 days.
  Positive maximum drawdown uses initial 100 plus each open and close wealth.
* No dates are dropped or filled. Nonpositive/nonfinite wealth is flagged;
  it is never silently capped. An algebraic path may continue, but CAGR,
  volatility and Sharpe are undefined after economic insolvency. Maximum
  drawdown can exceed 100% for an algebraic negative-wealth path.
"""

from __future__ import annotations

import itertools
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal


ROOT = Path(__file__).resolve().parent
TICKERS = ("DBA", "DBB", "DBC", "DBE", "DBO", "DBP")
RULES = ("Long", "Short", "Cash", "Momentum", "Reversal")
STRATEGIES = tuple(itertools.product(RULES, repeat=2))
STRATEGY_NAMES = tuple(f"{day}/{night}" for day, night in STRATEGIES)
COSTS_BPS = (0, 1, 2)
DOWNLOAD_START = "2006-12-01"
SAMPLE_START = "2007-01-09"
SAMPLE_END = "2025-12-31"
FIRST_TRADING_DATE = {ticker: "2007-01-05" for ticker in TICKERS}
FIRST_TRADING_DATE["DBC"] = "2006-02-03"
TIMEZONE = "America/New_York"
INITIAL_WEALTH = 100.0
ANNUAL_SESSIONS = 252
SECONDS_PER_YEAR = 365.2425 * 24 * 60 * 60
PRICE_COLUMNS = ("Open", "High", "Low", "Close", "Adj_Close")
RETURN_COLUMNS = (
    "daytime_return", "overnight_price_return", "overnight_adjusted_return"
)
REQUIRED_COLUMNS = (
    "Date", *PRICE_COLUMNS, "Volume", "Dividends", "Stock_Splits",
    "adjusted_open", *RETURN_COLUMNS, "in_sample",
)
RESULT_FILES = ("backtest_summary.csv", "equity_curves.csv", "session_statistics.csv",
                "conditional_tests.csv", "diagnostic_backtests.csv", "breakeven_costs.csv",
                "research_findings.md")
STAGE = ROOT / ".commodity_pending"
STAGE_MAGIC = "commodity-25-strategy-transaction-v1"


def canonical_rule(rule: str) -> str:
    value = "Cash" if rule == "Flat" else rule
    if value not in RULES:
        raise ValueError(f"Unknown rule: {rule}")
    return value


def canonical_strategy(strategy: str) -> str:
    parts = str(strategy).split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid Day/Night strategy name: {strategy}")
    return "/".join(canonical_rule(x) for x in parts)


def canonical_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if "Strategy" in result:
        result["Strategy"] = result.Strategy.map(canonical_strategy)
    if "Period" in result:
        result["Period"] = result.Period.astype(str)
    # Legacy descriptive columns use the same zero-exposure meaning.
    return result.rename(columns={c: c.replace("_flat_fraction", "_cash_fraction")
                                  .replace("_vs_FlatLong_", "_vs_CashLong_") for c in result})


def compare_existing(old: pd.DataFrame, new: pd.DataFrame, keys: list[str], label: str) -> None:
    """Every legacy row must survive; compare every shared numeric field."""
    old, new = canonical_frame(old), canonical_frame(new)
    if old.duplicated(keys).any() or new.duplicated(keys).any():
        raise ValueError(f"{label}: duplicate keys after Flat/Cash canonicalization")
    old, new = old.set_index(keys), new.set_index(keys)
    absent = old.index.difference(new.index)
    if len(absent):
        raise ValueError(f"{label}: missing legacy keys {absent[:3].tolist()}")
    aligned = new.loc[old.index]
    for column in old.columns.intersection(new.columns):
        if pd.api.types.is_numeric_dtype(old[column]) and pd.api.types.is_numeric_dtype(aligned[column]):
            np.testing.assert_allclose(old[column].to_numpy(dtype=float), aligned[column].to_numpy(dtype=float),
                                       rtol=1e-9, atol=1e-10, equal_nan=True,
                                       err_msg=f"{label}: legacy numeric difference in {column}")
        elif column in ("Start_date", "End_date", "Initial_date", "Date", "Status", "Data_quality_status"):
            if not np.array_equal(old[column].astype(str), aligned[column].astype(str)):
                raise ValueError(f"{label}: legacy metadata changed in {column}")


def validate_panel(frame: pd.DataFrame, groups: list[str], strategies=STRATEGY_NAMES) -> None:
    expected = set(strategies)
    if frame.duplicated(groups + ["Strategy"]).any():
        raise ValueError("Duplicate strategy rows")
    for key, group in frame.groupby(groups, sort=False):
        if len(group) != len(expected) or set(group.Strategy) != expected:
            raise ValueError(f"Incomplete strategy coverage for {key}")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def discard_stage() -> None:
    """Remove only a recognized transaction, never an unrelated directory."""
    if not STAGE.exists():
        return
    marker = STAGE / "manifest.json"
    if not marker.is_file() or json.loads(marker.read_text())["magic"] != STAGE_MAGIC:
        raise ValueError(f"Unrecognized temporary path; refusing to remove {STAGE}")
    # If a process was interrupted between directory renames, restore the
    # complete old results directory before cleaning staging artifacts.
    rollback = STAGE / "rollback_results"
    if rollback.exists() and not (ROOT / "results").exists():
        os.replace(rollback, ROOT / "results")
    shutil.rmtree(STAGE)


def begin_stage() -> dict:
    if STAGE.exists():
        discard_stage()
    required = [ROOT / name for name in ("data.py", "backtest.py", "research.py")]
    required += [ROOT / "data" / f"{t}_daily.csv" for t in TICKERS]
    required += [ROOT / "results" / name for name in RESULT_FILES]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise FileNotFoundError("Missing required existing files: " + "; ".join(missing))
    if set(p.name for p in (ROOT / "results").iterdir()) != set(RESULT_FILES):
        raise ValueError("Unexpected files in results/: refusing to replace unrelated files")
    manifest = {"magic": STAGE_MAGIC, "hashes": {str(p.relative_to(ROOT)): file_hash(p) for p in required}}
    STAGE.mkdir()
    (STAGE / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (STAGE / "old").mkdir()
    (STAGE / "new").mkdir()
    for name in RESULT_FILES:
        shutil.copy2(ROOT / "results" / name, STAGE / "old" / name)
    return manifest


def check_stage() -> dict:
    marker = STAGE / "manifest.json"
    if not marker.is_file():
        raise FileNotFoundError(f"Missing staged backtest: {marker}; run python backtest.py first")
    manifest = json.loads(marker.read_text())
    if manifest.get("magic") != STAGE_MAGIC:
        raise ValueError("Unrecognized staged result generation")
    for relative, expected in manifest["hashes"].items():
        path = ROOT / relative
        if not path.is_file() or file_hash(path) != expected:
            raise ValueError(f"Input/code/old result changed during transaction: {path}")
    return manifest


def publish_stage() -> None:
    """Publish a complete directory; never expose a mixed set of CSV versions."""
    check_stage()
    new = STAGE / "new"
    if set(p.name for p in new.iterdir()) != set(RESULT_FILES):
        raise ValueError("Staged generation does not contain exactly all seven outputs")
    current, rollback = ROOT / "results", STAGE / "rollback_results"
    os.replace(current, rollback)
    try:
        os.replace(new, current)
    except BaseException:
        os.replace(rollback, current)
        raise
    # A power loss can expose either a complete generation or a missing
    # directory between the two renames, never individual mixed-version files.
    # discard_stage() recovers the old directory if that gap was interrupted.
    discard_stage()


def calendar_schedule() -> pd.DataFrame:
    """NYSE and NYSE Arca have the same regular equity-session dates."""
    return mcal.get_calendar("NYSE").schedule(
        start_date=DOWNLOAD_START, end_date=SAMPLE_END
    )


def legacy_comparable() -> bool:
    """Only demand numerical equality when both dates AND frozen inputs match.

    Extending the sample or refreshing Yahoo history legitimately changes
    results; an old 2016-2025 result cannot equal a new 2007-2025 result.
    Source hashes make subsequent unchanged-input reruns strictly comparable.
    """
    old = pd.read_csv(STAGE / "old" / "backtest_summary.csv")
    if "Source_data_sha256" not in old:
        return False
    if not (old.Start_date.eq(SAMPLE_START).all() and old.End_date.eq(SAMPLE_END).all()):
        return False
    return all(old.loc[old.Ticker == ticker, "Source_data_sha256"].eq(
        file_hash(ROOT / "data" / f"{ticker}_daily.csv")).all() for ticker in TICKERS)


def require_close(actual: np.ndarray, expected: np.ndarray, label: str) -> None:
    if not np.allclose(actual, expected, rtol=1e-9, atol=1e-11, equal_nan=True):
        differences = np.flatnonzero(
            ~np.isclose(actual, expected, rtol=1e-9, atol=1e-11, equal_nan=True)
        )
        raise ValueError(f"{label}: inconsistent values at row(s) {differences[:6].tolist()}")


def read_and_validate(ticker: str, schedule: pd.DataFrame) -> pd.DataFrame:
    """Fail before writing results if a fund has an incomplete or altered file."""
    filename = ROOT / "data" / f"{ticker}_daily.csv"
    if not filename.is_file():
        raise ValueError(f"Missing input {filename}; run data.py first.")
    frame = pd.read_csv(filename)
    missing = set(REQUIRED_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"{ticker}: missing columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError(f"{ticker}: empty input; no backtest performed.")
    date_text = frame["Date"].astype(str)
    if not date_text.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        raise ValueError(f"{ticker}: Date must contain local YYYY-MM-DD session labels.")
    dates = pd.DatetimeIndex(pd.to_datetime(date_text, format="%Y-%m-%d", errors="raise"))
    if dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError(f"{ticker}: duplicate or unsorted dates; no automatic repair.")
    expected = pd.DatetimeIndex(schedule.index).tz_localize(None)
    expected = expected[expected >= max(DOWNLOAD_START, FIRST_TRADING_DATE[ticker])]
    if not dates.equals(expected):
        absent = expected.difference(dates).strftime("%Y-%m-%d").tolist()
        extra = dates.difference(expected).strftime("%Y-%m-%d").tolist()
        raise ValueError(
            f"{ticker}: exchange-calendar mismatch; missing={absent[:12]}, "
            f"unexpected={extra[:12]}. Dates will not be dropped or concatenated."
        )
    frame.index = dates
    frame.attrs["source_sha256"] = file_hash(filename)
    numeric = [col for col in REQUIRED_COLUMNS if col not in ("Date", "in_sample")]
    for col in numeric:
        frame[col] = pd.to_numeric(frame[col], errors="raise")
    finite_columns = [col for col in numeric if col not in RETURN_COLUMNS]
    if not np.isfinite(frame[finite_columns].to_numpy(dtype=float)).all():
        raise ValueError(f"{ticker}: missing or nonfinite prices/actions/volume.")
    if (frame[list(PRICE_COLUMNS) + ["adjusted_open"]] <= 0).any().any():
        raise ValueError(f"{ticker}: nonpositive price.")
    if (frame[["Volume", "Stock_Splits"]] < 0).any().any():
        raise ValueError(f"{ticker}: negative volume or split factor.")
    tolerance = 1e-8 * frame["Close"]
    invalid_ohlc = (
        (frame["Low"] > frame[["Open", "Close"]].min(axis=1) + tolerance)
        | (frame["High"] < frame[["Open", "Close"]].max(axis=1) - tolerance)
        | (frame["Low"] > frame["High"] + tolerance)
    )
    if invalid_ohlc.any():
        raise ValueError(f"{ticker}: invalid OHLC relationship.")
    flags = frame["in_sample"].astype(str).str.lower().map(
        {"true": True, "false": False, "1": True, "0": False}
    )
    expected_flags = (dates >= pd.Timestamp(SAMPLE_START)) & (dates <= pd.Timestamp(SAMPLE_END))
    if flags.isna().any() or not np.array_equal(flags.to_numpy(), expected_flags):
        raise ValueError(f"{ticker}: invalid in_sample flags.")
    frame["in_sample"] = expected_flags
    factor = frame["Adj_Close"] / frame["Close"]
    adjusted_open = frame["Open"] * factor
    if "adjustment_factor" in frame:
        require_close(frame["adjustment_factor"].to_numpy(), factor.to_numpy(), f"{ticker} factor")
    require_close(frame["adjusted_open"].to_numpy(), adjusted_open.to_numpy(), f"{ticker} adjusted_open")
    expected_returns = {
        "daytime_return": frame["Close"] / frame["Open"] - 1,
        "overnight_price_return": frame["Open"] / frame["Close"].shift(1) - 1,
        "overnight_adjusted_return": adjusted_open / frame["Adj_Close"].shift(1) - 1,
    }
    for col, series in expected_returns.items():
        require_close(frame[col].to_numpy(), series.to_numpy(), f"{ticker} {col}")
    compounded = (1 + frame["daytime_return"]) * (1 + frame["overnight_adjusted_return"]) - 1
    close_to_close = frame["Adj_Close"] / frame["Adj_Close"].shift(1) - 1
    require_close(compounded.to_numpy(), close_to_close.to_numpy(), f"{ticker} leg identity")
    if not np.isfinite(frame.loc[frame["in_sample"], list(RETURN_COLUMNS)].to_numpy()).all():
        raise ValueError(f"{ticker}: unavailable formal-sample return; no date can be skipped.")
    return frame


def positions(frame: pd.DataFrame, column: str, rule: str) -> np.ndarray:
    """Lag by one session within the SAME leg, before selecting formal dates."""
    rule = canonical_rule(rule)
    if rule in ("Long", "Cash", "Short"):
        value = {"Long": 1, "Cash": 0, "Short": -1}[rule]
        return np.full(int(frame["in_sample"].sum()), value, dtype=np.int8)
    signal = frame[column].shift(1).loc[frame["in_sample"]].to_numpy(dtype=float)
    if not np.isfinite(signal).all():
        raise ValueError(f"{column}: missing lagged signal; missing must never mean flat.")
    sign = np.sign(signal).astype(np.int8)
    if rule == "Momentum":
        return sign
    if rule == "Reversal":
        return -sign
    raise ValueError(f"Unknown rule {rule}")


def run_strategy(
    ticker: str,
    frame: pd.DataFrame,
    schedule: pd.DataFrame,
    day_rule: str,
    night_rule: str,
    cost_bps: float,
) -> tuple[dict, pd.DataFrame]:
    day_rule, night_rule = canonical_rule(day_rule), canonical_rule(night_rule)
    if not np.isfinite(cost_bps) or not 0 <= cost_bps < 5000:
        raise ValueError("Cost must be finite, nonnegative and below 5000 bps")
    sample = frame.loc[frame["in_sample"]]
    dates = sample.index
    n = len(sample)
    if n < 2:
        raise ValueError(f"{ticker}: insufficient formal observations.")
    day_position = positions(frame, "daytime_return", day_rule)
    night_position = positions(frame, "overnight_adjusted_return", night_rule)
    day_return = sample["daytime_return"].to_numpy(dtype=float)
    night_return = sample["overnight_adjusted_return"].to_numpy(dtype=float)
    fee = cost_bps / 10000.0

    initial_units = np.zeros(n, dtype=np.int8)
    initial_units[0] = abs(night_position[0])
    open_units = np.abs(day_position - night_position)
    next_night = np.append(night_position[1:], 0).astype(np.int8)
    close_units = np.abs(next_night - day_position)
    daily_turnover = initial_units + open_units + close_units

    # These factors encode the chronological event sequence exactly. A close
    # fee buys the next night's target before that night's return occurs.
    open_factor = (
        (1 - initial_units * fee)
        * (1 + night_position * night_return)
        * (1 - open_units * fee)
    )
    close_factor = (1 + day_position * day_return) * (1 - close_units * fee)
    daily_factor = open_factor * close_factor
    with np.errstate(over="ignore", invalid="ignore"):
        close_wealth = INITIAL_WEALTH * np.cumprod(daily_factor)
        prior_close_wealth = np.concatenate(([INITIAL_WEALTH], close_wealth[:-1]))
        open_wealth = prior_close_wealth * open_factor
    # Include the pre-open/pre-close fee values in insolvency detection, but
    # the requested MDD sampling is initial wealth plus AFTER-fee opens/closes.
    before_night = prior_close_wealth * (1 - initial_units * fee)
    after_night = before_night * (1 + night_position * night_return)
    after_day = open_wealth * (1 + day_position * day_return)
    initial_fee = prior_close_wealth * initial_units * fee
    open_fee = after_night * open_units * fee
    close_fee = after_day * close_units * fee
    daily_fees = initial_fee + open_fee + close_fee
    events = np.column_stack((before_night, after_night, open_wealth, after_day, close_wealth))
    nonfinite = ~np.isfinite(events).all(axis=1)
    nonpositive = (events <= 0).any(axis=1)
    invalid = nonfinite | nonpositive
    invalid_ever = np.maximum.accumulate(invalid)
    daily_net_return = daily_factor - 1
    daily_net_return[invalid_ever] = np.nan
    # The path above is not truncated or capped. Once wealth is nonpositive,
    # net percentage performance ceases to have its normal economic meaning.
    status = "OK"
    first_bad_date = ""
    if invalid.any():
        first_bad_date = dates[np.flatnonzero(invalid)[0]].strftime("%Y-%m-%d")
        status = "NONFINITE_WEALTH" if nonfinite.any() else "NONPOSITIVE_WEALTH"

    initial_date = frame.index[frame.index.get_loc(dates[0]) - 1]
    initial_close = schedule.loc[initial_date, "market_close"].tz_convert(TIMEZONE)
    final_close = schedule.loc[dates[-1], "market_close"].tz_convert(TIMEZONE)
    elapsed_years = (final_close - initial_close).total_seconds() / SECONDS_PER_YEAR
    final_wealth = float(close_wealth[-1])
    cagr = volatility = sharpe = np.nan
    if not invalid.any():
        cagr = float(np.expm1(np.log(final_wealth / INITIAL_WEALTH) / elapsed_years))
        daily_std = float(np.std(daily_net_return, ddof=1))
        volatility = daily_std * np.sqrt(ANNUAL_SESSIONS)
        if daily_std > 0:
            sharpe = float(np.mean(daily_net_return) / daily_std * np.sqrt(ANNUAL_SESSIONS))
        else:
            status = "ZERO_VOLATILITY_SHARPE_UNDEFINED"

    wealth_points = np.concatenate(([INITIAL_WEALTH], np.column_stack((open_wealth, close_wealth)).ravel()))
    max_drawdown = np.nan
    if np.isfinite(wealth_points).all():
        peaks = np.maximum.accumulate(wealth_points)
        max_drawdown = float(np.max(1 - wealth_points / peaks))
    strategy = f"{day_rule}/{night_rule}"
    benchmark_error = np.nan
    if strategy == "Long/Long" and cost_bps == 0:
        buy_and_hold = INITIAL_WEALTH * sample["Adj_Close"].to_numpy() / frame.loc[initial_date, "Adj_Close"]
        require_close(close_wealth, buy_and_hold, f"{ticker} no-cost Long/Long benchmark")
        expected_opens = INITIAL_WEALTH * sample["adjusted_open"].to_numpy() / frame.loc[initial_date, "Adj_Close"]
        require_close(open_wealth, expected_opens, f"{ticker} no-cost benchmark opens")
        benchmark_error = float(np.max(np.abs(close_wealth - buy_and_hold)))
    if strategy == "Long/Long" and int(daily_turnover.sum()) != 2:
        raise ValueError(f"{ticker}: Long/Long must trade only initial entry and final exit.")
    if not invalid.any():
        require_close(
            close_wealth / prior_close_wealth - 1, daily_net_return,
            f"{ticker} {strategy} daily returns",
        )
    summary = {
        "Ticker": ticker,
        "Source_data_sha256": frame.attrs.get("source_sha256", "UNSPECIFIED_INPUT"),
        "Signal_precision_note": "EXACT_ZERO_NO_TOLERANCE_YAHOO_ADJUSTED_FLOAT_SENSITIVE",
        "Strategy": strategy,
        "Cost_bps": cost_bps,
        "Start_date": dates[0].strftime("%Y-%m-%d"),
        "End_date": dates[-1].strftime("%Y-%m-%d"),
        "Trading_days": n,
        "Final_wealth": final_wealth,
        "CAGR": cagr,
        "Annualized_volatility": volatility,
        "Max_drawdown": max_drawdown,
        "Sharpe_ratio": sharpe,
        "Turnover_units": int(daily_turnover.sum()),
        "Total_fees_paid": float(daily_fees.sum()),
        "Cash_return": 0.0,
        "Initial_wealth": INITIAL_WEALTH,
        "Initial_date": initial_date.strftime("%Y-%m-%d"),
        "Elapsed_years": elapsed_years,
        "Risk_free_rate": 0.0,
        "Annualization_days": ANNUAL_SESSIONS,
        "Status": status,
        "First_invalid_wealth_date": first_bad_date,
        "Benchmark_max_abs_error": benchmark_error,
        "Data_quality_status": (
            "WARN_ZERO_VOLUME_EXECUTION_UNVERIFIED"
            if "Volume" in sample and (sample["Volume"] == 0).any()
            else "PASS"
        ),
        "Zero_volume_days": int((sample["Volume"] == 0).sum()) if "Volume" in sample else 0,
        "Data_anomaly_days": (
            int(sample["anomaly_flag"].astype(str).str.lower().isin(("true", "1")).sum())
            if "anomaly_flag" in sample else 0
        ),
    }
    curve = pd.DataFrame({
        "Date": dates.strftime("%Y-%m-%d"),
        "Ticker": ticker,
        "Strategy": strategy,
        "Cost_bps": cost_bps,
        "Night_position": night_position,
        "Day_position": day_position,
        "Open_wealth": open_wealth,
        "Close_wealth": close_wealth,
        "Daily_net_return": daily_net_return,
        "Initial_entry_units": initial_units,
        "Open_turnover_units": open_units,
        "Close_turnover_units": close_units,
        "Daily_turnover_units": daily_turnover,
        "Initial_fee": initial_fee,
        "Open_fee": open_fee,
        "Close_fee": close_fee,
        "Daily_fees": daily_fees,
        "Wealth_status": np.where(invalid_ever, "INVALID_WEALTH", "OK"),
    })
    if strategy == "Cash/Cash":
        np.testing.assert_array_equal(curve[["Open_wealth", "Close_wealth"]], INITIAL_WEALTH)
        assert summary["Turnover_units"] == summary["Total_fees_paid"] == 0
        assert summary["CAGR"] == summary["Annualized_volatility"] == summary["Max_drawdown"] == 0
        assert np.isnan(summary["Sharpe_ratio"])
    return summary, curve


def verify_curve(frame: pd.DataFrame, curve: pd.DataFrame, strategy: str, cost: float) -> None:
    """Independent event identities, including first-day historical signals."""
    sample = frame.loc[frame.in_sample]
    np.testing.assert_array_equal(curve.Date, sample.index.strftime("%Y-%m-%d"))
    day, night = canonical_strategy(strategy).split("/")
    for leg, rule, col in (("Day", day, "daytime_return"), ("Night", night, "overnight_adjusted_return")):
        lag = frame[col].shift().loc[sample.index].to_numpy()
        if not np.isfinite(lag).all():
            raise ValueError("Missing prior same-session signal")
        expected = (np.full(len(lag), {"Long": 1, "Short": -1, "Cash": 0}[rule])
                    if rule in ("Long", "Short", "Cash") else np.sign(lag) * (1 if rule == "Momentum" else -1))
        np.testing.assert_array_equal(curve[f"{leg}_position"], expected)
    pn, pd_ = curve.Night_position.to_numpy(), curve.Day_position.to_numpy()
    iu = np.r_[abs(pn[0]), np.zeros(len(pn) - 1)]
    ou, cu = abs(pd_ - pn), abs(np.r_[pn[1:], 0] - pd_)
    np.testing.assert_array_equal(curve.Daily_turnover_units, iu + ou + cu)
    prior = np.r_[INITIAL_WEALTH, curve.Close_wealth.to_numpy()[:-1]]
    rate = cost / 10000
    opening = prior * (1 - iu * rate) * (1 + pn * sample.overnight_adjusted_return.to_numpy()) * (1 - ou * rate)
    closing = opening * (1 + pd_ * sample.daytime_return.to_numpy()) * (1 - cu * rate)
    np.testing.assert_allclose(opening, curve.Open_wealth, rtol=1e-10, atol=1e-11)
    np.testing.assert_allclose(closing, curve.Close_wealth, rtol=1e-10, atol=1e-11)


def main() -> int:
    begin_stage()
    schedule = calendar_schedule()
    # Validate EVERY input before producing or replacing either output.
    inputs = {ticker: read_and_validate(ticker, schedule) for ticker in TICKERS}
    sample_dates = inputs[TICKERS[0]].index[inputs[TICKERS[0]]["in_sample"]]
    for ticker, frame in inputs.items():
        if not frame.index[frame["in_sample"]].equals(sample_dates):
            raise ValueError(f"{ticker}: formal sample differs across ETFs.")
    summaries, curves = [], []
    for ticker, frame in inputs.items():
        for day_rule, night_rule in STRATEGIES:
            for cost_bps in COSTS_BPS:
                summary, curve = run_strategy(
                    ticker, frame, schedule, day_rule, night_rule, cost_bps
                )
                summaries.append(summary)
                curves.append(curve)
                verify_curve(frame, curve, summary["Strategy"], cost_bps)
        print(f"{ticker}: validated {len(sample_dates)} sessions; 25 strategies x 3 costs complete.", flush=True)
    summary_frame = pd.DataFrame(summaries)
    curve_frame = pd.concat(curves, ignore_index=True)
    expected_runs = len(TICKERS) * len(STRATEGIES) * len(COSTS_BPS)
    expected_dates = schedule.loc[SAMPLE_START:SAMPLE_END].index
    if not sample_dates.equals(expected_dates) or expected_runs != 450:
        raise ValueError("Unexpected formal sample or strategy registry")
    if len(summary_frame) != expected_runs or len(curve_frame) != expected_runs * len(sample_dates):
        raise ValueError("Unexpected output dimensions; no files written.")
    keys = ["Ticker", "Strategy", "Cost_bps"]
    if summary_frame.duplicated(keys).any() or curve_frame.duplicated([*keys, "Date"]).any():
        raise ValueError("Duplicate output keys; no files written.")
    validate_panel(summary_frame, ["Ticker", "Cost_bps"])
    if legacy_comparable():
        compare_existing(pd.read_csv(STAGE / "old" / "backtest_summary.csv"), summary_frame, keys, "full summary")
        compare_existing(pd.read_csv(STAGE / "old" / "equity_curves.csv"), curve_frame, keys + ["Date"], "full curves")
    else:
        print("Sample/source generation changed: recomputing all outputs; old period totals are not an equality target.", flush=True)
    check_stage()
    result_dir = STAGE / "new"
    summary_path = result_dir / "backtest_summary.csv"
    curve_path = result_dir / "equity_curves.csv"
    # All work and checks finish in memory first. Only the two requested CSVs
    # are written; undefined values are explicit NaN with a matching Status.
    summary_frame.to_csv(summary_path, index=False, float_format="%.17g", na_rep="NaN")
    curve_frame.to_csv(curve_path, index=False, float_format="%.17g", na_rep="NaN")
    print(f"Staged backtest_summary.csv ({len(summary_frame)} rows) and equity_curves.csv ({len(curve_frame)} rows)")
    print("Old results unchanged. Run python research.py to validate and publish all seven outputs together.")
    exceptional = summary_frame.loc[summary_frame["Status"] != "OK", keys + ["Status"]]
    if len(exceptional):
        print("WARNING: undefined/economically invalid results:\n" + exceptional.to_string(index=False))
    quality = summary_frame.loc[
        summary_frame["Data_quality_status"] != "PASS",
        ["Ticker", "Data_quality_status", "Zero_volume_days", "Data_anomaly_days"],
    ].drop_duplicates()
    if len(quality):
        print("WARNING: data/execution limitations:\n" + quality.to_string(index=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        discard_stage()
        print(f"BACKTEST FAILED: {error}", file=sys.stderr)
        raise SystemExit(1)
