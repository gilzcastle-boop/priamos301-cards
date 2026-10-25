#!/usr/bin/env python3
"""
hookscore.py - score the first line of a Reel on the five things strong hooks
have in common, and rank a batch of them against each other.

What this is:  five local heuristics, computed on your machine from the text
alone. They measure properties that hooks which hold attention tend to share -
a length you can say in under three seconds, a concrete marker, something at stake,
the payload at the front rather than the back, and a viewer to aim it at.

What this is NOT:  a view predictor. It was tested against 74 real short-form
hooks, transcribed from the first three seconds of the top eight and bottom
eight performers on five channels. Separating a real hook from a deliberately
bad one it does well: AUC 0.83, and 9 of 10 written-to-be-bad hooks scored
below the real median. Separating a good creator's hits from that same
creator's misses it barely does at all: AUC 0.56, where 0.50 is a coin flip.

So use it for what it measured well. It catches greetings, preambles, hooks
with nothing concrete in them and hooks that take five seconds to say. It will
not tell you which of two decent hooks will travel, and nothing that reads text
can, because that is decided by your face, your edit, your audio and who
Instagram shows it to. Trust the retention graph over this script.

Each check returns 0 to 100. Higher is better.

Usage
  python3 hookscore.py hooks.txt              # one hook per line, ranked
  python3 hookscore.py --hook "I lost $18,000 on one missing contract."
  pbpaste | python3 hookscore.py -
  python3 hookscore.py hooks.txt --json
"""

import argparse
import json
import re
import statistics
import sys

WORD_RE = re.compile(r"[A-Za-z0-9$%'’-]+")   # English; Korean hooks use KO_* below
NUMBER_RE = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d+)?"                       # money, whole
    r"|\b\d[\d,]*(?:\.\d+)?\s?"                      # a figure, with or
    r"(?:%|k\b|x\b|hrs?\b|hours?\b|mins?\b|minutes?\b"  # without a unit
    r"|days?\b|weeks?\b|months?\b|years?\b)?",
    re.IGNORECASE)
PROPER_RE = re.compile(r"(?<!^)\b[A-Z][a-z]{2,}\b")
HASHTAG_RE = re.compile(r"(?:^|\s)#\w+")
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")

# Spoken hooks say their numbers out loud. "Zero dollars" and "twenty grand"
# are as concrete as "$0" and "$20,000", and counting only digits missed them.
# "one" and "first" are deliberately absent: they are filler far more often
# than they are a quantity.
SPOKEN_NUMBERS = {
    "zero", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "fifteen", "twenty", "thirty", "forty", "fifty",
    "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "million",
    "billion", "dozen", "half", "twice", "triple",
}
MONEY_WORDS = {
    "dollars", "dollar", "bucks", "grand", "percent", "cents",
    "millionaire", "billionaire", "revenue", "profit", "salary", "rent",
}

# Words that put something on the line. A hook with none of these is a
# statement; a hook with one is a reason to keep watching.
STAKES = {
    "stop", "never", "wrong", "mistake", "mistakes", "lost", "lose", "losing",
    "cost", "costs", "broke", "broken", "failed", "failure", "fail", "nobody",
    "no", "not", "don't", "dont", "doesn't", "didn't", "can't", "won't",
    "quit", "quitting", "fired", "deleted", "delete", "killed", "kills", "kill",
    "replaced", "replaces", "cut", "beat", "free", "paid", "charged", "hired",
    "saved", "first",
    "banned", "illegal", "worst", "hate", "hated", "wasted", "waste", "scam",
    "lie", "lied", "lying", "truth", "secret", "hidden", "stole", "stolen",
    "before", "until", "instead", "but", "except", "unless", "problem",
    "risk", "danger", "warning", "regret", "wish", "should", "shouldn't",
    "still", "already", "only", "without", "versus", "vs", "actually",
}

