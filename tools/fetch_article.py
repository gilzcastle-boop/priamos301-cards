#!/usr/bin/env python3
"""Fallback article reader for when Firecrawl has no credits left.

usage: python3 tools/fetch_article.py <article url> <out.txt>

Fetches the page straight from the outlet (the host must be on the environment's
allowed-domains list) and writes the headline and body text to <out.txt>, so that
priamos-daily and the fact-checker agent can read the source with the Read tool.

A news page carries more than one article's text (related stories, best-read lists with
long summaries), so a text block only counts as the body when it agrees with the page's
own description or headline. Exits 1 with a one-line reason when the page cannot be
fetched, has no usable body, or has no text block that matches its headline.
"""
import html
import json
import re
import subprocess
import sys
import time
from html.parser import HTMLParser

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")
# Lines that are page furniture, not article text. COPYRIGHT lines go at any length;
# the others only when the line is short, so a sentence about "구독자" is kept.
COPYRIGHT = re.compile(r"무단\s*전재|재배포\s*금지|All rights reserved|Copyright|ⓒ|©")
NOISE = re.compile(r"구독|로그인|기사제보|blocked by an extension|글자\s*크기|공유하기|"
                   r"\[카카오톡\]|\[메일\]|\[전화\]|채널 추가")
# id / class / itemprop values that outlets give the element holding the article text.
HINT = re.compile(r"(?i)articleBody|article[-_]?(body|txt|text|content|view)|"
                  r"news[-_]?(contents?|body|text|view)|view[-_]?(content|text|body|con)|"
                  r"cont[-_]?(body|text)|detail[-_]?(body|content|text)|text[-_]?area|art[-_]?(body|txt)")
MIN_BODY = 300          # characters in sentence-length lines
RETRY_CODES = {7, 35, 52, 56}   # curl: connect failed, TLS reset, empty reply, receive failure


def fetch(url):
    for attempt in range(3):
        out = subprocess.run(["curl", "-sS", "-L", "--max-time", "30", "-A", UA, "-w", "\n%{http_code}", url],
                             capture_output=True)
        if out.returncode not in RETRY_CODES:
            break
        time.sleep(2)
    if out.returncode != 0:
        sys.exit(f"FETCH FAILED: {out.stderr.decode('utf-8', 'replace').strip()[:200]}")
    body, _, code = out.stdout.rpartition(b"\n")
    if code.strip() != b"200":
        sys.exit(f"FETCH FAILED: HTTP {code.decode().strip()} (the outlet may block automated access)")
    m = re.search(rb"charset=[\"']?([\w-]+)", body[:4000], re.I)
    enc = m.group(1).decode() if m else "utf-8"
    try:
        return body.decode(enc, "replace")
    except LookupError:
        return body.decode("utf-8", "replace")


def meta(page, *keys):
    """Content of the first <meta property|name=key> found, whatever the attribute order."""
    tags = re.findall(r"(?is)<meta\b[^>]*>", page)
    for key in keys:
        for tag in tags:
            if re.search(r"(?i)(?:property|name)\s*=\s*[\"']%s[\"']" % re.escape(key), tag):
                m = re.search(r'(?is)content\s*=\s*"(.*?)"', tag) or re.search(r"(?is)content\s*=\s*'(.*?)'", tag)
                if m and m.group(1).strip():
                    return html.unescape(m.group(1)).strip()
    return ""


def clean_text(text):
    lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in text.split("\n")]
    return [ln for ln in lines
            if len(ln) >= 20 and not COPYRIGHT.search(ln) and not (len(ln) < 60 and NOISE.search(ln))]


def clean(fragment):
    fragment = re.sub(r"(?is)<(script|style|figure|figcaption|noscript|iframe|button|svg).*?</\1>", " ", fragment)
    fragment = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", fragment)
    return clean_text(html.unescape(re.sub(r"<[^>]+>", "", fragment)))


def sentences(lines):
    return sum(len(x) for x in lines if len(x) >= 40)


def squash(text):
    return re.sub(r"[\s\"'“”‘’·…]+", "", text)


def words(text):
    return set(re.findall(r"[0-9A-Za-z가-힣]{2,}", text))


