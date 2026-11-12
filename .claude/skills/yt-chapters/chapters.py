#!/usr/bin/env python3
"""chapters.py - YouTube chapters from a timestamped transcript.

    python3 chapters.py transcript.srt            # or .vtt / whisper .json
    python3 chapters.py transcript.srt --target 8 --json

Prints a description block you can paste straight under a video. YouTube's own rules, enforced here
rather than assumed: the list must start at 00:00, needs at least three entries, and each chapter
must be at least 10 seconds long. A block that breaks any of those silently does not become
chapters, which is why this checks instead of trusting.

Boundaries come from the gaps - the pauses you actually took between sections - scored by how long
the pause was and how much the vocabulary changes across it. It is a first draft you retitle, not a
summariser.
"""
import json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "yt-edit"))
from deadair import load, parse_ts  # noqa: E402  (same parser, one implementation)

STOP = set("the a an of for to in on and or is are was were be been with this that it as at by from "
           "you your i my we our they them he she but so if then than there here what which who how "
           "when where why not no yes do does did just really very like about into over out up down "
           "can could will would should have has had get got make made go going went one two".split())

# Korean (added for this account): content words of two syllables or more, trailing particle removed.
STOP_KO = set("그리고 그래서 그런데 하지만 그러면 그러니까 이제 그냥 진짜 정말 너무 우리 제가 저는 저희 이거 그거 "
              "저거 여기 저기 거기 있는 없는 하는 되는 같은 이런 그런 저런 어떤 때문 대해 통해 오늘 지금 먼저 다음 "
              "합니다 있습니다 됩니다 입니다 같습니다 했습니다 그렇게 이렇게 어떻게 굉장히 약간 사실 일단 번째 가지".split())
PARTICLE = re.compile(r"(으로|에서|에게|까지|부터|처럼|보다|은|는|이|가|을|를|의|에|도|만|로|과|와)$")

def keywords(text):
    out = {w for w in re.findall(r"[a-z']{4,}", text.lower()) if w not in STOP}
    for w in re.findall(r"[가-힣]{2,}", text):
        stem = PARTICLE.sub("", w)
        stem = stem if len(stem) >= 2 else w
        if stem not in STOP_KO and w not in STOP_KO: out.add(stem)
    return out

def mmss(t):
    t = int(t); h, m, s = t // 3600, (t % 3600) // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def main():
    a = sys.argv[1:]
    as_json = "--json" in a; a = [x for x in a if x != "--json"]
    target = int(a[a.index("--target") + 1]) if "--target" in a else 7
    a = [x for x in a if not x.startswith("--") and not x.isdigit()]
    if not a or not os.path.exists(a[0]): print(__doc__); sys.exit(1)
    cues = load(a[0])
    if len(cues) < 6: print("too few cues to chapter"); sys.exit(1)
    dur = cues[-1][1]
    cand = []
    for i in range(1, len(cues)):
        gap = cues[i][0] - cues[i - 1][1]
        before = " ".join(c[2] for c in cues[max(0, i - 12):i])
        after = " ".join(c[2] for c in cues[i:i + 12])
        kb, ka = keywords(before), keywords(after)
        shift = 1 - (len(kb & ka) / len(kb | ka)) if (kb | ka) else 0
        cand.append((gap * 1.6 + shift * 3.2, cues[i][0], i))
    cand.sort(reverse=True)
    picked, MIN = [0.0], 10.0
    for _, t, i in cand:
        if len(picked) >= target: break
        if all(abs(t - p) >= MIN for p in picked) and dur - t >= MIN:
            picked.append(t)
    picked.sort()
    chapters = []
    for n, t in enumerate(picked):
        end = picked[n + 1] if n + 1 < len(picked) else dur
        text = " ".join(c[2] for c in cues if c[0] >= t and c[1] <= end)
        kw = [w for w in keywords(text)]
        kw.sort(key=lambda w: (-text.lower().count(w), w))   # ties alphabetical, so two runs agree
        title = " ".join(w.capitalize() for w in kw[:3]) or "Section"
        chapters.append({"start": round(t, 2), "label": mmss(t), "draft_title": title,
                         "seconds": round(end - t, 2)})
    ok = len(chapters) >= 3 and chapters[0]["start"] == 0 and all(c["seconds"] >= MIN for c in chapters)
    if as_json:
        print(json.dumps({"valid": ok, "chapters": chapters}, indent=1, ensure_ascii=False)); return
    print()
    for c in chapters: print(f"  {c['label']} {c['draft_title']}")
    print(f"\n  {len(chapters)} chapters"
          f"{'' if ok else '  -- INVALID: YouTube needs 3+, a 00:00 first entry and 10s minimum each'}")
    print("  Retitle every line before pasting. These are the topic words, not your words.\n")

if __name__ == "__main__":
    main()
