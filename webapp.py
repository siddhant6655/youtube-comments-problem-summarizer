"""Local web frontend for the problem-scraper pipeline. Run with `python webapp.py`
and open http://127.0.0.1:5050 — single-user, local-only, not for public deployment."""

import threading
import uuid
from dataclasses import asdict

import netfix  # noqa: F401 — must import before anything opens a network connection
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from pipeline import run
from reporting.formatter import save_csv, save_json

load_dotenv()

app = Flask(__name__)

# In-memory job store. Fine for a local, single-user tool; not multi-process safe.
JOBS: dict[str, dict] = {}

# Maps a log-line prefix (as emitted by pipeline.run's log() calls) to how far along
# that checkpoint represents. Checked in order; the last matching one wins.
STAGE_PROGRESS = [
    ("[plan] generating", 5),
    ("[plan] search terms", 15),
    ("[plan] community hints", 20),
    ("[fetch] searching", 25),
    ("[fetch] collected", 50),
    ("[extract] analyzing", 55),
    ("[extract] found", 80),
    ("[bucket] clustering", 85),
    ("[bucket] grouped", 95),
]


def _run_job(job_id: str, params: dict) -> None:
    job = JOBS[job_id]
    try:
        job["status"] = "running"

        def log(message: str) -> None:
            job["log"].append(message)
            for prefix, pct in STAGE_PROGRESS:
                if message.startswith(prefix):
                    job["progress"] = pct

        result = run(
            params["industry"],
            params["category"],
            params["country"],
            params["platform"],
            num_search_terms=params["num_search_terms"],
            items_per_query=params["items_per_query"],
            comments_per_item=params["comments_per_item"],
            exclude_shorts=params["exclude_shorts"],
            min_views=params["min_views"],
            log=log,
        )
        saved_path = save_json(result)
        saved_csv_path = save_csv(result)

        serializable = dict(result)
        serializable["buckets"] = [asdict(b) for b in result["buckets"]]
        serializable["raw_items"] = [asdict(i) for i in result.get("raw_items", [])]
        serializable["problems"] = [asdict(p) for p in result.get("problems", [])]
        job["result"] = serializable
        job["saved_path"] = saved_path
        job["saved_csv_path"] = saved_csv_path
        job["progress"] = 100
        job["status"] = "done"
    except Exception as exc:
        job["status"] = "error"
        job["error"] = str(exc)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/run", methods=["POST"])
def start_run():
    data = request.get_json(force=True)

    for field in ("industry", "category", "country"):
        if not data.get(field, "").strip():
            return jsonify({"error": f"'{field}' is required"}), 400

    params = {
        "industry": data["industry"].strip(),
        "category": data["category"].strip(),
        "country": data["country"].strip(),
        "platform": data.get("platform") or "youtube",
        "num_search_terms": int(data["num_search_terms"]) if data.get("num_search_terms") else 10,
        "items_per_query": int(data["items_per_query"]) if data.get("items_per_query") else 5,
        "comments_per_item": int(data["comments_per_item"]) if data.get("comments_per_item") else 8,
        "exclude_shorts": not data.get("include_shorts", False),
        "min_views": int(data["min_views"]) if data.get("min_views") else 0,
    }

    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {
        "status": "queued",
        "progress": 0,
        "log": [],
        "result": None,
        "error": None,
        "saved_path": None,
        "saved_csv_path": None,
    }

    thread = threading.Thread(target=_run_job, args=(job_id, params), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        return jsonify({"error": "unknown job_id"}), 404
    return jsonify(job)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=True, use_reloader=False)
