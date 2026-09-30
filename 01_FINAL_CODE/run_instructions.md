# Reproduction instructions

Use Python 3.13.5 (the tested runtime), a new virtual environment and the frozen input files. No data download is required. Run from 01_FINAL_CODE:

```sh
python3.13 -m venv /absolute/path/commodity-repro-venv
/absolute/path/commodity-repro-venv/bin/python -m pip install -r requirements.lock.txt
/absolute/path/commodity-repro-venv/bin/python run_reproduction.py --output /absolute/path/new-commodity-results
```

The output directory must be new or empty. The command executes the original pipeline, data audit, all ledger grids/sensitivities, inference, 24 tables, two figures, findings, then 32 tests. It writes real start/end times, exit codes and logs to execution_logs. Output figures/tables are generated from CSV/Parquet. Templates contain captions/headers/footnotes only, never numeric data rows. Static legacy table hashes provide an independent reproduction target.

To check an existing native output directory without re-estimating:

```sh
/absolute/path/commodity-repro-venv/bin/python run_reproduction.py --output /absolute/path/existing-native-results --validate-only
```

Defaults locate ../02_FINAL_DATA/provided_prices, ../08_OLD_VS_NEW/legacy_validation_inputs and ../07_VALIDATION_AND_TESTS/unit_tests. Override --input, --legacy-reference, --tests if needed. Source uses COMMODITY_INPUT_ROOT, COMMODITY_OUTPUT_ROOT and COMMODITY_LEGACY_REFERENCE_ROOT internally. The delivered categorized CSVs are lossless projections of native outputs; validation-only expects native outputs, not the delivery root.

Tests are stored once, under 07_VALIDATION_AND_TESTS/unit_tests. Numba runtime cache goes into the NEW results directory, not this delivery. No R/notebook/shell analysis was used; the actual scripts are Python. Original engine.py is unmodified and used for legacy reproduction and fixed rule definitions. requirements.txt pins direct scientific dependencies; requirements.lock.txt includes the tested transitive set. Platform-specific floating point may differ at the last bits; acceptance uses explicit numeric tolerances, not an arbitrary requirement that all CSV bytes match.

Root seed20260928; custom stationary bootstrap2000 draws; actual arch8.0.0 SPA/StepM5000 draws; expected block10 baseline and5/20 sensitivity. Exact integer sub-seeds are in every relevant CSV. No seed or specification search is performed. Original protocol statistics use its original global RNG sequence, so distinguish them from new-protocol inference applied to the legacy wealth model.

This rebuild was executed in isolated .venv_repro with actual logs. The CLI validation-only command was also executed from the delivered 01_FINAL_CODE, using delivered data and tests; all 32 passed. A second full end-to-end rerun of the newly assembled CLI was not performed merely to package results; stage execution and table provenance were verified separately. Lost historical logs are not recreated. Packaging uses build_delivery.py (requires the native rebuild project and its captured logs); it changes metadata/file layout only and never invokes analysis functions.

To audit this delivery's manifest, schemas, counts, aliases and absence of duplicate/cache files without running analysis, use the standard-library-only command from 01_FINAL_CODE:

```sh
python3 -B check_delivery.py --package ..
```


## Workspace organization

2026-09-30整理工作目录后，本目录为唯一当前交付副本。数据目录原路径、内容、修改时间和权限保留；回测与统计数值未更改，也未重新运行。目录核验和ZIP打包忽略Finder生成的.DS_Store界面元数据，因此不会为了清理而触碰受保护数据目录。完整清理范围见工作目录根部CLEANUP_REPORT.md。源文件清单及校验值已更新。
