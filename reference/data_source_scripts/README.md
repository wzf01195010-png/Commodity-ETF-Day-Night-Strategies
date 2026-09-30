# Historical data-source scripts

These three Python scripts were copied byte-for-byte from `DATA_SOURCE_REFERENCE`:

- `data.py`: historical six-fund download, cleaning, and return construction.
- `backtest.py`: historical backtest dependency, including the superseded cost/short model.
- `extend_9_etfs.py`: historical extension to GLD, SLV, and USO.

They provide source provenance. They are not the final empirical-repair entry point. Use `../../01_FINAL_CODE/run_reproduction.py` with the frozen external data for the current analysis. None of these reference scripts was executed for this upload. They may download a different vendor snapshot or require older project outputs if run independently.
