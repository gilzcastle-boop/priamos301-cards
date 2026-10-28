# Figma 그림 받기 상태

priamos-daily 0단계가 이 파일을 읽는다. 두 길이 모두 막혔으면 회차를 기사 작업 전에 건너뛴다.

screenshot_blocked_until: 2026-11-01

- 2026-10-28 07:4x KST: `get_screenshot` 이 "Figma MCP tool call limit on the Starter plan"으로 거절됨 (Starter: 읽기 호출 월 20회).
- 2026-10-28 16:29 KST: 사용자가 환경 네트워크에 www.figma.com 을 허용함. `generate_image` 의 image.url 을 curl 로 받는 길이 열림(한도와 무관). 0단계 확인은 이제 통과한다.
