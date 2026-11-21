"""Excel (.xlsx) support for csvdelta.

This optional plugin lets csvdelta compare worksheets from two Excel
workbooks. It subclasses csvdelta.core.Differ and overrides run() so that
each sheet is converted to a Table before the normal keyed alignment runs.
The core algorithm itself is unchanged.

Install the extra dependency with:

    pip install csvdelta[excel]

The plugin is discovered through the "csvdelta.plugins" entry-point group,
so the core package does not need to import it. Rows are read in read-only
mode, but they are still held in memory for the diff, the same as CSV input.
"""

from csvdelta.core import Differ, Table

try:
    import openpyxl
except ImportError:  # openpyxl is an optional dependency
    openpyxl = None


def _cell_value(value):
    """Keep numbers as they are so numeric tolerance still works."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return value


def _load_sheet(path, sheet_name=None):
    """Read one worksheet into a Table. The first row is the header."""
    if openpyxl is None:
        raise ImportError("openpyxl is required: pip install csvdelta[excel]")

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook[sheet_name] if sheet_name else workbook.active
        title = sheet.title
        raw_rows = [
            [_cell_value(v) for v in row]
            for row in sheet.iter_rows(values_only=True)
        ]
    finally:
        workbook.close()

    if not raw_rows:
        raise ValueError(f"sheet {title!r} in {path} is empty")

    width = len(raw_rows[0])
    header = [str(h).strip() if h not in (None, "") else "" for h in raw_rows[0]]

    body = []
    for row in raw_rows[1:]:
        if all(c == "" for c in row):
            continue  # skip fully blank rows, which Excel often leaves behind
        row = list(row[:width]) + [""] * (width - len(row))
        body.append(row)

    return Table(header=header, rows=body)


class ExcelDiffer(Differ):
    """Differ that reads both inputs as Excel worksheets.

    Use it like the base Differ. Pass sheet_a and sheet_b to pick a sheet by
    name. If they are omitted, the active sheet of each workbook is used.
    """

    def __init__(self, key=None, tolerance=0.0, sheet_a=None, sheet_b=None):
        super().__init__(key=key, tolerance=tolerance)
        self.sheet_a = sheet_a
        self.sheet_b = sheet_b

    def run(self, path_a, path_b):
        table_a = _load_sheet(path_a, self.sheet_a)
        table_b = _load_sheet(path_b, self.sheet_b)
        return super().run(table_a, table_b)
