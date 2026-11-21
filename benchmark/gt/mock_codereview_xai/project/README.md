# Explain Yourself, Reviewer

HCI user study on how the explanation style of an AI code-review assistant affects developers' trust and review accuracy.

Hanbit University HCI Lab. Prototype: **ReviewLens** (v0.4 for the main study, v0.3 during the pilot).

## Research question

How does the explanation style of an AI code-review assistant affect developers' trust and review accuracy?

## Conditions

The study compares three explanation styles, used as a within-subjects factor:

| Code | Style | What the participant sees |
|------|-------|---------------------------|
| `terse` | One-line verdict | A short label only, e.g. "Possible bug: missing bounds check". No reasoning. |
| `rationale` | Short rationale | A brief natural-language paragraph explaining why the comment was raised. |
| `trace` | Evidence-linked | The rationale, plus highlighted code lines and a step-by-step execution/test trace that points to the defect. |

## Hypotheses

- **H1:** Trust increases with explanation richness (trace > rationale > terse). Trust is the composite of Q1 to Q3.
- **H2:** The trace style yields higher review accuracy (fewer errors per task) than the terse style.

Review accuracy = 1 - errors/3. Each pull request has three seeded defects. An error is a seeded defect that was missed, or a wrong AI suggestion that was accepted, so each task scores 0 to 3 errors.

## Design

- Within-subjects, N = 10 developers (P01 to P10). Each participant completes all four tasks under all three conditions, giving 12 task runs per participant.
- Tasks: T1 off-by-one error in pagination (Python), T2 SQL injection in a query builder, T3 race condition in cache refresh, T4 unclosed file handle.
- Condition order is counterbalanced with a Latin-square-style rotation of the six permutations, assigned round-robin.
- Each condition uses a different PR variant (set A, B or C) for each task.
- Time limit: 8 minutes (480 s) per task.
- Post-task questionnaire: 7-point Likert items Q1 to Q8, completed after each condition.

Participants: 10 professional or graduate developers, aged 24 to 38 (median 29), with 2 to 11 years of experience (median 5). Six men and four women.

Session length is 90 minutes: consent (10 min), training (10 min), three condition blocks of about 15 minutes each including the survey, and a 15-minute semi-structured interview. Compensation is 30,000 KRW.

## Key results (main study, data collection 2026-04-06 to 2026-05-15)

- Trust composite (mean of Q1 to Q3): terse 3.70, rationale 4.90, trace 5.67. Friedman chi2(2) = 13.00, p = .002, Kendall W = 0.65.
- Errors per task: terse 1.30, rationale 0.95, trace 0.65. Accuracy is 56.7%, 68.3% and 78.3%.
- Seconds per task are lowest in the trace condition. Friedman chi2(2) = 7.20, p = .027, Kendall W = 0.36. Holm-adjusted Wilcoxon results are reported in the analysis output.
- H1 and H2 are supported. The findings are limited by the small sample (N = 10), a single lab, and seeded-defect PRs. A larger replication (N = 20) is under consideration for 2027.

## Folder structure

```
proposal/      Study proposal (PDF, dated 2026-02-20)
irb/           IRB approval (protocol HBU-IRB-2026-0417) and consent materials
study/         Task descriptions and session materials
prototype/     ReviewLens prototype source (app, logger, UI spec)
data/          Pseudonymized session data on the lab server (P01 to P10)
analysis/      Analysis scripts for task logs and survey responses
results/       Figures and result summaries
papers/        Prior work, including Cho & Baek (2024) on explanations and reliance
notes/         Working notes from the team
admin/         Administrative items (budget, scheduling)
reading/       Background reading
```

## Running the analysis

Install Python 3 with `numpy`, `pandas`, `scipy` and `matplotlib`. Then run:

```
python analysis/analyze_logs.py --input <path to the task-log CSV in data/>
```

The script prints the Friedman and Wilcoxon results for seconds and errors. The survey analysis script in `analysis/` computes the trust composite and saves the trust figure to `results/figures/`.

## Team

- Han Ji-woo, PhD student, PI, analysis (hanjw@hanbit-hci.example)
- Prof. Seo Jun-ho, advisor
- Kwon Da-eun, MS student, interviews and sessions
- Yoon Min-seok, MS student, prototype developer

## Data handling

Participants are identified only by pseudonymized IDs (P01 to P10). Audio is recorded only during the interview and deleted within 6 months after transcription. Data are kept on the lab server for 3 years and are accessible only to the four team members. Participants may withdraw at any time without penalty.

## Key dates

- 2026-02-20: proposal
- 2026-03-04: IRB approval
- 2026-03-12 to 2026-03-13: pilot (3 participants, not in the main data)
- 2026-04-06 to 2026-05-15: data collection
- June 2026: analysis
- 2026-07-09: advisor meeting on results and findings

## Contact

Han Ji-woo, hanjw@hanbit-hci.example
