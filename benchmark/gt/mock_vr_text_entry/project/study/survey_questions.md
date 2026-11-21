# Post-Condition Questionnaire (Q1-Q8)

VRType study, HCI Lab (HCIL), Hanbit University
Protocol: HCIL-IRB-2026-031

## Purpose

This short questionnaire captures how each participant experienced each text-entry method right after completing it. It is answered once per condition, so every participant (P01-P16) gives two sets of ratings:

- `ray`: Ray-casting keyboard
- `swipe`: Hand-tracking swipe keyboard

The eight items map onto the perceived and experiential measures in the study proposal. The same constructs are explored further in the end-of-session interview.

## When it is administered

1. Participant completes the 3-minute practice for the condition.
2. Participant completes tasks T1-T4 in that condition, in fixed order.
3. Participant takes off the headset (or pauses) and answers Q1-Q8.
4. The next condition starts after the survey. Condition order follows the Latin square (8 participants start with `ray`, 8 start with `swipe`).

The questionnaire should take no more than about two minutes. Participants may skip any item, but the facilitator should ask them to answer and note any skipped items.

## Response scale

All items use a 7-point Likert scale:

| Value | Anchor |
|-------|--------|
| 1 | Strongly disagree |
| 2 | Disagree |
| 3 | Somewhat disagree |
| 4 | Neither agree nor disagree |
| 5 | Somewhat agree |
| 6 | Agree |
| 7 | Strongly agree |

Scores are recorded as integers from 1 to 7. Ratings are not reverse-coded. For Q4, a higher value always means more arm fatigue.

## Items

| ID | Construct | Item wording (English master) |
|----|-----------|-------------------------------|
| Q1 | Ease of use | The keyboard was easy to use. |
| Q2 | Perceived speed | I felt I could enter text quickly with this keyboard. |
| Q3 | Perceived accuracy | I felt I entered the text accurately with this keyboard. |
| Q4 | Arm fatigue (higher = more fatigue) | My arm felt tired after using this keyboard. |
| Q5 | Mental demand | Entering text with this keyboard required a lot of mental effort. |
| Q6 | Frustration | I felt frustrated while entering text with this keyboard. |
| Q7 | Enjoyment | I enjoyed entering text with this keyboard. |
| Q8 | Willingness to use again | I would be willing to use this keyboard again. |

The Korean wording used in sessions must match these items one-to-one. Any change to wording after the pilot must be recorded and reported.

## Data recording

Each completed questionnaire produces one row with:

- `participant` (P01-P16)
- `condition` (`ray` or `swipe`)
- `Q1`, `Q2`, `Q3`, `Q4`, `Q5`, `Q6`, `Q7`, `Q8` (integers 1-7)

That gives 32 rows for the full sample (16 participants x 2 conditions). Responses are stored pseudonymized on the lab server. Participant names never appear in the response records.

## Analysis plan

- Each item is compared between `ray` and `swipe` within participants using a two-sided Wilcoxon signed-rank test, alpha = .05.
- Results are reported per item, with the mean rating per condition and a 95% confidence interval.
- Q2 (perceived speed) and Q3 (perceived accuracy) are interpreted alongside the logged task times and error counts, since the hypotheses concern objective speed (H1) and errors (H2).
- Q4 is reported with particular attention because arm fatigue is a known concern for mid-air input.

## Notes for facilitators

- Read each item aloud exactly as written, then wait for the answer before continuing.
- Do not explain the difference between conditions or hint at which method is expected to be better.
- If a participant reports cybersickness or strong arm discomfort, pause the questionnaire, check on the participant, and remind them they may stop at any time.