# Openers that spend the first second saying nothing.
WEAK_OPENERS = [
    "so", "ok", "okay", "hey", "hi", "hello", "guys", "yo", "alright",
    "welcome", "today", "basically", "honestly", "look", "listen", "um",
    "just", "let", "lets", "let's", "i wanted", "i want", "one of",
    "have you", "did you", "do you", "are you", "in this", "in today",
    "the thing", "a lot", "there is", "there are", "this is", "it is",
    "as a", "when it", "if you've", "you know",
]

# Imperatives that earn the front position.
IMPERATIVES = {
    "stop", "steal", "copy", "delete", "try", "watch", "read", "save",
    "use", "build", "make", "write", "send", "take", "start", "quit",
    "never", "always", "don't", "dont", "do", "put", "run", "check",
}

DEALBREAKERS = [
    (re.compile(r"(?i)^\s*(?:stop scrolling|don'?t scroll)"),
     "Opens with \"stop scrolling\". Asking for attention proves you have not earned it."),
    (re.compile(r"(?i)\b(?:in (?:this|today'?s) (?:video|reel)|i'?m going to show you|i'?ll show you how)\b"),
     "Video preamble. Delete it and open on the payoff."),
    (re.compile(r"(?i)^\s*(?:hey |hi |what'?s up |welcome )"),
     "Greeting. Nobody came to the feed to be greeted."),
    (HASHTAG_RE,
     "Hashtag in the hook. Hashtags belong at the bottom of the caption, if anywhere."),
    (EMOJI_RE,
     "Emoji in the hook. On-screen text at hook size has room for words or for an emoji, not both."),
]


def clamp(n):
    return max(0.0, min(100.0, n))


def words(text):
    # "$18,000" is one word when it is spoken, so it is one word here too.
    return WORD_RE.findall(re.sub(r"(?<=\d),(?=\d)", "", text))


def check_length(text):
    """A hook has to land before the thumb moves. Roughly two seconds."""
    w = words(text)
    n = len(w)
    secs = n / 2.75                      # ~165 words per minute, spoken
    chars = len(text.strip())
    if 5 <= n <= 12:
        score = 100.0
    elif n < 5:
        score = clamp(100 - (5 - n) * 20)
    else:
        score = clamp(100 - (n - 12) * 11)
    if chars > 60:                       # two lines of big on-screen text
        score -= 12
    return clamp(score), f"{n} words, {chars} chars, ~{secs:.1f}s spoken (want 5-12 words)"


def check_specificity(text):
    """One concrete thing beats three abstract ones."""
    nums = [n.strip() for n in NUMBER_RE.findall(text) if n.strip()]
    propers = set(PROPER_RE.findall(text))
    low = [w.lower().strip("'’") for w in words(text)]
    spoken = [w for w in low if w in SPOKEN_NUMBERS or w in MONEY_WORDS]
    hits = len(nums) + len(propers) + len(spoken)
    score = 15.0 if hits == 0 else clamp(45 + hits * 30)
    found = ", ".join(nums[:2] + sorted(propers)[:2] + spoken[:2])
    return score, (f"{hits} concrete marker(s)" + (f": {found}" if found else
                   " - no number, no name, nothing checkable"))


def check_stakes(text):
    """Tension, cost, negation. Something the viewer might lose."""
    w = [x.lower().strip("'’") for x in words(text)]
    hits = [x for x in w if x in STAKES]
    markers = sorted(set(hits))
    if re.search(r"\$\s?\d", text):
        markers.append("a price")
    n = len(markers)
    score = {0: 20.0, 1: 70.0}.get(n, 100.0)
    detail = f"{n} tension marker(s)" + (f": {', '.join(markers[:4])}" if markers else
                                         " - nothing is at stake in this line")
    return clamp(score), detail


