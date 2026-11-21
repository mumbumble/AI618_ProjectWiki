"""Core diff algorithm for csvdelta. Works on in-memory tables only."""
import bisect
import hashlib
from dataclasses import dataclass, field


@dataclass
class Table:
    header: list
    rows: list


@dataclass
class CellChange:
    column: str
    old: str
    new: str


@dataclass
class RowChange:
    kind: str  # "added", "removed" or "changed"
    key: tuple
    cells: list = field(default_factory=list)
    row: list = None


@dataclass
class DiffResult:
    row_changes: list = field(default_factory=list)
    counts: dict = field(default_factory=dict)


def fingerprint(row):
    """8-byte blake2b digest of the joined cell values."""
    return hashlib.blake2b("\x1f".join(map(str, row)).encode(), digest_size=8).digest()


def _lcs_matches(fa, fb):
    """Hunt-Szymanski longest common subsequence over row fingerprints."""
    positions = {}
    for j, h in enumerate(fb):
        positions.setdefault(h, []).append(j)
    thresh, last, nodes = [], [], []  # nodes hold (i, j, previous node)
    for i, h in enumerate(fa):
        for j in reversed(positions.get(h, ())):
            k = bisect.bisect_left(thresh, j)
            nodes.append((i, j, last[k - 1] if k else -1))
            if k == len(thresh):
                thresh.append(j)
                last.append(len(nodes) - 1)
            else:
                thresh[k], last[k] = j, len(nodes) - 1
    pairs, node = [], (last[-1] if last else -1)
    while node != -1:
        i, j, node = nodes[node]
        pairs.append((i, j))
    return pairs[::-1]


class Differ:
    """Keyed hash alignment, or positional LCS when no key is given."""

    def __init__(self, key=None, tolerance=0.0):
        self.key = [key] if isinstance(key, str) else list(key or [])
        self.tolerance = tolerance

    def _labels(self, table):
        if not self.key:
            return [(n + 1,) for n in range(len(table.rows))]
        for col in self.key:
            if col not in table.header:
                raise KeyError(col)
        pos = [table.header.index(col) for col in self.key]
        labels = [tuple(row[p] for p in pos) for row in table.rows]
        if len(set(labels)) != len(labels):
            raise ValueError("duplicate key values in table")
        return labels

    def align_rows(self, table_a, table_b, keys_a, keys_b):
        """Return (index_a, index_b) pairs; None marks a missing side."""
        if self.key:
            where_b, seen = {k: j for j, k in enumerate(keys_b)}, set(keys_a)
            return ([(i, where_b.get(k)) for i, k in enumerate(keys_a)]
                    + [(None, j) for j, k in enumerate(keys_b) if k not in seen])
        fa = [fingerprint(r) for r in table_a.rows]
        fb = [fingerprint(r) for r in table_b.rows]
        pairs, prev_a, prev_b = [], -1, -1
        for i, j in _lcs_matches(fa, fb) + [(len(fa), len(fb))]:
            gap_a, gap_b = range(prev_a + 1, i), range(prev_b + 1, j)
            for k in range(max(len(gap_a), len(gap_b))):
                pairs.append((gap_a[k] if k < len(gap_a) else None,
                              gap_b[k] if k < len(gap_b) else None))
            if i < len(fa):
                pairs.append((i, j))
            prev_a, prev_b = i, j
        return pairs

    def compare_cells(self, columns, row_a, row_b):
        changes = []
        for name, ia, ib in columns:
            old, new = row_a[ia], row_b[ib]
            try:
                same = abs(float(old) - float(new)) <= self.tolerance
            except (TypeError, ValueError):
                same = old == new
            if not same:
                changes.append(CellChange(name, old, new))
        return changes

    def run(self, table_a, table_b):
        columns = [(c, i, table_b.header.index(c))
                   for i, c in enumerate(table_a.header) if c in table_b.header]
        keys_a, keys_b = self._labels(table_a), self._labels(table_b)
        counts = {"added": 0, "removed": 0, "changed": 0, "unchanged": 0}
        result = DiffResult(counts=counts)
        for ia, ib in self.align_rows(table_a, table_b, keys_a, keys_b):
            cells, row = [], None
            if ia is None:
                kind, key, row = "added", keys_b[ib], table_b.rows[ib]
            elif ib is None:
                kind, key, row = "removed", keys_a[ia], table_a.rows[ia]
            else:
                cells = self.compare_cells(columns, table_a.rows[ia], table_b.rows[ib])
                if not cells:
                    counts["unchanged"] += 1
                    continue
                kind, key = "changed", keys_a[ia]
            counts[kind] += 1
            result.row_changes.append(RowChange(kind, key, cells, row))
        return result


def diff_tables(table_a, table_b, key=None, tolerance=0.0):
    """Diff two in-memory Table objects and return a DiffResult."""
    return Differ(key=key, tolerance=tolerance).run(table_a, table_b)
