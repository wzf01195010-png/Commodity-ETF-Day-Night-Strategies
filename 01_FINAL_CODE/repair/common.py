from pathlib import Path
import importlib.util, json, hashlib, itertools, os
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("COMMODITY_OUTPUT_ROOT", str(ROOT / "outputs")))
DATA_ROOT = Path(os.environ.get("COMMODITY_INPUT_ROOT", str(ROOT / "data")))
CONFIG = json.loads((ROOT / "config.json").read_text())
TICKERS = CONFIG["tickers"]
RULES = CONFIG["rules"]
STRATS = list(itertools.product(RULES, RULES))
IDS = [f"N_{n}__D_{d}" for n, d in STRATS]
BH = STRATS.index(("Long", "Long"))
CASH = STRATS.index(("Cash", "Cash"))
LEGACY = "legacy_signal_switch_cost"
INDEX = "ledger_adjusted_index_diagnostic"
LEDGER = "ledger_split_adjusted_cash_ex_open"


def sid(n, d):
    if n not in RULES or d not in RULES:
        raise ValueError((n, d))
    return f"N_{n}__D_{d}"


def import_legacy_label(label):
    day, night = label.split("/")
    return dict(night_rule=night, day_rule=day, strategy_id=sid(night, day))


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def json_write(p, v):
    Path(p).write_text(json.dumps(v, indent=2, ensure_ascii=False, default=str) + "\n")


def source_path(t):
    found = [p for p in DATA_ROOT.rglob(f"{t}_daily.csv") if "__MACOSX" not in p.parts]
    if len(found) != 1:
        raise ValueError(found)
    return found[0]


def raw(t):
    return pd.read_csv(source_path(t), parse_dates=["Date"])


def engine():
    path = ROOT / "code/engine.py"
    if not path.exists():
        path = ROOT / "legacy_reference/engine.py"
    spec = importlib.util.spec_from_file_location("frozen_engine", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.DATA = str(source_path(TICKERS[0]).parent)
    return m


def auto_lag(n):
    return int(np.floor(4 * (n / 100) ** (2 / 9)))


def metrics(daily, path):
    x = np.asarray(daily, float)
    w = np.asarray(path, float)
    peak = np.maximum.accumulate(w)
    sd = x.std(ddof=1) if len(x) > 1 else np.nan
    return dict(
        terminal_wealth=float(w[-1]),
        MDD=float(np.max(1 - w / peak)),
        Vol=float(sd * np.sqrt(252)),
        SR=float(x.mean() / sd * np.sqrt(252)) if sd > 1e-15 else np.nan,
        CAGR=float((w[-1] / w[0]) ** (252 / len(x)) - 1) if w[-1] > 0 else np.nan,
        annualized_arithmetic_mean=float(x.mean() * 252),
    )
