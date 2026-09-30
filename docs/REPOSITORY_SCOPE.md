# Repository scope and source roles

Research source, test, data, and reference-input files are unchanged copies, verified by SHA-256 against the existing delivery. The numbered layout preserves the reproduction CLI's relative defaults. Both the nine frozen price inputs and nine baseline comparison inputs are included, so a new vendor download is unnecessary.

The repository includes all current Python sources in `Main results/01_FINAL_CODE`, all three final test modules, and the three distinct historical data-source scripts. Original routines also present in Overleaf are not duplicated. `legacy_reference/engine.py` supplies original fixed rule definitions and the baseline model; final portfolio accounting lives in `repair/ledger.py`.

The complete `02_FINAL_DATA/` directory is included, with Finder metadata omitted. It contains input prices, processed final daily returns, audits, catalogs, and data documentation. The 45 unique historical/diagnostic reference panels and nine original comparison CSVs are kept under `08_OLD_VS_NEW/` with explicit roles. All 81 logical return-panel catalog entries resolve to their original 72 physical files without new duplicates.

`build_delivery.py`, `check_delivery.py`, `repack_lossless.py`, and `repair/delivery_docs.py` are retained packaging utilities. They require completed native outputs or the complete empirical delivery and its metadata. This code-and-data repository does not include every generated result required by those packaging utilities. In particular, do not run `check_delivery.py --package .` expecting it to validate this repository: that utility validates the complete research-delivery schema.

The preserved `01_FINAL_CODE/run_instructions.md` describes the earlier full delivery. Where its packaging context differs, the root README and this document specify what is included here.

Full trade ledgers, paper tables/figures, statistical result tables, PDFs, source archives, caches, and virtual environments are not uploaded. Existing daily-return data are included for inspection, while the unchanged CLI can generate fresh native results into a new output directory. The prior pytest XML is existing empirical-stage evidence; neither code publication nor data publication reran the analysis. The manuscript and its Data Availability Statement were not edited.
