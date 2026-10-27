# Figma 그림 받기 상태

priamos-daily 0단계가 이 파일을 읽는다. 두 길이 모두 막혔으면 회차를 기사 작업 전에 건너뛴다.

screenshot_blocked_until: 2026-11-01

- 2026-10-28 07:4x KST: `get_screenshot` 이 "Figma MCP tool call limit on the Starter plan"으로 거절됨 (Starter: 읽기 호출 월 20회).
- 같은 시각 www.figma.com 은 환경 네트워크 정책에서 403(차단). `generate_image` 결과의 image.url 을 curl 로 받을 수 없음.
- 풀리는 조건: (1) 환경 네트워크 설정의 Allowed domains 에 www.figma.com 추가, 또는 (2) Figma 플랜 업그레이드, 또는 (3) 월 한도 초기화(날짜는 확실하지 않음).
- 미완성 회차: 20261028-01 (코리아 그랜드 페스티벌). 글·사실 확인 완료, 그림은 Figma 파일 노드 27:2 에 생성됨.
