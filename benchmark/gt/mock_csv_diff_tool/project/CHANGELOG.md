# Changelog

All notable changes to csvdelta are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-10-30

### Added

- `summary` command that prints row and cell counts for two CSV files without the full listing: `csvdelta summary A.csv B.csv`.
- `patch` command that applies a saved JSON delta to a CSV file: `csvdelta patch A.csv delta.json`.

### Changed

- Keyed alignment is about 2x faster. On the 1,000,000-row benchmark a diff went from 25.4 s to 12.7 s. At 100,000 rows it went from 2.30 s to 1.12 s.

## [0.3.2] - 2026-09-25

### Fixed

- `read_table` no longer keeps the UTF-8 byte order mark in the first column name. Files that start with a BOM, such as CSV files saved from Excel, produced a header like `'﻿id'` instead of `'id'`. As a result, `--key id` raised `KeyError` and every row was reported as both added and removed. The encoding check now returns `utf-8-sig` when a BOM is present, and it is no longer bypassed when a delimiter is passed explicitly. This affected 0.3.0 and 0.3.1. Thanks to mina-dev for the report. (#42)

## [0.2.0] - 2026-05-20

### Added

- Keyed alignment: `--key COL` (repeatable) matches rows by key columns instead of by position.
- `--tolerance FLOAT` for numeric cells. Two numeric values are equal when `abs(a - b) <= tolerance`.
- `--format json` output that follows delta schema version 1, with `added`, `removed`, and `changed` lists.

## [0.1.0] - 2026-03-14

### Added

- Initial release.
- `diff` command that compares two CSV files row by row by position.
- Text output that marks added rows with `+`, removed rows with `-`, and changed cells with `~`.
- Exit codes: 0 when the files are identical, 1 when differences are found, 2 on error.
