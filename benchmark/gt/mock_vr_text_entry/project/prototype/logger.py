"""Interaction logger for the VRType study.

Appends one row per task to data/task_logs.csv. The header is written
when the file is created. Columns:
participant, condition, task_id, seconds, errors
"""
import csv
import os

LOG_PATH = "data/task_logs.csv"
FIELDS = ["participant", "condition", "task_id", "seconds", "errors"]
VALID_CONDITIONS = {"ray", "swipe"}
VALID_TASKS = {"T1", "T2", "T3", "T4"}


class InteractionLogger:
    def __init__(self, path=LOG_PATH):
        self.path = path
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)

    def log_task(self, participant, condition, task_id, seconds, errors):
        """Append one task result.

        participant: pseudonymized ID, e.g. "P01"
        condition:   "ray" (ray-casting keyboard) or "swipe" (hand-tracking swipe)
        task_id:     "T1" to "T4"
        seconds:     time from first stroke/press to Enter
        errors:      backspace-corrected errors plus uncorrected wrong characters/words
        """
        if condition not in VALID_CONDITIONS:
            raise ValueError(f"unknown condition: {condition!r}")
        if task_id not in VALID_TASKS:
            raise ValueError(f"unknown task id: {task_id!r}")
        if seconds < 0:
            raise ValueError("seconds must be non-negative")
        if errors < 0:
            raise ValueError("errors must be non-negative")

        is_new = not os.path.exists(self.path) or os.path.getsize(self.path) == 0
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            if is_new:
                writer.writeheader()
            writer.writerow({
                "participant": participant,
                "condition": condition,
                "task_id": task_id,
                "seconds": f"{seconds:.1f}",
                "errors": int(errors),
            })


if __name__ == "__main__":
    logger = InteractionLogger()
    logger.log_task("P01", "ray", "T1", 23.1, 1)
    print(f"Row written to {logger.path}")