def relevant(lines, title, desc):
    """True when the text is this page's own article: it contains a piece of the page
    description, or at least half of the words of the headline or of the description.
    (Measured on 19 outlets, 2026-11-10: an article's own body scored 0.56 or more on the
    better of the two, another story's body 0.32 or less.)"""
    body = squash("".join(lines))
    d = squash(desc)
    if len(d) >= 40:
        n = 14
        if any(d[i:i + n] in body for i in (len(d) // 6, len(d) // 2 - n // 2, len(d) * 3 // 4 - n)):
            return True
    checked = False
    for ws in (words(title), words(desc)):
        if len(ws) >= 4:
            checked = True
            if sum(1 for w in ws if w in body) * 2 >= len(ws):
                return True
    return not checked   # nothing on the page to compare with


def from_json_ld(page):
    found = []
    for block in re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            body = isinstance(item, dict) and item.get("articleBody")
            if body and len(body) > 200:
                found.append(clean(body.replace("\\n", "\n")))
    return found


def from_fusion(page):
    # Arc/Fusion sites (chosun.com) ship the body as JSON content elements.
    texts = re.findall(r'"content":"((?:[^"\\]|\\.){20,})","(?:_id|type)"', page)
    lines = []
    for t in texts:
        try:
            lines += clean(json.loads(f'"{t}"'))
        except ValueError:
            pass
    return [lines]


class Containers(HTMLParser):
    """Collects text per innermost block container, so the article body can be found whether the
    outlet marks paragraphs with <p> tags or with <br> breaks inside one <div>."""
    SKIP = {"script", "style", "noscript", "iframe", "svg", "button", "select", "textarea", "figcaption"}
    BLOCK = {"div", "article", "section", "td", "main"}
    BREAK = {"br", "p", "li", "h1", "h2", "h3", "h4", "tr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.parent, self.text, self.skip, self.count = [0], {0: None}, {0: []}, [], 0
        self.hinted = set()

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip.append(tag)
        elif tag in self.BLOCK:
            self.count += 1
            self.parent[self.count] = self.stack[-1]
            self.text[self.count] = []
            self.stack.append(self.count)
            marks = " ".join(v or "" for k, v in attrs if k in ("id", "class", "itemprop"))
            if HINT.search(marks):
                self.hinted.add(self.count)
        elif tag in self.BREAK:
            self.text[self.stack[-1]].append("\n")

    def handle_endtag(self, tag):
        if self.skip and tag == self.skip[-1]:
            self.skip.pop()
        elif tag in self.BLOCK and len(self.stack) > 1:
            self.stack.pop()
        elif tag in self.BREAK:
            self.text[self.stack[-1]].append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.text[self.stack[-1]].append(data)


def from_containers(page):
    """Text blocks of the page, the likeliest article body first: blocks the outlet marks as
    the article text, then the others, each group from the most text to the least. After
    those, every block joined with its direct children, for outlets that wrap each paragraph
    in its own <div>."""
    parser = Containers()
    try:
        parser.feed(page)
    except Exception:
        return []
    own = {k: clean_text("".join(v)) for k, v in parser.text.items()}
    singles = sorted(own, key=lambda k: (k not in parser.hinted, -sentences(own[k])))
    merged = {}
    for k in sorted(own):
        p = parser.parent.get(k)
        if p is not None:
            merged.setdefault(p, list(own[p]))
            merged[p] += own[k]
    joined = sorted(merged, key=lambda k: (k not in parser.hinted, -sentences(merged[k])))
    return [own[k] for k in singles] + [merged[k] for k in joined]


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    url, out = sys.argv[1], sys.argv[2]
    page = fetch(url)
    title = meta(page, "og:title", "twitter:title", "title")
    if not title:
        t = re.search(r"(?is)<title[^>]*>(.*?)</title>", page)
        title = html.unescape(t.group(1)).strip() if t else ""
    desc = meta(page, "og:description", "description", "twitter:description")
    # Structured data first (cleanest), then the page's text blocks. The whole page is never
    # used: it would carry other stories' headlines along with the article.
    candidates = from_json_ld(page) + from_fusion(page) + from_containers(page)
    long_enough = [c for c in candidates if sentences(c) >= MIN_BODY]
    lines = next((c for c in long_enough if relevant(c, title, desc)), None)
    if lines is None:
        if long_enough:
            sys.exit("NO MATCH: the page has text, but none of it matches its own headline "
                     "(the body may load with scripts); use another outlet")
        sys.exit("NO BODY: the page has too little article text (it may load the body with scripts)")
    seen, body = set(), []
    for ln in lines:
        if ln not in seen:
            seen.add(ln)
            body.append(ln)
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"URL: {url}\nTITLE: {title}\n\n" + "\n".join(body) + "\n")
    print(f"ok {sum(len(x) for x in body)} chars, {len(body)} lines -> {out}")


if __name__ == "__main__":
    main()
