"""Execute/archive the supplied original pipeline and export reviewable comparisons."""

from pathlib import Path
import json
import os
import pickle
import shutil
import subprocess
import sys
import pandas as pd
from .common import OUT, ROOT, TICKERS, source_path, sha256


def collect(folder):
    folder = Path(folder)
    expected = json.loads(
        (Path(__file__).parent / "legacy_table_hashes.json").read_text()
    )
    rows = []
    for filename, digest in expected.items():
        f = folder / "Tables" / filename
        rows.append(
            dict(
                filename=filename,
                status="PASS" if f.exists() and sha256(f) == digest else "FAIL",
                source_sha256=digest,
                rerun_sha256=sha256(f) if f.exists() else "MISSING",
            )
        )
    pd.DataFrame(rows).to_csv(OUT / "original_table_reproduction.csv", index=False)
    assert all(r["status"] == "PASS" for r in rows)
    # Trusted pickle produced by the local unmodified analysis.py execution.
    with (folder / "code" / "results.pkl").open("rb") as f:
        result = pickle.load(f)
    rows = []
    for t in TICKERS:
        r = result[t]
        base = dict(
            ticker=t,
            period_start=str(r["start"].date()),
            period_end=str(r["end"].date()),
            n=r["T"],
            model_version="original_analysis_protocol",
            rule_order="NIGHT/DAY",
        )
        for group in ["desc", "pred"]:
            for test, values in r[group].items():
                if isinstance(values, dict):
                    for metric, value in values.items():
                        rows.append(
                            {
                                **base,
                                "analysis": group,
                                "test": test,
                                "statistic_name": metric,
                                "value": value,
                                "night_rule": "NOT_APPLICABLE",
                                "day_rule": "NOT_APPLICABLE",
                                "cost_bps": "NOT_APPLICABLE",
                            }
                        )
                else:
                    rows.append(
                        {
                            **base,
                            "analysis": group,
                            "test": test,
                            "statistic_name": "value",
                            "value": values,
                            "night_rule": "NOT_APPLICABLE",
                            "day_rule": "NOT_APPLICABLE",
                            "cost_bps": "NOT_APPLICABLE",
                        }
                    )
        for (n, d, c), values in r["pairwise"].items():
            for metric, value in values.items():
                rows.append(
                    {
                        **base,
                        "analysis": "pairwise",
                        "test": "original_bootstrap_block10",
                        "statistic_name": metric,
                        "value": value,
                        "night_rule": n,
                        "day_rule": d,
                        "cost_bps": int(round(c * 1e4)),
                    }
                )
        for c, values in r["spa"].items():
            for metric, value in values.items():
                rows.append(
                    {
                        **base,
                        "analysis": "spa_stepm",
                        "test": "original_arch_block10",
                        "statistic_name": metric,
                        "value": (
                            json.dumps(value)
                            if isinstance(value, (list, tuple))
                            else value
                        ),
                        "night_rule": "FAMILY_24_NON_BH",
                        "day_rule": "FAMILY_24_NON_BH",
                        "cost_bps": int(round(c * 1e4)),
                    }
                )
        for (n, d), values in r["breakeven"].items():
            for benchmark, value in values.items():
                rows.append(
                    {
                        **base,
                        "analysis": "breakeven",
                        "test": benchmark,
                        "statistic_name": "breakeven_bps",
                        "value": value,
                        "night_rule": n,
                        "day_rule": d,
                        "cost_bps": "SEARCH_VARIABLE",
                    }
                )
        for (start, end), values in r["sub"].items():
            for test, value in values.items():
                if isinstance(test, tuple):
                    n, d, c = test
                    rows.append(
                        {
                            **base,
                            "analysis": "subperiod",
                            "test": start + "_" + end,
                            "statistic_name": "terminal_wealth",
                            "value": value,
                            "night_rule": n,
                            "day_rule": d,
                            "cost_bps": int(round(c * 1e4)),
                        }
                    )
    pd.DataFrame(rows).to_csv(
        OUT / "original_protocol_reference_statistics.csv", index=False
    )
    print(
        f"Original pipeline: {len(expected)} byte-identical tables; original reported statistics exported.",
        flush=True,
    )


def reproduce():
    folder = OUT / "legacy_execution"
    code = folder / "code"
    code.mkdir(parents=True, exist_ok=True)
    source = ROOT / "legacy_reference"
    if not source.exists():
        source = ROOT / "code"
    for f in source.glob("*.py"):
        shutil.copy2(f, code / f.name)
    (folder / "Tables").mkdir(exist_ok=True)
    (folder / "Figures").mkdir(exist_ok=True)
    (code / "data").symlink_to(source_path(TICKERS[0]).parent, target_is_directory=True)
    for script in ["analysis.py", "make_tables.py", "make_figs.py"]:
        with (folder / f"{Path(script).stem}.log").open("w") as log:
            subprocess.run(
                [sys.executable, "-u", script],
                cwd=code,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )
    collect(folder)
