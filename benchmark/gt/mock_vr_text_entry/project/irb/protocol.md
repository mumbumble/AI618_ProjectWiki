# IRB Protocol: VRType Study

**Study title:** VRType: Comparing ray-casting and hand-tracking swipe text entry in VR
**Protocol number:** HCIL-IRB-2026-031
**IRB approval date:** 2026-07-08
**Lab:** HCI Lab (HCIL), Hanbit University
**Lead researcher:** 박서연 (Park Seoyeon), MSc student
**Advisor (PI):** 김태호 (Kim Taeho), Professor
**Pilot facilitator:** 최민준 (Choi Minjun), Research Assistant

---

## 1. Purpose

This study compares two text-entry methods for a commercial-style VR headset. The ray-casting keyboard ("ray") uses a controller ray and trigger press to select keys. The hand-tracking swipe keyboard ("swipe") uses bare-hand tracking, where a pinch starts a stroke and the fingertip glides over letters.

We test two hypotheses:

- **H1:** Swipe entry is faster than ray entry (lower seconds per task).
- **H2:** Swipe entry produces more errors than ray entry, consistent with a speed-accuracy trade-off.

We also record arm fatigue, perceived workload, and user preference. The study extends earlier work on mid-air typing under fatigue by testing a gesture-based method against ray-casting.

## 2. Study Design

- Within-subjects design with 2 conditions (ray, swipe) and 4 tasks per condition.
- Condition order follows a Latin square: 8 participants start with ray and 8 start with swipe.
- Tasks are always presented in the same order (T1 to T4) inside a condition. The task definitions are in study/tasks.md.
- Each condition begins with a 3-minute practice period.

## 3. Participants

- Target sample: 16 adults aged 20 to 34.
- Inclusion: age 20 to 34, right-handed, normal or corrected-to-normal vision, no known vestibular disorder.
- Exclusion: any current condition that would make arm use or headset wear unsafe.
- Participants are coded P01 to P16 in all records.
- Compensation: 15,000 KRW for the session.

Participants will be recruited through lab postings. Recruitment materials state that participation is voluntary and that participants may stop at any time.

## 4. Procedure

Each session lasts no more than 60 minutes. The steps are:

1. **Arrival and consent (about 5 minutes).** The researcher explains the study and the risks. The participant reads and signs the consent form (irb/consent_form.md). Questions are answered before the session begins.
2. **Screening check (about 2 minutes).** The researcher confirms handedness, age, and any relevant health conditions.
3. **Headset fitting.** The researcher fits the Aurora V2 headset and checks comfort and visibility.
4. **Condition 1 (about 20 minutes).** The participant completes a 3-minute practice period, then tasks T1 to T4. A post-condition questionnaire (Q1 to Q8, 7-point Likert) follows.
5. **Short break.** The participant removes the headset and rests for at least 3 minutes.
6. **Condition 2 (about 20 minutes).** Same structure as condition 1, with the other input method.
7. **Semi-structured interview (about 10 minutes).** Questions cover perceived speed, accuracy and errors, arm fatigue, enjoyment, mental effort and frustration, willingness to reuse, and preferred method with reasons. The interview is audio recorded with consent.
8. **Debrief and payment.** The researcher thanks the participant and provides the compensation.

During tasks, the system records the time per task and the number of errors. Errors include corrected errors (counted by backspace) and uncorrected wrong characters or words.

## 5. Pilot Phase

A pilot was conducted from 2026-08-25 to 2026-08-28 with 4 participants using app version v0.3.2. The pilot revealed a bug in swipe mode: after Backspace, the previous stroke buffer was not cleared, which duplicated the last word on the next stroke. This was fixed in v0.3.3, which was used for the main study.

The pilot also showed that the original T3 task (12-character random strings) caused 3 of 4 participants to give up or take more than 2 minutes. T3 was revised to an 8-character password-like string with one digit and one symbol. Pilot data are not included in the main analysis.

## 6. Main Study Dates

The main study ran from 2026-09-14 to 2026-10-02 with app version v0.3.3.

## 7. Risks and Mitigation

| Risk | Description | Mitigation |
|---|---|---|
| Cybersickness | Nausea, dizziness, or disorientation during headset use | Sessions are capped at 60 minutes. Breaks are offered between conditions. The researcher watches for symptoms and ends the session if needed. |
| Arm fatigue | Discomfort from holding the arm up during mid-air input | Keyboard panel is placed 0.7 m in front. Practice and tasks are short. Participants may rest at any time. Fatigue is measured with Q4. |
| Eye or head strain | Discomfort from headset use | Headset is adjusted before use. Participants can remove it at any time. |
| Frustration | Difficulty completing tasks | Practice is provided. Participants may skip a task on request. |

Participants may stop at any time without penalty. If a participant stops early, the data collected up to that point are kept only if the participant agrees.

Tracking loss may occur during swipe tasks. If it occurs, the researcher records it in the session notes. Data are kept unless the participant asks for removal. For example, P09 had a brief tracking loss on swipe T2 and the data were kept.

## 8. Data Handling

- All participants are coded P01 to P16. The name key is stored separately from study data and is not shared outside the research team.
- Task timing, error counts, and survey responses are stored on the lab server in pseudonymized form.
- Interview audio recordings are deleted 6 months after the study end date (2026-10-02), so by early April 2027.
- Only the research team (박서연, 김태호, 이도윤, 정하은, 최민준) has access to identifiable data. Access is limited to pseudonymized data for analysis.
- Results are reported in aggregate. No individual participant can be identified in publications.

## 9. Ethical Considerations

Participation is voluntary. Participants may withdraw at any time before the data are analyzed. Withdrawal does not affect compensation.

## 10. Contacts

- **Researcher:** 박서연 (Park Seoyeon), HCI Lab, Hanbit University
- **Advisor:** 김태호 (Kim Taeho), Professor, HCI Lab, Hanbit University
- **IRB questions:** Contact the Hanbit University IRB office with protocol number HCIL-IRB-2026-031.
