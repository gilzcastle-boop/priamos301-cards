---
name: priamos-daily
description: >-
  @priamos301 자동 뉴스 게시 1회분. 지금 화제인 한국 뉴스 1건을 골라 두 곳 이상에서
  사실을 확인하고, Figma로 그림을 그려 5장 캐러셀 카드뉴스(1080x1350)와 11초 릴스를 만들고,
  캡션을 점검한 뒤 저장소에 올려 카드와 릴스를 게시하고 기록·보고한다.
  예약 작업이 "priamos-daily 1회 실행"을 요청하거나 사용자가 "뉴스 하나 만들어 올려"라고 할 때 쓴다.
---

# priamos-daily: 뉴스 1건 → 카드 + 릴스 게시

사용자는 "카드뉴스랑 릴스 둘다 올리자", "자동으로 니가 올려줬음 좋겠는데"라고 자동 게시를 승인했다.
이 절차를 그대로 따르고, 한 단계라도 막히면 **게시하지 말고 건너뛴 이유를 보고**한다. 빈 회차가 틀린 게시물보다 낫다.

## 0. 준비와 중단 조건

```bash
cd /home/user/priamos301-cards && git pull origin main
D=$(TZ=Asia/Seoul date +%Y%m%d)                     # 오늘 날짜(한국)
W=$(mktemp -d)                                       # 작업 폴더 (저장소 밖)
```

- 다음 번호 `NN`: `cards/$D-NN.jpg` 중 가장 큰 번호 + 1 (없으면 01, 두 자리). `-c1.jpg` 처럼 끝에 `-cN` 이 붙은 캐러셀 슬라이드는 세지 않는다.
- 아래 중 하나라도 해당하면 이번 회차는 건너뛰고 보고만 한다.
  - `log/posted.md`에서 오늘(한국 날짜) 시각 칸에 `자동`이 붙은 행이 이미 5개 이상 있다(사용자가 직접 요청한 게시는 세지 않는다).
  - API 게시 한도: `GET https://graph.instagram.com/v26.0/<ig_id>/content_publishing_limit?fields=quota_usage,config`
    (`ig_id`는 `/me?fields=user_id`)의 `quota_usage`가 `config.quota_total`의 절반을 넘었다.
  - 예약 작업 프롬프트가 지금 회차를 건너뛰라고 했다.

## 1. 뉴스 고르기

후보 모으기:
- `HANKOOKILBO_MCP` 의 `list_most_read_news`, `list_popular_news`(section_cd "all"), `list_top_headlines`
- `firecrawl_search` 로 "오늘 화제 사건" 류 검색 (한국 언론 기사만)

고르는 기준: 최근 24시간 안의 사건·사회·연예·정치·국제 이슈 중, 한 문장으로 놀라움이 전해지고 사람들이 공유할 만한 것.

**주제 우선순위** (2026-10-26 실적 분석, priamos-weekly 가 매주 고친다):
팔로워가 거의 없어 조회는 전부 비팔로워 추천에서 나온다. 릴스 11개 중앙값 125회에서 위로 튄 것은
"상어 찍으려 배 빌린 유튜버가 국가보안시설 촬영"(4.9배), "'닥터X' 5·18 회차 방영 중단 청원"(2.1배), "승리 소주병"(1.5배)이었고,
정치 공방·북한·해외 사건·스포츠 기록은 모두 0.9~1.1배였다.
1. **우선**: "어? 왜?"가 나오는 사람 이야기, 기묘한 사건, 연예·방송·문화 논란, 생활·돈 화제(복권, 물가, 소비자 피해)
2. **보통**: 사건·사고, 사회, 국제 화제
3. **줄임**: 정치인 공방, 선거, 북한·안보, 법안·정책. 인스타그램은 정부·선거·사회적 쟁점을 다룬 "정치 콘텐츠"를 비팔로워에게 개인 신호와 각자의 설정(적게/표준/많이)에 따라서만 추천한다(help.instagram.com/339680465107440). 하루 1건까지만, 그날 가장 큰 뉴스일 때만 고른다
오늘 `log/posted.md` 의 자동 회차를 보고, 같은 분류가 3번 연속되지 않게 고른다.

