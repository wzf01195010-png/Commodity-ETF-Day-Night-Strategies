# Commodity ETF Daytime and Overnight Strategies

Code and frozen data for **Daytime and Overnight Exposure in Commodity ETFs: A Comparison of Trading Strategies**.

This repository contains the current empirical-repair code, its tests, pinned dependencies, static table definitions, the final frozen data, and the historical scripts needed to trace the baseline and data-source workflow. Research source and data files were copied without changes. Repository preparation and data publication did not rerun the research or change empirical results.

**The nine frozen market-price inputs and all nine baseline reconciliation inputs are included. No new Yahoo download is required. Their exact filenames and hashes are recorded in [docs/INPUTS_REQUIRED.csv](docs/INPUTS_REQUIRED.csv), and all copied data files are listed in [DATA_MANIFEST.csv](DATA_MANIFEST.csv). A fresh Yahoo download is not a substitute for the study's frozen snapshot.**

The repository also includes the existing final daily-return panels, data audits, exchange schedule, and the reference panels needed to resolve the complete return-panel catalog. Full trade ledgers, generated paper tables/figures, statistical result tables, and the Overleaf manuscript are not included in this data upload.

## Which code to use

| Location | Purpose |
|---|---|
| `01_FINAL_CODE/run_reproduction.py` | Final end-to-end entry point, with explicit input and output paths |
| `01_FINAL_CODE/repair/` | Price audits, self-financing ledger, backtests, inference, tables, figures, and reporting |
| `01_FINAL_CODE/config.json` | Fixed sample, strategy universe, costs, seeds, and replication settings |
| `01_FINAL_CODE/requirements.lock.txt` | Dependency versions from the tested environment |
| `01_FINAL_CODE/legacy_reference/` | Historical original pipeline, retained for baseline reproduction; also supplies fixed rule definitions |
| `07_VALIDATION_AND_TESTS/unit_tests/` | Final unit tests and full-output acceptance tests |
| `reference/data_source_scripts/` | Historical download and expansion scripts; their old backtest is not the final ledger |
| `docs/validation/` | Existing actual test record from the empirical-rebuild stage |
| `SOURCE_MANIFEST.csv` | SHA-256 hashes and source roles for copied code/configuration/test/evidence files |
| `02_FINAL_DATA/` | Frozen price inputs, processed daily returns, audits, and data documentation |
| `08_OLD_VS_NEW/` | Original baseline inputs and explicitly labeled reference return panels |
| `DATA_MANIFEST.csv` | SHA-256 hashes and roles for all 98 copied data/documentation files |

No R scripts or notebooks were used in the final empirical workflow. Duplicate Overleaf copies of the original Python routines are represented once by `legacy_reference`.

## Fixed research specification

- Nine ETFs: DBA, DBB, DBC, DBE, DBO, DBP, GLD, SLV, USO.
- Common evaluation period: 2007-01-09 through 2025-12-31; 4,776 trading-day observations per ETF, with preserved earlier warmup observations.
- 25 combinations of Cash, Long, Short, Momentum, and Reversal. Every canonical identifier lists overnight first: `N_<overnight_rule>__D_<daytime_rule>`.
- Principal transaction costs: 0, 1, and 2 bps of actual traded notional; existing 5/10 bps and other sensitivity specifications are retained.
- Signals and descriptive returns use the frozen adjusted-price analytical series. Strategy results use the share-cash ledger, signed distribution obligations, post-cost equity targets, and short-position rebalancing.
- Root random seed: 20260928; paired stationary bootstrap: 2,000 replications; SPA/StepM: 5,000 replications. Expected block lengths: 10 baseline, 5 and 20 sensitivity. HAC bandwidth follows the retained formula and equals 9 in the principal full-sample tests.

## Reproduce with the included frozen inputs

Use Python **3.13.5**, the tested version. From this repository's root:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r 01_FINAL_CODE/requirements.lock.txt
.venv/bin/python 01_FINAL_CODE/run_reproduction.py \
  --output '/absolute/path/NEW_COMMODITY_RESULTS'
```

Choose a new or empty output directory. The CLI locates the included frozen inputs, baseline comparison inputs, and tests using its existing relative defaults. The command performs the historical baseline, final analyses, tables/figures, and the full test suite. **These are instructions for a future reproduction, not a claim that this repository upload executed those stages.**

The archived files are already under `02_FINAL_DATA/provided_prices/` and `08_OLD_VS_NEW/legacy_validation_inputs/`. To use a separate byte-identical data copy, override `--input` and `--legacy-reference`.

For validation of an existing **native** output directory, without rerunning empirical estimation:

```sh
.venv/bin/python 01_FINAL_CODE/run_reproduction.py \
  --output '/absolute/path/existing-native-results' \
  --validate-only
```

Acceptance tests require native outputs, not just the categorized delivery CSVs. They write validation logs and acceptance summaries to the selected output directory; use an expendable copy if preserving that directory is required.

The two synthetic-data unit-test modules can be run without market data:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=01_FINAL_CODE \
  .venv/bin/python -m pytest -p no:cacheprovider \
  07_VALIDATION_AND_TESTS/unit_tests/test_ledger.py \
  07_VALIDATION_AND_TESTS/unit_tests/test_inference.py
```

See [docs/REPOSITORY_SCOPE.md](docs/REPOSITORY_SCOPE.md) for packaging-utility prerequisites, [docs/VALIDATION.md](docs/VALIDATION.md) for verification scope, and the preserved [run instructions](01_FINAL_CODE/run_instructions.md) for the original delivery context.

## Interpretation limits

The fixed data snapshot has not been independently verified against a second vendor or exchange records. The original download timestamp is unavailable. Recorded open/close fills, fractional shares, stock-borrow availability, financing, and distribution settlement are modeling assumptions. The inspected subperiods are descriptive, not untouched holdouts. Candidate-family significance adjustments are not a correction across every possible research choice. Keeping these limitations in the code repository does not alter or resolve them.
