#!/usr/bin/env python3
"""hookscore.py - score a YouTube hook before you waste a take on it.

Five properties, 0-100 each, and a verdict that is 60% the mean and 40% the weakest one. The
weakest-link weighting is deliberate: a hook with four strong properties and one dead one is a hook
that leaks at the dead one, and averaging hides that.

    python3 hookscore.py hooks.txt            # one hook per line, ranked
    python3 hookscore.py --hook "one line"    # score a single hook
    python3 hookscore.py --json hooks.txt     # machine-readable

WHAT THIS CAN AND CANNOT TELL YOU. Measured against 74 real short-form hooks (first 15 seconds of
auto-captions, top-8 and bottom-8 by views across five channels): it separates deliberately bad
hooks from real ones well, and it separates a creator's own hits from their own misses barely at
all. Treat a low score as a reason to look again, never a high score as a promise.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FORMULAS = json.load(open(os.path.join(HERE, "hooks.json"), encoding="utf-8"))["hooks"]

FILLER = {"basically","actually","literally","just","really","very","so","kind","sort","like",
          "guys","hey","welcome","today","video","subscribe","channel"}
VAGUE = {"amazing","incredible","insane","crazy","huge","massive","game","changer","secret",
         "powerful","ultimate","best","revolutionary","mind","blowing","unbelievable"}
CONCRETE = re.compile(r"\b(\d[\d,.]*\s?(%|k|m|x|s|m|h)?|\$\d|\d+\s?(second|minute|hour|day|week|month|year)s?)\b", re.I)
YOU = re.compile(r"\b(you|your|you're|youre|yourself)\b", re.I)
STAKE = re.compile(r"\b(lose|lost|wasting|waste|quit|fail|broke|cost|risk|before|stop|never|die|dying|dead)\b", re.I)
CURIOSITY = re.compile(r"\b(why|how|what|which|until|before|but|nobody|almost|except|reason|actually)\b", re.I)

def words(t): return re.findall(r"[a-z0-9'%$.]+", t.lower())

# -- Korean (added for this account) ----------------------------------------------------------
# The panel above reads Latin words only, so a Korean hook scored near zero on every property.
# These lists play the same five roles for Hangul text. They are uncalibrated heuristics: the
# 74-hook calibration in the docstring was English. A low score is a reason to look again.
HANGUL = re.compile(r"[가-힣]")
KO_FILLER = ("안녕하세요", "여러분 안녕", "오늘은", "이번 영상", "이번 시간", "구독", "좋아요", "알림 설정",
             "그냥", "약간", "일단", "뭔가")
KO_VAGUE = ("대박", "충격", "역대급", "레전드", "미친", "미쳤", "엄청", "완전", "최고의", "꿀팁", "놀라운",
            "소름", "실화", "경악", "어마어마")
KO_NUMBER = re.compile(r"\d[\d,.]*")
KO_NAMED = re.compile(r"[A-Z][A-Za-z0-9]+|[\"“‘「『][^\"”’」』]{2,}[\"”’」』]")
KO_YOU = re.compile(r"당신|여러분|님들|네가|니가|너는|넌 |본인|하세요|마세요|보세요|하시나요|계신가요|계시다면"
                    r"|있다면|한다면|이라면|라면|아시나요|모르면|모른다면")
KO_STAKE = re.compile(r"손해|잃|망하|망했|망한|실패|위험|절대|그만|멈추|후회|낭비|날리|날렸|죽|큰일|금지|주의"
                      r"|경고|조심|사기|폭락|해고|벌금|못 |안 됩|안됩|없어지|사라지|전에")
KO_CURIOSITY = re.compile(r"왜|어떻게|무엇|뭐가|뭘|어떤|이유|정체|비밀|진짜|사실은|그런데|근데|하지만|아무도"
                          r"|거의|의외|반전|결과|알고 보니")
KO_QUESTION_END = re.compile(r"(\?|까요|일까|을까|나요|는가)\s*$")
KO_CLOSED = re.compile(r"왜냐하면|때문입니다|때문이에요|때문이다|그래서")

def is_ko(t): return bool(HANGUL.search(t))
def ko_len(t):   # spoken length: Hangul syllables, plus two per Latin word or number
    return len(HANGUL.findall(t)) + 2 * len(re.findall(r"[A-Za-z0-9]+", t))

def specificity_ko(t):
    nums = len(KO_NUMBER.findall(t))
    vague = sum(t.count(w) for w in KO_VAGUE)
    filler = sum(t.count(w) for w in KO_FILLER)
    s = 34 + nums * 22 - vague * 16 - filler * 5 + min(18, 6 * len(KO_NAMED.findall(t)))
    return max(0, min(100, s))

def address_ko(t):
    n = len(KO_YOU.findall(t))
    first = 30 if KO_YOU.search(" ".join(t.split()[:4])) else 0
    return max(0, min(100, 26 + n * 20 + first))

def stakes_ko(t):
    return max(0, min(100, 22 + len(KO_STAKE.findall(t)) * 26 + (14 if KO_NUMBER.search(t) else 0)))

def curiosity_ko(t):
    q = 18 if KO_QUESTION_END.search(t.strip()) else 0
    closed = -18 if KO_CLOSED.search(t) else 0
    return max(0, min(100, 24 + len(KO_CURIOSITY.findall(t)) * 17 + q + closed))

def brevity_ko(t):
    n = ko_len(t)
    if n == 0: return 0
    # about 5.5 syllables a second: 18-55 syllables lands inside ten seconds
    if 18 <= n <= 55: return 100
    if n < 18: return max(30, 100 - (18 - n) * 5)
    return max(10, 100 - (n - 55) * 3)

def specificity(t):
    if is_ko(t): return specificity_ko(t)
    w = words(t)
    if not w: return 0
    nums = len(CONCRETE.findall(t))
    vague = sum(1 for x in w if x in VAGUE)
    filler = sum(1 for x in w if x in FILLER)
    s = 34 + nums * 22 - vague * 16 - filler * 5
    # proper nouns that are not sentence-initial read as named things
    s += min(18, 6 * sum(1 for x in t.split()[1:] if x[:1].isupper()))
    return max(0, min(100, s))

def address(t):
    if is_ko(t): return address_ko(t)
    n = len(YOU.findall(t))
    first = 30 if YOU.search(" ".join(t.split()[:6])) else 0
    return max(0, min(100, 26 + n * 20 + first))

def stakes(t):
    if is_ko(t): return stakes_ko(t)
    n = len(STAKE.findall(t))
    return max(0, min(100, 22 + n * 26 + (14 if CONCRETE.search(t) else 0)))

def curiosity(t):
    if is_ko(t): return curiosity_ko(t)
    n = len(CURIOSITY.findall(t))
    q = 18 if t.strip().endswith("?") else 0
    # a hook that resolves itself has no gap left
    closed = -18 if re.search(r"\b(because|so that|which means)\b", t, re.I) else 0
    return max(0, min(100, 24 + n * 17 + q + closed))

def brevity(t):
    if is_ko(t): return brevity_ko(t)
    n = len(words(t))
    if n == 0: return 0
    # 9-24 words is the band a spoken hook lands in at ~150wpm inside 10 seconds
    if 9 <= n <= 24: return 100
    if n < 9:  return max(30, 100 - (9 - n) * 11)
    return max(10, 100 - (n - 24) * 7)

PROPS = [("SPECIFICITY", specificity), ("ADDRESS", address), ("STAKES", stakes),
         ("CURIOSITY", curiosity), ("BREVITY", brevity)]

def classify(t):
    best, hits = None, 0
    for f in FORMULAS:
        pats = f["match"] + (f.get("match_ko", []) if is_ko(t) else [])
        n = sum(1 for p in pats if re.search(p, t, re.I))
        if n > hits: best, hits = f, n
    return (best["name"] if best else "Unclassified"), hits

def score(t):
    parts = {n: fn(t) for n, fn in PROPS}
    vals = list(parts.values())
    verdict = round(0.6 * (sum(vals) / len(vals)) + 0.4 * min(vals))
    name, hits = classify(t)
    return parts, verdict, name, hits

def band(v): return "STRONG" if v >= 72 else "WORKABLE" if v >= 55 else "WEAK"

def report(t, parts, verdict, name, hits):
    print(f"\n  {t.strip()}")
    print(f"  {'-' * min(72, max(20, len(t.strip())))}")
    for k, v in parts.items():
        print(f"    {k:<12} {v:3d}  {'#' * (v // 5)}")
    print(f"    {'VERDICT':<12} {verdict:3d}  {band(verdict)}")
    print(f"    formula      {name}" + (f"  ({hits} pattern{'s' if hits != 1 else ''} matched)" if hits else "  (no formula matched - that is usually a summary, not a hook)"))
    low = min(parts, key=parts.get)
    print(f"    weakest      {low} - {(FIX_KO if is_ko(t) else FIX)[low]}")

FIX = {
 "SPECIFICITY": "swap one adjective for a number, a name or a date",
 "ADDRESS": "say 'you' in the first six words",
 "STAKES": "name what it costs them to keep doing it the current way",
 "CURIOSITY": "cut the half of the sentence that answers itself",
 "BREVITY": "9 to 24 words. Read it out loud and stop where you run out of breath",
}

FIX_KO = {
 "SPECIFICITY": "형용사 하나를 숫자, 이름, 날짜로 바꾼다",
 "ADDRESS": "첫 네 어절 안에서 보는 사람에게 직접 말을 건다 (~라면, ~하세요, 여러분)",
 "STAKES": "지금 방식대로 하면 무엇을 잃는지 말한다",
 "CURIOSITY": "스스로 답해 버리는 뒷부분을 잘라 낸다",
 "BREVITY": "18~55음절. 소리 내어 읽고 숨이 차는 곳에서 끊는다",
}

def main():
    a = sys.argv[1:]
    as_json = "--json" in a
    a = [x for x in a if x != "--json"]
    if "--hook" in a:
        lines = [a[a.index("--hook") + 1]]
    elif a and os.path.exists(a[0]):
        lines = [l for l in open(a[0], encoding="utf-8").read().splitlines() if l.strip()]
    else:
        print(__doc__); sys.exit(1 if not a else 0)
    out = []
    for t in lines:
        parts, verdict, name, hits = score(t)
        out.append({"hook": t.strip(), "properties": parts, "verdict": verdict,
                    "band": band(verdict), "formula": name, "matched": hits})
    out.sort(key=lambda r: -r["verdict"])
    if as_json:
        print(json.dumps([{k: v for k, v in r.items() if k != "matched"} for r in out], indent=1, ensure_ascii=False)); return
    for r in out:
        report(r["hook"], r["properties"], r["verdict"], r["formula"], r["matched"])
    if len(out) > 1:
        print(f"\n  winner: {out[0]['hook'].strip()}  ({out[0]['verdict']}, {out[0]['band']})\n")

if __name__ == "__main__":
    main()
