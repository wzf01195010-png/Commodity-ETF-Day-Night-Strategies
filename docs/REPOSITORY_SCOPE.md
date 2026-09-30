# Repository scope and source roles

The research source and final test files are unchanged copies, verified by SHA-256 against the existing delivery. The numbered code/test layout preserves the reproduction CLI's relative defaults; explicit input/output arguments allow the frozen inputs to remain elsewhere.

The repository includes all current Python sources in `Main results/01_FINAL_CODE`, all three final test modules, and the three distinct historical data-source scripts. Original routines also present in Overleaf are not duplicated. `legacy_reference/engine.py` supplies the original fixed rule definitions and baseline model; final portfolio accounting lives in `repair/ledger.py`.

`build_delivery.py`, `check_delivery.py`, `repack_lossless.py`, and `repair/delivery_docs.py` are retained packaging utilities. They require completed native outputs or the complete empirical delivery and its metadata. The code-only repository does not meet those prerequisites by itself. In particular, do not run `check_delivery.py --package .` expecting it to validate this code-only repository: that utility validates the complete research-delivery schema.

The preserved `01_FINAL_CODE/run_instructions.md` describes the earlier full delivery. Where its packaging-only context differs from this repository, the root README and this scope document specify what is actually included here.

No market CSVs, Parquet panels, trade ledgers, generated paper tables/figures, PDFs, source archives, caches, or virtual environments were uploaded. The prior pytest XML is included once as existing validation evidence; it is not an upload-time analysis result. The manuscript and its Data Availability Statement were not edited.
