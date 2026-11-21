# csvdelta

csvdelta is an open-source Python tool that shows row-level and cell-level differences between two CSV files. It can match rows by one or more key columns, compare numbers with a tolerance, and write the result as text, JSON, or HTML. It is released under the MIT license and requires Python 3.9 or newer.

## Installation

```bash
pip install csvdelta
```

To read `.xlsx` sheets, install the optional Excel plugin, which uses openpyxl:

```bash
pip install "csvdelta[excel]"
```

## Quickstart

Compare two files, matching rows by the `id` column:

```bash
csvdelta diff old.csv new.csv --key id
```

Example output:

```text
- key=3 (row removed)
+ key=4 (row added)
~ key=2 amount: 20.0 -> 25.0
```

Lines starting with `+ ` are added rows, lines starting with `- ` are removed rows, and lines starting with `~ ` are changed cells.

## CLI usage

csvdelta has three commands:

| Command | Purpose |
| --- | --- |
| `csvdelta diff A.csv B.csv` | Show row and cell differences (default). |
| `csvdelta summary A.csv B.csv` | Print only the counts of added, removed, changed, and unchanged rows. |
| `csvdelta patch A.csv delta.json` | Apply the changes recorded in a JSON delta to `A.csv`. |

Options for `diff` and `summary`:

| Option | Description |
| --- | --- |
| `--key COL` | Column to match rows on. Repeat the option for a composite key. |
| `--delimiter CHAR` | Field delimiter. Default is `,`. |
| `--encoding NAME` | File encoding. Default is `utf-8`. |
| `--format {text,json,html}` | Output format. Default is `text`. |
| `--config PATH` | Read settings from a TOML config file. |
| `--ignore-case` | Compare text cells without regard to case. |
| `--tolerance FLOAT` | Treat numeric cells as equal when `abs(a - b) <= FLOAT`. |

Examples:

```bash
csvdelta diff old.csv new.csv --key id --tolerance 0.01
csvdelta diff old.csv new.csv --key id --format json > delta.json
csvdelta summary old.csv new.csv --key id
csvdelta patch old.csv delta.json
```

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | The files are identical. |
| `1` | The files differ. |
| `2` | An error occurred. |

This makes csvdelta easy to use in scripts and CI jobs.

## Configuration

A sample configuration file is in the `configs/` folder. Pass your own file with `--config PATH`. The supported keys are:

```toml
key_columns = []
delimiter = ","
encoding = "utf-8"
output_format = "text"
float_tolerance = 0.0
max_rows_in_memory = 500000
color = true
```

The config file is read with `tomllib` on Python 3.11 and newer. On Python 3.9 and 3.10, the `tomli` package is used instead. Command-line options override values from the config file.

## JSON delta format

The `--format json` output and the input to `patch` use this schema:

```json
{
  "version": 1,
  "added": [],
  "removed": [],
  "changed": [
    {
      "key": 2,
      "cells": [
        {"column": "amount", "old": 20.0, "new": 25.0}
      ]
    }
  ]
}
```

## Python API

```python
import csvdelta

result = csvdelta.diff_files("old.csv", "new.csv", key="id", tolerance=0.0)
print(csvdelta.summarize(result))
csvdelta.write_delta(result, "delta.json", fmt="json")
```

The public API consists of `diff_files`, `diff_tables`, `read_table`, `write_delta`, `summarize`, and the `DiffResult` class. See the `examples/demo.ipynb` notebook for a complete walkthrough. It writes two small CSV files, compares them, and prints the summary:

```python
{"added": 1, "removed": 1, "changed": 1, "unchanged": 1}
```

## How it works

csvdelta builds an index of key values for each file and matches rows by key. Rows that appear only in the first file are reported as removed, and rows that appear only in the second file are reported as added. Shared rows are then compared cell by cell. If no key is given, rows are aligned by position using a longest common subsequence over row fingerprints.

The core uses only the Python standard library. The key index is kept in memory, and the `max_rows_in_memory` setting (default 500000) controls how large a file can be before the tool warns about memory use.

## Performance

Measured on files with five columns (id, name, amount, city, flag), median of five runs:

| Rows | 0.3.2 | 0.4.0 |
| --- | --- | --- |
| 10,000 | 0.21 s | 0.10 s |
| 100,000 | 2.30 s | 1.12 s |
| 1,000,000 | 25.40 s | 12.70 s |

## Notes

- Files saved from Excel with a UTF-8 byte-order mark are read correctly from version 0.3.2 onward.
- Output colors can be turned off with `color = false` in the config file.

## License

MIT. See the license information in the repository.
