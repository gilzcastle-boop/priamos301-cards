#!/usr/bin/env python3
"""title.py - lint a YouTube title and thumbnail pairing before you publish it.

    python3 title.py --title "..." --thumb "AI RAN IT"
    python3 title.py titles.txt            # one per line, ranked
    python3 title.py --title "..." --json

The pairing is the unit, not the title. A title that repeats the thumbnail text wastes half the
click surface, and that is the single most common mistake this checks for.

Length: YouTube truncates around 60 characters on desktop search and around 40 on a mobile home
feed. Both limits are reported because they are different failures - a desktop truncation loses the
tail, a mobile one can lose the subject.
"""
import json, re, sys, os, unicodedata

DESKTOP, MOBILE, HARD = 60, 40, 100
VAGUE = {"amazing","incredible","insane","crazy","huge","massive","ultimate","best","powerful",
         "secret","revolutionary","mindblowing","epic","perfect","complete","everything"}
STOP = {"the","a","an","of","for","to","in","on","and","or","is","are","with","your","you","my","i",
        "this","that","it","how","what","why"}

def words(t): return re.findall(r"[a-z0-9']+", t.lower())

# -- Korean (added for this account) ----------------------------------------------------------
# A Hangul glyph is about twice as wide as a Latin letter, so the 60/40 cuts are applied to display
# width (wide characters count 2) when the title contains Hangul. That is an approximation of where
# the feed truncates, not a figure from YouTube. The 100 limit stays a character count.
HANGUL = re.compile(r"[가-힣]")
VAGUE_KO = ("대박", "충격", "역대급", "레전드", "미친", "미쳤", "소름", "실화", "경악", "놀라운", "엄청난",
            "완벽", "꿀팁", "어마어마")
FRONT_FILLER_KO = {"오늘", "오늘은", "이번", "이번에", "여러분", "진짜", "정말", "드디어", "요즘", "그냥"}
PARTICLE = re.compile(r"(으로|에서|에게|까지|부터|처럼|보다|은|는|이|가|을|를|의|에|도|만|로|과|와)$")

def width(s): return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)
def cut(s, limit):
    out, w = "", 0
    for c in s:
        w += 2 if unicodedata.east_asian_width(c) in "WF" else 1
        if w > limit: break
        out += c
    return out
def tokens_ko(t):   # content words with a trailing particle removed, plus any Latin words and numbers
    out = set(re.findall(r"\d[\d,.]*[가-힣%]{0,3}", t)) | set(re.findall(r"[a-z']{2,}", t.lower()))
    for w in re.findall(r"(?<![\d가-힣])[가-힣]{2,}", t):
        stem = PARTICLE.sub("", w)
        out.add(stem if len(stem) >= 2 else w)
    return out

def check(title, thumb=None):
    t = title.strip()
    n = len(t)
    ko = bool(HANGUL.search(t))
    issues, good = [], []
    if ko:
        w = width(t)
        if n > HARD: issues.append(("length", f"{n} characters - YouTube's hard limit is {HARD}"))
        elif w > DESKTOP: issues.append(("length", f"display width {w} (Hangul counts 2) - desktop search cuts near {DESKTOP}"))
        else: good.append(f"display width {w}, inside the {DESKTOP}-wide desktop cut")
        if w > MOBILE:
            issues.append(("mobile", f'a mobile feed shows about "{cut(t, MOBILE).rstrip()}..." - check the subject survives'))
    elif n > HARD: issues.append(("length", f"{n} characters - YouTube's hard limit is {HARD}"))
    elif n > DESKTOP: issues.append(("length", f"{n} characters - desktop search cuts near {DESKTOP}"))
    else: good.append(f"{n} characters, inside the {DESKTOP}-character desktop cut")
    if not ko and n > MOBILE:
        head = t[:MOBILE].rsplit(" ", 1)[0]
        issues.append(("mobile", f'a mobile feed shows about "{head}..." - check the subject survives'))
    caps = [w for w in t.split() if len(w) > 2 and w.isupper()]
    if len(caps) > 2: issues.append(("shouting", f"{len(caps)} all-caps words - two is the ceiling before it reads as spam"))
    elif caps: good.append(f"{len(caps)} all-caps word for emphasis")
    v = [w for w in words(t) if w in VAGUE] + [w for w in VAGUE_KO if w in t]
    if v: issues.append(("vague", f"{', '.join(sorted(set(v)))} - swap for a number, a name or a date"))
    nums = re.findall(r"\d[\d,.]*%?", t)
    if nums: good.append(f"carries a concrete figure ({', '.join(nums[:3])})")
    else: issues.append(("no-number", "no number, date or name - the most reliable single fix"))
    if t.endswith("?"): good.append("open question in the title")
    if ko:
        if t.split() and t.split()[0] in FRONT_FILLER_KO:
            issues.append(("front-load", f'the title opens on "{t.split()[0]}" - move the subject forward'))
    else:
        front = [w for w in words(t)[:3] if w not in STOP]
        if not front: issues.append(("front-load", "the first three words are all filler - move the subject forward"))
    if thumb:
        if ko or HANGUL.search(thumb): tw, hw = tokens_ko(t) - STOP, tokens_ko(thumb) - STOP
        else: tw, hw = set(words(t)) - STOP, set(words(thumb)) - STOP
        shared = tw & hw
        if shared:
            issues.append(("duplicate", f"thumbnail repeats the title on {', '.join(sorted(shared))} - "
                                        "the thumbnail should say what the title does not"))
        else:
            good.append("thumbnail and title carry different words")
        tn = len(thumb.split()) if HANGUL.search(thumb) else len(words(thumb))
        if tn > 4:
            issues.append(("thumb-length", f"{tn} words on the thumbnail - three is the ceiling at feed size"))
    score = max(0, min(100, 100 - 14 * len(issues) + 4 * len(good)))
    return {"title": t, "chars": n, "score": score, "issues": issues, "good": good}

def show(r):
    print(f'\n  "{r["title"]}"')
    print(f"  {r['chars']} chars   score {r['score']}/100")
    for k, m in r["issues"]: print(f"    x  {k:<12} {m}")
    for m in r["good"]:      print(f"    ok              {m}")

def main():
    a = sys.argv[1:]
    as_json = "--json" in a; a = [x for x in a if x != "--json"]
    thumb = a[a.index("--thumb") + 1] if "--thumb" in a else None
    if "--title" in a:
        rows = [check(a[a.index("--title") + 1], thumb)]
    elif a and os.path.exists(a[0]):
        rows = [check(l, thumb) for l in open(a[0], encoding="utf-8").read().splitlines() if l.strip()]
    else:
        print(__doc__); sys.exit(1)
    rows.sort(key=lambda r: -r["score"])
    if as_json: print(json.dumps(rows, indent=1, ensure_ascii=False)); return
    for r in rows: show(r)
    print()

if __name__ == "__main__":
    main()
