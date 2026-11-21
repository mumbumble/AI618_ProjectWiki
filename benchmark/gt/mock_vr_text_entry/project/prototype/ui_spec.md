# VRType Prototype: UI Specification

Prototype build: v0.3.3 (main study). Entry point: `prototype/app.py`.
Owner: 이도윤 (Lee Doyun), prototype developer. Study lead: 박서연 (Park Seoyeon).

## 1. Purpose

This document describes what the participant sees and does in the VRType prototype. The app runs on the fictional Aurora V2 headset, which provides built-in hand tracking and controllers. It supports two text-entry conditions, labelled exactly `ray` (Ray-casting keyboard) and `swipe` (Hand-tracking swipe keyboard).

## 2. Scene layout

- **Phrase prompt:** fixed at the top of the view. It shows the phrase or string the participant must copy for the current task (T1 to T4).
- **Condition badge:** shows `RAY` or `SWIPE` so the condition is always visible to the facilitator and participant.
- **Text field:** sits directly above the keyboard panel and shows what has been entered so far.
- **Candidate bar:** shown in swipe mode only. It has three word slots under the text field, filled by SwipeDecoder.
- **Keyboard panel:** a QWERTY layout placed 0.7 m in front of the participant's starting position.
- **Enter button:** green, at the lower right of the keyboard panel. Pressing it ends the current task.

## 3. Ray condition (`ray`)

- The keyboard is a virtual QWERTY panel. Key width is 2.6 cm.
- A ray comes from the dominant-hand controller. The participant points at a key and presses the trigger to select it.
- RayKeyboard performs the ray hit-test and trigger select.
- Ray direction is smoothed with a One-Euro filter (min_cutoff 1.0, beta 0.007) to reduce jitter without adding much lag.
- Each key select gives a 20 ms haptic pulse on the controller.
- The candidate bar is hidden in this mode.

## 4. Swipe condition (`swipe`)

- Hands are tracked bare-handed at 60 Hz through HandTracker.
- A pinch starts a stroke. The pinch threshold is a thumb-index distance below 0.025 m.
- The participant glides the index fingertip over the letters. The path is recorded while the pinch is held.
- Releasing the pinch ends the stroke.
- Each stroke is resampled to 64 points before matching.
- SwipeDecoder matches the stroke against a 20,000-word lexicon. The score combines path-shape distance with a bigram language-model log-probability. Beam width is 8.
- The candidate bar shows the top three words, best first.
- Pressing Backspace removes the last character. It also calls `clear_stroke_buffer()`, so the previous stroke cannot be reused (see section 7).

## 5. Task flow

TaskRunner controls the session. The flow for each condition is:

1. A 3-minute practice block, which is not logged.
2. Tasks T1, T2, T3, T4 in this fixed order. TaskRunner shows the prompt and advances to the next task after Enter.

Task content:

| ID | Task | Content |
|----|------|---------|
| T1 | Copy a short phrase | 5 words, drawn from a set of 10 common phrases |
| T2 | Copy a message | Two sentences, about 60 characters |
| T3 | Enter a password-like string | 8 characters, including one digit and one symbol |
| T4 | Enter a URL | For example `hanbit.ac.kr/lab/news` |

Timing starts at the first key press or first stroke of the task and stops at Enter.

## 6. Logging

- InteractionLogger exposes `log_task(participant, condition, task_id, seconds, errors)`.
- Each call appends one row to the study log CSV. The header is written when the file is first created.
- Columns: `participant,condition,task_id,seconds,errors`.
- Participants are coded P01 to P16. Example row: `P01,ray,T1,23.1,1`.
- `errors` counts backspace-corrected errors plus uncorrected wrong characters or words.

## 7. Known issues and changes

- **Pilot bug (v0.3.2):** in swipe mode, pressing Backspace did not clear the previous stroke buffer. The last word was duplicated on the next stroke. This was fixed in v0.3.3 by calling `clear_stroke_buffer()` on Backspace. Pilot data from v0.3.2 should be read with this in mind.
- **T3 change:** T3 originally used 12-character random strings. In the pilot, 3 of 4 participants gave up or took more than 2 minutes, so T3 was changed to the 8-character string with one digit and one symbol before the main study.

## 8. Component summary

| Component | Responsibility |
|-----------|----------------|
| RayKeyboard | Ray hit-test and trigger select |
| SwipeDecoder | Stroke matching, lexicon lookup, top-3 candidates |
| HandTracker | Wrapper around Aurora V2 hand tracking at 60 Hz |
| TaskRunner | Presents phrases and advances tasks |
| InteractionLogger | Writes one CSV row per completed task |

## 9. Open items

- Confirm the controller haptic amplitude on the Aurora V2 firmware before the next session.
- Keep the 0.7 m panel distance and 2.6 cm key width fixed across both conditions for all participants.
