#!/usr/bin/env python3
"""Publish one card (JPEG + caption .txt) or reel (MP4 + caption .txt) from this repo to Instagram.

Usage: python3 tools/publish.py cards/20261025-01.jpg
       python3 tools/publish.py cards/20261027-01.jpg --carousel   # -c*.jpg, the card itself, then -end.jpg
       python3 tools/publish.py reels/20261025-08.mp4

The file must already be pushed to the public repo (Meta fetches it by URL).
The access token is attached by the environment's network secret for
graph.instagram.com, so this script never reads or prints it.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

API = "https://graph.instagram.com/v26.0"
REPO_RAW = "https://raw.githubusercontent.com/gilzcastle-boop/priamos301-cards/main"


def call(method, url, data=None):
    cmd = ["curl", "-sS", "--max-time", "60", "-X", method, url]
    for k, v in (data or {}).items():
        cmd += ["--data-urlencode", f"{k}={v}"]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    body = json.loads(out)
    if "error" in body:
        raise SystemExit(f"Instagram API error: {json.dumps(body['error'], ensure_ascii=False)}")
    return body


def main():
    img = Path(sys.argv[1])
    caption = img.with_suffix(".txt").read_text(encoding="utf-8").strip()
    me = call("GET", f"{API}/me?fields=user_id,username")
    ig_id = me["user_id"]

    url = f"{REPO_RAW}/{img.as_posix()}"
    is_reel = img.suffix.lower() == ".mp4"
    if "--carousel" in sys.argv:
        # Slides c1..cN (cover and points), the info card as the recap slide, then the follow slide.
        end = img.with_name(f"{img.stem}-end.jpg")
        slides = sorted(img.parent.glob(f"{img.stem}-c*.jpg")) + [img] + ([end] if end.exists() else [])
        if len(slides) < 2:
            raise SystemExit(f"No {img.stem}-c*.jpg slides next to {img}")
        children = [call("POST", f"{API}/{ig_id}/media",
                         {"image_url": f"{REPO_RAW}/{s.as_posix()}", "is_carousel_item": "true"})["id"] for s in slides]
        # The album container errors out if it is created before every slide has finished downloading.
        for child in children:
            for _ in range(12):
                status = call("GET", f"{API}/{child}?fields=status_code")["status_code"]
                if status == "FINISHED":
                    break
                if status in ("ERROR", "EXPIRED"):
                    raise SystemExit(f"Carousel slide container {child} failed: {status}")
                time.sleep(5)
            else:
                raise SystemExit(f"Carousel slide container {child} not ready after a minute")
        payload = {"media_type": "CAROUSEL", "children": ",".join(children)}
    elif is_reel:
        # share_to_feed=false keeps reels in the Reels tab only, so the profile grid shows each story once (user request, 2026-10-28)
        payload = {"media_type": "REELS", "video_url": url, "share_to_feed": "false", "thumb_offset": "4000"}
    else:
        payload = {"image_url": url}
    container = call("POST", f"{API}/{ig_id}/media", {**payload, "caption": caption})["id"]

    # Meta recommends checking container status at most once a minute; images are usually
    # ready on the first check, videos need a few minutes of processing.
    checks = 10 if is_reel else 6
    for attempt in range(checks):
        status = call("GET", f"{API}/{container}?fields=status_code")["status_code"]
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise SystemExit(f"Container {container} failed: {status}")
        time.sleep(60 if attempt else (30 if is_reel else 10))
    else:
        raise SystemExit(f"Container {container} not ready after {checks - 1} minutes")

    media_id = call("POST", f"{API}/{ig_id}/media_publish", {"creation_id": container})["id"]
    info = call("GET", f"{API}/{media_id}?fields=permalink,timestamp")
    print(json.dumps({"media_id": media_id, **info}, ensure_ascii=False))


if __name__ == "__main__":
    main()
