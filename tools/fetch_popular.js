#!/usr/bin/env node
/*
 * 유튜브 인기 영상 수집기 → popular/data.json
 *
 *   YOUTUBE_API_KEY=... node tools/fetch_popular.js
 *       YouTube Data API v3로 한국·미국·일본 차트(18회, 18단위)와 재사용 허용(CC) 인기 영상
 *       (나라별 검색 1회 100단위 + 상세 1단위, 합 303단위)을 받아 합친다. 하루 기본 할당량은 10,000단위.
 *       키는 X-Goog-Api-Key 헤더로 보낸다.
 *
 *   node tools/fetch_popular.js --ingest a.json b.json ...
 *       PlayMCP YouTubeData 커넥터 응답({regionCode, videos, fetchedAt})을 받은 순서대로 합친다.
 *
 * 옵션: --out <파일>  --regions KR,US,JP  --keep-days 14  --fresh(이전 data.json을 무시)
 *       --no-reusable(재사용 허용 검색을 건너뛰어 18단위만 사용)
 */
'use strict';
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
  console.log(`재사용 허용 영상 ${cc}개, 사용 할당량 약 ${result.units}단위`);
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
  const key = process.env.YOUTUBE_API_KEY;
  if (!key) {
    console.error('YOUTUBE_API_KEY 환경변수가 없습니다. Google Cloud 콘솔에서 YouTube Data API v3 키를 만들어 넣어 주세요.');
    process.exit(2);
  }
  await collectFromApi(key);
})().catch((e) => { console.error(`실패: ${e.message}`); process.exit(1); });
