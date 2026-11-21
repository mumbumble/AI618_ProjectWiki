"""Dataset loading and train/dev/test splits for repojava_sum.

The processed table has one function per row with the fields
repo_id, commit_idx, func_id, code, summary and callees.
Rows are tab-separated. Newlines inside code and summaries are
stored as the two characters \\n, and callees are joined with "|".

Split settings (value of the data.split config key):
  intra_repo  within each repo, chronological 80/10/10 by commit_idx
  cross_repo  repo-level split, 992 train / 124 dev / 124 test repos

Source truncation (400 tokens) and summary truncation (48 tokens)
are applied later by the tokenizer step, not here.
"""

DEFAULT_SEED = 13
TRAIN_FRAC = 0.8
DEV_FRAC = 0.9  # dev ends here; test takes the remaining 10%
CROSS_TRAIN_REPOS = 992
CROSS_DEV_REPOS = 124


def _unescape(text):
    return text.replace("\\n", "\n").replace("\\t", "\t")


def read_rows(path):
    """Read the TSV table into a list of dicts. Malformed lines are skipped."""
    rows, skipped = [], 0
    with open(path, encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != len(header):
                skipped += 1
                continue
            rec = dict(zip(header, parts))
            rec["commit_idx"] = int(rec["commit_idx"])
            rec["code"] = _unescape(rec["code"])
            rec["summary"] = _unescape(rec["summary"])
            rec["callees"] = [c for c in rec["callees"].split("|") if c]
            rows.append(rec)
    print("read", len(rows), "rows, skipped", skipped, "malformed lines")
    return rows


def _seeded_permutation(items, seed=DEFAULT_SEED):
    """Fixed shuffle with a small LCG, so the order does not depend on
    Python's hash randomization or on the installed library versions."""
    state = seed
    out = list(items)
    for i in range(len(out) - 1, 0, -1):
        state = (state * 6364136223846793005 + 1442695040888963407) % (1 << 64)
        j = (state >> 33) % (i + 1)
        out[i], out[j] = out[j], out[i]
    return out


def intra_repo_split(rows):
    """Chronological 80/10/10 split inside every repository."""
    by_repo = {}
    for r in rows:
        by_repo.setdefault(r["repo_id"], []).append(r)
    splits = {"train": [], "dev": [], "test": []}
    for repo_id in sorted(by_repo):
        funcs = sorted(by_repo[repo_id], key=lambda r: (r["commit_idx"], r["func_id"]))
        n = len(funcs)
        cut1, cut2 = int(n * TRAIN_FRAC), int(n * DEV_FRAC)
        splits["train"].extend(funcs[:cut1])
        splits["dev"].extend(funcs[cut1:cut2])
        splits["test"].extend(funcs[cut2:])
    return splits


def cross_repo_split(rows, seed=DEFAULT_SEED):
    """Whole repositories go to one split, so test repos are unseen in training."""
    repos = _seeded_permutation(sorted({r["repo_id"] for r in rows}), seed)
    train_ids = set(repos[:CROSS_TRAIN_REPOS])
    dev_ids = set(repos[CROSS_TRAIN_REPOS:CROSS_TRAIN_REPOS + CROSS_DEV_REPOS])
    splits = {"train": [], "dev": [], "test": []}
    for r in rows:
        if r["repo_id"] in train_ids:
            splits["train"].append(r)
        elif r["repo_id"] in dev_ids:
            splits["dev"].append(r)
        else:
            splits["test"].append(r)
    return splits


class FunctionDataset:
    """One split of function-summary pairs."""

    def __init__(self, records):
        self.records = records
        # Caller index built over this split only, so no positives leak across splits.
        self.callers = {}
        for r in records:
            for callee in r["callees"]:
                self.callers.setdefault((r["repo_id"], callee), []).append(r["func_id"])

    def positives(self, i):
        """func_ids in the same repo that share a callee with record i (L_ret positives)."""
        r = self.records[i]
        found = set()
        for callee in r["callees"]:
            found.update(self.callers.get((r["repo_id"], callee), []))
        found.discard(r["func_id"])
        return sorted(found)

    def __len__(self):
        return len(self.records)

    def __getitem__(self, i):
        r = self.records[i]
        return {
            "func_id": r["func_id"],
            "repo_id": r["repo_id"],
            "code": r["code"],
            "summary": r["summary"],
        }


def load_split(path, setting="intra_repo", seed=DEFAULT_SEED):
    """Return a dict with FunctionDataset objects for train, dev and test."""
    rows = read_rows(path)
    if setting == "intra_repo":
        parts = intra_repo_split(rows)
    elif setting == "cross_repo":
        parts = cross_repo_split(rows, seed)
    else:
        raise ValueError("unknown split setting: %s" % setting)
    datasets = {name: FunctionDataset(recs) for name, recs in parts.items()}
    for name in ("train", "dev", "test"):
        print(setting, name, len(datasets[name]), "functions")
    return datasets
