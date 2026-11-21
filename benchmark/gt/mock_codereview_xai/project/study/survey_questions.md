# Post-Task Questionnaire (Q1–Q8)

**Project:** Explain Yourself, Reviewer (Hanbit University HCI Lab)
**Prototype:** ReviewLens v0.4 (main study)
**IRB protocol:** HBU-IRB-2026-0417
**Owner:** Han Ji-woo (PI)

## 1. Purpose

This questionnaire measures how developers experienced the AI code-review assistant under each explanation style. It is completed once per condition, so each participant fills it in three times. Together with the task-level measures (time and errors), the items feed the trust, understanding, calibration, confidence, workload, and intention constructs used in the analysis.

## 2. When it is administered

- Each participant completes all four review tasks under one explanation condition.
- Immediately after the fourth task of that condition, the participant completes the eight items below on the lab laptop.
- The next condition starts only after the survey is submitted.
- Each condition block, including the survey, takes about 15 minutes.
- Across 10 participants and 3 conditions, this gives 30 completed questionnaires.

## 3. Response scale

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

## 4. Instructions to participants

> "Please think about the review comments the assistant gave you during the last four tasks. Rate each statement from 1 (strongly disagree) to 7 (strongly agree). There are no right or wrong answers. Your honest impression is what we need."

The condition code (terse, rationale, or trace) is never shown to participants. Participants may skip the questionnaire or stop the session at any point without penalty.

## 5. Items

| ID | Item text | Construct | Direction |
|----|-----------|-----------|-----------|
| Q1 | I trusted the assistant's review comments. | Trust | Higher = more trust |
| Q2 | I believe the assistant's comments were reliable. | Trust | Higher = more trust |
| Q3 | I felt comfortable relying on the assistant for this review. | Trust | Higher = more trust |
| Q4 | I understood why the assistant raised each comment. | Understanding | Higher = more understanding |
| Q5 | The explanations helped me notice when the assistant was wrong. | Calibration | Higher = better calibration |
| Q6 | I was confident in my final review decisions. | Confidence | Higher = more confidence |
| Q7 | The review required a lot of mental effort. | Workload | Higher = more effort (not reverse-coded) |
| Q8 | I would like to use this assistant in my daily work. | Intention to use | Higher = more intention |

## 6. Scoring

- **Trust composite** = mean of Q1, Q2, and Q3, giving a score from 1 to 7. This is the primary outcome for H1.
- **Q7 (workload)** is not reverse-coded. A higher score means the review felt more effortful.
- Items Q4 to Q6 and Q8 are analysed individually as item-level measures.
- No item is reverse-coded anywhere in the dataset.

## 7. Data format

Responses are entered as integers from 1 to 7, one row per participant per condition. Columns are:

- `participant`: pseudonymized ID, P01 to P10
- `condition`: terse, rationale, or trace
- `Q1` to `Q8`: item responses, in the order listed in Section 5

Each participant therefore contributes exactly three rows. Missing responses are left blank and are not imputed.

## 8. Condition reference

- **terse**: a one-line verdict label only, with no reasoning.
- **rationale**: a short natural-language paragraph explaining why the comment was raised.
- **trace**: the rationale plus highlighted code lines and a step-by-step execution trace that points to the defect.

## 9. Link to research questions and hypotheses

- **RQ:** How does the explanation style of an AI code-review assistant affect developers' trust and review accuracy?
- **H1:** Trust increases with explanation richness (trace > rationale > terse). Measured by the trust composite (Q1 to Q3).
- **H2:** The trace style yields higher review accuracy (fewer errors per task) than the terse style. Accuracy is measured from task logs, not from this questionnaire. Q4 and Q5 help interpret whether any accuracy difference reflects better understanding and calibration.

## 10. Measures in the study

1. Trust (Q1 to Q3, composite)
2. Understanding of explanations (Q4)
3. Calibration, i.e. noticing when the assistant is wrong (Q5)
4. Confidence in final decisions (Q6)
5. Perceived mental effort (Q7)
6. Intention to use the assistant (Q8)

Task time and error counts are recorded automatically by the prototype and are reported separately from these items.

## 11. Alignment with the interview

The semi-structured interview, conducted in Korean after all three blocks, asks about the same constructs: trust, understanding of explanations, ability to spot wrong AI comments, confidence, mental effort, intention to use, and preferred explanation style. Interview answers are used to explain questionnaire patterns, not to replace them.

## 12. Notes for administrators

- Read the instructions in Section 4 verbatim before each block.
- Do not comment on the participant's ratings or on the assistant's accuracy during the survey.
- If a participant asks what a term means, repeat the item text and offer no further definition.
- Check that all eight items are answered before the participant moves to the next condition.
- Session facilitators: Kwon Da-eun (sessions), Yoon Min-seok (prototype setup).
- Questions about this instrument: hanjw@hanbit-hci.example
