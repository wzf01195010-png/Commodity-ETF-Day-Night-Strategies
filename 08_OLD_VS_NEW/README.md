# Baseline reconciliation inputs and reference panels

`legacy_validation_inputs/` contains the nine unchanged `*_25_strategies_2007_2025.csv` files used by the full reproduction/acceptance workflow to reconcile the original baseline. They are original baseline targets, not final repaired results. The existing CLI uses this directory by default.

`reference_return_panels/` contains 45 unique historical-model/adjusted-index diagnostic daily-return files referenced by `../02_FINAL_DATA/processed/return_panel_catalog.csv`. Final share-cash-ledger daily returns are stored in `../02_FINAL_DATA/processed/final_strategy_daily_returns/`. The catalog explicitly identifies models and aliases so reference panels cannot be mistaken for final results.

All files were copied without numerical changes. Their SHA-256 hashes are recorded in `../DATA_MANIFEST.csv`; the 18 direct reproduction input files are also listed in `../docs/INPUTS_REQUIRED.csv`.
