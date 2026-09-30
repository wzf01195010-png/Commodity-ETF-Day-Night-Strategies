# External frozen data required

Market data are not included in this code repository. The final CLI expects the nine unchanged `*_daily.csv` files, including warmup rows and prior-price metadata, from the research delivery's `02_FINAL_DATA/provided_prices/` directory. Pass that directory with `--input`, or place a local copy under `provided_prices/` here. Git ignores that directory.

See `../docs/INPUTS_REQUIRED.csv` for the exact expected filenames and SHA-256 hashes. No data were downloaded, edited, or published while creating this repository.
