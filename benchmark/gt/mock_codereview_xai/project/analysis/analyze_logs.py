"""Analysis of ReviewLens task logs (seconds and errors per task).

Usage: python analysis/analyze_logs.py --input data/task_logs.csv
"""
import csv
import sys

CONDITIONS = ["terse", "rationale", "trace"]
PAIRS = [("trace", "terse"), ("trace", "rationale"), ("rationale", "terse")]
E = 2.718281828459045


def fmt_p(p):
    return "<.001" if p < 0.001 else f"{p:.3f}".lstrip("0")


def read_logs(path):
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["seconds"] = float(r["seconds"])
        r["errors"] = int(r["errors"])
    return rows


def participant_means(rows, field):
    # one mean per participant and condition (averaged over the 4 tasks)
    cells = {}
    for r in rows:
        cells.setdefault((r["participant"], r["condition"]), []).append(r[field])
    people = sorted({r["participant"] for r in rows})
    return {c: [sum(cells[(p, c)]) / len(cells[(p, c)]) for p in people]
            for c in CONDITIONS}


def average_ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start
        while end + 1 < len(order) and values[order[end + 1]] == values[order[start]]:
            end += 1
        for k in range(start, end + 1):
            ranks[order[k]] = (start + end) / 2 + 1
        start = end + 1
    return ranks


def friedman(groups):
    n, k = len(groups[CONDITIONS[0]]), len(CONDITIONS)
    sums = {c: 0.0 for c in CONDITIONS}
    for i in range(n):
        for c, r in zip(CONDITIONS, average_ranks([groups[c][i] for c in CONDITIONS])):
            sums[c] += r
    chi2 = 12.0 / (n * k * (k + 1)) * sum(v * v for v in sums.values()) - 3 * n * (k + 1)
    p = E ** (-chi2 / 2)  # chi-square survival function, df = 2
    return chi2, p, chi2 / (n * (k - 1)), sums


def wilcoxon(x, y):
    diffs = [a - b for a, b in zip(x, y) if a != b]
    ranks = average_ranks([abs(d) for d in diffs])
    w_plus = sum(r for r, d in zip(ranks, diffs) if d > 0)
    w = min(w_plus, sum(ranks) - w_plus)
    n = len(diffs)
    # exact two-sided p: enumerate all 2^n sign patterns of the ranks
    hits = sum(1 for m in range(1 << n)
               if sum(ranks[i] for i in range(n) if (m >> i) & 1) <= w + 1e-9)
    return w, min(1.0, 2 * hits / (1 << n))


def holm(pvals):
    m = len(pvals)
    adj, running = [0.0] * m, 0.0
    for rank, i in enumerate(sorted(range(m), key=lambda j: pvals[j])):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adj[i] = running
    return adj


def main(argv):
    path = argv[argv.index("--input") + 1] if "--input" in argv else "data/task_logs.csv"
    rows = read_logs(path)
    print(f"Task-log rows: {len(rows)} ({path})\n")

    print("Per-condition totals and means (40 rows each)")
    for c in CONDITIONS:
        sub = [r for r in rows if r["condition"] == c]
        secs = sum(r["seconds"] for r in sub)
        errs = sum(r["errors"] for r in sub)
        mean_err = errs / len(sub)
        print(f"  {c:<10} total_s={secs:.0f} mean_s={secs / len(sub):.1f} "
              f"total_errors={errs} mean_errors={mean_err:.2f} "
              f"accuracy={100 * (1 - mean_err / 3):.1f}%")

    secs = participant_means(rows, "seconds")
    errs = participant_means(rows, "errors")
    n = len(secs["terse"])

    chi2, p, w, sums = friedman(secs)
    print(f"\nFriedman on per-participant mean seconds (n={n})")
    print(f"  chi2(2) = {chi2:.2f}, p = {fmt_p(p)}, Kendall W = {w:.2f}")
    print("  rank sums (1 = fastest): "
          + ", ".join(f"{c} {sums[c]:.0f}" for c in ["trace", "rationale", "terse"]))
    results = [wilcoxon(secs[a], secs[b]) for a, b in PAIRS]
    adjusted = holm([pv for _, pv in results])
    print("  Post-hoc Wilcoxon signed-rank, Holm-adjusted over 3 comparisons")
    for (a, b), (wv, pv), pa in zip(PAIRS, results, adjusted):
        print(f"    {a} vs {b}: W = {wv:g}, p = {fmt_p(pv)}, Holm p = {fmt_p(pa)}")

    chi2, p, w, _ = friedman(errs)
    print(f"\nFriedman on per-participant mean errors (n={n})")
    print(f"  chi2(2) = {chi2:.2f}, p = {fmt_p(p)}, Kendall W = {w:.2f}")
    wv, pv = wilcoxon(errs["trace"], errs["terse"])
    print(f"  Wilcoxon trace vs terse: W = {wv:g}, p = {fmt_p(pv)} (uncorrected)")


if __name__ == "__main__":
    main(sys.argv[1:])