**제외** (예외 없음):
- 자살·자해 사건, 성범죄 피해 상세, 미성년자가 특정될 수 있는 사건, 참사 희생자 신상
- 한 곳만 보도한 단독·루머, 확인 안 된 SNS 폭로, 혐오를 부추기는 기사
- 의료·투자 조언이 되는 기사
- `log/posted.md` 또는 `/me/media` 캡션 첫 줄에 이미 있는 주제

**사실 확인**: 후보 기사 본문을 `firecrawl_scrape` 로 읽고, **다른 언론사 기사 1곳 이상**에서 핵심 사실(숫자, 날짜, 장소, 누가 무엇을)을 확인한다.
두 기사가 다르면 넓은 표현을 쓰거나("수십 명") 그 사실을 빼고, 그래도 안 되면 다음 후보로 간다. 후보 5개가 모두 안 되면 이번 회차는 건너뛴다.

**표현 규칙**:
- 수사·재판 중인 일은 "혐의", "주장", "~로 전해졌습니다". 단정하지 않는다. 양쪽 입장이 있으면 둘 다 쓴다.
- 일반인은 실명 대신 A씨. 공인(정치인·연예인·기관장)은 기사대로 실명.
- 기사에 없는 숫자·결말·해석을 지어내지 않는다.

## 2. 글 만들기

사용자는 "카드뉴스 릴스 둘다 후킹이 있게 자극적으로"를 원한다. **자극은 사실로 만든다**: 숫자, 직접 인용, 대비, 질문.
"충격·경악·소름" 같은 형용사로 때우거나, 기사에 없는 과장·반전을 숨겨 두는 낚시는 하지 않는다(메타가 클릭베이트로 노출을 줄인다).

훅 공식 (하나를 고른다):
| 공식 | 예 |
|---|---|
| 질문 | 의학드라마에 5·18? / "방영 중단하라" 국회 청원 |
| 직접 인용 | 추미애 "화형을 당하더라도" / 이준석 "소방만 자꾸 도발" |
| 대비·반전 | 노루 잡으려 쏜 총에 / 80대가 맞았다 |
| 숫자 | 사거리 15~24㎞ / 경기 북부가 사정권 |
| 거리감 | 김포에서도 보인다 / 남쪽 겨눈 北 자주포 |
| 반복 | 2차 사고 막던 경찰관 (도장: 1월 이어 또) |

**우선**: 대비·반전("상어 찍으려 배 빌린 유튜버 / 국가보안시설 찍다 적발", 4.9배)과 질문("의학드라마에 5·18?", 2.1배)을 먼저 시도한다. 숫자만 앞세운 훅은 1.0배 근처였다.

| 항목 | 규칙 |
|---|---|
| 분류(label) | 사건 / 이슈 / 정치 / 연예 / 사회 / 국제 중 하나 |
| 도장(stamp) | 그림 위 빨간 도장, 6자 안팎의 사실 한 토막. 예: "시청률 19.5%", "설전", "1월 이어 또", "국회 청원" |
| 카드 제목(headline) | `"1줄\n[빨간 강조 2줄]"`, 각 줄 14자 안팎. 인용은 기사 문장에서 이어진 토막만 따옴표에 넣는다 |
| 카드 사실(facts) | 3~4개, `[키워드, 한 줄]`. 키워드 2~3자(어디서·무엇이·장면·청원·반격·상태…), 한 줄 30자 안팎. 캐러셀 마지막 장(한눈에 정리)이 된다 |
| 캐러셀 요점(points) | 정확히 3개, `[머리말, 제목, 본문]`. 머리말 2~5자(무슨 일 / 쟁점·숫자 / 그다음·반대 입장), 제목 2줄 각 14자 안팎(`\n`), 본문 70자 안팎 "~습니다"체. 한 장에 한 가지만 |
| 릴스 line1 / line2 | 12자 / 14자 안팎. line1이 질문·인용·긴장, line2가 결과. 첫 프레임부터 화면에 나온다 |
| 릴스 sub | 장소 · 날짜 |
| 릴스 subs | 2장면, 장면마다 2줄, 줄마다 16자 안팎(11초 릴스. 시청자가 평균 5초 안팎에서 넘겨서 짧게 줄였다) |
| 릴스 mood | 배경음(직접 합성한 원곡, 저작권 문제 없음). 사건·사고 `tense`, 사망·참사 `somber`, 정치·국제·북한 `mystery`, 스포츠·좋은 소식 `upbeat`, 연예·가벼운 이슈 `lofi` |

