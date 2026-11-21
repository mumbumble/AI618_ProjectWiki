"""Unit tests for reading and writing CSV tables."""

from csvdelta.io import detect_encoding, iter_rows, read_table, write_csv


def _write_bytes(path, data):
    path.write_bytes(data)
    return path


def test_read_table_header_and_rows(tmp_path):
    src = _write_bytes(tmp_path / "plain.csv", b"id,name,amount\n1,Ann,10.0\n2,Bob,20.0\n")
    table = read_table(src)
    assert table.header == ["id", "name", "amount"]
    assert table.rows == [["1", "Ann", "10.0"], ["2", "Bob", "20.0"]]


def test_read_table_custom_delimiter(tmp_path):
    src = _write_bytes(tmp_path / "semi.csv", b"id;name\n1;Ann\n")
    table = read_table(src, delimiter=";")
    assert table.header == ["id", "name"]
    assert table.rows == [["1", "Ann"]]


def test_read_table_respects_explicit_encoding(tmp_path):
    src = _write_bytes(tmp_path / "latin.csv", "name\nZoë\n".encode("latin-1"))
    table = read_table(src, encoding="latin-1")
    assert table.rows == [["Zoë"]]


def test_read_table_strips_bom_issue_42(tmp_path):
    # Regression test. A file saved from Excel starts with a UTF-8 BOM.
    # With an explicit delimiter, the first header name came back as
    # '﻿id', so a key lookup on "id" raised KeyError and every row
    # showed up as both added and removed.
    data = b"\xef\xbb\xbfid,name\n1,Ann\n2,Bob\n"
    src = _write_bytes(tmp_path / "excel.csv", data)
    table = read_table(src, delimiter=",")
    assert table.header[0] == "id"
    assert "﻿id" not in table.header
    assert table.rows == [["1", "Ann"], ["2", "Bob"]]


def test_detect_encoding_prefers_bom(tmp_path):
    src = _write_bytes(tmp_path / "bom.csv", b"\xef\xbb\xbfid\n1\n")
    assert detect_encoding(src) == "utf-8-sig"


def test_detect_encoding_plain_utf8(tmp_path):
    src = _write_bytes(tmp_path / "utf8.csv", "name\nZoë\n".encode("utf-8"))
    assert detect_encoding(src) == "utf-8"


def test_detect_encoding_falls_back_to_latin1(tmp_path):
    src = _write_bytes(tmp_path / "latin.csv", b"name\n\xe9t\xe9\n")
    assert detect_encoding(src) == "latin-1"


def test_iter_rows_yields_all_lines(tmp_path):
    src = _write_bytes(tmp_path / "rows.csv", b"id,name\n1,Ann\n2,Bob\n")
    all_rows = list(iter_rows(src))
    assert len(all_rows) == 3
    assert all_rows[0] == ["id", "name"]
    assert all_rows[-1] == ["2", "Bob"]


def test_write_csv_round_trip(tmp_path):
    src = _write_bytes(tmp_path / "in.csv", b"id,name,amount\n1,Ann,10.0\n3,Cho,30.0\n")
    table = read_table(src)
    out = tmp_path / "out.csv"
    write_csv(table, out)
    again = read_table(out)
    assert again.header == table.header
    assert again.rows == table.rows
