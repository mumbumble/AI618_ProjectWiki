# Reading notes: Han & Oyelaran (2023), "Mid-Air Typing Under Fatigue"

Prepared by: 박서연 (Park Seoyeon), HCI Lab (HCIL), Hanbit University
Purpose: background for the VRType proposal and the planned ray vs. swipe comparison

---

## 1. Bibliographic summary

- **Citation:** Han & Oyelaran (2023). *Mid-Air Typing Under Fatigue.*
- **Sample:** n = 20 adults.
- **Question:** Which mid-air text-entry method is faster and less tiring in VR: a ray-casting keyboard or a mid-air tap keyboard?
- **Main takeaway:** Ray-casting was faster and held up better over time than mid-air tapping, and the authors recommended testing gesture-based (swipe) input next.

## 2. Conditions

| Condition | Description |
|---|---|
| Ray-casting keyboard | Virtual QWERTY panel in front of the user; a ray from the controller selects keys with the trigger. |
| Mid-air tap keyboard | Keys are pressed by tapping with the bare index finger in mid-air. |

Both conditions used a QWERTY layout. The authors did not test swipe or gesture typing.

## 3. Results

- **Speed:** Ray-casting averaged **17.2 WPM**; mid-air tap averaged **12.9 WPM**. The gap was large enough that the authors treated ray-casting as the more usable default.
- **Fatigue:** Reported arm fatigue increased after about **10 minutes** of continuous typing. The increase was larger for the mid-air tap keyboard.
- **Errors:** Error rates were reported, but the paper treats speed and fatigue as the main outcomes. Errors were not analyzed against speed in a trade-off framework.

## 4. What the authors recommended

The discussion section calls for:

1. Trying gesture or swipe input, since it might reduce the number of discrete taps and therefore the arm movement.
2. Measuring fatigue over longer sessions, not just a single block.
3. Reporting per-task results, so that short and long entries can be compared.

We will take up items 1 and 3 directly. Item 2 is only partly covered, because our sessions are capped at 60 minutes and we measure fatigue with a single Likert item (Q4) after each condition.

## 5. Limitations I noticed

- The sample was relatively small (n = 20), and the paper gives little detail on how participants were randomized or counterbalanced.
- Only one task type was used, so it is unclear whether the speed gap holds for short phrases versus URLs or passwords.
- Speed and errors were reported separately. A method that is faster but less accurate could look better than it really is.
- Fatigue was self-reported only. There was no physiological or range-of-motion measure.

## 6. How our study extends this work

The VRType study builds on Han & Oyelaran (2023) by replacing the mid-air tap keyboard with a **hand-tracking swipe keyboard**. Ray-casting stays as the comparison baseline, so the new comparison is swipe vs. ray.

**Research questions**

- RQ1: Is swipe text entry faster than ray-casting in VR?
- RQ2: Does swipe text entry produce more errors than ray-casting, i.e., is there a speed-accuracy trade-off?

**Hypotheses**

- **H1:** Swipe is faster than ray (lower seconds per task).
- **H2:** Swipe produces more errors than ray (speed-accuracy trade-off).

**Design**

- Within-subjects, 2 conditions (ray, swipe) x 4 tasks.
- N = 16 participants (P01-P16), with a Latin-square order: 8 start with ray and 8 start with swipe.
- Tasks are always presented in the same order (T1-T4) inside each condition.
- A 3-minute practice block precedes each condition.

**Tasks**

- T1: copy a short common phrase (5 words, from a 10-phrase set).
- T2: copy a two-sentence message (about 60 characters).
- T3: enter an 8-character password-like string with one digit and one symbol.
- T4: enter a URL (e.g., "hanbit.ac.kr/lab/news").

T3 was shortened during the pilot. The original 12-character random strings were too hard: 3 of 4 pilot participants gave up or took more than 2 minutes.

**Measures**

- Seconds per task (first stroke or key press to Enter).
- Errors per task: backspace-corrected errors plus uncorrected wrong characters or words.
- Derived speed in WPM, computed from T1 and T2.
- 7-point Likert survey (Q1-Q8) after each condition: ease of use, perceived speed, perceived accuracy, arm fatigue, mental demand, frustration, enjoyment, and willingness to use again.
- Semi-structured interview at the end of the session (about 10 minutes).

**Analysis plan**

- Two-sided Wilcoxon signed-rank tests on per-participant means, n = 16, alpha = .05.
- Separate tests for time and errors. No correction is applied between the two tests.
- Per-task breakdown for time and errors, as requested by the advisor on 2026-11-10.
- Survey items tested with the same Wilcoxon procedure, uncorrected.

## 7. Open points

- Han & Oyelaran reported WPM, not per-task seconds. Our WPM is derived from T1 and T2 only, so the numbers are not directly comparable to theirs.
- Their ray condition gives a useful reference for our ray baseline. We should check whether our ray speed is in a similar range.
- Fatigue should be reported alongside the speed-accuracy result, since the prior work found fatigue grows with time.
- For the January 2027 conference submission, we should cite this paper in the related work section and state clearly what we changed (swipe instead of mid-air tap, per-task reporting, and the error-speed trade-off).
