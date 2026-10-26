#!/usr/bin/env python3
"""Fetch every post with its insights and print one JSON object per line.

usage: python3 tools/insights.py > insights.jsonl

Metrics: views, reach, likes, comments, saved, shares, total_interactions,
and for reels ig_reels_avg_watch_time (ms). Nothing is written to the repo:
these numbers are private account data.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from publish import API, call  # noqa: E402

BASE = ["views", "reach", "likes", "comments", "saved", "shares", "total_interactions"]


def insights(media):
    metrics = BASE + (["ig_reels_avg_watch_time"] if media.get("media_product_type") == "REELS" else [])
    try:
        data = call("GET", f"{API}/{media['id']}/insights?metric={','.join(metrics)}")["data"]
    except SystemExit as e:  # very new posts can refuse some metrics
        return {"error": str(e)[:200]}
    return {d["name"]: d["values"][0]["value"] for d in data}


def main():
    url = f"{API}/me/media?fields=id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count&limit=50"
    while url:
        page = call("GET", url)
        for m in page.get("data", []):
            row = {k: m.get(k) for k in ("id", "media_type", "media_product_type", "timestamp", "permalink", "like_count", "comments_count")}
            row["title"] = (m.get("caption") or "").split("\n")[0][:60]
            row.update(insights(m))
            print(json.dumps(row, ensure_ascii=False), flush=True)
        url = page.get("paging", {}).get("next")


if __name__ == "__main__":
    main()
