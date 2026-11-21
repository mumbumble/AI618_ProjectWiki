"""Unit tests for the core keyed and positional diff algorithm."""

import pytest

from csvdelta.core import CellChange, Differ, RowChange, Table


HEADER = ["id", "name", "amount"]


def make_table(rows):
    return Table(header=list(HEADER), rows=[list(r) for r in rows])


def kinds(result):
    return sorted(change.kind for change in result.row_changes)


def find(result, kind):
    return [change for change in result.row_changes if change.kind == kind]


def test_identical_tables():
    rows = [(1, "Ann", 10.0), (2, "Bob", 20.0), (3, "Cho", 30.0)]
    result = Differ(key=["id"]).run(make_table(rows), make_table(rows))
    assert result.row_changes == []


def test_added_row():
    a = make_table([(1, "Ann", 10.0), (2, "Bob", 20.0)])
    b = make_table([(1, "Ann", 10.0), (2, "Bob", 20.0), (4, "Dan", 40.0)])
    result = Differ(key=["id"]).run(a, b)
    assert kinds(result) == ["added"]
    added = find(result, "added")[0]
    assert isinstance(added, RowChange)
    assert "4" in str(added.key)


def test_removed_row():
    a = make_table([(1, "Ann", 10.0), (3, "Cho", 30.0)])
    b = make_table([(1, "Ann", 10.0)])
    result = Differ(key=["id"]).run(a, b)
    assert kinds(result) == ["removed"]
    removed = find(result, "removed")[0]
    assert "3" in str(removed.key)


def test_changed_cell():
    a = make_table([(1, "Ann", 10.0), (2, "Bob", 20.0)])
    b = make_table([(1, "Ann", 10.0), (2, "Bob", 25.0)])
    result = Differ(key=["id"]).run(a, b)
    assert kinds(result) == ["changed"]
    changed = find(result, "changed")[0]
    assert "2" in str(changed.key)
    assert len(changed.cells) == 1
    cell = changed.cells[0]
    assert isinstance(cell, CellChange)
    assert cell.column == "amount"
    assert float(cell.old) == 20.0
    assert float(cell.new) == 25.0


def test_example_mixed_changes():
    a = make_table([(1, "Ann", 10.0), (2, "Bob", 20.0), (3, "Cho", 30.0)])
    b = make_table([(1, "Ann", 10.0), (2, "Bob", 25.0), (4, "Dan", 40.0)])
    result = Differ(key=["id"]).run(a, b)
    assert kinds(result) == ["added", "changed", "removed"]


@pytest.mark.parametrize(
    "tolerance, expected_changes",
    [
        (0.0, 1),
        (0.01, 1),
        (0.05, 0),
        (0.5, 0),
    ],
)
def test_tolerance_numeric(tolerance, expected_changes):
    a = make_table([(1, "Ann", 10.0)])
    b = make_table([(1, "Ann", 10.04)])
    result = Differ(key=["id"], tolerance=tolerance).run(a, b)
    assert len(result.row_changes) == expected_changes


def test_positional_lcs():
    a = make_table([(1, "Ann", 10.0), (2, "Bob", 20.0), (3, "Cho", 30.0)])
    b = make_table([(1, "Ann", 10.0), (3, "Cho", 30.0)])
    result = Differ(key=None).run(a, b)
    assert kinds(result) == ["removed"]


def test_positional_lcs_insert():
    a = make_table([(1, "Ann", 10.0), (2, "Bob", 20.0), (3, "Cho", 30.0)])
    b = make_table([(1, "Ann", 10.0), (9, "Zed", 90.0), (2, "Bob", 20.0), (3, "Cho", 30.0)])
    result = Differ(key=None).run(a, b)
    assert kinds(result) == ["added"]
