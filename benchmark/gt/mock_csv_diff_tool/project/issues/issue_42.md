# Issue #42: read_table drops the first column name when the file starts with a UTF-8 BOM

- **Reported by:** mina-dev
- **Reported on:** 2026-09-12
- **Affected versions:** 0.3.0, 0.3.1
- **Fixed in:** 0.3.2 (2026-09-25)
- **Assigned to:** 이서연 (io and bug fixes)
- **Status:** Closed, fix merged 2026-09-25, release note still to be added

## Summary

When a CSV file starts with a UTF-8 byte order mark (BOM), which is what Excel writes by default for "CSV UTF-8" exports, `read_table` keeps the BOM as part of the first header cell. The first column is then named `'﻿id'` instead of `'id'`. Any key lookup on that column fails.

## Symptoms

- The header printed for the table shows `'﻿id'` where `'id'` is expected. It looks identical on screen, so the problem is easy to miss.
- Calling `diff_files(..., key="id")` or running `csvdelta diff A.csv B.csv --key id` raises `KeyError: 'id'`.
- When the key is not used, or the reader output is compared by hand, every row shows up as both added and removed, because the keys never match.

## Steps to reproduce

1. Create a file that starts with the UTF-8 BOM bytes `EF BB BF`, followed by the text below, and save it. The file name below is only an example.

```python
import csvdelta

data = b"\xef\xbb\xbf" + b"id,name\n1,Ann\n2,Bob\n"
with open("saved_from_excel.csv", "wb") as f:
    f.write(data)

table = csvdelta.read_table("saved_from_excel.csv")
print(table.header)            # ['﻿id', 'name']  <- wrong

csvdelta.diff_files("saved_from_excel.csv", "saved_from_excel.csv", key="id")
# KeyError: 'id'
```

2. Run the same steps with a second file that has the same rows but no BOM. The header of the first file does not match the second, so the diff reports every row as removed and added.

## Expected behavior

- `read_table` returns header `['id', 'name']` for both files.
- Diffing a file against itself with `key="id"` reports no differences.

## Actual behavior

- The first header cell keeps the BOM character.
- Keyed diffs fail or report all rows as changed.

## Root cause

`read_table` opens the file with the encoding `"utf-8"` when a delimiter is passed explicitly. In that branch the encoding detection step was skipped, so `detect_encoding` never ran and the BOM was never seen. The `"utf-8-sig"` codec, which strips the BOM on read, was never used.

## Fix

- `detect_encoding` now checks for the BOM first and returns `"utf-8-sig"` when it is present.
- `read_table` always goes through `detect_encoding`, including when the delimiter is given explicitly.
- The reader no longer returns the BOM character in the header.

## Regression test

The unit test `test_read_table_strips_bom_issue_42` writes a BOM file with the content from the reproduction steps, reads it with `read_table`, and asserts that the header is `['id', 'name']`. It fails on 0.3.1 and passes on 0.3.2.

## Release note (for the changelog entry of 0.3.2)

> Fixed #42: `read_table` no longer keeps the UTF-8 BOM in the first column name when the file was saved with a BOM (for example, by Excel). Keyed diffs on such files now work as expected.

## Workaround for 0.3.0 and 0.3.1

Remove the BOM before diffing, for example by re-saving the file as plain UTF-8 or by reading it with `encoding="utf-8-sig"` and writing a clean copy.
