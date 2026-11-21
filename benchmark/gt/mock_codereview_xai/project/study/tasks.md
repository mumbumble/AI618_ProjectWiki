# Study Tasks: Code Review with ReviewLens

Explain Yourself, Reviewer. HCI user study, Hanbit University HCI Lab.
Prototype: ReviewLens v0.4 (v0.3 was used during the pilot only).
Main data collection: 2026-04-06 to 2026-05-15.

## Purpose

Each participant reviews four pull requests (PRs) with ReviewLens. Each task ID (T1-T4) names one defect family. The task list below is the list the participant works through during the session, and the IDs match the `task_id` column in the task logs.

## Design at a glance

- Within-subjects: every participant completes all four tasks under all three explanation conditions, giving 12 task runs per participant.
- Conditions (condition codes used in all data files):
  - `terse`: one-line verdict label only, e.g. "Possible bug: missing bounds check". No reasoning.
  - `rationale`: a short natural-language paragraph explaining why the comment was raised.
  - `trace`: the rationale plus highlighted code lines and a step-by-step execution/test trace that points to the defect.
- Condition order: six possible orders of the three conditions, assigned round-robin across P01-P10 (P01 terse, rationale, trace; P02 terse, trace, rationale; and so on, with P07 repeating the P01 order).
- PR variants: each condition uses a different PR variant (set A, B, or C) of every task, so no participant sees the same PR text twice.

## Task list

### T1: Off-by-one in pagination (Python)

The PR changes a paginated listing endpoint. Page boundaries are computed with an index that is off by one, so the last item of a page is dropped or repeated on the next page.

Participant goal: find the three seeded defects in the PR, decide for each AI comment whether to accept or reject it, and add any finding the assistant missed.

### T2: SQL injection in a query builder

The PR adds a filter feature to a small query builder. User-supplied filter values are concatenated into the SQL string instead of being passed as bound parameters.

Participant goal: same as T1.

### T3: Race condition in cache refresh

The PR changes a cache that refreshes entries in the background. A check-then-set sequence is not protected by a lock, so two refresh workers can overwrite each other's results.

Participant goal: same as T1.

Pilot revision: see the section "Changes after the pilot" below.

### T4: Unclosed file handle (resource leak)

The PR adds an export routine that opens a file, writes records, and returns early on one error path without closing the handle.

Participant goal: same as T1.

## Procedure for each task run

1. The participant opens the PR in the diff viewer (left pane). AI comments appear in the comment list (right pane).
2. The participant selects a comment. The explanation panel (below the diff) shows the explanation for that comment in the current condition.
3. For each AI comment, the participant presses Accept or Reject.
4. The participant may add their own findings as free text.
5. The participant presses "Next comment" to move through the list.
6. The timer (top right) allows 8 minutes (480 s) per task. When the time is up, the task ends and the participant moves on.
7. The condition is not shown in the participant interface.

After each task run (one per condition), the participant completes the post-task questionnaire (Q1-Q8, 7-point Likert).

## Measures recorded per task run

- `seconds`: time spent on the task run, capped at 480.
- `errors`: an integer from 0 to 3, equal to the seeded defects missed plus the wrong AI suggestions accepted.
- Review accuracy = 1 - errors / 3.

Survey measures (from the post-task questionnaire):
- Trust composite = mean of Q1, Q2, Q3.
- Q4-Q8 cover understanding, calibration, confidence, mental effort, and intention to use.

## Research questions and hypotheses

- RQ: How does the explanation style of an AI code-review assistant affect developers' trust and review accuracy?
- H1: Trust increases with explanation richness (trace > rationale > terse), measured by the trust composite.
- H2: The trace condition yields higher review accuracy (fewer errors per task) than the terse condition.

## Analysis plan

- Per-participant means for each condition (N = 10).
- Friedman test across the three conditions for the trust composite, task seconds, and task errors. Kendall's W as the effect size.
- Post-hoc Wilcoxon signed-rank tests for each pair of conditions, with Holm correction over the three comparisons.
- Results are reported with the task IDs above, so each task can be traced back to its row in the logs.

## Changes after the pilot

The pilot ran on 2026-03-12 and 2026-03-13 with 3 participants. Those sessions are not part of the main data.

The pilot found a problem with T3. The first T3 PR was 420 lines long, and one pilot participant needed 14 minutes to finish the task. In response, the T3 PR was trimmed to 160 lines and the task instructions were reworded. The 8-minute (480 s) limit was then applied to T3 as it is to every other task. The revised T3 is the version used in the main data collection. T1, T2, and T4 were not changed.
