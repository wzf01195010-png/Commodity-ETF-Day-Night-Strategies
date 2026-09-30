"""Read-only content audit, manifest refresh, and ZIP/CRC audit. No analysis is invoked."""

import argparse
from collections import Counter, defaultdict
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import zipfile
import sys

sys.dont_write_bytecode = True
from build_delivery import digest, write_csv


def read(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def check(package, source=None):
    p = Path(package)
    checks = []

    def verify(name, ok, detail):
        checks.append(dict(check=name, status="PASS" if ok else "FAIL", detail=detail))
        if not ok:
            raise AssertionError(checks[-1])

    files = [f for f in p.rglob("*") if f.is_file() and f.name != ".DS_Store"]
    bad = [
        str(f.relative_to(p))
        for f in files
        if any(
            part
            in [
                "__pycache__",
                ".pytest_cache",
                ".DS_Store",
                "__MACOSX",
                "cache",
                "tmp",
                "backup",
                "draft",
            ]
            for part in f.parts
        )
        or f.suffix in [".pyc", ".pkl", ".zip", ".nbc", ".nbi"]
    ]
    verify("no_caches_or_source_archives", not bad, bad)
    ambiguous = {
        "final.csv",
        "final2.csv",
        "newest.csv",
        "output_new.csv",
        "test123.csv",
    }
    verify(
        "descriptive_filenames",
        not any(f.name in ambiguous for f in files),
        "Known ambiguous names absent.",
    )
    byhash = defaultdict(list)
    for f in files:
        byhash[digest(f)].append(f.relative_to(p).as_posix())
    duplicates = [v for v in byhash.values() if len(v) > 1]
    verify("no_duplicate_physical_file_content", not duplicates, duplicates)
    manifest = read(p / "00_README/FILE_MANIFEST.csv")
    listed = {r["relative_path"]: r for r in manifest}
    actual = {f.relative_to(p).as_posix() for f in files}
    verify(
        "manifest_coverage",
        actual == set(listed),
        {
            "missing_from_manifest": sorted(actual - set(listed)),
            "missing_from_folder": sorted(set(listed) - actual),
        },
    )
    for rel, r in listed.items():
        if rel != "00_README/FILE_MANIFEST.csv":
            verify(
                "manifest_sha256:" + rel,
                digest(p / rel) == r["sha256"],
                "Exact file hash match.",
            )
    keycols = {
        "ticker",
        "overnight_rule",
        "daytime_rule",
        "cost_bps",
        "sample_start",
        "sample_end",
        "model_version",
        "rule_order",
    }
    counts = {}
    for root in ["03_FINAL_RESULTS", "04_STATISTICAL_TESTS"]:
        for f in (p / root).rglob("*.csv"):
            rows = read(f)
            counts[f.relative_to(p).as_posix()] = len(rows)
            verify(
                "self_describing_csv:" + f.name,
                bool(rows) and keycols <= set(rows[0]),
                "Ticker, separated rules, cost, period and model are present.",
            )
            verify(
                "nonempty_csv_context:" + f.name,
                all(all(r[k] for k in keycols) for r in rows),
                "Context metadata is nonempty.",
            )
            for r in rows:
                if r.get("strategy_id", "").startswith("N_"):
                    verify(
                        "rule_order:" + f.name,
                        r["strategy_id"]
                        == f"N_{r['overnight_rule']}__D_{r['daytime_rule']}",
                        "Canonical Night/Day label and fields agree.",
                    )
    for metric in ["terminal_wealth", "mdd", "volatility", "sharpe"]:
        for cost in [0, 1, 2]:
            rel = f"03_FINAL_RESULTS/{metric}/{metric}_{cost}bps_2007_2025.csv"
            verify(
                "complete_grid:" + rel,
                counts.get(rel) == 225,
                "9 ETFs × 25 strategies at this cost.",
            )
    expected = {
        "03_FINAL_RESULTS/transaction_costs/transaction_costs_and_turnover_0_1_2bps_2007_2025.csv": 675,
        "03_FINAL_RESULTS/transaction_costs/cost_sensitivity_5_10bps_2007_2025.csv": 450,
        "03_FINAL_RESULTS/break_even_costs/break_even_costs_vs_buy_hold_and_cash_2007_2025.csv": 414,
        "03_FINAL_RESULTS/subperiod_results/subperiod_results.csv": 2025,
        "03_FINAL_RESULTS/other_final_results/financing_and_distribution_settlement_scenarios.csv": 2025,
        "04_STATISTICAL_TESTS/session_mean_tests/session_mean_tests.csv": 27,
        "04_STATISTICAL_TESTS/predictability_tests/same_session_predictability_tests.csv": 72,
        "04_STATISTICAL_TESTS/predictability_tests/cross_session_predictability_diagnostics.csv": 45,
        "04_STATISTICAL_TESTS/bootstrap_tests/paired_stationary_bootstrap_tests.csv": 1863,
        "04_STATISTICAL_TESTS/SPA_StepM/spa_stepm_results.csv": 81,
    }
    for rel, n in expected.items():
        verify(
            "required_result_count:" + rel, counts.get(rel) == n, f"Expected {n} rows."
        )
    catalog = read(p / "02_FINAL_DATA/processed/return_panel_catalog.csv")
    verify(
        "complete_return_panel_catalog",
        len(catalog) == 81 and len({r["data_path"] for r in catalog}) == 72,
        "81 logical panels stored as 72 distinct files; 9 byte-identical aliases explicitly documented.",
    )
    for r in catalog:
        verify(
            "return_panel:" + r["source_filename"],
            digest(p / r["data_path"]) == r["sha256"],
            "Alias or physical file exactly matches original logical panel hash.",
        )
    verify(
        "complete_trade_ledgers",
        len(
            list(
                (p / "03_FINAL_RESULTS/transaction_costs/trade_ledger").glob(
                    "*.parquet"
                )
            )
        )
        == 27,
        "Nine ETFs × three costs; row-level tests already in ledger_acceptance_checks.csv.",
    )
    verify(
        "complete_final_tables",
        len(list((p / "05_LATEX_TABLES").glob("*.tex"))) == 24,
        "Exactly 24 current generated tables.",
    )
    verify(
        "complete_final_figures",
        len(list((p / "06_FIGURES").glob("*.png"))) == 2,
        "Two final rendered figures; no duplicate format copies.",
    )
    verify(
        "manuscript_not_mislabeled",
        (p / "10_MANUSCRIPT/README.txt").read_text().strip()
        == "Manuscript was not updated in this empirical-repair stage."
        and len(list((p / "10_MANUSCRIPT").iterdir())) == 1,
        "Only the explicit unchanged-manuscript statement is delivered.",
    )
    if source:
        for r in read(
            p / "07_VALIDATION_AND_TESTS/validation_results/csv_projection_checks.csv"
        ):
            src = Path(source) / r["source_filename"]
            verify(
                "native_source_hash:" + src.name,
                digest(src) == r["source_sha256"],
                "Source values unchanged since curation.",
            )
            fields = r["source_fields_projected"].split("|")
            aliases = json.loads(r["field_aliases"])
            available = Counter(tuple(x[k] for k in fields) for x in read(src))
            delivered = read(p / r["relative_path"])
            for x in delivered:
                value = tuple(x[aliases.get(k, k)] for k in fields)
                verify(
                    "exact_source_csv_projection:" + r["relative_path"],
                    available[value] > 0,
                    "All selected original cell strings preserved, with multiplicity.",
                )
                available[value] -= 1
            verify(
                "projection_row_count:" + r["relative_path"],
                len(delivered) == int(r["source_rows_selected"]),
                "Selected row count preserved.",
            )
    # Compact evidence: do not store thousands of repeated per-row PASS lines.
    grouped = defaultdict(lambda: dict(status="PASS", checks=0))
    for r in checks:
        grouped[r["check"].split(":")[0]]["checks"] += 1
    return dict(
        checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        status="PASS",
        file_count=len(files),
        check_count=len(checks),
        groups=dict(grouped),
        required_result_rows=counts,
        source_csv_tokens_checked=bool(source),
        analysis_rerun=False,
    )


def refresh_manifest(p, newfile):
    rows = read(p / "00_README/FILE_MANIFEST.csv")
    byname = {r["relative_path"]: r for r in rows}
    rel = newfile.relative_to(p).as_posix()
    byname[rel] = dict(
        category=rel.split("/")[0],
        filename=newfile.name,
        relative_path=rel,
        description="文件层面最终目录审计；无分析重跑",
        generated_by="check_delivery.py",
        final_or_reference="final",
        notes="CSV original tokens, result coverage, no duplicate physical files, manifest hashes and alias inventory.",
        source_path="",
        sha256=digest(newfile),
        size_bytes=newfile.stat().st_size,
    )
    write_csv(
        p / "00_README/FILE_MANIFEST.csv",
        sorted(byname.values(), key=lambda r: r["relative_path"]),
    )


def zip_audit(p, destination):
    destination = Path(destination)
    if p in destination.parents:
        raise ValueError("ZIP must be outside package.")
    files = sorted(f for f in p.rglob("*") if f.is_file() and f.name != ".DS_Store")
    with zipfile.ZipFile(
        destination,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
        allowZip64=True,
    ) as z:
        for f in files:
            z.write(f, arcname=p.name + "/" + f.relative_to(p).as_posix())
    with zipfile.ZipFile(destination) as z:
        assert z.testzip() is None, "ZIP CRC failure"
        names = z.namelist()
        assert len(names) == len(set(names)) == len(files)
        for f in files:
            data = z.read(p.name + "/" + f.relative_to(p).as_posix())
            assert hashlib.sha256(data).hexdigest() == digest(f)
    return dict(
        status="PASS",
        archive=str(destination),
        size_bytes=destination.stat().st_size,
        files=len(files),
        sha256=digest(destination),
        crc_check="PASS",
        all_uncompressed_file_hashes="PASS",
        checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--create-zip", type=Path)
    args = parser.parse_args()
    p = args.package.resolve()
    report = check(p, args.source)
    if args.write_report:
        f = p / "07_VALIDATION_AND_TESTS/validation_results/packaging_validation.json"
        # Adding this report adds exactly one file if not already present.
        if not f.exists():
            report["file_count"] += 1
        f.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        refresh_manifest(p, f)
        report = check(p, args.source)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.create_zip:
        result = zip_audit(p, args.create_zip)
        args.create_zip.with_suffix(".verification.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
        print(json.dumps(result, indent=2))
