# Figma 그림 받기 상태

priamos-daily 0단계가 이 파일을 읽는다. 두 길이 모두 막혔으면 회차를 기사 작업 전에 건너뛴다.

screenshot_blocked_until: 2026-11-01

- 2026-10-28 07:4x KST: `get_screenshot` 이 "Figma MCP tool call limit on the Starter plan"으로 거절됨 (Starter: 읽기 호출 월 20회).
- 2026-10-28 16:29 KST: 사용자가 환경 네트워크에 www.figma.com 을 허용함. `generate_image` 의 image.url 을 curl 로 받는 길이 열림(한도와 무관). 0단계 확인은 이제 통과한다.
- 2026-11-26 21:5x KST: 사용자가 Figma "AI 크레딧" 화면을 확인함. 월간 316/500 사용, 일일 6/150 사용(Starter 플랜 View 좌석: 월 500, 하루 150. help.figma.com/hc/en-us/articles/33459875669015). 그림 1장에 2크레딧(gpt-image-2.5-sunburst)이고, 일일 숫자는 UTC 기준 그날 만든 3장과 맞는다. 기록상 10/30 이후 쓴 양이 약 304크레딧이라 이번 주기는 10월 말~11월 1일쯤 시작한 것으로 보인다(초기화 날짜는 화면에서 확인 못 함). 하루 5장에 다시 그리기를 더하면 한 달 약 340크레딧이라 한도 안이다. 월 450을 넘긴 것이 확인되면 다시 그리기를 아끼고 사용자에게 알린다.
