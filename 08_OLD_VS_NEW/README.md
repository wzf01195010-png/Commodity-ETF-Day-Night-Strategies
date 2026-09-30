# External baseline comparison inputs required

The full reproduction/acceptance workflow expects the nine `*_25_strategies_2007_2025.csv` files from the research delivery's `08_OLD_VS_NEW/legacy_validation_inputs/` directory. Pass that directory with `--legacy-reference`, or place a local copy under `legacy_validation_inputs/` here. They are baseline reconciliation targets, not final repaired results. Git ignores the local input directory.

Expected filenames and hashes are listed in `../docs/INPUTS_REQUIRED.csv`.
