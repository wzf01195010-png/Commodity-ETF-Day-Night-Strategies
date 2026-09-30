# Validation scope

## Existing empirical-stage evidence

`validation/prior_empirical_rebuild_pytest_results.xml` is an unchanged actual test record from the completed empirical rebuild: 32 tests, 0 failures, 0 errors, and 0 skipped. It contains synthetic-data unit tests and full-output acceptance checks. This is prior-stage evidence; no empirical analysis or pytest rerun was performed to create this repository.

## Repository preparation checks

- PASS: 31 copied source/configuration/test/evidence files match their originals byte-for-byte (see `../SOURCE_MANIFEST.csv`).
- PASS: all 24 included Python files parse with the available Python 3.13 runtime.
- PASS: included JSON configuration/template files parse.
- PASS: 18 required external-input hashes and paths recorded, without publishing those inputs.
- NOT TESTED in this upload: fresh dependency installation and a complete end-to-end reproduction from a fresh clone.
- NOT TESTED externally: flagged historical prices, real execution fills, borrow availability, historical settlement and financing conditions.

Syntax and file-integrity checks do not establish empirical validity or replace the prior numerical tests.
