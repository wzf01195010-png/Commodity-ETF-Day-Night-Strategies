# Final frozen data included

This directory is an unchanged copy of the research delivery's complete `02_FINAL_DATA/` contents, except Finder metadata. It contains nine `provided_prices/*_daily.csv` inputs, preserved warmup/prior-price metadata, final daily net-return panels, the exchange schedule, data reconciliation, corporate-action/anomaly audits, the strategy catalog, and original data documentation.

`DATA_DICTIONARY.md` describes the fields and construction. `data_manifest.json` records the frozen inputs' provenance and hashes. The original download timestamp is unavailable, and price anomalies have not been independently confirmed against a second vendor.

`processed/return_panel_catalog.csv` describes 81 logical model/ETF/cost panels stored as 72 unique physical files across this directory and `../08_OLD_VS_NEW/reference_return_panels/`. Byte-identical aliases remain explicit; no duplicate panel copies were invented. Every catalog path resolves in the repository.

The final CLI uses `provided_prices/` by default. No data were downloaded, edited, recomputed, or deleted during this upload. See `../DATA_MANIFEST.csv` for the exact copied-file hashes.