def check_frontload(text):
    """The interesting word cannot be in position nine."""
    w = words(text)
    if not w:
        return 0.0, "empty"
    low = [x.lower().strip("'’") for x in w]
    opener = " ".join(low[:2])
    penalty = 0
    hit_opener = None
    for weak in WEAK_OPENERS:
        if opener.startswith(weak) or low[0] == weak:
            penalty, hit_opener = 30, weak
            break
    payload = None
    for i, token in enumerate(low):
        if (token in STAKES or token in SPOKEN_NUMBERS or token in MONEY_WORDS
                or NUMBER_RE.match(w[i]) or (i and PROPER_RE.match(w[i]))):
            payload = i
            break
    if payload is None:
        base = 30.0
        where = "no payload word anywhere in the line"
    elif payload <= 3:
        base = 100.0
        where = f"payload at word {payload + 1}"
    elif payload <= 6:
        base = 70.0
        where = f"payload at word {payload + 1}, could move forward"
    else:
        base = 40.0
        where = f"payload at word {payload + 1}, too late"
    detail = where + (f"; weak opener \"{hit_opener}\"" if hit_opener else "")
    return clamp(base - penalty), detail


def check_address(text):
    """Aimed at one viewer, or floating in the air."""
    low = text.lower()
    w = [x.lower().strip("'’") for x in words(text)]
    if re.search(r"\b(you|your|you're|youre|yourself)\b", low):
        return 100.0, "speaks to the viewer"
    if w and w[0] in IMPERATIVES:
        return 90.0, f"imperative opener (\"{w[0]}\")"
    if re.search(r"\b(i|my|me|we|our)\b", low):
        return 70.0, "first person, no viewer named"
    return 35.0, "third person, nobody in the room"


# --- Korean hooks ------------------------------------------------------------
# The checks above count English words. A Korean hook gets the same five
# properties measured in Korean units: eojeol (space-separated chunks) for
# length, syllables for speaking time, and Korean tension vocabulary.
HANGUL_RE = re.compile(r"[가-힣]")
KO_WORD_RE = re.compile(r"[\w$%'’·]+(?:[.,]\d+\w*)*")
KO_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
KO_QUOTE_RE = re.compile(r"[\"“'‘「『][^\"”'’」』]{2,}[\"”'’」』]")
KO_PLACE_RE = re.compile(r"[가-힣]{1,8}(?:고속도로|분기점|공항|병원|경찰서|경찰청|지검|지법|법원"
                         r"|대학교|그룹|은행|시청|구청|군청|도청)")
KO_AMOUNTS = ("억", "조 원", "만 원", "만원", "절반", "두 배", "수십", "수백", "수천", "수만",
              "수억", "역대", "최초")
KO_STAKES = ("사망", "숨져", "숨진", "숨졌", "중상", "부상", "다쳐", "다친", "절단", "체포", "구속",
             "기소", "징역", "실형", "벌금", "논란", "파문", "폭로", "의혹", "경고", "위험", "비상",
             "사고", "참사", "폭발", "화재", "추락", "충돌", "붕괴", "실종", "피해", "손실", "적자",
             "폭락", "급락", "급등", "해고", "금지", "중단", "취소", "거부", "청원", "고발", "고소",
             "소송", "사기", "횡령", "갑질", "학대", "폭행", "살인", "흉기", "총기", "총격", "엽총",
             "맞았", "치여", "치였", "몰래", "비밀", "거짓", "처음", "최악", "결국", "끝내",
             "자주포", "미사일", "포격", "사정권", "겨눈", "겨냥", "도발", "위협", "무력", "전쟁",
             "않", "없", "아니", "못 ", "안 ")
KO_WEAK_OPENERS = ("안녕", "여러분 안녕", "오늘은", "오늘의", "자,", "자 ", "음", "그냥", "혹시",
                   "이번 영상", "지금부터", "솔직히", "있잖아")
KO_SYLLABLES_PER_SEC = 5.5   # read-aloud pace, about 330 syllables a minute
KO_DEALBREAKERS = [
    (re.compile(r"^\s*(?:스크롤\s?멈춰|넘기지\s?마)"),
     "\"스크롤 멈춰\"로 시작. 주목을 달라고 하는 건 아직 못 얻었다는 뜻이다."),
    (re.compile(r"이번 영상에서|오늘 영상에서|알려\s?드릴게요|끝까지 보세요"),
     "영상 예고형 서두. 지우고 결론부터 시작하라."),
    (re.compile(r"^\s*(?:안녕하세요|여러분 안녕)"),
     "인사로 시작. 피드에 인사받으러 온 사람은 없다."),
]


