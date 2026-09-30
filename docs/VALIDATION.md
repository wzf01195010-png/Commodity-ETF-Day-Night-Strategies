# Validation scope

## Existing empirical-stage evidence

`validation/prior_empirical_rebuild_pytest_results.xml` is an unchanged actual test record from the completed empirical rebuild: 32 tests, 0 failures, 0 errors, and 0 skipped. It contains synthetic-data unit tests and full-output acceptance checks. This is prior-stage evidence; no empirical analysis or pytest rerun was performed for either repository upload.

## Code-repository preparation checks

- PASS: 31 copied source/configuration/test/evidence files match their originals byte-for-byte (see `../SOURCE_MANIFEST.csv`).
- PASS: all 24 included Python files parsed with the available Python 3.13 runtime during initial preparation.
- PASS: included JSON configuration/template files parsed during initial preparation.
- PASS: reproduction CLI `--help` completed without executing analysis.

## Authorized data-upload checks

- PASS: 98 copied data/documentation/reference files match the originals byte-for-byte (see `../DATA_MANIFEST.csv`).
- PASS: all nine frozen market inputs and nine baseline reconciliation inputs are included with the original hashes.
- PASS: all 81 logical return-panel catalog paths resolve, match the catalog hashes, and map to the original 72 unique physical panel files.
- PASS: original source-data contents, modification times, sizes, and permissions remained unchanged during copying.
- PASS: existing research code/configuration/test/evidence files remain unchanged.
- NOT TESTED in this upload: fresh dependency installation and a complete end-to-end reproduction from a fresh clone.
- NOT TESTED externally: flagged historical prices, real execution fills, borrow availability, historical settlement and financing conditions.

Syntax, copy-integrity, and path checks do not establish empirical validity or replace the prior numerical tests. Full empirical estimation was not rerun for publication.
