# ReviewLens UI Specification

**Prototype:** ReviewLens (AI code-review assistant)
**Version:** v0.4 (v0.3 was used during the pilot; v0.4 is the build used for data collection)
**Implementation:** `prototype/app.py`
**Prototype developer:** Yoon Min-seok

## 1. Purpose

This document describes the participant-facing interface that `prototype/app.py` renders during a review task. The interface shows one pull request (PR) diff, a list of AI review comments, and an explanation for the selected comment. Participants review each PR for defects, accept or reject each AI comment, and may add their own findings. The explanation style is controlled by the session and is never shown as a label to the participant.

## 2. Screen Layout

```
+---------------------------------------------------------------+
| ReviewLens  Task T1 (Set B)                    Time 07:42     |
+-----------------------------+---------------------------------+
| Diff viewer                 | AI comments                     |
|  (PR file, line numbers,    |  1. Possible bug: ...  [ ]      |
|   highlight on selection)   |  2. Style: ...         [ ]      |
|                             |  3. ...                [ ]      |
|                             |                                 |
|                             | [ Next comment ]                |
+-----------------------------+---------------------------------+
| Explanation panel (content depends on session explanation style)|
|                                                               |
| [ Accept ]   [ Reject ]   Own finding: [____________] [Add]   |
+---------------------------------------------------------------+
```

## 3. Components

| Component | Behavior |
|---|---|
| Diff viewer (left pane) | Shows the PR file for the current task. Line numbers are always visible. Lines referenced by the current comment are highlighted only when the session style is `trace`. |
| Comment list (right pane) | Lists all AI comments for the PR variant, in the order the assistant produced them. The selected comment is marked. Each comment shows its one-line verdict label. |
| Explanation panel (below) | Shows the explanation for the selected comment, rendered according to the session style (see Section 4). |
| Accept / Reject buttons | Record a decision for the selected comment. Exactly one decision per comment; a decision can be changed until the participant presses "Next comment". |
| Next comment button | Moves selection to the next comment in the list. Disabled on the last comment. |
| Own finding field | Free-text field with an "Add" button. Participants use it to report a defect the AI did not raise. Each added finding is stored with the task ID. |
| Timer (top right) | Counts down from 08:00 (480 s). Turns amber at 01:00 remaining. |

## 4. Explanation Styles

The session supplies one of three condition codes: `terse`, `rationale`, or `trace`. The code is used internally only.

- **terse**: the explanation panel shows the verdict label only (for example, "Possible bug: missing bounds check"). No reasoning text, no code highlighting, no trace.
- **rationale**: the panel shows a short paragraph (two to four sentences) explaining why the comment was raised.
- **trace**: the panel shows the rationale paragraph, plus the highlighted code lines in the diff viewer, plus a step-by-step execution or test trace that points to the defect.

The participant interface must not show the words "terse", "rationale", or "trace", and must not show the condition number or name in any label, title, or tooltip.

## 5. Task Flow

1. The participant opens a task. The app loads the PR variant set (A, B, or C) assigned to the current condition for that task ID (T1 to T4).
2. The timer starts at 480 seconds. The first AI comment is selected.
3. For each comment, the participant reads the explanation panel, then presses Accept or Reject.
4. The participant may add own findings at any time during the task.
5. The task ends when the participant presses "Finish task" or when the timer reaches 00:00. At 00:00 all decision and text controls are disabled, and the app shows a notice that the task has ended.
6. The app then hands control to the post-task questionnaire for that condition.

Each participant completes four tasks per condition and three conditions in total. Condition order is set per participant in the session configuration.

## 6. Explanation Cache

The explanation panel caches rendered explanations to avoid flicker when participants move quickly between comments. The cache key is the pair `(condition, comment_id)`.

In v0.3 the cache was keyed only on the comment index. When a participant pressed "Next comment" quickly, the panel could show the explanation of the previous comment. This was found in the pilot and fixed in v0.4. Any change to the cache must keep the `(condition, comment_id)` key.

## 7. Data Recorded

The app records the following events for each task, with the pseudonymized participant ID (P01 to P10), condition code, task ID, and a timestamp:

- task start and task end (including whether the task ended by timeout)
- each comment selection
- each Accept or Reject decision, including changes
- each own finding, with its text
- elapsed seconds for the task

Seconds per task are calculated from task start and task end. Error counts are not computed in the UI; they are derived after the session from the recorded decisions and the seeded defects in each PR variant.

## 8. Changes from v0.3 to v0.4

- Explanation cache keyed on `(condition, comment_id)` (fixes stale explanations on fast navigation).
- Timer fixed at 480 seconds per task. Pilot sessions had a longer limit, and one pilot participant took 14 minutes on a single task, so the limit was enforced in the timer.
- Task T3 PR variants were reduced in size (diff trimmed to about 160 lines) before data collection.
- Condition code removed from all visible labels.

## 9. Known Limitations

- The diff viewer does not support syntax-aware folding; long files require scrolling.
- Own findings are free text only. They are not matched automatically against the seeded defects; this is done manually.
- The interface supports one active task at a time. Participants cannot return to a previous task after finishing it.
- The app is tested on desktop browsers only. Mobile layouts are not supported.