def ko_syllables(text):
    """Hangul syllables, plus about two per digit group or Latin word said aloud."""
    return (len(HANGUL_RE.findall(text)) + 2 * len(KO_NUMBER_RE.findall(text))
            + 2 * len(re.findall(r"[A-Za-z]+", text)))


def ko_stakes(text):
    found = [k.strip() for k in KO_STAKES if k in text]
    return found + (["물음표"] if "?" in text else [])


def ko_check_length(text):
    n = len(KO_WORD_RE.findall(text))
    secs = ko_syllables(text) / KO_SYLLABLES_PER_SEC
    chars = len(text.strip())
    if 3 <= n <= 8:
        score = 100.0
    elif n < 3:
        score = clamp(100 - (3 - n) * 25)
    else:
        score = clamp(100 - (n - 8) * 12)
    if chars > 26:                       # two lines of big on-screen Korean text
        score -= 12
    return clamp(score), f"{n}어절, {chars}자, 말하면 약 {secs:.1f}초 (권장 3-8어절)"


def ko_check_specificity(text):
    nums = KO_NUMBER_RE.findall(text)
    quotes = KO_QUOTE_RE.findall(text)
    places = KO_PLACE_RE.findall(text)
    amounts = [a for a in KO_AMOUNTS if a in text]
    hits = len(nums) + len(quotes) + len(places) + len(amounts)
    score = 15.0 if hits == 0 else clamp(45 + hits * 30)
    found = ", ".join(nums[:2] + quotes[:1] + places[:2] + amounts[:2])
    return score, (f"구체 표지 {hits}개" + (f": {found}" if found else
                   " - 숫자·고유명사·인용 없음"))


def ko_check_stakes(text):
    markers = ko_stakes(text)
    score = {0: 20.0, 1: 70.0}.get(len(markers), 100.0)
    return score, (f"긴장 표지 {len(markers)}개" + (f": {', '.join(markers[:4])}" if markers else
                   " - 걸린 것이 없는 문장"))


def ko_check_frontload(text):
    w = KO_WORD_RE.findall(text)
    if not w:
        return 0.0, "empty"
    weak = next((o for o in KO_WEAK_OPENERS if text.lstrip().startswith(o)), None)
    payload = next((i for i, tok in enumerate(w)
                    if KO_NUMBER_RE.search(tok) or ko_stakes(tok) or KO_PLACE_RE.search(tok)
                    or any(q in tok for q in "\"“'‘「『")), None)
    if payload is None:
        base, where = 30.0, "핵심 단어가 없음"
    elif payload <= 2:
        base, where = 100.0, f"핵심이 {payload + 1}번째 어절"
    elif payload <= 4:
        base, where = 70.0, f"핵심이 {payload + 1}번째 어절, 더 앞으로"
    else:
        base, where = 40.0, f"핵심이 {payload + 1}번째 어절, 너무 늦음"
    return clamp(base - (30 if weak else 0)), where + (f"; 약한 시작 \"{weak.strip()}\"" if weak else "")


def ko_check_address(text):
    if re.search(r"당신|여러분|너희|네가|니가|(?:^|\s)너(?:는|도|만|$|\s)", text):
        return 100.0, "시청자에게 직접 말함"
    if re.search(r"(?:세요|하라|마라|마세요|해라|봐라|봐요|말 것)[.!?]?\s*$", text.strip()):
        return 90.0, "명령형 문장"
    if re.search(r"(?:^|\s)(?:나|내가|내|저는|제가|저|우리)(?:\s|는|가|의|$)", text):
        return 70.0, "1인칭, 시청자는 없음"
    return 35.0, "3인칭 (뉴스형 훅에선 흔함)"


CHECKS = ["LENGTH", "SPECIFICITY", "STAKES", "FRONTLOAD", "ADDRESS"]