캡션(`$W/caption.txt`):
```
<제목 40자 이내, 핵심 검색어 포함> <이모지 1개>

<본문 5~8문장, "~습니다" 체, 문단 사이 빈 줄>

<마무리 1줄: 열린 질문(예: 여러분은 어떻게 생각하세요?) 또는 목적 있는 행동(예: 사고 현장을 보면 속도를 줄여 주세요)>

#구체적 #해시태그 #정확히 #다섯 #개
```
- 언론사 이름이나 출처 줄은 넣지 않는다. "경찰에 따르면"처럼 기관 출처는 괜찮다.
- `#이슈 #속보 #뉴스 #릴스 #추천` 같은 일반 태그는 쓰지 않는다.
- "좋아요·공유·댓글·태그 해 주세요"처럼 목적 없이 반응만 요구하지 않는다(메타 'engagement bait'). 질문이나 안전 행동은 괜찮고, 그래서 linter의 ONE ASK 경고는 무시해도 된다.
- 점검: `python3 -I .claude/skills/ig-caption/caption.py $W/caption.txt --keywords "검색어1,검색어2"` → `VERDICT READY` 가 될 때까지 고친다.
- 기계 흔적 정리: `python3 -I .claude/skills/ig-human/humanize.py $W/caption.txt --report` 로 보이지 않는 문자·굽은 따옴표를 지운다(바뀐 내용을 확인하고 덮어쓴다). 한국어 문장은 `detect.py` 점수가 낮게 나오기 쉬우니 점수는 참고만 하고, 같은 길이 문장만 이어지지 않게 짧은 문장을 한두 개 섞는다.
- 훅 점검: `python3 -I .claude/skills/ig-reel/hookscore.py --hook "<line1> <line2>"`. **55점** 미만이면 다른 공식으로 다시 쓴다.

### 2-1. 독립 사실 확인 (fact-checker 에이전트, 그림 전에)

글(`caption.txt`, `card.json`, `reel.json` — 그림 경로는 비워 둔 채)을 `$W` 에 쓴 뒤, Agent 도구로 `subagent_type: "fact-checker"` 를 부른다.
프롬프트: `작업 폴더 $W, 출처 <기사 주소 1> <기사 주소 2>. 판정해 줘.`
`fact-checker` 유형이 목록에 없다고 나오면(세션이 에이전트 파일보다 먼저 시작된 경우) `subagent_type: "general-purpose"`, `model: "sonnet"` 으로 부르고, 프롬프트 앞에 `.claude/agents/fact-checker.md` 의 본문(--- 아래 전부)을 그대로 붙인다.
- `PASS` → 다음 단계.
- `FIX` → 지적한 문구를 그대로 고치고, caption.py·hookscore 를 다시 돌린 뒤 다음 단계(다시 부르지 않는다).
- `FAIL` → 이 뉴스는 버리고 1단계에서 다음 후보로. 두 번째 후보도 FAIL 이면 회차를 건너뛴다.
그림(크레딧)은 사실 확인을 통과한 뒤에만 만든다.

## 3. 그림 (Figma, 1장에 2크레딧)

