"""ReviewLens prototype server (v0.4); the condition is never shown to participants."""
import json
import os
import time

from flask import Flask, jsonify, request, session

from logger import InteractionLogger

PROTOTYPE_VERSION = "v0.4"
TIME_LIMIT_S = 480  # 8 minutes per task
TASKS = ["T1", "T2", "T3", "T4"]
VARIANTS = ["A", "B", "C"]  # PR variant used by each condition block
PERMUTATIONS = [  # assigned round-robin over participants; P07 repeats P01
    ["terse", "rationale", "trace"], ["terse", "trace", "rationale"],
    ["rationale", "terse", "trace"], ["rationale", "trace", "terse"],
    ["trace", "terse", "rationale"], ["trace", "rationale", "terse"],
]
PR_ROOT = os.path.join("study", "prs")

app = Flask(__name__)
app.secret_key = os.environ.get("REVIEWLENS_KEY", "dev-only")
logger = InteractionLogger()  # writes to the study data folder
_explanation_cache = {}


def load_pr(task_id, variant):
    path = os.path.join(PR_ROOT, task_id, variant + ".json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def explanation_for(condition, comment):
    # v0.4 fix: the pilot cache was keyed on comment index only, so a quick
    # "Next comment" press showed the previous comment's explanation.
    key = (condition, comment["id"])
    if key not in _explanation_cache:
        view = {"verdict": comment["verdict"]}  # terse: label only
        if condition in ("rationale", "trace"):
            view["rationale"] = comment["rationale"]
        if condition == "trace":
            view["lines"] = comment["lines"]
            view["trace"] = comment["trace"]
        _explanation_cache[key] = view
    return _explanation_cache[key]


@app.post("/session")
def start_session():
    pid = request.get_json()["participant"]
    order = PERMUTATIONS[(int(pid.lstrip("P")) - 1) % len(PERMUTATIONS)]
    session.clear()
    session["participant"] = pid
    session["order"] = order
    session["step"] = 0  # 0-11: four tasks in each of three condition blocks
    return jsonify(version=PROTOTYPE_VERSION, time_limit=TIME_LIMIT_S)


@app.get("/task")
def show_task():
    condition = session["order"][session["step"] // len(TASKS)]
    task_id = TASKS[session["step"] % len(TASKS)]
    variant = VARIANTS[session["step"] // len(TASKS)]
    pr = load_pr(task_id, variant)
    session["task"] = {"id": task_id, "variant": variant, "condition": condition,
                       "started": time.time(), "decisions": {}}
    comments = [{"id": c["id"], "line": c["line"]} for c in pr["comments"]]
    return jsonify(task=task_id, diff=pr["diff"], comments=comments)


@app.get("/comment/<comment_id>")
def show_comment(comment_id):
    task = session["task"]
    pr = load_pr(task["id"], task["variant"])
    comment = next(c for c in pr["comments"] if c["id"] == comment_id)
    return jsonify(explanation_for(task["condition"], comment))


@app.post("/decision")
def record_decision():
    body = request.get_json()
    session["task"]["decisions"][body["comment_id"]] = body["action"]
    session.modified = True
    return jsonify(ok=True)


@app.post("/finish")
def finish_task():
    task = session["task"]
    pr = load_pr(task["id"], task["variant"])
    seconds = round(min(time.time() - task["started"], TIME_LIMIT_S), 1)
    found = set(request.get_json().get("found", []))  # seeded defects marked
    missed = sum(1 for d in pr["seeded_defects"] if d not in found)
    wrong = sum(1 for c in pr["comments"] if not c["valid"]
                and task["decisions"].get(c["id"]) == "accept")
    errors = min(missed + wrong, len(pr["seeded_defects"]))
    logger.log_task(session["participant"], task["condition"],
                    task["id"], seconds, errors)
    session["step"] += 1
    session.modified = True
    return jsonify(seconds=seconds, errors=errors,
                   done=session["step"] == len(TASKS) * len(VARIANTS))
