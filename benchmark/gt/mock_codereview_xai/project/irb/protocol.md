# IRB Protocol: "Explain Yourself, Reviewer"

**Institution:** Hanbit University HCI Lab
**Protocol number:** HBU-IRB-2026-0417
**IRB approval date:** 2026-03-04
**Principal investigator:** Han Ji-woo (PhD student, hanjw@hanbit-hci.example)
**Advisor:** Prof. Seo Jun-ho
**Team:** Han Ji-woo (PI, analysis), Kwon Da-eun (MS, interviews and sessions), Yoon Min-seok (MS, prototype developer)
**Data collection window:** 2026-04-06 to 2026-05-15

## 1. Purpose

This study examines how the explanation style of an AI code-review assistant affects developers' trust in the assistant and their accuracy when reviewing pull requests. The prototype is called ReviewLens. We compare three explanation styles: a one-line verdict only (terse), a short natural-language rationale (rationale), and an evidence-linked trace with highlighted code lines and a step-by-step execution trace (trace).

## 2. Participants

We will recruit 10 professional or graduate-level software developers (target N = 10). Eligibility requires at least one year of professional or research programming experience and familiarity with Python and SQL. Participants are aged 24 to 38 (median 29), have 2 to 11 years of experience (median 5), and include 6 men and 4 women. Recruitment is by lab email and referral. Participation is voluntary, and no one is recruited from a dependent relationship with the investigators.

## 3. Study Design

The study uses a within-subjects design. Each participant completes all four review tasks under all three explanation conditions, giving 12 task runs per person. Condition order is counterbalanced across the six possible permutations using a rotation assigned round-robin across participants. Each condition uses a different pull-request variant (set A, B, or C) for every task, so no task is seen twice in identical form.

Tasks are described in study/tasks.md. They cover four common defect types: an off-by-one error in pagination (T1), SQL injection in a query builder (T2), a race condition in a cache refresh (T3), and an unclosed file handle (T4). Each pull request contains three seeded defects.

## 4. Procedure

Each session lasts about 90 minutes and is held in person in the lab, with one participant and one facilitator present.

1. **Consent (10 min).** The facilitator reviews the consent form in irb/consent_form.md, answers questions, and collects a signed copy.
2. **Training (10 min).** The participant is shown the ReviewLens interface and practices on a practice pull request that is not used in the analysis.
3. **Three condition blocks (about 15 min each, including the survey).** For each condition, the participant completes the four tasks. Each task has an 8-minute (480 s) limit. For every AI comment the participant marks Accept or Reject and may add their own findings. After the four tasks, the participant completes the post-condition questionnaire (eight 7-point Likert items).
4. **Semi-structured interview (15 min).** The interview is conducted in Korean and covers trust, understanding of explanations, ability to spot incorrect AI comments, confidence, mental effort, intention to use, and preferred style. Audio is recorded for this segment only.

Task times and error counts are recorded automatically by the prototype logger. Participants are not told which condition they are in. Condition labels are hidden from the participant interface.

## 5. Risks and Mitigation

The risks are minimal. Participants may experience fatigue from the 90-minute session or mild stress from the time limit and the review task. To reduce these risks, the session includes short breaks between condition blocks, the time limit is stated clearly before each task, and participants may pause or stop at any time. Participants are told explicitly that their performance is not evaluated for employment or course purposes.

A pilot with three participants (2026-03-12 and 2026-03-13) was used to test the materials. Those pilot participants are not part of the main data. Following the pilot, the T3 pull request was shortened and its instructions were reworded, and the 8-minute time limit was confirmed for all tasks.

## 6. Compensation

Each participant receives 30,000 KRW in cash or gift voucher at the end of the session. Compensation is not conditional on completing every task, so participants who withdraw early are still paid for the time spent.

## 7. Consent and Withdrawal

Written informed consent is obtained before any study activity, using the form at irb/consent_form.md. Participants may withdraw at any time, for any reason, without penalty. If a participant withdraws, their data collected up to that point are deleted on request.

## 8. Data Handling and Confidentiality

- **Identifiers:** Participants are identified only by pseudonymized IDs P01 to P10. The mapping between names and IDs is kept separately from the data and is accessible only to the PI.
- **Audio:** Audio is recorded only during the interview. Recordings are deleted within 6 months after transcription.
- **Storage:** All study data are stored on the lab server. Data are retained for 3 years from the end of the study and then deleted.
- **Access:** Access is limited to the four team members listed above.
- **Reporting:** Results are reported only in aggregate. No individual participant can be identified in publications or presentations.

## 9. Deviations and Amendments

Any change to procedures, materials, or data handling will be submitted to the IRB as an amendment before implementation. Deviations that affect participant safety or data protection will be reported to the IRB within five working days.

## 10. Contact

For questions about this protocol or to request withdrawal, contact Han Ji-woo at hanjw@hanbit-hci.example.
