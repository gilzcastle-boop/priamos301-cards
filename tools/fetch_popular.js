#!/usr/bin/env node
/*
 * 유튜브 인기 영상 수집기 → popular/data.json
 *
 *   YOUTUBE_API_KEY=... node tools/fetch_popular.js   (환경이 키를 대신 넣어 주면 YOUTUBE_API_KEY 없이 실행)
 *       YouTube Data API v3로 한국·미국·일본 차트(18회, 18단위)와 재사용 허용(CC) 인기 영상
 *       (나라별 검색 1회 + 상세 1단위)을 받아 합친다. 키는 X-Goog-Api-Key 헤더로 보낸다.
 *       기본 한도: 검색은 하루 100회, 그 밖의 호출은 합쳐서 하루 10,000단위.
 *       나라 3곳이면 한 번에 검색 3회를 쓰므로 재사용 허용까지 받는 수집은 하루 33번까지 가능하다.
 *
 *   node tools/fetch_popular.js --ingest a.json b.json ...
 *       PlayMCP YouTubeData 커넥터 응답({regionCode, videos, fetchedAt})을 받은 순서대로 합친다.
 *
 * 옵션: --out <파일>  --regions KR,US,JP  --keep-days 14  --fresh(이전 data.json을 무시)
 *       --no-reusable(재사용 허용 검색을 건너뛴다. 검색 한도를 쓰지 않는다)
 */
'use strict';

// 프록시를 거치는 실행 환경(Claude 클라우드 세션 등)에서는 Node 내장 fetch가 프록시를 쓰도록
// NODE_USE_ENV_PROXY=1 을 붙여 한 번 다시 실행한다. 그래야 환경에 저장된 키가 요청에 붙는다. (Node 22.21 이상)
if ((process.env.HTTPS_PROXY || process.env.https_proxy) && !process.env.NODE_USE_ENV_PROXY) {
  const rerun = require('child_process').spawnSync(process.execPath, process.argv.slice(1), {
    stdio: 'inherit', env: Object.assign({}, process.env, { NODE_USE_ENV_PROXY: '1' })
  });
  process.exit(rerun.status == null ? 1 : rerun.status);
}

const fs = require('fs');
const path = require('path');
const core = require('../popular/core.js');

const args = process.argv.slice(2);
function opt(name, fallback) {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
}
const out = path.resolve(opt('--out', path.join(__dirname, '..', 'popular', 'data.json')));
const keepDays = Number(opt('--keep-days', '14'));
const regions = opt('--regions', core.PLAN.regions.join(',')).split(',').filter(Boolean);
const fresh = args.includes('--fresh');
const ingestAt = args.indexOf('--ingest');
const ingestFiles = ingestAt >= 0 ? args.slice(ingestAt + 1).filter((a) => !a.startsWith('--')) : null;

function loadState() {
  if (fresh || !fs.existsSync(out)) return { schema: 1, updatedAt: null, items: [] };
  return JSON.parse(fs.readFileSync(out, 'utf8'));
}

function save(state, source) {
  core.prune(state, state.updatedAt, keepDays);
  state.items.sort((a, b) => (b.viewCount || 0) - (a.viewCount || 0));
  // 영상 한 건을 한 줄에 써서 파일은 작게, 변경 내역은 줄 단위로 보이게 한다.
  const head = JSON.stringify({ schema: 1, updatedAt: state.updatedAt, source }).slice(0, -1);
  const body = state.items.map((it) => JSON.stringify(it)).join(',\n');
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, `${head},"items":[\n${body}\n]}\n`);
  console.log(`${path.relative(process.cwd(), out)}: 영상 ${state.items.length}개, 수집 ${core.fmtStamp(state.updatedAt)} (KST)`);
}

async function collectFromApi(key) {
  const now = new Date().toISOString();
  const result = await core.collectFromApi({ fetch, key, regions, reusable: !args.includes('--no-reusable') });
  if (!result.sightings.length) {
    throw new Error(result.lastError ? result.lastError.message : '받은 영상이 없습니다.');
  }
  const state = core.merge(loadState(), result.sightings, now);
  save(state, 'YouTube Data API v3 (videos.list mostPopular, search.list videoLicense=creativeCommon)');
  const cc = state.items.filter((it) => it.license === 'creativeCommon').length;
  console.log(`재사용 허용 영상 ${cc}개, 사용량: ${result.units}단위, 검색 ${result.searches}회`);
  if (result.failed.length) {
    console.warn(`받지 못한 차트: ${result.failed.join(', ')}${result.lastError ? ' — ' + result.lastError.message : ''}`);
  }
}

function ingest(files) {
  const batches = files.map((f) => JSON.parse(fs.readFileSync(f, 'utf8')))
    .filter((b) => b && b.fetchedAt && Array.isArray(b.videos))
    .sort((a, b) => Date.parse(a.fetchedAt) - Date.parse(b.fetchedAt));
  if (!batches.length) throw new Error('합칠 응답 파일이 없습니다 (fetchedAt, videos 필요).');
  let state = loadState();
  for (const b of batches) {
    state = core.merge(state, core.sightingsFromTool(b, b.regionCode), b.fetchedAt);
  }
  save(state, 'PlayMCP YouTubeData get_trending_videos (YouTube Data API mostPopular)');
}

(async () => {
  if (ingestFiles) return ingest(ingestFiles);
  // 키를 환경변수로 주지 않았으면 자리표시 값을 보낸다. 실행 환경이 www.googleapis.com 요청의
  // X-Goog-Api-Key 헤더에 저장된 키를 대신 넣어 주는 경우(네트워크 시크릿) 그대로 동작한다.
  const key = process.env.YOUTUBE_API_KEY || 'set-by-environment';
  await collectFromApi(key);
})().catch((e) => {
  console.error(`실패: ${e.message}`);
  if (/API key not valid|unregistered callers/i.test(e.message)) {
    console.error('YouTube Data API 키가 전달되지 않았습니다. YOUTUBE_API_KEY 환경변수를 넣거나, 실행 환경의 네트워크 시크릿에 '
      + 'www.googleapis.com / X-Goog-Api-Key 로 키를 저장해 주세요.');
  }
  process.exit(1);
});
