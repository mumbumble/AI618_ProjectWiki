# prototype/logger.py
# Interaction logger for ReviewLens (v0.4).
# Writes one row per participant x condition x task to data/task_logs.csv.
# Columns: participant,condition,task_id,seconds,errors

LOG_PATH = "data/task_logs.csv"
HEADER = "participant,condition,task_id,seconds,errors"
CONDITIONS = ("terse", "rationale", "trace")
TASK_IDS = ("T1", "T2", "T3", "T4")
TIME_LIMIT_S = 480      # 8 minutes per task
SEEDED_DEFECTS = 3      # each PR variant has 3 seeded defects


class InteractionLogger:
    """Appends task-level results to the study log CSV."""

    def __init__(self, path=LOG_PATH):
        self.path = path
        self._ensure_header()

    def _ensure_header(self):
        try:
            with open(self.path, "r") as f:
                first = f.readline().strip()
        except OSError:
            first = ""
        if first == "":
            with open(self.path, "w") as f:
                f.write(HEADER + "\n")
        elif first != HEADER:
            # never overwrite a file that holds data under another header
            raise ValueError("Unexpected header in " + self.path)

    def _validate(self, participant, condition, task_id, seconds, errors):
        if len(participant) != 3 or participant[0] != "P" or not participant[1:].isdigit():
            raise ValueError("Bad participant ID: " + participant)
        if condition not in CONDITIONS:
            raise ValueError("Unknown condition: " + condition)
        if task_id not in TASK_IDS:
            raise ValueError("Unknown task: " + task_id)
        if not 0 <= errors <= SEEDED_DEFECTS:
            raise ValueError("errors must be between 0 and 3")
        if seconds < 0:
            raise ValueError("seconds must be non-negative")

    def _already_logged(self, participant, condition, task_id):
        prefix = f"{participant},{condition},{task_id},"
        with open(self.path, "r") as f:
            return any(line.startswith(prefix) for line in f)

    @staticmethod
    def count_errors(missed_defects, wrong_accepted):
        # errors = seeded defects missed + wrong AI suggestions accepted
        return missed_defects + wrong_accepted

    def record_task(self, participant, condition, task_id, seconds, errors):
        self._validate(participant, condition, task_id, seconds, errors)
        if self._already_logged(participant, condition, task_id):
            raise ValueError(f"Duplicate row: {participant} {condition} {task_id}")
        # a task that runs past the limit is logged at the limit
        seconds = min(round(seconds, 1), TIME_LIMIT_S)
        row = f"{participant},{condition},{task_id},{seconds},{errors}"
        with open(self.path, "a") as f:
            f.write(row + "\n")
        return row

    def rows_for(self, participant):
        with open(self.path, "r") as f:
            lines = [line.strip() for line in f][1:]
        return [line for line in lines if line.startswith(participant + ",")]


if __name__ == "__main__":
    log = InteractionLogger()
    log.record_task("P01", "terse", "T1", 212.4, 2)
    print(log.rows_for("P01"))
