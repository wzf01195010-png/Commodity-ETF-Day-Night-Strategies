"""One-command reproduction in a NEW output directory; never overwrites delivery files."""

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parent
    package = root.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--input", type=Path, default=package / "02_FINAL_DATA" / "provided_prices"
    )
    parser.add_argument(
        "--legacy-reference",
        type=Path,
        default=package / "08_OLD_VS_NEW" / "legacy_validation_inputs",
    )
    parser.add_argument(
        "--tests", type=Path, default=package / "07_VALIDATION_AND_TESTS" / "unit_tests"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Check an existing native output directory, without re-estimating.",
    )
    args = parser.parse_args()
    out = args.output.resolve()
    if not args.validate_only and out.exists() and any(out.iterdir()):
        parser.error(
            "--output must be new or empty. Existing results are never overwritten."
        )
    out.mkdir(parents=True, exist_ok=True)
    logs = out / "execution_logs"
    logs.mkdir(exist_ok=True)
    env = dict(
        os.environ,
        COMMODITY_OUTPUT_ROOT=str(out),
        COMMODITY_INPUT_ROOT=str(args.input.resolve()),
        COMMODITY_LEGACY_REFERENCE_ROOT=str(args.legacy_reference.resolve()),
        PYTHONPATH=str(root),
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        PYTHONDONTWRITEBYTECODE="1",
        NUMBA_CACHE_DIR=str(out / "runtime_cache"),
    )
    steps = []
    if not args.validate_only:
        steps.extend(
            [
                (
                    "original_pipeline",
                    "from repair.legacy_provenance import reproduce; reproduce()",
                ),
                ("data_audit", "from repair.data_audit import audit; audit()"),
                (
                    "backtests",
                    "from repair.backtests import run_all,breakeven; run_all(); breakeven()",
                ),
                (
                    "session_and_predictability",
                    "from repair.inference import basic_tests; basic_tests()",
                ),
                (
                    "paired_bootstrap",
                    "from repair.inference import pairwise; pairwise()",
                ),
                ("spa_stepm", "from repair.inference import spa_stepm; spa_stepm()"),
                (
                    "tables_and_figures",
                    "from repair.presentation import tables,figures; tables(); figures()",
                ),
                ("findings", "from repair.reporting import findings; findings()"),
            ]
        )
    records = []

    def execute(name, cmd):
        start = dt.datetime.now(dt.timezone.utc).isoformat()
        print(f"{start} {name}", flush=True)
        with (logs / f"{name}.log").open("w") as f:
            r = subprocess.run(
                cmd, cwd=root, env=env, stdout=f, stderr=subprocess.STDOUT
            )
        records.append(
            dict(
                stage=name,
                command=cmd,
                started_at_utc=start,
                finished_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                exit_code=r.returncode,
            )
        )
        (logs / "execution_manifest.json").write_text(
            json.dumps(
                dict(python=sys.version, platform=platform.platform(), steps=records),
                indent=2,
            )
            + "\n"
        )
        if r.returncode:
            raise SystemExit(f"{name} failed; see {logs/name}.log")

    for name, code in steps:
        execute(name, [sys.executable, "-u", "-c", code])
    execute(
        "pytest",
        [
            sys.executable,
            "-m",
            "pytest",
            str(args.tests.resolve()),
            "-v",
            "-p",
            "no:cacheprovider",
            f'--junitxml={logs/"pytest_results.xml"}',
        ],
    )
    print(f"Completed. Outputs: {out}", flush=True)


if __name__ == "__main__":
    main()
