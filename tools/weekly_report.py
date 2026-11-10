#!/usr/bin/env python3
"""Join post insights with log/posted.md and print the ig-audit tables.

usage: python3 tools/insights.py > /tmp/ins.jsonl
       python3 tools/weekly_report.py /tmp/ins.jsonl [--days 7]

Reels are ranked by outlier multiple (views / median reel views) and sends per
reach, the two numbers ig-audit trusts; then grouped by category, slot hour,
hook formula and mood so the weekly review can see what separates the top
from the bottom. Output is markdown for the report; it is not saved anywhere.
"""
import argparse
import json
import re
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))


def log_rows():
    rows = {}
    for line in (ROOT / "log/posted.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 8 or not re.match(r"\d{4}-\d{2}-\d{2}", cells[0]):
            continue
        hook = cells[8] if len(cells) > 8 else "-"
        # Mascot A/B test (2026-11-09~): the last cell may end with "/ 마스코트O" or "/ 마스코트X".
        mascot = re.search(r"마스코트([OX])", hook)
        hook = re.sub(r"\s*/\s*마스코트[OX]\s*$", "", hook)
        # Reel layout A/B test (2026-11-10~): the last cell may end with "/ 전체화면" or "/ 테두리".
        layout = re.search(r"(전체화면|테두리)", hook)
        hook = re.sub(r"\s*/\s*(?:전체화면|테두리)\s*$", "", hook)
        meta = {"date": cells[0], "no": cells[1], "slot": cells[2], "cat": cells[3], "title": cells[4],
                "hook": hook, "mascot": f"마스코트{mascot.group(1)}" if mascot else "-",
                "layout": layout.group(1) if layout else "-"}
        for cell in cells[6:8]:
            for url in re.findall(r"https://www\.instagram\.com/(?:p|reel)/[\w-]+/", cell):
                rows[url] = meta
    return rows


def pct(a, b):
    return f"{100 * a / b:.1f}%" if b else "-"


def skip_median(items):
    """Median share of first views that left within 3 seconds (reels_skip_rate), or '-' when unknown."""
    vals = [r["skip"] for r in items if r.get("skip") is not None]
    return f"{statistics.median(vals):.0f}%" if vals else "-"


def table(title, groups):
    print(f"\n### {title}\n\n| 그룹 | 릴스 수 | 조회 중앙값 | 첫 3초 넘김 | 평균 시청 | 공유/도달 |\n|---|---|---|---|---|---|")
    for key, items in sorted(groups.items(), key=lambda kv: -statistics.median(r["views"] for r in kv[1])):
        views = statistics.median(r["views"] for r in items)
        watch = statistics.mean(r["watch"] for r in items)
        sends = sum(r["shares"] for r in items)
        reach = sum(r["reach"] for r in items)
        print(f"| {key} | {len(items)} | {views:.0f} | {skip_median(items)} | {watch:.1f}s | {pct(sends, reach)} |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("insights")
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()
    meta = log_rows()
    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    posts = []
    for line in Path(args.insights).read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        t = datetime.strptime(r["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
        if t < since or "views" not in r:
            continue
        m = meta.get(r["permalink"], {})
        posts.append({**r, "t": t.astimezone(KST), "cat": m.get("cat", "?"), "hook": m.get("hook", "-"),
                      "mascot": m.get("mascot", "-"), "layout": m.get("layout", "-"),
                      "skip": r.get("reels_skip_rate"),
                      "watch": (r.get("ig_reels_avg_watch_time") or 0) / 1000})
    reels = [p for p in posts if p.get("media_product_type") == "REELS"]
    others = [p for p in posts if p.get("media_product_type") != "REELS"]
    if not reels:
        print("최근 릴스가 없습니다.")
        return
    med = statistics.median(r["views"] for r in reels)
    print(f"## 최근 {args.days}일: 릴스 {len(reels)}개 / 그 외 {len(others)}개\n")
    print(f"- 릴스 조회 중앙값 {med:.0f}, 첫 3초 넘김 중앙값 {skip_median(reels)}, "
          f"평균 시청 {statistics.mean(r['watch'] for r in reels):.1f}s")
    low = [r for r in reels if r.get("skip") is not None and r["skip"] < 70]
    print(f"- 첫 3초 넘김 70% 미만 릴스 {len(low)}개 (2026-11-10 까지 300회를 넘긴 릴스는 모두 여기서 나왔다)")
    if others:
        print(f"- 카드·캐러셀 조회 중앙값 {statistics.median(p['views'] for p in others):.0f}, "
              f"도달 중앙값 {statistics.median(p['reach'] for p in others):.0f}")
    print("\n| 게시(KST) | 분류 | 훅·배경음 | 조회 | 배수 | 도달 | 넘김 | 시청 | 공유 | 저장 | 제목 |\n|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(reels, key=lambda r: (-r["views"] / med, -r["shares"])):
        print(f"| {r['t']:%m-%d %H:%M} | {r['cat']} | {r['hook']} | {r['views']} | {r['views'] / med:.1f}x | "
              f"{r['reach']} | {skip_median([r])} | {r['watch']:.1f}s | {r['shares']} | {r['saved']} | {r['title'][:28]} |")
    by = lambda f: {k: [r for r in reels if f(r) == k] for k in {f(r) for r in reels}}
    table("분류별", by(lambda r: r["cat"]))
    table("게시 시각별", by(lambda r: f"{r['t'].hour:02d}시"))
    table("훅·배경음별", by(lambda r: r["hook"]))
    if any(r["layout"] != "-" for r in reels):
        table("화면 시험별", by(lambda r: r["layout"]))
        table("화면 시험별(분류 안에서)", by(lambda r: f"{r['cat']} / {r['layout']}" if r["layout"] != "-" else "-"))
    if any(r["mascot"] != "-" for r in reels):
        table("마스코트 시험별", by(lambda r: r["mascot"]))
        # Same comparison inside each category, so one viral topic cannot decide the test alone.
        table("마스코트 시험별(분류 안에서)", by(lambda r: f"{r['cat']} / {r['mascot']}" if r["mascot"] != "-" else "-"))


if __name__ == "__main__":
    main()
