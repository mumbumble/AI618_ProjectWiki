"""VRType prototype application logic (app v0.3.3).

Two text-entry conditions for the VRType study:
  "ray"   - ray-casting keyboard driven by the dominant-hand controller
  "swipe" - bare-hand swipe keyboard driven by pinch strokes
"""
import math
import time

from logger import InteractionLogger

APP_VERSION = "0.3.3"
PANEL_DISTANCE_M = 0.7
KEY_WIDTH_CM = 2.6
HAND_TRACKING_HZ = 60
PINCH_THRESHOLD_M = 0.025
STROKE_POINTS = 64
BEAM_WIDTH = 8
TOP_K = 3
TASKS = ["T1", "T2", "T3", "T4"]
ROWS = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]
KEY_POS = {k: (c * KEY_WIDTH_CM, r * KEY_WIDTH_CM)
           for r, row in enumerate(ROWS) for c, k in enumerate(row)}


class OneEuroFilter:
    """Smooths the ray direction (min_cutoff 1.0, beta 0.007)."""

    def __init__(self, min_cutoff=1.0, beta=0.007, d_cutoff=1.0):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.x_prev = self.dx_prev = self.t_prev = None

    @staticmethod
    def _alpha(cutoff, dt):
        return 1.0 / (1.0 + (1.0 / (2 * math.pi * cutoff)) / dt)

    def __call__(self, x, t):
        if self.x_prev is None:
            self.x_prev, self.dx_prev, self.t_prev = x, 0.0, t
            return x
        dt = max(t - self.t_prev, 1e-6)
        dx = (x - self.x_prev) / dt
        a_d = self._alpha(self.d_cutoff, dt)
        dx_hat = a_d * dx + (1 - a_d) * self.dx_prev
        a = self._alpha(self.min_cutoff + self.beta * abs(dx_hat), dt)
        x_hat = a * x + (1 - a) * self.x_prev
        self.x_prev, self.dx_prev, self.t_prev = x_hat, dx_hat, t
        return x_hat


class RayKeyboard:
    """Ray hit-test on the virtual QWERTY panel; trigger press selects the key."""

    def __init__(self):
        self.smooth_x = OneEuroFilter()
        self.smooth_y = OneEuroFilter()

    def select(self, x_cm, y_cm, t, triggered):
        x, y = self.smooth_x(x_cm, t), self.smooth_y(y_cm, t)
        row, col = int(y // KEY_WIDTH_CM), int(x // KEY_WIDTH_CM)
        if triggered and 0 <= row < len(ROWS) and 0 <= col < len(ROWS[row]):
            return ROWS[row][col]
        return None


class HandTracker:
    """Wraps 60 Hz hand tracking: a pinch starts a stroke, release ends it."""

    def __init__(self):
        self.period = 1.0 / HAND_TRACKING_HZ
        self.pinching = False
        self.stroke = []

    def update(self, thumb, index, fingertip):
        pinch = math.dist(thumb, index) < PINCH_THRESHOLD_M
        if pinch and not self.pinching:
            self.stroke = []
        if pinch:
            self.stroke.append(fingertip)
        finished = self.pinching and not pinch
        self.pinching = pinch
        return list(self.stroke) if finished and self.stroke else None


class SwipeDecoder:
    """Matches a stroke to lexicon words: shape distance plus bigram log-prob."""

    def __init__(self, lexicon, bigram_logprob):
        self.lexicon = [w for w in lexicon if all(c.upper() in KEY_POS for c in w)]
        self.bigram_logprob = bigram_logprob

    @staticmethod
    def resample(points, n=STROKE_POINTS):
        last = len(points) - 1
        return [points[round(i * last / (n - 1))] for i in range(n)]

    def decode(self, stroke):
        if not stroke:
            return []
        path = self.resample(stroke)
        scored = []
        for word in self.lexicon:
            template = self.resample([KEY_POS[c.upper()] for c in word])
            shape = sum(math.dist(p, q) for p, q in zip(path, template)) / STROKE_POINTS
            scored.append((shape, word))
        beam = sorted(scored)[:BEAM_WIDTH]
        # Log-probs are negative, so subtracting them adds a penalty to unlikely words.
        ranked = sorted(beam, key=lambda s: s[0] - self.bigram_logprob(s[1]))
        return [w for _, w in ranked[:TOP_K]]


class TaskRunner:
    """Presents phrases in order, times each task and logs one row per task."""

    def __init__(self, participant, condition, prompts, logger):
        self.participant, self.condition = participant, condition
        self.prompts, self.logger = prompts, logger
        self.index, self.start, self.errors = 0, None, 0

    @property
    def task_id(self):
        return TASKS[self.index]

    def present(self):
        return self.task_id, self.prompts[self.task_id]

    def mark_first_input(self):
        if self.start is None:
            self.start = time.perf_counter()

    def finish(self, typed, target):
        uncorrected = sum(a != b for a, b in zip(typed, target)) + abs(len(typed) - len(target))
        seconds = round(time.perf_counter() - self.start, 1)
        self.logger.log_task(self.participant, self.condition, self.task_id,
                             seconds, self.errors + uncorrected)
        self.index += 1
        self.start, self.errors = None, 0
        return self.index < len(TASKS)


class VRTypeApp:
    """Routes controller and hand events to the active keyboard."""

    def __init__(self, participant, condition, prompts, lexicon, bigram_logprob):
        self.condition = condition  # "ray" or "swipe"
        self.keyboard = RayKeyboard()
        self.decoder = SwipeDecoder(lexicon, bigram_logprob)
        self.tracker = HandTracker()
        self.runner = TaskRunner(participant, condition, prompts, InteractionLogger())
        self.text = ""
        self.candidates = []

    def on_trigger(self, x_cm, y_cm, t):
        self.runner.mark_first_input()
        key = self.keyboard.select(x_cm, y_cm, t, triggered=True)
        if key:
            self.text += key  # ray mode also fires a 20 ms haptic pulse here

    def on_backspace(self):
        self.text = self.text[:-1]
        self.runner.errors += 1
        # Pilot bug (v0.3.2): the stroke buffer was not cleared after Backspace,
        # so the last word was duplicated on the next stroke. Fixed in v0.3.3.
        self.clear_stroke_buffer()

    def clear_stroke_buffer(self):
        self.candidates = []

    def on_hand_frame(self, thumb, index, fingertip):
        stroke = self.tracker.update(thumb, index, fingertip)
        if stroke:
            self.runner.mark_first_input()
            self.candidates = self.decoder.decode(stroke)
        return self.candidates

    def pick_candidate(self, position):
        if position < len(self.candidates):
            self.text += self.candidates[position] + " "
            self.clear_stroke_buffer()

    def submit(self):
        _, target = self.runner.present()
        more_tasks = self.runner.finish(self.text, target)
        self.text, self.candidates = "", []
        return more_tasks
