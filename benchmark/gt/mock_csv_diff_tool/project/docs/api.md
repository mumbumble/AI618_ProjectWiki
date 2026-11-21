# csvdelta API reference

This page documents the public Python API of csvdelta. All of it is available from the top-level package:

```python
import csvdelta
```

The package exports six names: `diff_files`, `diff_tables`, `read_table`, `write_delta`, `summarize`, and `DiffResult`. The installed version is available as `csvdelta.__version__`, which is `"0.4.0"`.

The core library uses only the standard library. Only `read_table`, `diff_files`, and `write_delta` touch the disk. `diff_tables`, `summarize`, and the result objects work entirely in memory.

## diff_files

```python
csvdelta.diff_files(path_a, path_b, key=None, tolerance=0.0) -> DiffResult
```

Reads both CSV files with `read_table` and compares them.

| Parameter | Type | Description |
|---|---|---|
| `path_a` | str or path-like | The old file. |
| `path_b` | str or path-like | The new file. |
| `key` | str, list of str, or None | Column name that identifies each row. Pass a list for a composite key. If None, rows are aligned by position using an LCS over row fingerprints. |
| `tolerance` | float | Numeric cells are equal when `abs(a - b) <= tolerance`. The default `0.0` means exact comparison. |

Rows whose key appears only in `path_a` are reported as removed. Rows whose key appears only in `path_b` are reported as added. Rows with a shared key are compared cell by cell.

Raises `KeyError` if a key column is missing from a file's header. Files saved with a UTF-8 BOM, such as files exported from Excel, work correctly from version 0.3.2 onward. Earlier versions reported every row as both added and removed.

```python
result = csvdelta.diff_files("A.csv", "B.csv", key="id")
```

## diff_tables

```python
csvdelta.diff_tables(table_a, table_b, key=None, tolerance=0.0) -> DiffResult
```

Works like `diff_files`, but takes two `Table` objects, usually returned by `read_table`. No file access happens. Use it when the data is already in memory or when you want to load the files yourself.

## read_table

```python
csvdelta.read_table(path, delimiter=",", encoding="utf-8") -> Table
```

Streams a CSV file and returns a `Table`. A `Table` has a `header` (list of column names) and `rows` (list of lists of cell values).

- A UTF-8 BOM at the start of the file is removed from the first column name.
- Pass `delimiter="auto"` to detect the delimiter from the file contents.

```python
table = csvdelta.read_table("A.csv", delimiter=";", encoding="latin-1")
print(table.header)
```

## write_delta

```python
csvdelta.write_delta(result, path, fmt="json") -> None
```

Writes a `DiffResult` to `path`. `fmt` is one of `"json"` (default), `"text"`, or `"html"`.

The JSON output follows this schema:

```json
{
  "version": 1,
  "added": [...],
  "removed": [...],
  "changed": [
    {"key": 2, "cells": [{"column": "amount", "old": "20.0", "new": "25.0"}]}
  ]
}
```

The `text` format uses the same line prefixes as the command line tool: `+` for added rows, `-` for removed rows, and `~` for changed cells.

## summarize

```python
csvdelta.summarize(result) -> dict
```

Returns the number of rows in each category:

```python
{"added": 1, "removed": 1, "changed": 1, "unchanged": 1}
```

## DiffResult

```python
class csvdelta.DiffResult
```

The object returned by `diff_files` and `diff_tables`.

- `row_changes`: list of `RowChange` objects, one per added, removed, or changed row.
- `counts`: number of changes of each kind.

Each `RowChange` has:

- `kind`: `"added"`, `"removed"`, or `"changed"`.
- `key`: the key value or values that identify the row.
- `cells`: list of `CellChange` objects for changed rows.

Each `CellChange` has `column`, `old`, and `new`.

## Example

Given these two files with `id` as the key:

- A: `id,name,amount` with rows `1,Ann,10.0`, `2,Bob,20.0`, `3,Cho,30.0`
- B: `id,name,amount` with rows `1,Ann,10.0`, `2,Bob,25.0`, `4,Dan,40.0`

```python
import csvdelta

table_a = csvdelta.read_table("A.csv")
table_b = csvdelta.read_table("B.csv")
result = csvdelta.diff_tables(table_a, table_b, key="id")

for change in result.row_changes:
    print(change.kind, change.key)
    for cell in change.cells:
        print(f"  {cell.column}: {cell.old} -> {cell.new}")

csvdelta.write_delta(result, "delta.json")
print(csvdelta.summarize(result))
```

Row 3 is removed, row 4 is added, and row 2 has one changed cell (`amount`, 20.0 to 25.0). Row 1 is unchanged. The summary is `{"added": 1, "removed": 1, "changed": 1, "unchanged": 1}`.