1. `create_session` — fileKey `4QiH37pw3t7wlqYLwdE1xQ`, description에 오늘 장면 요약.
2. `generate_image` — fileKey 같음, sessionId, model `gpt-image-2.5-sunburst`, width 1536, height 1024, prompt = 아래 STYLE + `\nScene: <장면>` + RULES.
3. `get_screenshot` — fileKey, nodeId(2번 결과), sessionId, maxDimension 1536, enableBase64Response true, contentsOnly true.
   PNG는 `~/.claude/projects/*/*/tool-results/mcp-Figma-blob-*.png` 중 가장 최근 파일로 저장된다. `$W/art.png` 로 복사하고 1536x1024인지 확인한다.
4. 그림을 직접 열어 본다. 글자가 섞였거나, 실존 인물처럼 보이거나, 피가 보이면 한 번만 다시 만든다. 그래도 안 되면 건너뛴다.

STYLE (그대로 쓴다):
```
Hand-drawn Japanese TV anime illustration in a warm retro 1980s-90s cel animation style: thin, slightly rough pencil line art, flat cel colors with simple two-tone shading, warm orange, tomato red and muted teal palette, soft film grain and faded print texture, nostalgic mood, a highly detailed lived-in background. Blended with a 1950s American magazine advertisement feel: bold simple shapes and cream paper tones.
```
RULES (그대로 쓴다):
```
Many small, carefully drawn details. Wide 3:2 composition. Absolutely no text, letters, numbers, logos or watermarks anywhere. No real or famous people. No blood or gore.
```
장면은 사건의 순간이나 상징(장소, 물건, 원래 창작 인물)으로 그린다. 정치인·연예인 본인은 그리지 않는다.

### 3-1. 예비: Runway (Figma가 안 될 때만, 1장에 8크레딧)

> **쓰지 않는다.** 사용자가 Runway 그림을 보고 "그림체가 너무 다르자나", 이어서 "됐다 필요하면 유료로 전환할게"라고 했다. Figma가 실패한 회차는 Runway로 넘어가지 말고 건너뛴다. 사용자가 다시 켜라고 할 때만 아래 절차를 쓴다(그때는 `assets/style-ref-1.jpg`, `style-ref-2.jpg` 를 raw.githubusercontent 주소로 referenceImages 에 넣어 그림체를 맞춘다).

사용자가 "런웨이 예비로 붙여놔"라고 승인했다. **Figma가 오류를 내거나 크레딧이 부족할 때, 또는 Figma 그림이 다시 그려도 4번 검사를 통과하지 못할 때만** 쓴다. Figma가 되면 Runway는 쓰지 않는다(무료 플랜이라 크레딧이 다시 채워지지 않는다).
1. `mcp__runway__generate_image` — model `gen-4`, ratio `4:3`, promptText = 위 STYLE + `\nScene: <장면>` + RULES (같은 문장 그대로).
   다른 모델(Seedream 등)은 무료 플랜에서 막혀 있으니 바꾸지 않는다.
2. `mcp__runway__get_task` (id = 1번의 taskId) 를 20~30초 간격으로 불러 `SUCCEEDED`(그림이 보이는 응답)가 될 때까지 기다린다. 보통 1분 안팎.
   그림은 `~/.claude/projects/*/*/tool-results/mcp-runway-blob-*.jpg` 중 가장 최근 파일(1440x1080)로 저장된다. 응답의 cloudfront 주소는 네트워크에서 막혀 있으니 내려받으려 하지 않는다.
3. `python3 tools/fit_art.py <그 jpg> $W/art.png 0.5` → 1536x1024로 잘라 맞춘다(세 번째 값은 남길 세로 위치, 0 위 ~ 1 아래).
4. 위 4번과 같은 기준으로 그림을 직접 열어 본다. Runway는 한 번만 시도한다.

Figma와 Runway가 모두 실패하거나(Runway 크레딧 8 미만, 유료 플랜 필요 오류 포함) 그림이 검사를 통과하지 못하면 그림 없이 게시하지 말고 건너뛴다.
보고에는 어느 도구로 그렸는지(Figma / Runway 예비)와 Runway를 썼다면 남은 크레딧(`get_task`/`generate_image` 응답의 `creditsRemaining`)을 적는다.

