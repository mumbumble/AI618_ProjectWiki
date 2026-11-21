# csvdelta Design Document

Version 0.4.0. This document explains how csvdelta is structured, why it is built this way, and where it is heading. It is written for contributors who want to change the diff algorithm, add an output format, or write a plugin.

## Goals and scope

csvdelta compares two CSV files and reports which rows were added, removed, or changed, down to the individual cell. The core uses only the Python standard library and runs on Python 3.9 or newer. It is released under the MIT license. Optional features, such as Excel input, are installed as extras.

## Modules

- `csvdelta/core.py` holds the data model and the diff algorithm. It defines `Table`, `RowChange`, `CellChange`, `DiffResult`, and `Differ`. Core code never opens a file.
- The reader/writer layer is the only code that touches disk. Its functions are `read_table`, `iter_rows`, `detect_encoding`, `write_delta`, and `write_csv`.
- The command-line layer parses arguments, loads the TOML config, calls the reader, runs the differ, and renders the result as text, JSON, or HTML. It provides the `diff`, `summary`, and `patch` commands.
- The package root re-exports the public API: `diff_files`, `diff_tables`, `read_table`, `write_delta`, `summarize`, and `DiffResult`. It also exposes `__version__`.

## Data flow

1. The command-line layer parses options and loads defaults from the config file. Command-line options override config values.
2. The reader loads both inputs with `read_table` and returns two `Table` objects, each holding a header list and a list of row lists.
3. `Differ.run` aligns the rows and compares the cells, producing a `DiffResult`.
4. The result goes to `write_delta` for JSON or HTML output, or to the text renderer. The final output is written to stdout.

## Diff algorithm

The core uses keyed hash alignment.

1. When key columns are given, build a dictionary from key tuple to row index for each table. This step is O(n).
2. Keys that appear only in table A are reported as removed. Keys that appear only in table B are reported as added.
3. For keys present in both tables, compare cells column by column. Numeric cells are equal when `abs(a - b) <= tolerance`.
4. When no key is given, fall back to positional LCS alignment. This computes a longest common subsequence over row fingerprints, using a Hunt–Szymanski style approach.

A row fingerprint is a blake2b digest of the joined cell values, truncated to 8 bytes. `Differ.run` executes the whole pipeline. Its two building blocks are `align_rows` and `compare_cells`.

## Reader/writer layer

- `read_table` streams the file with `csv.reader`, strips a UTF-8 byte order mark, and sniffs the delimiter when `delimiter="auto"` is set.
- `iter_rows` yields rows lazily so that callers can process large files without loading them whole.
- `detect_encoding` checks for a BOM first, then tries UTF-8, then falls back to latin-1. A file with a BOM is reported as `utf-8-sig`. Earlier versions skipped detection when an explicit delimiter was given, which left the BOM in the first header name. This was fixed in 0.3.2.
- `write_delta` produces JSON, text, or HTML output. `write_csv` writes tables back out.

## Plugins

Plugins are discovered through the entry-point group `csvdelta.plugins`. A plugin extends a core class by subclassing it. The Excel plugin defines `ExcelDiffer`, a subclass of `Differ`. It overrides `run` to convert sheet rows into a `Table` first, which lets `.xlsx` sheets be compared like CSV data. It depends on openpyxl, which is optional and installed with `pip install csvdelta[excel]`.

## Design decisions

- **D1.** The core is pure standard library with no pandas dependency. This keeps the install small and the behaviour predictable.
- **D2.** The reader streams its input, but the diff keeps the keyed index in memory. This is why `max_rows_in_memory` exists, with a default of 500000.
- **D3.** Plugins subclass `Differ` instead of calling hook methods.
- **D4.** Output formats are kept separate from the algorithm, so a new format never touches alignment code.
- **D5.** Exit codes are 0 for identical inputs, 1 for differences, and 2 for errors.

## Performance

Version 0.4.0 made alignment about twice as fast. On the benchmark, 1,000,000 rows dropped from 25.4 s (0.3.2) to 12.7 s (0.4.0). For 100,000 rows the time went from 2.30 s to 1.12 s. The benchmark uses five columns (id, name, amount, city, flag), a fixed seed of 7, and the median of five runs. The team's target for 0.5.0 is under 8 s for 1,000,000 rows.

## Planned changes

The Korean-language roadmap extends this architecture in several ways.

- **0.5.0 (target 2027-01).** A streaming external-sort diff removes the `max_rows_in_memory` limit. This changes decision D2. Column comparison will also run in parallel. Owners are 김민준 for the core and 이서연 for the reader/writer layer.
- **0.6.0 (planned 2027-04).** Plugin hooks replace subclassing, which changes decision D3. A Parquet plugin is planned alongside. 정우진 owns the plugins.
- **1.0.0 (planned 2027-09).** The public API is frozen.
