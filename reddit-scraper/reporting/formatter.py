import csv
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

FLAT_CSV_FIELDS = ["search_term", "video_title", "video_link", "comment", "problem", "problem_bucket", "type"]


def print_summary(result: dict) -> None:
    print()
    print(f"=== Problems: {result['industry']} / {result['category']} / {result['country']} ({result['platform']}) ===")
    print(f"{result['raw_item_count']} items scanned -> {result['problem_count']} problems -> {len(result['buckets'])} buckets")
    print()
    for b in result["buckets"]:
        print(f"[{b.count:>3}] {b.label} — {b.description}")
        for q in b.example_quotes[:3]:
            print(f'       "{q}"')
        print()


def save_json(result: dict, out_dir: str = "runs") -> str:
    Path(out_dir).mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_industry = result["industry"].replace(" ", "_")
    fname = f"{out_dir}/{result['platform']}_{safe_industry}_{ts}.json"

    serializable = dict(result)
    serializable["buckets"] = [asdict(b) for b in result["buckets"]]
    serializable["raw_items"] = [asdict(i) for i in result.get("raw_items", [])]
    serializable["problems"] = [asdict(p) for p in result.get("problems", [])]

    with open(fname, "w") as f:
        json.dump(serializable, f, indent=2, default=str)
    return fname


def build_flat_rows(result: dict) -> list[dict]:
    """One row per extracted problem: search term, video title/link, the actual
    comment (or video text) it came from, the problem, its bucket, and Short/Video."""
    raw_by_id = {item.id: item for item in result.get("raw_items", [])}

    rows = []
    for p in result.get("problems", []):
        raw = raw_by_id.get(p.raw_item_id)
        video_link = raw.url.split("&lc=")[0] if raw else p.url.split("&lc=")[0]
        rows.append(
            {
                "search_term": p.search_term,
                "video_title": raw.parent_title if raw else "",
                "video_link": video_link,
                "comment": raw.text if raw else "",
                "problem": p.text,
                "problem_bucket": p.bucket_label,
                "type": raw.media_type if raw else "",
            }
        )
    return rows


def save_csv(result: dict, out_dir: str = "runs") -> str:
    Path(out_dir).mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_industry = result["industry"].replace(" ", "_")
    fname = f"{out_dir}/{result['platform']}_{safe_industry}_{ts}.csv"

    rows = build_flat_rows(result)
    with open(fname, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FLAT_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return fname