## 4. 렌더

카드는 **5장 캐러셀(카드뉴스)** 로 만든다: 1장 표지 → 2~4장 요점 하나씩 → 5장 정보 카드(한눈에 정리).
단일 이미지는 10-25~26 게시분 11개의 도달이 1~2명(사실상 팔로워만)이라 캐러셀로 바꿨다. 넘기는 동작이 반응으로 잡히고, 프로필에 들어온 사람이 저장하기 좋다.
**확실하지 않은 사실**: Mosseri가 "캐러셀은 음악이 있어야 추천 대상이 된다"고 했다는 제3자 기록이 있다. 그런데 게시 API로는 캐러셀에 음악을 넣을 수 없다. 그래서 비팔로워 확산은 계속 릴스가 맡는다고 보고, 캐러셀 도달은 priamos-weekly 가 확인한다.

`$W/card.json` 하나로 다섯 장을 다 만든다. `focus`는 그림에서 보일 부분(세로 위치), `badge`는 분류 딱지 위치("right"/"left").
딱지(오른쪽 위)와 도장(그림 왼쪽 아래)이 그림의 주인공을 가리면 `focus`나 `badge`를 바꿔 다시 그린다:
```json
{"label": "사건", "stamp": "1월 이어 또", "headline": "2차 사고 막던 경찰관\n[화물차에 치여 발목 절단]",
 "facts": [["언제", "24일 새벽 영동고속도로 여주분기점(인천 방향)"],
           ["사고", "현장 수습하던 고속도로순찰대 A 경위, 6.5t 화물차에 치여"],
           ["상태", "발목 절단 중상, 긴급 수술… 생명엔 지장 없어"],
           ["또", "1월엔 서해안고속도로서 사고 조사하던 경정 숨져"]],
 "points": [["무슨 일", "2차 사고 막던 경찰관\n화물차에 치였다", "24일 새벽 영동고속도로 여주분기점에서 사고 현장을 수습하던 고속도로순찰대 A 경위가 6.5t 화물차에 치였습니다."],
            ["상태", "발목 절단 중상\n생명엔 지장 없어", "A 경위는 발목이 절단되는 중상을 입고 긴급 수술을 받았습니다. 생명에는 지장이 없는 것으로 전해졌습니다."],
            ["1월 이어 또", "재발 방지 대책에도\n비슷한 사고 잇따라", "1월에는 서해안고속도로에서 사고를 조사하던 경정이 숨졌습니다. 2차 사고를 막을 대책이 다시 거론됩니다."]],
 "image": "<$W/art.png 절대경로>", "focus": "50% 40%", "badge": "right"}
```
```bash
NODE_PATH=$(npm root -g) node tools/render_carousel.js $W/card.json cards/$D-$NN      # c1(표지)~c4(요점). "overflow" 가 나오면 요점을 줄인다
NODE_PATH=$(npm root -g) node tools/render_info_card.js $W/card.json cards/$D-$NN.jpg # 5장째. "facts overflow" 가 나오면 사실을 줄인다
```