def run(text):
    ko = bool(HANGUL_RE.search(text))
    results = {
        "LENGTH": (ko_check_length if ko else check_length)(text),
        "SPECIFICITY": (ko_check_specificity if ko else check_specificity)(text),
        "STAKES": (ko_check_stakes if ko else check_stakes)(text),
        "FRONTLOAD": (ko_check_frontload if ko else check_frontload)(text),
        "ADDRESS": (ko_check_address if ko else check_address)(text),
    }
    flags = [msg for pattern, msg in DEALBREAKERS + (KO_DEALBREAKERS if ko else [])
             if pattern.search(text)]
    scores = [results[c][0] for c in CHECKS]
    # The weakest property caps the hook, same logic as detect.py: one bad
    # property is enough for the thumb to keep moving.
    overall = statistics.mean(scores) * 0.6 + min(scores) * 0.4 - len(flags) * 15
    overall = clamp(overall)
    verdict = "STRONG" if overall >= 70 and min(scores) >= 55 and not flags else (
        "OK" if overall >= 50 else "WEAK")
    return results, overall, verdict, flags


def bar(score, width=24):
    filled = round(score / 100 * width)
    return "#" * filled + "." * (width - filled)


def render_one(text, results, overall, verdict, flags, out=sys.stdout):
    print("\nHOOK SCORE", file=out)
    print("=" * 62, file=out)
    print(f"  \"{text.strip()}\"\n", file=out)
    for name in CHECKS:
        score, detail = results[name]
        print(f"  {name:<13} {bar(score)} {score:5.1f}", file=out)
        print(f"  {'':<13} {detail}", file=out)
    print("-" * 62, file=out)
    print(f"  {'HOOK SCORE':<13} {bar(overall)} {overall:5.1f}   {verdict}", file=out)
    for f in flags:
        print(f"\n  DEALBREAKER  {f}", file=out)
    if verdict != "STRONG":
        weakest = min(CHECKS, key=lambda c: results[c][0])
        print(f"\n  Weakest property: {weakest}. Fix that one and re-run.", file=out)
    print("", file=out)


def render_table(rows, out=sys.stdout):
    print("\nHOOK RANKING\n" + "=" * 78, file=out)
    for i, r in enumerate(rows, 1):
        mark = "->" if i == 1 else "  "
        hook = r["hook"] if len(r["hook"]) <= 62 else r["hook"][:59] + "..."
        print(f"{mark} {r['score']:5.1f} {r['verdict']:<7} {hook}", file=out)
        print(f"        weakest: {r['weakest']} ({r['checks'][r['weakest']]['score']:.0f})", file=out)
        for f in r["flags"]:
            print(f"        dealbreaker: {f}", file=out)
    print("\nShoot the top one. If the top one is under 50, none of these are the hook.\n",
          file=out)


def main():
    ap = argparse.ArgumentParser(description="Score a Reel hook on five properties.")
    ap.add_argument("input", nargs="?", default="-", help="file with one hook per line, or -")
    ap.add_argument("--hook", help="score a single hook given on the command line")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.hook:
        lines = [args.hook]
    else:
        raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
    if not lines:
        print("nothing to score", file=sys.stderr)
        sys.exit(2)

    payload = []
    for line in lines:
        results, overall, verdict, flags = run(line)
        payload.append({
            "hook": line,
            "checks": {k: {"score": round(v[0], 1), "detail": v[1]} for k, v in results.items()},
            "weakest": min(CHECKS, key=lambda c: results[c][0]),
            "flags": flags,
            "score": round(overall, 1),
            "verdict": verdict,
        })

    if args.json:
        print(json.dumps(payload if len(payload) > 1 else payload[0], indent=2, ensure_ascii=False))
        return

    if len(payload) == 1:
        results, overall, verdict, flags = run(lines[0])
        render_one(lines[0], results, overall, verdict, flags)
    else:
        render_table(sorted(payload, key=lambda r: -r["score"]))

    sys.exit(0 if max(p["score"] for p in payload) >= 70 else 1)


if __name__ == "__main__":
    main()
