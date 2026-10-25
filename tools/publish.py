#!/usr/bin/env python3
"""Publish one card (JPEG + caption .txt) from this repo to Instagram.

Usage: python3 tools/publish.py cards/20261025-01.jpg

The image must already be pushed to the public repo (Meta fetches it by URL).
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

    container = call("POST", f"{API}/{ig_id}/media", {
        "image_url": f"{REPO_RAW}/{img.as_posix()}",
        "caption": caption,
    })["id"]

    # Meta recommends checking container status at most once a minute for 5 minutes;
    # images are usually ready on the first check.
    for attempt in range(6):
        status = call("GET", f"{API}/{container}?fields=status_code")["status_code"]
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise SystemExit(f"Container {container} failed: {status}")
        time.sleep(60 if attempt else 10)
    else:
        raise SystemExit(f"Container {container} not ready after 5 minutes")

    media_id = call("POST", f"{API}/{ig_id}/media_publish", {"creation_id": container})["id"]
    info = call("GET", f"{API}/{media_id}?fields=permalink,timestamp")
    print(json.dumps({"media_id": media_id, **info}, ensure_ascii=False))


if __name__ == "__main__":
    main()