릴스 spec (`$W/reel.json`) — **11초**. line1은 0초에 쾅 하고 뜨고(줌 펀치 + 쿵 소리), 도장이 0.3초에, line2가 `line2At`(1.0초)에 빨간 번쩍임과 함께 들어온다.
훅은 4초까지 보이고, 자막 2장면이 3초씩, 10.3초부터 끝 화면이 나온다. 10-26까지 16.5초 릴스는 평균 시청이 3.8~6.7초라 뒤쪽 절반을 거의 못 봤다.
`pan` 은 `[초, 그림 x, 그림 y, 확대]` (그림 좌표는 1536x1024 기준). 주인공에서 시작해 장면을 훑고 9.6초쯤 전체(768, 512, 1.0)로 빠진다:
```json
{"date": "2026. 10. 25.", "handle": "@priamos301", "label": "사건",
 "line1": "2차 사고 막던 경찰관", "line2": "화물차에 치여 발목 절단", "sub": "영동고속도로 여주분기점 · 24일 새벽",
 "stamp": "1월 이어 또", "mood": "tense", "line2At": 1.0, "headOut": 4.0, "endAt": 10.3, "duration": 11.0,
 "pan": [[0, 200, 430, 1.2], [2.0, 440, 600, 1.15], [4.0, 1040, 480, 1.12], [7.0, 1000, 470, 1.15], [9.6, 768, 512, 1.0], [11.0, 768, 512, 1.0]],
 "subs": [[4.3, 7.3, "교통 통제하다 6.5t 화물차에 치여\n발목 절단, 생명엔 지장 없어"], [7.3, 10.3, "1월에도 고속도로서 경정 숨져\n비슷한 사고 잇따라"]],
 "image": "<$W/art.png 절대경로>"}
```
```bash
tools/make_reel.sh $W/reel.json reels/$D-$NN.mp4      # 약 1분
cp $W/caption.txt cards/$D-$NN.txt && cp $W/caption.txt reels/$D-$NN.txt
```

게시 전에 눈으로 확인한다: 캐러셀 다섯 장을 열어 보고, 릴스는 아래 시트를 열어 본다. 글자가 잘리거나 넘치면 spec을 고쳐 다시 만든다.
```bash
ffmpeg -v error -y -i reels/$D-$NN.mp4 -vf "select='eq(n\,30)+eq(n\,100)+eq(n\,170)+eq(n\,260)',scale=270:480,tile=4x1" -frames:v 1 -vsync vfr $W/sheet.jpg
```

## 5. 게시

1. `git add cards/$D-$NN* reels/$D-$NN.*` → 커밋(세션의 커밋 서명 규칙을 따른다) → `git push -u origin main`.
2. 캐러셀 다섯 장(`cards/$D-$NN-c1.jpg`~`-c4.jpg`, `cards/$D-$NN.jpg`)과 릴스 mp4의 `https://raw.githubusercontent.com/gilzcastle-boop/priamos301-cards/main/...` 주소가 모두 200인지 확인한다.
3. `/me/media` 에서 같은 캡션 첫 줄이 유형별(CAROUSEL_ALBUM / VIDEO)로 이미 있으면 그 유형은 올리지 않는다.
4. 캐러셀 먼저, 릴스 나중(릴스가 프로필 맨 위에 오도록):
   ```bash
   python3 tools/publish.py cards/$D-$NN.jpg --carousel
   python3 tools/publish.py reels/$D-$NN.mp4     # 처리에 몇 분 걸림, 백그라운드로
   ```
   하나가 실패해도 나머지는 진행하고, 오류는 그대로 보고한다. 캐러셀이 실패하면 `--carousel` 없이 정보 카드 한 장으로 한 번 더 시도한다.

## 6. 기록과 보고

- `log/posted.md` 표에 한 줄 추가: 날짜, 번호, 시각(한국, 예약 작업이 돌린 회차면 `06:58 자동`처럼 `자동`을 붙인다), 분류, 제목, 출처 기사 주소 2개, 카드(캐러셀) 링크, 릴스 링크, `훅 공식 / mood / 릴스 길이`(예: `대비·반전 / tense / 11s`). 커밋하고 push. 마지막 칸은 priamos-weekly 가 무엇이 통했는지 가르는 데 쓴다.
- 한국어로 짧게 보고: 올린 제목과 링크 2개, 확인한 출처 2곳, fact-checker 판정, 고른 훅 공식과 배경음, 건너뛴 후보와 이유. 끝에 "내가 읽어야 할 것" / "내가 해야하는 것".

## 하지 않는 것

게시물 삭제, 프로필 변경, 댓글·DM, 그림 없는 게시, 출처 2곳 확인 없는 게시, 하루 자동 5건 초과.
사용자가 "자동 게시 멈춰"라고 하면 `list_triggers` 로 "자동 뉴스 게시" 예약을 찾아 `update_trigger` 로 `enabled: false` 로 바꾼다.
