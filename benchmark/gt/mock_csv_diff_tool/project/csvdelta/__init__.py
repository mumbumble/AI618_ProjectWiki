"""csvdelta: row- and cell-level differences between two CSV files.

Public API:

    diff_files(path_a, path_b, key=None, tolerance=0.0) -> DiffResult
    diff_tables(table_a, table_b, key=None, tolerance=0.0) -> DiffResult
    read_table(path, delimiter=",", encoding="utf-8") -> Table
    write_delta(result, path, fmt="json") -> None
    summarize(result) -> dict
    DiffResult

Example:

    >>> import csvdelta
    >>> result = csvdelta.diff_files("old.csv", "new.csv", key="id")
    >>> csvdelta.summarize(result)
    {'added': 1, 'removed': 1, 'changed': 1, 'unchanged': 1}
"""

from .core import DiffResult, Differ, summarize
from .io import read_table, write_delta

__version__ = "0.4.0"

__all__ = [
    "diff_files",
    "diff_tables",
    "read_table",
    "write_delta",
    "summarize",
    "DiffResult",
]


def _normalize_key(key):
    """Accept a single column name, a list of names, or None."""
    if key is None:
        return None
    if isinstance(key, str):
        return [key]
    return list(key)


def diff_tables(table_a, table_b, key=None, tolerance=0.0):
    """Compare two Table objects and return a DiffResult.

    key: column name or list of column names for keyed alignment.
         When omitted, rows are aligned by position using an LCS
         over row fingerprints.
    tolerance: absolute tolerance used when comparing numeric cells.
    """
    differ = Differ(key=_normalize_key(key), tolerance=tolerance)
    return differ.run(table_a, table_b)


def diff_files(path_a, path_b, key=None, tolerance=0.0):
    """Read two CSV files from disk and return the DiffResult between them.

    Arguments have the same meaning as in diff_tables. Both files are
    read with the default delimiter and UTF-8 encoding; a leading BOM
    is stripped automatically.
    """
    table_a = read_table(path_a)
    table_b = read_table(path_b)
    return diff_tables(table_a, table_b, key=key, tolerance=tolerance)
