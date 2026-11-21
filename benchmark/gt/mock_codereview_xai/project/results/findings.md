# Findings: "Explain Yourself, Reviewer"

Hanbit University HCI Lab. Summary of results from the within-subjects study of ReviewLens explanation styles (prototype v0.4).

Prepared by Han Ji-woo (analysis). Advisor: Prof. Seo Jun-ho.

## 1. Research question and hypotheses

**Research question:** How does the explanation style of an AI code-review assistant affect developers' trust and review accuracy?

Three explanation styles were compared within subjects:

- **terse**: one-line verdict label only, no reasoning
- **rationale**: short natural-language paragraph explaining why the comment was raised
- **trace**: rationale plus highlighted code lines and a step-by-step execution/test trace pointing to the defect

**H1:** Trust increases with explanation richness (trace > rationale > terse) on the trust composite (mean of Q1-Q3).
**H2:** The trace style yields higher review accuracy (fewer errors per task) than the terse style.

**Result summary:** H1 is supported. H2 is supported on the error measure, with the caveats listed in Section 7.

## 2. Sample and design

- 10 developers (P01-P10), professional or graduate, aged 24-38 (median 29), 2-11 years of experience (median 5); 6 men and 4 women.
- Each participant completed all 4 tasks under all 3 conditions, giving 12 task runs per participant and 120 task-log rows in total.
- Tasks: T1 off-by-one error in pagination (Python), T2 SQL injection in a query builder, T3 race condition in cache refresh, T4 unclosed file handle (resource leak).
- Each PR contained 3 seeded defects. Each condition used a different PR variant (set A, B or C) of each task.
- Condition order was counterbalanced over the six permutations of the three conditions, assigned round-robin.
- Task time limit was 8 minutes (480 s) per task.
- Data were collected from 2026-04-06 to 2026-05-15.

## 3. Measures

- **Trust composite:** mean of Q1-Q3 on a 7-point Likert scale (1 = strongly disagree, 7 = strongly agree).
- **Other survey items:** Q4 understanding, Q5 calibration, Q6 confidence, Q7 workload (higher = more effort, not reverse-coded), Q8 intention to use.
- **Task time:** seconds per task, from the interaction logger.
- **Review errors:** seeded defects missed plus wrong AI suggestions accepted, 0-3 per task. Review accuracy = 1 - errors/3.

## 4. Trust and survey results (H1)

Item means (terse / rationale / trace):

| Item | Terse | Rationale | Trace |
|---|---|---|---|
| Q1 I trusted the assistant's review comments. | 3.9 | 5.0 | 5.6 |
| Q2 I believe the assistant's comments were reliable. | 3.4 | 5.1 | 5.9 |
| Q3 I felt comfortable relying on the assistant. | 3.8 | 4.6 | 5.5 |
| Q4 I understood why the assistant raised each comment. | 3.2 | 5.2 | 6.0 |
| Q5 The explanations helped me notice when the assistant was wrong. | 3.1 | 4.4 | 5.5 |
| Q6 I was confident in my final review decisions. | 3.6 | 4.8 | 5.4 |
| Q7 The review required a lot of mental effort. | 4.9 | 4.5 | 3.8 |
| Q8 I would like to use this assistant in my daily work. | 3.5 | 4.6 | 5.3 |

**Trust composite (mean of Q1-Q3):** terse 3.70, rationale 4.90, trace 5.67.

Friedman test on the trust composite: chi2(2) = 13.00, p = .002, Kendall W = 0.65 (n = 10). The composite increases from terse to rationale to trace, which supports H1.

The trust composite by condition is shown in `results/figures/trust_composite_by_condition.png`. It is a bar chart with condition on the x-axis and the trust composite (1-7) on the y-axis. Bars are 3.70, 4.90 and 5.67, with 95% CI half-widths of 0.41, 0.36 and 0.30.

Item-level means are descriptive only. The confirmatory test is on the trust composite.

## 5. Task-time and error results (H2)

**Descriptive values (over 40 task runs per condition):**

| Measure | Terse | Rationale | Trace |
|---|---|---|---|
| Mean seconds per task | 212.4 | 187.6 | 163.9 |
| Total seconds | 8496 | 7504 | 6556 |
| Mean errors per task | 1.30 | 0.95 | 0.65 |
| Total errors | 52 | 38 | 26 |
| Review accuracy | 56.7% | 68.3% | 78.3% |

**Time (per-participant mean seconds):**

- Friedman test: chi2(2) = 7.20, p = .027, Kendall W = 0.36.
- Rank sums (1 = fastest): trace 14, rationale 20, terse 26.
- Post-hoc Wilcoxon signed-rank tests, Holm-adjusted over the three comparisons:
  - trace vs terse: W = 3, p = .010, Holm p = .030
  - trace vs rationale: W = 11, p = .053, Holm p = .106
  - rationale vs terse: W = 13, p = .085, Holm p = .106

Trace was the fastest condition. Only the trace vs terse comparison remains significant after the Holm correction.

**Errors (per-participant mean errors):**

- Friedman test: chi2(2) = 6.20, p = .045, Kendall W = 0.31.
- Post-hoc Wilcoxon signed-rank test, trace vs terse: W = 5, p = .020 (uncorrected).

The error comparison was not Holm-adjusted in the analysis. If it were adjusted across the three pairwise comparisons, the p-value would be .060, so this result should be treated as exploratory.

## 6. Conclusions

- **H1 (trust):** Supported. Trust composite rose from terse (3.70) to rationale (4.90) to trace (5.67), Friedman chi2(2) = 13.00, p = .002, W = 0.65.
- **H2 (accuracy):** Supported on the error measure. Trace had fewer errors per task than terse (0.65 vs 1.30), and accuracy rose from 56.7% to 78.3%. The trace vs terse Wilcoxon test gave p = .020, uncorrected. The Friedman test over styles gave p = .045.
- **Efficiency:** The trace style was also the fastest. Trace vs terse was significant after Holm correction (p = .030). The other time comparisons were not.
- **Workload:** Mental effort (Q7) was lowest for trace (3.8) and highest for terse (4.9).

## 7. Limitations

- The sample is small (N = 10) and comes from one lab. Results may not generalize to other developer populations.
- Tasks used PRs with seeded defects, which may differ from defects found in real code review.
- Error and time measures are from one session per condition, and the 8-minute limit may shape behaviour.
- The H2 error result is uncorrected and should be read as exploratory.
- The prior study (Cho & Baek, 2024) was between-subjects with 36 developers and found that long explanations raised acceptance of wrong suggestions by 17% and review time by 22%. The present study extends that work with a within-subjects design and an evidence-linked trace style. It did not test long explanations as a separate condition.

## 8. Next steps

Following the advisor meeting on 2026-07-09, the team agreed to:

- apply the Holm correction (done for the time comparisons),
- report Kendall W for each Friedman test (done),
- state the seeded-defect limitation explicitly (done in Section 7),
- consider an N = 20 replication in 2027.

Interview data (semi-structured, 15 minutes per session) will be coded against the same constructs: trust, understanding, calibration, confidence, mental effort, intention to use, and preferred style. Those results will be reported separately.
