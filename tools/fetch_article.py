#!/usr/bin/env python3
"""Fallback article reader for when Firecrawl has no credits left.

usage: python3 tools/fetch_article.py <article url> <out.txt>

Fetches the page straight from the outlet (the host must be on the environment's
allowed-domains list) and writes the headline and body text to <out.txt>, so that
priamos-daily and the fact-checker agent can read the source with the Read tool.
Exits 1 with a one-line reason when the page cannot be fetched or has no usable body.
"""
import html
import json
import re
import subprocess
import sys

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")
# Lines that are page furniture, not article text.
NOISE = re.compile(r"무단\s*전재|재배포\s*금지|All rights reserved|구독|로그인|기사제보|"
                   r"blocked by an extension|글자\s*크기|공유하기|Copyright|ⓒ|©")


def fetch(url):
    out = subprocess.run(["curl", "-sS", "-L", "--max-time", "30", "-A", UA, "-w", "\n%{http_code}", url],
                         capture_output=True)
    if out.returncode != 0:
        sys.exit(f"FETCH FAILED: {out.stderr.decode('utf-8', 'replace').strip()[:200]}")
    raw = out.stdout
    body, _, code = raw.rpartition(b"\n")
    if code.strip() != b"200":
        sys.exit(f"FETCH FAILED: HTTP {code.decode().strip()} (the outlet may block automated access)")
    m = re.search(rb"charset=[\"']?([\w-]+)", body[:4000], re.I)
    enc = m.group(1).decode() if m else "utf-8"
    try:
        return body.decode(enc, "replace")
    except LookupError:
        return body.decode("utf-8", "replace")


def clean(fragment):
    fragment = re.sub(r"(?is)<(script|style|figure|figcaption|noscript|iframe|button|svg).*?</\1>", " ", fragment)
    fragment = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", fragment)
    text = html.unescape(re.sub(r"<[^>]+>", "", fragment))
    lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in text.split("\n")]
    return [ln for ln in lines if len(ln) >= 20 and not NOISE.search(ln)]


def from_json_ld(page):
    for block in re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            body = isinstance(item, dict) and item.get("articleBody")
            if body and len(body) > 200:
                return clean(body.replace("\\n", "\n"))
    return []


def from_fusion(page):
    # Arc/Fusion sites (chosun.com) ship the body as JSON content elements.
    texts = re.findall(r'"content":"((?:[^"\\]|\\.){20,})","(?:_id|type)"', page)
    lines = []
    for t in texts:
        try:
            lines += clean(json.loads(f'"{t}"'))
        except ValueError:
            pass
    return lines


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    url, out = sys.argv[1], sys.argv[2]
    page = fetch(url)
    title = re.search(r'(?is)<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']', page)
    title = html.unescape(title.group(1)).strip() if title else ""
    paragraphs = re.findall(r"(?is)<p[^>]*>(.*?)</p>", page)
    candidates = [from_json_ld(page), from_fusion(page), clean("\n".join(f"<p>{p}</p>" for p in paragraphs))]
    # Some outlets put the body in a container with <br> breaks instead of <p> tags.
    for pat in (r'(?is)<article[^>]*>(.*?)</article>', r'(?is)<div[^>]+(?:itemprop=["\']articleBody["\']|id=["\'](?:articleBody|article-view-content-div|textBody)["\'])[^>]*>(.*?)</div>\s*(?:<div|<!--|</section)'):
        m = re.search(pat, page)
        if m:
            candidates.append(clean(m.group(1)))
    lines = max(candidates, key=lambda ls: sum(len(x) for x in ls))
    seen, body = set(), []
    for ln in lines:
        if ln not in seen:
            seen.add(ln)
            body.append(ln)
    if sum(len(x) for x in body) < 300:
        sys.exit("NO BODY: the page has too little article text (it may load the body with scripts)")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"URL: {url}\nTITLE: {title}\n\n" + "\n".join(body) + "\n")
    print(f"ok {sum(len(x) for x in body)} chars, {len(body)} lines -> {out}")


if __name__ == "__main__":
    main()
