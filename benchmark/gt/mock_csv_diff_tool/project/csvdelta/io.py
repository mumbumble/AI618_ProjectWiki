"""Reading and writing for csvdelta.

All disk access happens in this module. The diff core works on in-memory
tables only, so changing formats or encodings never touches the algorithm.
"""
import codecs
import csv
import html
import json

from csvdelta.core import Table

SNIFF_DELIMITERS = ",;\t|"
_CHUNK = 1 << 20


def detect_encoding(path):
    """Return a codec name: BOM first, then utf-8, then latin-1."""
    with open(path, "rb") as fh:
        if fh.read(3) == codecs.BOM_UTF8:
            return "utf-8-sig"
        fh.seek(0)
        decoder = codecs.getincrementaldecoder("utf-8")()
        try:
            for chunk in iter(lambda: fh.read(_CHUNK), b""):
                decoder.decode(chunk)
            decoder.decode(b"", final=True)
        except UnicodeDecodeError:
            return "latin-1"
    return "utf-8"


def iter_rows(reader):
    """Yield data rows from a csv reader, skipping blank lines."""
    for row in reader:
        if row:
            yield row


def _sniff_delimiter(sample):
    try:
        return csv.Sniffer().sniff(sample, delimiters=SNIFF_DELIMITERS).delimiter
    except csv.Error:
        return ","


def read_table(path, delimiter=",", encoding="utf-8"):
    """Load a CSV file into a Table. Use delimiter="auto" to sniff it."""
    if encoding in (None, "auto"):
        encoding = detect_encoding(path)
    if encoding.lower().replace("_", "-") == "utf-8":
        # utf-8-sig strips a leading BOM when present. Bypassing detection
        # here caused the BOM header bug fixed in 0.3.2.
        encoding = "utf-8-sig"
    with open(path, newline="", encoding=encoding) as fh:
        if delimiter == "auto":
            delimiter = _sniff_delimiter(fh.read(8192))
            fh.seek(0)
        reader = csv.reader(fh, delimiter=delimiter)
        header = next(reader, [])
        rows = list(iter_rows(reader))
    if header:
        header[0] = header[0].lstrip("﻿")
    return Table(header, rows)


def write_csv(table, path, delimiter=",", encoding="utf-8"):
    """Write a Table back out as CSV, header first."""
    with open(path, "w", newline="", encoding=encoding) as fh:
        writer = csv.writer(fh, delimiter=delimiter)
        writer.writerow(table.header)
        writer.writerows(table.rows)


def _key_text(key):
    if isinstance(key, (tuple, list)):
        return ", ".join(str(k) for k in key)
    return str(key)


def _render_text(result):
    lines = []
    for change in result.row_changes:
        if change.kind == "changed":
            for cell in change.cells:
                lines.append(
                    f"~ key={_key_text(change.key)} {cell.column}: {cell.old} -> {cell.new}"
                )
        else:
            sign = "+" if change.kind == "added" else "-"
            lines.append(sign + " " + ",".join(str(v) for v in change.cells))
    return "\n".join(lines) + "\n"


def _render_json(result):
    doc = {"version": 1, "added": [], "removed": [], "changed": []}
    for change in result.row_changes:
        if change.kind == "changed":
            doc["changed"].append({
                "key": list(change.key) if isinstance(change.key, tuple) else change.key,
                "cells": [{"column": c.column, "old": c.old, "new": c.new}
                          for c in change.cells],
            })
        else:
            doc[change.kind].append(list(change.cells))
    return json.dumps(doc, indent=2, ensure_ascii=False, default=str) + "\n"


def _html_row(kind, key, column, old, new):
    cells = "".join(f"<td>{html.escape(str(v))}</td>"
                    for v in (kind, key, column, old, new))
    return f"<tr>{cells}</tr>"


def _render_html(result):
    parts = ["<table>",
             "<tr><th>change</th><th>key</th><th>column</th><th>old</th><th>new</th></tr>"]
    for change in result.row_changes:
        key = _key_text(change.key)
        if change.kind == "changed":
            parts += [_html_row("changed", key, c.column, c.old, c.new)
                      for c in change.cells]
        else:
            row_text = ",".join(str(v) for v in change.cells)
            parts.append(_html_row(change.kind, key, "", "", row_text))
    parts.append("</table>")
    return ("<!DOCTYPE html>\n<html><body>\n"
            + "\n".join(parts) + "\n</body></html>\n")


_RENDERERS = {"json": _render_json, "text": _render_text, "html": _render_html}


def write_delta(result, path, fmt="json"):
    """Render a DiffResult as json, text or html and write it to path."""
    try:
        render = _RENDERERS[fmt]
    except KeyError:
        raise ValueError(f"unsupported format: {fmt!r}") from None
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(render(result))
