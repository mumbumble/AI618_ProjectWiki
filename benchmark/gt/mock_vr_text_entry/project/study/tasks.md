# VRType Task List

This document lists the four text-entry tasks (T1–T4) that every participant completes in each condition of the VRType study. The task IDs below are the same IDs written to the interaction log, so each log row can be matched to a task here.

## Conditions

- `ray`: Ray-casting keyboard. A virtual QWERTY panel sits 0.7 m in front of the participant. A ray from the dominant-hand controller points at keys, and a trigger press selects a key.
- `swipe`: Hand-tracking swipe keyboard. A pinch (thumb-index distance under 0.025 m) starts a stroke, the fingertip glides over the letters, and releasing the pinch ends the stroke. Three candidate words appear in the candidate bar.

## Task Sequence

Within each condition the tasks always run in the same order, T1 through T4. Each condition starts with a 3-minute practice period. Condition order follows a Latin square: 8 participants start with `ray` and 8 start with `swipe`.

| ID | Task | Content | Example |
|----|------|---------|---------|
| T1 | Copy a short common phrase | 5 words, drawn from a set of 10 common phrases | "see you at the lab" |
| T2 | Copy a two-sentence message | About 60 characters in total | A short reminder message shown on the prompt line |
| T3 | Enter a password-like string | Exactly 8 characters, with one digit and one symbol | "k7#Lm2qP" |
| T4 | Enter a URL | A lowercase web address | "hanbit.ac.kr/lab/news" |

The prompt for each task is shown at the top of the view. The participant copies it exactly as written.

## Procedure for Each Task

1. The experimenter starts the task, and TaskRunner shows the phrase prompt.
2. The timer starts at the first key press (`ray`) or the first stroke (`swipe`).
3. The participant types the text. Backspace may be used to correct mistakes.
4. The participant presses the green Enter button to finish. The timer stops.
5. TaskRunner advances to the next task.

Participants may stop at any time. Each session lasts at most 60 minutes, including the questionnaires and the interview.

## Measures Recorded per Task

- **seconds**: time from the first key press or stroke to the Enter press.
- **errors**: backspace-corrected errors plus any wrong characters or words left uncorrected at Enter.
- **WPM**: derived from T1 and T2 only, as the standard speed measure for copy tasks.

Each task produces one row in the study log with the columns `participant, condition, task_id, seconds, errors`. For example, `P01,ray,T1,23.1,1` means participant P01 completed T1 in the ray condition in 23.1 seconds with one error. Each participant produces 8 rows (2 conditions × 4 tasks), so the main study yields 128 rows for 16 participants.

## Relation to the Study Design

- **Research questions**: How do a ray-casting keyboard and a hand-tracking swipe keyboard differ in entry speed and error rate in VR?
- **H1**: Swipe is faster than ray (lower seconds per task).
- **H2**: Swipe produces more errors than ray (a speed-accuracy trade-off).
- **Design**: Within-subjects, 2 conditions × 4 tasks, N = 16 adults (P01–P16).
- **Analysis**: Two-sided Wilcoxon signed-rank tests on per-participant means, with alpha at .05. The per-task breakdown in T1–T4 is reported alongside the overall means.

## Change after the Pilot

The pilot ran from 25 to 28 August 2026 with 4 participants on app v0.3.2. In the first version of the pilot, T3 used 12-character random strings. Three of the four pilot participants gave up or took more than 2 minutes on this task. Because of this, T3 was changed to the current 8-character string with one digit and one symbol before the main study. The main study ran from 14 September to 2 October 2026 on app v0.3.3. The pilot-session notes (in Korean) record the original task, the timing problem, and the reason for the change.

No other task was changed after the pilot. T1, T2, and T4 are the same in the pilot and the main study.
